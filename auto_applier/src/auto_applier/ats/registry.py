from __future__ import annotations

from typing import Callable, Type

from ..models import ATSKind
from .base import SubmitterAdapter

_REGISTRY: dict[str, Type[SubmitterAdapter]] = {}


def register(name: str) -> Callable[[Type[SubmitterAdapter]], Type[SubmitterAdapter]]:
    def deco(cls: Type[SubmitterAdapter]) -> Type[SubmitterAdapter]:
        _REGISTRY[name] = cls
        return cls

    return deco


def get(ats_kind: ATSKind | str) -> SubmitterAdapter:
    key = ats_kind.value if isinstance(ats_kind, ATSKind) else ats_kind
    # Ensure built-in adapters are imported & registered.
    from . import greenhouse_api  # noqa: F401
    from . import playwright_generic  # noqa: F401

    cls = _REGISTRY.get(key) or _REGISTRY["__fallback__"]
    return cls()
