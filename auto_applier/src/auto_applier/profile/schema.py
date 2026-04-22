from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Personal(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""


class WorkAuth(BaseModel):
    us_work_auth: str = ""  # e.g. "US Citizen", "Green Card", "H1-B"
    needs_sponsorship_now: Optional[bool] = None
    needs_sponsorship_future: Optional[bool] = None
    visa_status: str = ""


class Compensation(BaseModel):
    desired_min_usd: Optional[int] = None
    desired_max_usd: Optional[int] = None
    currency: str = "USD"
    open_to_equity: Optional[bool] = None


class Experience(BaseModel):
    company: str
    title: str
    start: str  # YYYY-MM
    end: Optional[str] = None  # YYYY-MM, None = present
    location: str = ""
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str
    degree: str
    field: str = ""
    start: str = ""
    end: str = ""
    gpa: Optional[float] = None
    honors: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    description: str
    url: str = ""
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class QAEntry(BaseModel):
    question: str
    answer: str


class Profile(BaseModel):
    personal: Personal = Field(default_factory=Personal)
    work_authorization: WorkAuth = Field(default_factory=WorkAuth)
    compensation: Compensation = Field(default_factory=Compensation)

    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    fundamentals: list[str] = Field(default_factory=list)

    summary: str = ""
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)

    target_titles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    remote_ok: bool = True
    relocate_ok: bool = False

    qa_bank: list[QAEntry] = Field(default_factory=list)
