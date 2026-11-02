# Basis

A reading desk for prediction markets. Paste a Polymarket link. Basis loads the live market and writes a one-page brief: Pass or Watch, what a $100 buy pays, the risks, and an exit. It does not hold money, place orders, or connect a wallet.

This is the same job as a screenshot analyzer for Polymarket. The difference is the stance. The price is the forecast of the people already in the market. Basis has no news they lack, so it will not invent a pick and call it an edge.

## Run it

```bash
cd 12-python-basis-desk
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:8765

Paste a link such as `https://polymarket.com/event/...`, or a question. The left column is the busiest open markets right now. **Save a paper note** keeps the stance in this browser only.

```bash
python -m pytest -q tests
```

## What a reading will and will not do

Pass when the market is closed, inside 6 hours of the end, thin (under $2,000 of liquidity or $1,000 of volume today), wider than a 4¢ spread, or already decided (a side under 8¢ or over 92¢).

Watch when those checks pass. The headline states the crowd's price and the payoff. It is not a separate prediction.

The exit line is a paper rule: a fixed dollar size, out if the price moves 10¢ against you, or when 6 hours remain. Nothing in the app sends that order.
