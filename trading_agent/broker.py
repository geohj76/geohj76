"""Paper broker: simulates futures fills, fees, stops and take-profits with fake money.

There is intentionally NO live-order code here yet. Run paper trading for weeks
first; only add a live broker once results are consistently positive.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass


@dataclass
class Position:
    side: str           # "long" or "short"
    qty: float
    entry: float
    stop: float
    take_profit: float
    breakeven_at: float | None = None  # once price reaches this, stop moves to entry


class PaperBroker:
    def __init__(self, balance: float, fee_rate: float, log_file: str | None = None):
        self.balance = balance          # realized cash
        self.fee_rate = fee_rate
        self.position: Position | None = None
        self.trades: list[dict] = []
        self.log_file = log_file

    def equity(self, price: float) -> float:
        """Cash plus unrealized profit/loss of any open position."""
        if not self.position:
            return self.balance
        p = self.position
        direction = 1 if p.side == "long" else -1
        return self.balance + direction * (price - p.entry) * p.qty

    def open(self, side: str, qty: float, price: float, stop: float, take_profit: float, ts=None,
             breakeven_at: float | None = None):
        if self.position or qty <= 0:
            return
        self.balance -= qty * price * self.fee_rate
        self.position = Position(side, qty, price, stop, take_profit, breakeven_at)
        self._log(ts, "open", side, qty, price, 0.0)

    def close(self, price: float, ts=None, reason: str = "") -> float:
        if not self.position:
            return 0.0
        p = self.position
        direction = 1 if p.side == "long" else -1
        pnl = direction * (price - p.entry) * p.qty - p.qty * price * self.fee_rate
        self.balance += pnl
        self.trades.append({"side": p.side, "entry": p.entry, "exit": price, "qty": p.qty, "pnl": pnl})
        self._log(ts, f"close:{reason}", p.side, p.qty, price, pnl)
        self.position = None
        return pnl

    def check_exits(self, high: float, low: float, ts=None) -> float | None:
        """Within one candle, did price touch the stop or target? (Stop checked first: conservative.)"""
        p = self.position
        if not p:
            return None
        if p.side == "long":
            if low <= p.stop:
                return self.close(p.stop, ts, "breakeven" if p.stop == p.entry else "stop")
            if high >= p.take_profit:
                return self.close(p.take_profit, ts, "target")
            if p.breakeven_at is not None and high >= p.breakeven_at:
                p.stop, p.breakeven_at = max(p.stop, p.entry), None
        else:
            if high >= p.stop:
                return self.close(p.stop, ts, "breakeven" if p.stop == p.entry else "stop")
            if low <= p.take_profit:
                return self.close(p.take_profit, ts, "target")
            if p.breakeven_at is not None and low <= p.breakeven_at:
                p.stop, p.breakeven_at = min(p.stop, p.entry), None
        return None

    def _log(self, ts, action, side, qty, price, pnl):
        if not self.log_file:
            return
        new = not os.path.exists(self.log_file)
        with open(self.log_file, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "action", "side", "qty", "price", "pnl", "balance"])
            w.writerow([ts, action, side, f"{qty:.6f}", f"{price:.2f}", f"{pnl:.4f}", f"{self.balance:.4f}"])
