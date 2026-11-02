"""Hourly paper copy-trader. Polymarket has no paper-trading mode, so the
account is simulated here: fills walk the live order book (so size and
spread are real), fees follow the market's fee schedule, positions are marked
at CLOB midpoints and paid out when the market resolves.

State lives in one JSON file (plus an append-only fills log) and is rebuilt
nothing from the network, so the GitHub Actions job can restore it from the
log branch, run, and commit it back.
"""
from __future__ import annotations

from dataclasses import asdict
import datetime as dt
import json
from pathlib import Path
import time

from .api import PolymarketAPI
from .backtest import PriceSource, resolution_payout
from .copy import CopyConfig, Portfolio, LeaderBook, copy_trade, precheck, fill_from_book, Fill
from .selection import score_wallets, choose, WalletScore
from .universe import build_universe, screen_universe, fetch_history

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
MAX_COPY_AGE_H = 3.0          # a leader trade older than this when we first see it is a miss, not a copy


class PaperState:
    def __init__(self, path: Path, start_cash: float):
        self.path = path
        if path.exists():
            raw = json.loads(path.read_text())
        else:
            raw = {}
        self.portfolio = Portfolio.from_dict(raw["portfolio"]) if "portfolio" in raw else Portfolio(start_cash)
        self.start_cash = raw.get("start_cash", start_cash)
        self.started = raw.get("started") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        self.followed: list[dict] = raw.get("followed", [])
        self.cursor: dict[str, int] = raw.get("cursor", {})
        self.selected_at: int = raw.get("selected_at", 0)
        self.equity_history: list[list] = raw.get("equity_history", [])
        self.leaders = LeaderBook()
        self.leaders.shares = {tuple(k.split("|")): v for k, v in raw.get("leaders", {}).items()}
        self.last_notified: str = raw.get("last_notified", "")
        self.skipped: dict[str, int] = raw.get("skipped", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "portfolio": self.portfolio.to_dict(), "start_cash": self.start_cash, "started": self.started,
            "followed": self.followed, "cursor": self.cursor, "selected_at": self.selected_at,
            "equity_history": self.equity_history[-24 * 400:],
            "leaders": {"|".join(k): v for k, v in self.leaders.shares.items() if v > 0},
            "last_notified": self.last_notified, "skipped": self.skipped,
        }, indent=1))


def select_followed(api: PolymarketAPI, cfg: CopyConfig, log=print) -> list[dict]:
    """Full re-selection: leaderboards -> bot/dormancy screen -> trailing copy score -> top N."""
    now = int(time.time())
    kept, _ = screen_universe(api, build_universe(api), cfg, log=log)
    since = now - cfg.lookback_days * 86400
    histories = {w["wallet"]: fetch_history(api, w["wallet"], since, now) for w in kept}
    names = {w["wallet"]: w["name"] for w in kept}
    markets: dict[str, dict] = {}
    scores = score_wallets(histories, names, markets, PriceSource(api, markets), cfg, since, now, api=api, log=log)
    chosen = choose(scores, cfg)
    log(f"selected {len(chosen)} of {len(scores)} scored wallets")
    return [{"wallet": s.wallet, "name": s.name, "copy_return": round(s.copy_return, 4), "max_dd": round(s.max_dd, 4),
             "copied_buys": s.copied_buys, "since": now} for s in chosen]


