"""Dataclass for one allocation rebalance in the walk-forward simulator."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class Trade:
    """Fill metadata when target weight crosses the rebalance deadband."""

    bar_index: int
    timestamp: pd.Timestamp
    symbol: str
    prev_allocation: float
    new_allocation: float
    price: float
    regime: str
    regime_prob: float
    slippage_cost: float
