from __future__ import annotations

from typing import Iterable

import httpx
from bs4 import BeautifulSoup

from ..models import ATSKind
from ..utils.logging import get_logger
from .base import JobListing

log = get_logger(__name__)

# Ashby's public job board GraphQL endpoint. This schema is stable but undocumented;
# if it breaks, users can disable `ashby` in companies.yaml.
URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"

QUERY = """\
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
    teams { id name parentTeamId }
    jobPostings {
      id title teamId locationName employmentType isListed publishedDate
      address { postalAddress { addressRegion addressLocality addressCountry } }
      descriptionHtml
    }
  }
}
"""


def _strip(html: str) -> str:
    return BeautifulSoup(html or "", "lxml").get_text("\n").strip()


def fetch_board(slug: str, client: httpx.Client | None = None) -> list[JobListing]:
    owns = client is None
    client = client or httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"})
    try:
        resp = client.post(
            URL,
            json={
                "operationName": "ApiJobBoardWithTeams",
                "variables": {"organizationHostedJobsPageName": slug},
                "query": QUERY,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns:
            client.close()

    board = (data.get("data") or {}).get("jobBoard") or {}
    postings = board.get("jobPostings") or []
    listings: list[JobListing] = []
    for p in postings:
        if not p.get("isListed", True):
            continue
        listings.append(
            JobListing(
                source="ashby",
                source_job_id=str(p["id"]),
                company=slug,
                title=p.get("title", ""),
                jd_text=_strip(p.get("descriptionHtml") or ""),
                jd_url=f"https://jobs.ashbyhq.com/{slug}/{p['id']}",
                ats_kind=ATSKind.ashby,
                location=p.get("locationName"),
                apply_url=f"https://jobs.ashbyhq.com/{slug}/{p['id']}/application",
                extra={"slug": slug},
            )
        )
    return listings


class AshbyAdapter:
    name = "ashby"

    def fetch(self, config: dict) -> Iterable[JobListing]:
        slugs = [entry["slug"] for entry in (config or {}).get("ashby", []) if entry.get("slug")]
        with httpx.Client(timeout=30.0, headers={"User-Agent": "auto_applier/0.1"}) as client:
            for slug in slugs:
                try:
                    for listing in fetch_board(slug, client=client):
                        yield listing
                except httpx.HTTPError as e:
                    log.warning("ashby slug=%s fetch failed: %s", slug, e)
