from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import httpx

from ..models import ATSKind
from ..utils.logging import get_logger
from .base import JobListing

log = get_logger(__name__)

BASE = "https://api.lever.co/v0/postings/{slug}"


def fetch_board(slug: str, client: httpx.Client | None = None) -> list[JobListing]:
    owns = client is None
    client = client or httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"})
    try:
        resp = client.get(BASE.format(slug=slug), params={"mode": "json"})
        resp.raise_for_status()
        postings = resp.json()
    finally:
        if owns:
            client.close()

    listings: list[JobListing] = []
    for p in postings:
        description = p.get("descriptionPlain") or p.get("description") or ""
        lists = p.get("lists") or []
        extras = []
        for block in lists:
            text = block.get("text") or ""
            content = block.get("content") or ""
            extras.append(f"{text}\n{content}")
        jd_text = (description + "\n\n" + "\n\n".join(extras)).strip()

        categories = p.get("categories") or {}
        created_at = p.get("createdAt")
        posted_at = None
        if created_at:
            try:
                posted_at = datetime.fromtimestamp(int(created_at) / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass

        listings.append(
            JobListing(
                source="lever",
                source_job_id=str(p["id"]),
                company=slug,
                title=p.get("text", ""),
                jd_text=jd_text,
                jd_url=p.get("hostedUrl", ""),
                ats_kind=ATSKind.lever,
                location=categories.get("location"),
                remote=(categories.get("commitment", "").lower() == "remote") or None,
                apply_url=p.get("applyUrl") or p.get("hostedUrl"),
                posted_at=posted_at,
                extra={"slug": slug, "team": categories.get("team")},
            )
        )
    return listings


class LeverAdapter:
    name = "lever"

    def fetch(self, config: dict) -> Iterable[JobListing]:
        slugs = [entry["slug"] for entry in (config or {}).get("lever", []) if entry.get("slug")]
        with httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"}) as client:
            for slug in slugs:
                try:
                    for listing in fetch_board(slug, client=client):
                        yield listing
                except httpx.HTTPError as e:
                    log.warning("lever slug=%s fetch failed: %s", slug, e)
