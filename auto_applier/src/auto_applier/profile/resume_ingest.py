"""Build a master profile.yaml + base_resume.md from a folder of resumes.

The flow:
  1. Walk a source dir for .pdf / .docx / .txt / .md resumes.
  2. Extract plain text from each.
  3. Dedupe near-identical resumes (rapidfuzz token_set_ratio on first ~2KB).
  4. For each unique resume: Haiku extracts structured Profile fragments.
  5. Sonnet merges all fragments + the comprehensive raw text of the
     longest/strongest resume into one canonical Profile + base_resume.md.

Designed to handle ~200 resumes that are mostly variations of 5-10 base
resumes. Total cost typically ~$1-3 with prompt caching.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import anthropic
import yaml
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from .. import budget as _budget
from .. import config as _config
from ..utils.logging import get_logger
from .schema import Profile

log = get_logger(__name__)

SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md"}


@dataclass
class ResumeDoc:
    path: Path
    text: str
    char_len: int


class _PartialProfile(BaseModel):
    """What Haiku extracts per-resume — a superset of facts to merge later."""

    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    notes: str = ""


_EXTRACT_INSTRUCTIONS = """\
You are parsing a single resume into structured JSON. Extract ALL factual content
from the resume. Don't paraphrase or summarize — preserve the candidate's actual
phrasing, numbers, and bullet wording so we can reuse them later.

Return a JSON object matching this shape:
{
  "summary": str,                 # the resume's own summary/objective if present
  "skills": [str],                # all skills/keywords mentioned
  "technologies": [str],          # languages, frameworks, platforms, tools
  "experience": [
    {"company": str, "title": str, "start": "YYYY-MM" or "YYYY",
     "end": "YYYY-MM"|"YYYY"|null, "location": str,
     "bullets": [str]}            # preserve the EXACT bullet wording, including numbers
  ],
  "projects": [{"name": str, "description": str, "url": str, "bullets": [str]}],
  "education": [{"institution": str, "degree": str, "field": str,
                 "start": str, "end": str, "gpa": number|null, "honors": [str]}],
  "certifications": [str],
  "notes": str                    # anything that didn't fit (awards, languages, etc.)
}

Rules:
- NEVER invent content. If a field isn't in the resume, leave it empty / null.
- Bullets must be verbatim from the source.
- Return ONLY the JSON object. No prose.
"""

_MERGE_INSTRUCTIONS = """\
You are given multiple structured extractions from many versions of one
candidate's resume, plus the raw text of the most comprehensive version.
Produce a SINGLE master profile and a SINGLE strong base resume.

Return a JSON object with this shape:
{
  "profile": {<a Profile object — see schema below>},
  "base_resume_md": str    # markdown resume, the candidate's strongest comprehensive version
}

Rules for the profile:
- Union of all skills / technologies / fundamentals across versions (deduped).
- For experience: one entry per (company, title, dates) — merge bullets across
  versions, dedupe near-identical bullets, keep the strongest phrasings.
- Preserve exact bullet wording when possible — don't paraphrase.
- Aim for 5-8 bullets per role (best ones across all versions).
- Set target_titles based on titles the candidate has actually held + similar.
- Fill qa_bank with reasonable answers for the standard questions in the schema
  (sponsorship, salary, work auth) leaving them blank if unclear from the resumes.

Rules for base_resume_md:
- Markdown, ATS-friendly, single-column.
- Include: name + contact, summary, experience (most recent first), skills,
  projects (if relevant), education.
- Pull from the master profile you just built — don't add new content.

Profile schema (Pydantic):
""" + json.dumps(Profile.model_json_schema(), indent=2) + """

