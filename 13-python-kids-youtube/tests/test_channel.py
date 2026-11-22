"""Policy, schedule, pictures, and a tiny rendered episode."""

from __future__ import annotations

import array
import math
import wave
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from channel import art, assemble, catalog, music, safety, script, store, voice
from channel.config import ConfigError, load_config
from channel.lock import Busy, file_lock
from channel.metadata import description, next_publish_at, video_body
from channel.page import render_html
from channel.pipeline import daily, refresh_studio, render_episode
from channel.upload import CredentialsError, require_ready

ROOT = Path(__file__).resolve().parents[1]


def _cfg(tmp_path: Path, **overrides) -> dict:
    base = {
        "output_dir": str(tmp_path / "out"),
        "width": 320,
        "height": 180,
        "fps": 4,
        "preset": "ultrafast",
        "crf": 32,
        "upload_enabled": False,
        "schedule_hour_local": 7,
        "timezone": "America/Los_Angeles",
    }
    base.update(overrides)
    return load_config(ROOT / "config.json", base)


def _tone(text: str, dest: Path, **_kwargs) -> Path:
    sample_rate = 44100
    count = int(0.28 * sample_rate)
    buffer = array.array("h")
    for index in range(count):
        sample = int(5000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        buffer.append(sample)
        buffer.append(sample)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "w") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(buffer.tobytes())
    return dest


def test_catalog_is_reviewed_and_safe():
    catalog.validate(art.MOTIFS, set(art.THEMES))
    assert len(catalog.TOPICS) >= 21
    ids = [topic.id for topic in catalog.TOPICS]
    assert len(ids) == len(set(ids))
    config = load_config(ROOT / "config.json")
    for topic in catalog.TOPICS:
        episode = script.build(topic)
        body = video_body(topic, config)
        safety.check_episode(
            body["snippet"]["title"],
            body["snippet"]["description"],
            episode.narrations,
            episode.captions,
        )
        assert body["status"]["selfDeclaredMadeForKids"] is True
        assert "http" not in body["snippet"]["description"].lower()
        assert body["snippet"]["categoryId"] == "27"


def test_policy_blocks_personal_questions_and_fear():
    with pytest.raises(safety.PolicyError):
        safety.check_text("What is your name?", "scene")
    with pytest.raises(safety.PolicyError):
        safety.check_text("How old are you today?", "scene")
    with pytest.raises(safety.PolicyError):
        safety.check_text("Look at this scary monster.", "scene")
    with pytest.raises(safety.PolicyError):
        safety.check_text("Visit https://example.com for more.", "scene")
    with pytest.raises(safety.PolicyError):
        safety.check_text("Please subscribe right now.", "scene")


def test_long_sentence_is_rejected():
    words = " ".join(["word"] * 19) + "."
    with pytest.raises(safety.PolicyError):
        safety.check_text(words, "scene")


def test_kids_mode_cannot_be_disabled(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"made_for_kids": false}')
    with pytest.raises(ConfigError):
        load_config(path)


def test_schedule_is_private_and_in_the_future():
    config = load_config(
        ROOT / "config.json",
        {"schedule_hour_local": 7, "privacy": "public", "timezone": "America/Los_Angeles"},
    )
    now = datetime(2026, 11, 21, 18, 0, tzinfo=timezone.utc)  # 10:00 in Los Angeles
    body = video_body(catalog.TOPICS[0], config, now=now)
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["selfDeclaredMadeForKids"] is True
    published = body["status"]["publishAt"]
    assert published == "2026-11-22T15:00:00.000Z"
    later = datetime(2026, 11, 22, 14, 0, tzinfo=timezone.utc)  # 06:00 in Los Angeles
    assert next_publish_at(later, 7, ZoneInfo("America/Los_Angeles")) == "2026-11-22T15:00:00.000Z"


def test_description_has_no_growth_nag():
    text = description(catalog.TOPICS[0], "Little Lantern")
    safety.check_text(text, "description")
    assert "made for kids" in text.lower()


def test_store_picks_the_next_new_story():
    data = store.empty()
    first = store.next_topic(data)
    assert first.id == catalog.TOPICS[0].id
    data = store.upsert(
        data,
        {"id": first.id, "title": first.title, "date": "2026-11-21", "video": "x", "thumbnail": "y"},
    )
    assert store.next_topic(data).id == catalog.TOPICS[1].id
    for topic in catalog.TOPICS:
        data = store.upsert(data, {"id": topic.id, "title": topic.title, "date": "2026-11-21"})
    assert store.next_topic(data) is None


