"""Aggregator adapter for arbeitnow.com.

Free public API at https://www.arbeitnow.com/api/job-board-api that aggregates
thousands of jobs across Greenhouse / Lever / Ashby / Workday / company career
sites. We auto-detect the underlying ATS from the apply URL so submission still
works downstream.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

from ..models import ATSKind
from ..utils.logging import get_logger
from .base import JobListing

log = get_logger(__name__)

URL = "https://www.arbeitnow.com/api/job-board-api"


def _strip(html: str) -> str:
    return BeautifulSoup(html or "", "lxml").get_text("\n").strip()


def _ats_kind_for(url: str) -> ATSKind:
    u = (url or "").lower()
    if "greenhouse" in u or "boards.greenhouse.io" in u:
        return ATSKind.greenhouse
    if "lever.co" in u:
        return ATSKind.lever
    if "ashbyhq" in u or "jobs.ashby" in u:
        return ATSKind.ashby
    if "myworkdayjobs" in u or "workday" in u:
        return ATSKind.workday
    if "icims" in u:
        return ATSKind.icims
    return ATSKind.unknown


def fetch(
    *,
    queries: list[str] | None = None,
    remote_only: bool = False,
    max_pages: int = 5,
    client: httpx.Client | None = None,
) -> list[JobListing]:
    """Pull job listings from arbeitnow's public API.

    The API doesn't accept a query parameter — it returns the most recent jobs.
    We do client-side keyword filtering against `queries` if provided.
    """
    queries_lc = [q.lower() for q in (queries or [])]
    owns = client is None
    client = client or httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"})
    listings: list[JobListing] = []

    try:
        next_url: str | None = URL
        for _ in range(max_pages):
            if not next_url:
                break
            resp = client.get(next_url)
            resp.raise_for_status()
            payload = resp.json()
            for job in payload.get("data", []):
                title = job.get("title") or ""
                if remote_only and not job.get("remote"):
                    continue
                if queries_lc:
                    haystack = (title + " " + (job.get("description") or "")).lower()
                    if not any(q in haystack for q in queries_lc):
                        continue

                jd_text = _strip(job.get("description") or "")
                apply_url = job.get("url") or ""
                ats = _ats_kind_for(apply_url)
                created = job.get("created_at")
                posted_at = None
                if created:
                    try:
                        posted_at = datetime.fromtimestamp(int(created), tz=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                listings.append(
                    JobListing(
                        source="arbeitnow",
                        source_job_id=str(job.get("slug") or job.get("url") or title),
                        company=job.get("company_name") or "Unknown",
                        title=title,
                        jd_text=jd_text,
                        jd_url=apply_url,
                        ats_kind=ats,
                        location=job.get("location"),
                        remote=job.get("remote"),
                        apply_url=apply_url,
                        posted_at=posted_at,
                        extra={"tags": job.get("tags") or [], "slug": job.get("slug")},
                    )
                )
            next_url = (payload.get("links") or {}).get("next")
    finally:
        if owns:
            client.close()

    log.info("arbeitnow: %d listings after client-side filter", len(listings))
    return listings


class ArbeitnowAdapter:
    name = "arbeitnow"

    def fetch(self, config: dict) -> Iterable[JobListing]:
        cfg = (config or {}).get("arbeitnow") or {}
        if cfg is False or cfg.get("enabled") is False:
            return []
        queries = cfg.get("queries")
        # Fall back to top-level search.queries if arbeitnow-specific queries not given.
        if not queries:
            queries = ((config or {}).get("search") or {}).get("queries")
        remote_only = bool(cfg.get("remote_only", False))
        max_pages = int(cfg.get("max_pages", 5))
        return fetch(queries=queries, remote_only=remote_only, max_pages=max_pages)
