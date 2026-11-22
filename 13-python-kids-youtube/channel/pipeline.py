"""Render the next story, remember it, and optionally send it to YouTube."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from channel import art, assemble, catalog, page, safety, script, store, upload, voice
from channel.catalog import Topic
from channel.lock import Busy, file_lock
from channel.metadata import video_body
from channel.script import EpisodeScript


@dataclass
class Result:
    status: str
    topic_id: str | None = None
    path: str | None = None
    message: str = ""


def channel_today(timezone_name: str, now: datetime | None = None) -> str:
    zone = ZoneInfo(timezone_name)
    moment = now.astimezone(zone) if now else datetime.now(zone)
    return moment.date().isoformat()


def output_dir(config: dict, root: Path) -> Path:
    path = Path(config["output_dir"])
    if not path.is_absolute():
        path = root / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def queue_path(config: dict, root: Path) -> Path:
    return output_dir(config, root) / "queue.json"


def render_episode(
    topic: Topic,
    config: dict,
    root: Path,
    *,
    day: str | None = None,
    force: bool = False,
    synthesizer=None,
    engine: str | None = None,
    thumb_size: tuple[int, int] | None = None,
) -> Result:
    out = output_dir(config, root)
    data = store.load(queue_path(config, root))
    final = out / "episodes" / topic.id
    video_path = final / "episode.mp4"
    previous = next((item for item in data["episodes"] if item["id"] == topic.id), None)
    if video_path.exists() and not force:
        return Result("skipped", topic.id, str(video_path), f"Already rendered {topic.title}")

    episode = script.build(topic)
    body = video_body(topic, config)
    safety.check_episode(
        body["snippet"]["title"],
        body["snippet"]["description"],
        episode.narrations,
        episode.captions,
    )
    catalog.validate(art.MOTIFS, set(art.THEMES))

    chosen = engine or config["engine"]
    fallback = False
    if synthesizer is None:
        chosen, fallback = voice.resolve_engine(
            chosen, config["voice"], config["voice_rate"], out / "cache" / "voice"
        )

        def synthesizer(text: str, dest: Path) -> Path:
            produced = voice.cached(
                text,
                out / "cache" / "voice",
                engine=chosen,
                voice=config["voice"],
                rate=config["voice_rate"],
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            if Path(produced).resolve() != Path(dest).resolve():
                shutil.copy2(produced, dest)
            return dest

        if fallback:
            print("Edge voice is unavailable. This episode uses the offline espeak voice.")

    work = out / ".work" / topic.id
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    size = (config["width"], config["height"])
    scene_files: list[Path] = []
    poster: Path | None = None
    try:
        for index, scene in enumerate(episode.scenes):
            print(f"  scene {index + 1}/{len(episode.scenes)}: {scene.narration}")
            narration = work / f"{index:02d}.wav"
            mixed = work / f"{index:02d}-mix.wav"
            clip = work / f"{index:02d}.mp4"
            produced = Path(synthesizer(scene.narration, narration))
            duration = assemble.mix_narration(produced, mixed, scene.theme)
            frames = _frames(scene, episode, size, config["fps"], duration, index, work)
            assemble.encode_scene(
                frames, mixed, clip, size, config["fps"], config["preset"], config["crf"]
            )
            scene_files.append(clip)
            if index == 1:
                poster = work / "poster.jpg"
        episode_file = work / "episode.mp4"
        assemble.concat_scenes(scene_files, episode_file)
        info = assemble.probe(episode_file)
        duration = float(info["format"]["duration"])
        stage = out / ".ready" / topic.id
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        thumb = stage / "thumbnail.jpg"
        art.save_image(
            art.render_frame(
                kind="thumb",
                motif=topic.motif,
                theme=topic.theme,
                caption=topic.title,
                title=topic.title,
                size=thumb_size or (1280, 720),
                t=0.6,
            ),
            thumb,
        )
        shutil.copy2(episode_file, stage / "episode.mp4")
        if poster and poster.exists():
            shutil.copy2(poster, stage / "poster.jpg")
        meta = {
            "topic_id": topic.id,
            "title": topic.title,
            "channel": config["channel_name"],
            "made_for_kids": True,
            "voice_engine": chosen,
            "voice_fallback": fallback,
            "duration": round(duration, 2),
            "youtube": body,
        }
        (stage / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
        (stage / "script.json").write_text(
            json.dumps(
                {
                    "title": episode.title,
                    "scenes": [
                        {"kind": scene.kind, "motif": scene.motif, "narration": scene.narration}
                        for scene in episode.scenes
                    ],
                },
                indent=2,
            )
            + "\n"
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            shutil.rmtree(final)
        stage.rename(final)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        ready = out / ".ready" / topic.id
        if ready.exists():
            shutil.rmtree(ready, ignore_errors=True)

    record = {
        "id": topic.id,
        "title": topic.title,
        "date": day or channel_today(config["timezone"]),
        "video": f"episodes/{topic.id}/episode.mp4",
        "thumbnail": f"episodes/{topic.id}/thumbnail.jpg",
        "metadata": f"episodes/{topic.id}/metadata.json",
        "duration": round(duration, 2),
        "voice_engine": chosen,
        "voice_fallback": fallback,
        "uploaded": False,
        "youtube_id": None,
    }
    if previous and previous.get("youtube_id"):
        record["youtube_id"] = previous["youtube_id"]
        record["uploaded"] = bool(previous.get("uploaded"))
    data = store.upsert(store.load(queue_path(config, root)), record)
    store.save(queue_path(config, root), data)
    page.write_studio(out / "studio.html", data, config)
    return Result("rendered", topic.id, str(final / "episode.mp4"), f"Rendered {topic.title}")


def _frames(scene, episode: EpisodeScript, size, fps, duration, index, work: Path):
    count = max(2, int(duration * fps))
    width, height = size
    expected = width * height * 3
    for frame_index in range(count):
        image = art.render_frame(
            kind=scene.kind,
            motif=scene.motif,
            theme=scene.theme,
            caption=scene.caption,
            title=episode.title,
            size=size,
            t=frame_index / fps,
        )
        if index == 1 and frame_index == 0:
            art.save_image(image, work / "poster.jpg")
        raw = image.tobytes()
        if len(raw) != expected:
            raise RuntimeError("frame byte count does not match the video size")
        yield raw


def render_next(config: dict, root: Path, **kwargs) -> Result:
    data = store.load(queue_path(config, root))
    topic = store.next_topic(data)
    if topic is None:
        return Result("exhausted", message="Every story in the catalog has been rendered. Add a new topic.")
    return render_episode(topic, config, root, **kwargs)


def render_batch(config: dict, root: Path, count: int, **kwargs) -> list[Result]:
    results = []
    for _ in range(count):
        result = render_next(config, root, **kwargs)
        results.append(result)
        if result.status != "rendered":
            break
    return results


def daily(config: dict, root: Path, *, today: str | None = None, force: bool = False, **kwargs) -> Result:
    out = output_dir(config, root)
    try:
        with file_lock(out / ".daily.lock"):
            return _daily(config, root, today=today, force=force, **kwargs)
    except Busy as exc:
        return Result("busy", message=str(exc))


def _daily(config, root, *, today, force, **kwargs) -> Result:
    day = today or channel_today(config["timezone"])
    data = store.load(queue_path(config, root))
    existing = store.for_date(data, day)
    if existing and not force:
        return Result(
            "skipped",
            existing["id"],
            str(output_dir(config, root) / existing["video"]),
            f"Already rendered {existing['title']} for {day}",
        )
    result = render_next(config, root, day=day, force=force, **kwargs)
    if result.status == "rendered" and config.get("upload_enabled"):
        uploaded = upload_pending(config, root, only_id=result.topic_id)
        if uploaded:
            result = uploaded[0]
    return result


def upload_pending(config: dict, root: Path, only_id: str | None = None) -> list[Result]:
    upload.require_ready(config, root)
    out = output_dir(config, root)
    data = store.load(queue_path(config, root))
    results = []
    changed = False
    for record in data["episodes"]:
        if only_id and record["id"] != only_id:
            continue
        if record.get("uploaded"):
            continue
        topic = catalog.by_id(record["id"])
        episode_dir = out / "episodes" / topic.id
        body = json.loads((episode_dir / "metadata.json").read_text())["youtube"]
        if body["status"].get("selfDeclaredMadeForKids") is not True:
            raise safety.PolicyError("Refusing to upload a video that is not made for kids.")
        video_id = upload.upload_files(
            episode_dir / "episode.mp4",
            episode_dir / "thumbnail.jpg",
            body,
            config,
            root,
        )
        record["uploaded"] = True
        record["youtube_id"] = video_id
        changed = True
        results.append(Result("uploaded", topic.id, video_id, f"Uploaded {topic.title} as {video_id}"))
        print(results[-1].message)
    if changed:
        store.save(queue_path(config, root), data)
        page.write_studio(out / "studio.html", data, config)
    return results


def write_brand(config: dict, root: Path) -> Path:
    out = output_dir(config, root) / "brand"
    art.save_image(art.render_avatar(), out / "avatar.png")
    art.save_image(art.render_banner(config["tagline"]), out / "banner.png")
    page.write_about(out / "about.txt")
    return out


def refresh_studio(config: dict, root: Path) -> Path:
    out = output_dir(config, root)
    page.write_studio(out / "studio.html", store.load(queue_path(config, root)), config)
    return out / "studio.html"
