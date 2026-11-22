import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import desk  # noqa: E402
import page  # noqa: E402
from clipper import notify, publish, sources, stats, studio  # noqa: E402

TZ = "America/Los_Angeles"


class FakeUploadPost:
    def __init__(self):
        self.uploads, self.jobs = [], {}

    def upload(self, video, fields):
        assert Path(video).exists()
        self.uploads.append(dict(fields))
        job = f"job{len(self.uploads)}"
        self.jobs[job] = fields["platform[]"]
        return {"success": True, "job_id": job, "scheduled_date": fields["scheduled_date"]}

    def status(self, job_id=None, request_id=None):
        p = self.jobs[job_id]
        return {"status": "completed", "results": [
            {"platform": p, "success": True, "post_url": f"https://{p}.example/{job_id}"}]}


def make_approved_clip(page_dir, vod="kai_part1", mid="m01", hook="Kai vs 6 stars"):
    clip_dir = page_dir / "runs" / vod / "clips" / mid
    clip_dir.mkdir(parents=True)
    (clip_dir / "final.mp4").write_bytes(b"\0" * 64)
    (page_dir / "runs" / vod / "source.json").write_text(json.dumps(
        {"url": "https://youtube.com/watch?v=abc", "title": "GTA 6 Part 1", "streamer": "Kai Cenat",
         "platform": "YouTube"}))
    meta = {"moment": {"vod_in": "10:12:05", "vod_out": "10:12:40", "score": 80}, "hook": hook,
            "credit": "Kai Cenat (YouTube)", "status": "draft", "duration": 24.5, "cold_open": True,
            "hooks": [hook]}
    (clip_dir / "meta.json").write_text(json.dumps(meta))
    studio.approve(page_dir, f"{vod}/{mid}", hook)
    return f"{vod}/{mid}"


def set_desk(page_dir, **changes):
    cfg = json.loads((page_dir / "desk.json").read_text())
    cfg.update(changes)
    (page_dir / "desk.json").write_text(json.dumps(cfg))
    return cfg


