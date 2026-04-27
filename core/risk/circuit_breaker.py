"""Drawdown-based circuit breakers that can halt or scale down trading."""

import logging
import os
from typing import Dict, List, Optional, Tuple

from core.risk import constants as risk_constants
from core.risk.portfolio_state import PortfolioState
from core.timeutil import utc_now

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Evaluate portfolio drawdowns against configured halt and reduce thresholds."""

    def __init__(self, config: dict) -> None:
        """Create a breaker from the ``risk`` section of settings.

        Args:
            config: Risk thresholds (daily / weekly / peak drawdown limits, etc.).
        """
        self.cfg = config
        self._trigger_history: List[Dict] = []

    def check(self, portfolio: PortfolioState) -> Tuple[str, str]:
        """Evaluate all rules and return the dominant action.

        Args:
            portfolio: Current equity snapshot and reference levels.

        Returns:
            ``(action, reason)`` where ``action`` is one of ``NORMAL``, ``REDUCE_50_DAY``,
            ``REDUCE_50_WEEK``, ``CLOSE_ALL_DAY``, ``CLOSE_ALL_WEEK``, or ``HALTED``.
        """
        hit = self._locked_halt()
        if hit:
            return hit
        hit = self._peak_equity_halt(portfolio)
        if hit:
            return hit
        hit = self._weekly_halt(portfolio)
        if hit:
            return hit
        hit = self._weekly_reduce(portfolio)
        if hit:
            return hit
        hit = self._daily_halt(portfolio)
        if hit:
            return hit
        hit = self._daily_reduce(portfolio)
        if hit:
            return hit
        return "NORMAL", ""

    def _locked_halt(self) -> Optional[Tuple[str, str]]:
        if os.path.exists(risk_constants.TRADING_HALTED_LOCK):
            return "HALTED", "trading_halted.lock file present — manual intervention required"
        return None

    def _peak_equity_halt(self, portfolio: PortfolioState) -> Optional[Tuple[str, str]]:
        lim = self.cfg.get("max_dd_from_peak", 0.10)
        dd = portfolio.drawdown_from_peak
        if dd > -lim:
            return None
        self._write_lock_file(portfolio)
        return "HALTED", f"Peak DD {dd*100:.1f}% exceeds {lim*100:.0f}% limit"

    def _weekly_halt(self, portfolio: PortfolioState) -> Optional[Tuple[str, str]]:
        lim = self.cfg.get("weekly_dd_halt", 0.07)
        dd = portfolio.weekly_drawdown
        if dd > -lim:
            return None
        return "CLOSE_ALL_WEEK", f"Weekly DD {dd*100:.1f}% exceeds {lim*100:.0f}% limit"

    def _weekly_reduce(self, portfolio: PortfolioState) -> Optional[Tuple[str, str]]:
        lim = self.cfg.get("weekly_dd_reduce", 0.05)
        dd = portfolio.weekly_drawdown
        if dd > -lim:
            return None
        return "REDUCE_50_WEEK", f"Weekly DD {dd*100:.1f}% exceeds {lim*100:.0f}% reduce threshold"

    def _daily_halt(self, portfolio: PortfolioState) -> Optional[Tuple[str, str]]:
        lim = self.cfg.get("daily_dd_halt", 0.03)
        dd = portfolio.daily_drawdown
        if dd > -lim:
            return None
        return "CLOSE_ALL_DAY", f"Daily DD {dd*100:.1f}% exceeds {lim*100:.0f}% limit"

    def _daily_reduce(self, portfolio: PortfolioState) -> Optional[Tuple[str, str]]:
        lim = self.cfg.get("daily_dd_reduce", 0.02)
        dd = portfolio.daily_drawdown
        if dd > -lim:
            return None
        return "REDUCE_50_DAY", f"Daily DD {dd*100:.1f}% exceeds {lim*100:.0f}% reduce threshold"

    def _write_lock_file(self, portfolio: PortfolioState) -> None:
        """Write the peak-drawdown halt lock file; trading resumes only after manual delete."""
        with open(risk_constants.TRADING_HALTED_LOCK, "w") as f:
            f.write(
                f"Trading halted at {utc_now().isoformat()}\n"
                f"Peak DD: {portfolio.drawdown_from_peak*100:.2f}%\n"
                f"Equity: ${portfolio.equity:,.2f}\n"
                f"Delete this file to resume trading.\n"
            )
        logger.critical(
            f"Peak DD limit hit. Created {risk_constants.TRADING_HALTED_LOCK}. Manual deletion required."
        )

    def update(self, portfolio: PortfolioState) -> Tuple[str, str]:
        """Like :meth:`check`, but append to trigger history and log non-``NORMAL`` actions."""
        action, reason = self.check(portfolio)
        if action != "NORMAL":
            self._trigger_history.append({
                "time": utc_now().isoformat(),
                "action": action,
                "reason": reason,
                "equity": portfolio.equity,
                "daily_dd": portfolio.daily_drawdown,
                "weekly_dd": portfolio.weekly_drawdown,
                "peak_dd": portfolio.drawdown_from_peak,
            })
            logger.warning(f"Circuit breaker: {action} — {reason}")
        return action, reason

    def get_history(self) -> List[Dict]:
        """All recorded breaker events (time, action, reason, equity, drawdowns)."""
        return self._trigger_history
