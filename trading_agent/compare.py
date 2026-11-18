"""Compare the strategy with each filter switched on, one at a time.

    python compare.py                      # real BloFin BTC-USDT history, 1H candles (needs internet)
    python compare.py --bar 15m            # try another timeframe
    python compare.py --candles 20000      # more history
    python compare.py --synthetic          # fake data, just to check it runs
    python compare.py --strategy mean_reversion   # test the mean-reversion strategy

The data is split in two:
  TUNE  = first 70%  - use this to decide which switches look good
  CHECK = last 30%   - data the choice never saw. If a filter only helps
                       in TUNE but not CHECK, the improvement wasn't real.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import replace

import pandas as pd

from backtest import run_backtest
from config import Config

EMA_VARIANTS = [
    ("Baseline (no filters)", {}),
    ("1. ADX chop filter", {"use_adx_filter": True}),
    ("1b. Volatility filter", {"use_volatility_filter": True}),
    ("2. 200 EMA trend filter", {"use_trend_filter": True}),
    ("4a. Wait 1 candle", {"use_confirmation": True}),
    ("4b. Volume filter", {"use_volume_filter": True}),
    ("5. Breakeven stop", {"use_breakeven_stop": True}),
    ("1 + 2 together", {"use_adx_filter": True, "use_trend_filter": True}),
    ("All filters on", {"use_adx_filter": True, "use_volatility_filter": True,
                        "use_trend_filter": True, "use_confirmation": True,
                        "use_volume_filter": True, "use_breakeven_stop": True}),
]

MR_VARIANTS = [
    ("Baseline (BB 2.0, RSI 30/70)", {}),
    ("Wait for close back inside", {"use_reentry_confirm": True}),
    ("Range filter (ADX < 25)", {"use_range_filter": True}),
    ("200 EMA trend filter", {"use_trend_filter": True}),
    ("Volatility filter", {"use_volatility_filter": True}),
    ("Wider bands (2.5)", {"bb_std": 2.5}),
    ("Stricter RSI (25/75)", {"rsi_low": 25.0, "rsi_high": 75.0}),
    ("Wider stop (2.5 ATR)", {"mr_stop_atr_mult": 2.5}),
    ("Time stop (24 candles)", {"max_hold_bars": 24}),
    ("Range + wait inside", {"use_range_filter": True, "use_reentry_confirm": True}),
    ("Trend + wait inside", {"use_trend_filter": True, "use_reentry_confirm": True}),
]


def load_data(args, cfg: Config) -> pd.DataFrame:
    if args.synthetic:
        from data import synthetic_candles
        return synthetic_candles(args.candles)
    cache = f"history_{cfg.symbol}_{args.bar}.csv"
    if os.path.exists(cache) and not args.refresh:
        df = pd.read_csv(cache, parse_dates=["ts"])
        if len(df) >= args.candles:
            print(f"Using saved data in {cache} (add --refresh to re-download)")
            return df.tail(args.candles).reset_index(drop=True)
    from data import fetch_history
    print(f"Downloading {args.candles} {args.bar} candles of {cfg.symbol} from BloFin...")
    df = fetch_history(cfg.symbol, args.bar, args.candles)
    df.to_csv(cache, index=False)
    return df


def fmt(r: dict) -> str:
    return (f"{r['trades']:>6} {r['win_rate_pct']:>6.1f}% {r['return_pct']:>+8.2f}% "
            f"{r['max_drawdown_pct']:>6.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--strategy", default=Config().strategy, choices=["ema_cross", "mean_reversion"])
    ap.add_argument("--bar", default=Config().bar)  # 1H by default
    ap.add_argument("--candles", type=int, default=10000)
    ap.add_argument("--refresh", action="store_true", help="re-download history")
    args = ap.parse_args()

    # Start every variant from "all filters off" so the baseline really is the baseline.
    base = replace(Config(), bar=args.bar, strategy=args.strategy, max_hold_bars=0,
                   use_range_filter=False, use_reentry_confirm=False, use_adx_filter=False, use_volatility_filter=False,
                   use_trend_filter=False, use_confirmation=False, use_volume_filter=False,
                   use_breakeven_stop=False)
    df = load_data(args, base)
    split = int(len(df) * 0.7)
    tune, check = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)
    print(f"\n{args.strategy}: {len(df)} candles of {args.bar}, "
          f"{df['ts'].iloc[0]:%Y-%m-%d} to {df['ts'].iloc[-1]:%Y-%m-%d}\n")
    variants = MR_VARIANTS if args.strategy == "mean_reversion" else EMA_VARIANTS

    head = f"{'trades':>6} {'win':>7} {'return':>9} {'drop':>7}"
    print(f"{'':26}| {'TUNE (first 70%)':^31} | {'CHECK (last 30%)':^31}")
    print(f"{'Variant':26}| {head} | {head}")
    print("-" * 94)
    for name, switches in variants:
        cfg = replace(base, **switches)
        print(f"{name:26}| {fmt(run_backtest(tune, cfg))} | {fmt(run_backtest(check, cfg))}")
    print("\nwin = win rate, drop = biggest drop from peak.")
    print("Only trust a filter that beats the baseline in BOTH columns, with 30+ trades.")
    print("Change the matching setting in config.py to use it.")


if __name__ == "__main__":
    main()
