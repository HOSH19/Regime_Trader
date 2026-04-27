"""Cash, share count, and target weight carried across OOS bars."""

from dataclasses import dataclass


@dataclass
class WalkSimState:
    """Minimal book state for the allocation-based simulator."""

    cash: float
    shares: float
    current_allocation: float
