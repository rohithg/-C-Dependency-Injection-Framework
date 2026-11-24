---
description: Run one desk pass now (new VODs, countdown, scheduling, view numbers) and summarize
argument-hint: "[page folder, default .]"
---
Page folder: $ARGUMENTS (if empty, the current directory).

Run `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py tick <folder>` and then
`python3 ${CLAUDE_PLUGIN_ROOT}/desk.py list <folder>`.

Summarize in a few lines: new drafts (with their hooks), anything scheduled, view numbers
read, and what needs my yes. For each draft I should look at, check its `sheet.jpg` first and
tell me if the frames don't show the payoff the hook promises.
