from datetime import datetime
from decimal import Decimal
from pathlib import Path

from edge.models import Ladder, StrikeMarket
from edge.paper import Account, run_cycle
from edge.replay import run_document
from edge.risk import allow
from edge.strategy import complete_set_buy
from support import cfg, market

ROOT = Path(__file__).resolve().parents[1]
WHEN = datetime(2026, 11, 8, 12, 0)


def test_replay_locks_the_recorded_edge():
    account, results, _config = run_document(ROOT / "examples" / "replay.json")
    kinds = [opp.kind for result in results for opp in result.taken]
    assert "complete_set_buy" in kinds
    assert "maker" in kinds
    assert "ladder" in kinds
    assert results[1].matched, "the second snapshot should trade through the resting bids"
    # 30 shares bought at 0.40/0.40 (+6), 10 maker shares at 0.46/0.46 (+0.80),
    # 20 ladder shares with Kalshi fees, worst case +5.37.
    assert account.last_equity == Decimal("1012.17")
    assert account.cash == Decimal("992.17")
    assert account.packages[0].floor == Decimal("20")
    assert account.realized == Decimal("6.80")


def test_maker_bid_does_not_fill_until_the_ask_trades_through_it():
    wide = market("wide", [("0.52", "100")], [("0.52", "100")], [("0.46", "100")], [("0.46", "100")])
    account = Account("1000")
    first = run_cycle(account, [wide], [], [], cfg(), WHEN, 0)
    assert [opp.kind for opp in first.taken] == ["maker"]
    assert account.cash == Decimal("1000")
    still = market("wide", [("0.55", "100")], [("0.55", "100")], [("0.46", "100")], [("0.46", "100")])
    second = run_cycle(account, [still], [], [], cfg(), WHEN, 0)
    assert second.matched == []
    assert account.realized == 0


def test_unpaired_maker_fill_waits_instead_of_crossing():
    quoted = market("wide", [("0.52", "100")], [("0.52", "100")], [("0.46", "100")], [("0.46", "100")])
    account = Account("1000")
    run_cycle(account, [quoted], [], [], cfg(), WHEN, 0)
    # Only the YES ask trades through the bid. The NO ask stays above it.
    crossed = market("wide", [("0.46", "10")], [("0.52", "100")], [("0.46", "100")], [("0.46", "100")])
    result = run_cycle(account, [crossed], [], [], cfg(max_unpaired_notional="20"), WHEN, 0)
    assert result.matched
    assert account.lots
    assert not any("completed" in note for note in result.repairs)
    assert account.halted is False


def test_one_game_cannot_take_every_quote():
    def prop(name):
        book = market(name, [("0.52", "100")], [("0.52", "100")], [("0.46", "100")], [("0.46", "100")], title=name)
        book.event_id = "LAL-BOS"
        return book
    result = run_cycle(
        Account("1000"), [prop("points"), prop("rebounds"), prop("assists")], [], [],
        cfg(max_event_notional="12", quote_size="10"), WHEN, 0,
    )
    quoted = [opp for opp in result.taken if opp.kind == "maker"]
    assert len(quoted) == 1
    assert any(reason == "event notional cap" for _, reason in result.skipped)


def test_risk_blocks_a_halt_a_daily_loss_and_a_stale_book():
    book = market("free", [("0.40", "20")], [("0.40", "20")], ts_ms=1_000)
    opp = complete_set_buy(book, cfg())
    account = Account("1000")
    account.ensure_baseline(WHEN)
    assert allow(account, opp, cfg(), 1_000)[0]

    account.halted = True
    assert allow(account, opp, cfg(), 1_000)[1] == "kill switch"
    account.halted = False

    account.last_equity = Decimal("970")
    assert allow(account, opp, cfg(), 1_000)[1] == "daily loss limit"
    account.last_equity = account.day_start_equity

    assert allow(account, opp, cfg(max_book_age_ms=500), 2_000)[1] == "stale book"


def test_account_round_trip_keeps_a_locked_package(tmp_path):
    easy = market("E", [("0.40", "10")], [("0.70", "10")], [("0.30", "10")], fee_model="kalshi", fee_rate="0.07")
    hard = market("H", [("0.80", "10")], [("0.30", "10")], [("0.70", "10")], fee_model="kalshi", fee_rate="0.07")
    ladder = Ladder("kalshi", "EVT", "ladder", "greater", [StrikeMarket(easy, "1", "greater"), StrikeMarket(hard, "2", "greater")])
    account = Account("1000")
    run_cycle(account, [], [ladder], [], cfg(), WHEN, 0)
    path = tmp_path / "account.json"
    account.save(path)
    loaded = Account.load(path, "1000")
    assert loaded.packages[0].floor == account.packages[0].floor
    assert loaded.cash == account.cash
