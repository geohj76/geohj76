import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import run_backtest  # noqa: E402
from broker import PaperBroker  # noqa: E402
from config import Config  # noqa: E402
from data import parse_blofin_candles, synthetic_candles  # noqa: E402
from risk import RiskManager  # noqa: E402
from vision import parse_vision_reply, vision_allows  # noqa: E402


def test_parse_blofin_candles_sorts_oldest_first():
    payload = {"code": "0", "data": [
        ["1700000060000", "101", "102", "100", "101.5", "5", "x", "y", "1"],
        ["1700000000000", "100", "101", "99", "100.5", "4", "x", "y", "1"],
    ]}
    df = parse_blofin_candles(payload)
    assert list(df["close"]) == [100.5, 101.5]


def test_position_size_respects_risk_and_leverage():
    cfg = Config()
    rm = RiskManager(cfg)
    # $100 equity, 1% risk = $1; stop $100 away -> 0.01 BTC, but leverage cap 3x at $60k = 0.005
    qty = rm.position_size(100, 60000, 59900)
    assert abs(qty - 0.005) < 1e-9
    # Wide stop -> risk-based size is smaller than leverage cap
    qty = rm.position_size(100, 60000, 58000)
    assert abs(qty - 1 / 2000) < 1e-9


def test_kill_switches():
    rm = RiskManager(Config())
    d = date(2026, 1, 1)
    assert rm.can_trade(100, d)
    assert not rm.can_trade(94, d)                 # -6% in a day
    assert rm.can_trade(94, date(2026, 1, 2))      # new day resets
    assert not rm.can_trade(74, date(2026, 1, 3))  # -26% from peak
    assert not rm.can_trade(100, date(2026, 1, 4))  # drawdown halt is permanent


def test_broker_stop_loss_and_fees():
    b = PaperBroker(100, fee_rate=0.001)
    b.open("long", 0.001, 60000, 59000, 62000)
    pnl = b.check_exits(high=60100, low=58900)
    assert pnl < -1.0 and b.position is None
    assert b.balance < 99


def test_backtest_runs_and_never_exceeds_drawdown_much():
    result = run_backtest(synthetic_candles(1500), Config())
    assert result["trades"] > 0
    assert result["max_drawdown_pct"] < 30


def test_vision_parsing_and_veto():
    read = parse_vision_reply('Sure: {"bias": "bearish", "confidence": 0.8, "notes": "lower highs"}')
    assert read["bias"] == "bearish"
    assert not vision_allows("long", read)
    assert vision_allows("short", read)
    assert parse_vision_reply("garbage")["bias"] == "neutral"
