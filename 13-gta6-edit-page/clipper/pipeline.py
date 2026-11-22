import json
import re
import subprocess
from pathlib import Path

import numpy as np

from . import framing
from . import words as W
from .captions import build_ass
from .media import encoder_args, ffmpeg, frame_sheet, loudness_curve, probe

COLD_OPEN = (0.6, 1.4)
CLEAN = "highpass=f=70,afftdn=nf=-25"
TARGET_LUFS = -14.0
PEAK_LIMIT = 0.84  # about -1.5 dBFS


# ---------- audio ----------

def audio_chain(bleeps=(), duration=None):
    """Rumble cut and denoise, profanity replaced by a beep. Loudness is set at mastering."""
    chain = f"{CLEAN},aresample=48000"
    if not bleeps:
        return chain
    on = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in bleeps)
    return (f"{chain},volume=enable='{on}':volume=0[m];"
            f"sine=frequency=1000:sample_rate=48000:duration={duration:.2f},volume=0.12,"
            f"volume=enable='not({on})':volume=0[s];[m][s]amix=inputs=2:normalize=0:duration=first")


def integrated_lufs(path):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
                           "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", proc.stderr)
    return float(found[-1]) if found else None


# ---------- dead air ----------

def dead_air(words, duration, levels, hop, peak=None, min_gap=0.8, keep=0.15, protect=(2.0, 3.0)):
    """Quiet stretches with nobody talking, never around the peak. [(a, b)] to drop."""
    if not words or len(levels) == 0:
        return []
    spoken = np.concatenate([levels[int(w["start"] / hop): int(w["end"] / hop) + 1] for w in words])
    if len(spoken) == 0:
        return []
    quiet = np.median(spoken) - 6.0
    edges = [(0.0, words[0]["start"])]
    edges += [(a["end"], b["start"]) for a, b in zip(words, words[1:])]
    edges.append((words[-1]["end"], duration))
    cuts = []
    for a, b in edges:
        a, b = a + keep, b - keep
        if peak is not None:
            lo, hi = peak - protect[0], peak + protect[1]
            if a < hi and b > lo:
                continue
        if b - a < min_gap - 2 * keep:
            continue
        seg = levels[int(a / hop): max(int(a / hop) + 1, int(b / hop))]
        if len(seg) and np.percentile(seg, 90) < quiet:
            cuts.append((round(a, 2), round(b, 2)))
    return cuts


def remap(t, cuts):
    shift = 0.0
    for a, b in cuts:
        if t >= b:
            shift += b - a
        elif t > a:
            return a - shift
    return t - shift


def tighten(src, out, cuts, duration):
    keep, cur = [], 0.0
    for a, b in cuts:
        if a > cur:
            keep.append((cur, a))
        cur = b
    if cur < duration:
        keep.append((cur, duration))
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)
    ffmpeg("-i", src, "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
           "-af", f"aselect='{expr}',asetpts=N/SR/TB", "-c:v", "libx264", "-preset", "ultrafast",
           "-crf", "14", "-c:a", "aac", "-b:a", "256k", out)


# ---------- mastering ----------

