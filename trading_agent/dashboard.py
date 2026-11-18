"""Build a dashboard web page from the trade log.

    python dashboard.py                      # reads trades.csv -> dashboard.html
    python dashboard.py backtest_trades.csv  # any trade log

Open dashboard.html in your browser. While agent.py is running it rewrites the
page after every check, and the page reloads itself every 30 seconds.
Everything is in one file with no internet needed.
"""
from __future__ import annotations

import html
import json
import os
import sys

import pandas as pd

from config import Config


def load_trades(path: str) -> pd.DataFrame:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame(columns=["time", "action", "side", "qty", "price", "pnl", "balance"])
    return pd.read_csv(path)


def summarize(df: pd.DataFrame, starting_balance: float) -> dict:
    closes = df[df["action"].astype(str).str.startswith("close")]
    balances = [starting_balance] + df["balance"].astype(float).tolist()
    curve = pd.Series(balances)
    drawdown = (1 - curve / curve.cummax()).max() if len(curve) else 0.0
    wins = closes[closes["pnl"].astype(float) > 0]
    last = df.iloc[-1] if len(df) else None
    open_pos = None
    if last is not None and last["action"] == "open":
        open_pos = {"side": last["side"], "price": float(last["price"]), "qty": float(last["qty"])}
    balance = balances[-1]
    return {
        "balance": balance,
        "return_pct": (balance / starting_balance - 1) * 100,
        "trades": len(closes),
        "win_rate": 100 * len(wins) / len(closes) if len(closes) else None,
        "max_dd": drawdown * 100,
        "best": float(closes["pnl"].max()) if len(closes) else None,
        "worst": float(closes["pnl"].min()) if len(closes) else None,
        "open": open_pos,
    }


def _when(ts) -> str:
    t = pd.to_datetime(ts, errors="coerce", utc=True)
    return str(ts) if pd.isna(t) else t.strftime("%b %d, %H:%M UTC")


def _money(x: float | None, sign: bool = False) -> str:
    if x is None:
        return "–"
    s = f"{abs(x):,.2f}"
    if sign:
        return ("+$" if x >= 0 else "−$") + s
    return ("−$" if x < 0 else "$") + s


def build_html(df: pd.DataFrame, starting_balance: float, title: str = "Paper Trading",
               live: bool = True) -> str:
    s = summarize(df, starting_balance)
    points = [{"t": "start", "v": starting_balance}] + [
        {"t": _when(r.time), "v": float(r.balance)} for r in df.itertuples()
    ]
    closes = df[df["action"].astype(str).str.startswith("close")].tail(25).iloc[::-1]

    rows = []
    for r in closes.itertuples():
        pnl = float(r.pnl)
        status = "good" if pnl > 0 else "critical"
        icon = "▲" if pnl > 0 else "▼"
        word = "Win" if pnl > 0 else "Loss"
        reason = str(r.action).split(":", 1)[-1]
        rows.append(
            f"<tr><td>{html.escape(_when(r.time))}</td><td>{html.escape(str(r.side)).title()}</td>"
            f"<td class=num>{float(r.price):,.2f}</td><td>{html.escape(reason)}</td>"
            f"<td class=num><span class='dot {status}' aria-hidden=true>{icon}</span> "
            f"{word} {_money(pnl, sign=True)}</td>"
            f"<td class=num>{_money(float(r.balance))}</td></tr>"
        )
    table = "".join(rows) or "<tr><td colspan=6 class=empty>No closed trades yet. The agent is watching for a signal.</td></tr>"

    if s["open"]:
        o = s["open"]
        position = f"{o['side'].title()} {o['qty']:.6f} @ {o['price']:,.2f}"
    else:
        position = "None (flat)"
    win_rate = "–" if s["win_rate"] is None else f"{s['win_rate']:.0f}%"
    ret_cls = "up" if s["return_pct"] >= 0 else "down"
    data_json = json.dumps(points).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{'<meta http-equiv="refresh" content="30">' if live else ''}
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: light;
  --surface-0: #f4f3f0; --surface-1: #fcfcfb; --border: #e3e2dd;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #77766f;
  --grid: #e9e8e4; --series-1: #2a78d6; --ref: #9a998f;
  --good: #0ca30c; --critical: #d03b3b;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    color-scheme: dark;
    --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2e2c;
    --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #94938a;
    --grid: #2a2a28; --series-1: #3987e5; --ref: #6f6e66;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --surface-0: #111110; --surface-1: #1a1a19; --border: #2e2e2c;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #94938a;
  --grid: #2a2a28; --series-1: #3987e5; --ref: #6f6e66;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--surface-0); color: var(--text-primary);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1040px; margin: 0 auto; padding: 24px 16px 48px; }}
