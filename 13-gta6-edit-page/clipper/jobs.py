import json
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .sources import fetch_section, run_dir, source

PAD = 1.0


def default_jobs():
    return max(1, min(3, (os.cpu_count() or 2) // 2))


def _render_one(page, vod, moment, credit, model, layout, cam, cold_open, jumpcuts):
    from .pipeline import render_clip

    src = source(page, vod)
    clip_dir = run_dir(page, vod) / "clips" / moment["id"]
    clip_dir.mkdir(parents=True, exist_ok=True)
    path = src["path"]
    if not src.get("video", True):
        lo = max(0.0, moment["start"] - PAD)
        path = fetch_section(src, lo, moment["end"] + PAD, clip_dir / "section.mp4")
        moment = dict(moment, peak=moment["peak"] - lo, start=moment["start"] - lo,
                      end=moment["end"] - lo,
                      words=[dict(w, start=w["start"] - lo, end=w["end"] - lo)
                             for w in moment.get("words") or []] if moment.get("words") is not None else None)
    meta = render_clip(path, moment, clip_dir, credit=credit, model=model, layout=layout,
                       cam=cam, cold_open=cold_open, jumpcuts=jumpcuts)
    section = clip_dir / "section.mp4"
    if section.exists() and meta["status"] == "draft":
        section.unlink()
    return moment["id"], meta


def render_many(page, vod, moments, credit, model="base.en", layout="auto", cam=None,
                cold_open=True, jumpcuts=True, jobs=None):
    """Renders clips in parallel processes; yields (moment id, meta) as each finishes."""
    jobs = jobs or default_jobs()
    args = [(str(page), vod, m, credit, model, layout, cam, cold_open, jumpcuts) for m in moments]
    if jobs == 1 or len(args) <= 1:
        for a in args:
            yield _render_one(*a)
        return
    # spawn, not fork: the parent may already hold Whisper/OpenMP threads, and forking those deadlocks.
    with ProcessPoolExecutor(max_workers=jobs, mp_context=multiprocessing.get_context("spawn")) as pool:
        for result in pool.map(_render_one, *zip(*args)):
            yield result


def load_moments(page, vod):
    return json.loads((Path(page) / "runs" / vod / "moments.json").read_text())
