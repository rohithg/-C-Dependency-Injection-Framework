"""Soft original bed music. Nothing here is taken from a recording."""

from __future__ import annotations

import math
import array

SAMPLE_RATE = 44100

_ROOTS = {
    "garden": 261.63,
    "sky": 293.66,
    "night": 220.00,
    "sea": 246.94,
    "space": 196.00,
    "cozy": 261.63,
    "snow": 246.94,
}
_RATIOS = (1.0, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 3 / 2, 5 / 4, 9 / 8)


def render(seconds: float, theme: str = "garden", sample_rate: int = SAMPLE_RATE) -> array.array:
    """Stereo 16-bit bed at a quiet level, faded in and out."""
    root = _ROOTS.get(theme, _ROOTS["garden"])
    total = max(1, math.ceil(seconds * sample_rate))
    step = int(0.48 * sample_rate)
    fade = int(0.28 * sample_rate)
    out = array.array("h", [0]) * (total * 2)
    for i in range(total):
        t = i / sample_rate
        note = int(i / step) % len(_RATIOS)
        local = (i % step) / step
        freq = root * _RATIOS[note]
        hump = math.sin(math.pi * local)
        pad = math.sin(2 * math.pi * (root * 0.5) * t)
        arp = math.sin(2 * math.pi * freq * t) * (0.45 + 0.55 * hump)
        shimmer = math.sin(2 * math.pi * freq * 2.005 * t) * 0.15
        env = 1.0
        if i < fade:
            env = i / fade
        elif i > total - fade:
            env = max(0.0, (total - i) / fade)
        sample = (pad * 0.34 + arp * 0.58 + shimmer) * 0.10 * env
        value = int(max(-32767, min(32767, sample * 32767)))
        out[i * 2] = value
        out[i * 2 + 1] = value
    return out
