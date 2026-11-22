---
description: Set up the GTA 6 edit desk in a page folder (deps, desk.json, free posting logins, notifications, schedule)
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
5. Free posting (the default, `publish.provider: "free"`): walk me through connecting each
   platform once, one at a time, with `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py login <platform>`:
   - youtube: the Google Cloud steps in `${CLAUDE_PLUGIN_ROOT}/clipper/posters/youtube.py`
     (including "Publish app" so the login doesn't expire after 7 days), then
     `login youtube --client-secret <downloaded json>`.
   - instagram: the Meta app steps in `${CLAUDE_PLUGIN_ROOT}/clipper/posters/instagram.py`,
     then `login instagram --app-id <id>`; I paste the secret and token into the hidden
     prompt myself, never into chat.
   - tiktok, x: `login tiktok` / `login x` opens a browser window; I log in and close it.
     Put my TikTok handle in `publish.browser.handles.tiktok`. Tell me plainly that automating
     the TikTok/X web uploader is against their terms and the account risk is mine.
   Auto-approve is on by default; ask whether I want to keep it on for the first days.
6. Run `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py doctor <folder>` until every line is ok, then
   `desk.py tick <folder>` once and show me the result.
7. Print `python3 ${CLAUDE_PLUGIN_ROOT}/desk.py cron <folder>` and help me install it, and
   tell me how to keep the computer from sleeping (macOS: Battery/Energy settings).
