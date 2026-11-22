"""Instagram Reels through the Instagram Graph API with Facebook Login (free; 100 posts a day).

This route (not "Instagram Login") is the one that accepts a local file, so no public hosting
is needed. A Page token made from a long-lived user token doesn't expire, so after the one-time
setup nothing needs renewing.

One-time setup (`desk.py login instagram`):
  1. Make the Instagram account a Professional (Creator) account and link it to a Facebook Page.
  2. developers.facebook.com: create an app (type Business), add "Instagram" and "Facebook
     Login for Business". You are its admin, so it works in development mode for your accounts.
  3. Graph API Explorer: pick the app, add permissions instagram_basic,
     instagram_content_publish, instagram_manage_comments, instagram_manage_insights,
     pages_show_list, pages_read_engagement, business_management -> Generate Access Token.
  4. `python3 desk.py login instagram --app-id ID` and paste the app secret and that token
     when asked (they are not echoed or saved anywhere but ~/.config/clipper).
"""

import time
from pathlib import Path

from . import load_secret, save_secret

GRAPH = "https://graph.facebook.com/v23.0"


def _session(session):
    if session is None:
        import requests
        session = requests.Session()
    return session


def _check(r, what):
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        raise RuntimeError(f"Instagram {what}: {err.get('message') or data}")
    return data


def login(app_id, app_secret, short_token, session=None, page_name=None):
    http = _session(session)
    long = _check(http.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
        "fb_exchange_token": short_token}, timeout=60), "token exchange")["access_token"]
    pages = _check(http.get(f"{GRAPH}/me/accounts", params={
        "fields": "name,access_token,instagram_business_account{id,username}", "access_token": long},
        timeout=60), "page list")["data"]
    pages = [p for p in pages if p.get("instagram_business_account")
             and (not page_name or p["name"].lower() == page_name.lower())]
    if not pages:
        raise RuntimeError("no Facebook Page with a linked Instagram professional account was found")
    p = pages[0]
    ig = p["instagram_business_account"]
    save_secret("instagram", {"ig_user_id": ig["id"], "username": ig.get("username", ""),
                              "page": p["name"], "token": p["access_token"]})
    return ig.get("username") or ig["id"]


class Instagram:
    def __init__(self, creds=None, session=None, poll_seconds=5, poll_limit=120):
        self.creds = creds or load_secret("instagram")
        if not self.creds:
            raise RuntimeError("Instagram isn't connected: run `python3 desk.py login instagram`")
        self.http = _session(session)
        self.poll_seconds, self.poll_limit = poll_seconds, poll_limit

    def _p(self, **kw):
        return {"access_token": self.creds["token"], **kw}

    def post(self, video, entry):
        video = Path(video)
        ig = self.creds["ig_user_id"]
        box = _check(self.http.post(f"{GRAPH}/{ig}/media", data=self._p(
            media_type="REELS", upload_type="resumable", caption=entry["caption"][:2200],
            share_to_feed="true"), timeout=60), "container")
        with open(video, "rb") as f:
            _check(self.http.post(box.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v23.0/{box['id']}",
                                  headers={"Authorization": f"OAuth {self.creds['token']}", "offset": "0",
                                           "file_size": str(video.stat().st_size)}, data=f, timeout=1800),
                   "upload")
        for _ in range(self.poll_limit):
            status = _check(self.http.get(f"{GRAPH}/{box['id']}", params=self._p(fields="status_code,status"),
                                          timeout=60), "status")
            if status.get("status_code") == "FINISHED":
                break
            if status.get("status_code") in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram processing failed: {status.get('status')}")
            time.sleep(self.poll_seconds)
        else:
            raise RuntimeError("Instagram took too long to process the video")
        media = _check(self.http.post(f"{GRAPH}/{ig}/media_publish", data=self._p(creation_id=box["id"]),
                                      timeout=60), "publish")["id"]
        link = _check(self.http.get(f"{GRAPH}/{media}", params=self._p(fields="permalink"), timeout=60),
                      "permalink").get("permalink", "")
        if entry.get("comment"):
            try:
                self.http.post(f"{GRAPH}/{media}/comments", data=self._p(message=entry["comment"]), timeout=60)
            except Exception:
                pass
        return {"url": link, "ref": media}

    def counts(self, ref):
        m = _check(self.http.get(f"{GRAPH}/{ref}", params=self._p(fields="like_count,comments_count"),
                                 timeout=60), "counts")
        views = shares = None
        try:
            ins = _check(self.http.get(f"{GRAPH}/{ref}/insights", params=self._p(metric="views,shares"),
                                       timeout=60), "insights")
            got = {d["name"]: d["values"][0]["value"] for d in ins.get("data", [])}
            views, shares = got.get("views"), got.get("shares")
        except RuntimeError:
            pass
        return {"views": views, "likes": m.get("like_count"), "comments": m.get("comments_count"),
                "shares": shares}
