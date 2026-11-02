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

from .analysis import wallet_profile, profile_line
from .api import PolymarketAPI
from .backtest import PriceSource, resolution_payout
from .copy import CopyConfig, Portfolio, LeaderBook, copy_trade, precheck, fill_from_book, Fill
from .review import review_buy, review_to_dict
from .selection import score_wallets, choose, WalletScore
from .universe import build_universe, screen_universe, fetch_history

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
MAX_COPY_AGE_H = 3.0          # a leader trade older than this when we first see it is a miss, not a copy
ACTIVITY_KEEP = 300           # recent watched-wallet events kept in state for the report


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
        self.activity: list[dict] = raw.get("activity", [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "portfolio": self.portfolio.to_dict(), "start_cash": self.start_cash, "started": self.started,
            "followed": self.followed, "cursor": self.cursor, "selected_at": self.selected_at,
            "equity_history": self.equity_history[-24 * 400:],
            "leaders": {"|".join(k): v for k, v in self.leaders.shares.items() if v > 0},
            "last_notified": self.last_notified, "skipped": self.skipped,
            "activity": self.activity[-ACTIVITY_KEEP:],
        }, indent=1))


def select_followed(api: PolymarketAPI, cfg: CopyConfig, log=print) -> list[dict]:
    """Full re-selection: leaderboards -> bot/dormancy screen -> trailing copy score -> top N,
    each with a descriptive profile (win rate, sizing, favourite markets)."""
    now = int(time.time())
    kept, _ = screen_universe(api, build_universe(api), cfg, log=log)
    since = now - cfg.lookback_days * 86400
    histories = {w["wallet"]: fetch_history(api, w["wallet"], since, now) for w in kept}
    names = {w["wallet"]: w["name"] for w in kept}
    markets: dict[str, dict] = {}
    scores = score_wallets(histories, names, markets, PriceSource(api, markets), cfg, since, now, api=api, log=log)
    chosen = choose(scores, cfg)
    log(f"selected {len(chosen)} of {len(scores)} scored wallets")
    out = []
    for s in chosen:
        stats = wallet_profile(api, histories[s.wallet], markets)
        out.append({"wallet": s.wallet, "name": s.name, "copy_return": round(s.copy_return, 4), "max_dd": round(s.max_dd, 4),
                    "copied_buys": s.copied_buys, "since": now, "profile": profile_line(stats),
                    "stats": {k: v for k, v in stats.items() if k not in ("top_markets",)},
                    "top_markets": [{"title": r["title"], "volume": round(r["volume"]), "pnl": None if r["pnl"] is None else round(r["pnl"])}
                                    for r in stats.get("top_markets", [])[:3]]})
    return out



