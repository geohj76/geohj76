"""EMA crossover trend-following strategy with ATR-based stops.

Plain English:
  - When the fast average crosses ABOVE the slow average -> price is trending up -> go LONG.
  - When it crosses BELOW -> trending down -> go SHORT.
  - Stop-loss and take-profit distances scale with volatility (ATR).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import Config


def add_indicators(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=cfg.fast_ema, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=cfg.slow_ema, adjust=False).mean()
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    df["atr"] = true_range.rolling(cfg.atr_period).mean()
    return df


@dataclass
class Signal:
    side: str          # "long", "short", or "none"
    price: float
    stop: float = 0.0
    take_profit: float = 0.0
    reason: str = ""


def generate_signal(df: pd.DataFrame, cfg: Config) -> Signal:
    """Look at the last two *closed* candles and decide whether to enter."""
    df = add_indicators(df, cfg)
    if len(df) < cfg.slow_ema + 2 or pd.isna(df["atr"].iloc[-1]):
        return Signal("none", float(df["close"].iloc[-1]), reason="not enough data")

    prev, last = df.iloc[-2], df.iloc[-1]
    price, atr = float(last["close"]), float(last["atr"])
    crossed_up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
    crossed_down = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]

    if crossed_up:
        return Signal("long", price, price - cfg.stop_atr_mult * atr,
                      price + cfg.take_profit_atr_mult * atr, "fast EMA crossed above slow")
    if crossed_down:
        return Signal("short", price, price + cfg.stop_atr_mult * atr,
                      price - cfg.take_profit_atr_mult * atr, "fast EMA crossed below slow")
    return Signal("none", price, reason="no crossover")