header {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }}
h1 {{ font-size: 20px; margin: 0; }}
.badge {{ font-size: 12px; color: var(--text-secondary); border: 1px solid var(--border);
  border-radius: 999px; padding: 2px 10px; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }}
.tile, .card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; }}
.tile {{ padding: 14px 16px; }}
.tile .label {{ font-size: 12px; color: var(--text-secondary); }}
.tile .value {{ font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; margin-top: 2px; }}
.tile .sub {{ font-size: 12px; color: var(--text-muted); }}
.tile .sub.up::before {{ content: "▲ "; color: var(--good); }}
.tile .sub.down::before {{ content: "▼ "; color: var(--critical); }}
.card {{ padding: 16px; margin-bottom: 16px; }}
.card h2 {{ font-size: 15px; margin: 0 0 2px; }}
.card p {{ margin: 0 0 12px; color: var(--text-secondary); font-size: 13px; }}
.chart {{ position: relative; }}
svg {{ display: block; width: 100%; height: 280px; overflow: visible; }}
.tip {{ position: absolute; pointer-events: none; background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 10px; font-size: 12px; box-shadow: 0 4px 14px rgb(0 0 0 / .12);
  white-space: nowrap; opacity: 0; transition: opacity .1s; }}
.tip b {{ display: block; font-size: 14px; font-variant-numeric: tabular-nums; }}
.tip span {{ color: var(--text-secondary); }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; font-weight: 500; color: var(--text-secondary); border-bottom: 1px solid var(--border); padding: 8px; }}
td {{ padding: 8px; border-bottom: 1px solid var(--grid); white-space: nowrap; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
th.num {{ text-align: right; }}
.dot {{ font-size: 10px; }}
.dot.good {{ color: var(--good); }} .dot.critical {{ color: var(--critical); }}
.empty {{ text-align: center; color: var(--text-muted); padding: 24px; }}
footer {{ font-size: 12px; color: var(--text-muted); margin-top: 8px; }}
</style></head>
<body><main>
<header><h1>{html.escape(title)}</h1><span class="badge">{'Fake money · updates every 30s' if live else 'Simulated on past prices'}</span></header>

<section class="tiles">
  <div class="tile"><div class="label">Account balance</div><div class="value">{_money(s['balance'])}</div>
    <div class="sub {ret_cls}">{s['return_pct']:+.2f}% from {_money(starting_balance)}</div></div>
  <div class="tile"><div class="label">Closed trades</div><div class="value">{s['trades']}</div>
    <div class="sub">Win rate {win_rate}</div></div>
  <div class="tile"><div class="label">Biggest drop from peak</div><div class="value">{s['max_dd']:.1f}%</div>
    <div class="sub">Agent shuts down at 25%</div></div>
  <div class="tile"><div class="label">Best trade</div><div class="value">{_money(s['best'], True)}</div>
    <div class="sub">Worst: {_money(s['worst'], True)}</div></div>
  <div class="tile"><div class="label">Open position</div><div class="value" style="font-size:16px;margin-top:8px">{html.escape(position)}</div></div>
</section>

<section class="card">
  <h2>Account balance over time</h2>
  <p>Each point is a trade opening or closing. The dashed line is your starting balance.</p>
  <div class="chart" id="chart"><svg id="svg" role="img" aria-label="Account balance after each trade"></svg><div class="tip" id="tip"></div></div>
</section>

<section class="card">
  <h2>Recent trades</h2>
  <p>Last 25 closed trades, newest first.</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Time</th><th>Side</th><th class=num>Exit price</th><th>Exit reason</th><th class=num>Profit / loss</th><th class=num>Balance after</th></tr></thead>
    <tbody>{table}</tbody>
  </table></div>
</section>
<footer>Educational paper-trading project, not financial advice.</footer>
</main>

<script>
const DATA = {data_json};
const START = {starting_balance};
const svg = document.getElementById("svg"), tip = document.getElementById("tip"), box = document.getElementById("chart");
const NS = "http://www.w3.org/2000/svg";
const el = (n, a) => {{ const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); return e; }};
const fmt = v => "$" + v.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});

