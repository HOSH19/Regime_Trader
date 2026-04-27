# Regime Trader

Automated US-equity regime detection and allocation control. A Hidden Markov Model classifies the market into volatility-ordered states; a strategy layer maps those states to target long exposure.

The HMM is treated as a **volatility / environment classifier**, not a return forecaster. The stack is **long-only**.

---

## Feature engineering

All features are built in `data/feature_engineering.py` from OHLCV data using information available **at or before** each bar. Every column is passed through a **252-day rolling z-score** so the HMM sees comparable scales across regimes and calendar periods.

| Feature | Construction |
|--------|----------------|
| `ret_1`, `ret_5`, `ret_20` | Log returns over 1, 5, and 20 days |
| `realized_vol` | 20-day rolling std of daily log returns |
| `vol_ratio` | Short (5d) vs long (20d) realized vol ratio |
| `vol_norm` | Volume z-score vs 50-day rolling mean/std |
| `vol_trend` | First difference of 10-day volume SMA |
| `adx` | 14-period ADX (trend strength) |
| `sma50_slope` | One-day change in 50-day SMA of close |
| `rsi_zscore` | RSI(14) expressed as a rolling z-score |
| `dist_sma200` | Fractional distance of close from 200-day SMA |
| `roc_10`, `roc_20` | Rate of change over 10 and 20 days |
| `norm_atr` | ATR(14) / close |

### Macro features

When `use_macro_features: true`, three macro conditioning features are appended (fetched via `yfinance`, z-scored the same way):

| Feature | Source | What it captures |
|--------|--------|-----------------|
| `macro_vix` | `^VIX` | Market fear / implied vol level |
| `macro_yield_spread` | `^TNX − ^IRX` | Yield curve steepness; inversion precedes recessions |
| `macro_credit_proxy` | `HYG − LQD` log-return diff | Credit stress, duration-neutral |

Macro fetches are non-fatal — if `yfinance` is unavailable the engine falls back to price-only features.

---

## Regime detection (HMM)

Implemented in `core/hmm/`:

- **Emission model:** Gaussian or Student-t, selected via `emission_type` in config.
- **Model selection:** BIC over 3–7 hidden states with multiple random restarts.
- **Live inference:** forward algorithm only — Viterbi is never used for real-time probabilities to avoid look-ahead bias on the streaming boundary.
- **Training-time labeling:** Viterbi is used offline on the training window to assign each state a return-ranked human label (bear → bull). Volatility rank per state selects one of three strategy templates with different leverage and position caps.
- **Stability filter:** a new state must persist for `stability_bars` bars before the confirmed regime flips.
- **Flicker:** confirmed switches above `flicker_threshold` within `flicker_window` trigger uncertainty sizing.
- **Persistence:** model is retrained when older than `stale_max_days` and committed back to the repo via GitHub Actions.

### Student-t emissions

Financial returns have fat tails — crash days are far more common than a Gaussian model expects. The Student-t HMM (`core/hmm/student_t_model.py`) addresses this via the **Gaussian scale-mixture** representation:

> Student-t(ν) = ∫ Gaussian(x | μ, Σ/τ) · Gamma(τ | ν/2, ν/2) dτ

The EM algorithm adds a per-observation auxiliary weight:

> E[τ_{t,k}] = (ν + d) / (ν + δ_{t,k})

where δ is the Mahalanobis distance from state k. Outlier observations receive lower τ, reducing their pull on the covariance update. With ν=4 (the default), the tails match empirical equity return distributions without needing to estimate ν.

The base model interface (`core/hmm/base_model.py`) keeps emission type swappable without touching the engine.

---

## Strategy layer

Implemented in `core/strategies/`:

- Each HMM state maps to a **low / mid / high volatility** strategy class by volatility rank.
- Target long fraction of equity with optional leverage on the calm tier.
- Orders are suppressed inside a `rebalance_threshold` deadband.
- Low confidence or flicker halves position size via `uncertainty_size_mult`.

---

## Risk layer

Implemented in `core/risk/` and applied before any order reaches the broker:

- **Circuit breaker:** intraday / weekly drawdown soft thresholds through hard halt from peak drawdown; extreme breach writes a lock file requiring manual removal.
- **Per-trade sizing:** risk budget, gap-risk multiplier on stop distance, max single name, max gross exposure, max concurrent positions.
- **Operational guards:** duplicate trade window, mandatory stop on signal, correlation caps.

Risk checks are **independent of HMM correctness** — drawdown rules apply to realized equity regardless of regime accuracy.

---

## Configuration

All tunable parameters live in `config/settings.yaml`:

```yaml
hmm:
  emission_type: student_t   # gaussian | student_t
  student_t_dof: 4
  use_macro_features: true
  n_candidates: [3, 4, 5, 6, 7]
  stale_max_days: 3
```
