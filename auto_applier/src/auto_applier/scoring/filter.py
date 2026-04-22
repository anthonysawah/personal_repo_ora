from __future__ import annotations

from rapidfuzz import fuzz

from ..profile.schema import Profile


def prefilter_score(profile: Profile, jd_text: str, title: str) -> int:
    """Cheap 0-100 prefilter without LLM calls."""
    jd = jd_text.lower()
    title_lc = title.lower()

    title_score = 0
    for target in profile.target_titles:
        title_score = max(title_score, fuzz.partial_ratio(target.lower(), title_lc))

    skill_hits = sum(1 for s in profile.must_have_skills if s.lower() in jd)
    skill_total = max(1, len(profile.must_have_skills))
    skill_score = int(100 * skill_hits / skill_total)

    tech_hits = sum(1 for t in profile.technologies if t.lower() in jd)
    tech_score = min(100, tech_hits * 10)

    return int(0.4 * title_score + 0.4 * skill_score + 0.2 * tech_score)


def passes_prefilter(profile: Profile, jd_text: str, title: str, threshold: int = 30) -> bool:
    return prefilter_score(profile, jd_text, title) >= threshold
