from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Iterable

from bs4 import BeautifulSoup

from ..models import ATSKind
from ..utils.logging import get_logger
from .base import JobListing

log = get_logger(__name__)


def _strip(html: str) -> str:
    return BeautifulSoup(html or "", "lxml").get_text("\n").strip()


def _ats_kind_for(url: str) -> ATSKind:
    u = url.lower()
    if "greenhouse" in u:
        return ATSKind.greenhouse
    if "lever" in u:
        return ATSKind.lever
    if "ashbyhq" in u:
        return ATSKind.ashby
    if "myworkdayjobs" in u or "workday" in u:
        return ATSKind.workday
    if "icims" in u:
        return ATSKind.icims
    return ATSKind.unknown


class RSSAdapter:
    name = "rss"

    def fetch(self, config: dict) -> Iterable[JobListing]:
        import feedparser

        feeds = (config or {}).get("rss") or []
        for feed in feeds:
            url = feed.get("url")
            company = feed.get("company") or feed.get("name") or "rss"
            if not url:
                continue
            try:
                parsed = feedparser.parse(url)
            except Exception as e:  # noqa: BLE001
                log.warning("rss feed=%s failed: %s", url, e)
                continue
            for entry in parsed.entries:
                link = entry.get("link", "")
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                posted_at = None
                if getattr(entry, "published_parsed", None):
                    try:
                        posted_at = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass

                source_job_id = entry.get("id") or link or hashlib.sha256(
                    (title + link).encode()
                ).hexdigest()

                yield JobListing(
                    source="rss",
                    source_job_id=str(source_job_id),
                    company=company,
                    title=title,
                    jd_text=_strip(summary),
                    jd_url=link,
                    ats_kind=_ats_kind_for(link),
                    apply_url=link,
                    posted_at=posted_at,
                    extra={"feed": url},
                )
