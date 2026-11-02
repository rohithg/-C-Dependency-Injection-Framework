"""Turn today's TVM signal into broker orders.

Designed to be run once per trading day, ideally in the last ~10 minutes of
the session so the regime check sees a near-final close. Running after the
close works too; orders then fill at the next open.

State handling: the (asset, exposure) part of the state is rebuilt from live
positions every run, so the trader self-heals if an order failed or someone
touched the account. Only `days_held` (needed for the min-hold rule) is
persisted locally; if the file is missing we assume the hold period has
elapsed, which is the conservative choice (lets the signal re-pick).
"""
from __future__ import annotations

from dataclasses import asdict
import datetime as dt
import json
from pathlib import Path

import pandas as pd

from .broker import Broker, Order, Account
from .config import TVMConfig, DEFAULT
from .strategy import State, compute_signals, step, target_weights, exposure_from_weights, HOLD_UNKNOWN

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
MIN_ORDER_NOTIONAL = 5.0        # ignore dust rebalances below this (USD)
MIN_ORDER_FRACTION = 0.002      # ...or below 0.2% of equity


def load_days_held(path: Path) -> tuple[int, str | None, str | None]:
    if not path.exists():
        return HOLD_UNKNOWN, None, None
    raw = json.loads(path.read_text())
    return int(raw.get("days_held", HOLD_UNKNOWN)), raw.get("asset"), raw.get("as_of")


def save_state(path: Path, state: State, as_of: pd.Timestamp) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**asdict(state), "as_of": str(as_of.date())}, indent=2))


def reconstruct_state(acct: Account, cfg: TVMConfig, days_held: int, saved_asset: str | None) -> State:
    asset, exposure = exposure_from_weights(acct.weights(), cfg)
    if exposure == 0 and saved_asset in cfg.risk_assets:
        asset = saved_asset
    if saved_asset is not None and saved_asset != asset:
        days_held = HOLD_UNKNOWN   # positions changed under us; let the signal re-pick
    return State(asset=asset, exposure=round(exposure, 4), days_held=days_held, risk_on=exposure > 0)


def latest_signal_row(closes: pd.DataFrame, cfg: TVMConfig, live_prices: dict[str, float] | None) -> tuple[pd.Series, pd.Timestamp]:
    """Signals for 'today'. If live prices are supplied and today's bar is not
    in `closes` yet, append it so the SMA / vol / momentum reflect the
    near-close level."""
    px = closes.copy()
    today = pd.Timestamp(dt.date.today())
    if live_prices and px.index[-1].normalize() < today:
        row = {s: live_prices.get(s, px[s].iloc[-1]) for s in px.columns}
        px.loc[today] = row
    sig = compute_signals(px, cfg)
    return sig.iloc[-1], sig.index[-1]


def plan_orders(acct: Account, weights: dict[str, float], all_symbols: set[str]) -> list[Order]:
    """Diff target weights against current positions. Sells first."""
    orders: list[Order] = []
    threshold = max(MIN_ORDER_NOTIONAL, MIN_ORDER_FRACTION * acct.equity)
    targets = {s: weights.get(s, 0.0) * acct.equity for s in all_symbols | set(acct.positions)}
    for sym, target in targets.items():
        current = acct.positions.get(sym, 0.0)
        diff = target - current
        if target <= 0 and current > 0:
            orders.append(Order(sym, -current, liquidate=True))
        elif abs(diff) >= threshold:
            orders.append(Order(sym, diff))
    orders.sort(key=lambda o: o.notional)   # most negative (sells) first
    return orders


def run_once(broker: Broker, closes: pd.DataFrame, cfg: TVMConfig = DEFAULT, *, dry_run: bool = False,
             use_live_prices: bool = True, state_dir: Path = STATE_DIR, force: bool = False,
             log=print) -> dict:
    state_path = state_dir / "tvm_state.json"
    acct = broker.account()
    days_held, saved_asset, saved_as_of = load_days_held(state_path)

    live = None
    if use_live_prices and broker.market_is_open():
        live = {s: p for s in {cfg.trend_symbol, *cfg.risk_assets} if (p := broker.latest_price(s))}
    row, as_of = latest_signal_row(closes, cfg, live)

    # Re-running on the same signal date must not advance the hold counter.
    if saved_as_of == str(as_of.date()) and days_held < HOLD_UNKNOWN:
        days_held -= 1
    state = reconstruct_state(acct, cfg, days_held, saved_asset)

    new_state, traded = step(state, row, cfg)
    weights = target_weights(new_state, cfg)
    tradable = {cfg.cash_symbol, *cfg.risk_assets, *cfg.leveraged_2x.values()}
    orders = plan_orders(acct, weights, tradable) if (traded or force) else []

    report = {
        "as_of": str(as_of.date()), "equity": round(acct.equity, 2),
        "signal": {"risk_on": bool(row["risk_on"]), "realized_vol": round(float(row["realized_vol"]), 4),
                   "exposure_target": round(float(row["exposure_target"]), 3),
                   **{k: round(float(v), 4) for k, v in row.items() if k.startswith("mom_")}},
        "state_before": asdict(state), "state_after": asdict(new_state),
        "target_weights": weights, "current_weights": {k: round(v, 4) for k, v in acct.weights().items()},
        "orders": [asdict(o) for o in orders], "dry_run": dry_run, "live_prices_used": bool(live),
    }
    log(json.dumps(report, indent=2, default=str))

    if orders and not dry_run:
        broker.cancel_open_orders()
        results = []
        for o in orders:
            res = broker.submit(o)
            status = res.get("status", res) if isinstance(res, dict) else res
            results.append(str(status))
            log(f"submitted {o.symbol} {'LIQUIDATE' if o.liquidate else f'{o.notional:+.2f} USD'} -> {status}")
        report["order_results"] = results
    if not dry_run:
        save_state(state_path, new_state, as_of)
        _append_log(state_dir / "trade_log.jsonl", report)
    return report


def _append_log(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"ts": dt.datetime.now(dt.timezone.utc).isoformat(), **report}, default=str) + "\n")
