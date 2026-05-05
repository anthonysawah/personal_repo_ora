from __future__ import annotations

from auto_applier.ats.playwright_generic import (
    _job_location_states,
    _select_address_for_job,
)


PROFILE = {
    "personal": {
        "full_name": "Anthony Sawah",
        "street": "182 S Waters Edge Dr",
        "city": "Glendale Heights",
        "state": "IL",
        "zip": "60139",
        "country": "USA",
        "additional_addresses": [
            {
                "label": "Texas",
                "street": "5315 Ocotillo Pt",
                "city": "San Antonio",
                "state": "TX",
                "zip": "78261",
                "country": "USA",
                "use_for_states": ["TX"],
            }
        ],
    }
}


def test_state_extraction_handles_codes_and_names():
    assert _job_location_states("Austin, TX") == {"TX"}
    assert _job_location_states("Austin, Texas") == {"TX"}
    assert _job_location_states("Glendale Heights, IL / Remote") == {"IL"}
    assert _job_location_states("Remote") == set()
    assert _job_location_states(None) == set()


def test_picks_tx_address_for_tx_jobs():
    addr = _select_address_for_job(PROFILE, "Austin, TX")
    assert addr["state"] == "TX"
    assert addr["city"] == "San Antonio"
    assert addr["street"] == "5315 Ocotillo Pt"


def test_picks_primary_for_il_jobs():
    addr = _select_address_for_job(PROFILE, "Chicago, IL")
    assert addr["state"] == "IL"
    assert addr["city"] == "Glendale Heights"
    assert addr["street"] == "182 S Waters Edge Dr"


def test_picks_primary_when_unmatched():
    addr = _select_address_for_job(PROFILE, "Remote")
    assert addr["state"] == "IL"


def test_no_additional_addresses_falls_back():
    minimal = {"personal": {"city": "X", "state": "CA", "country": "USA"}}
    addr = _select_address_for_job(minimal, "Austin, TX")
    assert addr["state"] == "CA"
