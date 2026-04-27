"""Glue ``HMMEngine`` filtered states to ``StrategyOrchestrator`` outputs."""

import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from core.hmm import HMMEngine, RegimeState
from core.strategies import Signal, StrategyOrchestrator

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Run regime inference on the primary symbol, then fan out per-symbol targets."""

    def __init__(self, hmm_engine: HMMEngine, orchestrator: StrategyOrchestrator, config: dict) -> None:
        """Wire trained HMM, orchestrator, and full settings.

        Args:
            hmm_engine: Trained :class:`~core.hmm.engine.HMMEngine`.
            orchestrator: Mapping from ``regime_id`` to tier strategies.
            config: Full app config (uses ``hmm`` and nested keys).
        """
        self.hmm = hmm_engine
        self.orchestrator = orchestrator
        self.cfg = config

    def generate(
        self,
        symbols: List[str],
        bars_by_symbol: Dict[str, pd.DataFrame],
        current_allocations: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[Signal], Optional[RegimeState]]:
        """Run ``predict_regime_filtered`` on ``symbols[0]`` and build orchestrator signals.

        Returns:
            ``(signals, regime_state)`` or ``([], None)`` on insufficient data or HMM errors.
        """
        primary = symbols[0]
        primary_bars = bars_by_symbol.get(primary)

        if primary_bars is None or len(primary_bars) < self.cfg.get("hmm", {}).get("min_train_bars", 504):
            logger.warning("Insufficient bars for regime detection")
            return [], None

        try:
            regime_state = self.hmm.predict_regime_filtered(primary_bars)
        except Exception as e:
            logger.error(f"HMM prediction failed: {e}. Holding current regime.")
            return [], None

        is_flickering = self.hmm.is_flickering()

        signals = self.orchestrator.generate_signals(
            symbols=symbols,
            bars_by_symbol=bars_by_symbol,
            regime_state=regime_state,
            is_flickering=is_flickering,
            current_allocations=current_allocations,
        )

        return signals, regime_state
