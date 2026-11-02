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
from .adaptive import AdaptiveConfig, latest_allocation, regime_postmortem
from .kronos_signal import KronosConfig

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


def append_live_bar(closes: pd.DataFrame, live_prices: dict[str, float] | None) -> pd.DataFrame:
    """If live prices are supplied and today's bar is not in `closes` yet,
    append it so SMA / vol / momentum reflect the near-close level. Symbols
    without a live quote carry yesterday's close forward."""
    px = closes.copy()
    today = pd.Timestamp(dt.date.today())
    if live_prices and px.index[-1].normalize() < today:
        px.loc[today] = {s: live_prices.get(s, px[s].iloc[-1]) for s in px.columns}
    return px


def latest_signal_row(closes: pd.DataFrame, cfg: TVMConfig, live_prices: dict[str, float] | None) -> tuple[pd.Series, pd.Timestamp]:
    sig = compute_signals(append_live_bar(closes, live_prices), cfg)
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
             adaptive: AdaptiveConfig | None = None, kronos: KronosConfig | None = None,
             bars: dict[str, pd.DataFrame] | None = None, log=print) -> dict:
    """One daily decision.

    adaptive=None, kronos=None  fixed TVM rules
    adaptive=AdaptiveConfig     expert ensemble; trade toward its blended target
                                when it drifts > portfolio_band (L1) from holdings
    kronos=KronosConfig         Kronos candlestick forecaster (`bars` = daily OHLCV
                                per symbol); for rule "tvm-veto" the ensemble
                                supplies the base weights
    """
    state_path = state_dir / "tvm_state.json"
    acct = broker.account()
    days_held, saved_asset, saved_as_of = load_days_held(state_path)
    tradable = {cfg.cash_symbol, *cfg.risk_assets, *cfg.leveraged_2x.values()}

    live = None
    if use_live_prices and broker.market_is_open():
        wanted = tradable | {cfg.trend_symbol} if (adaptive or kronos) else {cfg.trend_symbol, *cfg.risk_assets}
        live = {s: p for s in wanted if s in closes.columns and (p := broker.latest_price(s))}
    px = append_live_bar(closes, live)
    sig = compute_signals(px, cfg)
    row, as_of = sig.iloc[-1], sig.index[-1]

    # Re-running on the same signal date must not advance the hold counter.
    if saved_as_of == str(as_of.date()) and days_held < HOLD_UNKNOWN:
        days_held -= 1
    state = reconstruct_state(acct, cfg, days_held, saved_asset)

    extra: dict = {}
    if adaptive is None and kronos is None:
        new_state, traded = step(state, row, cfg)
        weights = target_weights(new_state, cfg)
    else:
        cash = pd.Series(0.0, index=px.index)          # BIL column supplies the cash return when present
        tvm_weights, board = None, None
        if adaptive is not None or (kronos is not None and kronos.rule == "tvm-veto"):
            acfg = adaptive or AdaptiveConfig(max_leverage=cfg.max_leverage)
            tvm_weights, board = latest_allocation(px, cash, cfg, acfg)
        if kronos is None:
            weights, band = tvm_weights, adaptive.portfolio_band
            extra["mode_detail"] = "adaptive ensemble"
        else:
            weights, kextra = _kronos_decision(broker, bars or {}, as_of, live, kronos, cfg, tvm_weights, state_dir, log)
            band = kronos.portfolio_band
            extra.update(kextra)
        cur = {s: w for s, w in acct.weights().items() if s in tradable}
        dist = sum(abs(weights.get(s, 0.0) - cur.get(s, 0.0)) for s in set(weights) | set(cur))
        traded = dist > band
        asset, _ = exposure_from_weights(weights, cfg)
        lev_syms = set(cfg.leveraged_2x.values())
        exposure = sum(w * (2.0 if s in lev_syms else 1.0) for s, w in weights.items() if s != cfg.cash_symbol)
        new_state = State(asset=asset, exposure=round(exposure, 4), days_held=state.days_held + 1, risk_on=exposure > 0)
        extra["drift_from_target"] = round(dist, 4)
        if board is not None:
            pm = regime_postmortem(px, cfg, last_n=3)
            extra["learner"] = [{"expert": n, "weight": round(float(r.weight), 4), "trailing_1y": round(float(r.trailing_1y), 4)}
                                for n, r in board.iterrows()]
            extra["postmortem"] = [{"exit": str(r.exit.date()), "reentry": str(r.reentry.date()) if r.reentry is not None else None,
                                    "days_out": int(r.days_out), "missed": round(float(r.missed), 4), "verdict": r.verdict}
                                   for r in pm.itertuples()]

    orders = plan_orders(acct, weights, tradable) if (traded or force) else []

    report = {
        "as_of": str(as_of.date()), "equity": round(acct.equity, 2),
        "signal": {"risk_on": bool(row["risk_on"]), "realized_vol": round(float(row["realized_vol"]), 4),
                   "exposure_target": round(float(row["exposure_target"]), 3),
                   **{k: round(float(v), 4) for k, v in row.items() if k.startswith("mom_")}},
        "state_before": asdict(state), "state_after": asdict(new_state),
        "target_weights": weights, "current_weights": {k: round(v, 4) for k, v in acct.weights().items()},
        "orders": [asdict(o) for o in orders], "dry_run": dry_run, "live_prices_used": bool(live),
        **extra,
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


def _kronos_decision(broker: Broker, bars: dict[str, pd.DataFrame], as_of: pd.Timestamp, live: dict | None,
                     kcfg: KronosConfig, cfg: TVMConfig, tvm_weights: dict[str, float] | None,
                     state_dir: Path, log=print) -> tuple[dict[str, float], dict]:
    """Forecast today with Kronos, append it to the forecast history (which
    the calibration needs), and map it to target weights."""
    from .kronos_signal import forecast, load_predictor, load_forecasts, calibrate, kronos_weights, FORECAST_COLS

    today = as_of.normalize()
    todays_bars: dict[str, pd.DataFrame] = {}
    for sym in kcfg.symbols:
        b = bars[sym].copy()
        if live and b.index[-1].normalize() < today:
            tb = getattr(broker, "today_bar", lambda s: None)(sym)
            if tb is None and sym in live:
                p = live[sym]
                tb = {"open": p, "high": p, "low": p, "close": p}
            if tb is not None:
                # the broker's free IEX feed sees a few % of consolidated volume, so
                # use a typical recent day's volume instead of the partial-day figure
                tb["volume"] = float(b["volume"].tail(20).median())
                b.loc[today] = tb
        todays_bars[sym] = b

    hist_path = state_dir / "kronos_forecasts.csv"
    if not hist_path.exists() and kcfg.forecast_cache().exists():
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        hist_path.write_bytes(kcfg.forecast_cache().read_bytes())      # seed calibration from the backtest cache
    hist = load_forecasts(hist_path)
    hist = hist[pd.to_datetime(hist["date"]).dt.normalize() < today]    # re-running today recomputes today
    fc = forecast(load_predictor(kcfg.variant), todays_bars, kcfg)
    new = pd.DataFrame([{"date": today, "symbol": s, **r.to_dict()} for s, r in fc.iterrows()])
    hist = pd.concat([hist, new], ignore_index=True)
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    hist.to_csv(hist_path, index=False)
    cal = calibrate(hist)
    fc_today = cal[cal["date"] == today].set_index("symbol")

    weights = kronos_weights(fc_today, kcfg, cfg, tvm_weights)
    extra = {
        "mode_detail": f"Kronos-{kcfg.variant} candlestick forecast, rule '{kcfg.rule}'",
        "kronos": {s: {k: (round(float(v), 4) if pd.notna(v) else None) for k, v in r.items() if k in (*FORECAST_COLS, "z_ret")}
                   for s, r in fc_today.iterrows()},
        "kronos_history_days": int(cal["date"].nunique()),
    }
    if tvm_weights is not None:
        extra["tvm_weights"] = tvm_weights
    return weights, extra


def _append_log(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"ts": dt.datetime.now(dt.timezone.utc).isoformat(), **report}, default=str) + "\n")
