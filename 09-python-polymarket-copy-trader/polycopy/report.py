"""Markdown run summary, one-line text status, and notification plumbing.

Notifications reuse the channels of the sibling TVM project (GitHub issue
comment with @mention by default; Twilio / email-to-SMS / ntfy / Telegram if
their secrets are set) by importing `tvm.notify` from
../08-python-paper-trading-strategy.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

ISSUE_TITLE = "Polymarket copy trading: daily status"


def to_markdown(report: dict, mode: str = "") -> str:
    lines = [f"## Polymarket copy trading - {report['as_of']}" + (f" ({mode})" if mode else ""), "",
             f"**Equity:** ${report['equity']:,.2f} ({report['return']:+.2%} since {report['started']}, start ${report['start_cash']:,.0f})  |  "
             f"**Cash:** ${report['cash']:,.0f}  |  **Realised P&L:** ${report['realized']:+,.0f}  |  **Fees paid:** ${report['fees_paid']:,.0f}  |  "
             f"**Max DD:** {report['max_dd']:.1%}", ""]
    if report["fills"]:
        lines += ["### Fills this run", "| Side | Market | Outcome | Shares | Price | Fee | Copying |", "|---|---|---|---|---|---|---|"]
        for f in report["fills"]:
            lines.append(f"| {f['side']} | {f['title'][:60]} | {f['outcome']} | {f['shares']:.1f} | {f['price']:.3f} | {f['fee']:.2f} | {f.get('note', '')} |")
        lines.append("")
    else:
        lines += ["### No fills this run", ""]
    if report["skipped"]:
        lines.append("<sub>leader trades not copied: " + ", ".join(f"{k} x{v}" for k, v in sorted(report["skipped"].items(), key=lambda kv: -kv[1])) + "</sub>")
        lines.append("")
    lines += [f"### Open positions ({len(report['positions'])})"]
    if report["positions"]:
        lines += ["| Market | Outcome | Shares | Cost | Mark | Value | P&L | Ends | Leaders |", "|---|---|---|---|---|---|---|---|---|"]
        for p in sorted(report["positions"], key=lambda p: -(p["value"] or p["cost"])):
            mark = f"{p['mark']:.3f}" if p["mark"] is not None else "-"
            val = p["value"] if p["value"] is not None else p["cost"]
            lines.append(f"| {p['title'][:60]} | {p['outcome']} | {p['shares']:.1f} | ${p['cost']:,.0f} | {mark} | ${val:,.0f} | "
                         f"{val - p['cost']:+,.0f} | {p['end']} | {', '.join(w[:8] for w in p['leaders'])} |")
    lines.append("")
    lines += [f"### Following {len(report['followed'])} wallets" + (" (re-selected this run)" if report.get("reselected") else ""),
              "| Wallet | Trailing copy return | Max DD | Copied buys |", "|---|---|---|---|"]
    for f in report["followed"]:
        lines.append(f"| [{f['name'][:20]}](https://polymarket.com/profile/{f['wallet']}) | {f['copy_return']:+.1%} | {f['max_dd']:.1%} | {f['copied_buys']} |")
    lines.append("")
    lines.append(f"<sub>paper account simulated against live order books; watching {report['watching']} wallets incl. former leaders with open positions</sub>")
    return "\n".join(lines) + "\n"


def to_text(report: dict, mode: str = "") -> str:
    head = "Polycopy " + report["as_of"][5:10].replace("-", "/")
    if mode and mode != "live":
        head += f" [{mode}]"
    fills = report["fills"]
    buys = sum(1 for f in fills if f["side"] == "BUY")
    sells = sum(1 for f in fills if f["side"] == "SELL")
    res = sum(1 for f in fills if f["side"] == "RESOLVE")
    act = f"{buys} buys, {sells} sells, {res} resolved" if fills else "no fills"
    return (f"{head}: ${report['equity']:,.0f} ({report['return']:+.1%} since {report['started'][5:]}), "
            f"{len(report['positions'])} open positions, following {len(report['followed'])}. Today: {act}. "
            f"Fees ${report['fees_paid']:,.0f}, max DD {report['max_dd']:.1%}.")


def send_all(text: str, markdown: str, log=print) -> dict[str, str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "08-python-paper-trading-strategy"))
    try:
        from tvm.notify import send_all as _send
    except Exception as exc:
        log(f"notifications unavailable ({exc})")
        return {}
    env = dict(os.environ)
    env.setdefault("GITHUB_ISSUE_TITLE", ISSUE_TITLE)
    return _send(text, env=env, log=log, markdown=markdown)


def write_step_summary(markdown: str) -> bool:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return False
    with open(path, "a") as f:
        f.write(markdown)
    return True
