---
description: Set up the GTA 6 edit desk in a page folder (deps, desk.json, free posting logins, notifications, schedule)
argument-hint: "[page folder, default ~/gta6-page]"
---
Set up the GTA 6 edit desk. Page folder: $ARGUMENTS (if empty, use ~/gta6-page).

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py setup <folder>` in a terminal I can interact with
   (it asks a few questions with defaults and opens a browser window per platform for me to
   log in; I do the logins myself). Before it starts, tell me plainly that quick mode automates
   the web uploaders, which is against the platforms' terms, and that mode 2 (official
   YouTube/Instagram APIs) is safer for those two.
2. Afterwards run `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py doctor <folder>` and help me fix
   any line that isn't ok. Never ask me to paste a password, token or secret into chat.
3. Show me the ntfy topic from `<folder>/desk.json` and tell me to subscribe in the ntfy app.
