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


def test_dashboard_builds(tmp_path):
    from dashboard import write_dashboard
    log = tmp_path / "t.csv"
    run_backtest(synthetic_candles(800), Config(), str(log))
    out = write_dashboard(str(log), str(tmp_path / "d.html"), 100.0)
    page = open(out).read()
    assert "Account balance over time" in page and "const DATA" in page
    # Empty log still renders
    empty = write_dashboard(str(tmp_path / "missing.csv"), str(tmp_path / "e.html"), 100.0)
    assert "No closed trades yet" in open(empty).read()


def test_filters_only_remove_trades_and_adx_in_range():
    from dataclasses import replace
    from strategy import add_indicators
    from strategy import signal_at
    df = synthetic_candles(1500)
    off = replace(Config(), use_adx_filter=False, use_volatility_filter=False, use_trend_filter=False,
                  use_volume_filter=False, use_confirmation=False, use_breakeven_stop=False)
    ind = add_indicators(df, off)

    def n_signals(cfg):
        return sum(signal_at(ind, i, cfg).side != "none" for i in range(250, len(ind)))

    base = n_signals(off)
    assert base > 0
    for switch in ["use_adx_filter", "use_trend_filter", "use_volume_filter", "use_volatility_filter"]:
        assert n_signals(replace(off, **{switch: True})) <= base  # a filter never ADDS signals
    adx = ind["adx"].dropna()
    assert adx.between(0, 100).all()


def test_breakeven_stop_moves_to_entry():
    b = PaperBroker(100, fee_rate=0.0)
    b.open("long", 0.001, 60000, 59000, 62000, breakeven_at=60500)
    assert b.check_exits(high=60600, low=60100) is None
    assert b.position.stop == 60000
    pnl = b.check_exits(high=60100, low=59900)
    assert pnl == 0.0 and b.trades[-1]["exit"] == 60000


def test_mean_reversion_signals_and_time_stop():
    from dataclasses import replace
    from strategy import add_indicators, signal_at
    cfg = replace(Config(), strategy="mean_reversion", use_volatility_filter=False)
    df = synthetic_candles(1500)
    ind = add_indicators(df, cfg)
    assert ind["rsi"].dropna().between(0, 100).all()
    sigs = [signal_at(ind, i, cfg) for i in range(100, len(ind))]
    taken = [s for s in sigs if s.side != "none"]
    assert taken
    for s in taken:  # target is the middle band: above entry for longs, below for shorts
        if s.side == "long":
            assert s.stop < s.price < s.take_profit
        else:
            assert s.take_profit < s.price < s.stop
    r = run_backtest(df, replace(cfg, max_hold_bars=10))
    assert r["trades"] > 0
