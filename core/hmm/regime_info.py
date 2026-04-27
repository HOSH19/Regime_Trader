"""Per-regime training summary used to cap strategy templates."""

from dataclasses import dataclass


@dataclass
class RegimeInfo:
    """Labels and risk knobs for one mixture component after training."""

    regime_id: int
    regime_name: str
    expected_return: float
    expected_volatility: float
    recommended_strategy_type: str
    max_leverage_allowed: float
    max_position_size_pct: float
    min_confidence_to_act: float
