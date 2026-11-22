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
from datetime import date
from pathlib import Path

from clipper import moments as M
from clipper.media import require

PLATFORM_NAMES = {"youtube": "YouTube", "twitch": "Twitch", "kick": "Kick", "twitter": "X"}


def run_dir(page, vod):
    path = Path(page) / "runs" / vod
    path.mkdir(parents=True, exist_ok=True)
    return path


def fetch(page, url, section=None, streamer=None):
    """Returns the vod id. A local file is registered in place instead of downloaded."""
    local = Path(url)
    if local.exists():
        vod = local.stem
        meta = {"url": str(local.resolve()), "path": str(local.resolve()), "id": vod,
                "streamer": streamer or "", "platform": "", "offset": 0.0}
    else:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import download_range_func

        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        vod = info["id"]
        out = run_dir(page, vod)
        opts = {"format": "bv*[height<=1080]+ba/b[height<=1080]/b", "quiet": True,
                "outtmpl": str(out / "source.%(ext)s"), "merge_output_format": "mp4"}
        offset = 0.0
        if section:
            a, b = (M.parse_ts(x) for x in section.split("-"))
            opts.update(download_ranges=download_range_func(None, [(a, b)]),
                        force_keyframes_at_cuts=True)
            offset = a
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        path = next(out.glob("source.*"))
        meta = {"url": info.get("webpage_url", url), "path": str(path), "id": vod,
                "title": info.get("title", ""),
                "streamer": streamer or info.get("uploader") or info.get("channel") or "",
                "platform": PLATFORM_NAMES.get(info.get("extractor_key", "").lower(),
                                               info.get("extractor_key", "")),
                "offset": offset}
    meta["fetched_on"] = date.today().isoformat()
    (run_dir(page, vod) / "source.json").write_text(json.dumps(meta, indent=2))
    print(f"{vod}: {meta['path']}")
    return vod


def source(page, vod):
    return json.loads((Path(page) / "runs" / vod / "source.json").read_text())


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
                           streamer=src.get("streamer", ""))
    (run_dir(page, vod) / "moments.json").write_text(json.dumps(found, indent=2))
    for m in found:
        flag = f"  SKIP: {m['skip']}" if m["skip"] else ""
        print(f"{m['id']}  {m['vod_in']}-{m['vod_out']}  score {m['score']:>5}  "
              f"{'; '.join(m['reasons'])}  \"{m['hook']}\"{flag}")
    return found


def render(page, vod, ids=None, top=5, layout="auto", facecam=None, credit=None,
           model="base.en", cold_open=True, jumpcuts=True):
    from clipper.pipeline import render_clip

    src = source(page, vod)
    found = json.loads((run_dir(page, vod) / "moments.json").read_text())
    chosen = [m for m in found if (m["id"] in ids if ids else not m["skip"])][: (None if ids else top)]
    if credit is None:
        who = src.get("streamer") or vod
        credit = f"{who} ({src['platform']})" if src.get("platform") else who
    cam = tuple(int(v) for v in facecam.split(",")) if facecam else None
    for m in chosen:
        meta = render_clip(src["path"], m, run_dir(page, vod) / "clips" / m["id"], credit=credit,
                           model=model, layout=layout, cam=cam, cold_open=cold_open,
                           jumpcuts=jumpcuts)
        extra = (f" -{meta.get('dead_air_cut', 0)}s dead air, {meta.get('lufs')} LUFS"
                 if meta["status"] == "draft" else "")
        print(f"{m['id']}: {meta['status']} {meta.get('layout', '')}{extra} "
              f"{meta.get('final', meta.get('skip'))}")


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

    s = sub.add_parser("fetch")
    s.add_argument("page")
    s.add_argument("url")
    s.add_argument("--section", help="HH:MM:SS-HH:MM:SS, download only this part")
    s.add_argument("--streamer")

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
        fetch(a.page, a.url, a.section, a.streamer)
    elif a.cmd == "scan":
        scan(a.page, a.vod, a.top, a.timestamps, a.model, a.threshold, a.chat)
    elif a.cmd == "render":
        render(a.page, a.vod, a.ids, a.top, layout, a.facecam, a.credit, a.model,
               not a.no_cold_open, not a.no_jumpcuts)
    elif a.cmd == "auto":
        streamer = a.streamer or (a.credit.split(" (")[0] if a.credit else None)
        vod = fetch(a.page, a.url, a.section, streamer)
        scan(a.page, vod, max(10, a.top * 2), a.timestamps, a.model, a.threshold, a.chat)
        render(a.page, vod, None, a.top, layout, a.facecam, a.credit, a.model,
               not a.no_cold_open, not a.no_jumpcuts)
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
