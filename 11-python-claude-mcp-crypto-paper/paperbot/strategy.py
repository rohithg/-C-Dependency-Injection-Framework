"""The rules in prompts/trading_prompt.md as plain functions, shared by the
offline rule agent (live rounds without Claude Code) and the backtest."""
from __future__ import annotations

SMA_N, RSI_N, MOM_N = 20, 14, 6          # 6 four-hour candles = 24 hours
RSI_LO, RSI_HI, MOM_MIN = 50.0, 70.0, 0.01
STOP, TAKE = -0.03, 0.06
ENTRY_FRACTION = 0.25


def sma(xs: list[float], n: int) -> float | None:
    return sum(xs[-n:]) / n if len(xs) >= n else None


def rsi(xs: list[float], n: int = RSI_N) -> float | None:
    if len(xs) < n + 1:
        return None
    gains = losses = 0.0
    for a, b in zip(xs[-n - 1:-1], xs[-n:]):
        d = b - a
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def features(closes: list[float]) -> dict | None:
    if len(closes) < max(SMA_N, RSI_N + 1, MOM_N + 1):
        return None
    return {"close": closes[-1], "sma": sma(closes, SMA_N), "rsi": rsi(closes), "mom": closes[-1] / closes[-1 - MOM_N] - 1}


def entry_candidate(feats: dict[str, dict | None]) -> tuple[str, dict] | None:
    """Best qualifying symbol, or None."""
    ok = [(s, f) for s, f in feats.items() if f and f["close"] > f["sma"] and RSI_LO <= f["rsi"] <= RSI_HI and f["mom"] > MOM_MIN]
    return max(ok, key=lambda sf: sf[1]["mom"]) if ok else None


def exit_reason(f: dict | None, entry_price: float, last_price: float) -> str | None:
    unreal = last_price / entry_price - 1
    if unreal <= STOP:
        return f"stop: {unreal:+.1%} <= {STOP:+.0%}"
    if unreal >= TAKE:
        return f"take-profit: {unreal:+.1%} >= {TAKE:+.0%}"
    if f and f["close"] < f["sma"]:
        return f"close {f['close']:,.2f} < SMA20 {f['sma']:,.2f}"
    return None


def describe(symbol: str, f: dict) -> str:
    return f"{symbol} close {f['close']:,.2f} vs SMA20 {f['sma']:,.2f}, RSI {f['rsi']:.0f}, 24h {f['mom']:+.1%}"
