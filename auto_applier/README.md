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

**Essay mode** (controls how it handles open-ended questions like "describe
a time you failed" or "why this company"):

| Mode | Behavior |
|---|---|
| `flag` | Bail with `needs_human`. Safest. |
| `attempt` (default) | Compose a grounded answer (~150–220 words) using only profile facts. Blank if no material. |
| `aggressive` | Always answer. Extrapolate plausibly within domain/seniority. Won't invent companies/dates the candidate didn't have. |

Set via `SUBMIT_ESSAY_MODE` in `.env`, or per-run with `auto_applier submit
--essay-mode aggressive`.

**What it can't do (yet):**
- Solve captchas (stops + flags for human takeover)
- Create accounts on Workday / iCIMS for first-time applicants (login walls
  cause an immediate failure with a "needs human" message)

## Cost control

The `usage` table tracks every Claude call. Run:

```sh
auto_applier usage          # spend per day, broken out by stage
auto_applier usage --today  # today's running total
```

`ANTHROPIC_DAILY_BUDGET_USD` (in `.env`) is a hard cap — Claude calls fail
fast with `BudgetExceededError` once today's spend exceeds it. Set to `0` to
disable the cap.

## Per-company cooldown

Set `SUBMIT_PER_COMPANY_COOLDOWN_DAYS=14` (default) to prevent submitting
twice to the same employer within 14 days. Override per-run:

```sh
auto_applier submit --cooldown-days 30
auto_applier submit --cooldown-days 0    # disable
```

## Outcome tracker (IMAP)

`auto_applier track-outcomes` connects to your inbox and matches recent emails
to your submitted applications by company name. Classifies each as
`confirmation_received` / `interview_invitation` / `rejection` / unmatched.
Adds notes to the application's `confirmation_text` field.

Setup (Outlook / live.com):
1. Enable 2FA on your Microsoft account
2. Create an App Password at <https://account.microsoft.com/security> → App passwords
3. Set in `.env`:
   ```
   IMAP_HOST=outlook.office365.com
   IMAP_USER=anthonysawah@live.com
   IMAP_PASSWORD=<app password>
   ```

For Gmail:
1. Enable 2FA, create an App Password at <https://myaccount.google.com/apppasswords>
2. `IMAP_HOST=imap.gmail.com`, `IMAP_USER=you@gmail.com`, `IMAP_PASSWORD=<app password>`

Run periodically (cron / launchd) — e.g. once an hour:
```sh
auto_applier track-outcomes --lookback-days 7
```

## Retailor with a note

In the approval dashboard, click into any pending application and expand
"Retailor with a note". Type something like "emphasize Kubernetes and on-call,
de-emphasize DBA work" — the resume + cover letter regenerate. Cost ~$0.01–0.03.

## Notes

- LinkedIn / Indeed scraping is off by default (ToS concerns). Enable only if you accept the risk.
- The `submit` step has `--dry-run` — use it first.
- `data/` is gitignored. Resumes contain PII.
