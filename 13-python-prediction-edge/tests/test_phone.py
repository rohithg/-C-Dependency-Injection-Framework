import json
import subprocess
from pathlib import Path

from decimal import Decimal

from edge.crypto15m import settlement_up_prob, sigma_1m, taker_fee_dollars
from edge.fees import polymarket_taker_fee

PHONE = Path(__file__).resolve().parents[1] / "phone"


def test_phone_page_runs_in_the_browser_and_does_not_send_orders():
    page = (PHONE / "index.html").read_text()
    script = (PHONE / "edge.js").read_text()
    assert 'name="viewport" content="width=device-width' in page
    assert 'id="check"' in page and 'id="refresh"' in page
    assert "does not send orders" in page
    assert "server.py" not in page and "/api/" not in page
    assert "Place order" not in page and "Buy now" not in page
    assert "gamma-api.polymarket.com" in page
    assert "api.exchange.coinbase.com" in page
    assert "kalshi.com" not in page and "kalshi.com" not in script


def test_browser_math_matches_the_python_model():
    closes = [100.0 + (i % 3) * 0.02 for i in range(40)]
    sigma = sigma_1m(closes)
    assert sigma is not None
    prob = settlement_up_prob(100.0, 100.0, sigma, 1.0)
    fee = polymarket_taker_fee(Decimal("1"), Decimal("0.45"), Decimal("0.07"))
    kalshi_fee = taker_fee_dollars(0.50, 1)
    cases = {
        "closes": closes,
        "sigma": sigma,
        "prob": prob,
        "fee": float(fee),
        "kalshi_fee_is_two_cents": kalshi_fee,
    }
    node = r"""
const edge = require(process.argv[1]);
const c = JSON.parse(process.argv[2]);
const sigma = edge.sigma1m(c.closes);
const prob = edge.settlementUpProb(100, 100, sigma, 1);
const fee = edge.polyFee(0.45, 0.07);
let ask = prob - 0.025;
for (let i = 0; i < 6; i += 1) ask = prob - 0.025 - edge.polyFee(ask, 0.07);
const taken = edge.decide({ spot: 100, strike: 100, sigma, yesAsk: ask, noAsk: 0.99, rate: 0.07 });
const wide = edge.decide({ spot: 100, strike: 100, sigma, yesAsk: ask - 0.05, noAsk: 0.99, rate: 0.07 });
const early = edge.cycleDecision({ spot: 100, strike: 100, sigma, yesAsk: ask, noAsk: 0.99, rate: 0.07, secondsLeft: 840 });
if (Math.abs(sigma - c.sigma) > 1e-12) process.exit(2);
if (Math.abs(prob - c.prob) > 1e-6) process.exit(3);
if (Math.abs(fee - c.fee) > 1e-9) process.exit(4);
if (!taken || !taken.take || taken.side !== "up") process.exit(5);
if (!wide || wide.take) process.exit(6);
if (early.take || early.inWindow) process.exit(7);
process.stdout.write("ok");
"""
    result = subprocess.run(
        ["node", "-e", node, str(PHONE / "edge.js"), json.dumps(cases)],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "ok"
    assert kalshi_fee == 0.02
