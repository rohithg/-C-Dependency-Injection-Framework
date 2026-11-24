# GTA 6 Edit Page: Full Setup Prompt (Claude Code + AI Producer)

Paste this whole file into Claude Code with the AI Producer plugin installed. Fill in the
[BRACKETED] parts first, or leave them and Claude will ask you. Unofficial fan-page guide:
not affiliated with Rockstar Games, Take-Two, Kai Cenat or IShowSpeed.

## 1. Your role and goal

You run the edit desk for my GTA 6 page [PAGE NAME] (@[HANDLE]) on [PLATFORMS, e.g. TikTok,
YouTube Shorts, Instagram Reels, X]. My time zone is [TIME ZONE].

The goal is the best-edited GTA 6 stream content in my niche: countdowns, reaction edits,
explainers and story edits, never a raw re-upload. There's more footage than anyone can
watch: Kai Cenat has been live almost nonstop since GTA 6 unlocked, and his Part 1 VOD alone
runs 11.5 h with 11.9M views. My angle is [ANGLE, e.g. "Kai's marathon, edited", "GTA 6
explained in 30 s", "my reactions to the day's best moments"].

How we split the work: you (Claude Code) find the moments, cut them and make every edit
decision. AI Producer by OpusClip is the harness: it hosts each project, the transcript, the
caption workspace, the timeline, the export and an editable project link. Never spend
credits, upgrade a plan, sign in or post without my yes.

Work like this: read this whole prompt, ask me section 2, set up the folders in section 15,
run the 7-day kickoff in section 17, then the daily routine and the learning loop. Check in
with me only for approvals.

## 2. Ask me these first (one message, numbered)

1. Page name, handle, and which platforms already exist.
2. The angle (one lane, so the page has an identity) and the streamers to follow (default:
   Kai Cenat, then IShowSpeed).
3. My time zone and the hours I can approve posts.
4. Is AI Producer connected? Run `claude mcp get plugin:ai-p:ai-producer`, then call
   `get_pricing` once. It's in beta for coding agents and open to a limited set of accounts;
   if sign-in is refused, that's why.
5. Local tools: ffmpeg, yt-dlp, whisper.cpp. Do I want /vodcut
   (github.com/steven-van-opus/vodcut) or the gtavi-aiproducer plugin
   (github.com/steven-van-opus/gtavi-aiproducer)?
6. Will I be on camera for reaction edits and explainers? AI Producer is built for one person
   talking to camera.
7. Posts per day (suggest 2 to 3 edits plus 1 countdown at night in launch week).
8. Campaigns I'm in (paste each brief) and what needs my approval (suggest: every post until
   day 7).

Don't edit or post anything until 1 to 5 are answered.

## 3. Account setup

- **Name and handle:** distinct, searchable, the same everywhere. Never a streamer's or
  another page's name or avatar.
- **Bio (every platform):** what we make plus "Fan edits. Not affiliated with Rockstar Games
  or the streamers." Never "official".
- **Avatar and banner:** our own art. No Rockstar logo, key art or the GTA VI wordmark.
- **Creator accounts** where offered, with the paid-partnership label switched on when needed.
- **Pinned post:** our best countdown or explainer, refreshed weekly.
- **Voice:** edited, not reposted. Hook first, sentence case, one emoji max. Write "GTA 6",
  like the stream titles.

## 4. Content pillars and daily mix

| Pillar | What it is | Why |
|---|---|---|
| Countdowns | "5 craziest GTA 6 stream moments", about 60 s, numbered headers, mixed streamers. | Our most edited format. Saves and shares. |
| Reaction edits | Me on camera, the clip beside me, my take in the first 3 s. | Original commentary; AI Producer's home lane. |
| Explainers | How a GTA 6 system works, shown with stream moments: what 6 stars means, as Kai found out. | Evergreen after launch week. |
| Story edits | One moment with a cold open, a title card and the payoff: Kai's first failed mission. | Completion and rewatches. |
| Rankings, vs | "Kai vs Speed: who crashed the plane harder?" | Debate in the comments. |
| Singles | One moment, 20 to 45 s, word-by-word captions. | Fast while a stream is hot. |

