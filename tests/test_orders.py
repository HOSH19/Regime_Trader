"""
Tests for order executor in dry-run mode (no real API calls).
"""

import os
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_signal(symbol="SPY", entry=400.0, stop=390.0):
    from core.regime_strategies import Signal
    return Signal(
        symbol=symbol, direction="LONG", confidence=0.75,
        entry_price=entry, stop_loss=stop, take_profit=None,
        position_size_pct=0.20, leverage=1.0,
        regime_id=0, regime_name="BULL", regime_probability=0.75,
        timestamp=datetime.utcnow(), reasoning="test", strategy_name="Test",
    )


def _make_risk_decision(signal):
    from core.risk_manager import RiskDecision
    return RiskDecision(approved=True, modified_signal=signal, rejection_reason="")


def _mock_alpaca():
    client = MagicMock()
    account = MagicMock()
    account.equity = "100000"
    client.get_account.return_value = account
    return client


class TestOrderExecutorDryRun:
    def test_dry_run_submit_returns_trade_id(self):
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        signal = _make_signal()
        decision = _make_risk_decision(signal)
        order_id = executor.submit_order(signal, decision)
        assert order_id is not None
        assert "SPY" in order_id

    def test_rejected_signal_not_submitted(self):
        from broker.order_executor import OrderExecutor
        from core.risk_manager import RiskDecision
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        signal = _make_signal()
        rejected = RiskDecision(approved=False, modified_signal=None, rejection_reason="test rejection")
        order_id = executor.submit_order(signal, rejected)
        assert order_id is None

    def test_modify_stop_only_tightens(self):
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        result = executor.modify_stop("SPY", "order123", new_stop=385.0, current_stop=390.0)
        assert result is False

    def test_modify_stop_tighter_accepted(self):
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        result = executor.modify_stop("SPY", "order123", new_stop=395.0, current_stop=390.0)
        assert result is True

    def test_close_all_dry_run(self):
        from broker.order_executor import OrderExecutor
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        result = executor.close_all_positions()
        assert result is True
        client.trading_client.close_all_positions.assert_not_called()

    def test_trade_id_is_unique(self):
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
        from broker.order_executor import OrderExecutor
        from core.regime_strategies import Signal
        client = _mock_alpaca()
        executor = OrderExecutor(client, dry_run=True)
        signal = Signal(
            symbol="SPY", direction="LONG", confidence=0.75,
            entry_price=400.0, stop_loss=390.0, take_profit=420.0,
            position_size_pct=0.20, leverage=1.0,
            regime_id=0, regime_name="BULL", regime_probability=0.75,
            timestamp=datetime.utcnow(), reasoning="test", strategy_name="Test",
        )
        decision = _make_risk_decision(signal)
        order_id = executor.submit_bracket_order(signal, decision)
        assert order_id is not None
