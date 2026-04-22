from __future__ import annotations

from pathlib import Path

import yaml

from .. import config as _config
from .schema import Profile


def load_profile(path: Path | None = None) -> Profile:
    p = path or _config.settings.profile_path
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run `auto_applier init` first, then fill it in."
        )
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Profile.model_validate(raw)


def load_base_resume(path: Path | None = None) -> str:
    p = path or _config.settings.base_resume_path
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run `auto_applier init` first, then fill it in."
        )
    return p.read_text(encoding="utf-8")
