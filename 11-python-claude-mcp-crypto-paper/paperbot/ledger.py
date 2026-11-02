"""Paper ledger + risk gate. $100 of pretend money, nothing else.

Every write (buy / sell_all / hold) goes through `RiskGate.check` first and
is appended to the decision log whether it filled, was refused, or was a hold.
There is no code path that talks to an exchange or a wallet.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
from pathlib import Path

START_EQUITY = 100.0
FEE_RATE = 0.004                 # 0.4% of notional on every fill
MAX_ENTRY_FRACTION = 0.25        # one entry uses at most 25% of equity
MAX_FILLS_PER_DAY = 6
HALT_BELOW_FRACTION = 0.50       # no new buys once equity < 50% of the start
MIN_ORDER_USD = 1.0
SYMBOLS = ("BTC", "ETH", "SOL")


def utc(ts: float | None = None) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ts is not None \
        else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class Verdict:
    ok: bool
    reason: str = ""


class RiskGate:
    """Pure rules. `check` never mutates anything."""

    def __init__(self, fee_rate=FEE_RATE, max_entry_fraction=MAX_ENTRY_FRACTION, max_fills_per_day=MAX_FILLS_PER_DAY,
                 halt_below_fraction=HALT_BELOW_FRACTION):
        self.fee_rate, self.max_entry_fraction = fee_rate, max_entry_fraction
        self.max_fills_per_day, self.halt_below_fraction = max_fills_per_day, halt_below_fraction

    def check_buy(self, ledger: "Ledger", symbol: str, usd: float, price: float, now: float) -> Verdict:
        if symbol not in SYMBOLS:
            return Verdict(False, f"unknown symbol {symbol}; allowed: {', '.join(SYMBOLS)}")
        if not (price and price > 0):
            return Verdict(False, "no valid price")
        if usd is None or usd <= 0:
            return Verdict(False, "usd_amount must be positive (no shorting)")
        if usd < MIN_ORDER_USD:
            return Verdict(False, f"order below ${MIN_ORDER_USD:.0f} minimum")
        if ledger.position is not None:
            return Verdict(False, f"already holding {ledger.position['symbol']}; one position at a time (sell_all first)")
        equity = ledger.equity({symbol: price})
        if equity < self.halt_below_fraction * ledger.start_equity:
            return Verdict(False, f"equity ${equity:.2f} is below {self.halt_below_fraction:.0%} of the ${ledger.start_equity:.0f} start; new buys halted")
        cap = self.max_entry_fraction * equity
        if usd > cap + 1e-9:
            return Verdict(False, f"${usd:.2f} exceeds {self.max_entry_fraction:.0%} of equity (${cap:.2f})")
        if usd * (1 + self.fee_rate) > ledger.cash + 1e-9:
            return Verdict(False, f"${usd:.2f} plus fee exceeds cash ${ledger.cash:.2f} (no leverage)")
        if ledger.fills_today(now) >= self.max_fills_per_day:
            return Verdict(False, f"{self.max_fills_per_day} fills already today; daily fill limit reached")
        return Verdict(True)

    def check_sell(self, ledger: "Ledger", price: float | None, now: float) -> Verdict:
        if ledger.position is None:
            return Verdict(False, "nothing to sell; no open position")
        if not (price and price > 0):
            return Verdict(False, "no valid price")
        if ledger.fills_today(now) >= self.max_fills_per_day:
            return Verdict(False, f"{self.max_fills_per_day} fills already today; daily fill limit reached")
        return Verdict(True)


class Ledger:
    """State in state/ledger.json, one JSON line per decision in state/decisions.jsonl."""

    def __init__(self, state_dir: Path | str, gate: RiskGate | None = None, start_equity: float = START_EQUITY):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path, self.log_path = self.dir / "ledger.json", self.dir / "decisions.jsonl"
        self.gate = gate or RiskGate()
        if self.path.exists():
            s = json.loads(self.path.read_text())
        else:
            s = {"started": utc(), "start_equity": start_equity, "cash": start_equity, "position": None,
                 "fills": [], "equity_history": [], "fees_paid": 0.0, "refused": 0, "holds": 0}
        self.state = s

    # ---- views -----------------------------------------------------------------
    @property
    def cash(self) -> float:
        return self.state["cash"]

    @property
    def start_equity(self) -> float:
        return self.state["start_equity"]

    @property
    def position(self) -> dict | None:
        return self.state["position"]

    def equity(self, prices: dict[str, float]) -> float:
        p = self.position
        if p is None:
            return self.cash
        px = prices.get(p["symbol"], p.get("last_price") or p["entry_price"])
        return self.cash + p["qty"] * px

    def fills_today(self, now: float) -> int:
        day = utc(now)[:10]
        return sum(1 for f in self.state["fills"] if f["time"][:10] == day)

    def account(self, prices: dict[str, float]) -> dict:
        p = self.position
        eq = self.equity(prices)
        pos = None
        if p is not None:
            px = prices.get(p["symbol"], p["entry_price"])
            pos = {**p, "last_price": px, "value_usd": round(p["qty"] * px, 4),
                   "unrealized_pct": round(px / p["entry_price"] - 1, 6)}
        return {"paper_money_only": True, "cash_usd": round(self.cash, 4), "equity_usd": round(eq, 4),
                "return_since_start": round(eq / self.start_equity - 1, 6), "position": pos,
                "fees_paid_usd": round(self.state["fees_paid"], 4), "fills_today": self.fills_today(dt.datetime.now().timestamp()),
                "rules": {"one_position_at_a_time": True, "max_entry_fraction_of_equity": self.gate.max_entry_fraction,
                          "fee_per_fill": self.gate.fee_rate, "max_fills_per_day": self.gate.max_fills_per_day,
                          "buys_halt_below_fraction_of_start": self.gate.halt_below_fraction, "leverage": 0, "shorting": False},
                "prices": prices}

    # ---- writes ----------------------------------------------------------------
    def buy(self, symbol: str, usd: float, reason: str, price: float, now: float | None = None) -> dict:
        now = now or dt.datetime.now(dt.timezone.utc).timestamp()
        v = self.gate.check_buy(self, symbol, usd, price, now)
        if not v.ok:
            return self._refuse("buy", symbol, price, usd, reason, v.reason, now)
        fee = usd * self.gate.fee_rate
        qty = usd / price
        self.state["cash"] -= usd + fee
        self.state["position"] = {"symbol": symbol, "qty": qty, "entry_price": price, "entry_time": utc(now),
                                  "cost_usd": usd, "last_price": price}
        self.state["fees_paid"] += fee
        fill = {"time": utc(now), "side": "buy", "symbol": symbol, "price": price, "qty": qty, "usd": usd, "fee": fee}
        self.state["fills"].append(fill)
        return self._log({"action": "buy", "status": "filled", "symbol": symbol, "price": price, "size_usd": round(usd, 4),
                          "qty": qty, "fee": round(fee, 4), "reason": reason}, now)

    def sell_all(self, reason: str, prices: dict[str, float], now: float | None = None) -> dict:
        now = now or dt.datetime.now(dt.timezone.utc).timestamp()
        p = self.position
        price = prices.get(p["symbol"]) if p else None
        v = self.gate.check_sell(self, price, now)
        if not v.ok:
            return self._refuse("sell_all", p["symbol"] if p else None, price, None, reason, v.reason, now)
        gross = p["qty"] * price
        fee = gross * self.gate.fee_rate
        self.state["cash"] += gross - fee
        self.state["fees_paid"] += fee
        pnl = gross - fee - p["cost_usd"] * (1 + self.gate.fee_rate)
        self.state["fills"].append({"time": utc(now), "side": "sell", "symbol": p["symbol"], "price": price,
                                    "qty": p["qty"], "usd": gross, "fee": fee, "pnl_usd": pnl})
        self.state["position"] = None
        return self._log({"action": "sell_all", "status": "filled", "symbol": p["symbol"], "price": price,
                          "size_usd": round(gross, 4), "qty": p["qty"], "fee": round(fee, 4),
                          "pnl_usd": round(pnl, 4), "pnl_pct": round(price / p["entry_price"] - 1, 6), "reason": reason}, now)

    def hold(self, reason: str, prices: dict[str, float], now: float | None = None) -> dict:
        now = now or dt.datetime.now(dt.timezone.utc).timestamp()
        self.state["holds"] += 1
        p = self.position
        return self._log({"action": "hold", "status": "ok", "symbol": p["symbol"] if p else None,
                          "price": prices.get(p["symbol"]) if p else None, "size_usd": None, "fee": 0.0, "reason": reason}, now)

    def mark(self, prices: dict[str, float], now: float | None = None) -> float:
        """Record equity at `now` (call once per round)."""
        now = now or dt.datetime.now(dt.timezone.utc).timestamp()
        if self.position is not None and self.position["symbol"] in prices:
            self.position["last_price"] = prices[self.position["symbol"]]
        eq = self.equity(prices)
        self.state["equity_history"].append({"time": utc(now), "equity": round(eq, 4)})
        self.save()
        return eq

    # ---- internals --------------------------------------------------------------
    def _refuse(self, action, symbol, price, usd, reason, why, now) -> dict:
        self.state["refused"] += 1
        return self._log({"action": action, "status": "refused", "symbol": symbol, "price": price,
                          "size_usd": usd, "fee": 0.0, "reason": reason, "refused_because": why}, now)

    def _log(self, rec: dict, now: float) -> dict:
        rec = {"time": utc(now), **rec}
        with self.log_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        self.save()
        return rec

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, indent=2))

    def decisions(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        return [json.loads(ln) for ln in self.log_path.read_text().splitlines() if ln.strip()]

    def stats(self) -> dict:
        eq = [e["equity"] for e in self.state["equity_history"]] or [self.start_equity]
        peak, worst = eq[0], 0.0
        for v in eq:
            peak = max(peak, v)
            worst = min(worst, v / peak - 1)
        sells = [f for f in self.state["fills"] if f["side"] == "sell"]
        return {"equity": eq[-1], "return": eq[-1] / self.start_equity - 1, "fees_paid": self.state["fees_paid"],
                "max_drawdown": worst, "fills": len(self.state["fills"]), "round_trips": len(sells),
                "wins": sum(1 for f in sells if f["pnl_usd"] > 0), "refused": self.state["refused"], "holds": self.state["holds"]}
