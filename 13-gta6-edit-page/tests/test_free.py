"""The free path: local outbox, official free APIs (faked HTTP), browser posting (mock sites)."""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"  # never reach a real local model in tests
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import desk  # noqa: E402
import page  # noqa: E402
from clipper import outbox, posters, publish, stats, studio  # noqa: E402
from clipper.posters import instagram, youtube  # noqa: E402
from test_desk import make_approved_clip, set_desk  # noqa: E402

TZ = "America/Los_Angeles"


def at(day, hh, mm=0):
    return datetime(2026, 11, day, hh, mm, tzinfo=ZoneInfo(TZ))


class Resp:
    def __init__(self, data=None, status=200, headers=None):
        self._data, self.status_code, self.headers = data or {}, status, headers or {}
        self.text = json.dumps(self._data)

    def json(self):
        return self._data


class FakeHTTP:
    """Routes (method, url-prefix) to handlers and records every call."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _go(self, method, url, **kw):
        if "data" in kw and hasattr(kw["data"], "read"):
            kw["body"] = kw["data"].read()
        self.calls.append((method, url, kw))
        for (m, prefix), fn in self.routes.items():
            if m == method and url.startswith(prefix):
                return fn(url, kw)
        raise AssertionError(f"unexpected {method} {url}")

    def get(self, url, **kw):
        return self._go("GET", url, **kw)

    def post(self, url, **kw):
        return self._go("POST", url, **kw)

    def put(self, url, **kw):
        return self._go("PUT", url, **kw)


class FakePoster:
    def __init__(self, platform, fail_times=0):
        self.platform, self.fail_times, self.posted = platform, fail_times, []

    def post(self, video, entry):
        assert Path(video).exists()
        if self.fail_times:
            self.fail_times -= 1
            raise RuntimeError("upload page changed")
        self.posted.append(entry)
        n = len(self.posted)
        return {"url": f"https://{self.platform}.example/{entry['id']}", "ref": f"{self.platform}-{n}"}

    def counts(self, ref):
        return {"views": 4321, "likes": 99, "comments": 5, "shares": None}


class FreeDeskTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        self.page = page.init_page(self.tmp / "pg", {"name": "Six Stars Desk"})
        self.fakes = {p: FakePoster(p) for p in ("tiktok", "youtube", "instagram", "x")}
        self.get_poster = self.fakes.__getitem__

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_template_is_free_and_automatic_by_default(self):
        cfg = publish.load_desk(self.page)
        self.assertEqual(publish.provider(cfg), "free")
        self.assertTrue(cfg["auto_approve"]["enabled"])
        self.assertEqual(posters.routes(cfg)["tiktok"], "browser")

    def test_schedule_books_the_outbox_and_posts_when_due(self):
        cid = make_approved_clip(self.page)
        done = publish.schedule(self.page, cid, now=at(22, 9))
        self.assertEqual([d["job"] for d in done], ["outbox"] * 4)
        box = outbox.load(self.page)
        self.assertEqual([e["due"][11:16] for e in box], ["12:00", "12:20", "12:40", "13:00"])
        yt = next(e for e in box if e["platform"] == "youtube")
        self.assertEqual(yt["title"], "Kai vs 6 stars")
        self.assertIn("10:12:05", yt["description"])
        self.assertIn("kaicenat", yt["tags"])
        self.assertTrue(all(r["notes"] == "outbox" for r in page.read_board(self.page)))

        posted, failed = outbox.flush(self.page, at(22, 12, 25), self.get_poster)
        self.assertEqual([e["platform"] for e in posted], ["tiktok", "youtube"])
        posted, _ = outbox.flush(self.page, at(22, 21, 0), self.get_poster)
        self.assertEqual([e["platform"] for e in posted], ["instagram", "x"])
        rows = {r["platform"]: r for r in page.read_board(self.page)}
        self.assertEqual(rows["x"]["post_url"], f"https://x.example/{rows['x']['post_id']}")
        self.assertEqual(rows["x"]["date"], "2026-11-22T21:00")
        self.assertEqual(rows["x"]["notes"], "posted x:x-1")
        self.assertEqual(outbox.flush(self.page, at(23, 9), self.get_poster), ([], []))

    def test_x_caption_is_cut_to_280_and_campaigns_get_ad(self):
        cid = make_approved_clip(self.page)
        post = self.page / "posts" / f"{json.loads((self.page / 'runs/kai_part1/clips/m01/meta.json').read_text())['slug']}.md"
        post.write_text(post.read_text().replace("## X\n", "## X\n" + "word " * 80 + "\n", 1))
        publish.schedule(self.page, cid, ["x"], now=at(22, 9), campaign="Brand")
        cap = outbox.load(self.page)[0]["caption"]
        self.assertTrue(cap.startswith("#ad "))
        self.assertLessEqual(len(cap), 280)

    def test_failed_posts_back_off_then_give_up(self):
        cid = make_approved_clip(self.page)
        publish.schedule(self.page, cid, ["tiktok"], now=at(22, 9))
        self.fakes["tiktok"].fail_times = 5
        now = at(22, 12, 1)
        self.assertEqual(outbox.flush(self.page, now, self.get_poster), ([], []))
        e = outbox.load(self.page)[0]
        self.assertEqual((e["attempts"], e["next_try"][11:16]), (1, "12:31"))
        self.assertEqual(outbox.flush(self.page, now + timedelta(minutes=5), self.get_poster), ([], []))
        outbox.flush(self.page, at(22, 12, 31), self.get_poster)
        _, failed = outbox.flush(self.page, at(22, 13, 31), self.get_poster)
        self.assertEqual(len(failed), 1)
        self.assertIn("post failed: upload page changed", page.read_board(self.page)[0]["notes"])
        desk.main(["outbox", str(self.page), "--retry", e["id"]])
        self.fakes["tiktok"].fail_times = 0
        posted, _ = outbox.flush(self.page, at(22, 14), self.get_poster)
        self.assertEqual(len(posted), 1)

    def test_stats_use_the_platform_api_for_posts_it_made(self):
        cid = make_approved_clip(self.page)
        publish.schedule(self.page, cid, ["youtube"], now=at(10, 9))
        outbox.flush(self.page, at(10, 12, 30), self.get_poster)
        got = stats.pull(self.page, datetime(2026, 11, 11, 13, 0), get_poster=self.get_poster,
                         counts=None, cookies_from_browser=None)
        self.assertEqual([g[1:] for g in got], [("24h", 4321)])
        self.assertEqual(page.read_board(self.page)[0]["likes"], "99")

    def test_auto_approve_gates_and_daily_cap(self):
        def draft(mid, **kw):
            d = self.page / "runs/kai_part1/clips" / mid
            d.mkdir(parents=True)
            (d / "final.mp4").write_bytes(b"\0")
            meta = {"moment": {"vod_in": "1:00:00", "vod_out": "1:00:30", "score": 80}, "hook": "Kai vs 6 stars",
                    "credit": "Kai Cenat (YouTube)", "status": "draft", "duration": 30, "lufs": -14.2}
            meta.update(kw)
            (d / "meta.json").write_text(json.dumps(meta))
        draft("m01")
        (self.page / "runs/kai_part1/source.json").write_text(json.dumps({"streamer": "Kai Cenat"}))
        draft("m02", moment={"score": 10})
        draft("m03", duration=95)
        draft("m04", lufs=-19.0)
        draft("m05")
        draft("m06")
        set_desk(self.page, auto_approve={"enabled": True, "min_score": 60, "max_per_day": 2})
        cfg = publish.load_desk(self.page)
        today = at(22, 9).date()
        self.assertEqual(desk.auto_approve(self.page, cfg, today), ["kai_part1/m01", "kai_part1/m05"])
        self.assertEqual(desk.auto_approve(self.page, cfg, today), [])
        self.assertEqual(desk.auto_approve(self.page, cfg, today + timedelta(days=1)), ["kai_part1/m06"])
        cfg["auto_approve"]["enabled"] = False
        self.assertEqual(desk.auto_approve(self.page, cfg, today + timedelta(days=2)), [])

    def test_tick_books_and_posts_without_any_key_and_reports_nightly(self):
        os.environ.pop("UPLOAD_POST_API_KEY", None)
        cid = make_approved_clip(self.page)
        studio.set_fields(self.page, cid, queue=True)
        set_desk(self.page, platforms=["youtube", "x"], notify={"ntfy_topic": "t"})
        sent = []
        kw = dict(lister=lambda url: [], counts=lambda url: {"views": 100}, get_poster=self.get_poster,
                  sender=lambda d, t, m: sent.append(m))
        r1 = desk.tick(self.page, now=at(22, 9), **kw)
        self.assertEqual((len(r1["scheduled"]), r1["posted"]), (2, []))
        r2 = desk.tick(self.page, now=at(22, 23, 45), **kw)
        self.assertEqual(sorted(e["platform"] for e in r2["posted"]), ["x", "youtube"])
        self.assertIn("Posted: ", sent[-1])
        r3 = desk.tick(self.page, now=at(23, 23, 50), **kw)
        self.assertEqual(len(r3["stats"]), 2)
        self.assertTrue(any(line.startswith("Nightly: best") for line in r3["reports"]))
        r4 = desk.tick(self.page, now=at(23, 23, 55), **kw)
        self.assertEqual(r4["reports"], [])

    def test_doctor_lists_what_still_needs_connecting(self):
        lines = {name: ok for name, ok, _ in desk.doctor(self.page)}
        self.assertFalse(lines["tiktok (browser)"])
        self.assertFalse(lines["youtube (api)"])
        self.assertTrue(lines["auto-approve"])

    def test_cron_line_carries_path_for_ffmpeg(self):
        cron, plist = desk.cron_lines(self.page)
        self.assertIn("PATH=", cron)
        self.assertIn("<key>PATH</key>", plist)


class YouTubeApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        self.video = self.tmp / "v.mp4"
        self.video.write_bytes(b"\1" * 1000)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_resumable_upload_public_with_comment(self):
        http = FakeHTTP({
            ("POST", youtube.TOKEN): lambda u, kw: Resp({"access_token": "AT", "expires_in": 3600}),
            ("POST", youtube.UPLOAD): lambda u, kw: Resp(headers={"Location": "https://up.example/s1"}),
            ("PUT", "https://up.example/s1"): lambda u, kw: Resp({"id": "abc123"}),
            ("POST", youtube.API + "/commentThreads"): lambda u, kw: Resp({"id": "c1"}),
            ("GET", youtube.API + "/videos"): lambda u, kw: Resp({"items": [{"statistics": {
                "viewCount": "5000", "likeCount": "300", "commentCount": "12"}}]}),
        })
        yt = youtube.YouTube({"client_id": "cid", "client_secret": "cs", "refresh_token": "rt"}, session=http)
        got = yt.post(self.video, {"title": "Kai vs 6 stars", "description": "desc", "tags": ["gta6"],
                                   "comment": "Source: Kai", "campaign": ""})
        self.assertEqual(got, {"url": "https://www.youtube.com/shorts/abc123", "ref": "abc123"})
        init = http.calls[1][2]
        body = json.loads(init["data"])
        self.assertEqual(body["status"]["privacyStatus"], "public")
        self.assertIs(body["paidProductPlacementDetails"]["hasPaidProductPlacement"], False)
        self.assertEqual(init["headers"]["Authorization"], "Bearer AT")
        self.assertEqual(init["headers"]["X-Upload-Content-Length"], "1000")
        self.assertEqual(http.calls[2][2]["body"], b"\1" * 1000)
        self.assertEqual(http.calls[3][2]["json"]["snippet"]["videoId"], "abc123")
        self.assertEqual(yt.counts("abc123")["views"], 5000)
        self.assertEqual(sum(1 for c in http.calls if c[1] == youtube.TOKEN), 1)

    def test_login_saves_the_refresh_token(self):
        secret = self.tmp / "client.json"
        secret.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "cs"}}))
        http = FakeHTTP({("POST", youtube.TOKEN): lambda u, kw: Resp({"refresh_token": "RT", "access_token": "x"})})

        def browser(url):
            q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
            redirect = urllib.request.unquote(q["redirect_uri"])
            threading.Thread(target=lambda: urllib.request.urlopen(
                f"{redirect}/?code=CODE&state={q['state']}").read(), daemon=True).start()

        youtube.login(secret, open_browser=browser, session=http)
        self.assertEqual(posters.load_secret("youtube")["refresh_token"], "RT")
        self.assertEqual(http.calls[0][2]["data"]["code"], "CODE")
        self.assertEqual(oct((Path(os.environ["CLIPPER_CONFIG"]) / "youtube.json").stat().st_mode & 0o777), "0o600")


class InstagramApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        self.video = self.tmp / "v.mp4"
        self.video.write_bytes(b"\2" * 2048)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_resumable_reel_publish(self):
        G = instagram.GRAPH
        polls = iter(["IN_PROGRESS", "FINISHED"])
        http = FakeHTTP({
            ("POST", f"{G}/IG1/media_publish"): lambda u, kw: Resp({"id": "M9"}),
            ("POST", f"{G}/IG1/media"): lambda u, kw: Resp({"id": "C7", "uri": "https://rupload.facebook.com/ig-api-upload/v23.0/C7"}),
            ("POST", "https://rupload.facebook.com/"): lambda u, kw: Resp({"success": True}),
            ("GET", f"{G}/C7"): lambda u, kw: Resp({"status_code": next(polls)}),
            ("GET", f"{G}/M9/insights"): lambda u, kw: Resp({"data": [{"name": "views", "values": [{"value": 777}]}]}),
            ("GET", f"{G}/M9"): lambda u, kw: Resp({"permalink": "https://www.instagram.com/reel/XYZ/",
                                                    "like_count": 40, "comments_count": 3}),
            ("POST", f"{G}/M9/comments"): lambda u, kw: Resp({"id": "cm"}),
        })
        ig = instagram.Instagram({"ig_user_id": "IG1", "token": "PT"}, session=http, poll_seconds=0)
        got = ig.post(self.video, {"caption": "Kai vs 6 stars #gta6", "comment": "Source: Kai"})
        self.assertEqual(got, {"url": "https://www.instagram.com/reel/XYZ/", "ref": "M9"})
        box = http.calls[0][2]["data"]
        self.assertEqual((box["media_type"], box["upload_type"]), ("REELS", "resumable"))
        up = http.calls[1][2]
        self.assertEqual(up["headers"]["file_size"], "2048")
        self.assertEqual(up["headers"]["Authorization"], "OAuth PT")
        self.assertEqual(up["body"], b"\2" * 2048)
        self.assertEqual(ig.counts("M9"), {"views": 777, "likes": 40, "comments": 3, "shares": None})

    def test_login_finds_the_linked_page(self):
        G = instagram.GRAPH
        http = FakeHTTP({
            ("GET", f"{G}/oauth/access_token"): lambda u, kw: Resp({"access_token": "LONG"}),
            ("GET", f"{G}/me/accounts"): lambda u, kw: Resp({"data": [
                {"name": "Other", "access_token": "P0"},
                {"name": "Six Stars", "access_token": "P1",
                 "instagram_business_account": {"id": "IG1", "username": "sixstarsdesk"}}]}),
        })
        self.assertEqual(instagram.login("app", "secret", "SHORT", session=http), "sixstarsdesk")
        self.assertEqual(posters.load_secret("instagram")["token"], "P1")
        self.assertEqual(http.calls[0][2]["params"]["fb_exchange_token"], "SHORT")


MOCK_TIKTOK = """<html><body>
<input type=file id=f>
<div contenteditable=true id=cap>old</div>
<button data-e2e=post_video_button disabled id=go>Post</button>
<script>
document.getElementById('f').onchange = () => setTimeout(() => document.getElementById('go').disabled = false, 400);
document.getElementById('go').onclick = () => fetch('/posted', {method: 'POST',
  body: document.getElementById('cap').innerText}).then(() => location.href = '/tiktokstudio/content');
