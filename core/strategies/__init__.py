"""Volatility-ranked long-only allocation templates and orchestration.

Templates are chosen by each state's volatility rank among HMM components, not by return label.
The book is always long; high vol reduces size rather than flipping direction.
"""

from core.strategies.base_strategy import BaseStrategy
from core.strategies.high_vol_defensive import HighVolDefensiveStrategy
from core.strategies.label_map import (
    LABEL_TO_STRATEGY,
    BearTrendStrategy,
    BullTrendStrategy,
    CrashDefensiveStrategy,
    EuphoriaCautiousStrategy,
    MeanReversionStrategy,
)
from core.strategies.low_vol_bull import LowVolBullStrategy
from core.strategies.mid_vol_cautious import MidVolCautiousStrategy
from core.strategies.orchestrator import StrategyOrchestrator
from core.strategies.signal import Signal

__all__ = [
    "BaseStrategy",
    "BearTrendStrategy",
    "BullTrendStrategy",
    "CrashDefensiveStrategy",
    "EuphoriaCautiousStrategy",
    "HighVolDefensiveStrategy",
    "LABEL_TO_STRATEGY",
    "LowVolBullStrategy",
    "MeanReversionStrategy",
    "MidVolCautiousStrategy",
    "Signal",
    "StrategyOrchestrator",
]
