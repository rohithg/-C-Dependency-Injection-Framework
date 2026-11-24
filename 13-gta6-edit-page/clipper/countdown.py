"""'5 craziest GTA 6 stream moments': the page's most edited format (SETUP_PROMPT section 4).

Takes rendered drafts (their caption-free base.mp4 + words), trims each to its peak, plays
them #5 -> #1 with a title card, numbered headers, captions and a credit per segment.
"""

import json
from datetime import date
from pathlib import Path

from . import captions as C
from . import hooks as Hk
from .media import probe
from .pipeline import master

PRE, POST = 7.0, 4.0
TITLE_SECONDS = 2.8


def pick(page_dir, n=5):
    """Best n drafts or approved clips across all runs, by moment score."""
    found = []
    for meta_path in Path(page_dir, "runs").glob("*/clips/*/meta.json"):
        meta = json.loads(meta_path.read_text())
        if meta.get("status") in ("draft", "approved", "posted") and (meta_path.parent / "base.mp4").exists():
            found.append((meta["moment"].get("score", 0), meta_path.parent))
    found.sort(key=lambda t: -t[0])
    return [d for _, d in found[:n]]


def _window(meta, words, duration):
    peak = meta.get("peak") or duration / 2
    a, b = max(0.0, peak - PRE), min(duration, peak + POST)
    starts = [w["start"] for w in words if a - 1.5 <= w["start"] <= a + 1.5]
    if starts:
        a = max(0.0, min(starts, key=lambda s: abs(s - a)) - 0.1)
    return a, b


def build(page_dir, clip_dirs, title=None, slug=None):
    """clip_dirs best-first. Writes countdowns/<slug>/ with plan.json, meta.json, final.mp4."""
    page_dir = Path(page_dir).resolve()
    clip_dirs = [Path(d).resolve() for d in clip_dirs]
    n = len(clip_dirs)
    if n < 2:
        raise ValueError("a countdown needs at least 2 clips")
    plan = []
    for rank, d in enumerate(clip_dirs, 1):
        meta = json.loads((d / "meta.json").read_text())
        words = json.loads((d / "words.json").read_text())
        dur = probe(d / "base.mp4")["duration"]
        a, b = _window(meta, words, dur)
        plan.append({"rank": rank, "clip": str(d), "id": f"{d.parent.parent.name}/{d.name}",
                     "in": round(a, 2), "out": round(b, 2), "hook": meta["hook"],
                     "credit": meta["credit"], "seam": meta.get("seam"),
                     "moment": meta["moment"]})
    top = json.loads((clip_dirs[0] / "words.json").read_text())
    if title is None:
        event = Hk.heard_event(top)
        title = f"{n} craziest GTA 6 stream moments" + (f" (#1 is {event})" if event else "")
    slug = slug or f"{date.today().isoformat()}-top{n}"
    out = page_dir / "countdowns" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps({"title": title, "segments": plan}, indent=2))
    return _render(out, plan, title)


def rebuild(out_dir, title=None):
    plan = json.loads((Path(out_dir) / "plan.json").read_text())
    if title is not None:
        plan["title"] = title
        (Path(out_dir) / "plan.json").write_text(json.dumps(plan, indent=2))
    return _render(Path(out_dir), plan["segments"], plan["title"])


def _render(out, plan, title):
    order = list(reversed(plan))  # #n first, #1 last
    vparts, aparts, events, t = [], [], [], 0.0
    for i, seg in enumerate(order):
        a, b = seg["in"], seg["out"]
        vparts.append(f"[{i}:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS,fps=30[v{i}]")
        aparts.append(f"[{i}:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.05,afade=t=out:st={b - a - 0.08:.3f}:d=0.08[a{i}]")
        words = json.loads((Path(seg["clip"]) / "words.json").read_text())
        shifted = [dict(w, start=w["start"] - a + t, end=min(w["end"], b) - a + t)
                   for w in words if a <= w["start"] < b]
        events += C.caption_events(shifted, seg.get("seam"))
        # The first number waits for the title card to clear.
        events.append(C.text_event(max(t, TITLE_SECONDS), t + (b - a), "Num", f"#{seg['rank']}",
                                   C.HOOK_Y, layer=3, fade_in=80, fade_out=0))
        if seg["credit"]:
            events.append(C.text_event(t, t + (b - a), "Credit", seg["credit"], C.CREDIT_Y,
                                       layer=0, fade_out=0))
        t += b - a
    events.append(C.text_event(0, min(TITLE_SECONDS, t), "Hook", title, C.HOOK_Y, layer=4))
    k = len(order)
    vgraph = ";".join(vparts) + ";" + "".join(f"[v{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0[v]"
    agraph = ";".join(aparts) + ";" + "".join(f"[a{i}]" for i in range(k)) + f"concat=n={k}:v=0:a=1[a]"
    ass = C.header() + "\n" + "\n".join(events) + "\n"
    final, lufs = master(out, [Path(s["clip"]) / "base.mp4" for s in order], vgraph, agraph, ass)
    meta_path = out / "meta.json"
    old = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta = {
        "kind": "countdown", "status": old.get("status", "draft"), "hook": title, "hooks": [],
        "credit": " · ".join(dict.fromkeys(s["credit"] for s in plan if s["credit"])),
        "sources": [{"id": s["id"], "credit": s["credit"], "vod_in": s["moment"]["vod_in"],
                     "vod_out": s["moment"]["vod_out"]} for s in plan],
        "moment": {"score": round(sum(s["moment"].get("score", 0) for s in plan), 1),
                   "reasons": [f"countdown of {k}"], "vod_in": "", "vod_out": "",
                   "transcript": " | ".join(f"#{s['rank']} {s['hook']}" for s in plan)},
        "layout": "countdown", "final": str(final), "duration": round(probe(final)["duration"], 2),
        "lufs": round(lufs, 1) if lufs is not None else None,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta
