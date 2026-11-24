"""Judge (local AI reviewer), weekly autotune and the one-command setup wizard."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import desk  # noqa: E402
import page  # noqa: E402
from clipper import judge, studio  # noqa: E402
from clipper.wizard import Wizard  # noqa: E402


class FakeOllama:
    def __init__(self, verdicts, models=("qwen2.5vl:3b",)):
        self.verdicts, self.models, self.prompts = list(verdicts), models, []

    def __call__(self, req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/api/tags"):
            body = {"models": [{"name": m} for m in self.models]}
        else:
            sent = json.loads(req.data)
            self.prompts.append(sent)
            body = {"response": json.dumps(self.verdicts.pop(0))}
        return io.BytesIO(json.dumps(body).encode())


def draft(page_dir, mid, transcript="no way chat six stars on me already", **kw):
    d = page_dir / "runs/kai_part1/clips" / mid
    d.mkdir(parents=True)
    (d / "final.mp4").write_bytes(b"\0")
    (d / "sheet.jpg").write_bytes(b"\xff\xd8jpeg")
    meta = {"moment": {"vod_in": "1:00:00", "vod_out": "1:00:30", "score": 80, "transcript": transcript},
            "hook": "Kai vs 6 stars", "hooks": ["Kai vs 6 stars", "\u201cSix stars on me\u201d"],
            "credit": "Kai Cenat (YouTube)", "status": "draft", "duration": 30, "lufs": -14.1, "footage": "ok"}
    meta.update(kw)
    (d / "meta.json").write_text(json.dumps(meta))
    src = page_dir / "runs/kai_part1/source.json"
    if not src.exists():
        src.write_text(json.dumps({"streamer": "Kai Cenat"}))
    return d


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        self.page = page.init_page(self.tmp / "pg", {"name": "Six Stars Desk"})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_grounded_hooks_only(self):
        t = "no way chat six stars on me already"
        self.assertTrue(judge.grounded("Six stars on me", t, [], "Kai Cenat"))
        self.assertTrue(judge.grounded("Kai gets 6 stars", t, [], "Kai Cenat"))
        self.assertFalse(judge.grounded("Kai robs the bank", t, [], "Kai Cenat"))
        self.assertFalse(judge.grounded("one two three four five six seven", t, [], ""))

    def test_review_sends_the_sheet_and_falls_back_on_invented_hooks(self):
        d = draft(self.page, "m01")
        fake = FakeOllama([{"problem": "none", "reason": "clear chase", "hook": "Kai robs a bank"}])
        meta = json.loads((d / "meta.json").read_text())
        got = judge.review(d, meta, opener=fake)
        self.assertEqual(got, {"ok": True, "reason": "none: clear chase", "hook": "Kai vs 6 stars"})
        sent = fake.prompts[0]
        self.assertEqual(sent["format"]["properties"]["problem"]["enum"], ["none", "loading", "spoiler"])
        self.assertEqual(len(sent["images"]), 1)
        self.assertIn("six stars on me", sent["prompt"])

    def test_auto_approve_with_judge_rejects_and_rewrites_hooks(self):
        draft(self.page, "m01")
        draft(self.page, "m02")
        fake = FakeOllama([{"problem": "none", "reason": "good", "hook": "\u201cSix stars on me\u201d"},
                           {"problem": "spoiler", "reason": "credits roll"}])
        finalized = []
        import clipper.pipeline as pipeline
        orig = pipeline.finalize
        pipeline.finalize = lambda clip_dir, hook=None, credit=None: finalized.append((Path(clip_dir).name, hook))
        try:
            cfg = desk.publish.load_desk(self.page)
            got = desk.auto_approve(self.page, cfg, date(2026, 11, 22), judge_opener=fake)
        finally:
            pipeline.finalize = orig
        self.assertEqual(got, ["kai_part1/m01"])
        self.assertEqual(finalized, [("m01", "\u201cSix stars on me\u201d")])
        m2 = json.loads((self.page / "runs/kai_part1/clips/m02/meta.json").read_text())
        self.assertEqual((m2["judged"], m2["judge_reason"]), ("rejected", "spoiler: credits roll"))
        self.assertEqual(desk.auto_approve(self.page, cfg, date(2026, 11, 23), judge_opener=fake), [])

    def test_required_judge_blocks_auto_approve_when_missing(self):
        draft(self.page, "m01")
        cfg = desk.publish.load_desk(self.page)
        cfg["judge"] = {"enabled": True, "model": "qwen2.5vl:3b"}
        self.assertEqual(desk.auto_approve(self.page, cfg, date(2026, 11, 22),
                                           judge_opener=FakeOllama([], models=())), [])
        cfg["judge"]["enabled"] = "auto"
        self.assertEqual(desk.auto_approve(self.page, cfg, date(2026, 11, 22),
                                           judge_opener=FakeOllama([], models=())), ["kai_part1/m01"])


class FootageTest(unittest.TestCase):
    def test_black_and_frozen_are_caught_by_ffmpeg(self):
        import subprocess
        from clipper.media import footage_problem
        tmp = Path(tempfile.mkdtemp())
        try:
            def make(name, src):
                out = tmp / f"{name}.mp4"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src, "-t", "8",
                                "-pix_fmt", "yuv420p", str(out)], check=True)
                return out
            self.assertEqual(footage_problem(make("black", "color=c=black:s=640x360:r=30")), "black")
            self.assertEqual(footage_problem(make("still", "color=c=0x3366aa:s=640x360:r=30")), "frozen")
            self.assertIsNone(footage_problem(make("moving", "testsrc2=s=640x360:r=30")))
        finally:
            shutil.rmtree(tmp)


class AutotuneTest(unittest.TestCase):
    def test_more_clips_for_streamers_that_beat_the_median(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            pg = page.init_page(tmp / "pg", {"name": "x"})
            for i in range(4):
                for streamer, views in (("Kai Cenat", 90000), ("IShowSpeed", 20000), ("Other", 50000)):
                    pid = page.log_post(pg, {"date": f"2026-11-1{6 + i}T12:00", "platform": "tiktok",
                                             "format": "single", "streamer": streamer})
                    page.set_numbers(pg, pid, "24h", views)
            cfg = desk.publish.load_desk(pg)
            cfg["watch"].append({"streamer": "Other", "url": "u"})
            changes = desk.autotune(pg, cfg, page.read_board(pg), date(2026, 11, 22))
            self.assertEqual(changes, ["Kai Cenat 4\u21925 clips per VOD", "IShowSpeed 4\u21923 clips per VOD"])
            saved = json.loads((pg / "desk.json").read_text())
            self.assertEqual([w.get("clips_per_vod") for w in saved["watch"]], [5, 3, None])
        finally:
            shutil.rmtree(tmp)


class WizardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        self.cmds, self.logins, self.notified = [], [], []

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def fake_run(self, cmd, **kw):
        self.cmds.append((cmd, kw))
        return SimpleNamespace(returncode=0, stdout="0 3 * * * backup.sh\n*/15 * * * * old desk.py tick x\n")

    def wizard(self, system, answers=None, yes=False):
        answers = iter(answers or [])
        return Wizard(self.tmp / "pg", yes=yes, ask=lambda q: next(answers, ""), run=self.fake_run, system=system,
                      login=self.logins.append, home=self.tmp / "home", notify=self.notified.append,
                      judge_available=lambda model: False)

    def test_mac_with_all_defaults_needs_no_typing(self):
        desk_cfg = self.wizard("Darwin", yes=True).go()
        self.assertEqual(desk_cfg["publish"]["routes"],
                         {"youtube": "browser", "instagram": "browser", "tiktok": "browser", "x": "browser"})
        self.assertTrue(desk_cfg["notify"]["ntfy_topic"].startswith("gta6desk-"))
        self.assertEqual(self.notified, [desk_cfg["notify"]["ntfy_topic"]])
        self.assertEqual(sorted(self.logins), ["instagram", "tiktok", "x", "youtube"])
        plist = self.tmp / "home/Library/LaunchAgents/com.gta6desk.tick.plist"
        self.assertIn("<key>RunAtLoad</key>", plist.read_text())
        ran = [c[0] for c in self.cmds]
        self.assertIn(["launchctl", "load", "-w", str(plist)], ran)
        self.assertTrue(any(c[-1:] == ["chromium"] for c in ran))
        saved = json.loads((self.tmp / "pg/desk.json").read_text())
        self.assertEqual(saved["notify"]["ntfy_topic"], desk_cfg["notify"]["ntfy_topic"])

    def test_linux_replaces_its_own_cron_line_and_keeps_others(self):
        self.wizard("Linux", answers=["My Page", "https://www.twitch.tv/zackrawrr/videos", "2", "", "", "n"]).go()
        cron = next(kw for cmd, kw in self.cmds if cmd == ["crontab", "-"])["input"]
        self.assertIn("0 3 * * * backup.sh", cron)
        self.assertEqual(cron.count("desk.py tick"), 1)
        self.assertIn("PATH=", cron)
        saved = json.loads((self.tmp / "pg/desk.json").read_text())
        self.assertEqual(saved["publish"]["routes"]["youtube"], "api")
        self.assertEqual(saved["watch"][-1], {"streamer": "zackrawrr", "url": "https://www.twitch.tv/zackrawrr/videos"})
        self.assertEqual(sorted(self.logins), ["tiktok", "x"])


if __name__ == "__main__":
    unittest.main()
