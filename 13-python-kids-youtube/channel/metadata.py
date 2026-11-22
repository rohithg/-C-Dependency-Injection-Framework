"""YouTube title, description, and made-for-kids status."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from channel.catalog import Topic


def description(topic: Topic, channel_name: str) -> str:
    return (
        f"{topic.summary}\n\n"
        f"{channel_name} is a series of short learning stories for young children. "
        "Luma the lantern explains one idea, slowly and calmly.\n\n"
        "This video is made for kids. A grown-up is welcome to watch too.\n\n"
        "The words are simple, for young children. The pictures and music are original."
    )


def tags_for(topic: Topic) -> list[str]:
    words = [part for part in topic.title.lower().split() if len(part) > 2]
    tags = [
        "Little Lantern",
        "kids learning",
        "preschool",
        "educational videos for kids",
        "made for kids",
        "stories for children",
        topic.title,
        *words,
    ]
    kept: list[str] = []
    seen: set[str] = set()
    total = 0
    for tag in tags:
        key = tag.casefold()
        if key in seen:
            continue
        extra = len(tag) + (1 if kept else 0)
        if total + extra > 480:
            break
        kept.append(tag)
        seen.add(key)
        total += extra
    return kept


def next_publish_at(now: datetime, hour: int, tz: ZoneInfo) -> str:
    if not 0 <= int(hour) <= 23:
        raise ValueError("schedule hour must be 0-23")
    local = now.astimezone(tz)
    candidate = local.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if candidate <= local + timedelta(minutes=10):
        candidate += timedelta(days=1)
    utc = candidate.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def video_body(topic: Topic, config: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    title = f"{topic.title} | {config['channel_name']}"
    if len(title) > 100:
        title = title[:97] + "..."
    status: dict = {
        "privacyStatus": config["privacy"],
        "selfDeclaredMadeForKids": True,
        "embeddable": True,
    }
    if config.get("schedule_hour_local") is not None:
        status["privacyStatus"] = "private"
        status["publishAt"] = next_publish_at(
            now, int(config["schedule_hour_local"]), ZoneInfo(config["timezone"])
        )
    return {
        "snippet": {
            "title": title,
            "description": description(topic, config["channel_name"]),
            "tags": tags_for(topic),
            "categoryId": "27",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }
