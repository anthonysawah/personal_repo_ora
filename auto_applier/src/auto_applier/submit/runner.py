from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import select

from ..ats import registry
from ..ats.base import SubmitContext
from ..db import session_scope
from ..models import Application, AppStatus, Job
from ..profile.loader import load_profile
from ..utils.logging import get_logger

log = get_logger(__name__)


def run_submit(dry_run: bool = False, limit: int | None = None) -> dict:
    profile = load_profile()
    stats = {"submitted": 0, "failed": 0, "skipped": 0}

    with session_scope() as session:
        q = select(Application).where(Application.status == AppStatus.approved)
        apps = session.exec(q).all()
        if limit:
            apps = apps[:limit]

        for app in apps:
            job = session.get(Job, app.job_id)
            if not job:
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
            )

            adapter = registry.get(job.ats_kind)
            log.info("submitting app=%s via adapter=%s (dry_run=%s)", app.id, adapter.name, dry_run)
            result = adapter.submit(ctx)

            if result.ok:
                app.status = AppStatus.submitted
                app.submitted_at = datetime.now(timezone.utc)
                app.confirmation_text = result.confirmation_text
                app.confirmation_screenshot_path = result.confirmation_screenshot_path
                stats["submitted"] += 1
            else:
                app.status = AppStatus.failed
                app.error = result.error
                stats["failed"] += 1

            session.add(app)
            session.commit()

    return stats
