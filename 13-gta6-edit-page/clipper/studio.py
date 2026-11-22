"""Clip Studio: a local review page for drafts. Nothing is exported or logged without a click."""

import csv
import json
import os
import shutil
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import page as pagekit  # noqa: E402

from .pipeline import finalize  # noqa: E402

HASHTAGS = {"tiktok": "#gta6 #gta6clips", "youtube": "#gta6 #shorts",
            "instagram": "#gta6 #gta6clips", "x": ""}


def hashtags(platform, credit):
    """2 to 4 tags (SETUP_PROMPT section 7), one per credited streamer; none on X."""
    base = HASHTAGS[platform]
    if not base:
        return ""
    names = [c.split(" (")[0] for c in credit.split(" · ") if c]
    tags = base.split() + ["#" + "".join(ch for ch in n.lower() if ch.isalnum()) for n in names]
    return " ".join(list(dict.fromkeys(tags))[:4])


def clip_path(page_dir, clip_id):
    """'<vod>/<moment>' -> runs/<vod>/clips/<moment>; 'countdown/<slug>' -> countdowns/<slug>."""
    root = Path(page_dir).resolve()
    kind, _, name = clip_id.partition("/")
    path = (root / "countdowns" / name if kind == "countdown"
            else root / "runs" / kind / "clips" / name).resolve()
    if root not in path.parents or not name:
        raise ValueError("bad clip id")
    return path


def clips(page_dir):
    out = []
    root = Path(page_dir)
    metas = [(p, f"{p.parent.parent.parent.name}/{p.parent.name}")
             for p in root.glob("runs/*/clips/*/meta.json")]
    metas += [(p, f"countdown/{p.parent.name}") for p in root.glob("countdowns/*/meta.json")]
    for meta_path, cid in metas:
        meta = json.loads(meta_path.read_text())
        meta["moment"] = {k: v for k, v in meta["moment"].items() if k != "words"}
        meta.update(id=cid, vod=cid.split("/")[0])
        out.append(meta)
    out.sort(key=lambda m: ({"draft": 0, "approved": 1, "scheduled": 2, "posted": 3}.get(m["status"], 4),
                            m.get("kind") != "countdown", -m["moment"].get("score", 0)))
    return out


def _source(page_dir, vod):
    path = Path(page_dir, "runs", vod, "source.json")
    return json.loads(path.read_text()) if path.exists() else {}


def approve(page_dir, clip_id, slug):
    page_dir = Path(page_dir)
    clip_dir = clip_path(page_dir, clip_id)
    meta = json.loads((clip_dir / "meta.json").read_text())
    vod = clip_id.split("/")[0]
    src = _source(page_dir, vod)
    if meta.get("kind") == "countdown":
        streamer = "countdown"
    else:
        streamer = src.get("streamer") or (meta["credit"].split(" (")[0] if meta["credit"] else vod)
    post_slug = pagekit.slugify(slug)
    name = pagekit.export_name(date.today().isoformat(), streamer, post_slug)
    n = 2
    while (page_dir / "exports" / name).exists() and meta.get("export") != name:
        post_slug = f"{pagekit.slugify(slug)}-{n}"
        name = pagekit.export_name(date.today().isoformat(), streamer, post_slug)
        n += 1
    shutil.copy(clip_dir / "final.mp4", page_dir / "exports" / name)
    sources = meta.get("sources") or [{"id": clip_id, "credit": meta["credit"],
                                       "vod_in": meta["moment"]["vod_in"],
                                       "vod_out": meta["moment"]["vod_out"]}]
    lines = [f"# {post_slug}", "", f"Export: exports/{name}",
             *(f"Source: {_source(page_dir, s['id'].split('/')[0]).get('url', s['id'])} "
               f"{s['vod_in']}-{s['vod_out']} {s['credit']}" for s in sources),
             "Campaign: none  (if paid: \"#ad\" first and the platform label on)", ""]
    for platform, label in (("tiktok", "TikTok"), ("youtube", "YouTube Shorts"),
                            ("instagram", "Instagram Reels"), ("x", "X")):
        lines += [f"## {label}", meta["hook"], meta["credit"]]
        if hashtags(platform, meta["credit"]):
            lines.append(hashtags(platform, meta["credit"]))
        lines.append("")
    (page_dir / "posts" / f"{post_slug}.md").write_text("\n".join(lines))
    with open(page_dir / "provenance.csv", "a", newline="") as f:
        for s in sources:
            s_src = _source(page_dir, s["id"].split("/")[0])
            csv.writer(f).writerow([s_src.get("url", s["id"]), s["credit"].split(" (")[0],
                                    s_src.get("platform", ""), s["vod_in"], s["vod_out"],
                                    date.today().isoformat(), s["credit"], name])
    meta.update(status="approved", export=name, slug=post_slug)
    _save(clip_dir, meta)
    return meta


def queue_post(page_dir, clip_id):
    """Schedule now when Upload-Post is configured, else leave it for the next desk tick."""
    clip_dir = clip_path(page_dir, clip_id)
    meta = json.loads((clip_dir / "meta.json").read_text())
    meta["queue"] = True
    _save(clip_dir, meta)
    if os.environ.get("UPLOAD_POST_API_KEY"):
        from .publish import schedule
        schedule(page_dir, clip_id)
        meta = json.loads((clip_dir / "meta.json").read_text())
    return meta


def mark_posted(page_dir, clip_id, platform, fmt="single", when=None):
    clip_dir = clip_path(page_dir, clip_id)
    meta = json.loads((clip_dir / "meta.json").read_text())
    vod = clip_id.split("/")[0]
    m = meta["moment"]
    if meta.get("kind") == "countdown":
        fmt = "countdown"
    post_id = pagekit.log_post(page_dir, {
        "date": when or datetime.now().strftime("%Y-%m-%dT%H:%M"), "platform": platform,
        "format": fmt, "streamer": meta["credit"].split(" (")[0], "vod_id": vod,
        "in_out": f"{m['vod_in']}-{m['vod_out']}" if m["vod_in"] else "", "hook": meta["hook"],
        "cold_open": "peak" if meta.get("cold_open") else "", "length_sec": str(meta.get("duration", "")),
        "notes": f"clipper {meta.get('layout', '')}"})
    meta.setdefault("posts", []).append({"platform": platform, "post_id": post_id})
    meta["status"] = "posted"
    _save(clip_dir, meta)
    return post_id


def _save(clip_dir, meta):
    meta = {k: v for k, v in meta.items() if k not in ("id", "vod")}
    (Path(clip_dir) / "meta.json").write_text(json.dumps(meta, indent=2))


PAGE = """<!doctype html><meta charset=utf-8><title>Clip Studio</title>
<style>
body{margin:0;background:#120a24;color:#eee;font:15px system-ui,sans-serif}
header{padding:18px 28px;background:linear-gradient(90deg,#3b0d6e,#7a1fa2);font-weight:800;font-size:22px;letter-spacing:.5px}
header small{font-weight:400;opacity:.75;font-size:14px;margin-left:12px}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:20px;padding:24px}
.card{background:#1d1238;border:1px solid #3a2766;border-radius:14px;padding:14px}
.card.skipped,.card.rejected{opacity:.45}
video{width:100%;aspect-ratio:9/16;background:#000;border-radius:10px}
.tag{display:inline-block;padding:2px 8px;border-radius:99px;background:#3a2766;margin:2px 4px 2px 0;font-size:12px}
.chip{cursor:pointer;border:1px dashed #ffe500}
.status{float:right;font-weight:700;text-transform:uppercase;font-size:12px;color:#ffe500}
input,select{width:100%;box-sizing:border-box;margin:4px 0;padding:8px;border-radius:8px;border:1px solid #4a3680;background:#120a24;color:#eee}
button{padding:8px 12px;margin:4px 4px 0 0;border:0;border-radius:8px;font-weight:700;cursor:pointer;background:#4a3680;color:#fff}
button.go{background:#ffe500;color:#120a24}
p.t{font-size:13px;opacity:.75;max-height:5.5em;overflow:auto}
</style>
<header>CLIP STUDIO<small>GTA 6 edit desk: watch, fix the hook, approve, post, log</small>
<button id=cd style="float:right">Build top-5 countdown</button></header>
<main id=m></main>
<script>
const post=(u,b)=>fetch(u,{method:'POST',body:JSON.stringify(b)}).then(r=>r.json()).then(r=>{if(r.error)alert(r.error);load()});
function card(c){const m=c.moment,d=document.createElement('div');d.className='card '+c.status;
d.innerHTML=`<span class=status>${c.status}</span><b>${c.id}</b> ${m.vod_in?m.vod_in+'-'+m.vod_out:''}<br>
${(m.reasons||[]).map(r=>`<span class=tag>${r}</span>`).join('')}${c.layout?`<span class=tag>${c.layout}</span>`:''}
${c.dead_air_cut?`<span class=tag>-${c.dead_air_cut}s dead air</span>`:''}${c.lufs!=null?`<span class=tag>${c.lufs} LUFS</span>`:''}
${c.skip?`<p style=color:#f66>skip: ${c.skip}</p>`:''}
${c.final?`<video controls preload=metadata poster="/file?p=${encodeURIComponent(c.final.replace(/final\\.mp4$/,'poster.jpg'))}&v=${Date.now()}" src="/file?p=${encodeURIComponent(c.final)}"></video>`:''}
<p class=t>${m.transcript||''}</p>
<label>${c.kind=='countdown'?'Title':'Hook (6 words max)'}<input class=h value="${(c.hook||'').replace(/"/g,'&quot;')}"></label>
<div>${(c.hooks||[]).map(h=>`<span class="tag chip">${h}</span>`).join('')}</div>
<label>Credit<input class=c value="${(c.credit||'').replace(/"/g,'&quot;')}"></label>
<button class=rb>Re-render text</button><button class=ap>Approve</button><button class="go apq">Approve &amp; post</button><button class=rj>Reject</button>
<div style=margin-top:8px><select class=pf><option>tiktok<option>youtube<option>instagram<option>x</select>
<select class=fm><option>single<option>story<option>countdown<option>reaction<option>explainer<option>ranking</select>
<button class=ps>Mark posted</button> ${(c.posts||[]).map(p=>`<span class=tag>${p.platform} ${p.post_id}</span>`).join('')}</div>`;
const q=s=>d.querySelector(s);
d.querySelectorAll('.chip').forEach(ch=>ch.onclick=()=>{q('.h').value=ch.textContent});
q('.rb').onclick=()=>post('/api/finalize',{id:c.id,hook:q('.h').value,credit:q('.c').value});
const approve=queue=>post('/api/approve',{id:c.id,hook:q('.h').value,credit:q('.c').value,queue});
q('.ap').onclick=()=>approve(false);q('.apq').onclick=()=>approve(true);
q('.rj').onclick=()=>post('/api/status',{id:c.id,status:'rejected'});
q('.ps').onclick=()=>post('/api/posted',{id:c.id,platform:q('.pf').value,format:q('.fm').value});
return d}
function load(){fetch('/api/clips').then(r=>r.json()).then(cs=>{const m=document.getElementById('m');m.innerHTML='';
if(!cs.length)m.textContent='No drafts yet. Run: python3 clip.py auto PAGE_DIR VOD_URL';cs.forEach(c=>m.appendChild(card(c)))})}
document.getElementById('cd').onclick=e=>{e.target.disabled=true;e.target.textContent='Rendering...';
fetch('/api/countdown',{method:'POST',body:'{}'}).then(r=>r.json()).then(r=>{if(r.error)alert(r.error);
e.target.disabled=false;e.target.textContent='Build top-5 countdown';load()})};
load();
</script>"""


