"""Mutable snapshot of account equity, positions, and drawdown reference levels."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

from core.risk.position import Position
from core.timeutil import utc_now


@dataclass
class PortfolioState:
    """Inputs for :class:`~core.risk.circuit_breaker.CircuitBreaker` and :class:`~core.risk.risk_manager.RiskManager`."""

    equity: float
    cash: float
    buying_power: float
    positions: Dict[str, Position] = field(default_factory=dict)
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    peak_equity: float = 0.0
    daily_start_equity: float = 0.0
    weekly_start_equity: float = 0.0
    circuit_breaker_status: str = "NORMAL"
    flicker_rate: int = 0
    last_updated: datetime = field(default_factory=utc_now)

    @property
    def drawdown_from_peak(self) -> float:
        """Fractional drawdown versus ``peak_equity`` (negative when underwater)."""
        if self.peak_equity == 0:
            return 0.0
        return (self.equity - self.peak_equity) / self.peak_equity

    @property
    def daily_drawdown(self) -> float:
        """Fractional change versus ``daily_start_equity``."""
        if self.daily_start_equity == 0:
            return 0.0
        return (self.equity - self.daily_start_equity) / self.daily_start_equity

    @property
    def weekly_drawdown(self) -> float:
        """Fractional change versus ``weekly_start_equity``."""
        if self.weekly_start_equity == 0:
            return 0.0
        return (self.equity - self.weekly_start_equity) / self.weekly_start_equity

    @property
    def total_exposure(self) -> float:
        """Gross notional of open positions divided by ``equity``."""
        if self.equity == 0:
            return 0.0
        return sum(p.shares * p.current_price for p in self.positions.values()) / self.equity

    @property
    def n_positions(self) -> int:
        """Count of symbols in ``positions``."""
        return len(self.positions)
