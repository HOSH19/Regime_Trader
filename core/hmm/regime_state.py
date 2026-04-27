"""Live filtered regime state exposed to strategies and risk."""

from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass
class RegimeState:
    """Argmax regime, probabilities, and stability-filter confirmation flags."""

    label: str
    state_id: int
    probability: float
    state_probabilities: np.ndarray
    timestamp: datetime
    is_confirmed: bool
    consecutive_bars: int
