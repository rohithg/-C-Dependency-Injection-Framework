import re
from functools import lru_cache

PROFANITY = {"fuck", "fucking", "fucked", "fucker", "motherfucker", "shit", "shitty", "bitch",
             "bitches", "ass", "asshole", "damn", "dick", "pussy", "bastard", "hoe", "hoes"}
# Edits containing these are skipped, not bleeped (SETUP_PROMPT section 6, rule 5).
SLURS = {"nigga", "niggas", "nigger", "faggot", "fag", "retard", "retarded", "tranny"}
HYPE = {
    "no way": 3, "oh my god": 3, "bro": 1, "what": 1, "chat": 1, "wanted": 2, "six stars": 4,
    "6 stars": 4, "five stars": 3, "busted": 3, "wasted": 3, "failed": 3, "mission failed": 4,
    "let's go": 3, "lets go": 3, "yo": 1, "run": 1, "helicopter": 2, "plane": 2, "cops": 2,
    "police": 2, "crash": 2, "gator": 3, "alligator": 3, "what the": 2, "help": 1, "why": 1,
}


def norm(word):
    return re.sub(r"[^a-z0-9']", "", word.lower())


def mask(word):
    core = norm(word)
    if core in PROFANITY or core in SLURS:
        return re.sub(r"(?<=\w)\w", "*", word, count=0)
    return word


def bleep_spans(words, pad=0.05):
    return [(round(max(0.0, w["start"] - pad), 2), round(w["end"] + pad, 2))
            for w in words if norm(w["word"]) in PROFANITY]


def has_slur(words):
    return any(norm(w["word"]) in SLURS for w in words)


def hype_score(words, center=None, radius=10.0):
    text = " ".join(norm(w["word"]) for w in words
                    if center is None or abs(w["start"] - center) <= radius)
    return sum(weight * len(re.findall(rf"\b{re.escape(p)}\b", text)) for p, weight in HYPE.items())


@lru_cache(maxsize=2)
def _model(size):
    from faster_whisper import WhisperModel
    return WhisperModel(size, device="auto", compute_type="int8")


def transcribe(path, model="base.en", start=None, duration=None):
    """Word timestamps relative to `start` (or the file start)."""
    import subprocess

    import numpy as np

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    audio = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    if audio.size == 0:
        return []
    segments, _ = _model(model).transcribe(audio, word_timestamps=True, vad_filter=True)
    return [{"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)}
            for seg in segments for w in (seg.words or []) if w.word.strip()]
