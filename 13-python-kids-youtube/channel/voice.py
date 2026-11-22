"""Narration. Edge neural voices when they are reachable, espeak-ng otherwise."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import subprocess
import wave
from pathlib import Path


class VoiceError(RuntimeError):
    pass


def espeak_bin() -> str:
    for name in ("espeak-ng", "espeak"):
        found = shutil.which(name)
        if found:
            return found
    raise VoiceError("espeak-ng is not installed")


def synthesize(
    text: str,
    dest: Path,
    engine: str = "espeak",
    voice: str = "en-US-JennyNeural",
    rate: str = "-12%",
) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if engine == "edge":
        raw = dest.with_suffix(".mp3")
        _edge(text, raw, voice, rate)
        _to_wav(raw, dest)
        raw.unlink(missing_ok=True)
        return dest
    if engine == "espeak":
        raw = dest.with_suffix(".espeak.wav")
        subprocess.run(
            [espeak_bin(), "-v", "en-us+f3", "-s", "132", "-g", "6", "-a", "140", "-w", str(raw), text],
            check=True,
            capture_output=True,
        )
        _to_wav(raw, dest)
        raw.unlink(missing_ok=True)
        return dest
    raise VoiceError(f"Unknown voice engine {engine}")


def cached(
    text: str,
    cache_dir: Path,
    engine: str,
    voice: str,
    rate: str,
) -> Path:
    key = hashlib.sha256(f"{engine}|{voice}|{rate}|{text}".encode()).hexdigest()[:24]
    dest = cache_dir / f"{key}.wav"
    if not dest.exists() or dest.stat().st_size < 1000:
        synthesize(text, dest, engine=engine, voice=voice, rate=rate)
    return dest


def resolve_engine(prefer: str, voice: str, rate: str, cache_dir: Path) -> tuple[str, bool]:
    """Pick an engine. auto falls back to espeak for the whole episode."""
    if prefer == "espeak":
        espeak_bin()
        return "espeak", False
    if prefer == "edge":
        cached("Hello.", cache_dir, "edge", voice, rate)
        return "edge", False
    try:
        cached("Hello.", cache_dir, "edge", voice, rate)
        return "edge", False
    except Exception:
        espeak_bin()
        return "espeak", True


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 1
    return frames / rate


def _to_wav(src: Path, dest: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )


def _edge(text: str, dest: Path, voice: str, rate: str) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise VoiceError("edge-tts is not installed") from exc

    async def save() -> None:
        last: Exception | None = None
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text, voice, rate=rate)
                await communicate.save(str(dest))
                if dest.exists() and dest.stat().st_size > 500:
                    return
                last = VoiceError("Edge voice wrote an empty file")
            except Exception as exc:
                last = exc
            await asyncio.sleep(0.8 * (attempt + 1))
        raise VoiceError(f"Edge voice failed: {last}")

    asyncio.run(save())
