"""Local studio page. It stays on this computer and collects nothing."""

from __future__ import annotations

from html import escape
from pathlib import Path

from channel.catalog import TOPICS

ABOUT = """Little Lantern

Short, calm learning stories for young children.

Luma the lantern explains one small idea at a time: bees, rain, numbers, kindness, and how everyday things work. The words stay short. The pictures are drawn for this channel. There are no photos of children.

This channel is made for kids. It does not ask children for their names, ages, or where they live.

In YouTube Studio, set the channel itself to made for kids before the first video is public. Each upload from this studio is marked made for kids as well.
"""


def _clock(seconds: float | None) -> str:
    if not seconds:
        return ""
    whole = int(round(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def render_html(queue: dict, config: dict) -> str:
    done = {item["id"]: item for item in queue.get("episodes", [])}
    cards = []
    for topic in TOPICS:
        item = done.get(topic.id)
        if item:
            state = "Scheduled" if not item.get("uploaded") else "Uploaded"
            if item.get("youtube_id"):
                state = f"YouTube {item['youtube_id']}"
            video = escape(item["video"])
            thumb = escape(item["thumbnail"])
            media = (
                f'<video controls preload="metadata" poster="{thumb}" src="{video}"></video>'
            )
            length = _clock(item.get("duration"))
            detail = f"{state} · {length}" if length else state
        else:
            media = '<div class="pending">Not rendered yet</div>'
            detail = "In the catalog"
        cards.append(
            "<article>"
            f"{media}"
            f"<h2>{escape(topic.title)}</h2>"
            f"<p>{escape(topic.summary)}</p>"
            f"<p class='meta'>{escape(detail)}</p>"
            "</article>"
        )
    schedule = config.get("schedule_hour_local")
    if schedule is None:
        when = "New uploads stay private until privacy is changed in config.json."
    else:
        when = (
            f"Episodes are dated in {escape(str(config['timezone']))}. "
            f"YouTube holds each upload as private and publishes it at {int(schedule):02d}:00."
        )
    upload_line = (
        "Upload is on, so the daily job can send the next video."
        if config.get("upload_enabled")
        else "Upload is off until you connect a YouTube channel."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(config["channel_name"])}</title>
<style>
  body {{ margin: 0; font-family: Inter, "DejaVu Sans", sans-serif; background: #f4ecdf; color: #1d2433; }}
  header {{ background: #1d2433; color: #fff8ee; padding: 32px 8vw 28px; }}
  header p {{ max-width: 40rem; color: #f0d2c4; }}
  main {{ padding: 24px 8vw 64px; }}
  .note {{ background: #fff8ee; border: 2px solid #1d2433; border-radius: 16px; padding: 16px 18px; max-width: 46rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 18px; margin-top: 22px; }}
  article {{ background: white; border-radius: 18px; overflow: hidden; border: 2px solid #1d2433; }}
  img, video {{ width: 100%; display: block; background: #d9ecf8; }}
  video {{ margin-top: 0; }}
  article h2, article p {{ margin: 12px 14px; }}
  .meta {{ color: #8a5344; font-weight: 700; }}
  .pending {{ height: 140px; display: grid; place-items: center; background: #d9ecf8; color: #35506a; }}
</style>
</head>
<body>
<header>
  <h1>{escape(config["channel_name"])}</h1>
  <p>{escape(config["tagline"])}</p>
</header>
<main>
  <div class="note">
    <strong>Made for kids.</strong>
    This studio does not ask a child for a name, an age, or a place.
    {when}
    {upload_line}
  </div>
  <section class="grid">
    {''.join(cards)}
  </section>
</main>
</body>
</html>
"""


def write_studio(path: Path, queue: dict, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(queue, config))


def write_about(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ABOUT)
