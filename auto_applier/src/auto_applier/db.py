from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from . import config as _config
from . import models  # noqa: F401  register tables

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _config.settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(_config.settings.db_url, echo=False)
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
