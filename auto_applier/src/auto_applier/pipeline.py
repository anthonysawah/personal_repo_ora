from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlmodel import select

from . import config as _config
from .db import session_scope
from .discovery import load_adapters
from .discovery.filters import ExcludeRules
from .models import Application, AppStatus, Job
from .profile.loader import load_base_resume, load_profile
from .scoring.filter import passes_prefilter, prefilter_score
from .scoring.llm_match import score_fit
from .tailor.render_docx import render_docx
from .tailor.render_pdf import render_pdf
from .tailor.tailor import tailor_resume
from .utils.logging import get_logger

log = get_logger(__name__)


def _load_companies_config() -> dict:
    if _config.settings.companies_path.exists():
        return yaml.safe_load(_config.settings.companies_path.read_text(encoding="utf-8")) or {}
    return {}


def run_discover(sources: list[str] | None = None) -> dict:
    config = _load_companies_config()
    adapters = load_adapters(sources)
    excludes = ExcludeRules.from_config(config)
    stats = {"seen": 0, "inserted": 0, "duplicate": 0, "excluded": 0}

    with session_scope() as session:
        for adapter in adapters:
            log.info("discovery: running adapter=%s", adapter.name)
            for listing in adapter.fetch(config):
                stats["seen"] += 1
                excluded, reason = excludes.is_excluded(listing)
                if excluded:
                    stats["excluded"] += 1
                    log.debug("skipped %s @ %s — %s", listing.title, listing.company, reason)
                    continue

                dedupe = listing.dedupe_hash()
                exists = session.exec(
                    select(Job).where(Job.dedupe_hash == dedupe)
                ).first()
                if exists:
                    stats["duplicate"] += 1
                    continue

                job = Job(
                    source=listing.source,
                    source_job_id=listing.source_job_id,
                    company=listing.company,
                    title=listing.title,
                    location=listing.location,
                    remote=listing.remote,
                    jd_text=listing.jd_text,
                    jd_url=listing.jd_url,
                    apply_url=listing.apply_url,
                    ats_kind=listing.ats_kind,
                    posted_at=listing.posted_at,
                    dedupe_hash=dedupe,
                )
                session.add(job)
                stats["inserted"] += 1
            session.commit()

    return stats


def run_score(prefilter_threshold: int = 30, llm: bool = True) -> dict:
    profile = load_profile()
    stats = {"considered": 0, "filtered": 0, "scored": 0, "errors": 0}

    with session_scope() as session:
        # Find jobs with no Application row yet.
        all_jobs = session.exec(select(Job)).all()
        existing_app_job_ids = {
            a.job_id for a in session.exec(select(Application)).all()
        }

        for job in all_jobs:
            if job.id in existing_app_job_ids:
                continue
            stats["considered"] += 1

            if not passes_prefilter(profile, job.jd_text, job.title, prefilter_threshold):
                stats["filtered"] += 1
                app = Application(
                    job_id=job.id,
                    status=AppStatus.skipped,
                    fit_score=prefilter_score(profile, job.jd_text, job.title),
                    reason="prefilter below threshold",
                )
                session.add(app)
                continue

            if not llm:
                app = Application(
                    job_id=job.id,
                    status=AppStatus.scored,
                    fit_score=prefilter_score(profile, job.jd_text, job.title),
                    reason="prefilter only",
                )
                session.add(app)
                stats["scored"] += 1
                continue

            try:
                result = score_fit(profile, job.jd_text, job.title, job.company)
                app = Application(
                    job_id=job.id,
                    status=AppStatus.scored,
                    fit_score=result.fit_score,
                    reason=result.reason,
                )
                session.add(app)
                stats["scored"] += 1
            except Exception as e:  # noqa: BLE001
                log.warning("LLM score failed for job=%s: %s", job.id, e)
                stats["errors"] += 1

        session.commit()

    return stats


def run_tailor(limit: int | None = None, min_score: int = 60) -> dict:
    profile = load_profile()
    base_resume = load_base_resume()
    limit = limit or _config.settings.tailor_daily_limit
    stats = {"tailored": 0, "errors": 0, "total_input_tokens": 0, "total_output_tokens": 0, "cache_read": 0}

    with session_scope() as session:
        apps = session.exec(
            select(Application)
            .where(Application.status == AppStatus.scored)
            .where(Application.fit_score >= min_score)
        ).all()
        apps = sorted(apps, key=lambda a: a.fit_score or 0, reverse=True)[:limit]

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for app in apps:
            job = session.get(Job, app.job_id)
            if not job:
                continue
            try:
                tailored, usage = tailor_resume(
                    profile,
                    base_resume,
                    title=job.title,
                    company=job.company,
                    jd_text=job.jd_text,
                )
                art_dir = _config.settings.artifacts_dir / day / f"app-{app.id}"
                pdf_path = art_dir / "resume.pdf"
                docx_path = art_dir / "resume.docx"
                render_pdf(profile, tailored, pdf_path)
                render_docx(profile, tailored, docx_path)

                app.tailored_resume_json = json.dumps(tailored.model_dump())
                app.resume_pdf_path = str(pdf_path)
                app.resume_docx_path = str(docx_path)
                app.cover_letter_md = tailored.cover_letter_md
                app.status = AppStatus.pending_approval
                session.add(app)
                session.commit()

                stats["tailored"] += 1
                stats["total_input_tokens"] += usage["input_tokens"]
                stats["total_output_tokens"] += usage["output_tokens"]
                stats["cache_read"] += usage["cache_read_input_tokens"]

            except Exception as e:  # noqa: BLE001
                log.warning("tailor failed for app=%s: %s", app.id, e)
                app.error = str(e)
                session.add(app)
                session.commit()
                stats["errors"] += 1

    return stats


def run_daily(sources: list[str] | None = None, tailor_limit: int | None = None) -> dict:
    d = run_discover(sources)
    s = run_score()
    t = run_tailor(limit=tailor_limit)
    return {"discover": d, "score": s, "tailor": t}
