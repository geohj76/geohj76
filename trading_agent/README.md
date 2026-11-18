# Crypto Trading Agent (paper trading)

A beginner-friendly crypto futures trading agent for BTC-USDT on BloFin.
**It only trades fake money.** There is no live-order code yet, on purpose.

## How it works

| Part | File | What it does |
|---|---|---|
| Live prices | `data.py` | Pulls candles from BloFin's public API (no login or key needed) |
| Strategy | `strategy.py` | EMA 9/21 crossover: trend up = long, trend down = short. Stops and targets set by volatility (ATR) |
| Risk | `risk.py` | Risks 1% per trade, max 3x leverage, stops after -5% in a day, shuts down at -25% |
| Broker | `broker.py` | Simulated fills with fees; logs every trade to `trades.csv` |
| Screen vision | `vision.py` | Optional: screenshots your chart and asks Claude for a read. It can only **veto** a trade, never start one |
| Agent loop | `agent.py` | Ties it all together every 30 seconds |
| Dashboard | `dashboard.py` | Builds `dashboard.html`: balance, win rate, biggest drop, a balance chart and recent trades |
| Backtest | `backtest.py` | Tests the strategy on past data |

## Setup (on your own computer)

```bash
cd trading_agent
pip install -r requirements.txt
python -m pytest tests          # check everything works
python backtest.py --synthetic  # backtest on fake data (offline)
python backtest.py              # backtest on the last day of real BTC data
python agent.py                 # start paper trading with live prices
```

## Strategies

Pick one with `strategy` in `config.py`:

| `strategy` | Idea |
|---|---|
| `"ema_cross"` (default) | Trend following: buy when the fast average crosses above the slow one |
| `"mean_reversion"` | Fade the stretch: buy when price drops below the lower Bollinger Band with RSI oversold, take profit back at the 20-candle average |

Mean-reversion switches: `use_range_filter` (only trade sideways markets), `use_reentry_confirm`
(wait for a candle to close back inside the band), plus `bb_std`, `rsi_low`/`rsi_high`,
`mr_stop_atr_mult` and `max_hold_bars` (time stop).

```bash
python compare.py --strategy mean_reversion --bar 4H --candles 9000
```

Best result so far (real BloFin data, Jan 2023 – Nov 2026, 4H candles): mean reversion with
`use_reentry_confirm = True` was the only setup positive in both halves with 30+ trades each
(+3.5% / 116 trades, then +10.1% / 48 trades). Many variants were tested, so treat it as a lead
to paper trade, not a proven edge.

## Filters (on/off switches)

All in `config.py`. Defaults: **1H candles with the volatility filter on**, everything else off.

Results on real BloFin BTC-USDT data (Nov 2026):
- 1m and 15m candles lost money with every filter. 1H was far better.
- On Sep 2025 – Nov 2026 1H data, **no filter beat the baseline in both halves.** The volatility
  and ADX filters helped a lot in the recent ~4 months but slightly hurt in the 10 months before.
- The volatility filter is on as an experiment for paper trading, not because it's proven.

| Switch | What it does |
|---|---|
| `use_adx_filter` | Skips choppy, sideways markets (ADX below 20) |
| `use_volatility_filter` | Skips unusually quiet markets |
| `use_trend_filter` | Longs only above the 200 EMA, shorts only below |
| `use_confirmation` | Waits one more candle to confirm the crossover held |
| `use_volume_filter` | Only trades crossovers with above-average volume |
| `use_breakeven_stop` | Moves the stop to the entry price once a trade is 1 ATR in profit |
| `bar` | Timeframe: `"1m"`, `"15m"`, `"1H"` (default), `"4H"` |

Before switching anything on, compare them on real data:

```bash
python compare.py               # real BloFin history, 1H candles
python compare.py --bar 15m     # try another timeframe
```

It splits the history into TUNE (first 70%) and CHECK (last 30%). Only trust a filter
that beats the baseline in **both** columns with 30+ trades.

## Dashboard

While `agent.py` runs, open `dashboard.html` (in the `trading_agent` folder) in your browser.
It reloads itself every 30 seconds. Hover over the chart to see your balance after each trade.

- `python backtest.py --dashboard` builds `backtest_dashboard.html` for a backtest
- `python dashboard.py` rebuilds the dashboard from `trades.csv` any time

### Turn on screen vision (optional)

1. Get an Anthropic API key at console.anthropic.com and run `export ANTHROPIC_API_KEY=...`
2. Open your BloFin chart full-screen on your main monitor.
3. Run `python agent.py --vision`

Each screenshot costs a few cents, so the agent only looks when the strategy wants to open a trade.

## Rules before ever using real money

1. Paper trade for at least 4–8 weeks.
2. Review `trades.csv`: more than 50 trades, profitable after fees, max drawdown you can live with.
3. If it loses money on paper, it will lose money live. Change the strategy, don't add leverage.
4. When you're ready for live trading, create a BloFin API key with **trade-only permission
   and withdrawals disabled**, keep it on your computer, and never paste it in a chat.

This is an educational project, not financial advice.
