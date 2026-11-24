---
description: Review drafts with me and approve/schedule the ones I say yes to
argument-hint: "[page folder, default .]"
---
Page folder: $ARGUMENTS (if empty, the current directory).

1. Start Clip Studio in the background: `python3 ${CLAUDE_PLUGIN_ROOT}/clip.py studio <folder>`
   and give me the URL.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py list <folder>`. For each draft, look at its
   `runs/<vod>/clips/<id>/sheet.jpg` and `meta.json` and give me one line: hook, the best
   alternative from `hooks`, score, length, and any problem (payoff not visible, weak cold
   open, skip flag).
3. For each one I approve, run
   `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py approve <folder> <id> [--hook "..."] --post`
   and report the scheduled times. Campaign posts go through
   `desk.py schedule <folder> <id> --campaign NAME` instead.
