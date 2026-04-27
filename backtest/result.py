"""Container for equity path, fills, regime log, and window metadata."""

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from backtest.trade import Trade


@dataclass
class BacktestResult:
    """Everything :meth:`WalkForwardBacktester.run` returns for reporting."""

    equity_curve: pd.Series
    trade_log: List[Trade]
    regime_history: pd.DataFrame
    windows: List[Dict]
    config: Dict
