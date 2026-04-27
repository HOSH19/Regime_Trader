"""High-vol template: smaller long, wider stop, no short book."""

from typing import Optional

import pandas as pd

from core.hmm.regime_state import RegimeState
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import Signal
from core.strategies.stops import _compute_stop_and_params, _cap_long_stop_below_entry, _long_signal


class HighVolDefensiveStrategy(BaseStrategy):
    """Top vol third: reduced long (~60%), 1.0x leverage, stop at EMA50 − 1×ATR."""

    name = "HighVolDefensiveStrategy"

    def generate_signal(self, symbol, bars, regime_state) -> Optional[Signal]:
        """Return a defensive long or ``None`` if inputs are degenerate."""
        price, atr, ema50 = _compute_stop_and_params(bars)
        if atr == 0 or price == 0:
            return None

        stop = _cap_long_stop_below_entry(price, ema50 - 1.0 * atr, atr)
        alloc = self.config.get("high_vol_allocation", 0.60)
        reason = (
            f"High-vol regime ({regime_state.label}, p={regime_state.probability:.2f}). "
            "Reduced allocation — staying 60% long to catch rebounds."
        )
        return _long_signal(
            symbol, regime_state, price, stop, alloc, 1.0, reason, self.name,
            {"atr": atr, "ema50": ema50},
        )
