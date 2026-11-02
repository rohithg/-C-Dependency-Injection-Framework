# Paper crypto experiment: Claude Code + MCP tools + a $100 pretend account

**Paper money only. Not financial advice.** Learning project: no real money,
no exchange or broker account, no wallet, no API keys. Market data comes from
Kraken's public OHLC/Ticker endpoints, which need no key. If you ever ask to
switch this to real money, the answer is no: this is a paper experiment, and
the code has no path to any exchange.

## Verdict first: is it viable, and is it better than TVM?

No, and no. Prompt 02 ("grow a $100 account; one position; never risk more
than 25%; take profit or cut the loss rather than holding through a
reversal; here are 24 hourly bars") is discretionary, so two concrete readings
of it were replayed through the real ledger and risk gate over everything
Kraken's public API returns: the momentum reading the offline agent uses
(buy the strongest 24h mover while it is still rising near its highs, cut at
-2%, take at +4%, sell a 6h reversal) and the opposite one (buy the hardest
24h faller near its lows, sell a +2% bounce, cut at -3%). Same fees, same cap,
fills at the close that was the latest price at decision time.

**Hourly bars, a round every hour, last 30 days (all Kraken keeps; BTC -9%)**

| strategy | return | max drop | fees | fills | win rate |
|---|---|---|---|---|---|
| Prompt 02, momentum reading, 25% entries (the experiment) | **-6.3%** | -6.3% | $2.42 | 25 | 0% |
| Prompt 02, momentum reading, 100% entries (cap removed) | -23.1% | -23.1% | $8.88 | 25 | 0% |
| Opposite reading: buy the 24h dip, sell the +2% bounce | -5.7% | -5.9% | $3.76 | 39 | 42% |
| Random decisions inside the same gate (median of 20) | -15.8% | -15.8% | $13.89 | 152 | |
| Buy BTC once with 25%, hold | -2.4% | -3.0% | $0.10 | 1 | |
| TVM, its 13.4%/yr backtest average over the same 29 days | +1.0% | | | | |

**4-hour bars, same 24-bar logic, a round every 4 hours, last 120 days (BTC +23%)**

| strategy | return | max drop | fees | fills | win rate |
|---|---|---|---|---|---|
| Prompt 02, momentum reading, 25% entries | **-9.1%** | -10.5% | $7.22 | 74 | 22% |
| Prompt 02, momentum reading, 100% entries | -32.6% | -36.5% | $26.71 | 74 | 22% |
| Opposite reading: buy the 24h dip, sell the +2% bounce | -1.8% | -2.9% | $5.89 | 59 | 62% |
| Random decisions inside the same gate (median of 20) | -13.5% | -13.9% | $16.58 | 175 | |
| Buy BTC once with 25%, hold | +5.5% | -3.6% | $0.10 | 1 | |
| Buy BTC once with 100%, hold | +22.0% | -11.5% | $0.40 | 1 | |
| TVM, 13.4%/yr backtest average over the same 116 days | **+4.1%** | | | | |

What the numbers say:

- **Chasing 24-hour momentum in crypto loses.** Every one of the twelve
  hourly round trips lost; on 4-hour bars 22% won. A -2% stop on an asset
  that moves 1% an hour is a coin that mostly lands on "stopped out", and the
  "sell the reversal" clause sells most of the winners early.
- **Buying the dip is the better reading and still loses after fees.** 62%
  of those trades won and the account was about flat before costs; the $5.89
  in fees turned that into -1.8%. 0.4% per fill on a $25 position is $0.20 per
  round trip, which is most of a +2% bounce on $25.
- **Beating random is not the bar; beating doing nothing is.** Both readings
  beat the coin-flip agent (fewer fills, fewer fees) and lost to buying once
  and holding in both windows.
- **The 25% cap limits losses, not the fee drag,** and it caps the upside at a
  quarter of the asset's move: a perfect call on BTC's +23% run earns +5.5%.
- **TVM is better by every measure:** positive in both windows, a worst-ever
  drawdown of -23% against 30+ years of evidence, a few trades a year rather
  than a few a day, and 0.03% ETF spreads rather than 0.4% fills.
- **An LLM reading the same 24 bars does not change this.** Claude Code will
  pick one of these two readings each round depending on how the bars look,
  plus occasional arithmetic slips. The information in 24 hourly bars is the
  same whoever reads it; when I answered the prompt myself on live data the
  honest answer was "hold, the reason to do anything is weak", which is also
  what the agent said.

Reproduce: `python backtest.py` (about 45 s, two Kraken calls per symbol).

So why build it? Because the mechanics are worth learning: an MCP server with
tools a model can call, a risk gate that refuses bad orders before any ledger
is touched, an audit log of every decision including holds and refusals, and
a dashboard that shows fees and drawdown instead of just P&L. Those pieces
transfer to anything; the trading rules do not.

## What is in the folder

```
paperbot/kraken.py       public OHLC + Ticker (no key); newest, still-forming candle dropped
paperbot/ledger.py       $100 paper ledger + RiskGate; every decision logged to state/decisions.jsonl
paperbot/server.py       MCP server (mcp 2.x MCPServer): get_candles, get_account, buy, sell_all, hold
paperbot/strategy.py     two concrete readings of Prompt 02 (momentum, dip) shared by the rule agent and the backtest
paperbot/agent.py        offline rule agent that drives the same MCP tools over stdio (no Claude needed)
prompts/trading_prompt.md  Prompt 02 verbatim, plus the tool-calling harness paragraph
run_round.py             one round: Claude Code if installed, else the rule agent; then rebuilds the dashboard
build_dashboard.py       -> dashboard.html (equity, fees, biggest drop, refusals, every decision + reason)
backtest.py              the viability test above
.mcp.json                registers the server with Claude Code for this folder
tests/                   gate, ledger, strategy, server-over-stdio, dashboard (offline)
state/                   ledger.json, decisions.jsonl, rounds.jsonl   (gitignored)
```

Risk gate (`paperbot/ledger.py`), applied to every write tool before the
ledger changes:

| rule | implementation |
|---|---|
| one position at a time | `buy` refused while a position is open |
| single entry ≤ 25% of equity | `buy` refused above 25% of marked equity |
| no leverage, no shorting | `buy` refused if notional + fee exceeds cash or `usd_amount ≤ 0`; there is no sell-short tool |
| 0.4% fee on every fill | charged on buys and sells, tracked as `fees_paid` |
| ≤ 6 fills per day | `buy` and `sell_all` refused after the sixth fill in a UTC day |
| stop buying below 50% of start | `buy` refused when equity < $50; `sell_all` still allowed |

Fills use Kraken's last public trade price at the moment of the call.
Refusals are returned to the model as data (`status: "refused"`,
`refused_because: ...`) and logged like any other decision.

## Install

```bash
cd 11-python-claude-mcp-crypto-paper
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                          # mcp 2.x, requests, pytest
python -m pytest -q tests                                # 6 offline tests
```

## Register the MCP server with Claude Code

`.mcp.json` in this folder already declares the server, so Claude Code picks
it up automatically when started from this directory (it will ask once to
approve a project-scoped server). To register it explicitly instead:

```bash
claude mcp add paper-crypto -s project -e PAPERBOT_STATE_DIR=state -- python -m paperbot.server
claude mcp list                                          # should show paper-crypto
```

Inside Claude Code, `/mcp` lists the five tools. Nothing in them needs a key.

## Run one round

```bash
python run_round.py                  # Claude Code if `claude` is on PATH and logged in, else the rule agent
python run_round.py --agent rules    # force the offline rule agent (same tools, same rules)
python run_round.py --agent claude   # force Claude Code
open dashboard.html                  # macOS; or just open the file in a browser
```

With Claude Code, the round is `claude -p <prompt> --mcp-config .mcp.json
--allowedTools mcp__paper-crypto__* --output-format json --max-turns 15`,
so only these five tools are available to it. The rule agent connects to the
same server over stdio and follows `prompts/trading_prompt.md` literally, so
the two can be compared decision for decision in `state/rounds.jsonl`.

## It already runs every 4 hours

`.github/workflows/crypto-paper.yml` runs one round on GitHub's servers every
4 hours with the offline rule agent, keeps the account on the
`crypto-paper-log` branch, and sends "Crypto paper bot: daily status" on the
first run after 20:00 UTC. No Claude login and no key. Set the repository
variable `CRYPTO_PAPER_ENABLED` to `false` to pause it.

To run the same round on your own computer instead:

**macOS / Linux (cron):** `crontab -e`, then add one line (edit the path):

```
0 */4 * * *  cd /path/to/11-python-claude-mcp-crypto-paper && .venv/bin/python run_round.py >> state/cron.log 2>&1
```

**macOS (launchd, survives sleep better than cron):** save as
`~/Library/LaunchAgents/com.paperbot.round.plist`, edit the two paths, then
`launchctl load ~/Library/LaunchAgents/com.paperbot.round.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.paperbot.round</string>
  <key>ProgramArguments</key><array>
    <string>/path/to/11-python-claude-mcp-crypto-paper/.venv/bin/python</string>
    <string>run_round.py</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/11-python-claude-mcp-crypto-paper</string>
  <key>StartInterval</key><integer>14400</integer>
  <key>StandardOutPath</key><string>/path/to/11-python-claude-mcp-crypto-paper/state/launchd.log</string>
  <key>StandardErrorPath</key><string>/path/to/11-python-claude-mcp-crypto-paper/state/launchd.log</string>
</dict></plist>
```

**Windows (Task Scheduler), from an admin PowerShell:**

```powershell
schtasks /Create /SC HOURLY /MO 4 /TN "paperbot round" /TR "cmd /c cd /d C:\path\to\11-python-claude-mcp-crypto-paper && .venv\Scripts\python run_round.py >> state\cron.log 2>&1"
```

Each run appends to `state/rounds.jsonl` and rewrites `dashboard.html`. With
Claude Code each round costs a few cents of API usage on your Anthropic
account; the rule agent costs nothing. Kraken's public endpoints allow about
one request per second; a round makes four.

## About the trading prompt

`prompts/trading_prompt.md` is Prompt 02 as given, followed by one paragraph
telling the model how to act through the tools (call `get_account`, 24 hourly
candles per symbol, exactly one write tool, never retry a refused order). The
prompt is discretionary, so the offline agent and the backtest use the
momentum reading in `paperbot/strategy.py`; the dip-buying reading is there
too and is what `backtest.py` reports as "opposite reading". To test a
different idea, change the thresholds or add a third reading and re-run
`python backtest.py`.

A live round with the rule agent on 2026-11-02:

```
BTC 77,386.20: 24h -0.6%, last 6h -0.6%, 14% of the 24h range
ETH 2,266.22: 24h +0.2%, last 6h -0.8%, 30% of the 24h range
SOL 93.28: 24h -1.2%, last 6h -0.9%, 21% of the 24h range
HOLD  nothing is trending enough to pay a 0.8% round trip (...); weak reason to do anything, so cash
```

## Safety

- No exchange or wallet client exists in this code; the only network calls
  are two public Kraken GET endpoints and, with Claude Code, your own Anthropic
  account.
- `.mcp.json` passes no secrets. `state/` is gitignored.
- In a round, only the five paper tools are pre-approved (`--allowedTools`)
  and only this server is loaded (`--strict-mcp-config`); in non-interactive
  `-p` mode anything else Claude tries is denied rather than asked about.
- If you ask to connect this to real money: stop. This is a paper experiment,
  and the backtest above is the reason it should stay one.