def test_daily_skips_a_day_that_already_has_a_story(tmp_path):
    config = _cfg(tmp_path)
    out = Path(config["output_dir"])
    record = {
        "id": "why-bees-buzz",
        "title": "Why Bees Buzz",
        "date": "2026-11-21",
        "video": "episodes/why-bees-buzz/episode.mp4",
        "thumbnail": "episodes/why-bees-buzz/thumbnail.jpg",
        "uploaded": False,
    }
    store.save(out / "queue.json", store.upsert(store.empty(), record))

    def boom(text, dest, **kwargs):
        raise AssertionError("daily should not render")

    result = daily(config, tmp_path, today="2026-11-21", synthesizer=boom)
    assert result.status == "skipped"
    assert result.topic_id == "why-bees-buzz"


def test_daily_stops_when_the_catalog_is_used(tmp_path):
    config = _cfg(tmp_path)
    data = store.empty()
    for index, topic in enumerate(catalog.TOPICS):
        data = store.upsert(
            data,
            {"id": topic.id, "title": topic.title, "date": f"2026-01-{index + 1:02d}"},
        )
    store.save(Path(config["output_dir"]) / "queue.json", data)
    result = daily(config, tmp_path, today="2026-11-21")
    assert result.status == "exhausted"


def test_lock_blocks_a_second_job_and_clears_a_dead_one(tmp_path):
    path = tmp_path / "daily.lock"
    with file_lock(path):
        with pytest.raises(Busy):
            with file_lock(path):
                pass
    path.write_text("999999")
    with file_lock(path):
        assert path.read_text().strip() != "999999"


def test_frames_have_a_real_picture():
    frame = art.render_frame(
        kind="teach",
        motif="bee",
        theme="garden",
        caption="Fast wings push the air, and our ears hear a buzz.",
        title="Why Bees Buzz",
        size=(640, 360),
        t=0.4,
    )
    assert frame.size == (640, 360)
    dark, bright = frame.convert("L").getextrema()
    assert dark < 50
    assert bright > 220
    for motif in ("phases", "rocket", "whale", "n3", "rainbow", "book", "turtle"):
        image = art.render_frame(
            kind="teach",
            motif=motif,
            theme="garden",
            caption="Hello, little friend.",
            title="Hello",
            size=(320, 180),
            t=0.2,
        )
        dark, bright = image.convert("L").getextrema()
        assert bright - dark > 40


def test_music_is_quiet_and_audible(tmp_path):
    bed = music.render(1.5, "night")
    peak = max(abs(sample) for sample in bed)
    assert 200 < peak < 8000
    voice_path = _tone("hello", tmp_path / "voice.wav")
    duration = assemble.mix_narration(voice_path, tmp_path / "mix.wav", "garden")
    assert duration > 0.5
    # A longer file used to truncate the bed by one sample and crash the mix.
    long_voice = tmp_path / "long.wav"
    sample_rate = 44100
    count = int(2.4 * sample_rate)
    buffer = array.array("h", [0]) * (count * 2)
    with wave.open(str(long_voice), "w") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(buffer.tobytes())
    assert assemble.mix_narration(long_voice, tmp_path / "long-mix.wav", "sea") > 2.4


def test_espeak_writes_a_wav(tmp_path):
    dest = tmp_path / "hello.wav"
    voice.synthesize("Hello, little friend.", dest, engine="espeak")
    assert voice.wav_duration(dest) > 0.4


def test_render_makes_a_playable_episode(tmp_path):
    config = _cfg(tmp_path)
    result = render_episode(
        catalog.by_id("counting-little-stars"),
        config,
        tmp_path,
        day="2026-11-21",
        synthesizer=_tone,
        engine="espeak",
        thumb_size=(320, 180),
    )
    assert result.status == "rendered"
    video = Path(result.path)
    assert video.exists()
    info = assemble.probe(video)
    kinds = {stream["codec_type"] for stream in info["streams"]}
    assert {"video", "audio"} <= kinds
    assert float(info["format"]["duration"]) > 3
    meta = (video.parent / "metadata.json").read_text()
    assert '"selfDeclaredMadeForKids": true' in meta
    html = refresh_studio(config, tmp_path).read_text()
    assert "Counting Little Stars" in html
    assert "Made for kids" in html
    assert 'poster="episodes/counting-little-stars/thumbnail.jpg"' in html
    page = render_html({"episodes": []}, config)
    assert "Not rendered yet" in page


def test_unsafe_episode_is_not_rendered(tmp_path):
    config = _cfg(tmp_path)
    bad = catalog.Topic(
        "bad-episode",
        "A Calm Title",
        "bees",
        "garden",
        "bee",
        "Bees flap fast wings.",
        (("bee", "What is your name?"),),
    )
    with pytest.raises(safety.PolicyError):
        render_episode(bad, config, tmp_path, synthesizer=_tone, engine="espeak")
    assert not (Path(config["output_dir"]) / "episodes" / "bad-episode" / "episode.mp4").exists()


def test_upload_refuses_without_credentials(tmp_path):
    config = _cfg(tmp_path, upload_enabled=False)
    with pytest.raises(CredentialsError):
        require_ready(config, tmp_path)
    config["upload_enabled"] = True
    with pytest.raises(CredentialsError):
        require_ready(config, tmp_path)
