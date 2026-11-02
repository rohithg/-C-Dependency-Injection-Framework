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
    if report.get("reviews"):
        lines += ["### Trade review", ""]
        for r in report["reviews"][:12]:
            verdict = "APPROVED" if r["approved"] else "REJECTED"
            lines.append(f"**{verdict}** - {r['name'][:16]} bought ${r['usdc']:,.0f} of *{r['title'][:60]}* [{r['outcome']}] @ {r['price']:.3f} "
                         f"({_hhmm(r['ts'])}) -> {r['result']}")
            lines.append("")
            lines.append("| Check | Value | | Rule |")
            lines.append("|---|---|---|---|")
            for c in r["checks"]:
                lines.append(f"| {c['name']} | {c['value']} | {'ok' if c['ok'] else '**fail**'} | {c['note']} |")
            lines.append("")
        if len(report["reviews"]) > 12:
            lines.append(f"<sub>{len(report['reviews']) - 12} more reviews in state/activity.jsonl</sub>")
            lines.append("")
    if report.get("activity"):
        acts = sorted(report["activity"], key=lambda a: -a["ts"])
        lines += [f"### Wallet activity this run ({len(acts)} trades by watched wallets)",
                  "| Time (UTC) | Wallet | Action | Market | Outcome | Size | Price | What we did |", "|---|---|---|---|---|---|---|---|"]
        for a in acts[:40]:
            lines.append(f"| {_hhmm(a['ts'])} | {a['name'][:14]} | {a['kind']} | {a['title'][:50]} | {a['outcome'][:12]} | ${a['usdc']:,.0f} | {a['price']:.3f} | {a['decision']} |")
        if len(acts) > 40:
            lines.append(f"| ... | | | {len(acts) - 40} more | | | | |")
        lines.append("")
    lines += [f"### Following {len(report['followed'])} wallets" + (" (re-selected this run)" if report.get("reselected") else ""),
              "| Wallet | Copy return (90d, our rules) | Copy max DD | Copied buys | Their record | Biggest market |", "|---|---|---|---|---|---|"]
    for f in report["followed"]:
        top = (f.get("top_markets") or [{}])[0]
        top_s = f"{top['title'][:40]} (${top['volume']:,.0f}" + (f", {top['pnl']:+,.0f})" if top.get("pnl") is not None else ")") if top.get("title") else ""
        lines.append(f"| [{f['name'][:20]}](https://polymarket.com/profile/{f['wallet']}) | {f['copy_return']:+.1%} | {f['max_dd']:.1%} | "
                     f"{f['copied_buys']} | {f.get('profile', '')} | {top_s} |")
    lines.append("")
    lines.append(f"<sub>paper account simulated against live order books; watching {report['watching']} wallets incl. former leaders with open positions. "
                 "'Copy return' is what following this wallet under our rules would have made; 'their record' is what the wallet itself did.</sub>")
    return "\n".join(lines) + "\n"


def _hhmm(ts: int) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%m-%d %H:%M")


def to_text(report: dict, mode: str = "") -> str:
    head = "Polycopy " + report["as_of"][5:10].replace("-", "/")
    if mode and mode != "live":
        head += f" [{mode}]"
    fills = report["fills"]
    buys = sum(1 for f in fills if f["side"] == "BUY")
    sells = sum(1 for f in fills if f["side"] == "SELL")
    res = sum(1 for f in fills if f["side"] == "RESOLVE")
    act = f"{buys} buys, {sells} sells, {res} resolved" if fills else "no fills"
    seen = len(report.get("activity") or [])
    if seen:
        act += f" from {seen} leader trades"
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
