"""A concrete reading of prompts/trading_prompt.md (Prompt 02) for the
offline rule agent and the backtest.

The prompt is discretionary ("grow it", "take profit or cut the loss rather
than holding through a reversal") so something has to be pinned down to test
it. This is the most natural momentum reading of 24 hourly bars:

  entry  the symbol with the strongest 24h return, if it is up > 1.5% over
         24h, still rising over the last 6h, and in the top 40% of its 24h
         range (continuation, not a dip-buy); size 25% of equity
  exit   cut at -2%, take at +4%, or sell when the last 6h turned down by
         more than 1% (the "reversal" clause)

Both thresholds clear the 0.8% round-trip fee. Change these and re-run
backtest.py to test a different reading.
"""
from __future__ import annotations

WINDOW = 24                      # bars the prompt gives the model
SHORT = 6                        # "recent" momentum window, in bars
MOM_MIN, SHORT_MIN, RANGE_MIN = 0.015, 0.0, 0.60
STOP, TAKE, REVERSAL = -0.02, 0.04, -0.01
ENTRY_FRACTION = 0.25


def features(closes: list[float], highs: list[float] | None = None, lows: list[float] | None = None) -> dict | None:
    if len(closes) < WINDOW:
        return None
    c = closes[-WINDOW:]
    hi = max(highs[-WINDOW:]) if highs else max(c)
    lo = min(lows[-WINDOW:]) if lows else min(c)
    return {"close": c[-1], "mom": c[-1] / c[0] - 1, "short": c[-1] / c[-1 - SHORT] - 1,
            "range_pos": (c[-1] - lo) / (hi - lo) if hi > lo else 0.5, "hi": hi, "lo": lo}


def entry_candidate(feats: dict[str, dict | None]) -> tuple[str, dict] | None:
    ok = [(s, f) for s, f in feats.items() if f and f["mom"] > MOM_MIN and f["short"] > SHORT_MIN and f["range_pos"] >= RANGE_MIN]
    return max(ok, key=lambda sf: sf[1]["mom"]) if ok else None


def exit_reason(f: dict | None, entry_price: float, last_price: float) -> str | None:
    unreal = last_price / entry_price - 1
    if unreal <= STOP:
        return f"cut the loss: {unreal:+.1%} <= {STOP:+.0%}"
    if unreal >= TAKE:
        return f"take profit: {unreal:+.1%} >= {TAKE:+.0%}"
    if f and f["short"] <= REVERSAL:
        return f"reversal: last {SHORT}h {f['short']:+.1%}, not holding through it ({unreal:+.1%})"
    return None


def describe(symbol: str, f: dict) -> str:
    return (f"{symbol} {f['close']:,.2f}: 24h {f['mom']:+.1%}, last {SHORT}h {f['short']:+.1%}, "
            f"{f['range_pos']:.0%} of the 24h range")


def honest_hold(feats: dict[str, dict | None]) -> str:
    best = max((f for f in feats.values() if f), key=lambda f: f["mom"], default=None)
    if best is None:
        return "no candles; holding cash"
    bits = "; ".join(describe(s, f) for s, f in feats.items() if f)
    return f"nothing is trending enough to pay a 0.8% round trip ({bits}); weak reason to do anything, so cash"


# --- the opposite reading, so the verdict does not hinge on one interpretation ---
# buy the symbol that fell hardest over 24h and sits near the bottom of its range
# (a "dip"), sell on a +2% bounce, cut at -3%, or give up after 24 bars.
MR_DROP, MR_RANGE_MAX, MR_TAKE, MR_STOP, MR_MAX_BARS = -0.015, 0.25, 0.02, -0.03, 24


def entry_candidate_mr(feats: dict[str, dict | None]) -> tuple[str, dict] | None:
    ok = [(s, f) for s, f in feats.items() if f and f["mom"] < MR_DROP and f["range_pos"] <= MR_RANGE_MAX]
    return min(ok, key=lambda sf: sf[1]["mom"]) if ok else None


def exit_reason_mr(entry_price: float, last_price: float, bars_held: int) -> str | None:
    unreal = last_price / entry_price - 1
    if unreal >= MR_TAKE:
        return f"bounce sold: {unreal:+.1%}"
    if unreal <= MR_STOP:
        return f"cut the loss: {unreal:+.1%}"
    if bars_held >= MR_MAX_BARS:
        return f"no bounce after {bars_held} bars ({unreal:+.1%})"
    return None
