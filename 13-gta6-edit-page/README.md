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
- `desk.py`: runs the whole page unattended and for free: watches the streamers, clips,
  approves within quality gates, posts to TikTok, YouTube, Instagram and X at your slots,
  reads view numbers and sends you the nightly report. See "desk.py: fully automatic, free".

Unofficial fan-page kit, not affiliated with Rockstar Games, Take-Two, OpusClip, Kai Cenat or
IShowSpeed. It only posts to accounts you connect yourself with `desk.py login`, and nothing
in it costs money: no paid APIs, no credits.

## Start

```bash
python3 page.py init ~/sixstarsdesk --name "Six Stars Desk" --handle sixstarsdesk \
  --platforms "TikTok, YouTube Shorts, Instagram Reels, X" --timezone America/Los_Angeles
cd ~/sixstarsdesk
# free, fully automatic: see "desk.py" below (desk.py login ..., desk.py doctor, desk.py cron)
# or the prompt's original route (AI Producer uses paid OpusClip credits):
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
python3 clip.py countdown ~/sixstarsdesk   # or the "Build top-5 countdown" button in the studio
python3 clip.py studio ~/sixstarsdesk      # http://127.0.0.1:8765
```

| Step | What it does | Open-source project |
|---|---|---|
| fetch | Downloads a VOD or just one section of an 11 h stream | yt-dlp, ffmpeg |
| scan | Loudness spikes over the streamer's own baseline, streamed over the whole VOD | ffmpeg, NumPy |
| scan | Chat replay bursts (chatters and LUL/KEKW/💀 per 10 s; each chatter counts once, so one spammer can't fake a moment), `--chat` | chat-downloader |
| scan | YouTube's "Most replayed" graph for the VOD, when it has one: the parts viewers rewind to | yt-dlp |
| scan | Transcribes only the candidates; scores hype phrases ("six stars", "busted", "no way"); scores down sub/donation thank-yous and retold stories; skips slurs | faster-whisper (Whisper, CTranslate2, Silero VAD) |
| scan | Timestamps from VOD comments/chapters, `--timestamps file.txt` | (built in) |
| scan | Hook suggestions from the section 7 templates, built only from words heard on stream ("Kai vs 6 stars", a direct quote); pick one with a click in the studio | (built in) |
| render | Cut snapped to sentence edges and never mid-word, 20 to 60 s, cold open (payoff repeated in the first second) | ffmpeg |
| render | Dead air removed: quiet gaps with nobody talking are tightened to 0.3 s, never near the peak or over loud game action (`--no-jumpcuts` to keep) | ffmpeg, NumPy |
| render | Auto layout: finds the facecam and stacks it over gameplay, follows a moving face for IRL footage, or blurred-fill for gameplay only | OpenCV + YuNet face detector |
| render | Punch-in zoom on the peak | ffmpeg zoompan |
| render | Word-by-word captions (one highlight colour, the active word pops, profanity masked), hook card, credit line, all outside the top and bottom 10% | libass via ffmpeg |
| render | Rumble cut, denoise, profanity beeped; loudness measured and corrected until the export is within 0.5 LU of -14 LUFS, peaks limited to -1.5 dB | ffmpeg afftdn, ebur128, alimiter |
| countdown | Best drafts played #5 to #1, about 11 s each around the peak: title card ("5 craziest GTA 6 stream moments (#1 is 6 stars)"), numbered headers, captions and a credit per segment; shows up in the studio to approve like any clip | ffmpeg, libass |
| render | 1080x1920 H.264/AAC 30 fps (TikTok, Shorts, Reels, X), frame sheet, poster | ffmpeg |
| studio | Watch drafts, edit hook/credit (re-renders text only), approve, reject | (built in) |
| studio | Approve writes `exports/date_streamer_slug.mp4`, `posts/<slug>.md`, a `provenance.csv` row; "Mark posted" adds the post to `board.csv` | (built in) |

Facecam detection is automatic; if it ever picks the wrong box, pass `--facecam x,y,w,h`
(measure it once per streamer and keep it in `watchlist.md`), or `--layout track` for IRL
footage where the face stays small and still for a while. `--model small.en` transcribes
more accurately than the default `base.en` at about 3x the time.

Speed: online VODs are fetched **audio-first** (an 11 h stream is ~250 MB of audio instead
of 10+ GB of video), and video is downloaded only for the sections that become clips. Clips
render in parallel (`--jobs`, default: half your cores, up to 3) and use the hardware H.264
encoder when there is one (VideoToolbox on Macs, NVENC on NVIDIA) at a high bitrate,
otherwise x264. `CLIPPER_ENCODER=libx264` forces software encoding. `--video` downloads the
whole VOD instead.

If YouTube answers "Sign in to confirm you're not a bot", set
`CLIPPER_COOKIES_FROM_BROWSER=chrome` (or firefox, safari, edge) so yt-dlp uses your own
login, or put the browser in `desk.json` as `cookies_from_browser`.

Tests: `python3 -m unittest discover -s tests` (the end-to-end tests build a synthetic stream
with a facecam and a loud reaction, and need espeak-ng).

## desk.py: fully automatic, free

`desk.py tick` does one pass of the daily schedule; cron runs it every 15 minutes. Each pass:

1. Checks every channel in `desk.json` → `watch` (YouTube/Twitch/Kick channel pages, or a
   local folder your OBS recordings land in) for finished VODs. Live and upcoming streams and
   files still being written are skipped. The first time it sees a channel it takes only the
   newest VOD, so turning it on doesn't clip a backlog.
2. Clips each new VOD (`clips_per_vod` drafts) with the pipeline above.
3. At `countdown.at` (default 20:00) it builds a top-5 countdown from today's drafts.
4. **Auto-approves** (on by default) drafts that pass the quality gates: score ≥
   `min_score` (20; a real stream's loudest moments land around 20 to 35), 12 to 60 s (countdowns up to 180 s), loudness within 1.5 LU of -14, a hook and
   a credit, no slur/spoiler skip. At most `max_per_day`, best first. Clips with slurs are
   never even rendered.
5. Books each approved clip into the next free slot per platform (`slots`, staggered 20 min)
   in a local outbox, then **posts what's due** for free:

   | Platform | Route | Cost | Why this route |
   |---|---|---|---|
   | YouTube Shorts | YouTube Data API | free, 100 uploads/day | Uploads from unaudited apps are public since Nov 2026 |
   | Instagram Reels | Instagram Graph API (Facebook Login) | free, 100 posts/day | The route that takes a local file; the Page token doesn't expire |
   | TikTok | your logged-in browser (Playwright) | free | TikTok's API keeps posts private until an audit that personal tools don't qualify for |
   | X | your logged-in browser (Playwright) | free | The X API has no free tier any more ($0.015 a post) |

   `desk.py setup`'s default "quick" mode uses the browser route for YouTube and Instagram
   too, so connecting them is just a login. The table shows the official routes, which are
   the safer choice for those two.

   Captions come from `posts/<slug>.md` with streamer hashtags. The source VOD and timestamp
   go in the YouTube description and as the first comment on YouTube and Instagram. Campaign
   clips get `#ad`, and on YouTube the paid-placement flag. Each post's live URL goes into
   `board.csv`. A failed post is retried after 30 and 60 minutes, then reported. If the
   computer was asleep at slot time, the post goes out on the next pass.
6. Reads the 24h / 72h / 7d views: through the YouTube and Instagram APIs for posts it
   made, and yt-dlp for the rest. Only the checkpoint that is due is filled.
7. After `reports.at` (23:30) it adds the nightly best/worst, and on Sundays the weekly
   medians, to the push it sends you (free [ntfy](https://ntfy.sh) app, or a Discord webhook).

### One-time setup: one command

```bash
git clone https://github.com/rohithg/-C-Dependency-Injection-Framework && cd -C-Dependency-Injection-Framework/13-gta6-edit-page
python3 desk.py setup          # press Enter at each question; --yes accepts everything
```

`setup` does the following:

1. Installs the Python packages, the browser engine and ffmpeg (Homebrew on a Mac, apt on
   Linux).
2. Creates `~/gta6-page`, detects your time zone and generates a private notification topic.
3. Opens each platform's login in a browser window. You log in and close it, four times in
   all, and that's the only typing. The default "quick" mode posts to all four platforms
   through these saved logins, so there's no developer setup. Pick mode 2 for the official
   YouTube and Instagram APIs instead (more setup, safer for those accounts). The Google
   Cloud and Meta steps for that are at the top of `clipper/posters/youtube.py` and
   `clipper/posters/instagram.py`.
4. Offers to install the free local AI reviewer (Ollama with a 3 GB vision model).
5. Installs the 15-minute schedule (a LaunchAgent on macOS, crontab on Linux) and sends a
   test notification. Subscribe to the topic it prints in the free ntfy app.

It's safe to run again: it skips what's done and replaces its own schedule. `desk.py doctor`
shows anything still missing. Logins are kept in `~/.config/clipper` (mode 600), never in the
page folder or the repo. Keep the computer awake (macOS: Settings → Battery → prevent automatic
sleeping when plugged in). It has to be your own machine, because YouTube blocks downloads
from cloud servers.

### Why one AI reviewer and not an agent per task

Agents on every step (finding, cutting, captioning, posting) would make the desk slower,
cost money per run, and fail in new ways each time. Those steps are plain code here: same
input, same output, free. A model only helps where a person used to make a judgment call, so
there's exactly one:
- Before auto-approving, `clipper/judge.py` shows a local vision model the frame sheet and
  transcript. It rejects loading screens and spoilers, and picks the hook that reads best.
- Its hook must be built from words actually said on stream, or the original hook is kept.
- Black or frozen footage is caught earlier by ffmpeg (`blackdetect` / `freezedetect`),
  which is more reliable than a model.
- With `judge.enabled: "auto"`, approvals fall back to the quality gates when Ollama isn't
  running. Set it to `true` to never auto-approve without the judge.

Every Sunday the desk also tunes itself. Streamers whose clips beat the weekly median get one
more clip per VOD (up to 6), and ones far below it get one fewer (down to 1). The push tells
you what changed; turn it off with `reports.autotune: false`.

**Risks:**
- Automating the web uploaders is against TikTok's and X's terms, and quick mode does the
  same for YouTube and Instagram. Accounts can be limited or banned, and the risk is yours.
  The official API mode removes that for YouTube and Instagram.
- If a site changes its upload page, the push names the step that broke. Override that
  site's steps in `desk.json` → `publish.browser.steps` (the defaults and the step format
  are in `clipper/posters/browser.py`).

| Command | What it does |
|---|---|
| `desk.py tick PAGE` / `run PAGE --every 15` | One pass / loop forever (if you'd rather not use cron) |
| `desk.py setup [PAGE] [--yes]` | Everything from a fresh computer to a running desk |
| `desk.py doctor PAGE` | Checks ffmpeg, watch list, notifications, auto-approve, the AI reviewer and every platform login |
| `desk.py login youtube\|instagram\|tiktok\|x` | Connect a platform once |
| `desk.py outbox PAGE [--retry POST_ID]` | Posts waiting, posted, failed; retry a failed one |
| `desk.py list PAGE` | Drafts best first, with status, score, length, hook and alternatives |
| `desk.py approve PAGE kai_part1/m01 [--hook "..."] [--post]` | Approve by hand (re-rendering text if the hook changed), `--post` books it |
| `desk.py schedule PAGE ID [--platforms tiktok x] [--campaign "Brand"]` | Book an approved clip; `--campaign` adds `#ad` and the paid-placement flag |
| `desk.py stats PAGE` | Fill due view checkpoints now |
| `desk.py links PAGE --campaign "Brand" [--since 2026-11-20]` | Live post URLs to paste into the campaign dashboard |

Set `auto_approve.enabled` to false in `desk.json` to approve each clip yourself in the studio
(**Approve & post**) or with `/desk-review`. The paid route is still supported: set
`publish.provider` to `"upload-post"` and `UPLOAD_POST_API_KEY` to have Upload-Post schedule
everything instead of the outbox.

### Claude Code plugin (optional)

Not needed for the automation above, which runs without Claude. If you use Claude Code,
the repo is also a plugin marketplace. Claude can then set up the desk with you, run a tick,
go through drafts (checking frame sheets, suggesting hooks from what was said) and write the
nightly or weekly report.

```bash
claude plugin marketplace add rohithg/-C-Dependency-Injection-Framework
claude plugin install gta6-edit-desk@rohithg-tools
# or, in Claude Code: /plugin install gta6-edit-desk --marketplace rohithg/-C-Dependency-Injection-Framework
```

Commands: `/desk-setup`, `/desk-tick`, `/desk-review`, `/desk-report nightly|weekly`.

## What you still do by hand

With the defaults (free posting, auto-approve on, AI reviewer if installed) the daily loop needs nobody: find, clip,
approve, post, read views, report. What's left either needs you or has no way in:

| Once | Ongoing |
|---|---|
| Create the 4 accounts (phone/email verification can't be automated, and shouldn't be) | Glance at the nightly push; turn off a streamer or format the weekly report says to cut |
| `python3 desk.py setup`: Enter a few times, log in to four sites | Paste `desk.py links --campaign X` into a campaign dashboard (Content Rewards has no API for submitting) |
| Keep the computer on | Answer takedown requests (a legal reply has to come from you) |
| | Log in again if a TikTok/X session expires (the push tells you) |

Comment replies and on-camera reaction takes from the original prompt are optional now; the
automatic mode posts clips and countdowns only. Day to day you read one push a night. Nothing
needs a click unless a login expires or you run a campaign.

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
