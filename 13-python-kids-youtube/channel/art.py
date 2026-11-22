"""Drawn pictures for every scene. No photos and no outside art service."""

from __future__ import annotations

import math
import random
from functools import lru_cache, partial
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = (29, 36, 51)
CREAM = (255, 248, 238)
RED = (226, 84, 82)
YELLOW = (255, 198, 64)
GOLD = (255, 186, 48)
GREEN = (72, 164, 84)
LEAF = (96, 176, 78)
BLUE = (64, 150, 214)
ORANGE = (242, 146, 62)
VIOLET = (138, 108, 198)
BROWN = (154, 98, 58)
WHITE = (255, 255, 255)
PINK = (255, 150, 150)

THEMES: dict[str, tuple[tuple[int, int, int], ...]] = {
    "garden": ((168, 214, 245), (255, 236, 200), (118, 180, 92), (82, 148, 74)),
    "sky": ((142, 198, 240), (255, 224, 180), (116, 178, 98), (76, 144, 82)),
    "night": ((24, 32, 74), (78, 96, 168), (36, 48, 84), (22, 30, 62)),
    "sea": ((132, 202, 230), (186, 228, 220), (42, 136, 176), (26, 100, 148)),
    "space": ((14, 16, 42), (58, 36, 96), (24, 20, 52), (14, 12, 36)),
    "cozy": ((255, 210, 190), (255, 240, 220), (198, 148, 108), (164, 110, 82)),
    "snow": ((186, 214, 238), (232, 240, 246), (220, 230, 238), (186, 202, 216)),
}

