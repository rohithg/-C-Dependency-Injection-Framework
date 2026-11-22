import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import page  # noqa: E402


class PageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir = page.init_page(self.tmp / "mypage", {
            "name": "Six Stars Desk", "handle": "sixstarsdesk", "timezone": "America/Los_Angeles"})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def log(self, when, platform="tiktok", fmt="single", **kw):
        return page.log_post(self.dir, {"date": when, "platform": platform, "format": fmt, **kw})

    def test_init_copies_structure_and_fills_placeholders(self):
        for name in ("playbook.md", "watchlist.md", "campaigns.md", "facts.md", "ideas.md",
                     "projects.md", "provenance.csv", "board.csv", "LEARNED_RULES.md",
                     "takedowns.md", "SETUP_PROMPT.md"):
            self.assertTrue((self.dir / name).exists(), name)
        for name in ("runs", "countdowns", "exports", "posts"):
            self.assertTrue((self.dir / name).is_dir(), name)
        playbook = (self.dir / "playbook.md").read_text()
        self.assertIn("Six Stars Desk (@sixstarsdesk)", playbook)
        self.assertIn("[ANGLE]", playbook)
        with self.assertRaises(FileExistsError):
            page.init_page(self.dir, {})

    def test_log_assigns_ids_per_day_and_validates(self):
        self.assertEqual(self.log("2026-11-22T10:00"), "20261122-01")
        self.assertEqual(self.log("2026-11-22T13:00"), "20261122-02")
        self.assertEqual(self.log("2026-11-23T09:00"), "20261123-01")
        with self.assertRaises(ValueError):
            self.log("2026-11-22T10:00", platform="myspace")
        self.assertEqual(len(page.read_board(self.dir)), 3)

    def test_checkpoints_are_due_only_when_old_enough_and_blank(self):
        pid = self.log("2026-11-20T10:00", hook="Kai gets six stars")
        now = datetime(2026, 11, 23, 11, 0)
        due = page.due_checkpoints(page.read_board(self.dir), now)
        self.assertEqual([d[1] for d in due], ["24h", "72h"])
        page.set_numbers(self.dir, pid, "24h", 12000)
        due = page.due_checkpoints(page.read_board(self.dir), now)
        self.assertEqual([d[1] for d in due], ["72h"])

    def test_unjudged_posts_are_left_out_of_reports(self):
        a = self.log("2026-11-20T10:00", fmt="countdown", streamer="Kai Cenat")
        b = self.log("2026-11-20T19:00", fmt="single", streamer="IShowSpeed")
        self.log("2026-11-21T19:00", fmt="single")
        page.set_numbers(self.dir, a, "24h", 5000)
        page.set_numbers(self.dir, a, "72h", 90000)
        page.set_numbers(self.dir, b, "24h", 800)
        rows = page.read_board(self.dir)
        n = page.nightly(rows)
        self.assertEqual(n["judged"], 2)
        self.assertEqual(n["best"][1]["post_id"], a)
        self.assertEqual(n["best"][0], 90000)
        rep = page.weekly(rows, date(2026, 11, 22))
        self.assertEqual(rep["posts"], 2)
        self.assertEqual(rep["by"]["format"][0][0], "countdown")

    def test_clip_payout_applies_min_cap_and_fee(self):
        self.assertEqual(page.clip_payout(1500, 1.0, min_payout=2), 0.0)
        self.assertEqual(page.clip_payout(50000, 1.0, min_payout=2), 45.0)
        self.assertEqual(page.clip_payout(5_000_000, 1.0, cap=500), 450.0)

    def test_ten_k_target_math(self):
        need = page.needed_for_target(10000, 1.0, min_payout=2, cap=500, fee=0.10)
        self.assertAlmostEqual(need["paid_views"], 11_111_111, delta=1)
        self.assertEqual(need["views_to_hit_cap"], 500_000)
        self.assertAlmostEqual(need["min_clips_all_capped"], 22.2, places=1)

    def test_export_name(self):
        self.assertEqual(page.export_name("2026-11-22", "Kai Cenat", "Six stars, upside down!"),
                         "2026-11-22_kai-cenat_six-stars-upside-down.mp4")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
    def test_cut_produces_vertical_1080x1920_30fps(self):
        src, out = self.tmp / "src.mp4", self.tmp / "out.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=60:duration=6",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                        "-shortest", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
        cmd = page.cut_command(src, 1, 4, out, facecam=(1500, 50, 400, 300), bleeps=[(1, 1.5)])
        subprocess.run(cmd[:1] + ["-loglevel", "error"] + cmd[1:], check=True)
        probe = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)],
            capture_output=True, text=True, check=True).stdout)
        video = next(s for s in probe["streams"] if s["codec_type"] == "video")
        audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        self.assertEqual((video["width"], video["height"]), (1080, 1920))
        self.assertEqual(video["codec_name"], "h264")
        self.assertEqual(video["r_frame_rate"], "30/1")
        self.assertEqual(audio["codec_name"], "aac")
        self.assertAlmostEqual(float(probe["format"]["duration"]), 3.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
