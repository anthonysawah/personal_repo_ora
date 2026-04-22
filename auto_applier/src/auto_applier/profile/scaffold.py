from __future__ import annotations

from pathlib import Path

PROFILE_TEMPLATE = """\
# auto_applier profile — your source of truth for tailoring + form-filling.
# Fill everything out honestly and thoroughly. The more detail, the better the tailoring.

personal:
  full_name: ""
  email: ""
  phone: ""
  city: ""
  state: ""
  country: "USA"
  linkedin_url: ""
  github_url: ""
  portfolio_url: ""

work_authorization:
  us_work_auth: ""             # e.g. "US Citizen" | "Green Card" | "H1-B" | "OPT"
  needs_sponsorship_now: false
  needs_sponsorship_future: false
  visa_status: ""

compensation:
  desired_min_usd: null
  desired_max_usd: null
  currency: "USD"
  open_to_equity: true

# Skills you want tailored resumes to lean into. Be exhaustive.
must_have_skills: []
nice_to_have_skills: []
technologies: []               # languages, frameworks, platforms, tools you've used
fundamentals: []               # CS fundamentals, methodologies, patterns

summary: >
  One or two sentences of professional summary. The tailor rewrites this per-JD.

experience:
  - company: ""
    title: ""
    start: "2023-01"
    end: null                  # null = present
    location: ""
    technologies: []
    bullets:
      - ""
      - ""

education:
  - institution: ""
    degree: ""
    field: ""
    start: ""
    end: ""
    gpa: null
    honors: []

projects:
  - name: ""
    description: ""
    url: ""
    technologies: []
    bullets: []

target_titles: []              # job titles you're targeting — drives scoring
target_locations: []
remote_ok: true
relocate_ok: false

# Canned answers to common application questions. The Playwright submitter
# and tailor both pull from here.
qa_bank:
  - question: "Why do you want to work here?"
    answer: ""
  - question: "What's your greatest strength?"
    answer: ""
  - question: "Are you authorized to work in the United States?"
    answer: "Yes"
  - question: "Will you now or in the future require sponsorship?"
    answer: "No"
  - question: "What are your salary expectations?"
    answer: ""
  - question: "When can you start?"
    answer: "Two weeks after offer"
  - question: "How did you hear about us?"
    answer: "Company careers page"
  - question: "Gender"
    answer: "Decline to self-identify"
  - question: "Race/Ethnicity"
    answer: "Decline to self-identify"
  - question: "Veteran status"
    answer: "I am not a protected veteran"
  - question: "Disability status"
    answer: "I don't wish to answer"
"""

BASE_RESUME_TEMPLATE = """\
# YOUR NAME

your.email@example.com · (555) 555-5555 · City, State · linkedin.com/in/you · github.com/you

## Summary

One or two sentences. The tailor rewrites this per-JD; keep a strong default here for when the tailor fails.

## Experience

### Company · Title
*YYYY-MM – Present · Location*

- Impactful bullet quantified with a number.
- Another bullet leaning on keywords.
- Third bullet showing scope.

### Previous Company · Title
*YYYY-MM – YYYY-MM · Location*

- Impact.
- Impact.

## Projects

### Project Name — short description · [link](https://…)

- What it does, tech used, what you built.

## Education

**Institution** · Degree in Field · YYYY – YYYY

## Skills

Languages: …
Frameworks: …
Cloud / Infra: …
Tools: …
"""

COMPANIES_TEMPLATE = """\
# List companies to discover jobs from, grouped by ATS adapter.
# `slug` is the company's subdomain / board token on the ATS (e.g. for
# boards-api.greenhouse.io/v1/boards/<slug>/jobs, the slug is the segment).

greenhouse:
  - slug: stripe
  - slug: airbnb
  - slug: databricks

lever: []
ashby: []

rss: []
"""


def scaffold(data_dir: Path, force: bool = False) -> list[Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, body in [
        ("profile.yaml", PROFILE_TEMPLATE),
        ("base_resume.md", BASE_RESUME_TEMPLATE),
        ("companies.yaml", COMPANIES_TEMPLATE),
    ]:
        target = data_dir / name
        if target.exists() and not force:
            continue
        target.write_text(body, encoding="utf-8")
        written.append(target)

    return written
