from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from auto_applier.discovery.lever import fetch_board
from auto_applier.models import ATSKind


def test_lever_fetch_board():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "lever_example.json").read_text()
    )
    with respx.mock(base_url="https://api.lever.co") as router:
        router.get("/v0/postings/acme").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        listings = fetch_board("acme")

    assert len(listings) == 1
    l = listings[0]
    assert l.company == "acme"
    assert l.ats_kind == ATSKind.lever
    assert "Python" in l.jd_text
    assert "Build scalable APIs" in l.jd_text
    assert l.apply_url.endswith("/apply")
