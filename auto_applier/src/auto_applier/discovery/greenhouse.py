from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

from ..models import ATSKind
from ..utils.logging import get_logger
from .base import JobListing

log = get_logger(__name__)

BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    text = soup.get_text("\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_board(slug: str, client: httpx.Client | None = None) -> list[JobListing]:
    owns_client = client is None
    client = client or httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"})
    try:
        resp = client.get(BASE.format(slug=slug), params={"content": "true"})
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if owns_client:
            client.close()

    listings: list[JobListing] = []
    for job in payload.get("jobs", []):
        jd_html = job.get("content") or ""
        jd_text = _strip_html(jd_html)
        location = (job.get("location") or {}).get("name")
        posted_raw = job.get("updated_at") or job.get("first_published")
        posted_at = None
        if posted_raw:
            try:
                posted_at = datetime.fromisoformat(posted_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        listings.append(
            JobListing(
                source="greenhouse",
                source_job_id=str(job["id"]),
                company=slug,
                title=job.get("title", ""),
                jd_text=jd_text,
                jd_url=job.get("absolute_url", ""),
                ats_kind=ATSKind.greenhouse,
                location=location,
                apply_url=job.get("absolute_url"),
                posted_at=posted_at,
                extra={"gh_job_id": job["id"], "slug": slug},
            )
        )
    return listings


class GreenhouseAdapter:
    name = "greenhouse"

    def fetch(self, config: dict) -> Iterable[JobListing]:
        slugs = [entry["slug"] for entry in (config or {}).get("greenhouse", []) if entry.get("slug")]
        with httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"}) as client:
            for slug in slugs:
                try:
                    for listing in fetch_board(slug, client=client):
                        yield listing
                except httpx.HTTPError as e:
                    log.warning("greenhouse slug=%s fetch failed: %s", slug, e)