def run_once(api: PolymarketAPI, cfg: CopyConfig, state_dir: Path = STATE_DIR, *, start_cash: float = 10_000.0,
             reselect: bool = False, dry_run: bool = False, now: int | None = None, log=print) -> dict:
    now = now or int(time.time())
    state = PaperState(state_dir / "state.json", start_cash)
    port = state.portfolio
    report: dict = {"as_of": dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "fills": [], "skipped": {}, "reselected": False, "activity": [], "reviews": []}

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

    names = {f["wallet"]: f["name"] for f in state.followed}

    def classify(tr: dict) -> str:
        """new position / added / reduced / closed, judged before the trade is applied to LeaderBook."""
        had = state.leaders.shares.get((tr["proxyWallet"], tr["asset"]), 0.0)
        if tr["side"] == "BUY":
            return "new position" if had <= 1e-6 else "added"
        return "closed" if had - float(tr.get("size", 0) or 0) <= 1e-6 else "reduced"

    def event(tr: dict, decision: str) -> None:
        """Activity-monitor entry: what the watched wallet did and what we did about it."""
        report["activity"].append({
            "ts": int(tr["timestamp"]), "wallet": tr["proxyWallet"], "name": names.get(tr["proxyWallet"], tr["proxyWallet"][:8]),
            "kind": tr["_kind"], "side": tr["side"], "title": tr.get("title", ""), "outcome": tr.get("outcome", ""),
            "usdc": round(float(tr.get("usdcSize", 0) or 0), 2), "price": float(tr["price"]), "decision": decision})

    def skip(tr: dict, why: str, review: dict | None = None) -> None:
        event(tr, f"skipped: {why}")
        state.leaders.apply(tr)
        _count(report, state, why)
        if review:
            report["reviews"].append(review)

    for wallet in sorted(watching):
        since = state.cursor.get(wallet, now - 3600)
        try:
            trades = sorted(api.activity(wallet, since + 1, now + 1), key=lambda t: t["timestamp"])
        except Exception as exc:
            log(f"activity fetch failed for {wallet[:8]}: {exc}")
            continue
        for tr in trades:
            tr["proxyWallet"] = tr["proxyWallet"].lower()
            tr["_kind"] = classify(tr)
            state.cursor[wallet] = max(state.cursor.get(wallet, 0), int(tr["timestamp"]))
            if wallet not in followed and tr["side"] == "BUY":
                event(tr, "not followed"); state.leaders.apply(tr); continue
            if tr["side"] == "SELL" and tr["asset"] not in port.positions:
                event(tr, "not holding"); state.leaders.apply(tr); continue
            if now - tr["timestamp"] > MAX_COPY_AGE_H * 3600:
                skip(tr, "stale"); continue
            why = precheck(tr, cfg)
            if why:
                skip(tr, why); continue
            m = markets.get(tr["conditionId"])
            if m is None:
                m = markets[tr["conditionId"]] = api.market(tr["conditionId"])
            frac = None
            if tr["side"] == "BUY":
                approved, checks = review_buy(tr, m, book(tr["asset"]), cfg, port, now, MAX_COPY_AGE_H)
                if not approved:
                    failed = [c for c in checks if not c.ok]
                    why = failed[0].name + (f" {failed[0].value}" if failed[0].value else "")
                    skip(tr, why, review_to_dict(tr, m, False, checks, "rejected: " + ", ".join(c.name for c in failed)))
                    continue
            else:
                remaining = api.position(wallet, tr["conditionId"]).get(tr["asset"], 0.0)
                frac = min(1.0, float(tr["size"]) / (float(tr["size"]) + remaining)) if remaining >= 0 else 1.0
            fill, why = copy_trade(tr, m, port, state.leaders, cfg, exec_price, fraction_override=frac)
            if fill:
                fill.note = f"leader {tr['proxyWallet'][:8]} @ {float(tr['price']):.3f}"
                report["fills"].append(asdict(fill))
                event(tr, f"copied {fill.shares:.0f} @ {fill.price:.3f}")
                if tr["side"] == "BUY":
                    report["reviews"].append(review_to_dict(tr, m, True, checks, f"copied {fill.shares:.0f} shares @ {fill.price:.3f}"))
                log(f"{fill.side} {fill.shares:.1f} x {fill.price:.3f} {fill.title[:50]} [{fill.outcome}] copying {wallet[:8]}")
            else:
                event(tr, f"skipped: {why}")
                _count(report, state, why)
                if tr["side"] == "BUY":
                    report["reviews"].append(review_to_dict(tr, m, True, checks, "approved but not filled: " + why))
        if not trades:
            state.cursor[wallet] = max(state.cursor.get(wallet, 0), now - 3600)
    state.activity = (state.activity + report["activity"])[-ACTIVITY_KEEP:]

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
        with (state_dir / "activity.jsonl").open("a") as f:     # the activity monitor + every trade review, forever
            for a in report["activity"]:
                f.write(json.dumps({"run": report["as_of"], "type": "activity", **a}) + "\n")
            for r in report["reviews"]:
                f.write(json.dumps({"run": report["as_of"], "type": "review", **r}) + "\n")
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
