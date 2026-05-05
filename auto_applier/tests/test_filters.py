from __future__ import annotations

from auto_applier.discovery.base import JobListing
from auto_applier.discovery.filters import ExcludeRules
from auto_applier.models import ATSKind


def _listing(company: str, jd_text: str = "Generic JD text") -> JobListing:
    return JobListing(
        source="test",
        source_job_id="1",
        company=company,
        title="Engineer",
        jd_text=jd_text,
        jd_url="https://example.com/jobs/1",
        ats_kind=ATSKind.unknown,
    )


def test_exclude_company_substring_case_insensitive():
    rules = ExcludeRules.from_config(
        {"exclude": {"companies": ["Oracle", "Beacon Hill Staffing", "CVS"]}}
    )

    assert rules.is_excluded(_listing("Oracle"))[0] is True
    assert rules.is_excluded(_listing("oracle america"))[0] is True
    assert rules.is_excluded(_listing("Beacon Hill Staffing Group"))[0] is True
    assert rules.is_excluded(_listing("CVS Pharmacy"))[0] is True

    excluded, reason = rules.is_excluded(_listing("Oracle"))
    assert excluded is True
    assert "oracle" in (reason or "").lower()


def test_exclude_lets_unrelated_companies_through():
    rules = ExcludeRules.from_config(
        {"exclude": {"companies": ["Oracle", "CVS"]}}
    )
    assert rules.is_excluded(_listing("Stripe"))[0] is False
    assert rules.is_excluded(_listing("Anthropic"))[0] is False


def test_exclude_keyword_in_jd():
    rules = ExcludeRules.from_config(
        {"exclude": {"keywords": ["secret clearance", "TS/SCI"]}}
    )
    assert rules.is_excluded(_listing("Acme", "Must hold a secret clearance."))[0] is True
    assert rules.is_excluded(_listing("Acme", "Must hold TS/SCI clearance."))[0] is True
    assert rules.is_excluded(_listing("Acme", "Friendly remote SRE role."))[0] is False


def test_empty_config_excludes_nothing():
    rules = ExcludeRules.from_config({})
    assert rules.is_excluded(_listing("Anything"))[0] is False
    rules = ExcludeRules.from_config(None)
    assert rules.is_excluded(_listing("Anything"))[0] is False
