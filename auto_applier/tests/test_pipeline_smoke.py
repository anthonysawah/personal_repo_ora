from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx
import yaml

from auto_applier.config import settings
from auto_applier.db import init_db, session_scope
from auto_applier.models import Application, AppStatus, Job
from auto_applier.pipeline import run_discover, run_score
from auto_applier.profile.scaffold import scaffold


def test_discover_and_prefilter_only(sample_profile):
    # Write a minimal companies.yaml + profile.yaml + base_resume.md into the test data dir.
    scaffold(settings.data_dir)
    # Replace stub profile with our real sample profile.
    settings.profile_path.write_text(
        yaml.safe_dump(sample_profile.model_dump(), sort_keys=True), encoding="utf-8"
    )
    settings.companies_path.write_text(
        yaml.safe_dump({"greenhouse": [{"slug": "stripe"}]}), encoding="utf-8"
    )

    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "greenhouse_stripe.json").read_text()
    )
    init_db()

    with respx.mock(base_url="https://boards-api.greenhouse.io") as router:
        router.get("/v1/boards/stripe/jobs").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        d = run_discover(["greenhouse"])

    assert d["inserted"] == 2

    s = run_score(llm=False)
    assert s["considered"] == 2
    assert s["scored"] + s["filtered"] == 2

    with session_scope() as session:
        from sqlmodel import select

        apps = session.exec(select(Application)).all()
        jobs = session.exec(select(Job)).all()
    assert len(jobs) == 2
    assert len(apps) == 2
    scored = [a for a in apps if a.status == AppStatus.scored]
    skipped = [a for a in apps if a.status == AppStatus.skipped]
    # Backend role should score, Frontend Designer should skip.
    assert len(scored) == 1
    assert len(skipped) == 1
