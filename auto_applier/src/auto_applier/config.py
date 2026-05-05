from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""

    data_dir: Path = Field(default=Path("data"), alias="AUTO_APPLIER_DATA_DIR")
    db_url: str = Field(default="sqlite:///data/auto_applier.sqlite", alias="AUTO_APPLIER_DB_URL")

    tailor_model: str = "claude-sonnet-4-6"
    score_model: str = "claude-haiku-4-5"

    anthropic_daily_budget_usd: float = 5.00
    tailor_daily_limit: int = 30

    approval_host: str = "127.0.0.1"
    approval_port: int = 8765

    linkedin_li_at: str = ""
    indeed_enabled: bool = False
    linkedin_enabled: bool = False

    playwright_headless: bool = False
    submit_essay_mode: str = "attempt"  # flag | attempt | aggressive
    submit_per_company_cooldown_days: int = 14

    # IMAP outcome-tracker settings (live.com / outlook.com / Gmail).
    imap_host: str = ""        # e.g. outlook.office365.com or imap.gmail.com
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""    # App Password — see README
    imap_folder: str = "INBOX"
    imap_lookback_days: int = 30

    @property
    def profile_path(self) -> Path:
        return self.data_dir / "profile.yaml"

    @property
    def base_resume_path(self) -> Path:
        return self.data_dir / "base_resume.md"

    @property
    def companies_path(self) -> Path:
        return self.data_dir / "companies.yaml"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"


settings = Settings()
