# The structural edge

Three packages pay at least $1 no matter how the event lands. The functions in `edge/strategy.py` say when the book is offering one of them for less than that, after fees. There is no order router, no account, and no loop.

## Complete set

On Polymarket, YES and NO of the same market are separate books, and one of each is worth $1.

```
buy both when  ask(YES) + ask(NO) + taker fees  <  $1
sell both when bid(YES) + bid(NO) − taker fees  >  $1
```

The taker fee is `shares × rate × p × (1 − p)`. Rate is 0.07 on crypto, 0.04 to 0.05 on most other categories, and 0 on geopolitics. Makers pay nothing on taker-only markets. At 49 cents the crypto fee is about 1.75 cents **per leg**, so a 2-cent gap is a loss.

A Kalshi binary cannot do this. Its NO ask is one minus its YES bid, so the two sides are the same book and the sum of the asks is just the spread.

## Strike ladder

On a Kalshi "greater than" ladder, a higher strike implies every lower strike. Buy YES on the easier (lower) strike and NO on the harder (higher) one.

| Result | Payout |
|---|---|
| Below the easy strike | $1 |
| Between the two strikes | $2 |
| Above the hard strike | $1 |

Buy it when `ask(easy YES) + ask(hard NO) + fees < $1`. A "less than" ladder is the same shape with the easy contract at the higher cap. The code checks every easier strike against the harder strike with the highest bid, which is the cheapest NO and also the smaller fee.

Kalshi's taker fee is `ceil(0.07 × contracts × p × (1 − p))` to the next centicent.

## Maker quote

When both Polymarket spreads are 10 cents or tighter, and the best bids still add up to less than $1 minus the minimum edge, rest a bid on each side (one tick better if the edge survives). The profit is real only if **both** bids are hit. A wide book is skipped: the only way both of those bids fill is if the market falls onto one of them.

## Calling it

```python
from edge.config import Config
from edge.strategy import complete_set_buy, ladder_opportunities, maker_quote

trade = complete_set_buy(market, Config(min_edge="0.01", min_profit="0.05"))
# trade is None, or an Opportunity with size, net_profit, and two legs
```

Each function sizes to the touch only, and stops at `max_order_notional`. `latency_haircut` is added to a taker price before the fee is computed, so the decision is not made on a price that is already gone.

```bash
pip install -r requirements.txt
python -m pytest -q
```
