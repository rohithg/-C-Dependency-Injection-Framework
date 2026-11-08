# Structural edge on Polymarket and Kalshi

This bot does not pick winners. It buys packages that pay **at least $1** when the two venues are offering that package for less than $1 after fees. If the discount is not there, it does not trade. A scan that says nothing cleared the bar is the bot working.

Paper mode is the default. It needs no keys and sends no orders. Live mode lifts only the two packages whose worst case really is $1, and only after three separate switches are on.

## The edge

**Polymarket complete set.** YES and NO are different order books. One of each merges back to $1 (or you just hold both to resolution; one of them pays $1). Buy both when the asks, the taker fees, a one-tick haircut, and the merge gas still cost less than $1. The mirror, minting a pair and selling both into the bids, is paper-only: minting is an on-chain split and live mode does not do it.

Fees are why a "2 cent" dislocation is usually not a trade. Polymarket's taker fee is `shares × rate × p × (1 − p)` (rate 0.07 on crypto, 0.04 to 0.05 on most other categories, 0 on geopolitics). At 49 cents that fee is about 1.75 cents **per leg**. Makers pay nothing on taker-only markets, which is why the bot also rests bids.

**Maker quotes, paper only.** When the best YES bid and the best NO bid add up to less than $1 minus the minimum edge, the bot joins those bids (and improves one of them by a tick if the edge survives). Profit happens only if both bids are hit. A later snapshot fills a bid only when the ask trades through it. Sitting at the touch is not counted as a fill. Live mode does not rest these quotes: a quote left up for a whole polling interval can be picked off on one side, and this process has no fill socket to pull it.

**Kalshi strike ladder.** A single Kalshi binary cannot be arbed against itself. Its NO ask is one minus its YES bid, so the two sides are the same book. Across a "greater than" ladder the lower strike is the easier event: the higher strike implies it. Buying YES on the easier strike and NO on the harder strike pays $1 in both wings and $2 if the result lands between them. "Less than" ladders are the same shape with the easy end at the higher cap. Buckets (`between`) are skipped. So is `mutually_exclusive`: on Kalshi that means **at most** one market resolves YES, not exactly one, so buying every YES in the event can still go to zero.

**Cross-venue basis, opt-in.** A `links` file names one Polymarket condition and one Kalshi ticker that you have already decided are the same question. The bot buys the cheap YES and the other venue's NO. This is **not** risk-free. The rulebooks differ, and live trading leaves it off unless `live_basis` is true.

## What a pass will not do

It will not copy a wallet, fade a price, or trade because a model likes an outcome. Those are different products. The sibling [copy trader](../09-python-polymarket-copy-trader/) is the honest version of the copy idea, including the part where copying the leaderboard loses money.

Taker dislocations are competed for by faster bots. A scan every few seconds will often find none. That is the correct result, not a bug. The ladder and the maker quote are the two that a process this slow can still stand behind.

## Run it

```bash
cd 13-python-prediction-edge
pip install -r requirements.txt
python -m pytest -q

python run.py replay          # recorded books, no network: equity goes from $1000 to $1012.17
python run.py scan            # live public books, throwaway paper account, no orders
python run.py paper           # one live pass, saved to state/account.json
python run.py paper --loop    # keep going until you stop it, or the daily-loss halt trips
```

`scan` prints the closest books even when the edge is negative, so you can see fees eating a gross discount. Copy `config.example.json` to `config.json` to change size, the Kalshi series, or the thresholds. A key the bot does not know is rejected on load.

The replay's three steps are the whole strategy in miniature:

1. YES and NO both offered at 40 cents. Buy 30, merge, **+$6**.
2. Resting 46/46 bids get traded through. Both fill, merge, **+$0.80**.
3. "Above 100" is offered at 40 cents while "above 110" is bid at 70 cents. Buy the easy YES and the hard NO. Worst case pays $20, cost is $14.63 after Kalshi fees, **+$5.37** locked. Cash does not go up. The $20 sits in a package until the event resolves.

## Risk limits

| Control | Default | What it stops |
|---|---|---|
| `min_edge` | 1 cent a share | Trades that are only rounding |
| `max_spread` | 10 cents a side | Maker quotes in a book too wide to fill both ways |
| `min_profit` | 5 cents | Dust after gas |
| `latency_haircut` | 0.1 cent a leg | Deciding on a price that will be gone |
| `max_order_notional` | $25 | One package larger than this |
| `max_market_notional` | $50 | One market larger than this |
| `max_event_notional` | $75 | One game or one ladder larger than this. Props in the same game move together |
| `max_open_notional` | $250 | Locked packages plus quotes plus loose shares |
| `max_daily_loss` | $25 | New risk after the day's equity is down this much |
| `max_leg_loss` | 2 cents a share | How far a broken pair may be completed by crossing |
| `max_unpaired_notional` | $20 | Maker inventory held while waiting for the other bid |
| `max_book_age_ms` | 20 seconds | A book that was read too long ago |

A file at `state/KILL` halts the account: open quotes come off, nothing new is added. Repair of a pair that is already over the unpaired cap still runs, because completing it reduces risk.

Maker inventory under that cap is held. The bot keeps the light side's bid and stops bidding for more of the side it already holds. It does not cross the spread to flatten a small one-sided fill. That cross is what gives the edge back.

## Live orders

Live mode sends two kinds of taker order: buy both Polymarket tokens, or buy the two Kalshi ladder legs. It then merges a Polymarket pair in the ledger (the on-chain merge is optional; holding both to resolution pays the same $1) and locks a ladder package at its $1 floor.

All three have to be true or the command prints why it refused:

- `python run.py live --live`
- `"live_enabled": true` in the config
- `EDGE_LIVE_OK=I_UNDERSTAND_THIS_CAN_LOSE_MONEY`

Kalshi uses `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` (RSA-PSS or Ed25519, the key the platform issued). Orders are immediate-or-cancel on `POST /trade-api/v2/portfolio/events/orders`. A NO buy is an ask on the YES book at one minus the NO price. Polymarket uses `POLY_PRIVATE_KEY` and `py-clob-client`, which is not installed by default (`pip install py-clob-client`); without it, Polymarket live orders are skipped and Kalshi orders still go if that side is configured.

If one leg fills and the other does not, the bot tries once to complete the pair inside `max_leg_loss`. If it cannot, it halts and leaves the position in `state/live.json`. It does not keep firing.

## Layout

```
edge/strategy.py    complete set, maker quote, ladder, basis
edge/fees.py        Polymarket schedule and Kalshi centicent rounding
edge/paper.py       merges, locked packages, maker fills, repair
edge/polymarket.py  Gamma metadata and the CLOB book
edge/kalshi.py      strike ladders and the request signature
edge/live.py        gated taker submission
edge/risk.py        the limits above
run.py              scan, paper, replay, live
examples/replay.json
```

## Caveats

- The top of the book is the only size that is taken. A limit at a deeper price would also have to lift everything in front of it, and those shares can vanish.
- Paper fills both taker legs against one snapshot. Live can get one leg only. The halt exists for that case. Real fills will be worse than the paper ones, not better.
- Ladder packages tie up cash until resolution. Equity counts their $1 floor so the locked profit is visible. That cash is not spendable, and the extra $1 in the middle band is not marked.
- Kalshi's fee multiplier is 1 unless a series says otherwise. Check the current schedule before raising size. Polymarket reads `feeSchedule.rate` from Gamma.
- Nothing here is investment advice. The account in `replay` is a scripted book, and a live scan that finds no trade is the usual outcome.