def master(out_dir, inputs, vgraph, agraph, ass_text, name="final.mp4", tries=6):
    """Encode `vgraph` ([v]) + `agraph` ([a]) with subtitles, landing at -14 LUFS.

    Loudness is measured on an audio-only render and corrected (gain, then a peak limiter)
    until it is within 0.5 LU, then the video is encoded once. The limiter eats part of every
    gain step on hot audio, so steps follow the measured slope instead of assuming 1 dB per dB.
    """
    out_dir = Path(out_dir).resolve()
    ins = [x for p in inputs for x in ("-i", str(Path(p).resolve()))]
    wav = out_dir / "master.wav"

    def render_audio(gain):
        ffmpeg(*ins, "-filter_complex",
               f"{agraph};[a]volume={gain:.2f}dB,alimiter=limit={PEAK_LIMIT}:level=false,"
               f"aresample=48000[ao]", "-map", "[ao]", "-c:a", "pcm_s16le", wav)
        return integrated_lufs(wav)

    ffmpeg(*ins, "-filter_complex", agraph, "-map", "[a]", "-c:a", "pcm_s16le", wav)
    measured = integrated_lufs(wav)
    gain = TARGET_LUFS - measured if measured is not None else 0.0
    prev = None
    for _ in range(tries):
        got = render_audio(gain)
        if got is None or abs(got - TARGET_LUFS) <= 0.5:
            break
        slope = 1.0
        if prev and abs(gain - prev[0]) > 0.1:
            slope = min(1.0, max(0.1, (got - prev[1]) / (gain - prev[0])))
        prev = (gain, got)
        gain = min(30.0, gain + max(-12.0, min(12.0, (TARGET_LUFS - got) / slope)))

    (out_dir / "captions.ass").write_text(ass_text, encoding="utf-8")
    ffmpeg(*ins, "-i", wav, "-filter_complex", f"{vgraph};[v]ass=captions.ass[vo]",
           "-map", "[vo]", "-map", f"{len(inputs)}:a", "-r", 30, *encoder_args(final=True),
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", "-shortest", name, cwd=out_dir)
    wav.unlink(missing_ok=True)
    final = out_dir / name
    frame_sheet(final, out_dir / "sheet.jpg")
    ffmpeg("-ss", 0.5, "-i", final, "-frames:v", 1, "-vf", "scale=540:-2", out_dir / "poster.jpg")
    return final, integrated_lufs(final)


# ---------- clips ----------

def render_clip(src, moment, clip_dir, credit="", model="base.en", layout="auto", cam=None,
                cold_open=True, hook=None, jumpcuts=True):
    clip_dir = Path(clip_dir)
    clip_dir.mkdir(parents=True, exist_ok=True)
    raw, base = clip_dir / "raw.mp4", clip_dir / "base.mp4"
    start, end = moment["start"], moment["end"]
    ffmpeg("-ss", start, "-to", end, "-i", src, "-r", 30, "-c:v", "libx264", "-preset",
           "ultrafast", "-crf", "14", "-c:a", "aac", "-b:a", "256k", raw)
    duration = probe(raw)["duration"]

    if moment.get("words") is not None:
        words = [dict(w, start=round(w["start"] - start, 2), end=round(w["end"] - start, 2))
                 for w in moment["words"] if start <= w["start"] < end]
    else:
        words = W.transcribe(raw, model)
    meta = {"moment": {k: v for k, v in moment.items() if k != "words"}, "credit": credit,
            "hook": hook if hook is not None else moment["hook"],
            "hooks": moment.get("hooks", []), "status": "draft", "skip": moment.get("skip", "")}
    if W.has_slur(words):
        meta.update(status="skipped", skip="slur in transcript")
        (clip_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        return meta

    peak = moment["peak"] - start
    cuts = []
    if jumpcuts:
        cuts = dead_air(words, duration, loudness_curve(raw, hop=0.1), 0.1, peak)
    if cuts:
        tight = clip_dir / "tight.mp4"
        tighten(raw, tight, cuts, duration)
        words = [dict(w, start=round(remap(w["start"], cuts), 2), end=round(remap(w["end"], cuts), 2))
                 for w in words]
        peak = remap(peak, cuts)
        raw = tight
        duration = probe(raw)["duration"]
    (clip_dir / "words.json").write_text(json.dumps(words))

    meta.update(framing.render_base(raw, base, layout=layout, cam=cam, peak=peak,
                                    audio_filter=audio_chain(W.bleep_spans(words), duration)))
    meta.update(peak=round(peak, 2), cold_open=cold_open,
                dead_air_cut=round(sum(b - a for a, b in cuts), 2))
    (clip_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return finalize(clip_dir)


def finalize(clip_dir, hook=None, credit=None):
    """(Re)burn captions, hook and credit onto base.mp4. Cheap: run it after editing the hook."""
    clip_dir = Path(clip_dir).resolve()
    meta = json.loads((clip_dir / "meta.json").read_text())
    if meta.get("kind") == "countdown":
        from .countdown import rebuild
        return rebuild(clip_dir, title=hook)
    if hook is not None:
        meta["hook"] = hook
    if credit is not None:
        meta["credit"] = credit
    words = json.loads((clip_dir / "words.json").read_text())
    base = clip_dir / "base.mp4"
    duration = probe(base)["duration"]

    timeline, vgraph, agraph = words, "[0:v]null[v]", "[0:a]anull[a]"
    if meta.get("cold_open") and meta.get("peak") is not None:
        a = max(0.0, meta["peak"] - COLD_OPEN[0])
        b = min(duration, meta["peak"] + COLD_OPEN[1])
        co = b - a
        timeline = ([dict(w, start=w["start"] - a, end=w["end"] - a)
                     for w in words if a <= w["start"] < b] +
                    [dict(w, start=w["start"] + co, end=w["end"] + co) for w in words])
        vgraph = (f"[0:v]split[v1][v2];[v1]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[cv];"
                  f"[v2]setpts=PTS-STARTPTS[mv];[cv][mv]concat=n=2:v=1:a=0[v]")
        agraph = (f"[0:a]asplit[a1][a2];[a1]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[ca];"
                  f"[a2]asetpts=PTS-STARTPTS[ma];[ca][ma]concat=n=2:v=0:a=1[a]")
        duration += co

    ass = build_ass(timeline, duration, hook=meta["hook"], credit=meta["credit"],
                    caption_y=meta.get("seam"))
    final, lufs = master(clip_dir, [base], vgraph, agraph, ass)
    meta.update(final=str(final), duration=round(probe(final)["duration"], 2),
                lufs=round(lufs, 1) if lufs is not None else None)
    (clip_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta
