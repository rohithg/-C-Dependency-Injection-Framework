"""Free posters: each platform's own free route, no paid scheduler in between.

  youtube    YouTube Data API (free; public uploads allowed for unaudited projects since Nov 2026)
  instagram  Instagram Graph API through Facebook Login (free; local file upload via rupload)
  tiktok     your logged-in browser session (TikTok's API only posts privately until an audit
             that personal tools don't qualify for)
  x          your logged-in browser session (the X API has no free tier)

Every poster has `post(video, entry) -> {"url", "ref"}`; API posters also have `counts(ref)`.
Credentials live in ~/.config/clipper (or $CLIPPER_CONFIG), never in the page folder or repo.
"""

import json
import os
from pathlib import Path

DEFAULT_ROUTES = {"youtube": "api", "instagram": "api", "tiktok": "browser", "x": "browser"}


def config_dir():
    d = Path(os.environ.get("CLIPPER_CONFIG") or Path.home() / ".config" / "clipper")
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_secret(name):
    p = config_dir() / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def save_secret(name, data):
    p = config_dir() / f"{name}.json"
    p.write_text(json.dumps(data, indent=2))
    p.chmod(0o600)


def routes(desk):
    return {**DEFAULT_ROUTES, **desk.get("publish", {}).get("routes", {})}


def get_poster(platform, desk, session=None):
    route = routes(desk)[platform]
    if route == "api" and platform == "youtube":
        from .youtube import YouTube
        return YouTube(session=session)
    if route == "api" and platform == "instagram":
        from .instagram import Instagram
        return Instagram(session=session)
    if route == "browser":
        from .browser import BrowserPoster
        return BrowserPoster(platform, desk.get("publish", {}).get("browser", {}))
    raise ValueError(f"no poster for {platform} via {route}")
