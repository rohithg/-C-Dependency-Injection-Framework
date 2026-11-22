"""YouTube Shorts through the YouTube Data API v3 (free; default quota 100 uploads a day).

One-time setup (`desk.py login youtube`):
  1. console.cloud.google.com: new project, enable "YouTube Data API v3".
  2. OAuth consent screen: External, add yourself, then click "Publish app" so the refresh
     token doesn't expire after 7 days (you'll click past "Google hasn't verified this app").
  3. Credentials -> OAuth client ID -> Desktop app -> download JSON.
  4. `python3 desk.py login youtube --client-secret ~/Downloads/client_secret_....json`
"""

import json
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import load_secret, save_secret

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"
GAMING = "20"


def _session(session):
    if session is None:
        import requests
        session = requests.Session()
    return session


def login(client_secret_path, open_browser=webbrowser.open, session=None):
    """Loopback OAuth for a Desktop client; stores the refresh token in ~/.config/clipper."""
    raw = json.loads(Path(client_secret_path).expanduser().read_text())
    client = raw.get("installed") or raw.get("web") or raw
    state = secrets.token_urlsafe(16)
    got = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"YouTube connected. You can close this tab.")

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}"
    url = AUTH + "?" + urllib.parse.urlencode({
        "client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPES, "access_type": "offline", "prompt": "consent", "state": state})
    print(f"Opening Google sign-in. If no browser opens, visit:\n{url}")
    open_browser(url)
    while "code" not in got and "error" not in got:
        server.handle_request()
    server.server_close()
    if got.get("state") != state or "code" not in got:
        raise RuntimeError(f"sign-in failed: {got.get('error', 'state mismatch')}")
    r = _session(session).post(TOKEN, data={
        "code": got["code"], "client_id": client["client_id"], "client_secret": client["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=60).json()
    if "refresh_token" not in r:
        raise RuntimeError(f"no refresh token: {r}")
    save_secret("youtube", {"client_id": client["client_id"], "client_secret": client["client_secret"],
                            "refresh_token": r["refresh_token"]})
    return True


class YouTube:
    def __init__(self, creds=None, session=None):
        self.creds = creds or load_secret("youtube")
        if not self.creds:
            raise RuntimeError("YouTube isn't connected: run `python3 desk.py login youtube`")
        self.http = _session(session)
        self._token, self._expires = None, 0

    def token(self):
        if not self._token or time.time() > self._expires - 60:
            r = self.http.post(TOKEN, data={
                "client_id": self.creds["client_id"], "client_secret": self.creds["client_secret"],
                "refresh_token": self.creds["refresh_token"], "grant_type": "refresh_token"}, timeout=60)
            data = r.json()
            if "access_token" not in data:
                raise RuntimeError(f"YouTube token refresh failed: {data.get('error_description') or data}")
            self._token, self._expires = data["access_token"], time.time() + data.get("expires_in", 3600)
        return self._token

    def _auth(self, extra=None):
        return {"Authorization": f"Bearer {self.token()}", **(extra or {})}

    def post(self, video, entry):
        video = Path(video)
        body = {"snippet": {"title": entry["title"][:100], "description": entry["description"][:5000],
                            "categoryId": GAMING, "tags": entry.get("tags", [])},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
                # Since Nov 2026 a missing value no longer means "no paid placement".
                "paidProductPlacementDetails": {"hasPaidProductPlacement": bool(entry.get("campaign"))}}
        r = self.http.post(f"{UPLOAD}?uploadType=resumable&part=snippet,status,paidProductPlacementDetails",
                           headers=self._auth({"Content-Type": "application/json; charset=UTF-8",
                                               "X-Upload-Content-Type": "video/mp4",
                                               "X-Upload-Content-Length": str(video.stat().st_size)}),
                           data=json.dumps(body), timeout=60)
        if r.status_code >= 400 or "Location" not in r.headers:
            raise RuntimeError(f"YouTube upload refused: {r.status_code} {r.text[:300]}")
        with open(video, "rb") as f:
            up = self.http.put(r.headers["Location"], headers=self._auth({"Content-Type": "video/mp4"}),
                               data=f, timeout=1800)
        data = up.json()
        if up.status_code >= 400 or "id" not in data:
            raise RuntimeError(f"YouTube upload failed: {up.status_code} {str(data)[:300]}")
        vid = data["id"]
        if entry.get("comment"):
            try:
                self.http.post(f"{API}/commentThreads?part=snippet", headers=self._auth(), timeout=60, json={
                    "snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": entry["comment"]}}}})
            except Exception:
                pass  # the source is in the description too
        return {"url": f"https://www.youtube.com/shorts/{vid}", "ref": vid}

    def counts(self, ref):
        r = self.http.get(f"{API}/videos", params={"part": "statistics", "id": ref},
                          headers=self._auth(), timeout=60).json()
        s = (r.get("items") or [{}])[0].get("statistics", {})
        n = lambda k: int(s[k]) if k in s else None  # noqa: E731
        return {"views": n("viewCount"), "likes": n("likeCount"), "comments": n("commentCount"), "shares": None}
