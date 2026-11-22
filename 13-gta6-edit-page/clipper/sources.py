"""Where footage comes from: online VODs (yt-dlp) or local recordings.

Online VODs are fetched audio-first: an 11 h stream is ~250 MB of audio versus 10+ GB of
1080p video, and audio is all the scan needs. Video is then downloaded only for the few
sections that become clips.
"""

import json
import os
import time
from datetime import date
from pathlib import Path

from .media import ffmpeg

PLATFORM_NAMES = {"youtube": "YouTube", "youtubetab": "YouTube", "twitch": "Twitch",
                  "twitchvod": "Twitch", "kick": "Kick", "twitter": "X"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".flv", ".ts"}


def ydl_opts(**extra):
    """Base yt-dlp options. CLIPPER_COOKIES_FROM_BROWSER (chrome, firefox, safari...) gets past
    YouTube's 'confirm you're not a bot' check and age/member gates, using your own login."""
    opts = {"quiet": True, "no_warnings": True}
    browser = os.environ.get("CLIPPER_COOKIES_FROM_BROWSER")
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    opts.update(extra)
    return opts


def run_dir(page, vod):
    path = Path(page) / "runs" / vod
    path.mkdir(parents=True, exist_ok=True)
    return path


def source(page, vod):
    return json.loads((Path(page) / "runs" / vod / "source.json").read_text())


def _save(page, vod, meta):
    meta["fetched_on"] = date.today().isoformat()
    (run_dir(page, vod) / "source.json").write_text(json.dumps(meta, indent=2))


def fetch(page, url, section=None, streamer=None, audio_only=True, platform=None):
    """Registers a local file in place, or downloads an online VOD. Returns the vod id."""
    local = Path(url)
    if local.exists():
        vod = local.stem
        _save(page, vod, {"url": str(local.resolve()), "path": str(local.resolve()), "id": vod,
                          "streamer": streamer or "", "platform": platform or "", "offset": 0.0,
                          "video": True})
        return vod

    from yt_dlp import YoutubeDL
    from yt_dlp.utils import download_range_func

    from .moments import parse_ts

    with YoutubeDL(ydl_opts()) as ydl:
        info = ydl.extract_info(url, download=False)
    vod = info["id"]
    out = run_dir(page, vod)
    name = "audio" if audio_only else "source"
    opts = ydl_opts(outtmpl=str(out / f"{name}.%(ext)s"))
    if audio_only:
        opts["format"] = "ba[abr<=96]/ba/b"
    else:
        opts.update(format="bv*[height<=1080]+ba/b[height<=1080]/b", merge_output_format="mp4")
    offset = 0.0
    if section:
        a, b = (parse_ts(x) for x in section.split("-"))
        opts.update(download_ranges=download_range_func(None, [(a, b)]), force_keyframes_at_cuts=True)
        offset = a
    with YoutubeDL(opts) as ydl:
        ydl.download([info.get("webpage_url", url)])
    path = next(out.glob(f"{name}.*"))
    key = info.get("extractor_key", "").lower()
    _save(page, vod, {
        "url": info.get("webpage_url", url), "path": str(path), "id": vod,
        "title": info.get("title", ""),
        "streamer": streamer or info.get("uploader") or info.get("channel") or "",
        "platform": platform or PLATFORM_NAMES.get(key, info.get("extractor_key", "")),
        "offset": offset, "video": not audio_only})
    return vod


def fetch_section(src, start, end, out):
    """Video for [start, end] seconds of the file `src` was scanned from (VOD time - offset)."""
    out = Path(out)
    if src.get("video"):
        ffmpeg("-ss", start, "-to", end, "-i", src["path"], "-c:v", "libx264", "-preset",
               "ultrafast", "-crf", "14", "-c:a", "aac", "-b:a", "256k", out)
        return out
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import download_range_func

    a, b = start + src.get("offset", 0.0), end + src.get("offset", 0.0)
    opts = ydl_opts(format="bv*[height<=1080]+ba/b[height<=1080]/b", merge_output_format="mp4",
                    outtmpl=str(out.with_suffix(".%(ext)s")),
                    download_ranges=download_range_func(None, [(a, b)]), force_keyframes_at_cuts=True)
    with YoutubeDL(opts) as ydl:
        ydl.download([src["url"]])
    got = next(out.parent.glob(out.stem + ".*"))
    if got != out:
        got.rename(out)
    return out


def latest_vods(channel, limit=5, settle_seconds=120):
    """Newest finished VODs: [{'id', 'url', 'title'}]. Live or upcoming streams are skipped.

    `channel` is a channel's streams/videos page (YouTube, Twitch, Kick) or a local folder
    of recordings; a local file counts as finished once it stops growing.
    """
    folder = Path(channel).expanduser()
    if folder.is_dir():
        files = sorted((p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXTS),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        now = time.time()
        return [{"id": p.stem, "url": str(p.resolve()), "title": p.stem} for p in files
                if now - p.stat().st_mtime >= settle_seconds]

    from yt_dlp import YoutubeDL

    with YoutubeDL(ydl_opts(extract_flat="in_playlist", playlistend=limit)) as ydl:
        info = ydl.extract_info(channel, download=False)
    out = []
    for e in (info.get("entries") or [])[:limit]:
        if not e or e.get("live_status") in ("is_live", "is_upcoming", "post_live"):
            continue
        out.append({"id": e["id"], "url": e.get("url") or e.get("webpage_url"),
                    "title": e.get("title", "")})
    return out
