from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from auto_applier.discovery.greenhouse import fetch_board
from auto_applier.models import ATSKind


def test_fetch_board_parses_listings():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "greenhouse_stripe.json").read_text()
    )

    with respx.mock(base_url="https://boards-api.greenhouse.io") as router:
        router.get("/v1/boards/stripe/jobs").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        listings = fetch_board("stripe")

    assert len(listings) == 2
    backend = next(l for l in listings if "Backend" in l.title)
    assert backend.company == "stripe"
    assert backend.ats_kind == ATSKind.greenhouse
    assert "Python" in backend.jd_text
    assert backend.apply_url.startswith("https://boards.greenhouse.io/stripe/")
    assert backend.location == "San Francisco, CA / Remote"
    assert backend.dedupe_hash()  # non-empty
