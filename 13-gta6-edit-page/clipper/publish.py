"""Schedule approved clips to TikTok, YouTube Shorts, Instagram Reels and X through Upload-Post
(https://docs.upload-post.com), one API for all four, using each platform's official API.

The API key comes from the UPLOAD_POST_API_KEY environment variable; the connected profile
name is `publish.user` in desk.json. Nothing here posts without an approved export.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import page as pagekit  # noqa: E402

API = "https://api.upload-post.com/api"
LABELS = {"TikTok": "tiktok", "YouTube Shorts": "youtube", "Instagram Reels": "instagram", "X": "x"}


def load_desk(page_dir):
    path = Path(page_dir) / "desk.json"
    return json.loads(path.read_text()) if path.exists() else {}


def post_copy(page_dir, slug):
    """{platform: caption} from posts/<slug>.md (the '## TikTok' ... sections)."""
    text = (Path(page_dir) / "posts" / f"{slug}.md").read_text()
    out = {}
    for label, body in re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        platform = LABELS.get(label.strip())
        if platform:
            out[platform] = body.strip()
    return out


def first_comment(meta, sources, clip_id=""):
    """Answers 'where is this from?' before anyone asks (SETUP_PROMPT section 11)."""
    parts = []
    for s in meta.get("sources") or [{"credit": meta["credit"], "vod_in": meta["moment"]["vod_in"],
                                      "id": clip_id}]:
        title = sources.get(s.get("id", "").split("/")[0], {}).get("title", "")
        where = f"\u201c{title}\u201d" if title else "the stream VOD"
        parts.append(f"{s['credit']}: {where} at {s['vod_in']}" if s.get("vod_in") else s["credit"])
    return "Source: " + "; ".join(parts) + ". Fan edit, not affiliated with Rockstar or the streamers."


def next_slot(slots, tz, now, taken, min_lead=timedelta(minutes=10)):
    """Earliest configured 'HH:MM' slot after now + lead that is not already taken."""
    zone = ZoneInfo(tz)
    now = now.astimezone(zone)
    for day in range(0, 14):
        d = (now + timedelta(days=day)).date()
        for hhmm in sorted(slots):
            h, m = map(int, hhmm.split(":"))
            when = datetime(d.year, d.month, d.day, h, m, tzinfo=zone)
            if when >= now + min_lead and all(abs((when - t).total_seconds()) >= 600 for t in taken):
                return when
    raise ValueError("no free slot in the next 14 days")


def _taken(rows, platform, tz):
    zone = ZoneInfo(tz)
    out = []
    for r in rows:
        if r["platform"] == platform and r["date"]:
            t = datetime.fromisoformat(r["date"])
            out.append(t if t.tzinfo else t.replace(tzinfo=zone))
    return out


class UploadPost:
    def __init__(self, api_key=None, session=None):
        self.key = api_key or os.environ.get("UPLOAD_POST_API_KEY")
        if not self.key:
            raise RuntimeError("set UPLOAD_POST_API_KEY (Upload-Post dashboard -> API keys)")
        if session is None:
            import requests
            session = requests.Session()
        self.http = session

    def _headers(self):
        return {"Authorization": f"Apikey {self.key}"}

    def upload(self, video, fields):
        with open(video, "rb") as f:
            r = self.http.post(f"{API}/upload", headers=self._headers(), data=fields,
                               files={"video": (Path(video).name, f, "video/mp4")}, timeout=600)
        data = r.json()
        if r.status_code >= 400 or not data.get("success", False):
            raise RuntimeError(f"upload-post: {data.get('message') or data.get('error') or r.status_code}")
        return data

    def status(self, job_id=None, request_id=None):
        params = {"job_id": job_id} if job_id else {"request_id": request_id}
        r = self.http.get(f"{API}/uploadposts/status", headers=self._headers(), params=params, timeout=60)
        return r.json()


def schedule(page_dir, clip_id, platforms=None, client=None, now=None, campaign=None, at=None):
    """Upload the approved export once per platform, each at its own next free slot."""
    from .studio import _source, clip_path

    page_dir = Path(page_dir)
    desk = load_desk(page_dir)
    tz = desk.get("timezone", "UTC")
    pub = desk.get("publish", {})
    platforms = platforms or desk.get("platforms", ["tiktok", "youtube", "instagram", "x"])
    clip_dir = clip_path(page_dir, clip_id)
    meta = json.loads((clip_dir / "meta.json").read_text())
    if meta.get("status") == "scheduled":
        raise ValueError("already scheduled")
    if meta.get("status") != "approved":
        raise ValueError("approve the clip first")
    client = client or UploadPost()
    video = page_dir / "exports" / meta["export"]
    copy = post_copy(page_dir, meta["slug"])
    sources = {s["id"].split("/")[0]: _source(page_dir, s["id"].split("/")[0])
               for s in meta.get("sources") or [{"id": clip_id}]}
    comment = first_comment(meta, sources, clip_id)
    campaign = campaign or meta.get("campaign") or ""
    now = now or datetime.now(ZoneInfo(tz))
    done = []
    for platform in platforms:
        rows = pagekit.read_board(page_dir)
        when = at or next_slot(desk.get("slots", {}).get(platform, ["12:00", "18:00", "21:00"]),
                               tz, now, _taken(rows, platform, tz))
        caption = copy.get(platform) or f"{meta['hook']}\n{meta['credit']}"
        if campaign and not caption.startswith("#ad"):
            caption = "#ad " + caption
        fields = {"user": pub.get("user", ""), "platform[]": platform, "title": caption,
                  f"{platform}_first_comment": comment, "timezone": tz,
                  "scheduled_date": when.strftime("%Y-%m-%dT%H:%M:%S"),
                  "external_id": f"{meta['slug']}-{platform}"}
        if platform == "youtube":
            fields.update(youtube_title=meta["hook"][:100], youtube_description=caption)
        if campaign:
            fields["paid_partnership"] = "true"
        resp = client.upload(video, fields)
        job = resp.get("job_id") or resp.get("request_id") or ""
        url = ((resp.get("results") or {}).get(platform) or {}).get("url", "")
        m = meta["moment"]
        post_id = pagekit.log_post(page_dir, {
            "date": when.strftime("%Y-%m-%dT%H:%M"), "platform": platform,
            "format": "countdown" if meta.get("kind") == "countdown" else meta.get("format", "single"),
            "streamer": meta["credit"].split(" (")[0], "vod_id": clip_id.split("/")[0],
            "in_out": f"{m['vod_in']}-{m['vod_out']}" if m.get("vod_in") else "",
            "hook": meta["hook"], "cold_open": "peak" if meta.get("cold_open") else "",
            "length_sec": str(meta.get("duration", "")), "campaign": campaign,
            "notes": f"upload-post job {job}" if job else "upload-post", "post_url": url})
        done.append({"platform": platform, "post_id": post_id, "when": when.isoformat(), "job": job})
    meta["status"] = "scheduled"
    meta.setdefault("posts", []).extend({"platform": d["platform"], "post_id": d["post_id"]} for d in done)
    from .studio import _save
    _save(clip_dir, meta)
    return done


def resolve_urls(page_dir, client=None):
    """Fill post_url for scheduled posts once Upload-Post reports them published."""
    rows = pagekit.read_board(page_dir)
    pending = [r for r in rows if not r["post_url"] and "upload-post job " in r["notes"]]
    if not pending:
        return 0
    client = client or UploadPost()
    filled = 0
    for r in pending:
        job = r["notes"].split("upload-post job ", 1)[1].split()[0]
        data = client.status(job_id=job)
        for res in data.get("results") or []:
            url = res.get("post_url") or res.get("url") or ""
            if res.get("platform") == r["platform"] and url.startswith("http"):
                r["post_url"] = url
                filled += 1
    if filled:
        pagekit.write_board(page_dir, rows)
    return filled
