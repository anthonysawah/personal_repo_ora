from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import select

from .. import config as _config
from ..ats import registry
from ..ats.base import SubmitContext
from ..db import session_scope
from ..models import Application, AppStatus, Job
from ..profile.loader import load_profile
from ..utils.logging import get_logger

log = get_logger(__name__)


def _recent_submission_companies(session, cooldown_days: int) -> set[str]:
    """Return lowercased company names already submitted-to within the cooldown window."""
    if cooldown_days <= 0:
        return set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
    rows = session.exec(
        select(Application).where(Application.status == AppStatus.submitted)
    ).all()
    out: set[str] = set()
    for a in rows:
        if not a.submitted_at or a.submitted_at < cutoff:
            continue
        job = session.get(Job, a.job_id)
        if job and job.company:
            out.add(job.company.strip().lower())
    return out


def run_submit(
    dry_run: bool = False,
    limit: int | None = None,
    essay_mode: str | None = None,
    cooldown_days: int | None = None,
) -> dict:
    profile = load_profile()
    essay_mode = essay_mode or _config.settings.submit_essay_mode
    cooldown_days = (
        cooldown_days
        if cooldown_days is not None
        else _config.settings.submit_per_company_cooldown_days
    )
    stats = {"submitted": 0, "failed": 0, "skipped": 0, "cooldown_skipped": 0}

    with session_scope() as session:
        already_applied = _recent_submission_companies(session, cooldown_days)
        q = select(Application).where(Application.status == AppStatus.approved)
        apps = session.exec(q).all()
        if limit:
            apps = apps[:limit]

        for app in apps:
            job = session.get(Job, app.job_id)
            if not job:
                continue

            company_lc = (job.company or "").strip().lower()
            if company_lc and company_lc in already_applied:
                log.info(
                    "cooldown: skipping app %s (company=%s already submitted within %dd)",
                    app.id, job.company, cooldown_days,
                )
                app.status = AppStatus.skipped
                app.error = f"per-company cooldown ({cooldown_days}d)"
                session.add(app)
                stats["cooldown_skipped"] += 1
                continue

            pdf_path = Path(app.resume_pdf_path) if app.resume_pdf_path else None
            if not pdf_path or not pdf_path.exists():
                log.warning("app %s has no resume PDF; skipping", app.id)
                app.status = AppStatus.failed
                app.error = "Missing resume PDF"
                session.add(app)
                stats["failed"] += 1
                continue

            ctx = SubmitContext(
                job=job,
                application=app,
                profile=profile,
                resume_pdf_path=pdf_path,
                resume_docx_path=Path(app.resume_docx_path) if app.resume_docx_path else None,
                answers={q.question: q.answer for q in profile.qa_bank},
                dry_run=dry_run,
                essay_mode=essay_mode,
            )

            adapter = registry.get(job.ats_kind)
            log.info("submitting app=%s via adapter=%s (dry_run=%s)", app.id, adapter.name, dry_run)
            result = adapter.submit(ctx)

            if result.ok:
                app.status = AppStatus.submitted
                app.submitted_at = datetime.now(timezone.utc)
                app.confirmation_text = result.confirmation_text
                app.confirmation_screenshot_path = result.confirmation_screenshot_path
                if company_lc:
                    already_applied.add(company_lc)
                stats["submitted"] += 1
            else:
                app.status = AppStatus.failed
                app.error = result.error
                stats["failed"] += 1

            session.add(app)
            session.commit()

    return stats
