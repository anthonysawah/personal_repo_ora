from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ATSKind(str, Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    workday = "workday"
    icims = "icims"
    unknown = "unknown"


class AppStatus(str, Enum):
    discovered = "discovered"
    scored = "scored"
    tailored = "tailored"
    pending_approval = "pending_approval"
    approved = "approved"
    submitted = "submitted"
    failed = "failed"
    skipped = "skipped"


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    source_job_id: str = Field(index=True)
    company: str
    title: str
    location: Optional[str] = None
    remote: Optional[bool] = None
    jd_text: str
    jd_url: str
    apply_url: Optional[str] = None
    ats_kind: ATSKind = Field(default=ATSKind.unknown)
    posted_at: Optional[datetime] = None
    discovered_at: datetime = Field(default_factory=utcnow, index=True)
    dedupe_hash: str = Field(index=True)


class Application(SQLModel, table=True):
    __tablename__ = "applications"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    status: AppStatus = Field(default=AppStatus.scored, index=True)
    fit_score: Optional[int] = None
    reason: Optional[str] = None
    tailored_resume_json: Optional[str] = None
    resume_pdf_path: Optional[str] = None
    resume_docx_path: Optional[str] = None
    cover_letter_md: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    submitted_at: Optional[datetime] = None
    confirmation_text: Optional[str] = None
    confirmation_screenshot_path: Optional[str] = None
    error: Optional[str] = None


class Answer(SQLModel, table=True):
    __tablename__ = "answers"

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    question: str
    answer: str
    source: str  # profile | llm | user_override
    confidence: Optional[float] = None


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    stage: str
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: Optional[datetime] = None
    stats_json: Optional[str] = None
    error: Optional[str] = None


class Usage(SQLModel, table=True):
    """Token usage row per Claude call. Used by the daily-budget kill-switch."""

    __tablename__ = "usage"

    id: Optional[int] = Field(default=None, primary_key=True)
    day: str = Field(index=True)  # YYYY-MM-DD UTC
    stage: str  # "score" | "tailor" | "ingest" | "submit" | other
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)
