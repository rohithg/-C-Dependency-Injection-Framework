"""Phone notifications: ntfy (free app, no account: pick a long random topic name) and/or a
Discord webhook (URL in the DISCORD_WEBHOOK_URL environment variable)."""

import json
import os
import urllib.request


def send(desk, title, message, opener=urllib.request.urlopen):
    cfg = desk.get("notify", {})
    sent = []
    topic = cfg.get("ntfy_topic")
    if topic:
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=message.encode(),
                                     headers={"Title": title.encode("ascii", "ignore").decode()})
        opener(req, timeout=20)
        sent.append("ntfy")
    hook = os.environ.get(cfg.get("discord_webhook_env", "DISCORD_WEBHOOK_URL"), "")
    if hook:
        req = urllib.request.Request(hook, data=json.dumps({"content": f"**{title}**\n{message}"}).encode(),
                                     headers={"Content-Type": "application/json"})
        opener(req, timeout=20)
        sent.append("discord")
    return sent