def run_once(api: PolymarketAPI, cfg: CopyConfig, state_dir: Path = STATE_DIR, *, start_cash: float = 10_000.0,
             reselect: bool = False, dry_run: bool = False, now: int | None = None, log=print) -> dict:
    now = now or int(time.time())
    state = PaperState(state_dir / "state.json", start_cash)
    port = state.portfolio
    report: dict = {"as_of": dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "fills": [], "skipped": {}, "reselected": False}

    # ---- who to follow -----------------------------------------------------------------
    if reselect or not state.followed or now - state.selected_at > cfg.rebalance_days * 86400:
        state.followed = select_followed(api, cfg, log)
        state.selected_at = now
        report["reselected"] = True
        for f in state.followed:
            state.cursor.setdefault(f["wallet"], now - 3600)   # start copying from now, not their past
    followed = {f["wallet"] for f in state.followed}
    watching = followed | {w for p in port.positions.values() for w, s in p.by_wallet.items() if s > 0}

    # ---- pull new leader trades and mirror them ---------------------------------------
    markets: dict[str, dict] = {}
    books: dict[str, dict | None] = {}

    def book(token: str):
        if token not in books:
            books[token] = api.book(token)
        return books[token]

    def exec_price(token: str, side: str, ts: int, leader_price: float) -> float | None:
        b = book(token)
        if side == "BUY":
            budget = min(cfg.trade_fraction * port.last_equity, port.cash)
            got = fill_from_book(b, "BUY", notional=budget)
        else:
            pos = port.positions.get(token)
            got = fill_from_book(b, "SELL", shares=pos.shares if pos else 0.0) if pos else None
        return got[1] if got else None

    for wallet in sorted(watching):
        since = state.cursor.get(wallet, now - 3600)
        try:
            trades = sorted(api.activity(wallet, since + 1, now + 1), key=lambda t: t["timestamp"])
        except Exception as exc:
            log(f"activity fetch failed for {wallet[:8]}: {exc}")
            continue
        for tr in trades:
            tr["proxyWallet"] = tr["proxyWallet"].lower()
            state.cursor[wallet] = max(state.cursor.get(wallet, 0), int(tr["timestamp"]))
            if wallet not in followed and tr["side"] == "BUY":
                state.leaders.apply(tr); continue
            if tr["side"] == "SELL" and tr["asset"] not in port.positions:
                state.leaders.apply(tr); continue
            if now - tr["timestamp"] > MAX_COPY_AGE_H * 3600:
                state.leaders.apply(tr); _count(report, state, "stale"); continue
            why = precheck(tr, cfg)
            if why:
                state.leaders.apply(tr); _count(report, state, why); continue
            m = markets.get(tr["conditionId"])
            if m is None:
                m = markets[tr["conditionId"]] = api.market(tr["conditionId"])
            frac = None
            if tr["side"] == "SELL":
                remaining = api.position(wallet, tr["conditionId"]).get(tr["asset"], 0.0)
                frac = min(1.0, float(tr["size"]) / (float(tr["size"]) + remaining)) if remaining >= 0 else 1.0
            fill, why = copy_trade(tr, m, port, state.leaders, cfg, exec_price, fraction_override=frac)
            if fill:
                fill.note = f"leader {tr['proxyWallet'][:8]} @ {float(tr['price']):.3f}"
                report["fills"].append(asdict(fill))
                log(f"{fill.side} {fill.shares:.1f} x {fill.price:.3f} {fill.title[:50]} [{fill.outcome}] copying {wallet[:8]}")
            else:
                _count(report, state, why)
        if not trades:
            state.cursor[wallet] = max(state.cursor.get(wallet, 0), now - 3600)

    # ---- mark, resolve ---------------------------------------------------------------
    mids = api.midpoints([t for t in port.positions])
    for token, pos in list(port.positions.items()):
        m = markets.get(pos.condition_id) or api.market(pos.condition_id)
        payout = resolution_payout(m or {}, token)
        if payout is not None:
            f = port.resolve(token, payout, now)
            if f:
                report["fills"].append(asdict(f))
                log(f"RESOLVED {f.title[:50]} [{f.outcome}] -> {payout:.0f} on {f.shares:.1f} shares")
    equity = port.value(lambda tok: mids.get(tok))
    state.equity_history.append([report["as_of"], round(equity, 2)])

    report.update({
        "equity": round(equity, 2), "cash": round(port.cash, 2), "start_cash": state.start_cash, "started": state.started,
        "return": equity / state.start_cash - 1, "realized": round(port.realized, 2), "fees_paid": round(port.fees_paid, 2),
        "followed": state.followed, "watching": len(watching),
        "positions": [{"title": p.title, "outcome": p.outcome, "shares": round(p.shares, 2), "cost": round(p.cost, 2),
                       "mark": mids.get(t), "value": round(p.shares * mids[t], 2) if t in mids else None,
                       "end": dt.datetime.fromtimestamp(p.end_ts, dt.timezone.utc).strftime("%Y-%m-%d") if p.end_ts else "",
                       "leaders": sorted(p.by_wallet, key=p.by_wallet.get, reverse=True)[:2]} for t, p in port.positions.items()],
        "max_dd": _max_dd([e for _, e in state.equity_history]),
        "dry_run": dry_run,
    })
    if not dry_run:
        state.save()
        with (state_dir / "fills.jsonl").open("a") as f:
            for fl in report["fills"]:
                f.write(json.dumps({"run": report["as_of"], **fl}, default=str) + "\n")
    report["_state"] = state
    return report


def _count(report: dict, state: PaperState, why: str) -> None:
    key = why.split(" in ")[0] if why.startswith("ends in") else ("price out of range" if why.startswith("price ") else why)
    report["skipped"][key] = report["skipped"].get(key, 0) + 1
    state.skipped[key] = state.skipped.get(key, 0) + 1


def _max_dd(values: list[float]) -> float:
    peak, dd = float("-inf"), 0.0
    for v in values:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1 if peak > 0 else 0.0)
    return dd
