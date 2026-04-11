# TraderBot 🤖

A fully automated, HMM-based regime trading bot that trades US equities via Alpaca's paper/live API. Runs as a daily cron job and delivers a Telegram briefing every evening including regime analysis, portfolio state, orders placed, and top news headlines per ticker.

**Philosophy: risk management > signal generation.**

The edge is not in predicting market direction — it's in being fully invested during calm markets and reducing exposure during turbulent ones. When you cut your worst drawdowns in half, compounding works in your favour over time.

---

## How It Works

```
Every weekday at 4:05 PM ET (cron)
        │
        ▼
data/market_data.py         Fetch daily OHLCV bars from Alpaca (IEX feed)
        │
        ▼
data/feature_engineering.py Compute 14 OHLCV features, rolling z-score normalised
        │
        ▼
core/hmm_engine.py          Gaussian HMM — BIC model selection, forward algorithm
        │                   (no look-ahead bias), regime labelling
        ▼
core/regime_strategies.py   Volatility-rank → allocation size (always LONG)
        │
        ▼
core/risk_manager.py        Circuit breakers — absolute veto power over all orders
        │
        ▼
broker/                     Alpaca client, LIMIT/bracket orders, position tracker
        │
        ▼
monitoring/                 Structured JSON logs, Telegram daily briefing + news
```

**The HMM is a volatility classifier, not a price predictor.** It detects calm vs turbulent market environments. The strategy layer uses this to set portfolio allocation — fully invested in calm markets, reduced in turbulent ones.

**Always LONG, never SHORT.** V-shaped recoveries happen fast and the HMM is 2–3 days late detecting them. Shorting during rebounds wipes out crash gains.

---

## Features

- **Hidden Markov Model** — Gaussian HMM with BIC model selection (tests 3–7 regimes), manual forward algorithm to eliminate look-ahead bias, regime stability filter and flicker detection
- **14 engineered features** — log returns (1/5/20 day), realised volatility, vol ratio, volume z-score, ADX, SMA slope, RSI z-score, SMA200 distance, ROC, normalised ATR — all 252-period rolling z-score standardised
- **Walk-forward backtesting** — in-sample 252 days, out-of-sample 126 days, fill delay (signal day N, execute day N+1 open), slippage
- **Volatility-ranked allocation** — three strategy tiers mapped to HMM regime volatility rank, uncertainty mode halves position sizes
- **Circuit breakers** — daily drawdown halt, weekly drawdown halt, peak drawdown hard stop — independent veto power
- **Alpaca integration** — paper and live trading, LIMIT orders, bracket OCO orders, stop tightening, exponential backoff reconnection
- **Telegram daily briefing** — regime, portfolio P&L, signals, orders placed, top news headline per ticker (NewsAPI)
- **Cron-based** — no persistent server required; adapts automatically between market-open (full pipeline) and market-closed (summary only) runs

---

## Quick Start

### 1. Clone and create environment

```bash
git clone https://github.com/HOSH19/TraderBot.git
cd TraderBot

conda create -n regime-trader python=3.11 -y
conda activate regime-trader
pip install -r requirements.txt
```

### 2. Set up credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_PAPER=true

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

NEWSAPI_KEY=your_newsapi_key   # free at newsapi.org/register
```

- **Alpaca keys** — free paper trading account at [alpaca.markets](https://alpaca.markets) → Paper Trading → API Keys
- **Telegram bot** — message [@BotFather](https://t.me/BotFather) → `/newbot` → copy token. Then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to get your `chat_id`
- **NewsAPI key** — free tier (100 req/day) at [newsapi.org/register](https://newsapi.org/register)

### 3. Configure your tickers

Edit `config/settings.yaml`:

```yaml
broker:
  symbols: [AAPL, TSLA, GOOGL, NVDA, AMD]
  paper_trading: true
```

### 4. Test your setup

```bash
# Test Alpaca API connection
python -m pytest tests/test_alpaca_api.py -v

# Send a real Telegram message with live data
python tests/test_telegram.py
```

### 5. Set up the daily cron job

```bash
crontab -e
```

Add this line (runs Mon–Fri at 4:05 PM ET = 21:05 UTC):

```
5 21 * * 1-5 /path/to/conda/envs/regime-trader/bin/python /path/to/TraderBot/run_daily.py >> /path/to/TraderBot/logs/cron.log 2>&1
```

That's it. The bot runs automatically every weekday evening.

---

## Running Manually

```bash
# Full pipeline run (works any time — adapts to market hours)
python run_daily.py

# Walk-forward backtest
python main.py --backtest --symbols AAPL --start 2020-01-01 --end 2024-12-31

# Backtest with benchmark comparison
python main.py --backtest --symbols AAPL --start 2020-01-01 --end 2024-12-31 --compare

# Stress test
python main.py --stress-test --symbols AAPL --start 2020-01-01 --end 2024-12-31

# Train HMM only
python main.py --train-only
```

---

## What the Telegram Message Looks Like

**Weekday (market open / after close) — full briefing:**
```
🤖 HMM TRADER DAILY BRIEFING
📅 Monday, Apr 14 2026  |  📄 PAPER

📊 REGIME
🐂 BULL (98% confidence)
Stability: 5 bars

💼 PORTFOLIO
Equity: $100,000.00
📈 Daily P&L: +$320.00 (+0.32%)
From Peak: 0.0%  ✅
Circuit Breaker: NORMAL ✅

🎯 TODAY'S SIGNALS
• AAPL: LONG 25% @ $261.00  stop $248.95
• NVDA: LONG 20% @ $189.50  stop $180.52

