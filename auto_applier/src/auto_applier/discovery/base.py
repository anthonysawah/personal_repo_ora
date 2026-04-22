from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional, Protocol

from ..models import ATSKind


@dataclass
class JobListing:
    source: str
    source_job_id: str
    company: str
    title: str
    jd_text: str
    jd_url: str
    ats_kind: ATSKind = ATSKind.unknown
    location: Optional[str] = None
    remote: Optional[bool] = None
    apply_url: Optional[str] = None
    posted_at: Optional[datetime] = None
    extra: dict = field(default_factory=dict)

    def dedupe_hash(self) -> str:
        h = hashlib.sha256()
        h.update(self.source.encode())
        h.update(b"\0")
        h.update(self.source_job_id.encode())
        h.update(b"\0")
        h.update(self.company.encode())
        h.update(b"\0")
        h.update(self.title.encode())
        return h.hexdigest()


class DiscoveryAdapter(Protocol):
    name: str

    def fetch(self, config: dict) -> Iterable[JobListing]: ...
