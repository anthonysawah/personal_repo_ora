from __future__ import annotations

import yaml

from ..profile.schema import Profile

TAILOR_INSTRUCTIONS = """\
You are an expert resume tailor. Given a candidate's master profile and base resume,
plus a specific job description, produce a tailored resume as a JSON object.

Rules — these are absolute:
- Use ONLY facts from the candidate's profile / base_resume. NEVER invent roles,
  skills, numbers, companies, dates, or technologies the candidate doesn't have.
- You may rephrase, reorder, emphasize, and select — but not fabricate.
- Rewrite the summary to speak directly to the JD's must-haves in 1-2 sentences.
- For each experience entry, keep the factual header (company, title, dates, location)
  unchanged, but rewrite / reorder / prune bullets to match the JD's language and priorities.
  Aim for 3-5 bullets per role. Quantify impact where the source has numbers.
- Select a skill subset (8-15 items) most relevant to the JD, drawn from the profile.
- Use the job's own keywords naturally — ATS systems match on keywords.
- Also write a short per-job cover letter (150-220 words) in markdown.

Output format: a single JSON object matching this schema:
{
  "summary": string,
  "skills": string[],
  "experience": [
    {"company": str, "title": str, "start": str, "end": str|null, "location": str,
     "bullets": string[]}
  ],
  "projects": [{"name": str, "description": str, "url": str, "bullets": string[]}],
  "education": [
    {"institution": str, "degree": str, "field": str, "start": str, "end": str,
     "gpa": number|null, "honors": string[]}
  ],
  "keywords_used": string[],
  "cover_letter_md": string,
  "notes": string
}

Return only the JSON object. No prose before or after.
"""


def build_cached_system(profile: Profile, base_resume_md: str) -> str:
    profile_yaml = yaml.safe_dump(profile.model_dump(), sort_keys=True, allow_unicode=True)
    return (
        TAILOR_INSTRUCTIONS
        + "\n\n<candidate_profile>\n"
        + profile_yaml
        + "\n</candidate_profile>\n\n<base_resume>\n"
        + base_resume_md
        + "\n</base_resume>\n"
    )


def build_user_message(title: str, company: str, jd_text: str) -> str:
    return (
        f"<job>\n<title>{title}</title>\n<company>{company}</company>\n"
        f"<jd>\n{jd_text}\n</jd>\n</job>\n\nReturn the tailored resume JSON."
    )
