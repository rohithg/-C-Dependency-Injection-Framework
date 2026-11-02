"""Single-page local dashboard (Flask): paper balance, open positions, last 50
decisions, pass/fail counts. Read-only; it only renders data/ and logs/.

    python src/main.py --dashboard      -> http://localhost:8000
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
from pathlib import Path

from pipeline import DATA, LOGS, DecisionLog, load_config
from paper import PaperTrader

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>grok-trader paper dashboard</title>
<meta http-equiv="refresh" content="60">
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#0f1218;color:#e6e8ee}}
h1,h2{{font-weight:600}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card{{background:#1a1f2b;border-radius:10px;padding:14px 18px;min-width:160px}}
.card b{{display:block;font-size:22px}}.muted{{color:#8a93a6;font-size:13px}}table{{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}}
th,td{{padding:6px 8px;border-bottom:1px solid #2a3040;text-align:left;vertical-align:top}}th{{color:#8a93a6;font-weight:500}}
.BUY{{color:#4ade80}}.SKIP{{color:#8a93a6}}.SELL{{color:#60a5fa}}.ERROR{{color:#f87171}}.pos{{color:#4ade80}}.neg{{color:#f87171}}</style></head><body>
<h1>grok-trader <span class="muted">paper mode, refreshes every minute</span></h1>
<div class="cards">
<div class="card"><span class="muted">Paper equity</span><b>${equity:,.2f}</b><span class="muted">{ret:+.1%} since {started}</span></div>
<div class="card"><span class="muted">Cash</span><b>${balance:,.2f}</b></div>
<div class="card"><span class="muted">Open positions</span><b>{n_open}</b></div>
<div class="card"><span class="muted">Closed trades</span><b>{closed}</b><span class="muted">win rate {win_rate}, {rugs} rugs, {stops} stop-losses</span></div>
<div class="card"><span class="muted">Checks (all time in log)</span><b>{npass} / {nfail} / {nunk}</b><span class="muted">pass / fail / unknown</span></div>
<div class="card"><span class="muted">Decisions</span><b>{nbuy} buys</b><span class="muted">{nskip} skips, {nerr} errors</span></div>
</div>
<h2>Open positions</h2>{positions}
<h2>Last 50 decisions</h2>{decisions}
<p class="muted">Paper account only; no wallet exists. Fills include a 1% fee and order-size / half-pool-liquidity price impact. UNKNOWN never counts as PASS. Not financial advice.</p>
</body></html>"""


def render() -> str:
    cfg = load_config()
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    data_dir = Path(os.environ.get("SCANNER_DATA_DIR") or DATA)
    log_dir = Path(os.environ.get("SCANNER_LOG_DIR") or LOGS)
    trader = PaperTrader(data_dir / "paper_state.json", cfg, now)
    s = trader.stats()
    rows = DecisionLog(log_dir / "decisions.jsonl").tail(2000)
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    actions = {"BUY": 0, "SKIP": 0, "ERROR": 0}
    for r in rows:
        for c in r.get("checks", []):
            counts[c["status"]] = counts.get(c["status"], 0) + 1
        if r.get("type") == "decision":
            actions[r.get("action", "SKIP")] = actions.get(r.get("action", "SKIP"), 0) + 1
    pos_html = "<p class='muted'>none</p>"
    if trader.positions:
        pos_html = "<table><tr><th>Token</th><th>Cost</th><th>Entry</th><th>Last</th><th>P&L</th><th>Held</th><th>Stop / TP</th></tr>"
        for tok, p in trader.positions.items():
            last = p.get("last_price") or p["entry_price"]
            pnl = last / p["entry_price"] - 1
            pos_html += (f"<tr><td><a href='{html.escape(p.get('url') or '#')}' style='color:#60a5fa'>{html.escape(str(p.get('symbol')))}</a></td>"
                         f"<td>${p['cost_usd']:.2f}</td><td>{p['entry_price']:.3g}</td><td>{last:.3g}</td>"
                         f"<td class='{'pos' if pnl >= 0 else 'neg'}'>{pnl:+.0%}</td><td>{(now - p['entry_ts']) / 3600:.1f}h</td>"
                         f"<td>{p['stop']:.3g} / {p['take_profit']:.3g}</td></tr>")
        pos_html += "</table>"
    dec_html = "<table><tr><th>Time</th><th>Type</th><th>Token</th><th>Checks</th><th>Grok</th><th>Decision / reason</th></tr>"
    for r in reversed(rows[-50:]):
        if r.get("type") == "sell":
            dec_html += (f"<tr><td>{html.escape(r['ts'])}</td><td class='SELL'>SELL</td><td>{html.escape(str(r.get('symbol')))}</td><td></td><td></td>"
                         f"<td>{r['pnl_pct']:+.0%} (${r['pnl_usd']:+.2f}) {html.escape(r['reason'])}</td></tr>")
            continue
        checks = " ".join(f"<span class='{c['status']}' title='{html.escape(c['name'])}: {html.escape(c['value'])}'>"
                          f"{'&#10003;' if c['status'] == 'PASS' else ('&#10007;' if c['status'] == 'FAIL' else '?')}</span>" for c in r.get("checks", []))
        g = r.get("grok") or {}
        grok = f"{g['risk']}/10" if g.get("risk") is not None else html.escape(g.get("status", "-")) if g else "-"
        dec_html += (f"<tr><td>{html.escape(r['ts'])}</td><td class='{r.get('action')}'>{html.escape(str(r.get('action')))}</td>"
                     f"<td><a href='{html.escape(r.get('url') or '#')}' style='color:#60a5fa'>{html.escape(str(r.get('symbol') or r['token'][:8]))}</a></td>"
                     f"<td>{checks}</td><td>{grok}</td><td>{html.escape(str(r.get('reason', ''))[:160])}</td></tr>")
    dec_html += "</table>"
    return PAGE.format(equity=trader.equity(), ret=trader.equity() / trader.start_balance - 1, started=trader.started, balance=trader.balance,
                       n_open=len(trader.positions), closed=s["closed"], win_rate="-" if s["win_rate"] is None else f"{s['win_rate']:.0%}",
                       rugs=s["rugs"], stops=s["stop_losses"], npass=counts["PASS"], nfail=counts["FAIL"], nunk=counts["UNKNOWN"],
                       nbuy=actions["BUY"], nskip=actions["SKIP"], nerr=actions["ERROR"], positions=pos_html, decisions=dec_html)


def serve(port: int = 8000) -> None:
    from flask import Flask, Response
    app = Flask("grok-trader")
    app.add_url_rule("/", "index", lambda: Response(render(), mimetype="text/html"))
    print(f"dashboard: http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
