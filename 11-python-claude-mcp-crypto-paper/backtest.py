#!/usr/bin/env python3
"""Is this viable? Replay the trading prompt's rules through the real ledger
and risk gate over Kraken's public history, and compare with doing nothing.

    python backtest.py                 # 4h candles (Kraken keeps 720 = 120 days) and daily (720 days)
    python backtest.py --json out.json

Every run uses the same Ledger/RiskGate as the live rounds (fees, 25% cap,
6 fills/day, one position, halt below 50%), fills at the candle close that
was the latest price at decision time, and marks equity every candle.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paperbot import kraken, strategy                    # noqa: E402
from paperbot.ledger import Ledger, RiskGate            # noqa: E402

SYMBOLS = ("BTC", "ETH", "SOL")


def load(timeframe: str) -> dict[str, list[dict]]:
    data = {s: kraken.candles(s, timeframe, 720) for s in SYMBOLS}
    n = min(len(v) for v in data.values())
    return {s: v[-n:] for s, v in data.items()}


def replay(data: dict[str, list[dict]], agent: str, *, entry_fraction=0.25, seed=0, start_equity=100.0) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="pb-bt-"))
    try:
        led = Ledger(tmp, RiskGate(max_entry_fraction=entry_fraction), start_equity=start_equity)
        rng = random.Random(seed)

        def size(prices):            # the gate's cap, but never cash we do not have (fee included)
            return int(min(led.equity(prices) * entry_fraction, led.cash / (1 + led.gate.fee_rate)) * 100) / 100

        n = len(data["BTC"])
        warm = max(strategy.SMA_N, strategy.RSI_N + 1, strategy.MOM_N + 1)
        for i in range(warm, n):
            now = data["BTC"][i]["time"]
            prices = {s: data[s][i]["close"] for s in SYMBOLS}
            closes = {s: [c["close"] for c in data[s][: i + 1]] for s in SYMBOLS}
            feats = {s: strategy.features(closes[s]) for s in SYMBOLS}
            pos = led.position
            if agent == "rules":
                if pos:
                    why = strategy.exit_reason(feats[pos["symbol"]], pos["entry_price"], prices[pos["symbol"]])
                    if why:
                        led.sell_all(why, prices, now)
                else:
                    pick = strategy.entry_candidate(feats)
                    if pick:
                        sym, f = pick
                        led.buy(sym, size(prices), strategy.describe(sym, f), prices[sym], now)
            elif agent == "random":                       # zero-skill reference: coin flips inside the same gate
                if pos and rng.random() < 0.25:
                    led.sell_all("random", prices, now)
                elif not pos and rng.random() < 0.25:
                    sym = rng.choice(SYMBOLS)
                    led.buy(sym, size(prices), "random", prices[sym], now)
            elif agent.startswith("hold:"):               # buy once, never sell
                sym = agent.split(":")[1]
                if not pos and not led.state["fills"]:
                    led.buy(sym, size(prices), "buy and hold", prices[sym], now)
            led.mark(prices, now)
        s = led.stats()
        days = (data["BTC"][-1]["time"] - data["BTC"][warm]["time"]) / 86400
        return {"agent": agent, "entry_fraction": entry_fraction, "days": round(days, 1), **{k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()}}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def table(rows: list[dict], title: str) -> str:
    out = [f"\n{title}", "| strategy | return | max drop | fees | fills | refused | win rate |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        wr = f"{r['wins'] / r['round_trips']:.0%}" if r.get("round_trips") else "-"
        out.append(f"| {r['label']} | {r['return']:+.1%} | {r['max_drawdown']:.1%} | ${r['fees_paid']:.2f} | {r['fills']} | {r['refused']} | {wr} |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()
    results = {}
    for tf, label in (("4h", "4-hour candles, every candle is a round (what the 4-hourly schedule does)"),
                      ("1d", "daily candles (longer history; the prompt's SMA20 / RSI14 / 6-candle momentum applied to days)")):
        data = load(tf)
        days = (data["BTC"][-1]["time"] - data["BTC"][0]["time"]) / 86400
        rows = []
        r = replay(data, "rules"); rows.append({**r, "label": "Prompt rules, 25% entries (the experiment)"})
        r = replay(data, "rules", entry_fraction=1.0); rows.append({**r, "label": "Prompt rules, 100% entries (cap removed)"})
        rnd = [replay(data, "random", seed=k) for k in range(20)]
        rows.append({"label": "Random decisions, 25% entries (median of 20)", "return": statistics.median(x["return"] for x in rnd),
                     "max_drawdown": statistics.median(x["max_drawdown"] for x in rnd), "fees_paid": statistics.median(x["fees_paid"] for x in rnd),
                     "fills": int(statistics.median(x["fills"] for x in rnd)), "refused": int(statistics.median(x["refused"] for x in rnd)),
                     "round_trips": 0})
        for s in SYMBOLS:
            r = replay(data, f"hold:{s}"); rows.append({**r, "label": f"Buy {s} once with 25%, hold"})
        r = replay(data, "hold:BTC", entry_fraction=1.0); rows.append({**r, "label": "Buy BTC once with 100%, hold"})
        tvm = (1.134 ** (rows[0]["days"] / 365.25)) - 1
        rows.append({"label": f"TVM backtest average, same {rows[0]['days']:.0f} days (13.4%/yr, reference)", "return": tvm,
                     "max_drawdown": float("nan"), "fees_paid": 0.0, "fills": 0, "refused": 0, "round_trips": 0})
        print(f"\n=== {label}: {data['BTC'][0]['time']} -> {data['BTC'][-1]['time']} ({days:.0f} days of data, "
              f"BTC {data['BTC'][0]['close']:,.0f} -> {data['BTC'][-1]['close']:,.0f}) ===")
        print(table(rows, ""))
        results[tf] = rows
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
