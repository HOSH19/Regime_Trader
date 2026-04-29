# HMM Algo Trader

Automated US-equity algorithmic trading system built on a Hidden Markov Model regime classifier. The system is fully systematic and long-only — every decision from signal to order size to stop placement is rules-based with no discretion.

---

## Signal Flow

```
OHLCV + Macro Data
        │
        ▼
  Feature Engineering  ←── rolling z-score normalization
        │
        ▼
  HMM Regime Detection ←── BIC model selection + Student-t emissions
        │
  Stability Filter     ←── debounce + flicker guard
        │
        ▼
  Regime State  (label · probability · confirmation)
        │
        ├──────────────────────────────┐
        ▼                              ▼
  Strategy Selection           Technical Signal Filter
  (vol-tier mapping)           (RSI · MACD · Bollinger)
        │                              │
        └──────────────┬───────────────┘
                       ▼
               Signal  (direction · target size)
                       │
                       ▼
              Kelly Criterion Sizer
              + Correlation Check
                       │
                       ▼
               Risk Manager
         (circuit breaker · exposure caps · guards)
                       │
                       ▼
              Order Executor  (Alpaca limit → market retry)
                       │
                       ▼
              ATR Trailing Stop  (live GTC order on Alpaca)
                       │
                       ▼
              SQLite State Store  (equity · regime · trade log)
```

---

## 1 — Feature Engineering

Every feature is computed from OHLCV data using only information available **at or before** each bar, then passed through a **252-day rolling z-score**. The z-score means the HMM sees comparable scales across all market environments and calendar periods — a spike in volatility in 2020 and a quiet 2017 look numerically comparable to the model.

**Price features**

| Feature | What it captures |
|---------|----------------|
| `ret_1`, `ret_5`, `ret_20` | Momentum across short, medium, and longer horizons |
| `realized_vol` | 20-day rolling std of log returns — the core regime signal |
| `vol_ratio` | Short (5d) vol / long (20d) vol — catches vol regime transitions before they're obvious |
| `roc_10`, `roc_20` | Rate of change — trend persistence |
| `dist_sma200` | Fractional distance from the 200-day SMA — bear/bull structural position |
| `sma50_slope` | Derivative of the 50-day SMA — trend direction at medium scale |
| `adx` | Average Directional Index — measures trend strength independent of direction |
| `rsi_zscore` | RSI(14) expressed as a z-score — momentum normalized to its own history |
| `norm_atr` | ATR(14) / close — volatility as a fraction of price, comparable across time |

**Volume features**

| Feature | What it captures |
|---------|----------------|
| `vol_norm` | Volume z-scored vs its 50-day history — unusual participation |
| `vol_trend` | First difference of 10-day volume SMA — whether participation is growing or shrinking |

**Macro features** (when `use_macro_features: true`)

| Feature | Source | What it captures |
|---------|--------|----------------|
| `macro_vix` | VIX index | Market-implied fear — the single best real-time regime signal |
| `macro_yield_spread` | 10Y minus 3-month Treasury | Yield curve steepness; inversion has preceded every US recession since 1955 |
| `macro_credit_proxy` | HYG minus LQD log-return diff | Credit stress, duration-neutral — detects risk-off before equities reprice |

Macro fetches are non-fatal — if the data source is unavailable the engine trains on price features only.

---

## 2 — HMM Regime Detection

The core of the system. A **Hidden Markov Model** treats market regimes as a latent (unobservable) variable and infers the current regime from the observable feature sequence.

**Why an HMM?**

Markets don't transition smoothly — they snap between distinct states (low-vol bull, high-vol bear, crash) that persist for weeks to months. An HMM explicitly models this persistence via a transition matrix where the diagonal (self-transition probability) is high. This is more appropriate than a threshold-based rule because the model learns the statistical properties of each regime from data rather than having them hard-coded.

**BIC model selection**

The number of hidden states isn't fixed. The engine fits HMMs with 3, 4, 5, 6, and 7 states and selects the one with the lowest **Bayesian Information Criterion (BIC)**. BIC penalizes model complexity, preventing overfitting to the training data.

