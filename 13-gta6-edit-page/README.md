# GTA 6 Edit Page kit

The two-page "GTA 6 Edit Page: AI Producer Setup Prompt" turned into something you can run:

- `SETUP_PROMPT.md`: the full prompt, transcribed. Paste it into Claude Code.
- `template/`: the page folder from section 15 (playbook, watch list, campaigns, facts,
  ideas, projects, board.csv, provenance.csv, LEARNED_RULES, takedowns, runs/, countdowns/,
  exports/, posts/).
- `page.py`: the bookkeeping the prompt asks for, so Claude Code doesn't have to improvise
  it every day. Python 3.10+, stdlib only; `cut` needs ffmpeg.
- `clip.py` + `clipper/`: a local, free clipping pipeline (find moments, cut, auto-frame,
  caption, clean audio) and Clip Studio, a review page for approving drafts. See below.

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

## clip.py: the local clipping pipeline

Does the "find, cut, frame, caption, clean, prep" part locally and free, so the page doesn't
depend on AI Producer's beta access or credits. AI Producer is still the better editor for
motion graphics and reference styles; use either per edit.

```bash
pip install -r requirements.txt            # plus ffmpeg on PATH
python3 clip.py auto ~/sixstarsdesk "https://www.youtube.com/watch?v=<VOD>" \
  --section 10:00:00-10:30:00 --credit "Kai Cenat (YouTube)" --top 5 --chat
python3 clip.py studio ~/sixstarsdesk      # http://127.0.0.1:8765
```

| Step | What it does | Open-source project |
|---|---|---|
| fetch | Downloads a VOD or just one section of an 11 h stream | yt-dlp, ffmpeg |
| scan | Loudness spikes over the streamer's own baseline, streamed over the whole VOD | ffmpeg, NumPy |
| scan | Chat replay bursts (messages and LUL/KEKW/💀 per 10 s), `--chat` | chat-downloader |
| scan | Transcribes only the candidates; scores hype phrases ("six stars", "busted", "no way"); skips slurs | faster-whisper (Whisper, CTranslate2, Silero VAD) |
| scan | Timestamps from VOD comments/chapters, `--timestamps file.txt` | (built in) |
| render | Cut snapped to sentence edges, 20 to 60 s, cold open (payoff repeated in the first second) | ffmpeg |
| render | Auto layout: finds the facecam and stacks it over gameplay, follows a moving face for IRL footage, or blurred-fill for gameplay only | OpenCV + YuNet face detector |
| render | Punch-in zoom on the peak | ffmpeg zoompan |
| render | Word-by-word captions (one highlight colour, profanity masked), hook card, credit line, all outside the top and bottom 10% | libass via ffmpeg |
| render | Rumble cut, denoise, two-pass loudness to -14 LUFS, profanity beeped | ffmpeg afftdn + loudnorm |
| render | 1080x1920 H.264/AAC 30 fps (TikTok, Shorts, Reels, X), frame sheet, poster | ffmpeg |
| studio | Watch drafts, edit hook/credit (re-renders text only), approve, reject | (built in) |
| studio | Approve writes `exports/date_streamer_slug.mp4`, `posts/<slug>.md`, a `provenance.csv` row; "Mark posted" adds the post to `board.csv` | (built in) |

Facecam detection is automatic; if it ever picks the wrong box, pass `--facecam x,y,w,h`
(measure it once per streamer and keep it in `watchlist.md`). `--model small.en` transcribes
more accurately than the default `base.en` at about 3x the time.

Tests: `python3 -m unittest discover -s tests` (the end-to-end test builds a synthetic stream
with a facecam and a loud reaction, and needs espeak-ng).

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
