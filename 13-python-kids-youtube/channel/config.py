"""Load studio settings. Kids mode cannot be turned off."""

from __future__ import annotations

import json
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULTS: dict = {
    "channel_name": "Little Lantern",
    "tagline": "Calm learning stories for young children",
    "timezone": "America/Los_Angeles",
    "schedule_hour_local": 7,
    "voice": "en-US-JennyNeural",
    "voice_rate": "-12%",
    "engine": "auto",
    "width": 1280,
    "height": 720,
    "fps": 12,
    "privacy": "private",
    "upload_enabled": False,
    "client_secrets": "secrets/client_secret.json",
    "token_path": "secrets/youtube-token.json",
    "playlist": "Little Lantern",
    "output_dir": "output",
    "port": 8766,
    "made_for_kids": True,
    "preset": "veryfast",
    "crf": 20,
}


class ConfigError(ValueError):
    pass


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    data: dict = {}
    if path is not None and Path(path).exists():
        data = json.loads(Path(path).read_text())
    cfg = {**DEFAULTS, **data}
    if overrides:
        cfg.update(overrides)
    if cfg.get("made_for_kids") is False:
        raise ConfigError("Little Lantern only publishes videos made for kids.")
    cfg["made_for_kids"] = True
    if cfg["engine"] not in {"auto", "edge", "espeak"}:
        raise ConfigError("engine must be auto, edge, or espeak")
    if cfg["privacy"] not in {"private", "unlisted", "public"}:
        raise ConfigError("privacy must be private, unlisted, or public")
    try:
        ZoneInfo(cfg["timezone"])
    except Exception as exc:
        raise ConfigError(f"Unknown timezone {cfg['timezone']}") from exc
    hour = cfg["schedule_hour_local"]
    if hour is not None and not (isinstance(hour, int) and 0 <= hour <= 23):
        raise ConfigError("schedule_hour_local must be an hour from 0 to 23, or null")
    if int(cfg["width"]) % 2 or int(cfg["height"]) % 2:
        raise ConfigError("width and height must be even")
    if not 4 <= int(cfg["fps"]) <= 30:
        raise ConfigError("fps must be between 4 and 30")
    cfg["width"] = int(cfg["width"])
    cfg["height"] = int(cfg["height"])
    cfg["fps"] = int(cfg["fps"])
    cfg["crf"] = int(cfg["crf"])
    return cfg
