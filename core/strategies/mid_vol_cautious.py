"""Mid-vol template: long size scales with price vs the 50-day EMA."""

from typing import Optional

import pandas as pd

from core.hmm.regime_state import RegimeState
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import Signal
from core.strategies.stops import _compute_stop_and_params, _cap_long_stop_below_entry, _long_signal


class MidVolCautiousStrategy(BaseStrategy):
    """Middle vol third: higher allocation above EMA50, lower below; stop at EMA50 − 0.5×ATR."""

    name = "MidVolCautiousStrategy"

    def generate_signal(self, symbol, bars, regime_state) -> Optional[Signal]:
        """Return a trend-conditioned long or ``None`` if inputs are degenerate."""
        price, atr, ema50 = _compute_stop_and_params(bars)
        if atr == 0 or price == 0:
            return None

        stop = _cap_long_stop_below_entry(price, ema50 - 0.5 * atr, atr)
        trend_intact = price > ema50
        alloc_key = "mid_vol_allocation_trend" if trend_intact else "mid_vol_allocation_no_trend"
        alloc = self.config.get(alloc_key, 0.95 if trend_intact else 0.60)
        suffix = (
            "Trend intact (price > 50EMA). Stay invested."
            if trend_intact
            else "Trend broken (price < 50EMA). Reduce allocation."
        )
        reason = f"Mid-vol regime ({regime_state.label}, p={regime_state.probability:.2f}). {suffix}"
        meta = {"atr": atr, "ema50": ema50, "trend_intact": trend_intact}
        return _long_signal(symbol, regime_state, price, stop, alloc, 1.0, reason, self.name, meta)
