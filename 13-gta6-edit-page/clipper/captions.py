"""ASS subtitles for a 1080x1920 clip: word-by-word captions, hook card, credit lower third.

Follows SETUP_PROMPT section 6/7: the streamer's real words, about 4 words per cue, max 2
lines, one highlight colour, nothing in the top or bottom 10% of the frame.
"""

from .words import mask

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = int(H * 0.12), int(H * 0.86)
HOOK_Y, CREDIT_Y = int(H * 0.12), int(H * 0.88)


def _ts(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _bgr(hex_rgb):
    h = hex_rgb.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def header(font="DejaVu Sans"):
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,5,80,80,0,1",
        f"Style: Hook,{font},70,&H00FFFFFF,&H00FFFFFF,&H00000000,&HE6000000,-1,0,0,0,100,100,0,0,3,18,0,8,90,90,0,1",
        f"Style: Num,{font},96,&H0000E5FF,&H00FFFFFF,&H00000000,&HE6000000,-1,0,0,0,100,100,0,0,3,16,0,8,90,90,0,1",
        f"Style: Credit,{font},38,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,10,0,2,60,60,0,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])


def cues(words, per_cue=4, max_gap=0.7):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= per_cue or w["start"] - cur[-1]["end"] > max_gap):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def caption_events(words, caption_y=None, highlight="#FFE500"):
    """One event per spoken word: the cue stays up, the current word is coloured and pops."""
    y = min(max(caption_y or int(H * 0.66), SAFE_TOP), SAFE_BOTTOM)
    hl = _bgr(highlight)
    lines = []
    for cue in cues(words):
        shown = [_esc(mask(w["word"])) for w in cue]
        for i, w in enumerate(cue):
            end = cue[i + 1]["start"] if i + 1 < len(cue) else w["end"] + 0.25
            if end <= w["start"]:
                continue
            text = " ".join(
                f"{{\\c{hl}\\fscx118\\fscy118\\t(0,120,\\fscx100\\fscy100)}}{s}"
                f"{{\\c&H00FFFFFF&\\fscx100\\fscy100}}" if j == i else s
                for j, s in enumerate(shown))
            lines.append(f"Dialogue: 1,{_ts(w['start'])},{_ts(end)},Cap,,0,0,0,,"
                         f"{{\\pos({W // 2},{y})}}{text}")
    return lines


def text_event(start, end, style, text, y, layer=2, fade_in=0, fade_out=150):
    return (f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,,"
            f"{{\\pos({W // 2},{y})\\fad({fade_in},{fade_out})}}{_esc(text)}")


def build_ass(words, duration, hook="", credit="", caption_y=None, font="DejaVu Sans",
              highlight="#FFE500", hook_seconds=3.0):
    lines = [header(font), *caption_events(words, caption_y, highlight)]
    if hook:
        lines.append(text_event(0, min(hook_seconds, duration), "Hook", hook, HOOK_Y))
    if credit:
        lines.append(text_event(0, duration, "Credit", credit, CREDIT_Y, layer=0, fade_out=0))
    return "\n".join(lines) + "\n"
