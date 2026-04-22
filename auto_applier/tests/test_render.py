from __future__ import annotations

from auto_applier.tailor.render_pdf import render_html
from auto_applier.tailor.tailor import TailoredExperience, TailoredResume


def test_render_html_contains_expected_fields(sample_profile):
    tailored = TailoredResume(
        summary="Payments-focused backend engineer.",
        skills=["Python", "PostgreSQL", "Kubernetes"],
        experience=[
            TailoredExperience(
                company="Analytical Engine Co",
                title="Senior Engineer",
                start="2022-01",
                end=None,
                location="Remote",
                bullets=["Built ledger handling 10M txns/day."],
            )
        ],
        keywords_used=["Python", "PostgreSQL"],
        cover_letter_md="Dear team, …",
    )
    html = render_html(sample_profile, tailored)
    assert "Ada Lovelace" in html
    assert "Senior Engineer" in html
    assert "Built ledger handling 10M txns/day." in html
    assert "Python" in html
