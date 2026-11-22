"""Mix narration with bed music and encode the frames."""

from __future__ import annotations

import array
import json
import subprocess
import wave
from pathlib import Path

from channel.music import SAMPLE_RATE, render as render_bed


def mix_narration(voice_wav: Path, dest: Path, theme: str, head: float = 0.2, tail: float = 0.45) -> float:
    with wave.open(str(voice_wav)) as handle:
        voice = array.array("h")
        voice.frombytes(handle.readframes(handle.getnframes()))
        if handle.getnchannels() != 2 or handle.getframerate() != SAMPLE_RATE:
            raise RuntimeError("narration must be 44100 Hz stereo")
    voice_frames = len(voice) // 2
    head_n = int(head * SAMPLE_RATE)
    tail_n = int(tail * SAMPLE_RATE)
    total = head_n + voice_frames + tail_n
    bed = render_bed(total / SAMPLE_RATE, theme, SAMPLE_RATE)
    if len(bed) < total * 2:
        bed.extend([0] * (total * 2 - len(bed)))
    peak = max((abs(sample) for sample in voice), default=1) or 1
    scale = (0.78 * 32767) / peak
    out = array.array("h", [0]) * (total * 2)
    for index in range(voice_frames * 2):
        out[head_n * 2 + index] = int(max(-32767, min(32767, voice[index] * scale)))
    for index in range(total * 2):
        mixed = out[index] + int(bed[index])
        out[index] = max(-32767, min(32767, mixed))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "w") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(out.tobytes())
    return total / SAMPLE_RATE


def encode_scene(
    frames,
    audio: Path,
    dest: Path,
    size: tuple[int, int],
    fps: int,
    preset: str,
    crf: int,
) -> None:
    width, height = size
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-i",
        str(audio),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame in frames:
            process.stdin.write(frame)
        process.stdin.close()
    except BrokenPipeError:
        process.stdin.close()
    error = process.stderr.read().decode() if process.stderr else ""
    code = process.wait()
    if code != 0:
        raise RuntimeError(error.strip() or f"ffmpeg exited {code}")


def concat_scenes(scenes: list[Path], dest: Path) -> None:
    listing = dest.with_suffix(".concat.txt")
    listing.write_text("".join(f"file '{scene.resolve()}'\n" for scene in scenes))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )
    listing.unlink(missing_ok=True)


def probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_entries",
            "stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
