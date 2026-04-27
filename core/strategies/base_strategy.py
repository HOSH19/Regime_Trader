"""Protocol for volatility-tier strategies that map bars + regime to a ``Signal``."""

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from core.hmm.regime_state import RegimeState
from core.strategies.signal import Signal


class BaseStrategy(ABC):
    """Subclass to implement ``generate_signal`` for one vol tier."""

    name: str = "BaseStrategy"

    def __init__(self, config: dict) -> None:
        """Store the ``strategy`` section of settings.

        Args:
            config: Strategy thresholds (allocations, leverage, etc.).
        """
        self.config = config

    @abstractmethod
    def generate_signal(
        self,
        symbol: str,
        bars: pd.DataFrame,
        regime_state: RegimeState,
    ) -> Optional[Signal]:
        """Return a long signal or ``None`` if inputs are invalid."""
        pass
