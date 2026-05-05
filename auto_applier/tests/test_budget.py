from __future__ import annotations

import pytest

from auto_applier import budget as _budget
from auto_applier import config as _config
from auto_applier.db import init_db


def test_cost_for_call_haiku_basic():
    cost = _budget.cost_for_call(
        "claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    # 1M input @ $1 + 1M output @ $5 = $6
    assert round(cost, 2) == 6.00


def test_cost_for_call_sonnet_with_caching():
    # 1M input + 1M output + 1M cache_read (10% of input price) + 1M cache_creation (1.25x)
    cost = _budget.cost_for_call(
        "claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    # 3 + 15 + 0.30 + 3.75 = 22.05
    assert round(cost, 2) == 22.05


def test_record_and_assert_under_budget():
    init_db()
    _config.settings.anthropic_daily_budget_usd = 0.10  # tight cap

    # First record under cap — fine.
    cost1 = _budget.record_usage(
        stage="test", model="claude-haiku-4-5", input_tokens=1000, output_tokens=1000
    )
    assert cost1 > 0
    _budget.assert_under_budget("test")  # still fine

    # Pump enough usage to bust the cap.
    _budget.record_usage(
        stage="test",
        model="claude-sonnet-4-6",
        input_tokens=200_000,
        output_tokens=200_000,
    )

    with pytest.raises(_budget.BudgetExceededError):
        _budget.assert_under_budget("test")


def test_zero_budget_means_no_cap():
    init_db()
    _config.settings.anthropic_daily_budget_usd = 0
    _budget.record_usage(
        stage="test",
        model="claude-sonnet-4-6",
        input_tokens=10_000_000,
        output_tokens=10_000_000,
    )
    # No exception even with huge usage
    _budget.assert_under_budget("test")