</script></body></html>"""

MOCK_X = """<html><body>
<input type=file data-testid=fileInput id=f>
<div contenteditable=true data-testid=tweetTextarea_0 id=cap></div>
<button data-testid=tweetButton aria-disabled=true id=go>Post</button>
<script>
document.getElementById('f').onchange = () => setTimeout(() => document.getElementById('go').setAttribute('aria-disabled', 'false'), 300);
document.getElementById('go').onclick = () => fetch('/posted', {method: 'POST', body: document.getElementById('cap').innerText})
  .then(() => { const t = document.createElement('div'); t.dataset.testid = 'toast';
    t.innerHTML = 'Your post was sent. <a href="/sixstars/status/1999">View</a>'; document.body.appendChild(t); });
</script></body></html>"""


MOCK_TIKTOK_CONTENT = """<html><body><a href="/@sixstars/video/7001">newest</a></body></html>"""

MOCK_YT = """<html><body>
<input type=file id=f>
<div id=title-textarea><div id=textbox contenteditable=true>v.mp4</div></div>
<div id=description-textarea><div id=textbox contenteditable=true></div></div>
<div id=kids hidden><tp-yt-paper-radio-button name=VIDEO_MADE_FOR_KIDS_NOT_MFK onclick="window.kids=1">no</tp-yt-paper-radio-button></div>
<button id=next-button onclick="window.next=(window.next||0)+1;
  if (window.next==3) document.getElementById('vis').hidden=false">Next</button>