> BIC = −2 · log-likelihood + k · ln(n)

where k is the number of free parameters and n is the number of observations. Each candidate is fit with multiple random restarts and the best log-likelihood per candidate is used.

**Student-t emissions**

Standard Gaussian HMMs underweight crash events — a −10% day sits in the extreme tail and barely influences regime assignment. Financial returns have **fat tails** (excess kurtosis), so the system uses a **Student-t emission model** by default.

The Student-t is derived via a Gaussian scale-mixture:

> Student-t(ν) = ∫ Gaussian(x | μ, Σ/τ) · Gamma(τ | ν/2, ν/2) dτ

Each observation gets a per-state auxiliary weight:

> E[τ_{t,k}] = (ν + d) / (ν + δ_{t,k})

where δ is the squared Mahalanobis distance of observation t from state k's mean. A crash observation has high δ, so τ is low — it gets **downweighted in the covariance M-step**. This means the model doesn't distort its understanding of normal regimes just because a few extreme observations occurred. With ν=4 (the default), tail thickness matches empirical equity return distributions.

**Forward algorithm — no look-ahead bias**

Live regime inference uses the **normalized forward algorithm** only. The forward algorithm computes the probability of the observed sequence up to time t for each state, then normalizes. Critically, it never looks at future bars. **Viterbi decoding is never used in live inference** — Viterbi is a smoothing algorithm that uses the full sequence to label each bar, which would constitute look-ahead bias on the streaming boundary.

Viterbi is used only at training time to assign human-readable labels to states.

**Regime labels**

After training, each state is assigned a human label by sorting states on their expected return (derived from Viterbi paths on training data). With 5 states the labels are BEAR → WEAK\_BEAR → NEUTRAL → WEAK\_BULL → BULL. With 3 states: BEAR → NEUTRAL → BULL. Volatility rank per state selects the strategy tier.

**Stability filter**

The raw HMM argmax flips bar-to-bar even within a confirmed regime as probabilities fluctuate. The stability filter requires a new state to persist for `stability_bars` consecutive bars before the confirmed regime changes. This prevents unnecessary rebalancing on transient probability shifts.

**Flicker guard**

Even with the stability filter, a choppy market can produce rapid regime switches. Confirmed switches within the last `flicker_window` bars are counted. If the count exceeds `flicker_threshold`, all position sizes are halved via `uncertainty_size_mult`. The system is still trading — just with appropriate humility about regime certainty.

---

## 3 — Strategy Selection

Each HMM state maps to one of three strategy tiers by volatility rank (calmest state → LowVolBull, most volatile → HighVolDefensive). Volatility rank is computed at training time from mean ATR-normalized volatility within each state.

| Tier | Regime character | Target allocation | Leverage |
|------|-----------------|-------------------|----------|
| LowVolBull | Low vol, positive drift | 95% of equity | 1.25× |
| MidVolCautious | Mid vol, trend-dependent | 60–95% of equity | 1.0× |
| HighVolDefensive | High vol, negative drift | 60% of equity | 1.0× |

A **rebalance deadband** suppresses signals when the current allocation is already within `rebalance_threshold` (10%) of the target. This avoids trading costs from minor drift.

When regime probability is below `min_confidence` (0.55) or flicker is detected, position sizes are halved regardless of tier.

---

## 4 — Technical Signal Filter

The HMM answers *what environment are we in* — it does not answer *is this a good entry right now*. The technical filter adds a second confirmation gate that checks momentum or mean-reversion conditions per-symbol.

The regime tier determines which signal type is appropriate:

**Momentum confirmation** (low-vol / bull regimes)

- RSI(14) in [50, 75] — above 50 means recent gains outpace losses; above 75 risks being overbought
- MACD histogram positive and increasing — the fast EMA is accelerating away from the slow EMA

Both conditions give full size. Either condition alone gives 60% size. Neither blocks the signal.

**Mean-reversion confirmation** (mid-vol / neutral regimes)

- Price at or below the lower Bollinger Band (20-period, 2σ) — statistically extended on the downside
- Price below the midline (20-day SMA) — moderate extension