class DeskUnitTest(unittest.TestCase):
    """The paid Upload-Post provider, and provider-independent desk behaviour."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        self.page = page.init_page(self.tmp / "pg", {"name": "Six Stars Desk"})
        set_desk(self.page, publish={"provider": "upload-post", "user": "sixstars"})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_next_slot_skips_taken_and_too_soon(self):
        now = datetime(2026, 11, 22, 11, 55, tzinfo=ZoneInfo(TZ))
        taken = [datetime(2026, 11, 22, 17, 0, tzinfo=ZoneInfo(TZ))]
        got = publish.next_slot(["12:00", "17:00", "20:30"], TZ, now, taken)
        self.assertEqual(got.strftime("%H:%M"), "20:30")
        got = publish.next_slot(["12:00"], TZ, now + timedelta(hours=1), [])
        self.assertEqual((got.day, got.strftime("%H:%M")), (23, "12:00"))

    def test_schedule_staggers_platforms_and_logs_the_board(self):
        cid = make_approved_clip(self.page)
        fake = FakeUploadPost()
        now = datetime(2026, 11, 22, 11, 0, tzinfo=ZoneInfo(TZ))
        done = publish.schedule(self.page, cid, client=fake, now=now)
        self.assertEqual([d["platform"] for d in done], ["tiktok", "youtube", "instagram", "x"])
        self.assertEqual([u["scheduled_date"][11:16] for u in fake.uploads],
                         ["12:00", "12:20", "12:40", "13:00"])
        tiktok, youtube, _, x = fake.uploads
        self.assertTrue(tiktok["title"].startswith("Kai vs 6 stars\nKai Cenat (YouTube)"))
        self.assertIn("#kaicenat", tiktok["title"])
        self.assertNotIn("#", x["title"])
        self.assertEqual(youtube["youtube_title"], "Kai vs 6 stars")
        self.assertIn("GTA 6 Part 1", tiktok["tiktok_first_comment"])
        self.assertIn("10:12:05", tiktok["tiktok_first_comment"])
        self.assertNotIn("paid_partnership", tiktok)
        rows = page.read_board(self.page)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["notes"], "upload-post job job1")
        meta = json.loads((self.page / "runs/kai_part1/clips/m01/meta.json").read_text())
        self.assertEqual(meta["status"], "scheduled")
        with self.assertRaises(ValueError):
            publish.schedule(self.page, cid, client=fake, now=now)

        self.assertEqual(publish.resolve_urls(self.page, fake), 4)
        self.assertEqual(page.read_board(self.page)[3]["post_url"], "https://x.example/job4")

    def test_queued_clip_goes_out_on_the_next_tick(self):
        os.environ.pop("UPLOAD_POST_API_KEY", None)
        cid = make_approved_clip(self.page)
        self.assertTrue(studio.queue_post(self.page, cid)["queue"])
        fake = FakeUploadPost()
        report = desk.tick(self.page, now=datetime(2026, 11, 22, 9, 0, tzinfo=ZoneInfo(TZ)), client=fake,
                           lister=lambda url: [], counts=lambda url: None, sender=lambda *a: None)
        self.assertEqual(len(report["scheduled"]), 4)
        self.assertEqual(report["urls"], 4)

    def test_campaign_posts_get_ad_and_paid_label(self):
        cid = make_approved_clip(self.page)
        fake = FakeUploadPost()
        publish.schedule(self.page, cid, ["tiktok"], client=fake, campaign="Brand X",
                         now=datetime(2026, 11, 22, 9, 0, tzinfo=ZoneInfo(TZ)))
        self.assertTrue(fake.uploads[0]["title"].startswith("#ad "))
        self.assertEqual(fake.uploads[0]["paid_partnership"], "true")
        self.assertEqual(page.read_board(self.page)[0]["campaign"], "Brand X")
        publish.resolve_urls(self.page, fake)
        self.assertEqual(desk.campaign_links(self.page, "brand x"), ["https://tiktok.example/job1"])
        self.assertEqual(desk.campaign_links(self.page, "brand x", since="2026-12-01"), [])

    def test_stats_fill_only_the_checkpoint_due_now(self):
        old = page.log_post(self.page, {"date": "2026-11-10T12:00", "platform": "tiktok",
                                        "format": "single", "post_url": "https://t.example/1"})
        fresh = page.log_post(self.page, {"date": "2026-11-21T10:00", "platform": "youtube",
                                          "format": "single", "post_url": "https://y.example/2"})
        page.log_post(self.page, {"date": "2026-11-20T10:00", "platform": "x", "format": "single"})
        seen = []

        def counts(url):
            seen.append(url)
            return {"views": 1000 * len(seen), "likes": 7, "comments": 3, "shares": None}

        filled = stats.pull(self.page, datetime(2026, 11, 22, 11, 0), counts=counts)
        self.assertEqual(sorted(f[:2] for f in filled), sorted([(old, "7d"), (fresh, "24h")]))
        rows = {r["post_id"]: r for r in page.read_board(self.page)}
        self.assertEqual((rows[old]["views_24h"], rows[old]["views_7d"]), ("", "1000"))
        self.assertEqual(rows[fresh]["likes"], "7")
        self.assertEqual(stats.pull(self.page, datetime(2026, 11, 22, 11, 0), counts=counts), [])

    def test_old_boards_without_post_url_still_load(self):
        (self.page / "board.csv").write_text(",".join(page.BOARD_COLUMNS[:-1]) + "\n")
        page.log_post(self.page, {"date": "2026-11-21T10:00", "platform": "x", "format": "single"})
        self.assertEqual(page.read_board(self.page)[0]["post_url"], "")

    def test_notify_ntfy_and_discord(self):
        sent = []
        os.environ["TEST_HOOK"] = "https://discord.example/hook"
        try:
            got = notify.send({"notify": {"ntfy_topic": "six-stars-xyz", "discord_webhook_env": "TEST_HOOK"}},
                              "GTA 6 edit desk", "3 new drafts", opener=lambda req, timeout: sent.append(req))
        finally:
            del os.environ["TEST_HOOK"]
        self.assertEqual(got, ["ntfy", "discord"])
        self.assertEqual(sent[0].full_url, "https://ntfy.sh/six-stars-xyz")
        self.assertIn(b"3 new drafts", sent[1].data)

    def test_tick_skips_while_another_tick_holds_the_lock(self):
        import fcntl
        lock = open(desk._state_path(self.page).with_name("tick.lock"), "w")
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            self.assertIsNone(desk.tick(self.page, sender=lambda *a: None))
        finally:
            lock.close()

    def test_a_vod_that_keeps_failing_is_dropped_after_three_tries(self):
        cfg = json.loads((self.page / "desk.json").read_text())
        cfg["watch"] = [{"streamer": "Kai Cenat", "url": "chan"}]
        (self.page / "desk.json").write_text(json.dumps(cfg))
        sent = []
        for _ in range(3):
            desk.tick(self.page, now=datetime(2026, 11, 22, 9, 0, tzinfo=ZoneInfo(TZ)), lister=lambda url: [{"id": "gone", "url": str(self.tmp / "missing.mp4")}],
                      counts=lambda url: None, sender=lambda d, t, m: sent.append(m))
        self.assertEqual(desk.load_state(self.page)["seen"]["chan"], ["gone"])
        self.assertEqual(len(sent), 1)
        self.assertIn("Gave up after 3 tries", sent[0])

    def test_new_vods_takes_only_the_newest_on_first_sight(self):
        state = {"seen": {}, "countdowns": []}
        cfg = {"watch": [{"streamer": "Kai Cenat", "url": "chan"}]}
        listing = [{"id": "v3", "url": "u3"}, {"id": "v2", "url": "u2"}, {"id": "v1", "url": "u1"}]
        got = desk.new_vods(self.page, cfg, state, lister=lambda url: listing)
        self.assertEqual([v["id"] for _, v in got], ["v3"])
        state["seen"]["chan"].append("v3")
        listing.insert(0, {"id": "v4", "url": "u4"})
        got = desk.new_vods(self.page, cfg, state, lister=lambda url: listing)
        self.assertEqual([v["id"] for _, v in got], ["v4"])

    def test_local_folder_watch_waits_for_recordings_to_settle(self):
        rec = self.tmp / "recordings"
        rec.mkdir()
        (rec / "old.mp4").write_bytes(b"x")
        past = time.time() - 600
        os.utime(rec / "old.mp4", (past, past))
        (rec / "still_recording.mp4").write_bytes(b"x")
        (rec / "notes.txt").write_text("x")
        self.assertEqual([v["id"] for v in sources.latest_vods(str(rec))], ["old"])


if __name__ == "__main__":
    unittest.main()