function draw() {{
  svg.innerHTML = "";
  const W = svg.clientWidth, H = svg.clientHeight, L = 56, R = 12, T = 10, B = 24;
  const vals = DATA.map(d => d.v);
  let lo = Math.min(START, ...vals), hi = Math.max(START, ...vals);
  const pad = Math.max((hi - lo) * 0.1, 0.5); lo -= pad; hi += pad;
  const x = i => L + (DATA.length < 2 ? 0 : i * (W - L - R) / (DATA.length - 1));
  const y = v => T + (hi - v) * (H - T - B) / (hi - lo);

  for (let k = 0; k <= 4; k++) {{
    const v = lo + (hi - lo) * k / 4, yy = y(v);
    svg.append(el("line", {{x1: L, x2: W - R, y1: yy, y2: yy, stroke: "var(--grid)", "stroke-width": 1}}));
    const t = el("text", {{x: L - 8, y: yy + 4, "text-anchor": "end", "font-size": 11, fill: "var(--text-muted)"}});
    t.textContent = "$" + v.toFixed(v >= 1000 ? 0 : 2); svg.append(t);
  }}
  const xl = el("text", {{x: W - R, y: H - 4, "text-anchor": "end", "font-size": 11, fill: "var(--text-muted)"}});
  xl.textContent = "Trades →"; svg.append(xl);
  svg.append(el("line", {{x1: L, x2: W - R, y1: y(START), y2: y(START), stroke: "var(--ref)", "stroke-width": 1, "stroke-dasharray": "4 4"}}));

  const d = DATA.map((p, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(p.v).toFixed(1)).join(" ");
  svg.append(el("path", {{d, fill: "none", stroke: "var(--series-1)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round"}}));
  const last = DATA.length - 1;
  svg.append(el("circle", {{cx: x(last), cy: y(DATA[last].v), r: 4, fill: "var(--series-1)", stroke: "var(--surface-1)", "stroke-width": 2}}));

  const cross = el("line", {{y1: T, y2: H - B, stroke: "var(--text-muted)", "stroke-width": 1, opacity: 0}});
  const dot = el("circle", {{r: 5, fill: "var(--series-1)", stroke: "var(--surface-1)", "stroke-width": 2, opacity: 0}});
  svg.append(cross, dot);
  const hit = el("rect", {{x: L, y: 0, width: Math.max(W - L - R, 1), height: H, fill: "transparent"}});
  svg.append(hit);
  const move = ev => {{
    const r = svg.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    const i = Math.max(0, Math.min(last, Math.round((px - L) / ((W - L - R) / Math.max(last, 1)))));
    const cx = x(i), cy = y(DATA[i].v);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("opacity", 1);
    dot.setAttribute("cx", cx); dot.setAttribute("cy", cy); dot.setAttribute("opacity", 1);
    const chg = DATA[i].v - START;
    tip.innerHTML = `<b>${{fmt(DATA[i].v)}}</b><span>${{chg >= 0 ? "+" : "−"}}${{fmt(Math.abs(chg))}} vs start · ${{DATA[i].t}}</span>`;
    tip.style.opacity = 1;
    const tw = tip.offsetWidth;
    tip.style.left = Math.min(Math.max(cx - tw / 2, 0), box.clientWidth - tw) + "px";
    tip.style.top = Math.max(cy - 58, 0) + "px";
  }};
  const leave = () => {{ cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); tip.style.opacity = 0; }};
  hit.addEventListener("mousemove", move); hit.addEventListener("touchmove", move, {{passive: true}});
  hit.addEventListener("mouseleave", leave); hit.addEventListener("touchend", leave);
}}
draw();
addEventListener("resize", draw);
</script>
</body></html>"""


def write_dashboard(log_file: str, out_file: str = "dashboard.html",
                    starting_balance: float | None = None, title: str = "Paper Trading",
                    live: bool = True) -> str:
    start = Config().starting_balance if starting_balance is None else starting_balance
    page = build_html(load_trades(log_file), start, title, live)
    tmp = out_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(tmp, out_file)  # atomic, so the browser never loads a half-written page
    return out_file


if __name__ == "__main__":
    log = sys.argv[1] if len(sys.argv) > 1 else Config().log_file
    out = sys.argv[2] if len(sys.argv) > 2 else "dashboard.html"
    print("Wrote", write_dashboard(log, out))
