"""
Track open positions, P&L, and sync with Alpaca on startup.
Updates PortfolioState and CircuitBreaker on every fill via WebSocket.
"""

import logging
import threading
from datetime import datetime
from typing import Dict, Optional

from core.risk_manager import PortfolioState, Position

logger = logging.getLogger(__name__)


class PositionTracker:
    def __init__(self, alpaca_client, portfolio_state: PortfolioState):
        self.client = alpaca_client
        self.portfolio = portfolio_state
        self._lock = threading.Lock()
        self._ws_thread: Optional[threading.Thread] = None

    def sync_from_alpaca(self):
        """Reconcile tracked positions with actual Alpaca positions on startup."""
        try:
            account = self.client.get_account()
            self.portfolio.equity = float(account.equity)
            self.portfolio.cash = float(account.cash)
            self.portfolio.buying_power = float(account.buying_power)

            if self.portfolio.peak_equity == 0:
                self.portfolio.peak_equity = self.portfolio.equity
            if self.portfolio.daily_start_equity == 0:
                self.portfolio.daily_start_equity = self.portfolio.equity
            if self.portfolio.weekly_start_equity == 0:
                self.portfolio.weekly_start_equity = self.portfolio.equity

            alpaca_positions = self.client.get_positions()
            with self._lock:
                self.portfolio.positions = {}
                for pos in alpaca_positions:
                    self.portfolio.positions[pos.symbol] = Position(
                        symbol=pos.symbol,
                        shares=float(pos.qty),
                        entry_price=float(pos.avg_entry_price),
                        entry_time=datetime.utcnow(),
                        current_price=float(pos.current_price),
                        stop_loss=0.0,
                        regime_at_entry="UNKNOWN",
                    )
            logger.info(
                f"Portfolio synced: equity=${self.portfolio.equity:,.2f} "
                f"positions={list(self.portfolio.positions.keys())}"
            )
        except Exception as e:
            logger.error(f"sync_from_alpaca failed: {e}")

    def update_position_price(self, symbol: str, price: float):
        with self._lock:
            if symbol in self.portfolio.positions:
                self.portfolio.positions[symbol].current_price = price
            self.portfolio.last_updated = datetime.utcnow()

    def on_fill(self, symbol: str, qty: float, price: float, side: str, trade_id: str, regime: str = ""):
        """Called when a fill notification is received."""
        with self._lock:
            if side.upper() == "BUY":
                if symbol in self.portfolio.positions:
                    pos = self.portfolio.positions[symbol]
                    total_shares = pos.shares + qty
                    pos.entry_price = (pos.entry_price * pos.shares + price * qty) / total_shares
                    pos.shares = total_shares
                else:
                    self.portfolio.positions[symbol] = Position(
                        symbol=symbol,
                        shares=qty,
                        entry_price=price,
                        entry_time=datetime.utcnow(),
                        current_price=price,
                        stop_loss=0.0,
                        regime_at_entry=regime,
                        trade_id=trade_id,
                    )
            elif side.upper() == "SELL":
                if symbol in self.portfolio.positions:
                    pos = self.portfolio.positions[symbol]
                    pos.shares -= qty
                    if pos.shares <= 0:
                        del self.portfolio.positions[symbol]

        self._refresh_equity()
        logger.info(f"Fill: {side} {qty} {symbol} @ ${price:.2f} trade_id={trade_id}")

    def update_stop(self, symbol: str, new_stop: float):
        with self._lock:
            if symbol in self.portfolio.positions:
                self.portfolio.positions[symbol].stop_loss = new_stop

    def _refresh_equity(self):
        try:
            account = self.client.get_account()
            with self._lock:
                self.portfolio.equity = float(account.equity)
                self.portfolio.cash = float(account.cash)
                self.portfolio.buying_power = float(account.buying_power)
                self.portfolio.daily_pnl = self.portfolio.equity - self.portfolio.daily_start_equity
                self.portfolio.weekly_pnl = self.portfolio.equity - self.portfolio.weekly_start_equity
                if self.portfolio.equity > self.portfolio.peak_equity:
                    self.portfolio.peak_equity = self.portfolio.equity
        except Exception as e:
            logger.warning(f"_refresh_equity failed: {e}")

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.portfolio.positions.get(symbol)

    def get_all_positions(self) -> Dict[str, Position]:
        with self._lock:
            return dict(self.portfolio.positions)

    def reset_daily(self):
        self.portfolio.daily_start_equity = self.portfolio.equity
        self.portfolio.daily_pnl = 0.0

    def reset_weekly(self):
        self.portfolio.weekly_start_equity = self.portfolio.equity
        self.portfolio.weekly_pnl = 0.0
