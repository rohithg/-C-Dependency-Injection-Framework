---
name: gta6-edit-desk
description: Operate the GTA 6 stream-edit page kit (desk.py, clip.py, page.py). Use when the user asks to clip VODs, review or approve drafts, post or schedule clips, read view numbers, build a countdown, or run the nightly/weekly review for their GTA 6 edit page.
---

# GTA 6 edit desk

The kit lives at `${CLAUDE_PLUGIN_ROOT}`. The user's page folder (playbook, board.csv,
runs/, exports/ ...) is the current directory unless they name another; call it PAGE.
`PAGE/SETUP_PROMPT.md` is the full brief: its rules on credit, rights, spoilers, captions and
approvals always apply.

## Commands

| Goal | Command |
|---|---|
| Everything due right now (new VODs, countdown, auto-approve, booking, posting, view numbers, reports, notification) | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py tick PAGE` |
| Set everything up on a fresh computer (interactive; the user does the logins) | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py setup PAGE` |
| Is everything able to run unattended? | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py doctor PAGE` |
| Connect a platform (free): youtube, instagram, tiktok or x | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py login <platform>` (the user does the login) |
| Posts waiting / posted / failed, retry one | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py outbox PAGE [--retry POST_ID]` |
| Clip one VOD or local recording | `python3 ${CLAUDE_PLUGIN_ROOT}/clip.py auto PAGE URL --credit "Kai Cenat (YouTube)" --top 5` |
| List drafts | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py list PAGE` |
| Approve (new hook optional), and schedule to all platforms | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py approve PAGE <vod>/<id> --hook "..." --post` |
| Countdown from today's best | `python3 ${CLAUDE_PLUGIN_ROOT}/clip.py countdown PAGE` |
| Review page for the user | `python3 ${CLAUDE_PLUGIN_ROOT}/clip.py studio PAGE` (run in the background, give the URL) |
| View checkpoints now | `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py stats PAGE` |
| Nightly / weekly review | `python3 ${CLAUDE_PLUGIN_ROOT}/page.py nightly PAGE`, `... weekly PAGE` |
| Campaign math | `python3 ${CLAUDE_PLUGIN_ROOT}/page.py money --rate R --min MIN --cap CAP --board PAGE` |

## Rules

- When you approve by hand, ask the user first, and look at `runs/<vod>/clips/<id>/sheet.jpg`:
  the frames must show the payoff the hook promises. The desk itself auto-approves when
  `auto_approve.enabled` is true in `PAGE/desk.json` (the default), within its quality gates
  and `max_per_day`; don't turn that on or off without the user saying so.
- Hooks: 6 words max, built from what was said on stream. Prefer one of the `hooks`
  suggestions in the clip's `meta.json`; never invent a quote or a claim.
- A clip whose `skip` is set (slur, spoiler) is never posted.
- Campaign posts: pass `--campaign NAME` to `desk.py schedule` so "#ad" and the paid
  partnership label go on; check the brief in `PAGE/campaigns.md` first.
- After `nightly`, write one rule into `PAGE/LEARNED_RULES.md` naming the posts it came from.
  After `weekly`, fold what beat the median into `PAGE/playbook.md`.
- Secrets (platform tokens, UPLOAD_POST_API_KEY, webhook URLs, cookies) live in
  ~/.config/clipper or environment variables only; never write them into the page, the repo
  or chat, and never ask the user to paste one into chat.
