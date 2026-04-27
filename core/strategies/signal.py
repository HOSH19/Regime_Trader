"""Immutable order intent emitted by strategies before risk checks."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Signal:
    """Symbol, direction, sizing, stops, and audit fields for one proposed trade."""

    symbol: str
    direction: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: Optional[float]
    position_size_pct: float
    leverage: float
    regime_id: int
    regime_name: str
    regime_probability: float
    timestamp: datetime
    reasoning: str
    strategy_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
