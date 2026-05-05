"""Daily-budget kill-switch.

Tracks Claude token usage in the `usage` table and lets the pipeline check
"have I exceeded today's budget?" before making expensive calls.

Pricing (USD per million tokens, as of 2026-04). Not authoritative — adjust
when Anthropic moves prices. Cache reads are 10% of input price.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import select

from . import config as _config
from .db import session_scope
from .models import Usage
from .utils.logging import get_logger

log = get_logger(__name__)


_PRICING = {
    "claude-opus-4-7":     (5.00, 25.00),
    "claude-opus-4-6":     (5.00, 25.00),
    "claude-opus-4-5":     (5.00, 25.00),
    "claude-sonnet-4-6":   (3.00, 15.00),
    "claude-sonnet-4-5":   (3.00, 15.00),
    "claude-haiku-4-5":    (1.00,  5.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def cost_for_call(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> float:
    """Return the dollar cost for a single Claude call."""
    in_price, out_price = _PRICING.get(model, (3.00, 15.00))  # safe default ~ Sonnet tier
    base_input = (input_tokens / 1_000_000.0) * in_price
    cache_read = (cache_read_input_tokens / 1_000_000.0) * in_price * 0.10
    cache_write = (cache_creation_input_tokens / 1_000_000.0) * in_price * 1.25
    output = (output_tokens / 1_000_000.0) * out_price
    return base_input + cache_read + cache_write + output


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class DailyUsage:
    day: str
    cost_usd: float
    rows: int


def today_usage() -> DailyUsage:
    day = _today()
    with session_scope() as session:
        rows = session.exec(select(Usage).where(Usage.day == day)).all()
    return DailyUsage(day=day, cost_usd=sum(r.cost_usd for r in rows), rows=len(rows))


def assert_under_budget(stage: str = "") -> None:
    """Raise BudgetExceededError if today's spend has already exceeded the cap."""
    cap = float(_config.settings.anthropic_daily_budget_usd or 0)
    if cap <= 0:
        return  # no budget set
    usage = today_usage()
    if usage.cost_usd >= cap:
        raise BudgetExceededError(
            f"daily budget exceeded for {usage.day}: "
            f"${usage.cost_usd:.2f} >= ${cap:.2f} cap "
            f"(stage={stage}). Raise ANTHROPIC_DAILY_BUDGET_USD in .env to continue."
        )


def record_usage(
    *,
    stage: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> float:
    """Record a single Claude call's token use + cost. Returns the cost."""
    cost = cost_for_call(
        model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
    )
    row = Usage(
        day=_today(),
        stage=stage,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cost_usd=cost,
    )
    with session_scope() as session:
        session.add(row)
        session.commit()
    return cost


def record_from_response(*, stage: str, model: str, usage: Any) -> float:
    """Convenience: record from an Anthropic response.usage object."""
    return record_usage(
        stage=stage,
        model=model,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )
