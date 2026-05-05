# auto_applier

Pipeline that discovers jobs, scores fit with Claude, tailors a resume + cover letter per job, stages them for approval in a local dashboard, and submits via ATS adapters (Greenhouse / Lever / Ashby) or a Playwright fallback (Workday / iCIMS / arbitrary career sites). LinkedIn is discovery-only.

## Quick start

```sh
cd auto_applier
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # fill in ANTHROPIC_API_KEY
auto_applier init      # scaffolds data/profile.yaml + data/base_resume.md

# Option A — bootstrap the profile from a folder of existing resumes
mkdir -p data/ingest && cp ~/Downloads/sawah_resumes/*.{pdf,docx} data/ingest/
auto_applier ingest --src data/ingest    # writes data/profile.yaml + data/base_resume.md

# Option B — fill in data/profile.yaml + data/base_resume.md by hand

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

## Auto-submit (Playwright + Claude)

For ATS platforms without a clean public API (Workday, iCIMS, company career sites),
`submit` falls through to a Playwright + Claude vision pipeline:

1. Chromium opens the apply URL
2. Each step: screenshots the page + extracts visible form fields (id, label, type)
3. Sends screenshot + fields + your profile + Q&A bank to Claude Sonnet
4. Claude returns a JSON action plan (fill/select/click/upload/wait)
5. Playwright executes; loop until confirmation page is detected, or captcha / login wall stops us

**Setup** (one-time):

```sh
pip install -e '.[playwright]'
playwright install chromium
```

By default Playwright runs headful so you can watch + intervene. Set
`PLAYWRIGHT_HEADLESS=true` in `.env` once you trust it. Screenshots of every
step are saved under `data/artifacts/<date>/app-<id>/playwright/`.

**What it can't do (yet):**
- Solve captchas (it stops + flags for human takeover)
- Create accounts on Workday / iCIMS for first-time applicants (login walls
  cause an immediate failure with a "needs human" message)
- Open-ended essay questions ("describe a time you failed") — the model is
  instructed not to fabricate, so it'll flag `needs_human` and return.

## Notes

- LinkedIn / Indeed scraping is off by default (ToS concerns). Enable only if you accept the risk.
- The `submit` step has `--dry-run` — use it first.
- `data/` is gitignored. Resumes contain PII.
