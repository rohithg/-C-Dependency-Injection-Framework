"""Paper trading only. A fake USD balance in data/paper_state.json; no wallet,
no keys, no signing code anywhere in this project.

Fills are deliberately pessimistic: every buy and sell pays `dex_fee_pct`
plus a price impact of (order size) / (half the pool's USD liquidity), capped
at `max_price_impact_pct`. A pool whose liquidity has gone to zero pays
nothing on exit (that is what a rug looks like to a holder). Positions are
closed by stop-loss, take-profit, a maximum holding time, or liquidity
collapse; new buys stop for the day once the daily loss cap is hit.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


def utc_day(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


class PaperTrader:
    def __init__(self, path: Path, cfg: dict, now: float):
        self.path, self.cfg = path, cfg
        raw = json.loads(path.read_text()) if path.exists() else {}
        start = float(cfg.get("paper_start_balance_usd", 1000))
        self.balance: float = raw.get("balance", start)
        self.start_balance: float = raw.get("start_balance", start)
        self.started: str = raw.get("started", utc_day(now))
        self.positions: dict[str, dict] = raw.get("positions", {})
        self.closed: list[dict] = raw.get("closed", [])
        self.day: str = raw.get("day", utc_day(now))
        self.day_start_equity: float = raw.get("day_start_equity", self.balance)
        self.halted_day: str = raw.get("halted_day", "")
        self.equity_history: list[list] = raw.get("equity_history", [])

    # ------------------------------------------------------------------ persistence
    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "balance": self.balance, "start_balance": self.start_balance, "started": self.started,
            "positions": self.positions, "closed": self.closed[-500:], "day": self.day,
            "day_start_equity": self.day_start_equity, "halted_day": self.halted_day,
            "equity_history": self.equity_history[-5000:],
        }, indent=1))

    # ------------------------------------------------------------------ valuation
    def equity(self, prices: dict[str, dict] | None = None) -> float:
        prices = prices or {}
        total = self.balance
        for tok, p in self.positions.items():
            price = float((prices.get(tok) or {}).get("priceUsd") or p.get("last_price") or p["entry_price"])
            total += p["tokens"] * price
        return total

    def rollover(self, now: float, prices: dict[str, dict] | None = None) -> None:
        day = utc_day(now)
        if day != self.day:
            self.day, self.day_start_equity = day, self.equity(prices)

    def daily_loss(self, prices: dict[str, dict] | None = None) -> float:
        if self.day_start_equity <= 0:
            return 0.0
        return max(0.0, 1.0 - self.equity(prices) / self.day_start_equity)

    # ------------------------------------------------------------------ entries
    def can_buy(self, now: float, prices: dict[str, dict] | None = None) -> tuple[bool, str]:
        self.rollover(now, prices)
        if self.halted_day == self.day:
            return False, "daily loss cap hit; no new buys today"
        if self.daily_loss(prices) >= self.cfg["max_daily_loss_pct"]:
            self.halted_day = self.day
            return False, f"daily loss {self.daily_loss(prices):.1%} >= {self.cfg['max_daily_loss_pct']:.0%}; stopping for the day"
        if len(self.positions) >= self.cfg.get("max_open_positions", 10):
            return False, f"{len(self.positions)} open positions (max {self.cfg.get('max_open_positions', 10)})"
        if self.balance < 1.0:
            return False, "no paper balance left"
        return True, "ok"

    def buy(self, token: str, pair: dict, now: float, prices: dict[str, dict] | None = None) -> dict | None:
        if token in self.positions:
            return None
        notional = min(self.cfg["max_position_pct"] * self.equity(prices), self.balance)
        if notional < 1.0:
            return None
        price, liq = float(pair["price_usd"]), float(pair["liquidity_usd"])
        impact = self._impact(notional, liq)
        fill = price * (1 + self.cfg["dex_fee_pct"] + impact)
        tokens = notional / fill
        self.balance -= notional
        pos = {"symbol": pair.get("symbol"), "name": pair.get("name"), "pair": pair.get("pair"), "entry_ts": now,
               "entry_price": fill, "mid_at_entry": price, "tokens": tokens, "cost_usd": notional, "impact_at_entry": impact,
               "liquidity_at_entry": liq, "stop": fill * (1 - self.cfg["stop_loss_pct"]), "take_profit": fill * (1 + self.cfg["take_profit_pct"]),
               "last_price": price, "url": pair.get("url")}
        self.positions[token] = pos
        return {"action": "BUY", "token": token, **pos}

    # ------------------------------------------------------------------ exits
    def update(self, prices: dict[str, dict], now: float) -> list[dict]:
        """Mark every position and close the ones that hit an exit rule. Returns the sells."""
        self.rollover(now, prices)
        sells = []
        for token, pos in list(self.positions.items()):
            p = prices.get(token)
            if p is None:
                pos["stale"] = pos.get("stale", 0) + 1       # DEX Screener no longer lists it; after 3 cycles treat as dead
                if pos["stale"] >= 3:
                    sells.append(self._close(token, 0.0, 0.0, now, "delisted / no price for 3 cycles"))
                continue
            price = float(p.get("priceUsd") or 0.0)
            liq = float((p.get("liquidity") or {}).get("usd") or 0.0)
            pos["last_price"], pos["last_liquidity"], pos["stale"] = price, liq, 0
            age_h = (now - pos["entry_ts"]) / 3600
            reason = None
            if liq < self.cfg["min_liquidity_usd"] / 4 or price <= 0:
                reason = f"liquidity collapsed to ${liq:,.0f}"
            elif price <= pos["stop"]:
                reason = f"stop-loss ({price / pos['entry_price'] - 1:+.0%})"
            elif price >= pos["take_profit"]:
                reason = f"take-profit ({price / pos['entry_price'] - 1:+.0%})"
            elif age_h >= self.cfg["max_hold_hours"]:
                reason = f"max hold {self.cfg['max_hold_hours']}h ({price / pos['entry_price'] - 1:+.0%})"
            if reason:
                sells.append(self._close(token, price, liq, now, reason))
        eq = self.equity(prices)
        self.equity_history.append([int(now), round(eq, 2)])
        if self.daily_loss(prices) >= self.cfg["max_daily_loss_pct"]:
            self.halted_day = self.day
        return sells

    def _close(self, token: str, price: float, liq: float, now: float, reason: str) -> dict:
        pos = self.positions.pop(token)
        gross = pos["tokens"] * price
        impact = self._impact(gross, liq) if liq > 0 else self.cfg["max_price_impact_pct"]
        proceeds = gross * (1 - self.cfg["dex_fee_pct"] - impact) if liq > 0 else 0.0
        self.balance += proceeds
        rec = {"action": "SELL", "token": token, "symbol": pos.get("symbol"), "entry_ts": pos["entry_ts"], "exit_ts": now,
               "entry_price": pos["entry_price"], "exit_price": price, "proceeds_usd": proceeds, "cost_usd": pos["cost_usd"],
               "pnl_usd": proceeds - pos["cost_usd"], "pnl_pct": proceeds / pos["cost_usd"] - 1 if pos["cost_usd"] else 0.0,
               "hold_hours": (now - pos["entry_ts"]) / 3600, "reason": reason, "impact_at_exit": impact}
        self.closed.append(rec)
        return rec

    def _impact(self, notional: float, liq: float) -> float:
        if liq <= 0:
            return self.cfg["max_price_impact_pct"]
        return min(self.cfg["max_price_impact_pct"], notional / (liq / 2.0))

    # ------------------------------------------------------------------ stats
    def stats(self) -> dict:
        wins = [c for c in self.closed if c["pnl_usd"] > 0]
        losses = [c for c in self.closed if c["pnl_usd"] <= 0]
        return {
            "closed": len(self.closed), "wins": len(wins), "losses": len(losses),
            "win_rate": len(wins) / len(self.closed) if self.closed else None,
            "avg_win_pct": sum(c["pnl_pct"] for c in wins) / len(wins) if wins else None,
            "avg_loss_pct": sum(c["pnl_pct"] for c in losses) / len(losses) if losses else None,
            "biggest_loss_pct": min((c["pnl_pct"] for c in self.closed), default=None),
            "stop_losses": sum(1 for c in self.closed if c["reason"].startswith("stop-loss")),
            "realized_pnl_usd": sum(c["pnl_usd"] for c in self.closed),
            "rugs": sum(1 for c in self.closed if c["proceeds_usd"] == 0.0),
        }
