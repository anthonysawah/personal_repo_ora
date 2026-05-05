from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

import anthropic
from pydantic import BaseModel, Field

from .. import budget as _budget
from .. import config as _config
from ..profile.schema import Education, Profile
from .prompts import build_cached_system, build_user_message


class TailoredExperience(BaseModel):
    company: str
    title: str
    start: str
    end: Optional[str] = None
    location: str = ""
    bullets: list[str] = Field(default_factory=list)


class TailoredProject(BaseModel):
    name: str
    description: str = ""
    url: str = ""
    bullets: list[str] = Field(default_factory=list)


class TailoredResume(BaseModel):
    summary: str
    skills: list[str] = Field(default_factory=list)
    experience: list[TailoredExperience] = Field(default_factory=list)
    projects: list[TailoredProject] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    keywords_used: list[str] = Field(default_factory=list)
    cover_letter_md: str = ""
    notes: str = ""


@lru_cache(maxsize=1)
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


def tailor_resume(
    profile: Profile,
    base_resume_md: str,
    *,
    title: str,
    company: str,
    jd_text: str,
    model: Optional[str] = None,
    extra_user_note: str = "",
) -> tuple[TailoredResume, dict]:
    """Returns (tailored, usage_info). `extra_user_note` is appended to the user
    message — used by the dashboard's "retailor with note" feature."""
    _budget.assert_under_budget("tailor")
    client = _client()
    system_text = build_cached_system(profile, base_resume_md)
    use_model = model or _config.settings.tailor_model

    user_msg = build_user_message(title, company, jd_text)
    if extra_user_note.strip():
        user_msg = (
            user_msg
            + "\n\n<additional_instructions from=\"user\">\n"
            + extra_user_note.strip()
            + "\n</additional_instructions>"
        )

    resp = client.messages.create(
        model=use_model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )

    _budget.record_from_response(stage="tailor", model=use_model, usage=resp.usage)
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(_strip_fences(text))
    tailored = TailoredResume.model_validate(data)

    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
    }
    return tailored, usage
