import base64
from decimal import Decimal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from edge.config import Config
from edge.kalshi import kalshi_order, parse_event_ladder, parse_market, sign_request
from edge.live import Fill, _kalshi_fill, execute, gate
from edge.models import Leg, Opportunity
from edge.paper import Account
from edge.polymarket import parse_market_spec
from support import cfg, market


def test_gamma_spec_uses_the_clob_tokens_and_the_fee_schedule():
    spec = parse_market_spec({
        "acceptingOrders": True,
        "enableOrderBook": True,
        "closed": False,
        "version": "v1",
        "conditionId": "0xabc",
        "question": "Will it rain?",
        "outcomes": "[\"Yes\", \"No\"]",
        "clobTokenIds": "[\"10\", \"11\"]",
        "feesEnabled": True,
        "feeSchedule": {"rate": 0.05, "exponent": 1, "takerOnly": True},
        "orderPriceMinTickSize": 0.001,
        "orderMinSize": 5,
    })
    assert spec["yes_token"] == "10"
    assert spec["fee_rate"] == Decimal("0.05")
    assert spec["tick"] == Decimal("0.001")
    assert spec["min_size"] == Decimal("5")


def test_closed_and_non_binary_markets_are_ignored():
    assert parse_market_spec({"closed": True, "outcomes": ["Yes", "No"], "clobTokenIds": ["1", "2"]}) is None
    assert parse_market_spec({
        "acceptingOrders": True, "enableOrderBook": True, "outcomes": ["Home", "Away"],
        "clobTokenIds": ["1", "2"],
    }) is None


def test_kalshi_parser_builds_the_no_ask_from_the_yes_bid_and_rejects_a_crossed_quote():
    market_raw = {
        "ticker": "KX-1", "event_ticker": "KX", "status": "active", "yes_sub_title": "above 100",
        "strike_type": "greater", "floor_strike": 100,
        "yes_bid_dollars": "0.4000", "yes_bid_size_fp": "12",
        "yes_ask_dollars": "0.4500", "yes_ask_size_fp": "8",
        "no_ask_dollars": "0.6000",
    }
    parsed = parse_market(market_raw)
    assert parsed.no.asks[0].price == Decimal("0.60")
    assert parsed.no.asks[0].size == Decimal("12")
    ladder = parse_event_ladder({
        "event_ticker": "KX", "title": "BTC",
        "markets": [
            market_raw,
            {**market_raw, "ticker": "KX-2", "floor_strike": 110, "yes_sub_title": "above 110",
             "yes_bid_dollars": "0.2000", "no_ask_dollars": "0.8000"},
        ],
    })
    assert ladder is not None and len(ladder.strikes) == 2
    inconsistent = dict(market_raw, no_ask_dollars="0.5000")
    assert parse_market(inconsistent) is None


def test_no_buy_is_an_ask_on_the_yes_book():
    leg = Leg("kalshi", "KX-1", "KX-1:no", "no", "buy", "0.4200", "5", "0.10", "above")
    order = kalshi_order(leg, "cid-1")
    assert order["side"] == "ask"
    assert order["price"] == "0.5800"
    assert order["count"] == "5.00"
    assert order["time_in_force"] == "immediate_or_cancel"
    assert order["post_only"] is False
    body = {"fill_count": "5.00", "average_fill_price": "0.5800", "average_fee_paid": "0.0200"}
    fill = _kalshi_fill(body, leg)
    assert fill.price == Decimal("0.4200")
    assert fill.fee == Decimal("0.1000")


def test_signature_verifies_with_the_kalshi_pss_rule():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signed = sign_request(key, "1700000000000", "POST", "/trade-api/v2/portfolio/events/orders?ignored=1")
    key.public_key().verify(
        base64.b64decode(signed),
        b"1700000000000POST/trade-api/v2/portfolio/events/orders",
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )


def test_live_gates_and_a_broken_leg_halts():
    config = cfg(live_enabled=True)
    assert gate(config, False)
    assert gate(Config(live_enabled=False), True)
    assert "EDGE_LIVE_OK" in gate(config, True)
    book = market("pair", [("0.40", "10")], [("0.90", "10")], title="pair")
    legs = (
        Leg("polymarket", "pair", book.yes.token_id, "yes", "buy", "0.40", "10", "0", "pair"),
        Leg("polymarket", "pair", book.no.token_id, "no", "buy", "0.40", "10", "0", "pair"),
    )
    opp = Opportunity("complete_set_buy", "pair", "10", "0.20", "2", legs, True, ("pair",), "test")
    account = Account("1000")

    class Scripted:
        def __init__(self):
            self.sent = []

        def supports(self, leg):
            return True

        def submit(self, leg):
            self.sent.append(leg.outcome)
            if leg.outcome == "no":
                return Fill(Decimal("0"), leg.price, Decimal("0"))
            return Fill(leg.size, leg.price, leg.fee)

    notes = execute([opp], Scripted(), account, [book], {book.yes.token_id: book.yes, book.no.token_id: book.no}, cfg())
    assert account.halted
    assert any("HALTED" in note for note in notes)
    assert account.lots[book.yes.token_id].qty == Decimal("10")


def test_unknown_config_key_is_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"bankroll": "10", "not_a_setting": 1}')
    try:
        Config.load(path)
    except ValueError as exc:
        assert "not_a_setting" in str(exc)
    else:
        raise AssertionError("unknown key was accepted")