Return ONLY the JSON object.
"""


def _strip_pdf(path: Path) -> str:
    from pdfminer.high_level import extract_text

    try:
        return extract_text(str(path)) or ""
    except Exception as e:  # noqa: BLE001
        log.warning("pdf parse failed for %s: %s", path.name, e)
        return ""


def _strip_docx(path: Path) -> str:
    from docx import Document

    try:
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:  # noqa: BLE001
        log.warning("docx parse failed for %s: %s", path.name, e)
        return ""


def _read_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _strip_pdf(path)
    if ext in (".docx", ".doc"):
        return _strip_docx(path)
    if ext in (".txt", ".md"):
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    return ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def collect_resumes(src_dir: Path) -> list[ResumeDoc]:
    docs: list[ResumeDoc] = []
    files = [p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    log.info("ingest: found %d candidate files in %s", len(files), src_dir)
    for p in sorted(files):
        text = _read_text(p)
        if len(text.strip()) < 200:
            log.info("skipping %s (too short / unparseable)", p.name)
            continue
        docs.append(ResumeDoc(path=p, text=text, char_len=len(text)))
    return docs


def dedupe_resumes(docs: list[ResumeDoc], threshold: int = 88) -> list[ResumeDoc]:
    """Drop near-duplicate resumes. When two are similar, keep the longer one."""
    docs = sorted(docs, key=lambda d: d.char_len, reverse=True)
    kept: list[ResumeDoc] = []
    norms: list[str] = []
    for d in docs:
        sample = _normalize(d.text)[:2500]
        is_dup = False
        for n in norms:
            if fuzz.token_set_ratio(sample, n) >= threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(d)
            norms.append(sample)
    log.info("ingest: deduped %d -> %d unique resumes", len(docs), len(kept))
    return kept


def _client() -> anthropic.Anthropic:
    if not _config.settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=_config.settings.anthropic_api_key)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    return t.strip()


def _extract_one(client: anthropic.Anthropic, doc: ResumeDoc, model: str) -> _PartialProfile:
    _budget.assert_under_budget("ingest")
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _EXTRACT_INSTRUCTIONS,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"<resume filename=\"{doc.path.name}\">\n{doc.text[:18000]}\n</resume>\n"
                    "Return the JSON object."
                ),
            }
        ],
    )
    _budget.record_from_response(stage="ingest", model=model, usage=resp.usage)
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(_strip_fences(text))
    return _PartialProfile.model_validate(data)


def extract_all(
    docs: list[ResumeDoc], model: Optional[str] = None, max_workers: int = 6
) -> list[tuple[ResumeDoc, _PartialProfile]]:
    client = _client()
    model = model or _config.settings.score_model  # Haiku
    out: list[tuple[ResumeDoc, _PartialProfile]] = []

    def task(doc: ResumeDoc) -> tuple[ResumeDoc, _PartialProfile] | None:
        try:
            return doc, _extract_one(client, doc, model)
        except Exception as e:  # noqa: BLE001
            log.warning("extract failed for %s: %s", doc.path.name, e)
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(task, d) for d in docs]
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                out.append(res)
    return out


def merge_to_master(
    extractions: list[tuple[ResumeDoc, _PartialProfile]],
    model: Optional[str] = None,
) -> tuple[Profile, str]:
    if not extractions:
        raise RuntimeError("no resumes successfully extracted; nothing to merge")

    # Pick the longest resume as the canonical raw reference.
    canonical = max(extractions, key=lambda pair: pair[0].char_len)[0]
    extractions_payload = [
        {"source": doc.path.name, "extracted": p.model_dump()}
        for doc, p in extractions
    ]

    user_text = (
        "<extractions>\n"
        + json.dumps(extractions_payload, indent=2)
        + "\n</extractions>\n\n"
        + f"<canonical_resume filename=\"{canonical.path.name}\">\n"
        + canonical.text[:20000]
        + "\n</canonical_resume>\n\nReturn the JSON object."
    )

    _budget.assert_under_budget("ingest")
    client = _client()
    use_model = model or _config.settings.tailor_model
    resp = client.messages.create(
        model=use_model,  # Sonnet
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": _MERGE_INSTRUCTIONS,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    _budget.record_from_response(stage="ingest", model=use_model, usage=resp.usage)
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(_strip_fences(text))

    profile = Profile.model_validate(data["profile"])
    base_resume_md = data["base_resume_md"]
    return profile, base_resume_md


def write_outputs(profile: Profile, base_resume_md: str) -> tuple[Path, Path]:
    profile_path = _config.settings.profile_path
    resume_path = _config.settings.base_resume_path

    profile_path.parent.mkdir(parents=True, exist_ok=True)

    profile_yaml = yaml.safe_dump(
        profile.model_dump(), sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    profile_path.write_text(profile_yaml, encoding="utf-8")
    resume_path.write_text(base_resume_md, encoding="utf-8")
    return profile_path, resume_path


def ingest(
    src_dir: Path,
    *,
    dry_run: bool = False,
    extract_model: Optional[str] = None,
    merge_model: Optional[str] = None,
    max_workers: int = 6,
) -> dict:
    """Top-level entry point. Returns stats."""
    src_dir = Path(src_dir).expanduser().resolve()
    if not src_dir.exists():
        raise FileNotFoundError(f"ingest source dir not found: {src_dir}")

    docs = collect_resumes(src_dir)
    if not docs:
        raise RuntimeError(f"no parseable resumes in {src_dir}")
    deduped = dedupe_resumes(docs)
    stats = {
        "files_found": len(docs),
        "unique_after_dedupe": len(deduped),
        "src": str(src_dir),
    }

    if dry_run:
        stats["sample"] = [d.path.name for d in deduped[:10]]
        return stats

    extractions = extract_all(deduped, model=extract_model, max_workers=max_workers)
    stats["extracted"] = len(extractions)

    profile, base_resume_md = merge_to_master(extractions, model=merge_model)

    profile_path, resume_path = write_outputs(profile, base_resume_md)
    stats["profile_path"] = str(profile_path)
    stats["base_resume_path"] = str(resume_path)
    stats["skills_count"] = len(profile.must_have_skills) + len(profile.nice_to_have_skills) + len(profile.technologies)
    stats["experience_count"] = len(profile.experience)
    return stats
