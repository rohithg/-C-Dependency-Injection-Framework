---
description: Set up the GTA 6 edit desk in a page folder (deps, desk.json, notifications, posting, schedule)
argument-hint: "[page folder, default ~/gta6-page]"
---
Set up the GTA 6 edit desk. Page folder: $ARGUMENTS (if empty, use ~/gta6-page).

1. If the folder doesn't exist: `python3 ${CLAUDE_PLUGIN_ROOT}/page.py init <folder>` and ask me
   for page name, handle, platforms and time zone, then fill `playbook.md`.
2. Install: `pip install -r ${CLAUDE_PLUGIN_ROOT}/requirements.txt`; check `ffmpeg -version`.
   If ffmpeg is missing, tell me the one install command for my OS (brew / apt / winget).
3. Walk through `<folder>/desk.json` with me: streamers and their channel URLs (or a local
   recordings folder), posting slots in my time zone, clips per VOD, countdown time.
4. Notifications: suggest the free ntfy app with a long random topic; put it in desk.json.
5. Posting: explain Upload-Post (connect TikTok, YouTube, Instagram, X once in their
   dashboard), then have me set `UPLOAD_POST_API_KEY` in my shell profile myself and put the
   profile name in desk.json `publish.user`. Never ask me to paste the key into chat.
6. Run `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py tick <folder>` once and show me the result.
7. Print `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py cron <folder>` and help me install it.
