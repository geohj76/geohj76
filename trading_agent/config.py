"""All the knobs in one place. Start conservative; change one thing at a time."""
from dataclasses import dataclass


@dataclass
class Config:
    # --- Market ---
    symbol: str = "BTC-USDT"        # BloFin instrument id (perpetual futures)
    bar: str = "1H"                 # candle size. 1H tested best on real data (1m/15m lost money)
    poll_seconds: int = 30          # how often the agent checks for new prices

    # --- Strategy (EMA trend-following with ATR stops) ---
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
    vision_every_n_polls: int = 10  # screenshots cost money; don't send every poll
    monitor_index: int = 1          # 1 = main monitor

    # --- Safety ---
    paper_trading: bool = True      # True = fake money. There is no live mode yet.
    log_file: str = "trades.csv"
