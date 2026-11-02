#!/usr/bin/env python3
"""Walk-forward backtest of copying Polymarket's top wallets.

    python run_backtest.py                       # fetch (cached) + report + chart
    python run_backtest.py --start 2026-05-01 --end 2026-11-01 --follow 10
    python run_backtest.py --config my.json --no-plot

Every month: score every screened wallet on the trailing `lookback_days` by
replaying its trades through the copy rules, follow the top `follow_n`, then
replay the next month with real hourly prices, latency, fees and slippage.
Reported alongside: the naive "copy today's leaderboard" portfolio
(survivorship-biased: it knows who ended up on top), cash, and VOO.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import time
import warnings

import pandas as pd

from polycopy.api import PolymarketAPI
from polycopy.backtest import PriceSource, simulate, summarize, format_summary, month_starts
from polycopy.copy import CopyConfig, DEFAULT, Portfolio, LeaderBook
from polycopy.selection import score_wallets, choose, scores_table
from polycopy.universe import build_universe, screen_universe, fetch_history

warnings.filterwarnings("ignore", category=FutureWarning)
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
UNIVERSE_FILE = HERE / "data_cache" / "universe.json"


def ts(d: str) -> int:
    return int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())


def load_universe(api: PolymarketAPI, cfg: CopyConfig, refresh: bool, log) -> list[dict]:
    if UNIVERSE_FILE.exists() and not refresh and time.time() - UNIVERSE_FILE.stat().st_mtime < 86400:
        return json.loads(UNIVERSE_FILE.read_text())["kept"]
    uni = build_universe(api)
    kept, dropped = screen_universe(api, uni, cfg, log=log)
    UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    UNIVERSE_FILE.write_text(json.dumps({"kept": kept, "dropped": dropped, "built_at": int(time.time())}, indent=1))
    return kept


def voo_benchmark(index: pd.DatetimeIndex) -> pd.Series | None:
    """Growth of $1 in VOO over the same days (daily closes forward-filled over weekends)."""
    try:
        sys.path.insert(0, str(HERE.parent / "08-python-paper-trading-strategy"))
        from tvm.data import load_closes
        px = load_closes(["VOO"], start=str(index[0].date() - dt.timedelta(days=7)))["VOO"]
        px = px.reindex(px.index.union(index)).ffill().reindex(index)
        return px / px.iloc[0]
    except Exception as exc:  # offline or sibling project missing
        print(f"(VOO benchmark unavailable: {exc})")
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="JSON overriding CopyConfig fields")
    ap.add_argument("--start", default="2026-05-01", help="first evaluated month (UTC)")
    ap.add_argument("--end", default=None, help="end of evaluation (default: start of today)")
    ap.add_argument("--follow", type=int, help="override follow_n")
    ap.add_argument("--refresh-universe", action="store_true")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    cfg = CopyConfig.from_json(args.config) if args.config else DEFAULT
    if args.follow:
        cfg = CopyConfig(**{**cfg.__dict__, "follow_n": args.follow})
    log = (lambda *_: None) if args.quiet else print
    api = PolymarketAPI(log=lambda m: log("   ", m))

    start_ts = ts(args.start)
    end_ts = ts(args.end) if args.end else int(dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    hist_since = start_ts - cfg.lookback_days * 86400

    wallets = load_universe(api, cfg, args.refresh_universe, log)
    names = {w["wallet"]: w["name"] for w in wallets}
    log(f"{len(wallets)} screened wallets; fetching history since {dt.datetime.fromtimestamp(hist_since, dt.timezone.utc).date()}")
    histories: dict[str, list[dict]] = {}
    for i, w in enumerate(wallets, 1):
        histories[w["wallet"]] = fetch_history(api, w["wallet"], hist_since, end_ts)
        if i % 25 == 0:
            log(f"  {i}/{len(wallets)} wallets, {sum(map(len, histories.values()))} trades, {api.requests_made} requests")
    all_trades = sorted((t for h in histories.values() for t in h), key=lambda t: t["timestamp"])
    log(f"{len(all_trades)} trades from {len(histories)} wallets")

    markets: dict[str, dict] = {}
    prices = PriceSource(api, markets)

    # ---- walk-forward --------------------------------------------------------
    months = month_starts(dt.date.fromtimestamp(start_ts), dt.date.fromtimestamp(end_ts - 1))
    boundaries = months + [end_ts]
    wf_port, wf_leaders = Portfolio(10_000.0), LeaderBook()
    wf_equity, picks, skip_tot = [], [], {}
    for m0, m1 in zip(boundaries[:-1], boundaries[1:]):
        m1 = min(m1, end_ts)
        if m1 <= m0:
            continue
        t0 = time.time()
        scores = score_wallets(histories, names, markets, prices, cfg, m0 - cfg.lookback_days * 86400, m0, api=api)
        chosen = choose(scores, cfg)
        follow = {s.wallet for s in chosen}
        res = simulate(all_trades, markets, prices, cfg, m0, m1, wf_port, wf_leaders, follow=follow, api=api)
        wf_equity.append(res.equity)
        for k, v in res.skipped.items():
            skip_tot[k] = skip_tot.get(k, 0) + v
        month = dt.datetime.fromtimestamp(m0, dt.timezone.utc).strftime("%Y-%m")
        picks.append({"month": month, "scored": len(scores), "followed": [s.name for s in chosen],
                      "copied_buys": res.copied_buys, "equity_end": float(res.equity.iloc[-1]) if len(res.equity) else None})
        log(f"{month}: scored {len(scores)} wallets, following {len(chosen)}: {', '.join(s.name[:12] for s in chosen)}  "
            f"-> {res.copied_buys} buys copied, equity {res.equity.iloc[-1]:,.0f}  ({time.time()-t0:.0f}s, {api.requests_made} req)")
    wf = pd.concat(wf_equity)

    # ---- naive leaderboard copy (biased) -----------------------------------------
    top_now = [w["wallet"] for w in sorted(wallets, key=lambda w: -w["pnl"])[: cfg.follow_n]]
    naive = simulate(all_trades, markets, prices, cfg, start_ts, end_ts, Portfolio(10_000.0), LeaderBook(), follow=set(top_now), api=api)

    # ---- everyone, small size ---------------------------------------------------------
    small = CopyConfig(**{**cfg.__dict__, "trade_fraction": cfg.trade_fraction / 5, "max_market_fraction": cfg.max_market_fraction / 2})
    everyone = simulate(all_trades, markets, prices, small, start_ts, end_ts, Portfolio(10_000.0), LeaderBook(), api=api)

    curves = {"Cash": pd.Series(10_000.0, index=wf.index),
              "Copy: walk-forward top-%d by copyability" % cfg.follow_n: wf,
              "Copy: today's leaderboard top-%d (biased)" % cfg.follow_n: naive.equity.reindex(wf.index).ffill(),
              "Copy: every screened wallet (%.1f%%/trade)" % (small.trade_fraction * 100): everyone.equity.reindex(wf.index).ffill()}
    voo = voo_benchmark(wf.index)
    if voo is not None:
        curves["VOO buy & hold"] = voo * 10_000.0

    # ---- report ---------------------------------------------------------------------
    print(f"\nPolymarket copy trading, {args.start} -> {dt.datetime.fromtimestamp(end_ts, dt.timezone.utc).date()}, "
          f"$10,000 start, {cfg.latency_min} min latency, {cfg.slippage:.2f} slippage, taker fees\n")
    lines = []
    for name, eq in curves.items():
        s = summarize(eq)
        print("  " + format_summary(name, s))
        lines.append(f"| {name} | {s.get('Total', 0):+.1%} | {s.get('CAGR', 0):+.1%} | {s.get('Vol', 0):.1%} | {s.get('Sharpe', float('nan')):.2f} | {s.get('MaxDD', 0):.1%} |")
    wf_fills = [f for f in wf_port.fills]
    buys = [f for f in wf_fills if f.side == "BUY"]
    sells = [f for f in wf_fills if f.side == "SELL"]
    res_f = [f for f in wf_fills if f.side == "RESOLVE"]
    wins = sum(1 for f in res_f if f.price > 0)
    print(f"\n  walk-forward: {len(buys)} buys, {len(sells)} sells, {len(res_f)} resolutions ({wins} won), "
          f"fees paid ${wf_port.fees_paid:,.0f}, realised PnL ${wf_port.realized:,.0f}, open positions {len(wf_port.positions)}")
    print("  skipped leader trades:", ", ".join(f"{k} {v}" for k, v in sorted(skip_tot.items(), key=lambda kv: -kv[1])))
    print("\n  Month by month:")
    for p in picks:
        print(f"   {p['month']}  scored {p['scored']:3d}  copied {p['copied_buys']:4d} buys  equity {p['equity_end']:>9,.0f}  follow: {', '.join(p['followed'])}")
    scores = score_wallets(histories, names, markets, prices, cfg, end_ts - cfg.lookback_days * 86400, end_ts, api=api)
    print("\n  Who we would follow today (trailing %d days):" % cfg.lookback_days)
    print(scores_table(scores, 15).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    RESULTS.mkdir(exist_ok=True)
    md = ["# Polymarket copy-trading walk-forward backtest", "",
          f"{args.start} -> {dt.datetime.fromtimestamp(end_ts, dt.timezone.utc).date()}, $10,000 start, "
          f"{len(wallets)} screened wallets, follow top {cfg.follow_n} re-picked monthly on the trailing {cfg.lookback_days} days, "
          f"{cfg.latency_min} min latency, {cfg.slippage:.2f} slippage per side, Polymarket taker fees, "
          f"{cfg.trade_fraction:.0%} of equity per copied buy (max {cfg.max_market_fraction:.0%} per market).", "",
          "| portfolio | total | CAGR | vol | Sharpe | max DD |", "|---|---|---|---|---|---|", *lines, "",
          f"Walk-forward copy: {len(buys)} buys, {len(sells)} sells, {len(res_f)} resolutions ({wins} paid out), "
          f"fees ${wf_port.fees_paid:,.0f}, realised PnL ${wf_port.realized:,.0f}.", "",
          "Skipped leader trades: " + ", ".join(f"{k} {v}" for k, v in sorted(skip_tot.items(), key=lambda kv: -kv[1])), "",
          "## Followed wallets by month", "", "| month | wallets scored | copied buys | equity at month end | followed |", "|---|---|---|---|---|",
          *[f"| {p['month']} | {p['scored']} | {p['copied_buys']} | {p['equity_end']:,.0f} | {', '.join(p['followed'])} |" for p in picks], "",
          "## Who the rules would follow today", "", md_table(scores_table(scores, 15)), ""]
    (RESULTS / "polymarket_backtest.md").write_text("\n".join(md))
    pd.DataFrame(curves).to_csv(RESULTS / "polymarket_equity.csv")
    json.dump([f.__dict__ for f in wf_fills], open(RESULTS / "polymarket_fills.json", "w"), default=str)
    print(f"\nreport written to {RESULTS / 'polymarket_backtest.md'}")
    if not args.no_plot:
        _plot(curves)


def md_table(df: pd.DataFrame) -> str:
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns)
    return head + "\n" + "\n".join("| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False))


def _plot(curves: dict[str, pd.Series]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 6))
    for name, eq in curves.items():
        ax.plot(eq.index, eq / eq.iloc[0], lw=1.8 if "walk-forward" in name else 1.1, label=name)
    ax.set_ylabel("Growth of $1"); ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Copying Polymarket top wallets, paper, hourly latency, fees and slippage")
    fig.tight_layout()
    fig.savefig(RESULTS / "polymarket_equity.png", dpi=130)
    print(f"chart written to {RESULTS / 'polymarket_equity.png'}")


if __name__ == "__main__":
    main()
