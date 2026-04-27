"""Structured outcome of :meth:`core.risk.risk_manager.RiskManager.validate_signal`."""

from dataclasses import dataclass, field
from typing import List, Optional

from core.strategies.signal import Signal


@dataclass
class RiskDecision:
    """Approval flag, optional resized signal, rejection text, and sizing notes."""

    approved: bool
    modified_signal: Optional[Signal]
    rejection_reason: str
    modifications: List[str] = field(default_factory=list)