<div id=vis hidden><tp-yt-paper-radio-button name=PUBLIC onclick="window.pub=1">Public</tp-yt-paper-radio-button>
  <span class=video-url-fadeable><a href="https://youtube.com/shorts/SHORT1">link</a></span></div>
<button id=done-button disabled onclick="fetch('/posted',{method:'POST',body:JSON.stringify({
  title: document.querySelector('#title-textarea #textbox').innerText,
  desc: document.querySelector('#description-textarea #textbox').innerText,
  kids: window.kids, next: window.next, pub: window.pub})})">Done</button>
<script>
document.getElementById('f').onchange = () => { document.getElementById('kids').hidden = false;
  setTimeout(() => document.getElementById('done-button').disabled = false, 300); };
</script></body></html>"""


class BrowserPosterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import playwright  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("playwright not installed")
        cls.captions = []
        captions = cls.captions

        class Site(BaseHTTPRequestHandler):
            def do_GET(self):
                body = {"/tiktokstudio/upload": MOCK_TIKTOK, "/compose/post": MOCK_X, "/upload": MOCK_YT,
                        "/tiktokstudio/content": MOCK_TIKTOK_CONTENT}.get(self.path, "<p>done</p>")
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body.encode())

            def do_POST(self):
                captions.append(self.rfile.read(int(self.headers["Content-Length"])).decode())
                self.send_response(204)
                self.end_headers()

            def log_message(self, *a):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        self.video = self.tmp / "v.mp4"
        self.video.write_bytes(b"\0" * 64)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_tiktok_upload_types_caption_and_waits_for_processing(self):
        from clipper.posters.browser import BrowserPoster
        p = BrowserPoster("tiktok", {"base_url": self.base, "upload_timeout_s": 20})
        got = p.post(self.video, {"caption": "Kai vs 6 stars\nKai Cenat (YouTube) #gta6"})
        self.assertEqual(got, {"url": f"{self.base}/@sixstars/video/7001", "ref": "7001"})
        self.assertEqual(self.captions[-1].replace("\r", ""), "Kai vs 6 stars\nKai Cenat (YouTube) #gta6")

    def test_x_returns_the_post_url_from_the_toast(self):
        from clipper.posters.browser import BrowserPoster
        p = BrowserPoster("x", {"base_url": self.base, "upload_timeout_s": 20})
        got = p.post(self.video, {"caption": "Kai vs 6 stars"})
        self.assertEqual(got, {"url": f"{self.base}/sixstars/status/1999", "ref": "1999"})
        self.assertEqual(self.captions[-1], "Kai vs 6 stars")


    def test_youtube_studio_flow_needs_no_developer_app(self):
        from clipper.posters.browser import SITES, BrowserPoster
        steps = [[k, self.base + "/upload" if v == "https://www.youtube.com/upload" else v, *rest]
                 for k, v, *rest in SITES["youtube"]["steps"]]
        p = BrowserPoster("youtube", {"base_url": self.base, "upload_timeout_s": 20, "steps": {"youtube": steps}})
        got = p.post(self.video, {"title": "Kai vs 6 stars", "description": "Source: Kai\n#gta6"})
        self.assertEqual(got, {"url": "https://youtube.com/shorts/SHORT1", "ref": "SHORT1"})
        sent = json.loads(self.captions[-1])
        self.assertEqual((sent["title"], sent["kids"], sent["next"], sent["pub"]), ("Kai vs 6 stars", 1, 3, 1))
        self.assertEqual(sent["desc"].replace("\r", ""), "Source: Kai\n#gta6")

    def test_a_missing_element_names_the_step_that_broke(self):
        from clipper.posters.browser import BrowserPoster
        p = BrowserPoster("x", {"base_url": self.base, "steps": {"x": [["goto", "/compose/post"],
                                                                      ["click", "#no-such-button"]]}})
        import clipper.posters.browser as b
        orig = b.BrowserPoster._run

        def fast(self, page, step, entry, video):
            page.set_default_timeout(1000)
            if step[0] == "click":
                page.locator(step[1]).first.click(timeout=1000)
                return None
            return orig(self, page, step, entry, video)
        b.BrowserPoster._run = fast
        try:
            with self.assertRaisesRegex(RuntimeError, "x step click '#no-such-button' failed"):
                p.post(self.video, {"caption": "x"})
        finally:
            b.BrowserPoster._run = orig

    def test_handle_steps_are_skipped_without_a_handle(self):
        from clipper.posters.browser import BrowserPoster
        p = BrowserPoster("instagram", {"handles": {"instagram": "YOUR_INSTAGRAM_HANDLE"}})
        self.assertIsNone(p._run(None, ["goto", "/{handle}/reels/"], {}, self.video))


if __name__ == "__main__":
    unittest.main()
