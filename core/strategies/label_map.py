"""Backward-compat class aliases and return-label → template registry."""

from typing import Dict

from core.strategies.high_vol_defensive import HighVolDefensiveStrategy
from core.strategies.low_vol_bull import LowVolBullStrategy
from core.strategies.mid_vol_cautious import MidVolCautiousStrategy

CrashDefensiveStrategy = HighVolDefensiveStrategy
BearTrendStrategy = HighVolDefensiveStrategy
MeanReversionStrategy = MidVolCautiousStrategy
BullTrendStrategy = LowVolBullStrategy
EuphoriaCautiousStrategy = LowVolBullStrategy

LABEL_TO_STRATEGY: Dict[str, type] = {
    "CRASH": HighVolDefensiveStrategy,
    "STRONG_BEAR": HighVolDefensiveStrategy,
    "WEAK_BEAR": MidVolCautiousStrategy,
    "BEAR": MidVolCautiousStrategy,
    "NEUTRAL": MidVolCautiousStrategy,
    "WEAK_BULL": LowVolBullStrategy,
    "BULL": LowVolBullStrategy,
    "STRONG_BULL": LowVolBullStrategy,
    "EUPHORIA": LowVolBullStrategy,
}
