# The structural edge

Four packages pay at least $1 no matter how the event lands. The functions in `edge/strategy.py` say when the book is offering one of them for less than that, after fees. There is no order router, no account, and no loop.

## Complete set

On Polymarket, YES and NO of the same market are separate books, and one of each is worth $1.

```
buy both when  ask(YES) + ask(NO) + taker fees  <  $1
sell both when bid(YES) + bid(NO) − taker fees  >  $1
```

The taker fee is `shares × rate × p × (1 − p)`. Rate is 0.07 on crypto, 0.04 to 0.05 on most other categories, and 0 on geopolitics. Makers pay nothing on taker-only markets. At 49 cents the crypto fee is about 1.75 cents **per leg**, so a 2-cent gap is a loss.

A Kalshi binary cannot do this. Its NO ask is one minus its YES bid, so the two sides are the same book and the sum of the asks is just the spread.

## Outcome basket

On a Polymarket event where the rules make exactly one outcome win, one YES of every outcome pays $1. That list includes the "Other" bucket when the rules have one.

```
buy every YES when  sum of asks + taker fees  <  $1
```

A list that leaves a name out pays $0 when the missing name wins. The same screen is why a group of placeholder markets that are not taking orders is not a basket: the missing name is still in the rules.

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
from edge.strategy import complete_set_buy, ladder_opportunities, maker_quote, yes_basket

trade = complete_set_buy(market, Config(min_edge="0.01", min_profit="0.05"))
basket = yes_basket(outcomes, Config(min_edge="0.01", min_profit="0.05"))
# trade is None, or an Opportunity with size, net_profit, and two legs
```

Each function sizes to the touch only, and stops at `max_order_notional`. `latency_haircut` is added to a taker price before the fee is computed, so the decision is not made on a price that is already gone.

```bash
pip install -r requirements.txt
python -m pytest -q
```

## Phone

`phone/index.html` is the paper screen for a phone browser. It does not use Krypt Trader and it does not need a computer left on. The page reads Polymarket's 15-minute Up/Down books and Coinbase's 1-minute prices itself, and it reads the Millennium Prize asks the same way. A take is still one contract in the last minute, and only when the edge after the fee is 2¢ to 3¢. Nothing on the page sends an order.

`paper/15m-week-poly.json` is that rule on one week of those windows, Nov 1–8, 2016 windows, 85 trades. The entry there is the last trade print. The phone uses the ask.

`paper/2026-11-08-copy.json` copies one open position from each of the week's top Polymarket wallets, $25 at the ask. Wallets whose book is outside 15¢ to 85¢, under $500, or hedged on both sides are skipped. Kalshi's public leaderboard hides those books, so nothing was copied there.

`paper/2026-11-08-50-to-500.json` was a $50 Liverpool longshot and is cancelled. `paper/2026-11-08-edge.json` puts $19.57 of that $50 into the two baskets still at least 1¢ under $1 after fees: another 16 shares of the 2030 World Cup final, and 5 shares of the Maduro sentence brackets. Together they lock $1.43. The rest of the $50 stays cash.

`paper/2026-11-08-scan.json` is the next pass: 103,814 Kalshi ladder pairs and 1,163 Polymarket YES+NO books, none of them 1¢ under $1 after fees. Maduro's smallest ask had grown to 15.9, so `paper/2026-11-08-maduro-add.json` buys the other 10.9 shares and locks another $0.39.
