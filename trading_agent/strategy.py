"""EMA crossover trend-following strategy with ATR-based stops and optional filters.

Plain English:
  - When the fast average crosses ABOVE the slow average -> price is trending up -> go LONG.
  - When it crosses BELOW -> trending down -> go SHORT.
  - Stop-loss and take-profit distances scale with volatility (ATR).
  - Optional filters (switched on/off in config.py) skip the weaker signals.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import Config


def add_indicators(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    df = df.copy()
    close, high, low = df["close"], df["high"], df["low"]
    df["ema_fast"] = close.ewm(span=cfg.fast_ema, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=cfg.slow_ema, adjust=False).mean()
    df["ema_trend"] = close.ewm(span=cfg.trend_ema, adjust=False).mean()

    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    df["atr"] = true_range.rolling(cfg.atr_period).mean()
    df["atr_typical"] = df["atr"].rolling(100, min_periods=20).median()

    # ADX (Wilder): 0-100, higher = stronger trend in either direction.
    up, down = high.diff(), -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    alpha = 1 / cfg.adx_period
    atr_w = true_range.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean() / atr_w
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean() / atr_w
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df["adx"] = dx.ewm(alpha=alpha, adjust=False).mean()

    df["vol_avg"] = df["volume"].rolling(cfg.volume_period).mean()
    return df


def warmup_bars(cfg: Config) -> int:
    """How many candles the indicators need before signals are trustworthy."""
    need = max(cfg.slow_ema, 3 * cfg.adx_period, cfg.volume_period)
    if cfg.use_trend_filter:
        need = max(need, cfg.trend_ema)
    if cfg.use_volatility_filter:
        need = max(need, 100)
    return need + cfg.atr_period + 2


@dataclass
class Signal:
    side: str          # "long", "short", or "none"
    price: float
    stop: float = 0.0
    take_profit: float = 0.0
    reason: str = ""
    breakeven_at: float | None = None  # price at which the stop moves to entry


def _crossover(df: pd.DataFrame, i: int) -> str:
    prev, cur = df.iloc[i - 1], df.iloc[i]
    if prev["ema_fast"] <= prev["ema_slow"] and cur["ema_fast"] > cur["ema_slow"]:
        return "long"
    if prev["ema_fast"] >= prev["ema_slow"] and cur["ema_fast"] < cur["ema_slow"]:
        return "short"
    return "none"


def signal_at(df: pd.DataFrame, i: int, cfg: Config) -> Signal:
    """Signal for candle i of a DataFrame that already has indicators."""
    last = df.iloc[i]
    price, atr = float(last["close"]), float(last["atr"])
    if i < 2 or pd.isna(atr):
        return Signal("none", price, reason="not enough data")

    if cfg.use_confirmation:
        # The crossover happened on the PREVIOUS candle; this candle must confirm it.
        side = _crossover(df, i - 1)
        if side == "long" and not (last["ema_fast"] > last["ema_slow"] and price > last["ema_fast"]):
            return Signal("none", price, reason="filtered: crossover not confirmed")
        if side == "short" and not (last["ema_fast"] < last["ema_slow"] and price < last["ema_fast"]):
            return Signal("none", price, reason="filtered: crossover not confirmed")
    else:
        side = _crossover(df, i)
    if side == "none":
        return Signal("none", price, reason="no crossover")

    if cfg.use_adx_filter and not (last["adx"] >= cfg.adx_min):
        return Signal("none", price, reason=f"filtered: choppy (ADX {last['adx']:.0f})")
    if cfg.use_volatility_filter and not (atr >= cfg.min_atr_ratio * last["atr_typical"]):
        return Signal("none", price, reason="filtered: volatility too low")
    if cfg.use_trend_filter:
        if (side == "long" and price < last["ema_trend"]) or (side == "short" and price > last["ema_trend"]):
            return Signal("none", price, reason=f"filtered: against the {cfg.trend_ema} EMA trend")
    if cfg.use_volume_filter:
        bar = df.iloc[i - 1] if cfg.use_confirmation else last  # the crossover candle
        if not (bar["volume"] > bar["vol_avg"]):
            return Signal("none", price, reason="filtered: low volume")

    sign = 1 if side == "long" else -1
    breakeven = price + sign * cfg.breakeven_trigger_atr * atr if cfg.use_breakeven_stop else None
    return Signal(
        side, price,
        stop=price - sign * cfg.stop_atr_mult * atr,
        take_profit=price + sign * cfg.take_profit_atr_mult * atr,
        reason=f"fast EMA crossed {'above' if side == 'long' else 'below'} slow",
        breakeven_at=breakeven,
    )


def generate_signal(df: pd.DataFrame, cfg: Config) -> Signal:
    """Signal for the latest closed candle (used by the live agent)."""
    df = add_indicators(df, cfg)
    if len(df) < cfg.slow_ema + 2:
        return Signal("none", float(df["close"].iloc[-1]), reason="not enough data")
    return signal_at(df, len(df) - 1, cfg)
