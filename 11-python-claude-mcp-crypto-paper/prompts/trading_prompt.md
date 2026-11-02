You are running one round of a paper-money crypto experiment. $100 of pretend money, no real exchange, no keys. You may only act through the `paper-crypto` MCP tools. Do not ask the user anything. Finish the round in one pass.

Procedure:

1. Call `get_account`.
2. For each of BTC, ETH and SOL call `get_candles(symbol, "4h", 60)`.
3. From the closes of each symbol compute: the 20-candle simple moving average (SMA20), the 14-candle RSI, and the 24-hour change (last close divided by the close 6 candles earlier, minus 1).
4. Decide, using only these rules:
   - If there is **no open position**: among the symbols whose last close is above SMA20, whose RSI is between 50 and 70, and whose 24-hour change is above +1%, pick the one with the largest 24-hour change and call `buy` for **25% of equity** (round down to cents). If no symbol qualifies, call `hold`.
   - If there **is an open position**: call `sell_all` if its last close is below SMA20, or its unrealized return is at or below -3%, or at or above +6%. Otherwise call `hold`.
5. Call exactly one write tool (`buy`, `sell_all` or `hold`) per round, with a one-line `reason` that names the numbers you used (for example "BTC close 77,300 > SMA20 76,100, RSI 58, 24h +2.1%").
6. If the gate refuses an order, do not retry with different numbers; call `hold` with the refusal text as the reason.

Rules you cannot change: one position at a time, at most 25% of equity per entry, no leverage, no shorting, 0.4% fee on every fill, at most 6 fills per day, no new buys once equity is below $50. End your reply with one line: ACTION, symbol (if any), and the reason.

(Stand-in for "Prompt 02", which was not included in the request. The built-in rule agent in `paperbot/agent.py` implements exactly these rules, so Claude Code and the offline agent can be compared like for like. Replace this file with your own prompt; keep step 5 and 6.)
