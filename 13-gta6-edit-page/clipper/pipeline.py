import json
import subprocess
from pathlib import Path

from . import framing
from . import words as W
from .captions import build_ass
from .media import ffmpeg, frame_sheet, probe

COLD_OPEN = (0.6, 1.4)


CLEAN = "highpass=f=70,afftdn=nf=-25"
TARGET = "I=-14:TP=-1.5:LRA=11"


def measure_loudness(src):
    """First loudnorm pass; the second pass uses these numbers to land on -14 LUFS."""
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-vn", "-af",
                           f"{CLEAN},loudnorm={TARGET}:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True)
    blob = proc.stderr[proc.stderr.rfind("{"):proc.stderr.rfind("}") + 1]
    try:
        m = json.loads(blob)
        float(m["input_i"])
    except (ValueError, KeyError):
        return None
    return m


def audio_chain(bleeps=(), duration=None, measured=None):
    """Rumble cut, denoise, -14 LUFS (the short-form norm), profanity replaced by a beep."""
    norm = f"loudnorm={TARGET}"
    if measured:
        norm += (f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
                 f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
                 f":offset={measured['target_offset']}:linear=true")
    chain = f"{CLEAN},{norm},aresample=48000"
    if not bleeps:
        return chain
    on = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in bleeps)
    return (f"{chain},volume=enable='{on}':volume=0[m];"
            f"sine=frequency=1000:sample_rate=48000:duration={duration:.2f},volume=0.12,"
            f"volume=enable='not({on})':volume=0[s];[m][s]amix=inputs=2:normalize=0:duration=first")


def render_clip(src, moment, clip_dir, credit="", model="base.en", layout="auto", cam=None,
                cold_open=True, hook=None):
    clip_dir = Path(clip_dir)
    clip_dir.mkdir(parents=True, exist_ok=True)
    raw, base = clip_dir / "raw.mp4", clip_dir / "base.mp4"
    start, end = moment["start"], moment["end"]
    ffmpeg("-ss", start, "-to", end, "-i", src, "-c:v", "libx264", "-preset", "ultrafast",
           "-crf", "14", "-c:a", "aac", "-b:a", "256k", raw)
    duration = probe(raw)["duration"]

    words = W.transcribe(raw, model)
    (clip_dir / "words.json").write_text(json.dumps(words))
    meta = {"moment": moment, "credit": credit, "hook": hook if hook is not None else moment["hook"],
            "status": "draft", "skip": moment.get("skip", "")}
    if W.has_slur(words):
        meta.update(status="skipped", skip="slur in transcript")
        (clip_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        return meta

    peak = moment["peak"] - start
    meta.update(framing.render_base(
        raw, base, layout=layout, cam=cam, peak=peak,
        audio_filter=audio_chain(W.bleep_spans(words), duration, measure_loudness(raw))))
    meta["peak"] = round(peak, 2)
    meta["cold_open"] = cold_open
    (clip_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return finalize(clip_dir)


def finalize(clip_dir, hook=None, credit=None):
    """(Re)burn captions, hook and credit onto base.mp4. Cheap: run it after editing the hook."""
    clip_dir = Path(clip_dir).resolve()
    meta = json.loads((clip_dir / "meta.json").read_text())
    if hook is not None:
        meta["hook"] = hook
    if credit is not None:
        meta["credit"] = credit
    words = json.loads((clip_dir / "words.json").read_text())
    base = clip_dir / "base.mp4"
    duration = probe(base)["duration"]

    timeline, graph = words, "[0:v]null[v];[0:a]anull[a]"
    if meta.get("cold_open") and meta.get("peak") is not None:
        a = max(0.0, meta["peak"] - COLD_OPEN[0])
        b = min(duration, meta["peak"] + COLD_OPEN[1])
        co = b - a
        timeline = ([dict(w, start=w["start"] - a, end=w["end"] - a)
                     for w in words if a <= w["start"] < b] +
                    [dict(w, start=w["start"] + co, end=w["end"] + co) for w in words])
        graph = (f"[0:v]split[v1][v2];[0:a]asplit[a1][a2];"
                 f"[v1]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[cv];"
                 f"[a1]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[ca];"
                 f"[v2]setpts=PTS-STARTPTS[mv];[a2]asetpts=PTS-STARTPTS[ma];"
                 f"[cv][ca][mv][ma]concat=n=2:v=1:a=1[v][a]")
        duration += co

    seam = meta.get("seam")
    ass = clip_dir / "captions.ass"
    ass.write_text(build_ass(timeline, duration, hook=meta["hook"], credit=meta["credit"],
                             caption_y=seam), encoding="utf-8")
    final = clip_dir / "final.mp4"
    ffmpeg("-i", base, "-filter_complex", f"{graph};[v]ass={ass.name}[vo]",
           "-map", "[vo]", "-map", "[a]", "-r", 30, "-c:v", "libx264", "-preset", "medium",
           "-crf", 18, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", final.name, cwd=clip_dir)
    frame_sheet(final, clip_dir / "sheet.jpg")
    ffmpeg("-ss", 0.5, "-i", final, "-frames:v", 1, "-vf", "scale=540:-2", clip_dir / "poster.jpg")
    meta["final"] = str(final)
    meta["duration"] = round(probe(final)["duration"], 2)
    (clip_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta
