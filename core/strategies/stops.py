"""Internal helpers for ATR-based stops and building long ``Signal`` rows."""

from typing import Any, Dict

import pandas as pd

from core.hmm.regime_state import RegimeState
from core.strategies.signal import Signal
from core.timeutil import utc_now
from data.feature_engineering import compute_atr


def _ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average with ``adjust=False``."""
    return series.ewm(span=span, adjust=False).mean()


def _compute_stop_and_params(bars: pd.DataFrame) -> tuple:
    """Last-bar close, ATR(14), and EMA(50) from OHLCV ``bars``."""
    close = bars["close"] if "close" in bars.columns else bars["Close"]
    high = bars["high"] if "high" in bars.columns else bars["High"]
    low = bars["low"] if "low" in bars.columns else bars["Low"]

    atr_series = compute_atr(high, low, close, 14)
    ema50 = _ema(close, 50)

    current_price = float(close.iloc[-1])
    atr = float(atr_series.iloc[-1])
    ema50_val = float(ema50.iloc[-1])

    return current_price, atr, ema50_val


def _cap_long_stop_below_entry(entry: float, stop: float, atr: float) -> float:
    """Force a long protective stop strictly below ``entry`` using a small ATR cushion."""
    cushion = max(0.01 * atr, entry * 1e-6, 1e-4)
    return min(stop, entry - cushion)


def _long_signal(
    symbol: str,
    regime_state: RegimeState,
    price: float,
    stop: float,
    alloc: float,
    leverage: float,
    reasoning: str,
    strategy_name: str,
    metadata: Dict[str, Any],
) -> Signal:
    """Build a long ``Signal`` with regime fields copied from ``regime_state``."""
    return Signal(
        symbol=symbol,
        direction="LONG",
        confidence=regime_state.probability,
        entry_price=price,
        stop_loss=stop,
        take_profit=None,
        position_size_pct=alloc,
        leverage=leverage,
        regime_id=regime_state.state_id,
        regime_name=regime_state.label,
        regime_probability=regime_state.probability,
        timestamp=utc_now(),
        reasoning=reasoning,
        strategy_name=strategy_name,
        metadata=metadata,
    )
