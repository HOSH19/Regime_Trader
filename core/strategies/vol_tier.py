"""Select ``LowVol`` / ``MidVol`` / ``HighVol`` strategy class from a vol rank in ``[0, 1]``."""

from core.strategies.high_vol_defensive import HighVolDefensiveStrategy
from core.strategies.low_vol_bull import LowVolBullStrategy
from core.strategies.mid_vol_cautious import MidVolCautiousStrategy


def _strategy_class_for_vol_rank_fraction(position: float) -> type:
    """Tercile mapping: bottom → low vol, middle → mid, top → defensive."""
    if position <= 0.33:
        return LowVolBullStrategy
    if position >= 0.67:
        return HighVolDefensiveStrategy
    return MidVolCautiousStrategy