The Bollinger Band is a volatility envelope: when price reaches the lower band, it has moved more than 2 standard deviations from its recent mean. Mean-reversion assumes this is a temporary dislocation.

**High-vol / defensive regimes** — no technical gate; the strategy is already defensive and the priority is capital preservation over entry timing.

Confirmation returns a `strength` scalar in [0, 1] that directly scales `position_size_pct`. A failed confirmation drops the signal entirely.

---

## 5 — Kelly Criterion Sizing

Before applying any hard risk caps, the system computes a **Kelly-optimal position fraction** for each signal.

The Kelly Criterion maximizes long-run geometric growth rate:

> f* = (p · b − q) / b

where p is win rate, q = 1 − p, and b is the payoff ratio (avg win / avg loss). Full Kelly is aggressive and sensitive to estimation error, so the system uses **half-Kelly** (f = 0.5 · f*). With conservative default priors (win rate 0.52, payoff ratio 1.5), the starting Kelly fraction is modest until historical trade data accumulates.

**Correlation-aware sizing**

Adding a correlated position to an existing book doesn't reduce portfolio risk proportionally. The sizer computes the 20-day return correlation between the incoming symbol and every existing position:

- Correlation ≥ 0.70 — position size is multiplied by (1 − correlation), reducing concentration
- Correlation ≥ 0.85 — signal is rejected entirely; the position would be nearly redundant with an existing holding

The Kelly fraction is then further capped by the hard `max_single_position` (15%) limit.

---

## 6 — Risk Manager

A validation pipeline that every signal passes through before reaching the broker. Each check is independent — failing any one rejects or modifies the signal.

| Check | What it enforces |
|-------|-----------------|
| Circuit breaker state | Hard stop if daily/weekly/peak drawdown gates are breached |
| Circuit breaker reduction | Halve size on soft drawdown thresholds |
| Stop-loss present | Reject any signal missing a positive stop-loss |
| Daily trade cap | Reject when `max_daily_trades` is reached for the session |
| Duplicate symbol | Reject the same symbol traded within `duplicate_block_seconds` |
| Max concurrent positions | Reject when already holding `max_concurrent` names |
| Per-trade risk budget | Size down using risk-per-share and gap-risk multiplier |
| Gross exposure | Reject if adding this position would exceed `max_exposure` of equity |
| Leverage cap | Force leverage to 1.0× if circuit breaker is active or 3+ positions are held |

**Per-trade risk budget**

Position size is derived from the stop distance:

> shares = (equity × max_risk_per_trade) / (entry − stop_loss)

A `gap_risk_multiplier` (3×) is applied to the stop distance for overnight positions — the assumption is that a gap-through could move 3× the stop distance before the position can be closed. This prevents overfitting position size to a tight stop that won't protect against gap risk.

**Circuit breaker**

Five drawdown gates run in priority order. Once a hard halt is triggered, a lock file is written to disk — trading cannot resume until the file is manually deleted. This prevents the system from re-entering after a catastrophic drawdown during a process restart.

| Gate | Threshold | Action |
|------|-----------|--------|
| Daily drawdown | −2% | Reduce all sizes 50% |
| Daily drawdown | −3% | Close all positions, halt for the day |
| Weekly drawdown | −5% | Reduce all sizes 50% |
| Weekly drawdown | −7% | Close all positions, halt for the week |
| Drawdown from peak | −10% | Close all, write lock file, require manual restart |

---

## 7 — Order Execution

Orders are submitted as **limit orders** with a small offset above the ask (0.1%) to maximize fill probability while avoiding crossing the spread at market. If a limit order is unfilled after 30 seconds, it is cancelled and re-submitted as a market order.

All orders use a `client_order_id` in the format `{symbol}-{uuid8}` for idempotency — if the process crashes between submission and confirmation, the same trade ID prevents double-fills on restart.

The executor also supports **bracket orders** — a market entry with child stop-loss and optional take-profit attached. These are used when the stop must be placed atomically with the entry.

---

## 8 — ATR Trailing Stops

