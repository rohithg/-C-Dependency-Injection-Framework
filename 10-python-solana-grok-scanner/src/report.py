"""Markdown / one-line summaries of a cycle (GitHub step summary, daily
notification via the sibling TVM project's channels)."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import sys

ISSUE_TITLE = "Solana token scanner: daily status"


def to_markdown(report: dict, mode: str = "paper") -> str:
    s = report["stats"]
    ret = report["equity"] / report["start_balance"] - 1
    lines = [f"## Solana new-token scanner - {report['as_of']} ({mode})", "",
             f"**Paper equity:** ${report['equity']:,.2f} ({ret:+.1%} since {report['started']}, start ${report['start_balance']:,.0f})  |  "
             f"**Cash:** ${report['balance']:,.2f}  |  **Open:** {len(report['positions'])}  |  **Closed:** {s['closed']} "
             f"(win rate {_pct(s['win_rate'])}, avg win {_pct(s['avg_win_pct'])}, avg loss {_pct(s['avg_loss_pct'])}, "
             f"{s['stop_losses']} stop-losses, {s['rugs']} rugs)  |  **Today's loss:** {report['daily_loss']:.1%}"
             + ("  |  **HALTED for today**" if report.get("halted") else ""), ""]
    if report["buys"] or report["sells"]:
        lines += ["### Trades this run", "| | Token | Size | Price | Result / reason |", "|---|---|---|---|---|"]
        for b in report["buys"]:
            f = b["fill"]
            lines.append(f"| BUY | {b.get('symbol')} | ${f['cost_usd']:.2f} | {f['entry_price']:.3g} (impact {f['impact_at_entry']:.1%}) | {b['reason'][:120]} |")
        for sl in report["sells"]:
            lines.append(f"| SELL | {sl.get('symbol')} | ${sl['proceeds_usd']:.2f} | {sl['exit_price']:.3g} | {sl['pnl_pct']:+.0%} (${sl['pnl_usd']:+.2f}) {sl['reason']} |")
        lines.append("")
    c = report["counts"]
    lines += [f"### Scanned {len(report['scanned'])} new tokens  (checks: {c.get('PASS', 0)} pass / {c.get('FAIL', 0)} fail / {c.get('UNKNOWN', 0)} unknown; {report['errors']} errors)"]
    if report["scanned"]:
        lines += ["| Token | Liquidity | Age | Largest | Top-10 | Mint | Freeze | LP | Rug flags | Grok | Decision |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in report["scanned"][:40]:
            ch = {x["name"]: x for x in r.get("checks", [])}
            g = r.get("grok") or {}
            grok = f"{g['risk']}/10" if g.get("risk") is not None else (g.get("status", "-") if g else "-")
            sym = r.get("symbol") or r["token"][:6]
            lines.append(f"| [{sym}]({r.get('url', '')}) | {_v(ch, 'liquidity')} | {_v(ch, 'pool age')} | {_v(ch, 'largest holder (ex-pool)')} | "
                         f"{_v(ch, 'top-10 holders (ex-pool)')} | {_v(ch, 'mint authority')} | {_v(ch, 'freeze authority')} | {_v(ch, 'LP locked/burned')} | "
                         f"{_v(ch, 'rug signals')} | {grok} | **{r.get('action')}** {r.get('reason', '')[:80]} |")
        lines.append("")
    if report["positions"]:
        lines += ["### Open paper positions", "| Token | Cost | Entry | Last | P&L | Held | Stop / TP |", "|---|---|---|---|---|---|---|"]
        for p in report["positions"]:
            last = p.get("last_price") or p["entry_price"]
            held = (dt.datetime.now(dt.timezone.utc).timestamp() - p["entry_ts"]) / 3600
            lines.append(f"| [{p.get('symbol')}]({p.get('url', '')}) | ${p['cost_usd']:.2f} | {p['entry_price']:.3g} | {last:.3g} | "
                         f"{last / p['entry_price'] - 1:+.0%} | {held:.1f}h | {p['stop']:.3g} / {p['take_profit']:.3g} |")
        lines.append("")
    lines.append("<sub>Paper account only. Fills pay a 1% fee plus order/half-pool-liquidity price impact; a pool that loses its liquidity pays nothing on exit. "
                 "UNKNOWN never counts as PASS. Not financial advice.</sub>")
    return "\n".join(lines) + "\n"


def to_text(report: dict, mode: str = "paper") -> str:
    s = report["stats"]
    ret = report["equity"] / report["start_balance"] - 1
    return (f"Scanner {report['as_of'][5:10].replace('-', '/')}" + ("" if mode == "paper" else f" [{mode}]") +
            f": paper ${report['equity']:,.0f} ({ret:+.1%} since {report['started'][5:]}), {len(report['positions'])} open, "
            f"{s['closed']} closed (win rate {_pct(s['win_rate'])}, {s['rugs']} rugs). This run: {len(report['scanned'])} scanned, "
            f"{len(report['buys'])} buys, {len(report['sells'])} sells." + (" HALTED today (loss cap)." if report.get("halted") else ""))


def _v(ch: dict, name: str) -> str:
    c = ch.get(name)
    if not c:
        return "-"
    mark = {"PASS": "", "FAIL": " **x**", "UNKNOWN": " ?"}[c["status"]]
    return f"{c['value']}{mark}"


def _pct(v) -> str:
    return "-" if v is None else f"{v:.0%}"


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
