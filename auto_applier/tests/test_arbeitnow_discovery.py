from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from auto_applier.discovery.arbeitnow import fetch
from auto_applier.models import ATSKind


def test_arbeitnow_fetch_and_filter_by_query():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "arbeitnow_sample.json").read_text()
    )
    with respx.mock(base_url="https://www.arbeitnow.com") as router:
        router.get("/api/job-board-api").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        listings = fetch(queries=["site reliability"], max_pages=1)

    assert len(listings) == 1
    sre = listings[0]
    assert sre.company == "Stripe"
    assert sre.ats_kind == ATSKind.greenhouse
    assert sre.remote is True


def test_arbeitnow_no_query_returns_all():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "arbeitnow_sample.json").read_text()
    )
    with respx.mock(base_url="https://www.arbeitnow.com") as router:
        router.get("/api/job-board-api").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        listings = fetch(queries=None, max_pages=1)
    assert len(listings) == 3
    companies = {l.company for l in listings}
    assert {"Stripe", "Oracle", "Acme Design Co"} == companies


def test_arbeitnow_remote_only_filter():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "arbeitnow_sample.json").read_text()
    )
    with respx.mock(base_url="https://www.arbeitnow.com") as router:
        router.get("/api/job-board-api").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        listings = fetch(queries=None, remote_only=True, max_pages=1)
    # Oracle one is remote=false, gets excluded.
    assert all(l.remote for l in listings)
    assert all(l.company != "Oracle" for l in listings)
