"""The live trading agent (PAPER MONEY ONLY).

Every `poll_seconds` it:
  1. pulls fresh candles from BloFin (live price action)
  2. checks stops / take-profits on any open position
  3. runs the kill switches (daily loss, max drawdown)
  4. asks the strategy for a signal
  5. optionally screenshots your chart and asks Claude for a second opinion
  6. sizes and places the trade on the paper broker, and logs it to trades.csv
  7. refreshes dashboard.html so you can watch it in your browser

    python agent.py            # price feed only
    python agent.py --vision   # also let Claude look at your screen

Stop it any time with Ctrl+C.
"""
from __future__ import annotations

import argparse
import time

from broker import PaperBroker
from config import Config
from dashboard import write_dashboard
from data import fetch_candles
from risk import RiskManager
from strategy import generate_signal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vision", action="store_true", help="screenshot your chart for Claude to review")
    args = ap.parse_args()

    cfg = Config(use_vision=args.vision or Config.use_vision)
    if not cfg.paper_trading:
        raise SystemExit("Live trading is not implemented. Keep paper_trading=True.")

    broker = PaperBroker(cfg.starting_balance, cfg.fee_rate, cfg.log_file)
    risk = RiskManager(cfg)
    vision = None
    if cfg.use_vision:
        from vision import ChartVision, vision_allows
        vision = ChartVision(cfg.vision_model, cfg.monitor_index)
    last_bar_ts = None

    print(f"Paper-trading {cfg.symbol} on {cfg.bar} candles ({cfg.strategy}) "
          f"with ${cfg.starting_balance:.2f} fake money.")
    print("Open dashboard.html in your browser to watch it live.")
    while True:
        try:
            df = fetch_candles(cfg.symbol, cfg.bar, limit=400)
            closed = df.iloc[:-1]  # the newest candle is still forming; ignore it
            bar = closed.iloc[-1]
            new_bar = bar["ts"] != last_bar_ts  # only act once per finished candle
            last_bar_ts = bar["ts"]
            if new_bar:
                broker.check_exits(bar["high"], bar["low"], bar["ts"])
                pos = broker.position
                if pos and cfg.max_hold_bars and pos.bars_held >= cfg.max_hold_bars:
                    broker.close(float(bar["close"]), bar["ts"], "time")
            equity = broker.equity(float(df["close"].iloc[-1]))

            if not risk.can_trade(equity):
                if broker.position:
                    broker.close(float(df["close"].iloc[-1]), bar["ts"], "risk halt")
                print(f"HALTED: {risk.halted_reason}. Equity ${equity:.2f}")
                if risk.halted_reason.startswith("max drawdown"):
                    break
            elif new_bar:
                sig = generate_signal(closed, cfg)
                if sig.reason.startswith("filtered"):
                    print(f"  signal skipped - {sig.reason}")
                if not broker.position and sig.side != "none":
                    read = vision.analyze(cfg.symbol) if vision else None  # look only when it matters
                    if read:
                        print(f"  Claude sees: {read['bias']} ({read['confidence']:.0%}) - {read['notes']}")
                    if read and not vision_allows(sig.side, read):
                        print(f"  {sig.side} signal vetoed by chart read")
                    else:
                        qty = risk.position_size(equity, sig.price, sig.stop)
                        broker.open(sig.side, qty, sig.price, sig.stop, sig.take_profit, bar["ts"],
                                    sig.breakeven_at)
                        print(f"  OPEN {sig.side} {qty:.6f} @ {sig.price:.2f} "
                              f"stop {sig.stop:.2f} target {sig.take_profit:.2f} ({sig.reason})")

            pos = broker.position
            status = f"{pos.side} @ {pos.entry:.2f}" if pos else "flat"
            print(f"[{bar['ts']:%H:%M}] price {df['close'].iloc[-1]:.2f} | equity ${equity:.2f} | {status}")
            write_dashboard(cfg.log_file, starting_balance=cfg.starting_balance)
        except KeyboardInterrupt:
            raise
        except Exception as e:  # network blips etc. - keep running
            print(f"  error: {e}")
        time.sleep(cfg.poll_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
