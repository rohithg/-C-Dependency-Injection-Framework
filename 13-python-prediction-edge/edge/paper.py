"""Paper account.

Complete-set buys are merged into cash: one YES and one NO are worth $1, so
once both legs are on the book the capital is free again (minus the merge
gas we charge). Ladder and basis packages stay locked. Their worst-case
payout is counted in equity, and it is not spendable.

Maker bids fill only when a later snapshot's ask trades through the bid.
Joining the touch is not modeled as a fill. That under-fills relative to a
live queue, which is the direction we want for a paper number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path

from .books import best_bid, buy_limit, consume_ask, consume_bid
from .fees import maker_fee, taker_fee
from .money import ONE, SIZE_QUANTUM, ZERO, D, floor_to
from .risk import allow
from .strategy import plan_markets


@dataclass
class Lot:
    token_id: str
    market_id: str
    outcome: str
    venue: str
    title: str
    qty: object = ZERO
    cost: object = ZERO
    event_id: str = ""

    def __post_init__(self) -> None:
        self.qty = D(self.qty)
        self.cost = D(self.cost)


@dataclass
class FeeSpec:
    """The fee fields maker_fee() reads. Stored by value so a later book update cannot change a resting order."""

    fee_model: str
    fee_rate: object
    fee_exponent: object = 1
    fee_multiplier: object = 1
    maker_rate: object = 0
    taker_only: bool = True

    def __post_init__(self) -> None:
        self.fee_rate = D(self.fee_rate)
        self.fee_exponent = D(self.fee_exponent)
        self.fee_multiplier = D(self.fee_multiplier)
        self.maker_rate = D(self.maker_rate)

    def to_dict(self) -> dict:
        return {
            "fee_model": self.fee_model, "fee_rate": str(self.fee_rate), "fee_exponent": str(self.fee_exponent),
            "fee_multiplier": str(self.fee_multiplier), "maker_rate": str(self.maker_rate), "taker_only": self.taker_only,
        }


@dataclass
class Resting:
    market_id: str
    token_id: str
    outcome: str
    venue: str
    title: str
    price: object
    size: object
    fee: FeeSpec
    event_id: str = ""

    def __post_init__(self) -> None:
        self.price = D(self.price)
        self.size = D(self.size)


@dataclass
class Package:
    kind: str
    title: str
    qty: object
    cost: object
    floor: object
    market_ids: tuple[str, ...]
    event_id: str = ""

    def __post_init__(self) -> None:
        self.qty = D(self.qty)
        self.cost = D(self.cost)
        self.floor = D(self.floor)


@dataclass
class CycleResult:
    taken: list
    skipped: list
    repairs: list
    matched: list
    watches: list
    opportunities: list


class Account:
    def __init__(self, cash):
        self.cash = D(cash)
        self.lots: dict[str, Lot] = {}
        self.resting: list[Resting] = []
        self.packages: list[Package] = []
        self.fees_paid = ZERO
        self.realized = ZERO
        self.day = ""
        self.day_start_equity = None
        self.last_equity = self.cash
        self.last_marks: dict[str, object] = {}
        self.halted = False
        self.activity: list[str] = []

    def available(self):
        return self.cash - self.reserved()

    def reserved(self):
        return sum((order.price * order.size for order in self.resting), ZERO)

    def reserved_for(self, market_ids: tuple[str, ...]):
        ids = set(market_ids)
        return sum((order.price * order.size for order in self.resting if order.market_id in ids), ZERO)

    def open_notional(self):
        lots = sum((lot.cost for lot in self.lots.values()), ZERO)
        locked = sum((pkg.cost for pkg in self.packages), ZERO)
        return lots + locked + self.reserved()

    def market_notional(self, market_ids: tuple[str, ...]):
        ids = set(market_ids)
        lots = sum((lot.cost for lot in self.lots.values() if lot.market_id in ids), ZERO)
        locked = sum((pkg.cost for pkg in self.packages if ids.intersection(pkg.market_ids)), ZERO)
        return lots + locked + self.reserved_for(market_ids)

    def event_notional(self, event_id: str):
        if not event_id:
            return ZERO
        lots = sum((lot.cost for lot in self.lots.values() if lot.event_id == event_id), ZERO)
        locked = sum((pkg.cost for pkg in self.packages if pkg.event_id == event_id), ZERO)
        resting = sum((order.price * order.size for order in self.resting if order.event_id == event_id), ZERO)
        return lots + locked + resting

    def unpaired_notional(self, market_id: str):
        lots = [lot for lot in self.lots.values() if lot.market_id == market_id and lot.qty > 0]
        if not lots:
            return ZERO
        if len(lots) == 1:
            return lots[0].cost
        a, b = lots[0], lots[1]
        if a.qty == b.qty:
            return ZERO
        big = a if a.qty > b.qty else b
        extra = abs(a.qty - b.qty)
        return big.cost * extra / big.qty

    def equity(self, marks: dict | None = None):
        marks = self.last_marks if marks is None else marks
        loose = ZERO
        for lot in self.lots.values():
            if lot.qty <= 0:
                continue
            loose += lot.qty * D(marks.get(lot.token_id, ZERO))
        locked = sum((pkg.floor for pkg in self.packages), ZERO)
        return self.cash + locked + loose

    def daily_pnl(self):
        if self.day_start_equity is None:
            return ZERO
        return self.last_equity - self.day_start_equity

    def ensure_baseline(self, now: datetime) -> None:
        if self.day_start_equity is None:
            self.day = now.date().isoformat()
            self.day_start_equity = self.equity({})
            self.last_equity = self.day_start_equity

    def mark(self, books: dict, now: datetime) -> None:
        marks = {}
        for token, book in books.items():
            bid = best_bid(book)
            marks[token] = bid.price if bid else ZERO
        self.last_marks = marks
        equity = self.equity(marks)
        day = now.date().isoformat()
        if self.day != day or self.day_start_equity is None:
            self.day = day
            self.day_start_equity = equity
        self.last_equity = equity

    def match_resting(self, books: dict) -> list[str]:
        notes = []
        still: list[Resting] = []
        for order in self.resting:
            book = books.get(order.token_id)
            filled = ZERO
            if book is not None and not self.halted:
                for level in book.asks:
                    if level.price > order.price or filled >= order.size:
                        break
                    take = min(level.size, order.size - filled)
                    if take <= 0:
                        continue
                    level.size -= take
                    filled += take
            if filled > 0:
                fee = maker_fee(order.fee, filled, order.price)
                # Drop the size before paying so the cash this order had reserved is spendable.
                order.size -= filled
                self._buy(order.venue, order.market_id, order.token_id, order.outcome, order.title, filled, order.price, fee, order.event_id)
                notes.append(f"maker fill {order.outcome} {filled} @ {order.price} on {order.title}")
            if order.size > 0:
                still.append(order)
        self.resting = still
        self._refresh()
        return notes

    def repair(self, binaries, books: dict, config, force: bool = False) -> list[str]:
        notes = []
        for market in binaries:
            y = self.lots.get(market.yes.token_id)
            n = self.lots.get(market.no.token_id)
            yq = y.qty if y else ZERO
            nq = n.qty if n else ZERO
            if yq == nq:
                continue
            if not force and self.unpaired_notional(market.market_id) <= config.max_unpaired_notional:
                continue
            if yq > nq:
                need, held, other = yq - nq, y, market.no
            else:
                need, held, other = nq - yq, n, market.yes
            ask = _first_ask(other)
            if ask is None:
                continue
            price = buy_limit(ask.price, config.latency_haircut, other.tick or SIZE_QUANTUM)
            if price is None:
                continue
            size = floor_to(min(need, ask.size), SIZE_QUANTUM)
            if size <= 0:
                continue
            fee = taker_fee(other, size, price)
            held_cost = held.cost * size / held.qty
            if held_cost + price * size + fee > size * (ONE + config.max_leg_loss):
                notes.append(f"holding unpaired {market.title}: completing would lose more than {config.max_leg_loss} per share")
                continue
            if self.available() < price * size + fee:
                notes.append(f"holding unpaired {market.title}: not enough cash to complete")
                continue
            self._buy(other.venue, other.market_id, other.token_id, other.outcome, market.title, size, price, fee, market.event_id)
            consume_ask(other, size)
            self._merge(market.yes.token_id, market.no.token_id, size, config.merge_gas_usd)
            notes.append(f"completed broken pair on {market.title}, {size} shares")
        self._refresh()
        return notes

    def merge_pairs(self, binaries, gas) -> list[str]:
        notes = []
        for market in binaries:
            y = self.lots.get(market.yes.token_id)
            n = self.lots.get(market.no.token_id)
            if not y or not n:
                continue
            size = min(y.qty, n.qty)
            if size <= 0:
                continue
            self._merge(market.yes.token_id, market.no.token_id, size, gas)
            notes.append(f"merged {size} pairs on {market.title}")
        self._refresh()
        return notes

    def execute(self, opp, books: dict, config) -> None:
        if opp.kind == "maker":
            self._replace_quotes(opp, books)
            self.activity.append(f"quote {opp.size} @ {opp.quotes[0].price}+{opp.quotes[1].price} on {opp.title} (if both fill, {opp.net_profit})")
            return
        if opp.kind == "complete_set_sell":
            self.cash -= opp.size
            for leg in opp.legs:
                self.cash += leg.price * leg.size - leg.fee
                self.fees_paid += leg.fee
                consume_bid(books[leg.token_id], leg.size)
            self.cash -= config.merge_gas_usd
            self.realized += opp.net_profit
            self.activity.append(f"mint-sell {opp.size} on {opp.title} for {opp.net_profit}")
            self._refresh()
            return
        for leg in opp.legs:
            self._buy(leg.venue, leg.market_id, leg.token_id, leg.outcome, leg.title, leg.size, leg.price, leg.fee, opp.event_id)
            book = books.get(leg.token_id)
            if book is not None:
                consume_ask(book, leg.size)
        if opp.kind == "complete_set_buy":
            self._merge(opp.legs[0].token_id, opp.legs[1].token_id, opp.size, config.merge_gas_usd)
            self.activity.append(f"bought set {opp.size} on {opp.title} for {opp.net_profit}")
        else:
            self._lock(opp)
            self.activity.append(f"locked {opp.kind} {opp.size} on {opp.title}, worst case {opp.size}, cost in the package")
        self._refresh()

    def cancel_except(self, market_ids: set[str]) -> None:
        self.resting = [order for order in self.resting if order.market_id in market_ids]

    def drop_heavy_quotes(self, binaries) -> None:
        """After a one-sided maker fill, stop bidding for more of the side we already hold."""
        heavy: set[str] = set()
        for market in binaries:
            y = self.lots.get(market.yes.token_id)
            n = self.lots.get(market.no.token_id)
            yq = y.qty if y else ZERO
            nq = n.qty if n else ZERO
            if yq > nq:
                heavy.add(market.yes.token_id)
            elif nq > yq:
                heavy.add(market.no.token_id)
        if heavy:
            self.resting = [order for order in self.resting if order.token_id not in heavy]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))

    def to_dict(self) -> dict:
        return {
            "cash": str(self.cash),
            "fees_paid": str(self.fees_paid),
            "realized": str(self.realized),
            "day": self.day,
            "day_start_equity": None if self.day_start_equity is None else str(self.day_start_equity),
            "last_equity": str(self.last_equity),
            "halted": self.halted,
            "lots": [self._lot_dict(lot) for lot in self.lots.values() if lot.qty > 0],
            "packages": [
                {"kind": p.kind, "title": p.title, "qty": str(p.qty), "cost": str(p.cost),
                 "floor": str(p.floor), "market_ids": list(p.market_ids), "event_id": p.event_id}
                for p in self.packages
            ],
            "activity": self.activity[-50:],
            "resting": [
                {"market_id": o.market_id, "token_id": o.token_id, "outcome": o.outcome, "venue": o.venue,
                 "title": o.title, "price": str(o.price), "size": str(o.size), "fee": o.fee.to_dict(),
                 "event_id": o.event_id}
                for o in self.resting
            ],
        }

    @classmethod
    def load(cls, path: Path, default_cash) -> "Account":
        if not path.exists():
            return cls(default_cash)
        raw = json.loads(path.read_text())
        account = cls(raw["cash"])
        account.fees_paid = D(raw.get("fees_paid", 0))
        account.realized = D(raw.get("realized", 0))
        account.day = raw.get("day") or ""
        start = raw.get("day_start_equity")
        account.day_start_equity = None if start is None else D(start)
        account.last_equity = D(raw.get("last_equity", account.cash))
        account.halted = bool(raw.get("halted", False))
        account.activity = list(raw.get("activity") or [])
        for row in raw.get("lots") or []:
            lot = Lot(row["token_id"], row["market_id"], row["outcome"], row["venue"], row["title"], row["qty"], row["cost"], row.get("event_id", ""))
            account.lots[lot.token_id] = lot
        for row in raw.get("packages") or []:
            account.packages.append(Package(
                row["kind"], row["title"], row["qty"], row["cost"], row["floor"], tuple(row["market_ids"]),
                row.get("event_id", ""),
            ))
        for row in raw.get("resting") or []:
            fee = row.get("fee") or {}
            account.resting.append(Resting(
                row["market_id"], row["token_id"], row["outcome"], row["venue"], row["title"],
                row["price"], row["size"], FeeSpec(
                    fee.get("fee_model", "polymarket"), fee.get("fee_rate", 0), fee.get("fee_exponent", 1),
                    fee.get("fee_multiplier", 1), fee.get("maker_rate", 0), bool(fee.get("taker_only", True)),
                ),
                row.get("event_id", ""),
            ))
        return account

    def _buy(self, venue, market_id, token_id, outcome, title, size, price, fee, event_id: str = "") -> None:
        spend = price * size + fee
        if self.available() + _PENNY < spend:
            raise RuntimeError(f"paper cash shortfall: need {spend}, have {self.available()}")
        self.cash -= spend
        self.fees_paid += fee
        lot = self.lots.get(token_id)
        if lot is None:
            lot = Lot(token_id, market_id, outcome, venue, title, event_id=event_id)
            self.lots[token_id] = lot
        lot.qty += size
        lot.cost += spend

    def _merge(self, yes_token: str, no_token: str, size, gas) -> None:
        yes, no = self.lots[yes_token], self.lots[no_token]
        if yes.qty < size or no.qty < size:
            raise RuntimeError("merge larger than the pair on the book")
        yes_cost = yes.cost * size / yes.qty
        no_cost = no.cost * size / no.qty
        self.cash += size - gas
        self.realized += size - yes_cost - no_cost - gas
        self._shrink(yes, size, yes_cost)
        self._shrink(no, size, no_cost)

    def _lock(self, opp) -> None:
        cost = ZERO
        for leg in opp.legs:
            lot = self.lots[leg.token_id]
            take = lot.cost * leg.size / lot.qty
            self._shrink(lot, leg.size, take)
            cost += take
        self.packages.append(Package(opp.kind, opp.title, opp.size, cost, opp.size, opp.market_ids, opp.event_id))

    def _shrink(self, lot: Lot, size, cost) -> None:
        lot.qty -= size
        lot.cost -= cost
        if lot.qty <= 0:
            self.lots.pop(lot.token_id, None)

    def _replace_quotes(self, opp, books: dict) -> None:
        market_id = opp.market_ids[0]
        self.resting = [order for order in self.resting if order.market_id != market_id]
        for leg in opp.quotes:
            book = books[leg.token_id]
            self.resting.append(Resting(
                market_id, leg.token_id, leg.outcome, leg.venue, leg.title, leg.price, leg.size, _fee_spec(book),
                opp.event_id,
            ))

    def _refresh(self) -> None:
        self.last_equity = self.equity(self.last_marks)

    @staticmethod
    def _lot_dict(lot: Lot) -> dict:
        return {
            "token_id": lot.token_id, "market_id": lot.market_id, "outcome": lot.outcome,
            "venue": lot.venue, "title": lot.title, "qty": str(lot.qty), "cost": str(lot.cost),
            "event_id": lot.event_id,
        }


_PENNY = D("0.0000001")


def index_books(binaries, ladders, links) -> dict:
    books = {}
    for market in binaries:
        books[market.yes.token_id] = market.yes
        books[market.no.token_id] = market.no
    for ladder in ladders:
        for strike in ladder.strikes:
            books[strike.market.yes.token_id] = strike.market.yes
            books[strike.market.no.token_id] = strike.market.no
    for link in links:
        for market in (link.left, link.right):
            books[market.yes.token_id] = market.yes
            books[market.no.token_id] = market.no
    return books


def run_cycle(account: Account, binaries, ladders, links, config, now: datetime, now_ms: int) -> CycleResult:
    books = index_books(binaries, ladders, links)
    account.ensure_baseline(now)
    if account.halted:
        account.cancel_except(set())
        matched: list[str] = []
    else:
        matched = account.match_resting(books)
        account.drop_heavy_quotes(binaries)
    repairs = account.repair(binaries, books, config)
    account.merge_pairs(binaries, config.merge_gas_usd)
    opportunities, watches = plan_markets(binaries, ladders, links, config)
    taken = []
    skipped = []
    used: set[str] = set()
    if not account.halted:
        for opp in opportunities:
            if any(market_id in used for market_id in opp.market_ids):
                skipped.append((opp, "overlaps a better trade"))
                continue
            ok, reason = allow(account, opp, config, now_ms)
            if not ok:
                skipped.append((opp, reason))
                continue
            account.execute(opp, books, config)
            used.update(opp.market_ids)
            taken.append(opp)
    wanted = set() if account.halted else {opp.market_ids[0] for opp in opportunities if opp.kind == "maker"}
    account.cancel_except(wanted)
    account.mark(books, now)
    return CycleResult(taken, skipped, repairs, matched, watches, opportunities)


def _fee_spec(book) -> FeeSpec:
    return FeeSpec(book.fee_model, book.fee_rate, book.fee_exponent, book.fee_multiplier, book.maker_rate, book.taker_only)


def _first_ask(book):
    for level in book.asks:
        if level.size > 0 and ZERO < level.price < ONE:
            return level
    return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
