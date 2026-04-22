from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

import anthropic
import yaml
from pydantic import BaseModel, Field

from .. import config as _config
from ..profile.schema import Profile

SYSTEM_INSTRUCTIONS = """\
You are an expert technical recruiter. Given a candidate profile and a job description,
return a single JSON object with:
  fit_score: integer 0-100 (100 = ideal match)
  reason: short rationale, 1-2 sentences
  must_have_gaps: list of critical missing skills/experience (empty if none)

Weigh must-have skill overlap, title match, years of experience, and location fit.
Be strict — 90+ is a genuinely strong match, 70-89 is solid, 50-69 is stretch, <50 is no.
Return only the JSON object, no prose.
"""


class MatchResult(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    reason: str
    must_have_gaps: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    if not _config.settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=_config.settings.anthropic_api_key)


def _cached_prefix(profile: Profile) -> str:
    profile_yaml = yaml.safe_dump(profile.model_dump(), sort_keys=True, allow_unicode=True)
    return (
        SYSTEM_INSTRUCTIONS
        + "\n\n<candidate_profile>\n"
        + profile_yaml
        + "\n</candidate_profile>\n"
    )


def score_fit(
    profile: Profile,
    jd_text: str,
    title: str,
    company: str,
    model: Optional[str] = None,
) -> MatchResult:
    client = _client()
    resp = client.messages.create(
        model=model or _config.settings.score_model,
        max_tokens=400,
        system=[
            {
                "type": "text",
                "text": _cached_prefix(profile),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"<job>\n<title>{title}</title>\n<company>{company}</company>\n"
                    f"<jd>\n{jd_text}\n</jd>\n</job>\nReturn the JSON object."
                ),
            }
        ],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "").strip()
    # Strip accidental code fences.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    return MatchResult.model_validate(data)