def make_handler(page_dir):
    root = Path(page_dir).resolve()

    def clip_dir(clip_id):
        return clip_path(root, clip_id)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/clips":
                self._json(clips(root))
            elif url.path == "/file":
                self._file(Path(parse_qs(url.query).get("p", [""])[0]).resolve())
            else:
                self.send_error(404)

        def _file(self, path):
            if root not in path.parents or not path.is_file():
                return self.send_error(404)
            size = path.stat().st_size
            start, end = 0, size - 1
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                a, _, b = rng[6:].partition("-")
                start = int(a) if a else max(0, size - int(b))
                end = int(b) if a and b else end
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", "video/mp4" if path.suffix == ".mp4" else "image/jpeg")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    left -= len(chunk)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            try:
                if self.path == "/api/countdown":
                    from .countdown import build, pick
                    return self._json(build(root, pick(root, body.get("n", 5))))
                cid = body["id"]
                path = clip_dir(cid)
                if self.path == "/api/finalize":
                    self._json(finalize(path, hook=body.get("hook"), credit=body.get("credit")))
                elif self.path == "/api/approve":
                    meta = json.loads((path / "meta.json").read_text())
                    if meta["status"] not in ("approved", "scheduled"):
                        hook, credit = body.get("hook", meta["hook"]), body.get("credit", meta["credit"])
                        if (hook, credit) != (meta["hook"], meta["credit"]):
                            finalize(path, hook=hook, credit=credit)
                        meta = approve(root, cid, body.get("slug") or hook)
                    if body.get("queue") and meta["status"] == "approved":
                        meta = queue_post(root, cid)
                    self._json(meta)
                elif self.path == "/api/posted":
                    self._json({"post_id": mark_posted(root, cid, body["platform"],
                                                       body.get("format", "single"))})
                elif self.path == "/api/status":
                    meta = json.loads((path / "meta.json").read_text())
                    meta["status"] = body["status"]
                    _save(path, meta)
                    self._json(meta)
                else:
                    self.send_error(404)
            except Exception as exc:  # surfaced in the page as an alert
                self._json({"error": str(exc)}, 400)

    return Handler


def serve(page_dir, port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(page_dir))
    print(f"Clip Studio on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    server.serve_forever()
