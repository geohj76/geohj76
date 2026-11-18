"""Live and historical price data.

Live prices come from BloFin's *public* market-data endpoint, so no API key
or login is needed just to watch prices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests

BLOFIN_BASE = "https://openapi.blofin.com"
COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


def parse_blofin_candles(payload: dict) -> pd.DataFrame:
    """Turn BloFin's candle response into a tidy, oldest-first DataFrame."""
    if str(payload.get("code")) != "0":
        raise RuntimeError(f"BloFin error: {payload.get('msg')}")
    rows = [r[:6] for r in payload.get("data", [])]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    for c in COLUMNS[1:]:
        df[c] = df[c].astype(float)
    return df.sort_values("ts").reset_index(drop=True)


def fetch_candles(symbol: str = "BTC-USDT", bar: str = "1m", limit: int = 300) -> pd.DataFrame:
    """Fetch the most recent candles from BloFin."""
    resp = requests.get(
        f"{BLOFIN_BASE}/api/v1/market/candles",
        params={"instId": symbol, "bar": bar, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    return parse_blofin_candles(resp.json())


def synthetic_candles(n: int = 2000, start_price: float = 60000.0, seed: int = 7) -> pd.DataFrame:
    """Fake but realistic-looking price data for testing without internet."""
    rng = np.random.default_rng(seed)
    # Random walk with slowly changing trend so the strategy has something to do.
    drift = np.repeat(rng.normal(0, 0.0004, n // 200 + 1), 200)[:n]
    returns = drift + rng.normal(0, 0.003, n)
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, 0.002, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    ts = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame(
        {"ts": ts, "open": open_, "high": high, "low": low, "close": close,
         "volume": rng.uniform(1, 50, n)}
    )
