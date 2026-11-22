---
description: Nightly or weekly review from board.csv, with the learning-loop write-ups
argument-hint: "[nightly|weekly] [page folder, default .]"
---
Arguments: $ARGUMENTS (first word nightly or weekly, default nightly; second the page folder,
default .)

1. Fill any due view numbers: `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py stats <folder>`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/page.py <nightly|weekly> <folder>`.
3. Nightly: write one rule into `LEARNED_RULES.md` from the best and worst edit, naming the
   post ids, and propose tomorrow's one-variable test.
   Weekly: fold what beat the median into `playbook.md` (caption look, formats, slots), and
   adjust `desk.json` slots or `clips_per_vod` if the numbers say so. Show me the diff.
4. If campaigns are running, add `page.py money --board <folder>` with the brief's rate,
   minimum and cap from `campaigns.md`.
