"""Local clipping pipeline for the GTA 6 edit page.

  fetch     download a VOD (or one section of it) into PAGE/runs/<vod>/
  scan      rank the moments in it -> runs/<vod>/moments.json
  render    turn moments into 1080x1920 drafts with captions -> runs/<vod>/clips/<id>/
  auto      fetch + scan + render the top N
  finalize  re-burn the hook / credit on one draft
  countdown join the best drafts into a "5 craziest moments" countdown
  studio    review page: watch, edit the hook, approve, mark posted
"""

import argparse
import json
import sys
from pathlib import Path

from clipper import moments as M
from clipper import sources as S
from clipper.media import require
from clipper.sources import run_dir, source

def fetch(page, url, section=None, streamer=None, audio_only=True):
    vod = S.fetch(page, url, section, streamer, audio_only=audio_only)
    print(f"{vod}: {S.source(page, vod)['path']}")
    return vod


def scan(page, vod, top=10, timestamps=None, model="base.en", threshold=6.0, chat=False):
    src = source(page, vod)
    stamps = M.read_timestamps(timestamps) if timestamps else []
    spikes = []
    if chat:
        from clipper import chat as C
        spikes = C.spikes(C.download(src["url"]))
        print(f"chat: {len(spikes)} spikes")
    found = M.find_moments(src["path"], top=top, timestamps=stamps, model=model,
                           threshold=threshold, offset=src.get("offset", 0.0), chat_spikes=spikes,
                           streamer=src.get("streamer", ""), heatmap=src.get("heatmap") or ())
    (run_dir(page, vod) / "moments.json").write_text(json.dumps(found, indent=2))
    for m in found:
        flag = f"  SKIP: {m['skip']}" if m["skip"] else ""
        print(f"{m['id']}  {m['vod_in']}-{m['vod_out']}  score {m['score']:>5}  "
              f"{'; '.join(m['reasons'])}  \"{m['hook']}\"{flag}")
    return found


def render(page, vod, ids=None, top=5, layout="auto", facecam=None, credit=None,
           model="base.en", cold_open=True, jumpcuts=True, jobs=None):
    from clipper.jobs import load_moments, render_many

    src = source(page, vod)
    found = load_moments(page, vod)
    chosen = [m for m in found if (m["id"] in ids if ids else not m["skip"])][: (None if ids else top)]
    if credit is None:
        who = src.get("streamer") or vod
        credit = f"{who} ({src['platform']})" if src.get("platform") else who
    cam = tuple(int(v) for v in facecam.split(",")) if facecam else None

    def run(moments, cam):
        out = {}
        for mid, meta in render_many(page, vod, moments, credit, model, layout, cam, cold_open,
                                     jumpcuts, jobs):
            extra = (f" -{meta.get('dead_air_cut', 0)}s dead air, {meta.get('lufs')} LUFS"
                     if meta["status"] == "draft" else "")
            print(f"{mid}: {meta['status']} {meta.get('layout', '')}{extra} "
                  f"{meta.get('final', meta.get('skip'))}")
            out[mid] = meta
        return out

    metas = run(chosen, cam)
    redo = shared_facecam(metas) if layout == "auto" and cam is None else None
    if redo:
        cam, mids = redo
        print(f"facecam {','.join(map(str, cam))} from the other clips; re-rendering "
              + " ".join(mids))
        metas.update(run([m for m in chosen if m["id"] in mids], cam))
    return list(metas.values())


def shared_facecam(metas):
    """A webcam sits in one place all stream, but on some moments detection misses it and the
    layout falls back to tracking a face, often a game character's. When most clips found the
    cam, returns (median box, ids of the clips that should be re-rendered with it)."""
    drafts = {mid: m for mid, m in metas.items() if m.get("status") == "draft"}
    stacked = [m["cam"] for m in drafts.values() if m.get("layout") == "stack" and m.get("cam")]
    others = [mid for mid, m in drafts.items() if m.get("layout") != "stack"]
    if not others or len(stacked) < 2 or len(stacked) < len(others):
        return None
    cam = []
    for i in range(4):
        vals = sorted(box[i] for box in stacked)
        mid = len(vals) // 2
        cam.append(vals[mid] if len(vals) % 2 else round((vals[mid - 1] + vals[mid]) / 2))
    return tuple(cam), others


