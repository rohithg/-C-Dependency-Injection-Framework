"""Rank the moments in a VOD.

Pass 1 scans loudness over the whole file (fast, works on 11 h VODs): a streamer yelling over
their own baseline is the strongest cheap signal for a reaction. Pass 2 transcribes only the
best candidates and rescores them on hype phrases ("six stars", "busted", "no way"), drops
anything with a slur and snaps the cut to sentence edges.
"""

import re

import numpy as np

from . import words as W
from .media import loudness_curve, probe

HOP = 0.5


def parse_ts(text):
    seconds = 0.0
    for part in str(text).strip().split(":"):
        seconds = seconds * 60 + float(part)
    return seconds


def fmt_ts(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 3600:d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def read_timestamps(path):
    """Lines like '10:12:05 First Failed Mission Upside Down Landing' (VOD comments, chapters)."""
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–|]?\s*(.*)", line)
        if m:
            out.append((parse_ts(m.group(1)), m.group(2).strip()))
    return out


def loud_peaks(levels, min_gap=30.0, threshold=6.0, baseline_window=120.0):
    """(time, excess_db) for spikes above a rolling-median baseline, at least min_gap apart."""
    if len(levels) == 0:
        return []
    win = max(3, int(baseline_window / HOP) | 1)
    padded = np.pad(levels, win // 2, mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(padded, win)
    step = max(1, win // 8)
    baseline = np.repeat(np.median(view[::step], axis=1), step)[: len(levels)]
    smooth = np.convolve(np.pad(levels, 2, mode="edge"), np.ones(5) / 5, mode="valid")
    excess = smooth - baseline
    order = np.argsort(-excess)
    picked = []
    gap = int(min_gap / HOP)
    taken = np.zeros(len(levels), dtype=bool)
    for i in order:
        if excess[i] < threshold:
            break
        if taken[i]:
            continue
        picked.append((i * HOP, float(excess[i])))
        taken[max(0, i - gap): i + gap] = True
    return picked


def snap_window(words, peak, pre=14.0, post=8.0, min_len=20.0, max_len=60.0):
    """Cut from the sentence that sets the moment up to the end of the reaction."""
    start, end = peak - pre, peak + post
    if words:
        starts = [w["start"] for w in words]
        ends = [w["end"] for w in words]
        gaps_before = [w["start"] for prev, w in zip(words, words[1:])
                       if w["start"] - prev["end"] > 0.6 and peak - pre - 6 <= w["start"] <= peak - 4]
        if gaps_before:
            start = min(gaps_before, key=lambda t: abs(t - (peak - pre)))
        elif starts and starts[0] > start:
            start = max(start, starts[0] - 0.3)
        after = [e for e, nxt in zip(ends, starts[1:] + [1e9]) if e >= peak + post and nxt - e > 0.5]
        if after:
            end = min(after[0] + 0.4, peak + post + 15)
    if end - start < min_len:
        end = start + min_len
    if end - start > max_len:
        start = max(start, end - max_len)
    return max(0.0, start), end


def hook_guess(words, peak, label=""):
    if label:
        return " ".join(label.split()[:6])
    near = [w for w in words if abs(w["start"] - peak) <= 4]
    text = " ".join(W.mask(w["word"]) for w in near[:6]).strip()
    return text[:1].upper() + text[1:] if text else ""


def find_moments(src, top=10, timestamps=(), transcribe=True, model="base.en",
                 candidates=3, threshold=6.0, offset=0.0, chat_spikes=()):
    """Ranked moments. `offset` is where `src` starts in the VOD (a downloaded section)."""
    duration = probe(src)["duration"]
    levels = loudness_curve(src, hop=HOP)
    found = [{"peak": t, "loud_db": round(db, 1), "label": "", "chat_z": 0.0}
             for t, db in loud_peaks(levels, threshold=threshold)[: top * candidates]]
    for t, z in chat_spikes:
        t -= offset
        if not 0 <= t <= duration:
            continue
        near = [f for f in found if abs(f["peak"] - t) <= 20]
        if near:
            near[0]["chat_z"] = max(near[0]["chat_z"], z)
        else:
            found.append({"peak": t, "loud_db": 0.0, "label": "", "chat_z": z})
    for t, label in timestamps:
        t -= offset
        if 0 <= t <= duration:
            found = [f for f in found if abs(f["peak"] - t) > 20]
            found.append({"peak": t + 6, "loud_db": 0.0, "label": label, "chat_z": 0.0})

    moments = []
    for f in found:
        peak = f["peak"]
        lo = max(0.0, peak - 40)
        clip_words = []
        if transcribe:
            clip_words = [dict(w, start=w["start"] + lo, end=w["end"] + lo)
                          for w in W.transcribe(src, model, start=lo, duration=75)]
        reasons = []
        if f["loud_db"]:
            reasons.append(f"+{f['loud_db']} dB over baseline")
        if f["label"]:
            reasons.append(f"timestamp: {f['label']}")
        if f["chat_z"]:
            reasons.append(f"chat spike z={f['chat_z']}")
        hype = W.hype_score(clip_words, center=peak)
        if hype:
            reasons.append(f"hype phrases {hype}")
        start, end = snap_window(clip_words, peak)
        end = min(end, duration)
        inside = [w for w in clip_words if start <= w["start"] < end]
        moments.append({
            "peak": round(peak, 2), "start": round(start, 2), "end": round(end, 2),
            "vod_in": fmt_ts(start + offset), "vod_out": fmt_ts(end + offset),
            "score": round(f["loud_db"] + 2.0 * hype + 4.0 * f["chat_z"] + (25 if f["label"] else 0), 1),
            "reasons": reasons, "hook": hook_guess(clip_words, peak, f["label"]),
            "skip": "slur in transcript" if W.has_slur(inside) else "",
            "transcript": " ".join(W.mask(w["word"]) for w in inside),
        })
    moments.sort(key=lambda m: (bool(m["skip"]), -m["score"]))
    for i, m in enumerate(moments[:top], 1):
        m["id"] = f"m{i:02d}"
    return moments[:top]
