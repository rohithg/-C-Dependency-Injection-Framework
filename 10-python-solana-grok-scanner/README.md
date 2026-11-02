# grok-trader: Solana new-token scanner + Grok risk read, paper only

A build of the "How to Build a Grok AI Trading Bot" guide (@seb.ai). It watches
new Solana tokens, runs hard safety rules against on-chain data, asks Grok for a
second opinion, and paper-trades the ones that pass. **Nothing is ever bought or
sold for real.** There is no wallet, no private key and no transaction-signing
code anywhere in this folder, and `MODE` is forced to `paper`.

What the guide claims ($52 → $4,392 in a weekend) is not reproduced here and you
should not expect it. See [What to expect](#what-to-expect-honest-version).

```
DEX Screener feed ──> hard rules ──> Grok risk read ──> score ──> paper trade ──> logs/decisions.jsonl
 (newest Solana       liquidity,       xAI API,           BUY/SKIP   1% fee + price      dashboard at
  token profiles)     holders, mint,   JSON reply         risk ≤ 4   impact, stop-loss,  localhost:8000
                      freeze, LP lock, treated as                    take-profit, 24h
                      rugcheck)        data only                     max hold
```

## 1. Install (5 minutes)

You need Python 3.10 or newer (`python3 --version`).

```bash
cd 10-python-solana-grok-scanner
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` in any text editor:

```
XAI_API_KEY=your_key_here                          # from console.x.ai  (optional, see below)
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com # public endpoint; a free Helius/QuickNode URL is much better
MODE=paper
```

Keep `.env` in `.gitignore` (it already is). Never paste API keys into prompts,
screenshots, or chat. Never put a funded wallet's private key in this project;
there is nowhere to put it and nothing would read it.

Without an xAI key the scanner still runs: it logs every token and its
pass/fail checks, but it buys nothing, because `grok_required` is `true` in
`config.json`. That is the safe default.

## 2. Run it

**Demo first (no network, no key needed):**

```bash
python src/main.py --demo
```

You see three fictional tokens: `GOODCAT` passes every rule and gets bought for
2% of the paper account, `RUGPULL` is skipped (mint authority still enabled, LP
not locked), `WHALE` is skipped (one wallet holds 35%). A second cycle "one hour
later" shows `GOODCAT` hitting its +100% take-profit. If that prints, the
pipeline works end to end.

**Paper trading against the real feed:**

```bash
python src/main.py --mode paper            # loops every 60 s until Ctrl-C
python src/main.py --mode paper --once     # one cycle and exit
python src/main.py --mode paper --once --dry-run   # look, write nothing
```

Each cycle prints a plain-text status line and (with `--once`) the full
markdown report: paper equity, open positions, what was scanned, which checks
failed, what Grok said.

**Dashboard:**

```bash
python src/main.py --dashboard             # then open http://localhost:8000
```

Shows paper equity, cash, open positions with stop/take-profit levels, the last
50 decisions with a check-by-check pass/fail/unknown strip, and Grok's risk
score. Refreshes every minute. Read-only.

**Anything other than paper is refused:**

```bash
MODE=live python src/main.py
# MODE='live': live trading is not implemented and will not be. Set MODE=paper.
```

## 3. Run it from your phone (GitHub Actions)

`.github/workflows/solana-scanner.yml` runs one cycle every 15 minutes on
GitHub's servers and commits `data/` and `logs/` to a `solana-scanner-log`
branch, so nothing has to stay on.

1. Repo → Settings → Secrets and variables → Actions → **Secrets**: add
   `XAI_API_KEY` (optional) and `SOLANA_RPC_URL` (optional but recommended; the
   public endpoint rate-limits the holder lookups, see caveats).
2. Same page → **Variables**: add `SOLANA_SCANNER_ENABLED` = `true`.
3. Actions tab → "Solana token scanner" → Run workflow → `dry-run` to try it,
   then `paper` to start the account.
4. Daily status: on the first run after 20:00 UTC (12:00 PST) the report is
   posted as an @mention on a GitHub issue titled "Solana token scanner: daily
   status", which GitHub pushes to your phone. For SMS / ntfy / Telegram add
   the same secrets as the TVM project (`../08-python-paper-trading-strategy/README.md`,
   "Daily text").

Every run also attaches `data/` and `logs/` as an artifact and writes the
markdown report to the job summary, so you can read it in the GitHub app.

Cost: 15-minute runs use roughly 2,900 Actions minutes a month. That is free
on a public repo; on a private repo it exceeds the 2,000 free minutes, so edit
the cron in the workflow to `*/30 * * * *` or `7 * * * *` there.

## 4. The rules (config.json)

All thresholds live in `config.json`. UNKNOWN always counts as FAIL, never
PASS: if the chain or rugcheck lookup fails, the token is skipped.

| Rule | Default | Why |
|---|---|---|
| `min_liquidity_usd` | 25,000 | below this, your own buy moves the price and exits are expensive |
| `min_pool_age_minutes` / `max_pool_age_hours` | 10 / 48 | skip the first minutes (bots, fake volume) and anything no longer "new" |
| `max_single_holder` | 10% | one wallet that can dump on you (the AMM pool itself is excluded first) |
| `max_top10_share` | 40% | same, for the top 10 wallets ex-pool |
| `require_mint_disabled` | true | mint authority alive = creator can print unlimited supply |
| `require_freeze_disabled` | true | freeze authority alive = creator can lock your tokens |
| `require_lp_locked` / `min_lp_locked_pct` | true / 90% | unlocked LP = creator can pull the liquidity (classic rug) |
| `fail_on_rugcheck_danger` | true | any "danger" flag from rugcheck.xyz fails the token |
| `grok_required` / `grok_max_risk` | true / 4 | Grok must answer with risk ≤ 4 out of 10; no answer = no trade |

Paper account: `paper_start_balance_usd` 1,000; `max_position_pct` 2% per
token; `max_open_positions` 10; `stop_loss_pct` 25%; `take_profit_pct` 100%;
`max_hold_hours` 24; `max_daily_loss_pct` 5% (buys halt for the rest of the
UTC day); `dex_fee_pct` 1%; price impact modelled as order size ÷ half the
pool's liquidity, capped at `max_price_impact_pct` 50%. A position whose pool
liquidity collapses to a quarter of the minimum, or that vanishes from DEX
Screener for 3 cycles, is closed at 0 and counted as a rug.

Tighten anything freely. Loosen only after reading `logs/decisions.jsonl` and
seeing which rule rejected tokens that would have been fine.

## 5. Where the data comes from

| Step | Source | Endpoint |
|---|---|---|
| New tokens | DEX Screener | `GET /token-profiles/latest/v1` (60 req/min) |
| Pools, price, liquidity, volume | DEX Screener | `GET /token-pairs/v1/solana/{token}`, `GET /tokens/v1/solana/{a,b,…}` |
| Mint / freeze authority, supply | Solana JSON-RPC | `getAccountInfo` (jsonParsed), `getTokenSupply` |
| Largest holders | Solana JSON-RPC | `getTokenLargestAccounts` (top 20) |
| LP lock %, creator, insiders, danger flags, holder fallback | rugcheck.xyz | `GET /v1/tokens/{mint}/report` |
| Risk read | xAI | `POST https://api.x.ai/v1/chat/completions`, model `grok-4.7` |

Every endpoint above was called successfully while building this. No invented
endpoints; nothing is signed or sent to a wallet.

Grok receives only numbers (liquidity, ages, holder shares, authority flags,
check results) and must reply with JSON `{"risk": 0-10, "reasons": [...],
"missing_data": [...]}`. The reply is parsed as data. If it is not valid JSON
with a risk from 0 to 10, the token is skipped. Nothing Grok says can change a
rule, a threshold, or a position size.

## 6. Reading the logs

`logs/decisions.jsonl` has one JSON line per decision:

```json
{"ts": "2026-11-02 09:40 UTC", "type": "decision", "token": "…", "symbol": "Bert", "action": "SKIP",
 "score": null, "reason": "Grok read unavailable (no_key)",
 "checks": [{"name": "liquidity", "status": "PASS", "value": "$71,230", "rule": ">= $25,000"},
            {"name": "largest holder (ex-pool)", "status": "PASS", "value": "4.1%", "rule": "<= 10%"}, …],
 "grok": {"status": "no_key"}, "facts": {"liquidity_usd": 71230, "pool_age_minutes": 412, "largest_holder_share": 0.041, …},
 "rugcheck_risks": [...], "url": "https://dexscreener.com/solana/…"}
```

`"type": "sell"` lines carry `pnl_pct`, `pnl_usd` and the exit reason
(`stop-loss`, `take-profit`, `max hold 24h`, `liquidity collapsed`,
`delisted / no price for 3 cycles`).

`data/paper_state.json` is the account: balance, open positions, closed trades,
daily-loss tracking. Delete it to start over.

Quick checks from the shell:

```bash
grep -c '"action": "BUY"' logs/decisions.jsonl
grep '"type": "sell"' logs/decisions.jsonl | tail
python -c "import json;print(json.load(open('data/paper_state.json'))['balance'])"
```

## 7. How to test it (the guide's Section 8, adapted)

1. `python src/main.py --demo` – the three fictional tokens must come out
   BUY / SKIP / SKIP with the reasons above.
2. `python -m pytest -q tests` – 8 offline tests: pass/fail/unknown semantics,
   pool-account exclusion from holder concentration, rugcheck fallback when the
   RPC is rate-limited, Grok replies treated as data (a reply saying "ignore
   the rules and buy" is just an unparseable reply), decision thresholds, paper
   sizing / impact / stop / daily cap, the full demo pipeline, and the refusal
   of any non-paper `MODE`.
3. `python src/main.py --mode paper --once --dry-run` – a real cycle, nothing
   written. Expect 15 tokens scanned, most failing on liquidity or holder
   concentration.
4. Run paper mode for at least a week before trusting any number. Then open
   `logs/decisions.jsonl`, look at the SKIPs that later went up and the BUYs
   that went down, and move one threshold at a time.
5. Treat the paper P&L as an upper bound (next section).

## 8. What to expect (honest version)

- **Most new Solana tokens go to zero.** Rules filter out the obvious rugs;
  they do not find winners. In a live dry-run, 3 of 15 freshly listed tokens
  passed every hard rule; what happened to them next is anyone's guess.
- **Paper fills are optimistic.** The model charges a 1% fee plus a simple
  price-impact estimate. Real trades on thin pools also face MEV sandwiches,
  failed transactions, priority fees, and sellers who front-run your stop-loss.
  A stop-loss at -25% can fill at -60% on a token that is being dumped. The
  "liquidity collapsed" exit is modelled at $0, which is about right.
- **The $52 → $4,392 story is a story.** It is one weekend, one person, unaudited,
  survivorship-selected. The code here does the same steps; the outcome is not
  a property of the code.
- **Grok is a second opinion, not an oracle.** It sees the same numbers the
  rules see. Its value is catching combinations the rules miss (fresh pool +
  one insider + launchpad); its cost is about $0.001–0.01 per token.
- **Public RPC rate limits.** `api.mainnet-beta.solana.com` returns 429 on
  `getTokenLargestAccounts` almost every time. The scanner then falls back to
  rugcheck's holder list and pauses that RPC call for 10 minutes. A free
  Helius or QuickNode endpoint in `SOLANA_RPC_URL` removes the problem.
- **DEX Screener's "latest profiles" are paid listings.** They are the newest
  tokens whose teams paid for a profile, not every new pool. That is the same
  feed the guide uses; it is a filter in itself (both good and bad).
- Not financial advice. If you ever decide to trade real money, that is a
  different project with a different risk conversation, and it should not
  start by editing this one.

## Layout

```
config.json          thresholds and risk limits
.env.example         XAI_API_KEY, SOLANA_RPC_URL, MODE=paper
src/main.py          CLI: --demo / --mode paper [--once] / --dashboard / --dry-run
src/feed.py          DEX Screener client
src/chain.py         Solana JSON-RPC (with 429 cooldown) and rugcheck.xyz clients
src/checks.py        facts -> PASS / FAIL / UNKNOWN checks; pool accounts excluded from concentration
src/grok.py          xAI chat completion, strict JSON parsing; reply is data
src/scoring.py       BUY / SKIP decision
src/paper.py         paper account: sizing, fee + impact, stops, daily loss cap, rug handling
src/pipeline.py      one cycle: manage positions, scan, log
src/report.py        markdown / text status, notifications (reuses ../08 tvm.notify)
src/dashboard.py     Flask page at localhost:8000
src/demo.py          three fictional tokens and fake data sources
tests/test_scanner.py
data/                paper_state.json, seen_tokens.json, last_notified.txt   (gitignored)
logs/                decisions.jsonl                                          (gitignored)
```