def main(argv=None):
    p = argparse.ArgumentParser(prog="clip.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(s, render_opts=False):
        s.add_argument("--model", default="base.en", help="faster-whisper model (tiny.en .. large-v3)")
        if render_opts:
            s.add_argument("--top", type=int, default=5)
            s.add_argument("--layout", default="auto", choices=["auto", "stack", "track", "fit"])
            s.add_argument("--facecam", help="x,y,w,h of the facecam in the source (forces stack)")
            s.add_argument("--credit", help='default: "<uploader> (<platform>)"')
            s.add_argument("--no-cold-open", action="store_true")
            s.add_argument("--no-jumpcuts", action="store_true", help="keep dead air")
            s.add_argument("--jobs", type=int, help="clips rendered in parallel (default: cores/2, max 3)")

    s = sub.add_parser("fetch")
    s.add_argument("page")
    s.add_argument("url")
    s.add_argument("--section", help="HH:MM:SS-HH:MM:SS, download only this part")
    s.add_argument("--streamer")
    s.add_argument("--video", action="store_true", help="download the whole video, not audio-first")

    s = sub.add_parser("scan")
    s.add_argument("page")
    s.add_argument("vod")
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--timestamps", help="file of 'HH:MM:SS label' lines from VOD comments")
    s.add_argument("--threshold", type=float, default=6.0, help="dB over baseline for a peak")
    s.add_argument("--chat", action="store_true", help="use the chat replay as a signal")
    common(s)

    s = sub.add_parser("render")
    s.add_argument("page")
    s.add_argument("vod")
    s.add_argument("--ids", nargs="*")
    common(s, render_opts=True)

    s = sub.add_parser("auto")
    s.add_argument("page")
    s.add_argument("url")
    s.add_argument("--section")
    s.add_argument("--streamer")
    s.add_argument("--video", action="store_true", help="download the whole video, not audio-first")
    s.add_argument("--timestamps")
    s.add_argument("--threshold", type=float, default=6.0)
    s.add_argument("--chat", action="store_true", help="use the chat replay as a signal")
    common(s, render_opts=True)

    s = sub.add_parser("finalize")
    s.add_argument("page")
    s.add_argument("clip", help="<vod>/<moment id>, e.g. VZqkMbVwvqQ/m01")
    s.add_argument("--hook")
    s.add_argument("--credit")

    s = sub.add_parser("countdown")
    s.add_argument("page")
    s.add_argument("--clips", nargs="*", help="<vod>/<id> best first; default: top drafts by score")
    s.add_argument("-n", type=int, default=5)
    s.add_argument("--title")
    s.add_argument("--slug")

    s = sub.add_parser("studio")
    s.add_argument("page")
    s.add_argument("--port", type=int, default=8765)

    a = p.parse_args(argv)
    for tool in ("ffmpeg", "ffprobe"):
        require(tool)
    layout = getattr(a, "layout", "auto")
    if getattr(a, "facecam", None):
        layout = "stack"

    if a.cmd == "fetch":
        fetch(a.page, a.url, a.section, a.streamer, not a.video)
    elif a.cmd == "scan":
        scan(a.page, a.vod, a.top, a.timestamps, a.model, a.threshold, a.chat)
    elif a.cmd == "render":
        render(a.page, a.vod, a.ids, a.top, layout, a.facecam, a.credit, a.model,
               not a.no_cold_open, not a.no_jumpcuts, a.jobs)
    elif a.cmd == "auto":
        streamer = a.streamer or (a.credit.split(" (")[0] if a.credit else None)
        vod = fetch(a.page, a.url, a.section, streamer, not a.video)
        scan(a.page, vod, max(10, a.top * 2), a.timestamps, a.model, a.threshold, a.chat)
        render(a.page, vod, None, a.top, layout, a.facecam, a.credit, a.model,
               not a.no_cold_open, not a.no_jumpcuts, a.jobs)
        print(f"\nreview: python3 clip.py studio {a.page}")
    elif a.cmd == "finalize":
        from clipper.pipeline import finalize
        vod, mid = a.clip.split("/")
        meta = finalize(Path(a.page) / "runs" / vod / "clips" / mid, a.hook, a.credit)
        print(meta["final"])
    elif a.cmd == "countdown":
        from clipper.countdown import build, pick
        dirs = ([Path(a.page) / "runs" / c.split("/")[0] / "clips" / c.split("/")[1] for c in a.clips]
                if a.clips else pick(a.page, a.n))
        meta = build(a.page, dirs, a.title, a.slug)
        print(f"{meta['final']}  {meta['duration']}s  {meta['lufs']} LUFS  \"{meta['hook']}\"")
    elif a.cmd == "studio":
        from clipper.studio import serve
        serve(a.page, a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
