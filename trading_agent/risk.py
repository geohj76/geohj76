"""Risk manager: decides HOW BIG a trade is and WHETHER trading is allowed at all."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from config import Config


@dataclass
class RiskManager:
    cfg: Config
    peak_equity: float = 0.0
    day: date | None = None
    day_start_equity: float = 0.0
    halted_reason: str = ""

    def position_size(self, equity: float, entry: float, stop: float) -> float:
        """Coin quantity so that hitting the stop loses ~risk_per_trade of equity,
        capped so notional value never exceeds max_leverage x equity."""
        stop_distance = abs(entry - stop)
        if stop_distance <= 0 or equity <= 0:
            return 0.0
        qty_by_risk = (equity * self.cfg.risk_per_trade) / stop_distance
        qty_by_leverage = (equity * self.cfg.max_leverage) / entry
        return max(0.0, min(qty_by_risk, qty_by_leverage))

    def can_trade(self, equity: float, today: date | None = None) -> bool:
        """Kill switches. Returns False (and records why) if trading must stop."""
        today = today or date.today()
        if self.day != today:  # new day -> reset the daily loss counter
            self.day, self.day_start_equity = today, equity
            if self.halted_reason.startswith("daily"):
                self.halted_reason = ""
        self.peak_equity = max(self.peak_equity, equity)

        if self.halted_reason.startswith("max drawdown"):
            return False  # permanent until a human restarts the agent
        if equity <= self.peak_equity * (1 - self.cfg.max_drawdown):
            self.halted_reason = f"max drawdown hit ({self.cfg.max_drawdown:.0%} from peak)"
            return False
        if equity <= self.day_start_equity * (1 - self.cfg.daily_loss_limit):
            self.halted_reason = f"daily loss limit hit ({self.cfg.daily_loss_limit:.0%})"
            return False
        return True
