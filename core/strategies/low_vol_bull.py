"""Calm-vol template: high long fraction and elevated leverage."""

from typing import Optional

import pandas as pd

from core.hmm.regime_state import RegimeState
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import Signal
from core.strategies.stops import _compute_stop_and_params, _cap_long_stop_below_entry, _long_signal


class LowVolBullStrategy(BaseStrategy):
    """Lowest volatility third: long, ~95% allocation, ~1.25x leverage, wide ATR/EMA stop."""

    name = "LowVolBullStrategy"

    def generate_signal(self, symbol, bars, regime_state) -> Optional[Signal]:
        """Return a full-size long or ``None`` if ATR/price are degenerate."""
        price, atr, ema50 = _compute_stop_and_params(bars)
        if atr == 0 or price == 0:
            return None

        stop = _cap_long_stop_below_entry(price, max(price - 3 * atr, ema50 - 0.5 * atr), atr)
        alloc = self.config.get("low_vol_allocation", 0.95)
        leverage = self.config.get("low_vol_leverage", 1.25)
        reason = (
            f"Low-vol regime ({regime_state.label}, p={regime_state.probability:.2f}). "
            "Calm market — full allocation with modest leverage."
        )
        return _long_signal(
            symbol, regime_state, price, stop, alloc, leverage, reason, self.name,
            {"atr": atr, "ema50": ema50},
        )
