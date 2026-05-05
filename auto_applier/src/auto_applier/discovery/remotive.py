"""Adapter for remotive.com — free remote-jobs aggregator with a public API."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

from ..models import ATSKind
from ..utils.logging import get_logger
from .base import JobListing

log = get_logger(__name__)

URL = "https://remotive.com/api/remote-jobs"


def _strip(html: str) -> str:
    return BeautifulSoup(html or "", "lxml").get_text("\n").strip()


def _ats_kind_for(url: str) -> ATSKind:
    u = (url or "").lower()
    if "greenhouse" in u:
        return ATSKind.greenhouse
    if "lever.co" in u:
        return ATSKind.lever
    if "ashbyhq" in u:
        return ATSKind.ashby
    if "myworkdayjobs" in u or "workday" in u:
        return ATSKind.workday
    if "icims" in u:
        return ATSKind.icims
    return ATSKind.unknown


def fetch(
    *,
    queries: list[str] | None = None,
    category: str | None = "software-dev",
    limit: int = 100,
    client: httpx.Client | None = None,
) -> list[JobListing]:
    owns = client is None
    client = client or httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"})
    listings: list[JobListing] = []

    queries_lc = [q.lower() for q in (queries or [])]
    try:
        if queries_lc:
            for q in queries_lc:
                params = {"limit": limit, "search": q}
                if category:
                    params["category"] = category
                resp = client.get(URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
                listings.extend(_parse_payload(payload))
        else:
            params = {"limit": limit}
            if category:
                params["category"] = category
            resp = client.get(URL, params=params)
            resp.raise_for_status()
            listings.extend(_parse_payload(resp.json()))
    finally:
        if owns:
            client.close()

    # Dedupe within this fetch.
    seen: set[str] = set()
    unique: list[JobListing] = []
    for j in listings:
        if j.source_job_id in seen:
            continue
        seen.add(j.source_job_id)
        unique.append(j)
    log.info("remotive: %d listings after dedupe", len(unique))
    return unique


def _parse_payload(payload: dict) -> list[JobListing]:
    out: list[JobListing] = []
    for j in payload.get("jobs", []):
        url = j.get("url") or ""
        posted_at = None
        if j.get("publication_date"):
            try:
                posted_at = datetime.fromisoformat(j["publication_date"].replace("Z", "+00:00"))
            except ValueError:
                pass
        out.append(
            JobListing(
                source="remotive",
                source_job_id=str(j.get("id") or url),
                company=j.get("company_name") or "Unknown",
                title=j.get("title") or "",
                jd_text=_strip(j.get("description") or ""),
                jd_url=url,
                ats_kind=_ats_kind_for(url),
                location=j.get("candidate_required_location") or "Remote",
                remote=True,
                apply_url=url,
                posted_at=posted_at,
                extra={"tags": j.get("tags") or [], "salary": j.get("salary") or ""},
            )
        )
    return out


class RemotiveAdapter:
    name = "remotive"

    def fetch(self, config: dict) -> Iterable[JobListing]:
        cfg = (config or {}).get("remotive") or {}
        if cfg is False or cfg.get("enabled") is False:
            return []
        queries = cfg.get("queries") or ((config or {}).get("search") or {}).get("queries")
        category = cfg.get("category", "software-dev")
        limit = int(cfg.get("limit", 100))
        return fetch(queries=queries, category=category, limit=limit)
