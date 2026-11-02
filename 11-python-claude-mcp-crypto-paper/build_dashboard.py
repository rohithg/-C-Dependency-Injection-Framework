#!/usr/bin/env python3
"""Render dashboard.html from state/: equity curve, fees, biggest drop,
refused orders, every decision with its reason. Static file, no server.

    python build_dashboard.py [--state-dir state] [--out dashboard.html]
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from paperbot.ledger import Ledger  # noqa: E402

CSS = """body{font-family:system-ui,sans-serif;margin:24px;background:#0f1218;color:#e6e8ee;max-width:1100px}
.banner{background:#3b2f0b;color:#ffd666;border:1px solid #806000;border-radius:8px;padding:10px 14px;font-weight:600;margin-bottom:18px}
h1,h2{font-weight:600}.cards{display:flex;gap:14px;flex-wrap:wrap}.card{background:#1a1f2b;border-radius:10px;padding:12px 16px;min-width:150px}
.card b{display:block;font-size:22px}.muted{color:#8a93a6;font-size:13px}table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}
th,td{padding:6px 8px;border-bottom:1px solid #2a3040;text-align:left;vertical-align:top}th{color:#8a93a6;font-weight:500}
.buy{color:#4ade80}.sell_all{color:#60a5fa}.hold{color:#8a93a6}.refused{color:#f87171}.pos{color:#4ade80}.neg{color:#f87171}
svg{background:#1a1f2b;border-radius:10px;margin-top:8px}"""


def equity_svg(points: list[dict], start: float, w=1040, h=240) -> str:
    if len(points) < 2:
        now = points[-1]["equity"] if points else start
        return f"<p class='muted'>Equity chart appears after two rounds (now ${now:.2f}).</p>"
    ys = [p["equity"] for p in points]
    lo, hi = min(ys + [start]), max(ys + [start])
    pad = (hi - lo) * 0.1 or 1.0
    lo, hi = lo - pad, hi + pad
    sx = lambda i: 50 + i * (w - 70) / (len(ys) - 1)
    sy = lambda v: 15 + (hi - v) * (h - 40) / (hi - lo)
    path = " ".join(f"{'M' if i == 0 else 'L'}{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(ys))
    base = sy(start)
    labels = "".join(f"<text x='8' y='{sy(v):.0f}' fill='#8a93a6' font-size='11'>${v:.0f}</text>" for v in (lo + pad, start, hi - pad))
    return (f"<svg width='{w}' height='{h}'>{labels}"
            f"<line x1='50' y1='{base:.1f}' x2='{w - 20}' y2='{base:.1f}' stroke='#3a4152' stroke-dasharray='4 4'/>"
            f"<path d='{path}' fill='none' stroke='{'#4ade80' if ys[-1] >= start else '#f87171'}' stroke-width='2'/>"
            f"<text x='50' y='{h - 8}' fill='#8a93a6' font-size='11'>{html.escape(points[0]['time'])}</text>"
            f"<text x='{w - 20}' y='{h - 8}' fill='#8a93a6' font-size='11' text-anchor='end'>{html.escape(points[-1]['time'])}</text></svg>")


def build(state_dir: Path, out: Path) -> Path:
    led = Ledger(state_dir)
    s, st = led.stats(), led.state
    pos = st["position"]
    rows = []
    for d in reversed(led.decisions()):
        cls = "refused" if d.get("status") == "refused" else d.get("action", "")
        size = f"${d['size_usd']:.2f}" if d.get("size_usd") else ""
        px = f"{d['price']:,.2f}" if d.get("price") else ""
        reason = html.escape(str(d.get("reason", "")))
        if d.get("refused_because"):
            reason += f" <span class='refused'>refused: {html.escape(d['refused_because'])}</span>"
        if d.get("pnl_usd") is not None:
            reason += f" <span class='{'pos' if d['pnl_usd'] >= 0 else 'neg'}'>P&amp;L ${d['pnl_usd']:+.2f} ({d['pnl_pct']:+.1%})</span>"
        rows.append(f"<tr><td>{html.escape(d['time'])}</td><td class='{cls}'>{html.escape(d.get('action', ''))}"
                    f"{' (refused)' if cls == 'refused' else ''}</td><td>{html.escape(str(d.get('symbol') or ''))}</td>"
                    f"<td>{px}</td><td>{size}</td><td>{'$%.2f' % d['fee'] if d.get('fee') else ''}</td><td>{reason}</td></tr>")
    pos_html = "<p class='muted'>none (all cash)</p>"
    if pos:
        pos_html = (f"<p>{pos['symbol']}: {pos['qty']:.6f} bought at ${pos['entry_price']:,.2f} on {pos['entry_time']}, "
                    f"last ${pos.get('last_price', pos['entry_price']):,.2f} "
                    f"(<span class='{'pos' if pos.get('last_price', pos['entry_price']) >= pos['entry_price'] else 'neg'}'>"
                    f"{pos.get('last_price', pos['entry_price']) / pos['entry_price'] - 1:+.2%}</span>)</p>")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>paper crypto experiment</title><style>{CSS}</style></head><body>
<div class="banner">Paper money only. Not financial advice.</div>
<h1>Paper crypto experiment <span class="muted">$100 start, 0.4% fee, one position, 25% max entry, 6 fills/day</span></h1>
<div class="cards">
<div class="card"><span class="muted">Equity</span><b>${s['equity']:.2f}</b><span class="{'pos' if s['return'] >= 0 else 'neg'}">{s['return']:+.2%} since {html.escape(st['started'][:10])}</span></div>
<div class="card"><span class="muted">Fees paid</span><b>${s['fees_paid']:.2f}</b><span class="muted">{s['fills']} fills</span></div>
<div class="card"><span class="muted">Biggest drop</span><b>{s['max_drawdown']:.1%}</b><span class="muted">peak to trough</span></div>
<div class="card"><span class="muted">Orders refused by the gate</span><b>{s['refused']}</b><span class="muted">{s['holds']} holds</span></div>
<div class="card"><span class="muted">Round trips</span><b>{s['round_trips']}</b><span class="muted">{s['wins']} winners</span></div>
</div>
<h2>Equity over time</h2>{equity_svg(st['equity_history'], st['start_equity'])}
<h2>Open position</h2>{pos_html}
<h2>Every decision</h2>
<table><tr><th>Time</th><th>Action</th><th>Symbol</th><th>Price</th><th>Size</th><th>Fee</th><th>Reason</th></tr>{''.join(rows) or '<tr><td colspan=7 class=muted>no rounds yet</td></tr>'}</table>
<p class="muted">Fills at Kraken's last public trade price; no exchange account exists. Generated by build_dashboard.py.</p>
</body></html>"""
    out.write_text(page)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", default=str(ROOT / "state"))
    ap.add_argument("--out", default=str(ROOT / "dashboard.html"))
    a = ap.parse_args()
    print(build(Path(a.state_dir), Path(a.out)))
