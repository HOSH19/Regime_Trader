"""Tests for :class:`~broker.order_executor.OrderExecutor` in ``dry_run`` (no broker I/O)."""

import os
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.timeutil import utc_now


def _make_signal(symbol="SPY", entry=400.0, stop=390.0):
    """Long signal with 20% allocation and 1.0× leverage.

    Args:
        symbol: Ticker.
        entry: Reference price.
        stop: Protective stop below entry.

    Returns:
        :class:`~core.strategies.signal.Signal` fixture.
    """
    from core.strategies import Signal
    return Signal(
        symbol=symbol, direction="LONG", confidence=0.75,
        entry_price=entry, stop_loss=stop, take_profit=None,
        position_size_pct=0.20, leverage=1.0,
        regime_id=0, regime_name="BULL", regime_probability=0.75,
        timestamp=utc_now(), reasoning="test", strategy_name="Test",
    )


def _make_risk_decision(signal):
    """Approved :class:`~core.risk.risk_decision.RiskDecision` wrapping ``signal``."""
    from core.risk import RiskDecision
    return RiskDecision(approved=True, modified_signal=signal, rejection_reason="")


def _mock_alpaca():
    """``MagicMock`` client with ``get_account().equity == "100000"``."""
    client = MagicMock()
    account = MagicMock()
    account.equity = "100000"
    client.get_account.return_value = account
    return client


class TestOrderExecutorDryRun:
    """Sizing and guard rails without ``trading_client`` side effects."""

    def test_dry_run_submit_returns_trade_id(self):
        """``submit_order`` returns a symbol-prefixed synthetic id."""
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        signal = _make_signal()
        decision = _make_risk_decision(signal)
        order_id = executor.submit_order(signal, decision)
        assert order_id is not None
        assert "SPY" in order_id

    def test_rejected_signal_not_submitted(self):
        """Unapproved decision yields ``None``."""
        from broker.order_executor import OrderExecutor
        from core.risk import RiskDecision
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        signal = _make_signal()
        rejected = RiskDecision(approved=False, modified_signal=None, rejection_reason="test rejection")
        order_id = executor.submit_order(signal, rejected)
        assert order_id is None

    def test_modify_stop_only_tightens(self):
        """Loosening stop returns ``False``."""
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        result = executor.modify_stop("SPY", "order123", new_stop=385.0, current_stop=390.0)
        assert result is False

    def test_modify_stop_tighter_accepted(self):
        """Tightening stop returns ``True`` in dry-run."""
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        result = executor.modify_stop("SPY", "order123", new_stop=395.0, current_stop=390.0)
        assert result is True

    def test_close_all_dry_run(self):
        """``close_all_positions`` short-circuits without SDK call."""
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        result = executor.close_all_positions()
        assert result is True
        client.trading_client.close_all_positions.assert_not_called()

    def test_trade_id_is_unique(self):
        """Each dry-run submit gets a distinct client order id prefix body."""
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        ids = set()
        for _ in range(10):
            signal = _make_signal()
            decision = _make_risk_decision(signal)
            order_id = executor.submit_order(signal, decision)
            ids.add(order_id)
        assert len(ids) == 10, "trade_ids should be unique"

    def test_bracket_order_dry_run(self):
        """Bracket path returns non-null id when TP is set."""
        from broker.order_executor import OrderExecutor
        from core.strategies import Signal
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        signal = Signal(
            symbol="SPY", direction="LONG", confidence=0.75,
            entry_price=400.0, stop_loss=390.0, take_profit=420.0,
            position_size_pct=0.20, leverage=1.0,
            regime_id=0, regime_name="BULL", regime_probability=0.75,
            timestamp=utc_now(), reasoning="test", strategy_name="Test",
        )
        decision = _make_risk_decision(signal)
        order_id = executor.submit_bracket_order(signal, decision)
        assert order_id is not None