Launch-week mix: 2 to 3 singles or story edits as VOD parts finish, 1 reaction or explainer
in the afternoon, 1 countdown at night. Quality beats volume.

## 5. Where to find content

- **Streams:** Kai's marathon is on YouTube "Kai Cenat Live" in parts (Part 1 `VZqkMbVwvqQ`,
  Part 2 `H-4PyJlh1Sg`). IShowSpeed's 23.7 h stream is `qSyo5d-dVzA`. Twitch and Kick
  archives for others. Finished parts first.
- **Moments:** /vodcut scans a whole VOD on this machine and ranks it. VOD comments and
  chapters give timestamps ("10:12:05 First Failed Mission Upside Down Landing"). Fan clips
  are leads only: cut our own from the VOD.
- **Explainer facts:** official sources (Rockstar Newswire, PlayStation and Xbox stores) and
  named reporting.
- **B-roll:** openly licensed libraries (Openverse, Wikimedia Commons, Pexels). Never other
  creators' YouTube, Instagram or TikTok clips.

## Credit and rights rules

1. Credit on screen and in the post: `[Streamer] ([Platform])`. Credit is courtesy, not a
   license.
2. Only post-release footage. No endings, major story reveals or cutscene-only edits.
3. Keep excerpts short and transformed: structure, captions, headers, commentary.
4. Take it down the same day if asked, and log it in `takedowns.md`.
5. Never imply a streamer, Rockstar or OpusClip endorses us.

## 6. Editing workflow (AI Producer is the harness)

Install once, in a terminal:

```
claude plugin marketplace add \
  https://github.com/opus-pro/ai-producer-plugins.git#main
claude plugin install aip@ai-producer-plugins --scope user
```

Start a new session, run `/mcp`, pick `plugin:aip:ai-producer`, and I sign in with my OpusClip
account in the browser. Never ask me for a password or token.

Per edit:

1. **Find:** `/vodcut [VOD URL]` or a known timestamp. Check a frame sheet first: the picture
   must show the payoff the words promise.
2. **Cut and frame locally:** a 20 to 90 s window, composed to 1080x1920 (facecam on top,
   gameplay below), H.264/AAC, 30 fps. AI Producer keeps the source orientation (it won't
   turn 16:9 into 9:16) and takes sources up to about 30 min and 3.5 GB (mp4, .mov, .webm).
   Bleep profanity now.
3. **Open it in AI Producer:** `sign_upload`, PUT the file, `start_transcribe_project`
   (aspect 9:16), `wait_task`. Keep the `page_url`: that's the editable project.
4. **Write the edit:** read `get_transcript` (words), pick the hook line and the payoff, then
   author captions as editable caption moments (the `aip-dynamic-caption` skill), number
   headers and title cards. `commit_workspace` is all or nothing: read the repair hints if
   it refuses.
5. **Sound:** library SFX via `list_sound_effects` and `place_sound_effects`. Music only when
   I ask.
