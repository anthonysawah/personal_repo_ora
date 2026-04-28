from __future__ import annotations

from pathlib import Path

from auto_applier.profile.resume_ingest import (
    ResumeDoc,
    collect_resumes,
    dedupe_resumes,
)


def _resume_text(name: str, variant: str = "") -> str:
    return (
        f"# {name}\n\n"
        "Experienced software engineer focused on backend systems.\n\n"
        "## Experience\n\n"
        "### Acme Corp - Senior Engineer (2022 - Present)\n"
        "- Built distributed payment ledger handling 10M txns/day\n"
        "- Led migration from monolith to microservices\n"
        f"{variant}\n"
        "## Skills\n"
        "Python, Go, PostgreSQL, Kubernetes, AWS\n"
        "## Education\n"
        "MIT, BS Computer Science, 2018\n"
    )


def test_collect_resumes_skips_short_and_unsupported(tmp_path):
    (tmp_path / "good.txt").write_text(_resume_text("Anthony Sawah"), encoding="utf-8")
    (tmp_path / "tiny.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG fake")

    docs = collect_resumes(tmp_path)
    assert len(docs) == 1
    assert docs[0].path.name == "good.txt"
    assert docs[0].char_len > 200


def test_dedupe_drops_near_identical_keeps_longest(tmp_path):
    base = _resume_text("Anthony Sawah")
    longer = base + "\n\n## Projects\n- Side project: built a thing\n- Built another thing\n"
    very_different = (
        "# Anthony Sawah\n\n## Experience\n### Different Co - Designer\n"
        "- Designed graphics\n- Made motion design\n\n## Skills\nFigma, motion\n"
    )

    docs = [
        ResumeDoc(path=tmp_path / "v1.pdf", text=base, char_len=len(base)),
        ResumeDoc(path=tmp_path / "v2.pdf", text=base + "\nminor tweak\n", char_len=len(base) + 14),
        ResumeDoc(path=tmp_path / "v3.pdf", text=longer, char_len=len(longer)),
        ResumeDoc(path=tmp_path / "designer.pdf", text=very_different, char_len=len(very_different)),
    ]

    kept = dedupe_resumes(docs)
    # The three near-duplicate engineering resumes should collapse to one (the longest);
    # the designer resume is genuinely different and stays.
    assert len(kept) == 2
    names = {d.path.name for d in kept}
    assert "v3.pdf" in names  # longest of the duplicates wins
    assert "designer.pdf" in names
