"""Tests for :class:`~core.hmm.engine.HMMEngine`: BIC fit, labels, forward pass, I/O."""

import os
import sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.timeutil import utc_now


def _make_synthetic_bars(n: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Synthetic OHLCV with alternating vol regimes for stable training.

    Args:
        n: Number of business days.
        seed: RNG seed.

    Returns:
        Indexed OHLCV frame.
    """
    rng = np.random.default_rng(seed)
    prices = [100.0]
    for i in range(n - 1):
        regime = "bull" if (i % 200) < 130 else "bear"
        vol = 0.008 if regime == "bull" else 0.018
        drift = 0.0003 if regime == "bull" else -0.0002
        prices.append(prices[-1] * np.exp(rng.normal(drift, vol)))

    prices = np.array(prices)
    high = prices * (1 + rng.uniform(0, 0.005, n))
    low = prices * (1 - rng.uniform(0, 0.005, n))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)

    idx = pd.bdate_range("2018-01-01", periods=n)
    return pd.DataFrame({
        "open": prices * (1 + rng.normal(0, 0.001, n)),
        "high": high,
        "low": low,
        "close": prices,
        "volume": volume,
    }, index=idx)


def _load_config():
    """Load ``config/settings.yaml``.

    Returns:
        Parsed settings dict.
    """
    import yaml
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")
    with open(cfg_path) as f:
        return yaml.safe_load(f)


class TestHMMEngine:
    """Training, inference, probability mass, pickle round-trip, and staleness."""

    def test_train_selects_best_n(self):
        """``n_regimes`` stays inside candidate list; BIC is finite."""
        from core.hmm import HMMEngine
        config = _load_config()
        hmm = HMMEngine(config.get("hmm", {}))
        bars = _make_synthetic_bars()
        hmm.train(bars)
        assert hmm.n_regimes in [3, 4, 5, 6, 7]
        assert hmm.bic_score < float("inf")

    def test_regime_labels_assigned(self):
        """Every component gets a non-empty label string."""
        from core.hmm import HMMEngine
        config = _load_config()
        hmm = HMMEngine(config.get("hmm", {}))
        bars = _make_synthetic_bars()
        hmm.train(bars)
        assert len(hmm.labels) == hmm.n_regimes
        for label in hmm.labels:
            assert isinstance(label, str) and len(label) > 0

    def test_regime_infos_built(self):
        """``RegimeInfo`` rows have leverage and cap in allowed sets."""
        from core.hmm import HMMEngine
        config = _load_config()
        hmm = HMMEngine(config.get("hmm", {}))
        bars = _make_synthetic_bars()
        hmm.train(bars)
        assert len(hmm.regime_infos) == hmm.n_regimes
        for info in hmm.regime_infos:
            assert info.max_leverage_allowed in [1.0, 1.25]
            assert 0 < info.max_position_size_pct <= 1.0

    def test_predict_returns_regime_state(self):
        """Filtered prediction returns in-range probability and known label."""
        from core.hmm import HMMEngine
        config = _load_config()
        hmm = HMMEngine(config.get("hmm", {}))
        bars = _make_synthetic_bars()
        hmm.train(bars)
        state = hmm.predict_regime_filtered(bars)
        assert state is not None
        assert 0.0 <= state.probability <= 1.0
        assert state.label in hmm.labels

    def test_forward_probs_sum_to_one(self):
        """Last-step ``predict_regime_proba`` sums to 1."""
        from core.hmm import HMMEngine
        config = _load_config()
        hmm = HMMEngine(config.get("hmm", {}))
        bars = _make_synthetic_bars()
        hmm.train(bars)
        proba = hmm.predict_regime_proba(bars)
        assert abs(proba.sum() - 1.0) < 1e-6

    def test_save_and_load(self, tmp_path):
        """Pickle preserves ``n_regimes`` and label list."""
        from core.hmm import HMMEngine
        config = _load_config()
        hmm = HMMEngine(config.get("hmm", {}))
        bars = _make_synthetic_bars()
        hmm.train(bars)
        path = str(tmp_path / "model.pkl")
        hmm.save(path)

        hmm2 = HMMEngine(config.get("hmm", {}))
        hmm2.load(path)
        assert hmm2.n_regimes == hmm.n_regimes
        assert hmm2.labels == hmm.labels

    def test_stale_detection(self):
        """``is_stale`` flips when ``training_date`` is older than ``max_days``."""
        from core.hmm import HMMEngine
        from datetime import datetime, timedelta
        config = _load_config()
        hmm = HMMEngine(config.get("hmm", {}))
        hmm.training_date = utc_now()
        assert not hmm.is_stale(max_days=3)
        hmm.training_date = utc_now() - timedelta(days=10)
        assert hmm.is_stale(max_days=3)