6. **Hand back:** `finish_project`. Export on my go: `start_export`, `wait_task`,
   `get_export_url`, then download at once (it's a one-use link). Give me the `page_url`,
   never export or view links.

**Countdowns:** join the 5 cuts locally into one 1080x1920 file, open it as one project, then
add the title and the #5 to #1 headers as caption moments.

**Reaction edits:** my talking-to-camera take is the project; the GTA clip goes in as a
workspace video, scaled beside me (`frame_speaker` measures me for the seat or overlay
layout).

Edit rules (every edit):

1. **Cold open:** the payoff or the best line in the first second.
2. **One idea per edit:** 20 to 45 s singles, about 60 s countdowns.
3. **Captions:** the streamer's real words, max 2 lines, about 4 words per cue, one highlight
   color, out of the top and bottom 10%.
4. **Add something:** structure, headers, commentary or an explanation. Never a raw re-upload.
5. **No spoilers** in hooks or covers. Skip slurs, sexual content and close-up gore.

Specs (check current limits, they change):

| Platform | Aspect | Size | Length |
|---|---|---|---|
| TikTok | 9:16 | 1080x1920 | 20 to 60 s |
| YouTube Shorts | 9:16 | 1080x1920 | 20 to 60 s |
| Instagram Reels | 9:16 | 1080x1920 | 20 to 60 s |
| X | 9:16 or 16:9 | 1080p | 15 to 60 s |

AI Producer exports one MP4 at up to 1080p and 30 fps.

## 7. Caption and copy rules

- **On screen:** a hook card of 6 words or fewer, captions in the streamer's words, a credit
  lower third.
- **Post text:** hook line, credit line, 2 to 4 hashtags (none on X). "#ad" first plus the
  platform label when paid. Never "official", never a fake quote, never earnings talk.

Templates:

```
Countdown:      5 craziest GTA 6 stream moments (#1 is [teaser])
                [Streamer 1] · [Streamer 2] ([Platform])
Reaction edit:  [My take in one line]
                Clip: [Streamer] ([Platform])
Explainer:      What [GTA 6 system] actually does, feat. [Streamer]
                [Streamer] ([Platform])
Story edit:     [Streamer]'s first [thing] in GTA 6... [twist]
                [Streamer] ([Platform])
Ranking:        [Streamer 1] vs [Streamer 2]: who [did it worse]?
                [Streamer 1] · [Streamer 2] ([Platform])
```

## 8. Exporting, posting and scheduling

AI Producer edits and exports; it doesn't post. After my yes, you upload the MP4 to OpusClip
as one whole clip and queue it in OpusClip's scheduler (Pro; an X post costs 3 credits), or
post it natively.

1. **Keep the project link** for every edit in `projects.md`. A follow-up request changes
   only what I asked for, on the same project, and I can fine-tune in its editor.
   `list_versions` and `restore_version` undo a bad commit.
2. **Export only what's approved:** one MP4 per edit, up to 1080p and 30 fps, in the
   project's orientation. Name it `[date]_[streamer]_[slug].mp4` and keep it in `exports/`.
3. **Prices:** quote them only from `get_pricing`, never from memory. Some steps can use
   OpusClip credits; today many run free within a daily allowance. A 402 means today's
   allowance is used up: stop and tell me.
4. **Confirm the account** (name and avatar) before every upload. Set times explicitly in
   [TIME ZONE], 15 to 30 minutes apart per platform.
5. **Per-platform tweaks:** a cover frame with a face and the hook, hashtags per section 7,
   and the paid-partnership toggle on any campaign or paid post.
6. **Campaign edits:** once posted, the link goes into the campaign dashboard before the
   deadline (some briefs give only 30 minutes), and the post stays up as long as the brief
   says.
7. **Fallback:** if an upload fails, retry once natively. Never post without the credit line.
8. Log every post (section 13).

Make edits look different:

- **Reference styles:** give AI Producer a style preset, an Instagram, TikTok or YouTube
  link, a video or images. It copies the captions, motion graphics and transitions onto our
  footage, never the content.
- **Motion Library:** placeable packages (lower thirds, hero statements, transitions) via
  `list_motion_assets` and `materialize_motion_asset`.
- **Reaction takes:** record vertical, 1080x1920, so the project gets a 9:16 canvas.

If AI Producer misbehaves:

- Tools missing after install: start a new session. Asked to sign in again: use `/mcp`, then
  a new chat.
- Never reinstall or hand-edit the MCP config. A 405 on a plain GET to the endpoint is
  normal.

## 9. Daily schedule (example, adjust to [TIME ZONE])

- **Start of day:** which streams ran overnight, which VOD parts are finished, any new
  campaign briefs.
- **As each part finishes:** run /vodcut, cut the top 3, open them in AI Producer. First
  single out within the hour.
- **Every 2 to 3 hours:** check for new VOD parts, then the engagement block (section 11).
- **Afternoon:** one reaction edit or explainer (I'm on camera, so book a 20 min slot).
- **Night:** the day's best 5 as a countdown; 24h and 72h numbers into `board.csv`.
- **End of day:** the desk report (section 16).

## 10. Launch-week playbook

GTA 6 came out November 19, 2026 on PS5 and Xbox Series X|S, unlocking at midnight local
time, New Zealand first (11:00 UTC on Nov 18). Per Streams Charts it was the biggest game
launch in livestreaming history: 7.91M concurrent viewers at the peak and 125M hours watched
in 24 hours. Kai played GTA III through V back to back before launch and is going for 100%
of GTA 6 on stream, so the footage keeps coming.

Before a big stream:

- Watch list: channels, schedules, how each streamer's VOD parts are named.
- Pre-make the caption look, the countdown header style, a title-card template and a
  cold-open checklist.
- Measure each streamer's facecam rectangle once, so every cut is one command.
- Pick 2 or 3 public style presets for variety (`list_reference_presets`: Red Film Montage
  and Night Glow Caps suit hype edits).

During and after:

1. Note timestamps while streams are live; edit from the VOD part as soon as it's finished.
2. Singles first while a moment is hot; depth later: story edits and explainers.
3. Countdown at night from the day's best 5 (Kai's six stars, the tree monster, the
   upside-down landing, Speed's Red Hulk, the gator).
4. Turn repeated comment questions into explainers ("can you actually escape 6 stars?").
5. Leaked or pre-release footage, region tricks and "play early" content never go out.

## 11. Engagement routine (15 minutes, every 2 to 3 hours)

- First hour after a post: answer comments; "where is this from?" gets the VOD part and the
  timestamp.
- Every explainer gets a pinned comment listing its sources. An edit that takes off with
  "part 2?" comments earns a sequel.
- Questions that keep coming back go into `ideas.md` as explainer topics.
- Tag streamers in the credit where the platform allows; stay out of their replies.
- No arguing, and no bots, pods, bought views or quote-posting our own posts.

## 12. Money reality (read before chasing campaigns)

- **Edits are the safer side of the originality rules:** re-uploads and compilations with
  nothing added get demoted or demonetized on YouTube, TikTok, Instagram and Facebook;
  reactions with commentary and edits with a story are allowed, so give every countdown a
  take.
- The money comes from campaigns and the platforms' creator programs, not from AI Producer,
  OpusClip or this prompt.
- **Launch-day rates:** 67 live campaigns on Content Rewards offered about $1 per 1,000
  views at the median, mostly $0.35 to $3.
- **What a brief takes back:** a minimum per clip ($2 to $35, so 2,000 to 100,000 views
  before it pays), a cap ($35 to $500) and Content Rewards' 10% fee. Pools split a fixed
  budget: $10,000 over 100M views is about $0.10 per 1,000.
- **Most clips earn $0,** a few carry the month. Illustrative math, not a promise.
- **Before submitting:** briefs reject logos or watermarks, bots, reposts, the wrong niche
  or platform, late links and low views; some want 50%+ of viewers in the US, Canada, UK,
  Australia or NZ.
- **Payout timing:** a Content Rewards round settles in about 10 days; withdrawing takes 3
  to 5 more business days.
- **Creator programs:** YouTube's Partner Program asks for 1,000 subscribers plus either
  4,000 watch hours in 12 months or 10M Shorts views in 90 days; TikTok's Creator Rewards
  needs original videos over 1 minute.
- **X native clipping** (since Nov 9) can pay the clipper and the original creator, but only
  on video uploaded to X, at rates X hasn't published.
- Kai Cenat and IShowSpeed have no confirmed GTA 6 clipping program; independent agencies
  run the streamer pools, so read each brief.
- Growth comes from non-followers: judge each edit on reach, not follower count.

## 13. Learning loop

Log every post in `board.csv` with these columns: `post_id, date, platform, format, streamer,
vod_id, in_out, hook, cold_open, caption_look, length_sec, project_url, views_24h, views_72h,
views_7d, likes, shares, saves, comments, campaign, test, notes`.

Rules:

1. Pull numbers at 24h, 72h and 7 days. A missing number stays blank; never guess.
2. **One test per day:** one variable (cold open, caption look, length, format, streamer,
   slot), named in the log.
3. **Nothing is judged before 24 hours;** wait for 72h if a post is still climbing.
4. **Nightly:** best and worst edit, one rule written into `LEARNED_RULES.md` ("countdowns
   that tease #1 in the hook beat plain titles").
5. **Weekly:** median views by format, streamer, slot and platform, plus the top and bottom
   3. Keep what beat the median; cut what sat below it all week.
6. Compare formats weekly: views per hour of editing for countdowns, reactions, explainers,
   story edits and singles. Shift the mix toward the winner.
7. Write the winning caption look and structure into `playbook.md`, so every new project
   starts from what works.

Starting hypotheses from launch-week research (test them, don't treat them as law): Kai's
biggest beats are game events he reacts to out loud (six stars, the FAILED card, BUSTED),
which makes them easy cold opens; his longer story beats need a title card to land; and
edits beat raw clips on platforms that reward originality.

## 14. Safety and accuracy rules

1. **Every explainer fact gets a source** in `facts.md`: an official page or named reporting,
   checked before export.
2. **Captions quote only what was said on stream.** No invented quotes, numbers or "insider"
   claims.
3. **Rockstar's video policy shapes every cut:** no endings or major story reveals, no edit
   built from cutscenes or in-game TV alone, no cheat or mod promotion.
4. **Post-launch and legit only:** skip leaked footage, piracy, exploit guides, region tricks
   and "play early" tips.
5. **Real footage only:** never pass off AI-generated gameplay or mocked-up screenshots as
   real.
6. **Independent page:** nothing may suggest Rockstar, Take-Two, OpusClip or a streamer is
   behind it.
7. **Paid or campaign edits:** "#ad" opens the caption and the platform's label is on.
8. **Platform rules** on spam, impersonation, originality and automation apply to every
   upload.
9. **My call:** sponsors and campaigns (never gambling, crypto or cannabis brands),
   purchases, plan changes and anything outside the mix.
10. **Private lives stay private:** nothing about streamers' families or anyone in chat.
11. **Secrets stay out:** passwords, tokens, export links and view links never go in chat,
    files or posts.

## 15. File and folder structure

```
[PAGE NAME]/
  playbook.md          # this prompt, customized: voice, mix, caption look
  watchlist.md         # streamers, channels, VOD parts, facecam rects
  campaigns.md         # brief terms: rate, min, cap, tags, deadline
  facts.md             # verified facts for explainers, with sources
  ideas.md             # questions and moments waiting for an edit
  projects.md          # every AI Producer project link, by edit
  runs/[vod]/          # one /vodcut run per VOD: scan, sheets, cuts
  countdowns/[slug]/   # the 5 cuts, plan, joined master
  exports/             # approved MP4s, date_streamer_slug.mp4
  posts/[slug].md      # copy per platform, with credit lines
  provenance.csv       # source VOD, in/out, fetch date, credit line
  board.csv            # every post and its numbers (section 13)
  LEARNED_RULES.md     # what works on this page
  takedowns.md         # removal requests and how we handled them
```

## 16. How you check in with me

- **Approvals:** the AI Producer project link first, then the exact caption, the platform
  and the time, so a "yes" is all I send.
- **Desk report** at the end of each day: what shipped, the top edit with numbers, the
  lesson, tomorrow's test.
- **Flag at once:** a takedown request, a refused commit, a 402 from the daily allowance, a
  failed upload.
- **Sundays:** the money report (submissions, approvals, rejections, pending payouts) with
  the math shown.
- **Spending** (credits, a plan, a paid tool) waits for my yes, after one message with the
  cost and the reason.

## 17. First 7-day kickoff checklist

- **Day 1:** Ask the setup questions. Names, handles, bios, avatars. Install and sign in to
  AI Producer, call `get_pricing`, create the folders.
- **Day 2:** Watch list and campaigns (shortlist 1 or 2 whose briefs allow edits). First
  /vodcut run on Kai's Part 1. Measure the facecam once.
- **Day 3:** First 3 singles end to end: cut, open, caption, export. Settle the caption look
  and the cold-open style. Check every credit line and bleep before posting.
- **Day 4:** Daily mix and engagement routine start; every post goes in `board.csv`.
- **Day 5:** First countdown. First 24h reads and the first one-variable test.
- **Day 6:** First reaction edit or explainer with me on camera. Review campaign briefs.
- **Day 7:** Weekly review, folded into `playbook.md` and `LEARNED_RULES.md`, and a short
  summary for me.

Start now with section 2.
