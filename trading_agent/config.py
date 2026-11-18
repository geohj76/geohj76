"""All the knobs in one place. Start conservative; change one thing at a time."""
from dataclasses import dataclass


@dataclass
class Config:
    # --- Market ---
    symbol: str = "BTC-USDT"        # BloFin instrument id (perpetual futures)
    bar: str = "1H"                 # candle size. 1H tested best on real data (1m/15m lost money)
    poll_seconds: int = 30          # how often the agent checks for new prices

    # --- Which strategy to run ---
    strategy: str = "ema_cross"     # "ema_cross" (trend following) or "mean_reversion"
    max_hold_bars: int = 0          # time stop: close a trade after this many candles (0 = off)

    # --- Strategy A: EMA crossover trend-following with ATR stops ---
    fast_ema: int = 9
    slow_ema: int = 21
    atr_period: int = 14
    stop_atr_mult: float = 2.0      # stop-loss distance = 2 x ATR
    take_profit_atr_mult: float = 4.0  # 2:1 reward-to-risk

    # --- Filters: ON/OFF switches (True = on). Turn on ONE at a time and test. ---
    # 1. Skip choppy markets: only trade when ADX says there's a real trend.
    use_adx_filter: bool = False
    adx_period: int = 14
    adx_min: float = 20.0
    # 1b. Skip dead markets: only trade when volatility is at least normal.
    use_volatility_filter: bool = True   # ON for paper testing. Helped Jun-Nov 2026, NOT Sep 2025-Jun 2026: unproven
    min_atr_ratio: float = 0.8      # ATR must be >= 80% of its recent typical level
    # 2. Only trade with the bigger trend (longs above the 200 EMA, shorts below).
    use_trend_filter: bool = False
    trend_ema: int = 200
    # 4a. Wait one extra candle to confirm the crossover held.
    use_confirmation: bool = False
    # 4b. Only trade crossovers with above-average volume.
    use_volume_filter: bool = False
    volume_period: int = 20
    # 5. Move the stop to the entry price once a trade is this many ATRs in profit.
    use_breakeven_stop: bool = False
    breakeven_trigger_atr: float = 1.0
    # (3. Slower timeframe = change `bar` above, e.g. "15m" or "1H".)
    # Filters 1b (volatility) and 2 (200 EMA trend) also apply to mean reversion.

    # --- Strategy B: mean reversion (Bollinger Bands + RSI) ---
    # Buy when price is stretched far BELOW its 20-candle average and RSI says oversold;
    # sell short when stretched far ABOVE and overbought. Take profit back at the average.
    bb_period: int = 20
    bb_std: float = 2.0             # band width in standard deviations
    rsi_period: int = 14
    rsi_low: float = 30.0           # oversold
    rsi_high: float = 70.0          # overbought
    mr_stop_atr_mult: float = 1.5   # stop-loss distance beyond entry
    # Mean-reversion switches:
    use_range_filter: bool = False  # only trade when ADX is LOW (sideways market)
    range_adx_max: float = 25.0
    use_reentry_confirm: bool = False  # wait for a candle to close back inside the band

    # --- Risk limits (the most important section) ---
    starting_balance: float = 100.0
    risk_per_trade: float = 0.01    # risk 1% of the account per trade
    max_leverage: float = 3.0       # hard cap, never above this
    daily_loss_limit: float = 0.05  # stop trading for the day after -5%
    max_drawdown: float = 0.25      # shut down completely after -25% from peak
    fee_rate: float = 0.0006        # ~0.06% taker fee per side

    # --- Screen vision (optional) ---
    use_vision: bool = False        # turn on to have Claude look at your chart
    vision_model: str = "claude-opus-5-5"
    monitor_index: int = 1          # 1 = main monitor

    # --- Safety ---
    paper_trading: bool = True      # True = fake money. There is no live mode yet.
    log_file: str = "trades.csv"
