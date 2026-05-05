"""Discovery-side filters: exclude companies / keywords before they hit the DB."""

from __future__ import annotations

from dataclasses import dataclass

from .base import JobListing


@dataclass
class ExcludeRules:
    companies: list[str]  # case-insensitive substring match against company name
    keywords: list[str]  # case-insensitive substring match against JD text

    @classmethod
    def from_config(cls, config: dict | None) -> "ExcludeRules":
        cfg = ((config or {}).get("exclude") or {})
        return cls(
            companies=[c.strip().lower() for c in (cfg.get("companies") or []) if c.strip()],
            keywords=[k.strip().lower() for k in (cfg.get("keywords") or []) if k.strip()],
        )

    def is_excluded(self, listing: JobListing) -> tuple[bool, str | None]:
        company_lc = (listing.company or "").lower()
        for needle in self.companies:
            if needle and needle in company_lc:
                return True, f"excluded company: {needle}"
        if self.keywords:
            jd_lc = (listing.jd_text or "").lower()
            for needle in self.keywords:
                if needle and needle in jd_lc:
                    return True, f"excluded keyword: {needle}"
        return False, None
