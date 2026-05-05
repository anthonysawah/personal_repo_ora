from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..models import Application, Job
from ..profile.schema import Profile


@dataclass
class SubmitResult:
    ok: bool
    confirmation_text: str = ""
    confirmation_screenshot_path: str | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class SubmitContext:
    job: Job
    application: Application
    profile: Profile
    resume_pdf_path: Path
    resume_docx_path: Path | None = None
    answers: dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    # How to handle open-ended essay questions (Workday/iCIMS often have these):
    #   "flag"       — bail with needs_human (safest, default behavior pre-override)
    #   "attempt"    — compose a grounded answer using profile facts only; blank if nothing
    #   "aggressive" — always answer; extrapolate within domain/seniority, never invent
    #                  specific companies/dates/events the candidate never had
    essay_mode: str = "attempt"


class SubmitterAdapter(Protocol):
    name: str

    def submit(self, ctx: SubmitContext) -> SubmitResult: ...
