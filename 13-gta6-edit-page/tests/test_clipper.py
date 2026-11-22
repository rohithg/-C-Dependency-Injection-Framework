import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"  # never reach a real local model in tests
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import page  # noqa: E402
from clipper import captions, chat, framing, hooks, moments, pipeline, words  # noqa: E402


def W(word, start, end=None):
    return {"word": word, "start": start, "end": end if end is not None else start + 0.3}


class UnitTest(unittest.TestCase):
    def test_profanity_is_masked_and_bleeped_slurs_skip(self):
        ws = [W("what", 1.0), W("the", 1.3), W("fuck", 1.6), W("bro", 2.0)]
        self.assertEqual(words.mask("fuck"), "f***")
        self.assertEqual(words.mask("bro"), "bro")
        self.assertEqual(words.bleep_spans(ws), [(1.55, 1.95)])
        self.assertFalse(words.has_slur(ws))
        self.assertTrue(words.has_slur(ws + [W("retard", 3.0)]))

    def test_hype_score_counts_phrases_near_the_peak(self):
        ws = [W(w, 10 + i * 0.3) for i, w in enumerate("no way bro six stars chat".split())]
        self.assertGreaterEqual(words.hype_score(ws, center=11), 3 + 1 + 4 + 1)
        self.assertEqual(words.hype_score(ws, center=60), 0)

    def test_loud_peaks_find_the_spike_over_the_baseline(self):
        levels = np.full(400, -30.0, dtype=np.float32)
        levels[110:116] = -8
        levels[300:303] = -12
        peaks = moments.loud_peaks(levels)
        self.assertEqual(len(peaks), 2)
        self.assertAlmostEqual(peaks[0][0], 56.5, delta=1.5)
        self.assertGreater(peaks[0][1], peaks[1][1])

    def test_snap_window_starts_on_a_sentence_and_clamps_length(self):
        ws = ([W("setup", 40.0 + i * 0.4) for i in range(5)] +
              [W("payoff", 48.0 + i * 0.4) for i in range(8)] + [W("after", 70.0)])
        start, end = moments.snap_window(ws, peak=55)
        self.assertEqual(start, 48.0)
        self.assertGreaterEqual(end - start, 20)
        self.assertLessEqual(end - start, 60)

    def test_timestamps_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("10:12:05 First Failed Mission Upside Down Landing\nnot a stamp\n1:02 gator\n")
        self.assertEqual(moments.read_timestamps(f.name),
                         [(36725.0, "First Failed Mission Upside Down Landing"), (62.0, "gator")])

    def test_captions_stay_inside_the_safe_zone(self):
        ws = [W(w, i * 0.4) for i, w in enumerate("no way bro six stars what the fuck".split())]
        ass = captions.build_ass(ws, 5.0, hook="Kai hits six stars", credit="Kai Cenat (YouTube)",
                                 caption_y=50)
        self.assertIn("f***", ass)
        self.assertNotIn("fuck", ass)
        self.assertEqual(ass.count("Style: Cap"), 1)
        self.assertEqual(sum(1 for l in ass.splitlines() if ",Cap," in l), 8)
        ys = [int(y) for y in __import__("re").findall(r"\\pos\(540,(\d+)\)", ass)]
        self.assertTrue(all(192 <= y <= 1728 for y in ys), ys)

    def test_chat_spikes_lead_the_burst(self):
        msgs = [(t, "hi") for t in range(0, 900, 5)]
        msgs += [(400 + i * 0.1, "OMEGALUL") for i in range(80)]
        found = chat.spikes(msgs)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0][0], 392, delta=10)

    def test_one_spammer_is_not_a_chat_spike(self):
        msgs = [(t, "hi", f"u{t % 7}") for t in range(0, 900, 5)]
        spam = [(400 + i * 0.1, "OMEGALUL", "spammer") for i in range(80)]
        crowd = [(600 + i * 0.1, "OMEGALUL", f"c{i}") for i in range(80)]
        self.assertEqual(chat.spikes(msgs + spam), [])
        self.assertAlmostEqual(chat.spikes(msgs + crowd)[0][0], 592, delta=10)

    def test_replay_peaks_take_the_tops_of_most_replayed(self):
        heat = [[i * 10.0, i * 10.0 + 10, 0.2] for i in range(100)]
        heat[0][2] = heat[99][2] = 1.0
        heat[30][2], heat[31][2], heat[70][2] = 1.0, 0.9, 0.6
        self.assertEqual(moments.replay_peaks(heat), [(305.0, 1.0), (705.0, 0.6)])
        self.assertEqual(moments.replay_peaks([]), [])

    def test_off_moment_phrases(self):
        said = [W(w, i * 0.3) for i, w in enumerate("yo thank you for the five gifted bro".split())]
        self.assertEqual(words.off_moment(said, 1.0), ["thank you for the", "gifted"])
        hype = [W(w, i * 0.3) for i, w in enumerate("no way six stars on me".split())]
        self.assertEqual(words.off_moment(hype, 1.0), [])

    def test_cuts_never_land_mid_word(self):
        ws = [{"word": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.45} for i in range(200)]
        start, end = moments.snap_window(ws, 50.2)
        for t in (start, end):
            self.assertIsNone(moments._inside_word(ws, t), t)
        self.assertLessEqual(end - start, 60)

    def test_layout_choice(self):
        steady_small = [(i * 0.25, (1600, 60, 100, 100)) for i in range(40)]
        moving_big = [(i * 0.25, (100 + i * 20, 300, 260, 260)) for i in range(40)]
        nothing = [(i * 0.25, None) for i in range(40)]
        self.assertEqual(framing.choose_layout(steady_small, 1920, 1080)[0], "stack")
        self.assertEqual(framing.choose_layout(moving_big, 1920, 1080)[0], "track")
        self.assertEqual(framing.choose_layout(nothing, 1920, 1080), ("fit", None))

    def test_refine_cam_snaps_to_the_still_box(self):
        motion = np.full((360, 640), 40.0, dtype=np.float32)
        motion[20:120, 480:620] = 2.0
        face = (1620, 120, 120, 120)
        cam = framing.refine_cam((1500, 0, 400, 300), face, motion, scale=640 / 1920)
        self.assertEqual(cam, (1440, 60, 420, 300))

    def test_audio_chain_with_bleeps_is_one_graph(self):
        chain = pipeline.audio_chain([(1.0, 1.4)], 10.0)
        self.assertIn("afftdn", chain)
        self.assertIn("sine=frequency=1000", chain)
        self.assertTrue(chain.endswith("duration=first"))

    def test_hooks_name_what_was_heard_and_fit_six_words(self):
        ws = [W(w, 50 + i * 0.3) for i, w in enumerate("no way bro six stars six stars chat".split())]
        got = hooks.suggest(ws, 51, "Kai Cenat (YouTube)")
        self.assertEqual(got[0], "Kai vs 6 stars")
        self.assertTrue(all(len(h.split()) <= 6 for h in got))
        self.assertTrue(any(h.startswith("\u201c") for h in got))
        self.assertEqual(hooks.suggest([W("busted", 1)], 1, "IShowSpeed")[0], "Speed gets busted in GTA 6")
        self.assertEqual(hooks.suggest(ws, 51, "Kai", label="First Failed Mission")[0],
                         "First Failed Mission")
        quiet = hooks.suggest([W("hello", 1)], 1, "Kai Cenat")
        self.assertIn("Kai was not ready for this", quiet)

    def test_dead_air_skips_quiet_gaps_but_not_the_peak_or_loud_action(self):
        hop = 0.1
        levels = np.full(300, -60.0)
        ws = [W("a", 1.0, 2.0), W("b", 6.0, 7.0), W("c", 12.0, 13.0), W("d", 20.0, 21.0)]
        for w in ws:
            levels[int(w["start"] / hop): int(w["end"] / hop)] = -20.0
        levels[140:170] = -15.0  # explosion, nobody talking
        cuts = pipeline.dead_air(ws, 30.0, levels, hop, peak=19.5)
        self.assertIn((2.15, 5.85), cuts)
        self.assertFalse(any(a < 17 and b > 12.5 for a, b in cuts if a > 7))
        self.assertFalse(any(a < 22.5 and b > 17.5 for a, b in cuts))
        self.assertAlmostEqual(pipeline.remap(6.0, [(2.15, 5.85)]), 2.3)
        self.assertAlmostEqual(pipeline.remap(3.0, [(2.15, 5.85)]), 2.15)

    def test_caption_pop_on_active_word(self):
        ass = captions.build_ass([W("six", 0), W("stars", 0.4)], 2.0)
        self.assertEqual(ass.count("\\fscx118"), 2)


def _have(*tools):
    return all(shutil.which(t) for t in tools)


@unittest.skipUnless(_have("ffmpeg", "ffprobe", "espeak-ng"), "needs ffmpeg and espeak-ng")
def studio_clips(pg):
    from clipper import studio
    return studio.clips(pg)


class EndToEndTest(unittest.TestCase):
    """A 70 s synthetic stream: quiet talk, then a loud 'six stars' reaction with a swear at 55 s."""

    @classmethod
    def setUpClass(cls):
        import fixtures

        cls.tmp = Path(tempfile.mkdtemp())
        face = cls.tmp / "face.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=0xd9a27e:s=720x900", "-frames:v", "1", str(face)], check=True)
        face_src = Path("/tmp/fx/face.jpg")
        cls.has_real_face = face_src.exists()
        cls.vod = fixtures.make_vod(cls.tmp / "kai_part1.mp4", face_src if cls.has_real_face else face,
                                    duration=70)
        cls.page = page.init_page(cls.tmp / "pg", {"name": "Six Stars Desk"})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_desk_tick_watch_folder_to_posted_for_free(self):
        import desk
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from test_free import FakePoster

        os.environ["CLIPPER_CONFIG"] = str(self.tmp / "config")
        pg = page.init_page(self.tmp / "desk_pg", {"name": "Six Stars Desk"})
        rec = self.tmp / "recordings"
        rec.mkdir()
        os.symlink(self.vod, rec / "kai_part1.mp4")
        os.utime(self.vod, (time.time() - 600, time.time() - 600))
        cfg = json.loads((pg / "desk.json").read_text())
        cfg.update(watch=[{"streamer": "Kai Cenat", "platform": "YouTube", "url": str(rec)}],
                   clips_per_vod=2, model="tiny.en", jobs=2, countdown={"enabled": False},
                   auto_approve={"enabled": True, "min_score": 0}, platforms=["tiktok", "youtube"])
        (pg / "desk.json").write_text(json.dumps(cfg))
        fakes, sent = {p: FakePoster(p) for p in ("tiktok", "youtube")}, []
        kw = dict(get_poster=fakes.__getitem__, counts=lambda url: {"views": 1},
                  sender=lambda d, title, msg: sent.append(msg))
        tz = ZoneInfo("America/Los_Angeles")
        report = desk.tick(pg, now=datetime(2026, 11, 22, 9, 0, tzinfo=tz), **kw)

        self.assertEqual(len(report["drafts"]), 2)
        self.assertEqual(len(report["approved"]), 2)
        self.assertEqual(sorted(d["when"][11:16] for d in report["scheduled"]),
                         ["12:00", "12:20", "17:00", "17:20"])
        self.assertEqual(report["posted"], [])
        src = json.loads((pg / "runs/kai_part1/source.json").read_text())
        self.assertTrue(src["video"])
        self.assertIn("2 new drafts", sent[0])
        self.assertIn("2 auto-approved", sent[0])

        later = desk.tick(pg, now=datetime(2026, 11, 22, 18, 0, tzinfo=tz), lister=lambda url: [], **kw)
        self.assertEqual(len(later["posted"]), 4)
        self.assertEqual(len(fakes["tiktok"].posted), 2)
        self.assertEqual(sum(1 for r in page.read_board(pg) if r["post_url"]), 4)
        self.assertEqual({c["status"] for c in studio_clips(pg)}, {"scheduled"})

    def test_auto_then_studio(self):
        import clip
        from clipper import studio

        clip.main(["auto", str(self.page), str(self.vod), "--credit", "Kai Cenat (YouTube)",
                   "--top", "2", "--model", "tiny.en"])
        found = json.loads((self.page / "runs/kai_part1/moments.json").read_text())
        top = found[0]
        self.assertLessEqual(top["start"], 55)
        self.assertGreaterEqual(top["end"], 57)
        self.assertNotIn("fuck", top["transcript"])

        clip_dir = self.page / "runs/kai_part1/clips/m01"
        meta = json.loads((clip_dir / "meta.json").read_text())
        if self.has_real_face:
            self.assertEqual(meta["layout"], "stack")
            x, y, w, h = meta["cam"]
            self.assertLessEqual(abs(x - 1460) + abs(y - 40) + abs(w - 420) + abs(h - 316), 30)
        info = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(clip_dir / "final.mp4")],
            capture_output=True, text=True, check=True).stdout)["streams"]
        v = next(s for s in info if s["codec_type"] == "video")
        self.assertEqual((v["width"], v["height"], v["r_frame_rate"]), (1080, 1920, "30/1"))
        self.assertTrue((clip_dir / "sheet.jpg").exists())
        self.assertLessEqual(abs(meta["lufs"] - (-14)), 1.0)
        self.assertTrue(meta["hooks"])
        self.assertTrue(all(len(h.split()) <= 6 for h in meta["hooks"]))
        self.assertIn("f***", (clip_dir / "captions.ass").read_text())

        meta = pipeline.finalize(clip_dir, hook="Kai hits six stars")
        self.assertIn("Kai hits six stars", (clip_dir / "captions.ass").read_text())

        approved = studio.approve(self.page, "kai_part1/m01", "six stars")
        self.assertTrue((self.page / "exports" / approved["export"]).exists())
        self.assertIn("Kai Cenat (YouTube)", (self.page / "posts/six-stars.md").read_text())
        prov = list(csv.reader(open(self.page / "provenance.csv")))
        self.assertEqual(len(prov), 2)

        post_id = studio.mark_posted(self.page, "kai_part1/m01", "tiktok", "single",
                                     when="2026-11-22T19:30")
        row = page.read_board(self.page)[0]
        self.assertEqual((row["post_id"], row["platform"], row["hook"]),
                         (post_id, "tiktok", "Kai hits six stars"))

        from clipper import countdown
        cd = countdown.build(self.page, countdown.pick(self.page, 5), slug="top")
        self.assertEqual(len(cd["sources"]), 2)
        self.assertLessEqual(abs(cd["lufs"] - (-14)), 1.0)
        self.assertIn("countdown/top", [c["id"] for c in studio.clips(self.page)])
        approved = studio.approve(self.page, "countdown/top", "top 2")
        self.assertTrue((self.page / "exports" / approved["export"]).exists())
        self.assertEqual(len(list(csv.reader(open(self.page / "provenance.csv")))), 4)


if __name__ == "__main__":
    unittest.main()
