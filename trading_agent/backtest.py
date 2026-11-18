"""Test the strategy on past data before risking anything.

    python backtest.py              # uses live BloFin history (needs internet)
    python backtest.py --synthetic  # uses fake data (works offline)
"""
from __future__ import annotations

import argparse

import pandas as pd

from broker import PaperBroker
from config import Config
from risk import RiskManager
from strategy import add_indicators, generate_signal


def run_backtest(df: pd.DataFrame, cfg: Config) -> dict:
    broker = PaperBroker(cfg.starting_balance, cfg.fee_rate)
    risk = RiskManager(cfg)
    df = add_indicators(df, cfg)
    equity_curve = []
    warmup = cfg.slow_ema + cfg.atr_period

    for i in range(warmup, len(df)):
        bar = df.iloc[i]
        broker.check_exits(bar["high"], bar["low"], bar["ts"])
        equity = broker.equity(bar["close"])
        equity_curve.append(equity)

        if not risk.can_trade(equity, bar["ts"].date()):
            if broker.position:
                broker.close(bar["close"], bar["ts"], "risk halt")
            continue
        if broker.position:
            continue

        sig = generate_signal(df.iloc[: i + 1], cfg)
        if sig.side != "none":
            qty = risk.position_size(equity, sig.price, sig.stop)
            broker.open(sig.side, qty, sig.price, sig.stop, sig.take_profit, bar["ts"])

    if broker.position:
        broker.close(df["close"].iloc[-1], df["ts"].iloc[-1], "end")

    curve = pd.Series(equity_curve or [cfg.starting_balance])
    trades = broker.trades
    wins = [t for t in trades if t["pnl"] > 0]
    return {
        "start": cfg.starting_balance,
        "end": round(broker.balance, 2),
        "return_pct": round((broker.balance / cfg.starting_balance - 1) * 100, 2),
        "trades": len(trades),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1) if trades else 0.0,
        "max_drawdown_pct": round(100 * (1 - (curve / curve.cummax())).max(), 2),
        "halted": risk.halted_reason or "no",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="use fake data (offline)")
    args = ap.parse_args()
    cfg = Config()
    if args.synthetic:
        from data import synthetic_candles
        df = synthetic_candles()
    else:
        from data import fetch_candles
        df = fetch_candles(cfg.symbol, cfg.bar, limit=1440)
    for k, v in run_backtest(df, cfg).items():
        print(f"{k:>18}: {v}")


if __name__ == "__main__":
    main()
