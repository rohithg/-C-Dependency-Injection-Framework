"""Fill the 24h / 72h / 7d view checkpoints in board.csv from the live posts.

Posts that went out through a free API (YouTube, Instagram) are read through that API.
Everything else is read with yt-dlp (YouTube and TikTok work without logging in; X usually
needs `cookies_from_browser` in desk.json). A number that can't be read stays blank.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import page as pagekit  # noqa: E402


def ytdlp_counts(url, cookies_from_browser=None):
    from yt_dlp import YoutubeDL

    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {"views": info.get("view_count"), "likes": info.get("like_count"),
            "comments": info.get("comment_count"), "shares": info.get("repost_count")}


def current_checkpoint(row, now):
    """The latest checkpoint whose time has come. Earlier ones that were missed stay blank:
    a 7-day number read on day 3 would be a guess."""
    age = now - datetime.fromisoformat(row["date"])
    current = None
    for name, after in pagekit.CHECKPOINTS.items():
        if age >= after:
            current = name
    return current


def auto_counts(page_dir, cookies_from_browser=None, get_poster=None):
    """counts(url): the platform API when the post went out through one, else yt-dlp."""
    from . import outbox

    refs = outbox.refs(page_dir)
    apis = {}

    def counts(url):
        platform, ref = refs.get(url, (None, None))
        if platform and ref and get_poster:
            if platform not in apis:
                try:
                    poster = get_poster(platform)
                    apis[platform] = poster if hasattr(poster, "counts") else None
                except Exception:
                    apis[platform] = None
            if apis[platform]:
                try:
                    got = apis[platform].counts(ref)
                    if got.get("views") is not None:
                        return got
                except Exception:
                    pass
        return ytdlp_counts(url, cookies_from_browser)

    return counts


def pull(page_dir, now=None, counts=None, cookies_from_browser=None, get_poster=None):
    """Read every due, blank checkpoint. Returns [(post_id, checkpoint, views)]."""
    now = now or datetime.now()
    counts = counts or auto_counts(page_dir, cookies_from_browser, get_poster)
    rows = pagekit.read_board(page_dir)
    filled = []
    for row in rows:
        cp = current_checkpoint(row, now)
        if not cp or row[f"views_{cp}"] or not row["post_url"]:
            continue
        try:
            got = counts(row["post_url"])
        except Exception as exc:  # one unreadable post must not stop the rest
            row["notes"] = (row["notes"] + f" | stats failed: {str(exc)[:60]}").strip(" |")
            continue
        if got.get("views") is None:
            continue
        row[f"views_{cp}"] = str(int(got["views"]))
        for key in ("likes", "comments", "shares"):
            if got.get(key) is not None:
                row[key] = str(int(got[key]))
        filled.append((row["post_id"], cp, int(got["views"])))
    if filled:
        pagekit.write_board(page_dir, rows)
    return filled
