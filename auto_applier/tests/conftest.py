from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    """Point settings at a per-test tmp data dir so tests don't touch real data/."""
    monkeypatch.setenv("AUTO_APPLIER_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "auto_applier.sqlite"
    monkeypatch.setenv("AUTO_APPLIER_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "test-key"))

    # Reset the settings + db singletons so they re-read env.
    import auto_applier.config as cfg
    import auto_applier.db as dbmod

    fresh = cfg.Settings()
    # Mutate the existing Settings object in place so stale `from ..config import settings`
    # references across library code still see the new values. (Avoid that import shape
    # in production code — it's brittle — but we defensively support it here.)
    for field in type(fresh).model_fields:
        setattr(cfg.settings, field, getattr(fresh, field))
    dbmod._engine = None

    yield tmp_path


@pytest.fixture
def sample_profile():
    from auto_applier.profile.schema import (
        Compensation,
        Education,
        Experience,
        Personal,
        Profile,
        WorkAuth,
    )

    return Profile(
        personal=Personal(
            full_name="Ada Lovelace",
            email="ada@example.com",
            phone="+1 555 000 0000",
            city="London",
            state="",
            country="UK",
            linkedin_url="https://linkedin.com/in/ada",
            github_url="https://github.com/ada",
        ),
        work_authorization=WorkAuth(us_work_auth="US Citizen", needs_sponsorship_now=False),
        compensation=Compensation(desired_min_usd=160000, desired_max_usd=220000),
        must_have_skills=["Python", "distributed systems", "PostgreSQL"],
        nice_to_have_skills=["Go", "Kubernetes"],
        technologies=["Python", "Go", "PostgreSQL", "Redis", "AWS", "Kubernetes"],
        fundamentals=["algorithms", "systems design"],
        summary="Backend engineer focused on payments infra.",
        experience=[
            Experience(
                company="Analytical Engine Co",
                title="Senior Engineer",
                start="2022-01",
                end=None,
                location="Remote",
                technologies=["Python", "PostgreSQL"],
                bullets=["Built a payments ledger handling 10M txns/day"],
            )
        ],
        education=[
            Education(institution="Cambridge", degree="BA", field="Math", start="1830", end="1833")
        ],
        target_titles=["Senior Backend Engineer", "Staff Engineer"],
        target_locations=["Remote"],
        remote_ok=True,
    )


@pytest.fixture
def sample_base_resume():
    return (
        "# Ada Lovelace\n\nBackend engineer, payments infra.\n\n"
        "## Experience\n\n### Analytical Engine Co — Senior Engineer\n\n"
        "- Built payments ledger.\n- Scaled systems.\n"
    )
