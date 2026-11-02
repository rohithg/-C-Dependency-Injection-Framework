# Paper crypto experiment: Claude Code + MCP tools + a $100 pretend account

**Paper money only. Not financial advice.** Learning project: no real money,
no exchange or broker account, no wallet, no API keys. Market data comes from
Kraken's public OHLC/Ticker endpoints, which need no key. If you ever ask to
switch this to real money, the answer is no: this is a paper experiment, and
the code has no path to any exchange.

## Verdict first: is it viable, and is it better than TVM?

No, and no. The prompt's rules were replayed through the real ledger and risk
gate over everything Kraken's public API returns (720 candles). Same fees,
same 25% cap, same 6-fills-a-day limit, fills at the close that was the latest
price at decision time.

**4-hour candles, last 120 days (BTC 62,723 → 77,404, +23%)**

| strategy | return | max drop | fees | fills |
|---|---|---|---|---|
| Prompt rules, 25% entries (the experiment) | **-6.2%** | -8.6% | $6.92 | 70 |
| Prompt rules, 100% entries (cap removed) | -23.7% | -30.5% | $26.54 | 70 |
| Random decisions inside the same gate (median of 20) | -11.6% | -11.7% | $16.78 | 175 |
| Buy BTC once with 25%, hold | +6.2% | -3.6% | $0.10 | 1 |
| Buy BTC once with 100%, hold | +24.5% | -11.5% | $0.40 | 1 |
| TVM (the other strategy), its 13.4%/yr backtest average over 116 days | +4.1% | | | |

**Daily candles, last 719 days (BTC 88,087 → 78,239, -11%)**

| strategy | return | max drop | fees | fills |
|---|---|---|---|---|
| Prompt rules, 25% entries | **-4.0%** | -13.5% | $12.33 | 124 |
| Prompt rules, 100% entries | -23.6% | -46.3% | $45.76 | 124 |
| Random decisions inside the same gate (median of 20) | -15.2% | -21.9% | $16.58 | 175 |
| Buy BTC once with 25%, hold | -4.7% | -16.1% | $0.10 | 1 |
| Buy BTC once with 100%, hold | -18.7% | -53.1% | $0.40 | 1 |
| TVM, 13.4%/yr backtest average over 699 days | **+27.2%** | -22.8% worst ever | | |

What the numbers say:

- **Fees decide it.** 0.4% per fill on a $100 account is $0.10 per $25 entry,
  $0.20 per round trip, and the rules trade about every other day. Seven to
  twelve dollars of a hundred went to fees. No signal this simple earns that
  back; the 17–35% win rate shows the stop at -3% is hit far more often than
  the +6% target on 4-hour crypto noise.
- **Beating random is not the bar; beating doing nothing is.** The rules did
  beat the random agent (fewer fills, so fewer fees), and lost to buying once
  and holding in both windows.
- **The 25% cap limits losses, not the fee drag.** It also caps the upside at
  a quarter of the asset's move, so even a perfect call on a +23% BTC run
  earns +6%.
- **TVM is better by every measure**: +27% vs -4% over the same two years,
  with a worst-ever drawdown of -23% against 30+ years of evidence, and it
  trades a few times a year instead of a few times a week.
- **An LLM reading the same candles does not change this.** Claude Code
  following the prompt will make the same decisions as the rule agent, plus
  occasional arithmetic slips. The information in 60 four-hour candles is the
  same whoever reads it.

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
paperbot/strategy.py     the trading prompt's rules as functions (shared by the rule agent and the backtest)
paperbot/agent.py        offline rule agent that drives the same MCP tools over stdio (no Claude needed)
prompts/trading_prompt.md  the prompt Claude Code gets each round (stand-in for "Prompt 02", see below)
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

A round from this build, rule agent, live Kraken data:

```
tools: buy, get_account, get_candles, hold, sell_all
BTC close 77,403.90 vs SMA20 77,578.82, RSI 54, 24h -0.6%
ETH close 2,270.29 vs SMA20 2,256.98, RSI 62, 24h +0.3%
SOL close 93.42 vs SMA20 95.09, RSI 34, 24h -1.3%
2026-11-02 17:02:17 UTC  agent=rules  HOLD  [ok] no entry qualifies (...)
equity $100.00 (+0.00%), fees $0.00, max drop 0.0%, refused 0, holds 1  ->  dashboard.html
```

## Run it every 4 hours on your computer

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

The request said "paste Prompt 02 here" but Prompt 02 was not included, so
`prompts/trading_prompt.md` is a stand-in: SMA20 / RSI14 / 24-hour momentum
entries with a -3% stop and +6% target, 25% of equity per entry. The rule agent
and the backtest implement exactly that, so replacing the prompt and re-running
`backtest.py` (after mirroring the new rules in `paperbot/strategy.py`) is how
to test a different idea. Keep steps 5 and 6 of the prompt (one write tool per
round, never retry a refused order) whatever else you change.

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
