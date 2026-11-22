import json
import shutil
import subprocess

import numpy as np


def require(tool):
    if not shutil.which(tool):
        raise SystemExit(f"{tool} not found on PATH")


def run(cmd, cwd=None):
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if proc.returncode:
        raise RuntimeError(f"{cmd[0]} failed:\n{proc.stderr[-2000:]}")
    return proc.stdout


def ffmpeg(*args, cwd=None):
    return run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *map(str, args)], cwd=cwd)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    num, den = (video or {}).get("r_frame_rate", "30/1").split("/")
    return {
        "duration": float(data["format"]["duration"]),
        "width": video and int(video["width"]),
        "height": video and int(video["height"]),
        "fps": float(num) / float(den or 1),
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
    }


def loudness_curve(path, hop=0.5, rate=8000):
    """dBFS per `hop` seconds over the whole file, streamed so an 11 h VOD fits in memory."""
    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(rate), "-f", "s16le", "-"], stdout=subprocess.PIPE)
    block = int(rate * hop) * 2
    levels = []
    while True:
        chunk = proc.stdout.read(block * 240)
        if not chunk:
            break
        samples = np.frombuffer(chunk[: len(chunk) // 2 * 2], dtype=np.int16).astype(np.float32)
        n = len(samples) // (block // 2)
        if n == 0:
            continue
        frames = samples[: n * (block // 2)].reshape(n, -1) / 32768.0
        rms = np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-9
        levels.extend(20 * np.log10(rms))
    proc.wait()
    return np.array(levels, dtype=np.float32)


def frame_sheet(src, out, start=0.0, duration=None, tiles=6):
    duration = duration or probe(src)["duration"]
    step = max(duration / tiles, 0.1)
    ffmpeg("-ss", start, "-t", duration, "-i", src,
           "-vf", f"fps=1/{step:.3f},scale=360:-2,tile={tiles}x1", "-frames:v", 1, out)
