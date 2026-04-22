from __future__ import annotations

from auto_applier.scoring.filter import prefilter_score


def test_prefilter_high_on_matching_title_and_skills(sample_profile):
    jd = "Looking for a Senior Backend Engineer with Python, distributed systems, PostgreSQL."
    score = prefilter_score(sample_profile, jd, "Senior Backend Engineer")
    assert score >= 60


def test_prefilter_low_on_unrelated(sample_profile):
    jd = "Frontend designer with Figma and motion design skills."
    score = prefilter_score(sample_profile, jd, "Frontend Designer")
    assert score < 60
