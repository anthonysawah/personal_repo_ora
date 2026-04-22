from __future__ import annotations

import base64

import httpx

from ..utils.logging import get_logger
from .base import SubmitContext, SubmitResult, SubmitterAdapter
from .registry import register

log = get_logger(__name__)


@register("greenhouse")
class GreenhouseSubmitter(SubmitterAdapter):
    """Submit via Greenhouse's job-board application endpoint.

    NOTE: Greenhouse's public application endpoint requires a per-board API
    token that's usually not exposed. For most Greenhouse boards the real
    submission path is a Playwright-driven form fill against the
    board's public apply URL. We implement the API path here for boards that
    expose it; companies that don't get routed to the Playwright fallback
    via the `ats_kind=unknown` path at submit time.
    """

    name = "greenhouse"

    def submit(self, ctx: SubmitContext) -> SubmitResult:
        extra = (ctx.job.ats_kind, ctx.job.apply_url)
        if ctx.dry_run:
            log.info("greenhouse dry-run submit company=%s title=%s", ctx.job.company, ctx.job.title)
            return SubmitResult(
                ok=True,
                confirmation_text=f"DRY RUN: would POST resume to {ctx.job.apply_url}",
                extra={"apply_url": ctx.job.apply_url},
            )

        # Real submission requires a per-board API token (greenhouse_api_token)
        # which most public boards don't ship. Fall back to Playwright form-fill.
        from .playwright_generic import PlaywrightGenericSubmitter

        log.info("greenhouse: no API token path available, deferring to Playwright form-fill")
        return PlaywrightGenericSubmitter().submit(ctx)


def _b64(path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _submit_via_gh_api(
    *,
    board_token: str,
    gh_job_id: str | int,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    resume_pdf_path,
    api_token: str,
) -> SubmitResult:
    """Helper for callers that DO have a Greenhouse job-board API token."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{gh_job_id}"
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "resume_content": _b64(resume_pdf_path),
        "resume_content_filename": resume_pdf_path.name,
    }
    try:
        resp = httpx.post(url, json=payload, auth=(api_token, ""), timeout=60.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return SubmitResult(ok=False, error=str(e))
    return SubmitResult(ok=True, confirmation_text=resp.text[:500])
