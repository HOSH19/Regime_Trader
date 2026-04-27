"""Dataclass for one open equity position and derived P&L metrics."""

from dataclasses import dataclass
from datetime import datetime

from core.timeutil import ensure_utc, utc_now


@dataclass
class Position:
    """One live or paper position with entry context and a protective stop."""

    symbol: str
    shares: float
    entry_price: float
    entry_time: datetime
    current_price: float
    stop_loss: float
    regime_at_entry: str
    current_regime: str = ""
    trade_id: str = ""

    @property
    def unrealized_pnl(self) -> float:
        """Mark-to-market P&L in dollars (shares × price change)."""
        return (self.current_price - self.entry_price) * self.shares

    @property
    def unrealized_pnl_pct(self) -> float:
        """Fractional return since entry (0 if ``entry_price`` is zero)."""
        if self.entry_price == 0:
            return 0.0
        return (self.current_price / self.entry_price - 1)

    @property
    def holding_period_hours(self) -> float:
        """Hours between ``entry_time`` and now (UTC-aware)."""
        return (utc_now() - ensure_utc(self.entry_time)).total_seconds() / 3600
