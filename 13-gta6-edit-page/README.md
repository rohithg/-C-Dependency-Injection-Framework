# GTA 6 Edit Page kit

The two-page "GTA 6 Edit Page: AI Producer Setup Prompt" turned into something you can run:

- `SETUP_PROMPT.md`: the full prompt, transcribed. Paste it into Claude Code.
- `template/`: the page folder from section 15 (playbook, watch list, campaigns, facts,
  ideas, projects, board.csv, provenance.csv, LEARNED_RULES, takedowns, runs/, countdowns/,
  exports/, posts/).
- `page.py`: the bookkeeping the prompt asks for, so Claude Code doesn't have to improvise
  it every day. Python 3.10+, stdlib only; `cut` needs ffmpeg.

Unofficial fan-page kit, not affiliated with Rockstar Games, Take-Two, OpusClip, Kai Cenat or
IShowSpeed. Nothing here signs in, spends credits or posts.

## Start

```bash
python3 page.py init ~/sixstarsdesk --name "Six Stars Desk" --handle sixstarsdesk \
  --platforms "TikTok, YouTube Shorts, Instagram Reels, X" --timezone America/Los_Angeles
cd ~/sixstarsdesk
# install AI Producer (SETUP_PROMPT.md section 6), then:
claude          # paste SETUP_PROMPT.md and say: Follow this prompt.
```

## Commands

| Command | What it does |
|---|---|
| `init DIR --name --handle ...` | Creates the page folder and fills the placeholders you pass. |
| `log DIR --platform tiktok --format single --hook ...` | Adds a post to `board.csv`, prints its id. |
| `views DIR ID --at 24h --views N [--likes ...]` | Records a 24h / 72h / 7d checkpoint. |
| `due DIR` | Checkpoints that are due and still blank. |
| `nightly DIR` | Best and worst edit (posts under 24h are never judged). |
| `weekly DIR` | Median views by format, streamer, slot and platform; keep / cut; top and bottom 3. |
| `money --target 10000 --rate 1 --min 2 --cap 500` | Views and clips a monthly goal needs. |
| `money --rate 1 --min 2 --cap 500 --views 4000 120000` or `--board DIR` | Net payout per clip after min, cap and the 10% fee. |
| `name "Kai Cenat" "six stars"` | `2026-11-22_kai-cenat_six-stars.mp4` |
| `cut SRC 10:12:05 10:12:40 OUT --facecam x,y,w,h [--bleep 3-3.6]` | Fallback cut: 1080x1920, facecam on top, gameplay below, H.264/AAC 30 fps, muted bleeps. |

Tests: `python3 -m unittest discover -s tests`

## What you still do by hand

Claude Code + AI Producer handle finding moments, cutting, captions, SFX and exports. These
stay with you, because they need your identity, your face or your money:

| One-time (roughly an afternoon) | Daily |
|---|---|
| Create the 4 accounts (phone/email verification, names, bios, avatar you own) | Say "yes" to every edit before export and before posting |
| Install Claude Code and the AI Producer plugin, sign in to OpusClip in the browser | Post or schedule each export on each platform (AI Producer doesn't post) |
| Sign up for Content Rewards (and any other campaign sites), payout and tax details | Record your on-camera reaction / explainer takes (~20 min) |
| Read and pick campaign briefs | Paste each post link into the campaign dashboard before its deadline |
| | Reply to comments in the first hour (15 min every 2 to 3 hours) |
| | Read views at 24h / 72h / 7d off each app (`page.py due` tells you which) |
| | Handle takedown requests the same day |

At the prompt's pace (3 to 4 edits a day on 4 platforms, ~350 to 450 uploads a month), that's
about **2 to 4 hours a day** of your own time once the system runs, more in week one.

## The $10k/month math

Using the prompt's own section 12 numbers (median ~$1 per 1,000 views, 10% fee, per-clip
minimums and caps):

```
$ python3 page.py money --target 10000 --rate 1 --min 2 --cap 500
  paid views needed:          11,111,111
  views before a clip pays:   2,000
  views where a clip caps:    500,000
  clips needed if ALL capped: 22
```

So $10k needs about **11M paid views a month**, spread so that clips land between each
brief's minimum and cap: e.g. 22 clips that each hit 500k+ views, or ~110 clips at ~100k.
New pages usually get hundreds to low thousands of views per post, which is $0 under most
minimums. Pools pay less as more clippers join ($10,000 over 100M views is $0.10 per 1,000),
and launch-week campaign budgets dry up. $10k/month is a top-few-percent outcome, not a
default one; treat the first month as finding out which format gets reach, and let
`page.py money --board DIR` tell you what you actually earned.