📋 ORDERS PLACED
• AAPL: BUY 95 shares @ $261.26 (LIMIT)

📦 OPEN POSITIONS
• TSLA: 40 shares  📈 +2.3%  stop $335.00

📰 TOP NEWS
• AAPL: Apple Unveils New AI Features... — Bloomberg  2h ago
• TSLA: Down 30% From Highs, Should You Buy?... — Motley Fool  4h ago
...

Next run: tomorrow after market close
```

**Weekend / holiday — summary only, no orders:**
```
🤖 REGIME TRADER MARKET SUMMARY
📅 Saturday, Apr 12 2026  |  📄 PAPER
🔴 Market: CLOSED (weekend)  |  Next open: Mon Apr 14 09:30 ET

📊 REGIME (last close)
🐂 BULL (98% confidence)
Stability: 1 bars

💼 PORTFOLIO
Equity: $100,000.00  |  From Peak: 0.0%

📦 No open positions

📉 PRICE SNAPSHOT (last close)
• AAPL: $260.43  📈 +1.2% wk
• TSLA: $348.87  📉 -2.1% wk
...

📰 TOP NEWS
• AAPL: ...
...

No orders placed — market closed
```

---

## Configuration (`config/settings.yaml`)

```yaml
broker:
  paper_trading: true
  symbols: [AAPL, TSLA, GOOGL, NVDA, AMD]
  timeframe: 1Day

hmm:
  n_candidates: [3, 4, 5, 6, 7]   # model sizes tested via BIC
  min_train_bars: 504               # minimum 2 years of data
  stability_bars: 3                 # bars before regime change confirmed
  min_confidence: 0.55              # minimum probability to act

strategy:
  low_vol_allocation: 0.95          # fully invested in calm markets
  high_vol_allocation: 0.60         # reduced in turbulent markets
  low_vol_leverage: 1.25            # modest leverage in calm conditions
  rebalance_threshold: 0.10         # only rebalance when drift >10%

risk:
  max_risk_per_trade: 0.01          # 1% portfolio max loss per trade
  max_exposure: 0.80                # max 80% invested at any time
  daily_dd_halt: 0.03               # halt at 3% daily loss
  max_dd_from_peak: 0.10            # hard stop at 10% from peak equity
```

---

## Project Structure

```
TraderBot/
├── run_daily.py              # ← main entry point (cron target)
├── main.py                   # backtest, stress-test, train CLI
├── config/
│   └── settings.yaml         # all bot parameters
├── core/
│   ├── hmm_engine.py         # Gaussian HMM, BIC, forward algorithm
│   ├── regime_strategies.py  # vol-rank allocation strategies
│   ├── risk_manager.py       # circuit breakers, order validation
│   └── signal_generator.py   # combines HMM + strategy → signals
├── data/
│   ├── market_data.py        # Alpaca historical + real-time data
│   ├── feature_engineering.py# 14 OHLCV features, z-score normalised
│   └── news_fetcher.py       # NewsAPI top headline per ticker
├── broker/
│   ├── alpaca_client.py      # Alpaca SDK wrapper
│   ├── order_executor.py     # LIMIT/bracket order management
│   └── position_tracker.py   # position sync + P&L tracking
├── backtest/
│   ├── backtester.py         # walk-forward engine
│   ├── performance.py        # Sharpe, Sortino, Calmar, drawdown
│   └── stress_test.py        # crash injection, gap risk, misclassification
├── monitoring/
│   ├── logger.py             # structured JSON rotating logs
│   ├── dashboard.py          # Rich terminal dashboard
│   ├── alerts.py             # rate-limited alert delivery
│   └── telegram_notifier.py  # Telegram daily briefing + alerts
└── tests/
    ├── test_alpaca_api.py    # API connectivity
    ├── test_telegram.py      # sends real Telegram message
    ├── test_hmm.py           # HMM training, labelling, persistence
    ├── test_look_ahead.py    # verifies zero look-ahead bias
    ├── test_strategies.py    # allocation strategy logic
    ├── test_risk.py          # circuit breakers, order validation
    └── test_orders.py        # order executor dry-run
```

---

## FAQ

**Why the forward algorithm instead of `model.predict()`?**
`model.predict()` uses the Viterbi algorithm which processes the entire sequence and revises past states using future data — look-ahead bias that makes backtests unrealistically good. The forward algorithm only uses data up to the current bar. `test_look_ahead.py` verifies this.

**Why BIC model selection?**
Instead of manually choosing the number of regimes, BIC selects the simplest model that best explains the data. It tests 3–7 regimes and picks the lowest score (penalises complexity). This prevents overfitting to noise.

**Why always long, never short?**
Walk-forward backtesting consistently showed shorting destroys returns: (1) markets have long-term upward drift, (2) V-shaped recoveries happen fast and the HMM is 2–3 days late detecting them, (3) short positions during rebounds wipe out crash gains.

**What happens if the bot crashes mid-run?**
`state_snapshot.json` is saved on every successful run. On the next run, the bot loads this and reconciles with Alpaca's actual positions. Stops remain active at the broker level regardless.

**How do I switch to live trading?**
Set `paper_trading: false` in `config/settings.yaml`. You will be required to type `YES I UNDERSTAND THE RISKS` on startup.

**Does it run if my machine is off?**
No — cron requires the machine to be on. For 24/7 unattended operation, deploy to a cloud VPS (DigitalOcean, AWS, etc.) and set the cron there.

---

## Disclaimer

This software is for **educational purposes only**. It does not constitute financial advice. Past performance of any backtested strategy does not guarantee future results. Always paper trade first and understand the risks before using real capital. The authors take no responsibility for any financial losses.
