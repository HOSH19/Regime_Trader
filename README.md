# Regime Trader

Automated US-equity regime detection and **allocation** control: a Gaussian HMM summarizes the market into volatility-ordered states; a strategy layer maps those states to target long exposure; a separate risk layer can veto or resize any order. The engineered pieces are the feature pipeline, the bias-aware HMM interface, the walk-forward backtester, and the drawdown-first risk rules—not directional alpha.

**Design principle:** risk management and exposure discipline matter more than signal quality. The HMM is treated as a **volatility / environment classifier**, not a return forecaster. The stack is **long-only** so late regime exits do not fight sharp recoveries with short exposure.

---

## Feature engineering

All observables are built in `data/feature_engineering.py` from **OHLCV only**, using information available **at or before** each bar. Every column is passed through a **252-trading-day rolling z-score** (mean and standard deviation of the raw feature over that window) so the HMM sees comparable scales across regimes and calendar periods.

| Feature | Construction |
|--------|----------------|
| `ret_1`, `ret_5`, `ret_20` | Log returns over 1, 5, and 20 days, z-scored |
| `realized_vol` | 20-day rolling std of daily log returns, z-scored |
| `vol_ratio` | Short (5d) vs long (20d) realized vol ratio, z-scored |
| `vol_norm` | Volume z-score vs 50-day rolling mean/std |
| `vol_trend` | First difference of 10-day volume SMA, z-scored |
| `adx` | 14-period ADX (trend strength), z-scored |
| `sma50_slope` | One-day change in 50-day SMA of close, z-scored |
| `rsi_zscore` | RSI(14) expressed as rolling z-score vs its 252-day history |
| `dist_sma200` | Fractional distance of close from its 200-day SMA, z-scored |
| `roc_10`, `roc_20` | Rate of change over 10 and 20 days, z-scored |
| `norm_atr` | ATR(14) / close (volatility scale vs price), z-scored |

Rows with any missing feature (warm-up) are dropped before training or inference. The matrix fed to the HMM is **strictly causal**: no future bars, no Viterbi-smoothed states as inputs.

---

## Regime detection (HMM)

Implemented in `core/hmm_engine.py`:

- **Model:** `hmmlearn` Gaussian HMM, full covariance, multiple random inits (`n_init`), BIC-driven choice of **3–7** hidden states (`n_candidates`).
- **Live / sequential inference:** filtered state probabilities use a **manual forward algorithm** only. **Viterbi / `predict()` is not used** for real-time regime probabilities, avoiding smoothed (look-ahead) state paths on the streaming boundary.
- **Training-time labeling:** Viterbi is used **offline** on the training window only to assign each mixture component a **return-ranked** human label (e.g. bear → bull ordering). Within that, **volatility rank** per state selects one of three **strategy templates** (calm / mid / defensive) with different caps on leverage and max position size.
- **Stability filter:** a raw argmax state must persist for `stability_bars` before the **confirmed** regime flips; unconfirmed bars still expose probabilities and labels for risk/UI.
- **Flicker:** recent confirmed transitions are counted over `flicker_window`; above `flicker_threshold`, downstream logic can treat the model as unstable (e.g. uncertainty sizing).
- **Persistence:** model + metadata are serialized; **retraining is triggered by calendar age** (`stale_max_days`), not by whether the cash session is open.

---

## Strategy layer

Implemented in `core/regime_strategies.py` and driven by `config/settings.yaml` under `strategy`:

- **Regime → handler:** each HMM state maps to a **low / mid / high volatility** strategy class according to that state’s volatility rank among all states.
- **Allocation:** target long fraction of equity (and optional leverage on the calm tier) from configured floors/ceilings; **mid-vol** tier can distinguish trend vs range using price vs SMA200.
- **Rebalance deadband:** orders are suppressed unless target allocation differs from current allocation by at least `rebalance_threshold` (fraction of equity).
- **Uncertainty:** low confidence or flicker scales size by `uncertainty_size_mult`.
- **Signals:** the orchestrator emits **long** targets per symbol; there is no short book by design.

`core/signal_generator.py` wires HMM state + orchestrator into a single pipeline used by live code and backtests.

---

## Risk layer

Implemented in `core/risk_manager.py` and applied before any order reaches the broker:

- **Circuit breaker:** hierarchical actions from intraday / weekly drawdown soft thresholds through **hard halt** from peak drawdown; extreme peak breach can write a **lock file** requiring manual removal.
- **Per-trade sizing:** risk budget per trade, **gap-risk multiplier** on stop distance for overnight-aware share counts, min notional, max single name, max gross exposure, max concurrent positions, leverage caps tightened when multiple positions or breaker soft states apply.
- **Operational guards:** duplicate trade time window, mandatory stop on signal, spread-related rejects (where used), correlation caps (config present for portfolio-level constraints).

Risk checks are **independent of HMM correctness**: even with wrong regimes, drawdown rules still apply to realized equity.

---

## Backtesting and evaluation

- **`backtest/backtester.py`:** **walk-forward** runs: train HMM on an in-sample window (default 252 sessions), simulate out-of-sample (default 126), step the window forward. The simulator is **allocation-based** (target weights, rebalance when the deadband is crossed), not a full fill simulator for every tick.
- **Execution model:** signal at bar *t*, optional **fill delay** at bar *t+1* open plus **slippage**; equity path and a rebalance **trade log** are recorded together with **regime history**.
- **`backtest/performance.py`:** returns, drawdown, Sharpe/Sortino/Calmar, trade statistics, buy-and-hold / SMA(200) / random-allocation benchmarks, Rich report output.
- **`backtest/stress_test.py`:** Monte Carlo **crash gaps** (multiplicative shocks), **ATR-scaled overnight gaps**, and **shuffled close paths** to stress drawdowns and dependence on regime ordering.

---

## Automation and monitoring

- **`run_daily.py`:** single entry for scheduled runs: loads config, fetches bars, **loads or retrains HMM if stale**, computes regime, pulls account state, optionally fetches **NewsAPI** headlines, then either **full trading path** (signals, risk, Alpaca orders) or **closed-market Telegram summary** without placing orders.
- **`monitoring/telegram_notifier.py`:** HTML messages for **daily briefing** (open session) vs **market summary** (weekend / post-close copy paths), plus alert helper for failures and breaker events.
- **`monitoring/`:** structured rotating logs, optional webhooks/email hooks for alerts, terminal dashboard for local monitoring.
- **CI:** GitHub Actions can run the daily script on a fixed UTC schedule; model and snapshot state can be cached between runs.

Configuration for all of the above lives in **`config/settings.yaml`** (broker, HMM, strategy, risk, backtest, monitoring).