_BOLD_CANDIDATES = (
    "/usr/share/fonts/truetype/macos/Inter-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
_TEXT_CANDIDATES = (
    "/usr/share/fonts/truetype/macos/Inter-Medium.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


def _first_font(paths: tuple[str, ...]) -> str:
    for path in paths:
        if Path(path).exists():
            return path
    raise RuntimeError("No usable font found")


BOLD_PATH = _first_font(_BOLD_CANDIDATES)
TEXT_PATH = _first_font(_TEXT_CANDIDATES)


@lru_cache(maxsize=64)
def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = BOLD_PATH if bold else TEXT_PATH
    return ImageFont.truetype(path, max(10, int(size)))


def _box(cx: float, cy: float, rx: float, ry: float | None = None) -> list[float]:
    ry = rx if ry is None else ry
    return [cx - rx, cy - ry, cx + rx, cy + ry]


def _ow(s: float) -> int:
    return max(2, int(s * 0.045))


def _shade(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(max(0, min(255, channel + amount)) for channel in color)


def _sky_color(theme: str, y: float, height: int) -> tuple[int, int, int]:
    top, bottom = THEMES[theme][0], THEMES[theme][1]
    blend = y / max(1, height - 1)
    return tuple(int(a + (b - a) * blend) for a, b in zip(top, bottom))


def _vertical(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    column = Image.new("RGB", (1, height))
    pixels = column.load()
    for y in range(height):
        blend = y / max(1, height - 1)
        pixels[0, y] = tuple(int(a + (b - a) * blend) for a, b in zip(top, bottom))
    return column.resize((width, height), Image.Resampling.BILINEAR)


def _star_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        arm = radius if i % 2 == 0 else radius * 0.42
        points.append((cx + math.cos(angle) * arm, cy + math.sin(angle) * arm))
    return points


def _star(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, fill: tuple[int, int, int] = YELLOW) -> None:
    draw.polygon(_star_points(cx, cy, radius * 1.12), fill=NAVY)
    draw.polygon(_star_points(cx, cy, radius), fill=fill)


def _eyes(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, gap: float = 0.22) -> None:
    radius = max(2.0, s * 0.075)
    for side in (-1, 1):
        ex = cx + side * s * gap
        draw.ellipse(_box(ex, cy, radius, radius * 1.08), fill=NAVY)
        draw.ellipse(_box(ex - radius * 0.35, cy - radius * 0.35, radius * 0.28), fill=WHITE)


def _smile(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float) -> None:
    draw.arc(_box(cx, cy, s * 0.22, s * 0.16), 20, 160, fill=NAVY, width=max(2, int(s * 0.045)))


def _cloud(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, fill: tuple[int, int, int] = WHITE) -> None:
    ow = max(2, int(s * 0.04))
    for dx, dy, r in ((-0.45, 0.08, 0.38), (0.0, -0.12, 0.48), (0.42, 0.06, 0.36), (0.0, 0.16, 0.42)):
        draw.ellipse(_box(cx + dx * s, cy + dy * s, r * s), fill=fill, outline=NAVY, width=ow)


def _leaf(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, angle_hint: float = 0.0) -> None:
    sway = angle_hint
    points = [
        (cx + sway, cy - s),
        (cx + s * 0.62, cy + sway * 0.2),
        (cx + sway * 0.3, cy + s * 0.95),
        (cx - s * 0.62, cy - sway * 0.1),
    ]
    draw.polygon(points, fill=LEAF, outline=NAVY)
    draw.line([(cx, cy - s * 0.75), (cx, cy + s * 0.7)], fill=_shade(LEAF, -50), width=max(2, int(s * 0.08)))


def _flower(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, t: float) -> None:
    sway = math.sin(t * 1.4) * s * 0.05
    ow = _ow(s)
    draw.line([(cx, cy + s * 0.15), (cx + sway, cy + s * 1.05)], fill=GREEN, width=max(3, int(s * 0.08)))
    _leaf(draw, cx + s * 0.28, cy + s * 0.62, s * 0.28, sway)
    petal = (255, 122, 138)
    for i in range(6):
        angle = t * 0.2 + i * math.pi / 3
        px = cx + sway + math.cos(angle) * s * 0.38
        py = cy + math.sin(angle) * s * 0.38
        draw.ellipse(_box(px, py, s * 0.28), fill=petal, outline=NAVY, width=ow)
    draw.ellipse(_box(cx + sway, cy, s * 0.22), fill=YELLOW, outline=NAVY, width=ow)


def _sun(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, t: float, face: bool = True) -> None:
    ow = _ow(s)
    for i in range(12):
        angle = t * 0.5 + i * math.pi / 6
        x0 = cx + math.cos(angle) * s * 0.78
        y0 = cy + math.sin(angle) * s * 0.78
        left = angle + 0.16
        right = angle - 0.16
        x1 = cx + math.cos(left) * s * 1.22
        y1 = cy + math.sin(left) * s * 1.22
        x2 = cx + math.cos(right) * s * 1.22
        y2 = cy + math.sin(right) * s * 1.22
        draw.polygon([(x0, y0), (x1, y1), (x2, y2)], fill=ORANGE)
    draw.ellipse(_box(cx, cy, s * 0.72), fill=YELLOW, outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.28, cy - s * 0.28, s * 0.16), fill=(255, 236, 170))
    if face:
        _eyes(draw, cx, cy - s * 0.02, s)
        _smile(draw, cx, cy + s * 0.16, s)


def _moon_disc(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, face: bool = True) -> None:
    ow = _ow(s)
    draw.ellipse(_box(cx, cy, s), fill=(255, 236, 196), outline=NAVY, width=ow)
    for dx, dy, r in ((-0.25, -0.1, 0.16), (0.22, 0.18, 0.1), (0.05, -0.32, 0.08)):
        draw.ellipse(_box(cx + dx * s, cy + dy * s, r * s), fill=(236, 214, 164))
    if face:
        _eyes(draw, cx, cy - s * 0.02, s * 0.9, gap=0.2)
        _smile(draw, cx, cy + s * 0.18, s * 0.85)


def _crescent(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, cut: tuple[int, int, int]) -> None:
    _moon_disc(draw, cx, cy, s, face=False)
    draw.ellipse(_box(cx + s * 0.42, cy, s * 0.5), fill=cut)


def _half_moon(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, cut: tuple[int, int, int]) -> None:
    _moon_disc(draw, cx, cy, s, face=False)
    draw.pieslice(_box(cx, cy, s * 0.96), 90, 270, fill=cut)
    draw.line([(cx, cy - s), (cx, cy + s)], fill=NAVY, width=_ow(s))


def draw_luma(draw: ImageDraw.ImageDraw, cx: float, cy: float, s: float, t: float) -> None:
    cy = cy + math.sin(t * 2.1) * s * 0.06
    ow = _ow(s)
    draw.ellipse(_box(cx, cy, s * 1.18), fill=(255, 214, 120))
    draw.arc(_box(cx, cy - s * 0.95, s * 0.34), 200, 340, fill=NAVY, width=max(3, int(s * 0.08)))
    draw.rounded_rectangle(
        [cx - s * 0.26, cy - s * 0.98, cx + s * 0.26, cy - s * 0.62],
        radius=max(2, int(s * 0.12)),
        fill=GOLD,
        outline=NAVY,
        width=ow,
    )
    draw.ellipse(_box(cx, cy + s * 0.02, s * 0.7, s * 0.76), fill=GOLD, outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.26, cy - s * 0.22, s * 0.14, s * 0.2), fill=(255, 230, 160))
    _eyes(draw, cx, cy - s * 0.02, s * 0.95, gap=0.2)
    _smile(draw, cx, cy + s * 0.2, s * 0.8)
    draw.ellipse(_box(cx - s * 0.34, cy + s * 0.16, s * 0.1, s * 0.065), fill=PINK)
    draw.ellipse(_box(cx + s * 0.34, cy + s * 0.16, s * 0.1, s * 0.065), fill=PINK)
    draw.ellipse(_box(cx - s * 0.24, cy + s * 0.72, s * 0.14, s * 0.07), fill=BROWN, outline=NAVY, width=max(2, ow // 2))
    draw.ellipse(_box(cx + s * 0.24, cy + s * 0.72, s * 0.14, s * 0.07), fill=BROWN, outline=NAVY, width=max(2, ow // 2))


def draw_bee(draw, cx, cy, s, t, cut, n=0):
    bob = math.sin(t * 3) * s * 0.06
    cx = cx + math.sin(t * 1.6) * s * 0.08
    cy = cy + bob
    ow = _ow(s)
    draw.ellipse(_box(cx - s * 0.18, cy - s * 0.42, s * 0.36, s * 0.2), fill=(236, 246, 255), outline=NAVY, width=ow)
    draw.ellipse(_box(cx + s * 0.28, cy - s * 0.36, s * 0.3, s * 0.16), fill=(236, 246, 255), outline=NAVY, width=ow)
    stripes = (YELLOW, NAVY, YELLOW, NAVY, YELLOW)
    for i, color in enumerate(stripes):
        draw.ellipse(_box(cx - s * 0.42 + i * s * 0.22, cy, s * 0.24, s * 0.32), fill=color, outline=NAVY, width=max(2, ow // 2))
    _eyes(draw, cx + s * 0.36, cy - s * 0.04, s * 0.55, gap=0.16)
    _smile(draw, cx + s * 0.36, cy + s * 0.12, s * 0.4)


def draw_flower(draw, cx, cy, s, t, cut, n=0):
    _flower(draw, cx, cy - s * 0.15, s * 0.85, t)


def draw_sun(draw, cx, cy, s, t, cut, n=0):
    _sun(draw, cx, cy, s * 0.85, t, face=True)


def draw_moon(draw, cx, cy, s, t, cut, n=0):
    _moon_disc(draw, cx, cy + math.sin(t) * s * 0.03, s * 0.9, face=True)


def draw_phases(draw, cx, cy, s, t, cut, n=0):
    spots = (-1.25, 0.0, 1.25)
    _crescent(draw, cx + spots[0] * s, cy, s * 0.38, cut)
    _half_moon(draw, cx + spots[1] * s, cy, s * 0.38, cut)
    _moon_disc(draw, cx + spots[2] * s, cy, s * 0.38, face=False)


def draw_cloud(draw, cx, cy, s, t, cut, n=0):
    _cloud(draw, cx, cy + math.sin(t) * s * 0.04, s * 0.95)


def draw_rain(draw, cx, cy, s, t, cut, n=0):
    _cloud(draw, cx, cy - s * 0.35, s * 0.7)
    for i in range(8):
        drop_x = cx + ((i - 3.5) * s * 0.16)
        cycle = (t * 0.55 + i * 0.13) % 1
        drop_y = cy + cycle * s * 0.95
        draw.line([(drop_x, drop_y), (drop_x + 2, drop_y + s * 0.16)], fill=BLUE, width=max(2, int(s * 0.035)))
    _flower(draw, cx, cy + s * 0.72, s * 0.28, t)


def draw_star(draw, cx, cy, s, t, cut, n=0):
    tw = 0.9 + 0.1 * math.sin(t * 3)
    _star(draw, cx, cy, s * 0.55 * tw)
    _star(draw, cx - s * 0.55, cy + s * 0.25, s * 0.22)
    _star(draw, cx + s * 0.5, cy + s * 0.18, s * 0.16, fill=WHITE)


def draw_count(draw, cx, cy, s, t, cut, n=1):
    span = max(1, n - 1)
    for i in range(n):
        x = cx + (i - span / 2) * s * 0.48
        tw = 0.92 + 0.08 * math.sin(t * 2 + i)
        _star(draw, x, cy + s * 0.18, s * 0.2 * tw)
    label = font(int(s * 0.95), bold=True)
    text = str(n)
    origin = (cx, cy - s * 0.55)
    halo = max(2, int(s * 0.035))
    for dx, dy in ((-halo, 0), (halo, 0), (0, -halo), (0, halo), (-halo, -halo), (halo, -halo), (-halo, halo), (halo, halo)):
        draw.text((origin[0] + dx, origin[1] + dy), text, font=label, fill=NAVY, anchor="mm")
    draw.text(origin, text, font=label, fill=YELLOW, anchor="mm")


def draw_fish(draw, cx, cy, s, t, cut, n=0):
    cx = cx + math.sin(t * 1.5) * s * 0.08
    ow = _ow(s)
    draw.polygon(
        [
            (cx - s * 0.55, cy),
            (cx - s * 1.0, cy - s * 0.32),
            (cx - s * 1.0, cy + s * 0.32),
        ],
        fill=ORANGE,
        outline=NAVY,
    )
    draw.ellipse(_box(cx + s * 0.05, cy, s * 0.62, s * 0.38), fill=ORANGE, outline=NAVY, width=ow)
    draw.ellipse(_box(cx + s * 0.15, cy + s * 0.08, s * 0.4, s * 0.16), fill=(255, 196, 140))
    draw.polygon(
        [(cx + s * 0.15, cy - s * 0.05), (cx - s * 0.05, cy - s * 0.38), (cx + s * 0.28, cy - s * 0.02)],
        fill=ORANGE,
        outline=NAVY,
    )
    draw.ellipse(_box(cx + s * 0.36, cy - s * 0.06, s * 0.07), fill=NAVY)
    draw.ellipse(_box(cx + s * 0.34, cy - s * 0.08, s * 0.025), fill=WHITE)
    for i in range(3):
        cycle = (t * 0.4 + i * 0.3) % 1
        draw.ellipse(
            _box(cx + s * 0.7, cy - s * 0.2 - cycle * s * 0.6, s * 0.05 + cycle * s * 0.04),
            outline=WHITE,
            width=2,
        )


def draw_bird(draw, cx, cy, s, t, cut, n=0):
    cy = cy + math.sin(t * 2) * s * 0.05
    ow = _ow(s)
    draw.polygon(
        [(cx - s * 0.2, cy), (cx - s * 0.85, cy - s * 0.18), (cx - s * 0.75, cy + s * 0.2)],
        fill=BLUE,
        outline=NAVY,
    )
    draw.ellipse(_box(cx, cy, s * 0.42, s * 0.32), fill=BLUE, outline=NAVY, width=ow)
    draw.ellipse(_box(cx + s * 0.08, cy + s * 0.06, s * 0.22, s * 0.14), fill=(186, 220, 245))
    draw.ellipse(_box(cx + s * 0.32, cy - s * 0.18, s * 0.22), fill=BLUE, outline=NAVY, width=ow)
    draw.polygon(
        [(cx + s * 0.48, cy - s * 0.16), (cx + s * 0.78, cy - s * 0.08), (cx + s * 0.48, cy - s * 0.02)],
        fill=ORANGE,
    )
    draw.ellipse(_box(cx + s * 0.36, cy - s * 0.24, s * 0.045), fill=NAVY)
    draw.line([(cx + s * 0.05, cy + s * 0.28), (cx + s * 0.02, cy + s * 0.55)], fill=ORANGE, width=max(2, ow // 2))
    draw.line([(cx - s * 0.12, cy + s * 0.28), (cx - s * 0.16, cy + s * 0.55)], fill=ORANGE, width=max(2, ow // 2))


def draw_tree(draw, cx, cy, s, t, cut, n=0):
    ow = _ow(s)
    draw.rounded_rectangle(
        [cx - s * 0.1, cy + s * 0.05, cx + s * 0.1, cy + s * 0.85],
        radius=6,
        fill=BROWN,
        outline=NAVY,
        width=max(2, ow // 2),
    )
    for dx, dy, r in ((0, -0.35, 0.48), (-0.32, -0.05, 0.36), (0.32, -0.02, 0.34)):
        draw.ellipse(_box(cx + dx * s, cy + dy * s, r * s), fill=GREEN, outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.12, cy - s * 0.15, s * 0.08), fill=RED, outline=NAVY, width=2)
    draw.ellipse(_box(cx + s * 0.18, cy - s * 0.28, s * 0.07), fill=RED, outline=NAVY, width=2)


def draw_nest(draw, cx, cy, s, t, cut, n=0):
    ow = _ow(s)
    draw.ellipse(_box(cx, cy + s * 0.18, s * 0.78, s * 0.4), fill=BROWN, outline=NAVY, width=ow)
    draw.arc(_box(cx, cy + s * 0.05, s * 0.7, s * 0.28), 200, 340, fill=_shade(BROWN, 40), width=max(2, int(s * 0.04)))
    for dx in (-0.28, 0.0, 0.28):
        draw.ellipse(_box(cx + dx * s, cy + s * 0.02, s * 0.15, s * 0.2), fill=(232, 242, 248), outline=NAVY, width=max(2, ow // 2))


def draw_rocket(draw, cx, cy, s, t, cut, n=0):
    cy = cy + math.sin(t * 2) * s * 0.05
    ow = _ow(s)
    flicker = 0.75 + 0.25 * abs(math.sin(t * 14))
    draw.polygon(
        [
            (cx - s * 0.14, cy + s * 0.48),
            (cx + s * 0.14, cy + s * 0.48),
            (cx, cy + s * (0.95 + 0.2 * flicker)),
        ],
        fill=ORANGE,
    )
    draw.polygon(
        [
            (cx - s * 0.07, cy + s * 0.5),
            (cx + s * 0.07, cy + s * 0.5),
            (cx, cy + s * (0.78 + 0.12 * flicker)),
        ],
        fill=YELLOW,
    )
    draw.polygon([(cx - s * 0.42, cy + s * 0.42), (cx - s * 0.18, cy + s * 0.05), (cx - s * 0.18, cy + s * 0.48)], fill=RED, outline=NAVY)
    draw.polygon([(cx + s * 0.42, cy + s * 0.42), (cx + s * 0.18, cy + s * 0.05), (cx + s * 0.18, cy + s * 0.48)], fill=RED, outline=NAVY)
    draw.rounded_rectangle(
        [cx - s * 0.2, cy - s * 0.55, cx + s * 0.2, cy + s * 0.5],
        radius=max(4, int(s * 0.12)),
        fill=(238, 244, 250),
        outline=NAVY,
        width=ow,
    )
    draw.polygon([(cx - s * 0.2, cy - s * 0.4), (cx + s * 0.2, cy - s * 0.4), (cx, cy - s * 1.05)], fill=RED, outline=NAVY)
    draw.ellipse(_box(cx, cy - s * 0.05, s * 0.11), fill=(150, 206, 240), outline=NAVY, width=max(2, ow // 2))


def draw_train(draw, cx, cy, s, t, cut, n=0):
    cx = cx + math.sin(t * 1.2) * s * 0.06
    ow = _ow(s)
    for i in range(3):
        cycle = (t * 0.35 + i / 3) % 1
        draw.ellipse(
            _box(cx - s * 0.55 + cycle * 8, cy - s * 0.55 - cycle * s * 0.45, s * (0.08 + cycle * 0.06)),
            fill=WHITE,
            outline=NAVY,
            width=2,
        )
    draw.rounded_rectangle([cx - s * 0.15, cy - s * 0.55, cx + s * 0.45, cy + s * 0.05], radius=8, fill=RED, outline=NAVY, width=ow)
    draw.rounded_rectangle([cx - s * 0.85, cy - s * 0.15, cx + s * 0.15, cy + s * 0.28], radius=8, fill=BLUE, outline=NAVY, width=ow)
    draw.rectangle([cx - s * 0.02, cy - s * 0.72, cx + s * 0.08, cy - s * 0.45], fill=NAVY)
    draw.rectangle([cx + s * 0.05, cy - s * 0.38, cx + s * 0.28, cy - s * 0.16], fill=(190, 230, 250), outline=NAVY, width=2)
    for wheel_x in (-0.55, -0.2, 0.15):
        draw.ellipse(_box(cx + wheel_x * s, cy + s * 0.34, s * 0.14), fill=NAVY)
        draw.ellipse(_box(cx + wheel_x * s, cy + s * 0.34, s * 0.05), fill=YELLOW)


def draw_apple(draw, cx, cy, s, t, cut, n=0):
    ow = _ow(s)
    draw.ellipse(_box(cx, cy + s * 0.05, s * 0.58, s * 0.5), fill=RED, outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.22, cy - s * 0.12, s * 0.12, s * 0.16), fill=(255, 170, 160))
    draw.line([(cx, cy - s * 0.4), (cx + s * 0.04, cy - s * 0.72)], fill=BROWN, width=max(3, int(s * 0.05)))
    _leaf(draw, cx + s * 0.22, cy - s * 0.62, s * 0.22, s * 0.05)


def draw_butterfly(draw, cx, cy, s, t, cut, n=0):
    flap = 0.55 + 0.45 * abs(math.sin(t * 4))
    ow = _ow(s)
    wing = (255, 140, 170)
    draw.ellipse(_box(cx - s * 0.38, cy - s * 0.12, s * 0.42 * flap, s * 0.36), fill=wing, outline=NAVY, width=ow)
    draw.ellipse(_box(cx + s * 0.38, cy - s * 0.12, s * 0.42 * flap, s * 0.36), fill=wing, outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.28, cy + s * 0.28, s * 0.28 * flap, s * 0.24), fill=(255, 196, 120), outline=NAVY, width=ow)
    draw.ellipse(_box(cx + s * 0.28, cy + s * 0.28, s * 0.28 * flap, s * 0.24), fill=(255, 196, 120), outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.38, cy - s * 0.12, s * 0.12), fill=YELLOW)
    draw.ellipse(_box(cx + s * 0.38, cy - s * 0.12, s * 0.12), fill=YELLOW)
    draw.rounded_rectangle([cx - s * 0.06, cy - s * 0.45, cx + s * 0.06, cy + s * 0.5], radius=6, fill=NAVY)
    draw.line([(cx, cy - s * 0.4), (cx - s * 0.18, cy - s * 0.7)], fill=NAVY, width=2)
    draw.line([(cx, cy - s * 0.4), (cx + s * 0.18, cy - s * 0.7)], fill=NAVY, width=2)
    draw.ellipse(_box(cx - s * 0.18, cy - s * 0.7, s * 0.04), fill=NAVY)
    draw.ellipse(_box(cx + s * 0.18, cy - s * 0.7, s * 0.04), fill=NAVY)


def draw_heart(draw, cx, cy, s, t, cut, n=0):
    pulse = 1 + 0.04 * math.sin(t * 3)
    s = s * pulse
    ow = _ow(s)
    draw.polygon(
        [(cx - s * 0.72, cy), (cx + s * 0.72, cy), (cx, cy + s * 0.85)],
        fill=RED,
    )
    draw.ellipse(_box(cx - s * 0.32, cy - s * 0.12, s * 0.4), fill=RED, outline=NAVY, width=ow)
    draw.ellipse(_box(cx + s * 0.32, cy - s * 0.12, s * 0.4), fill=RED, outline=NAVY, width=ow)
    draw.polygon([(cx - s * 0.7, cy + s * 0.02), (cx + s * 0.7, cy + s * 0.02), (cx, cy + s * 0.82)], fill=RED)


def draw_balloon(draw, cx, cy, s, t, cut, n=0):
    cy = cy + math.sin(t * 1.5) * s * 0.06
    ow = _ow(s)
    draw.line([(cx, cy + s * 0.45), (cx + math.sin(t) * s * 0.08, cy + s * 1.0)], fill=NAVY, width=max(2, int(s * 0.03)))
    draw.ellipse(_box(cx, cy, s * 0.46, s * 0.58), fill=(255, 112, 122), outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.16, cy - s * 0.18, s * 0.1, s * 0.16), fill=(255, 200, 200))
    draw.polygon([(cx - s * 0.08, cy + s * 0.5), (cx + s * 0.08, cy + s * 0.5), (cx, cy + s * 0.66)], fill=RED, outline=NAVY)


def draw_turtle(draw, cx, cy, s, t, cut, n=0):
    cx = cx + math.sin(t * 0.8) * s * 0.04
    ow = _ow(s)
    for dx, dy in ((-0.45, 0.28), (0.45, 0.28), (-0.38, -0.05), (0.5, 0.02)):
        draw.ellipse(_box(cx + dx * s, cy + dy * s, s * 0.16, s * 0.1), fill=GREEN, outline=NAVY, width=2)
    draw.ellipse(_box(cx + s * 0.62, cy - s * 0.02, s * 0.2), fill=LEAF, outline=NAVY, width=ow)
    _eyes(draw, cx + s * 0.66, cy - s * 0.06, s * 0.35, gap=0.12)
    draw.ellipse(_box(cx, cy, s * 0.55, s * 0.38), fill=GREEN, outline=NAVY, width=ow)
    for dx, dy in ((-0.18, -0.08), (0.16, -0.1), (0.0, 0.12), (-0.2, 0.14)):
        draw.ellipse(_box(cx + dx * s, cy + dy * s, s * 0.12), outline=_shade(GREEN, -40), width=max(2, int(s * 0.03)))


def draw_snow(draw, cx, cy, s, t, cut, n=0):
    ow = _ow(s)
    draw.ellipse(_box(cx, cy + s * 0.28, s * 0.42), fill=WHITE, outline=NAVY, width=ow)
    draw.ellipse(_box(cx, cy - s * 0.22, s * 0.28), fill=WHITE, outline=NAVY, width=ow)
    draw.polygon([(cx - s * 0.22, cy - s * 0.48), (cx + s * 0.22, cy - s * 0.48), (cx + s * 0.16, cy - s * 0.7), (cx - s * 0.16, cy - s * 0.7)], fill=NAVY)
    draw.rectangle([cx - s * 0.28, cy - s * 0.52, cx + s * 0.28, cy - s * 0.44], fill=RED)
    draw.rectangle([cx - s * 0.32, cy + s * 0.02, cx + s * 0.32, cy + s * 0.1], fill=RED)
    _eyes(draw, cx, cy - s * 0.24, s * 0.4, gap=0.16)
    draw.polygon([(cx, cy - s * 0.12), (cx + s * 0.16, cy - s * 0.08), (cx, cy - s * 0.04)], fill=ORANGE)
    for i in range(10):
        cycle = (t * 0.3 + i * 0.17) % 1
        flake_x = cx + math.sin(i) * s * 0.9
        flake_y = cy - s * 0.8 + cycle * s * 1.6
        draw.ellipse(_box(flake_x, flake_y, s * 0.035), fill=WHITE, outline=NAVY, width=1)


def draw_whale(draw, cx, cy, s, t, cut, n=0):
    cx = cx + math.sin(t * 0.7) * s * 0.05
    ow = _ow(s)
    draw.polygon(
        [(cx - s * 0.72, cy + s * 0.05), (cx - s * 1.05, cy - s * 0.28), (cx - s * 0.95, cy + s * 0.32)],
        fill=BLUE,
        outline=NAVY,
    )
    draw.ellipse(_box(cx + s * 0.05, cy, s * 0.78, s * 0.4), fill=BLUE, outline=NAVY, width=ow)
    draw.ellipse(_box(cx + s * 0.1, cy + s * 0.12, s * 0.5, s * 0.18), fill=(170, 214, 236))
    draw.polygon([(cx + s * 0.15, cy + s * 0.05), (cx - s * 0.05, cy + s * 0.35), (cx + s * 0.28, cy + s * 0.12)], fill=(48, 120, 180), outline=NAVY)
    draw.ellipse(_box(cx + s * 0.48, cy - s * 0.08, s * 0.06), fill=NAVY)
    draw.ellipse(_box(cx + s * 0.46, cy - s * 0.1, s * 0.02), fill=WHITE)
    for i in range(3):
        cycle = (t * 0.45 + i * 0.25) % 1
        draw.ellipse(_box(cx + s * 0.15, cy - s * 0.35 - cycle * s * 0.4, s * (0.04 + cycle * 0.04)), fill=WHITE, outline=NAVY, width=1)


def draw_seed(draw, cx, cy, s, t, cut, n=0):
    ow = _ow(s)
    grow = 0.85 + 0.15 * math.sin(t)
    draw.ellipse(_box(cx, cy + s * 0.45, s * 0.7, s * 0.28), fill=(120, 86, 54))
    draw.ellipse(_box(cx, cy + s * 0.38, s * 0.1, s * 0.14), fill=(196, 150, 72), outline=NAVY, width=2)
    draw.line([(cx, cy + s * 0.3), (cx, cy - s * 0.15 * grow)], fill=GREEN, width=max(3, int(s * 0.06)))
    _leaf(draw, cx + s * 0.22, cy - s * 0.15, s * 0.32 * grow, s * 0.04)
    _leaf(draw, cx - s * 0.18, cy + s * 0.02, s * 0.26 * grow, -s * 0.04)


def draw_rainbow(draw, cx, cy, s, t, cut, n=0):
    colors = (RED, ORANGE, YELLOW, GREEN, BLUE, VIOLET)
    for i, color in enumerate(colors):
        inset = i * s * 0.1
        width = max(6, int(s * 0.09))
        draw.arc(
            _box(cx, cy + s * 0.35, s * 0.95 - inset, s * 0.75 - inset),
            200,
            340,
            fill=color,
            width=width,
        )
    _cloud(draw, cx - s * 0.72, cy + s * 0.32, s * 0.28)
    _sun(draw, cx + s * 0.78, cy - s * 0.15, s * 0.22, t, face=False)


def draw_book(draw, cx, cy, s, t, cut, n=0):
    ow = _ow(s)
    open_shift = math.sin(t) * s * 0.02
    draw.rounded_rectangle(
        [cx - s * 0.92, cy - s * 0.62, cx - 2, cy + s * 0.68],
        radius=10,
        fill=CREAM,
        outline=NAVY,
        width=ow,
    )
    draw.rounded_rectangle(
        [cx + 2, cy - s * 0.62, cx + s * 0.92, cy + s * 0.68],
        radius=10,
        fill=WHITE,
        outline=NAVY,
        width=ow,
    )
    draw.rectangle([cx - s * 0.06, cy - s * 0.62, cx + s * 0.06, cy + s * 0.68], fill=(214, 96, 86))
    for i in range(4):
        y = cy - s * 0.32 + i * s * 0.2
        draw.line([(cx + s * 0.18, y), (cx + s * 0.74, y + open_shift)], fill=(176, 190, 204), width=max(2, int(s * 0.025)))
    _star(draw, cx - s * 0.46, cy, s * 0.2)


def draw_water(draw, cx, cy, s, t, cut, n=0):
    ow = _ow(s)
    bob = math.sin(t * 2) * s * 0.04
    draw.ellipse(_box(cx, cy + s * 0.35, s * 0.75, s * 0.22), fill=(36, 120, 170))
    draw.pieslice(_box(cx, cy + bob, s * 0.42, s * 0.55), 200, 340, fill=BLUE, outline=NAVY, width=ow)
    draw.ellipse(_box(cx - s * 0.12, cy - s * 0.08 + bob, s * 0.08, s * 0.12), fill=(210, 236, 255))


def draw_leaf_motif(draw, cx, cy, s, t, cut, n=0):
    sway = math.sin(t * 1.3) * s * 0.08
    _leaf(draw, cx, cy, s * 0.9, sway)


def draw_lantern(draw, cx, cy, s, t, cut, n=0):
    draw_luma(draw, cx, cy, s * 0.85, t)


MOTIF_FN = {
    "lantern": draw_lantern,
    "bee": draw_bee,
    "flower": draw_flower,
    "seed": draw_seed,
    "leaf": draw_leaf_motif,
    "water": draw_water,
    "sun": draw_sun,
    "moon": draw_moon,
    "phases": draw_phases,
    "cloud": draw_cloud,
    "rain": draw_rain,
    "star": draw_star,
    "fish": draw_fish,
    "bird": draw_bird,
    "tree": draw_tree,
    "nest": draw_nest,
    "rocket": draw_rocket,
    "train": draw_train,
    "apple": draw_apple,
    "butterfly": draw_butterfly,
    "heart": draw_heart,
    "balloon": draw_balloon,
    "turtle": draw_turtle,
    "snow": draw_snow,
    "whale": draw_whale,
    "rainbow": draw_rainbow,
    "book": draw_book,
    "n1": partial(draw_count, n=1),
    "n2": partial(draw_count, n=2),
    "n3": partial(draw_count, n=3),
    "n4": partial(draw_count, n=4),
    "n5": partial(draw_count, n=5),
}
MOTIFS = set(MOTIF_FN)


_BACKGROUNDS: dict[tuple, Image.Image] = {}
_STAR_FIELDS: dict[tuple, list[tuple[float, float, float]]] = {}


def _background(theme: str, size: tuple[int, int]) -> Image.Image:
    key = (theme, size)
    if key not in _BACKGROUNDS:
        _BACKGROUNDS[key] = _paint_background(theme, size)
    return _BACKGROUNDS[key].copy()


def _paint_background(theme: str, size: tuple[int, int]) -> Image.Image:
    width, height = size
    top, bottom, ground, far = THEMES[theme]
    image = _vertical(size, top, bottom).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.ellipse(_box(width * 0.5, height * 1.08, width * 0.78, height * 0.42), fill=far)
    draw.ellipse(_box(width * 0.5, height * 1.05, width * 0.92, height * 0.36), fill=ground)
    if theme == "sea":
        for i, shade in enumerate((180, 210, 230)):
            y = height * (0.72 + i * 0.05)
            draw.arc([width * 0.05, y, width * 0.95, y + height * 0.08], 200, 340, fill=(shade, shade + 10, 255), width=3)
    elif theme == "space":
        rng = random.Random("craters")
        for _ in range(5):
            draw.ellipse(
                _box(rng.uniform(width * 0.2, width * 0.8), rng.uniform(height * 0.78, height * 0.9), rng.uniform(8, 22)),
                outline=_shade(ground, 30),
                width=2,
            )
    elif theme == "snow":
        pass
    elif theme != "night":
        tuft = _shade(ground, -28)
        rng = random.Random(theme)
        crest = int(height * 0.7)
        for i in range(8):
            x = int(width * (0.08 + i * 0.12))
            blade = int(height * rng.uniform(0.03, 0.055))
            draw.line([(x, crest), (x - 8, crest - blade)], fill=tuft, width=3)
            draw.line([(x, crest), (x + 10, crest - int(blade * 0.75))], fill=tuft, width=3)
        if theme == "garden":
            for x in (0.18, 0.4, 0.62, 0.84):
                _flower(draw, width * x, height * 0.69, height * 0.035, 0.4)
    return image


def _star_field(theme: str, size: tuple[int, int]) -> list[tuple[float, float, float]]:
    key = (theme, size)
    if key not in _STAR_FIELDS:
        rng = random.Random(theme)
        width, height = size
        _STAR_FIELDS[key] = [
            (rng.random() * width, rng.random() * height * 0.62, rng.uniform(1.4, 3.0))
            for _ in range(26)
        ]
    return _STAR_FIELDS[key]


def _atmosphere(draw: ImageDraw.ImageDraw, theme: str, motif: str, size: tuple[int, int], t: float) -> None:
    width, height = size
    if theme in {"night", "space"}:
        for index, (x, y, radius) in enumerate(_star_field(theme, size)):
            twinkle = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 3 + index))
            if twinkle < 0.35:
                continue
            draw.ellipse(_box(x, y, radius * twinkle), fill=(255, 244, 210))
        if motif not in {"moon", "phases", "star", "n1", "n2", "n3", "n4", "n5"}:
            _moon_disc(draw, width * 0.84, height * 0.16, min(size) * 0.055, face=False)
        return
    if theme == "snow":
        for i in range(16):
            cycle = (t * 0.25 + i * 0.07) % 1
            x = (0.05 + (i * 0.067) % 1) * width
            y = cycle * height * 0.7
            draw.ellipse(_box(x, y, 2.4), fill=WHITE)
    drift = ((0.12, 0.16, 0.10, 26), (0.48, 0.12, 0.08, 16), (0.78, 0.2, 0.07, 22))
    for index, (x, y, scale, speed) in enumerate(drift):
        cx = (x * width + t * speed * 8) % (width + 220) - 110
        _cloud(draw, cx, y * height, width * scale * 0.45, fill=WHITE if theme != "snow" else (248, 252, 255))
    if theme in {"garden", "sky", "cozy", "sea"} and motif != "sun":
        _sun(draw, width * 0.88, height * 0.15, min(size) * 0.055, t, face=False)


def _wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=face) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _draw_centered(draw, lines, face, cx, cy, fill, size) -> None:
    line_h = int(size * 1.18)
    block = line_h * len(lines)
    y0 = cy - block / 2 + line_h / 2
    for index, line in enumerate(lines):
        draw.text((cx, y0 + index * line_h), line, font=face, fill=fill, anchor="mm")


def _fit_text(draw, text, max_width, max_height, start):
    size = start
    face = font(size, bold=True)
    lines = _wrap(draw, text, face, max_width)
    while size > 16:
        face = font(size, bold=True)
        lines = _wrap(draw, text, face, max_width)
        if len(lines) * size * 1.18 <= max_height and all(draw.textlength(line, font=face) <= max_width for line in lines):
            return face, lines, size
        size -= 2
    return face, lines, size


def _card(draw, box, radius) -> None:
    shadow = [box[0] + 5, box[1] + 6, box[2] + 5, box[3] + 6]
    draw.rounded_rectangle(shadow, radius=radius, fill=(40, 48, 64))
    draw.rounded_rectangle(box, radius=radius, fill=CREAM, outline=NAVY, width=4)


def _layout(kind: str, width: int, height: int) -> dict:
    unit = min(width, height)
    if kind == "title":
        return {
            "motif": (width * 0.7, height * 0.58, unit * 0.16),
            "luma": (width * 0.32, height * 0.58, unit * 0.17),
            "card": "title",
        }
    if kind == "bye":
        return {"motif": None, "luma": (width * 0.5, height * 0.44, unit * 0.22), "card": "bottom"}
    if kind == "thumb":
        return {
            "motif": (width * 0.52, height * 0.38, unit * 0.28),
            "luma": (width * 0.16, height * 0.58, unit * 0.09),
            "card": "thumb",
        }
    return {
        "motif": (width * 0.58, height * 0.4, unit * 0.24),
        "luma": (width * 0.16, height * 0.56, unit * 0.11),
        "card": "bottom",
    }


def render_frame(
    *,
    kind: str,
    motif: str,
    theme: str,
    caption: str,
    title: str,
    size: tuple[int, int],
    t: float,
) -> Image.Image:
    if theme not in THEMES:
        theme = "garden"
    width, height = size
    image = _background(theme, size)
    draw = ImageDraw.Draw(image)
    _atmosphere(draw, theme, motif, size, t)
    places = _layout(kind, width, height)
    cut = _sky_color(theme, height * 0.4, height)
    if places["motif"] and motif in MOTIF_FN:
        cx, cy, scale = places["motif"]
        MOTIF_FN[motif](draw, cx, cy + math.sin(t * 1.3) * scale * 0.03, scale, t, cut)
    if places["luma"]:
        lx, ly, ls = places["luma"]
        draw_luma(draw, lx, ly, ls, t)
    _lettering(draw, kind, caption, title, size)
    if kind == "teach":
        _bug(draw, size)
    return image.convert("RGB")


def _bug(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    width, height = size
    box = [int(width * 0.04), int(height * 0.045), int(width * 0.34), int(height * 0.12)]
    draw.rounded_rectangle(box, radius=14, fill=CREAM, outline=NAVY, width=3)
    face = font(max(14, int(width * 0.028)), bold=True)
    draw.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), "Little Lantern", font=face, fill=NAVY, anchor="mm")


def _lettering(draw, kind, caption, title, size) -> None:
    width, height = size
    if kind == "title":
        block = [int(width * 0.08), int(height * 0.08), int(width * 0.92), int(height * 0.3)]
        _card(draw, block, radius=28)
        kicker = font(max(16, int(width * 0.028)), bold=False)
        draw.text((width / 2, block[1] + (block[3] - block[1]) * 0.28), "Little Lantern", font=kicker, fill=(180, 90, 70), anchor="mm")
        face, lines, px = _fit_text(draw, title or caption, int(width * 0.76), int(height * 0.14), int(width * 0.06))
        _draw_centered(draw, lines, face, width / 2, block[1] + (block[3] - block[1]) * 0.64, NAVY, px)
        return
    top = 0.73 if kind != "thumb" else 0.68
    block = [int(width * 0.06), int(height * top), int(width * 0.94), int(height * 0.95)]
    _card(draw, block, radius=26)
    text = title if kind == "thumb" else caption
    start = int(width * (0.072 if kind == "thumb" else 0.04))
    face, lines, px = _fit_text(
        draw,
        text,
        block[2] - block[0] - int(width * 0.06),
        block[3] - block[1] - int(height * 0.04),
        start,
    )
    _draw_centered(draw, lines, face, width / 2, (block[1] + block[3]) / 2, NAVY, px)
    if kind == "thumb":
        kicker = font(max(14, int(width * 0.028)), bold=True)
        label = "Little Lantern"
        text_width = draw.textlength(label, font=kicker)
        pad_x = int(width * 0.012)
        pad_y = int(height * 0.012)
        left = int(width * 0.06)
        mid = int(height * 0.09)
        draw.rounded_rectangle(
            [left - pad_x, mid - pad_y * 2, left + text_width + pad_x, mid + pad_y * 2],
            radius=12,
            fill=CREAM,
            outline=NAVY,
            width=3,
        )
        draw.text((left, mid), label, font=kicker, fill=NAVY, anchor="lm")


def render_avatar(size: int = 800) -> Image.Image:
    image = _vertical((size, size), (255, 214, 170), (255, 236, 200)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.ellipse(_box(size * 0.5, size * 1.15, size * 0.7, size * 0.38), fill=(118, 180, 92))
    draw_luma(draw, size * 0.5, size * 0.48, size * 0.24, 0.6)
    return image.convert("RGB")


def render_banner(tagline: str, size: tuple[int, int] = (2560, 1440)) -> Image.Image:
    width, height = size
    image = _background("garden", size)
    draw = ImageDraw.Draw(image)
    _atmosphere(draw, "garden", "flower", size, 0.8)
    block = [int(width * 0.3), int(height * 0.38), int(width * 0.7), int(height * 0.62)]
    _card(draw, block, radius=36)
    title_font = font(max(32, int(width * 0.046)), bold=True)
    sub_font = font(max(18, int(width * 0.02)), bold=False)
    draw.text((width / 2, height * 0.46), "Little Lantern", font=title_font, fill=NAVY, anchor="mm")
    draw.text((width / 2, height * 0.55), tagline, font=sub_font, fill=(160, 84, 64), anchor="mm")
    draw_luma(draw, width * 0.16, height * 0.58, min(size) * 0.1, 0.8)
    _flower(draw, width * 0.86, height * 0.56, min(size) * 0.08, 0.4)
    return image.convert("RGB")


def save_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        image.convert("RGB").save(path, quality=90)
    else:
        image.convert("RGB").save(path)