Every open position has a hard stop placed as a **GTC (Good Till Cancelled) StopOrder directly on Alpaca**. Placing the stop at the broker level means it survives process crashes, network outages, and restarts — the position is protected even when the trading process is not running.

The stop price is set using **Average True Range (ATR)**:

> stop = current_price − (ATR_multiplier × ATR_14)

ATR measures the typical daily range including gaps, so the stop is wide enough to avoid being triggered by normal volatility while still protecting against meaningful adverse moves.

The multiplier varies by regime:

| Regime tier | ATR multiplier | Rationale |
|------------|---------------|-----------|
| Low-vol / bull | 1.5× | Tighter stop — market is calm, adverse move is more signal |
| Mid-vol / neutral | 2.0× | Standard room for noise |
| High-vol / defensive | 3.0× | Wider stop — normal swings are large; a tight stop would whipsaw |

On each bar, if the new ATR stop is **higher** than the current stop, the GTC order is replaced (trailing tighter). The stop **never widens** — this property preserves accumulated gains in a trending position.

---

## 9 — State Persistence

All runtime state is stored in a **SQLite database** (`state.db`, WAL mode for concurrent read safety):

| Table | Contents |
|-------|---------|
| `snapshot` | Latest equity, cash, regime, circuit-breaker status — read on restart to restore position context |
| `equity_curve` | Timestamped equity + cash — full P&L history |
| `regime_history` | Label, probability, confirmation flag per bar — regime attribution analysis |
| `trade_log` | Every submitted order with symbol, side, qty, fill price, regime active at time of trade, strategy tier |

The trade log enables **post-trade regime attribution** — which regime was the system in when each trade was placed, and what was the subsequent P&L. This is the foundation for computing realized win rates and payoff ratios to eventually replace the Kelly prior defaults.

---

## Backtesting

The walk-forward backtester avoids look-ahead bias by strictly separating in-sample and out-of-sample windows:

1. Train HMM on the in-sample window (default 252 bars / 1 year)
2. Simulate the out-of-sample window bar-by-bar (default 126 bars / 6 months), calling `predict_regime_filtered` with only the history up to that bar
3. Step forward by `step_size` bars and repeat

This means no future data ever influences a trade decision — the model trained on years 1–2 is used to trade year 3, then retrained on years 2–3 to trade year 4, and so on.

**Slippage and fill delay** are modelled explicitly: signals on bar N fill at the next bar's open (fill\_delay = 1 bar), with a 0.05% slippage applied to the fill price.

**Stress tests** run three additional scenarios on top of the base backtest:
- **Crash injection** — random 20–40% price drops inserted at random dates
- **Gap risk** — overnight gaps of 5–15% applied to open positions
- **Regime misclassification** — random regime label flips to test how sensitive returns are to HMM accuracy

---

## Configuration

```yaml
hmm:
  emission_type: student_t   # gaussian | student_t
  student_t_dof: 4           # lower = heavier tails
  use_macro_features: true
  n_candidates: [3, 4, 5, 6, 7]
  stability_bars: 3
  flicker_threshold: 4
  min_confidence: 0.55

technical:
  rsi_bull_min: 50
  rsi_bull_max: 75
  bb_period: 20
  bb_std: 2.0

risk:
  max_risk_per_trade: 0.01       # 1% of equity per trade
  max_single_position: 0.15      # 15% max in one name
  correlation_reduce_threshold: 0.70
  correlation_reject_threshold: 0.85
  daily_dd_halt: 0.03
  weekly_dd_halt: 0.07
  max_dd_from_peak: 0.10
  gap_risk_multiplier: 3.0
```

---

## Running

```bash
# Paper trading (default)
python run_daily.py

# Live trading loop (streaming bars)
python main.py

# Dry run — full pipeline, no orders placed
python main.py --dry-run

# Walk-forward backtest
python main.py --backtest --symbols SPY --start 2019-01-01 --end 2024-12-31

# Backtest with stress tests
python main.py --backtest --stress-test --symbols SPY

# Retrain HMM only
python main.py --train-only

# Run tests
python -m pytest tests/ -v
```
