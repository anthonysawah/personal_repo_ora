# auto_applier

Pipeline that discovers jobs, scores fit with Claude, tailors a resume + cover letter per job, stages them for approval in a local dashboard, and submits via ATS adapters (Greenhouse / Lever / Ashby) or a Playwright fallback (Workday / iCIMS / arbitrary career sites). LinkedIn is discovery-only.

## Quick start

```sh
cd auto_applier
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # fill in ANTHROPIC_API_KEY
auto_applier init      # scaffolds data/profile.yaml + data/base_resume.md
# edit data/profile.yaml and data/base_resume.md
auto_applier doctor
auto_applier run-daily
auto_applier review    # opens http://127.0.0.1:8765 to approve
auto_applier submit
```

## Pipeline stages

1. `discover` — ATS APIs + optional scrapers → `jobs` table
2. `score` — rapidfuzz prefilter, then Claude Haiku for 0-100 fit → `applications` (scored)
3. `tailor` — Claude Sonnet with prompt-cached profile + base resume, rendered to PDF + DOCX
4. `review` — FastAPI dashboard; user approves / skips / retailors
5. `submit` — dispatches to ATS adapter (Greenhouse/Lever/Ashby API, Playwright fallback)

## Notes

- LinkedIn / Indeed scraping is off by default (ToS concerns). Enable only if you accept the risk.
- The `submit` step has `--dry-run` — use it first.
- `data/` is gitignored. Resumes contain PII.
