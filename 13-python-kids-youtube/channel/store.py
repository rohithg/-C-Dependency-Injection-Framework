"""Local record of rendered episodes. This is the whole database."""

from __future__ import annotations

import json
from pathlib import Path

from channel.catalog import TOPICS, Topic


def empty() -> dict:
    return {"episodes": []}


def load(path: Path) -> dict:
    if not path.exists():
        return empty()
    data = json.loads(path.read_text())
    data.setdefault("episodes", [])
    return data


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def ids(data: dict) -> set[str]:
    return {episode["id"] for episode in data["episodes"]}


def next_topic(data: dict, topics: tuple[Topic, ...] = TOPICS) -> Topic | None:
    done = ids(data)
    for topic in topics:
        if topic.id not in done:
            return topic
    return None


def for_date(data: dict, day: str) -> dict | None:
    for episode in data["episodes"]:
        if episode.get("date") == day:
            return episode
    return None


def upsert(data: dict, record: dict) -> dict:
    episodes = [item for item in data["episodes"] if item["id"] != record["id"]]
    episodes.append(record)
    episodes.sort(key=lambda item: item.get("date") or item["id"])
    return {"episodes": episodes}
