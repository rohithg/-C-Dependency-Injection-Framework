"""Clip Studio: a local review page for drafts. Nothing is exported or logged without a click."""

import csv
import json
import shutil
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import page as pagekit  # noqa: E402

from .pipeline import finalize  # noqa: E402

HASHTAGS = {"tiktok": "#gta6 #gta6clips #kaicenat", "youtube": "#gta6 #shorts",
            "instagram": "#gta6 #gta6clips", "x": ""}


def clips(page_dir):
    out = []
    for meta_path in sorted(Path(page_dir, "runs").glob("*/clips/*/meta.json")):
        meta = json.loads(meta_path.read_text())
        clip_dir = meta_path.parent
        vod = clip_dir.parent.parent.name
        meta.update(id=f"{vod}/{clip_dir.name}", vod=vod)
        out.append(meta)
    out.sort(key=lambda m: ({"draft": 0, "approved": 1, "posted": 2}.get(m["status"], 3),
                            -m["moment"].get("score", 0)))
    return out


def _source(page_dir, vod):
    path = Path(page_dir, "runs", vod, "source.json")
    return json.loads(path.read_text()) if path.exists() else {}


def approve(page_dir, clip_id, slug):
    page_dir = Path(page_dir)
    clip_dir = page_dir / "runs" / clip_id.replace("..", "").replace("/", "/clips/", 1)
    meta = json.loads((clip_dir / "meta.json").read_text())
    vod = clip_id.split("/")[0]
    src = _source(page_dir, vod)
    streamer = src.get("streamer") or (meta["credit"].split(" (")[0] if meta["credit"] else vod)
    name = pagekit.export_name(date.today().isoformat(), streamer, slug)
    shutil.copy(clip_dir / "final.mp4", page_dir / "exports" / name)
    post_slug = pagekit.slugify(slug)
    lines = [f"# {post_slug}", "", f"Export: exports/{name}",
             f"Source: {src.get('url', vod)} {meta['moment']['vod_in']}-{meta['moment']['vod_out']}",
             "Campaign: none  (if paid: \"#ad\" first and the platform label on)", ""]
    for platform, label in (("tiktok", "TikTok"), ("youtube", "YouTube Shorts"),
                            ("instagram", "Instagram Reels"), ("x", "X")):
        lines += [f"## {label}", meta["hook"], meta["credit"]]
        if HASHTAGS[platform]:
            lines.append(HASHTAGS[platform])
        lines.append("")
    (page_dir / "posts" / f"{post_slug}.md").write_text("\n".join(lines))
    with open(page_dir / "provenance.csv", "a", newline="") as f:
        csv.writer(f).writerow([src.get("url", vod), streamer, src.get("platform", ""),
                                meta["moment"]["vod_in"], meta["moment"]["vod_out"],
                                date.today().isoformat(), meta["credit"], name])
    meta.update(status="approved", export=name, slug=post_slug)
    _save(clip_dir, meta)
    return meta


def mark_posted(page_dir, clip_id, platform, fmt="single", when=None):
    clip_dir = Path(page_dir) / "runs" / clip_id.replace("/", "/clips/", 1)
    meta = json.loads((clip_dir / "meta.json").read_text())
    vod = clip_id.split("/")[0]
    m = meta["moment"]
    post_id = pagekit.log_post(page_dir, {
        "date": when or datetime.now().strftime("%Y-%m-%dT%H:%M"), "platform": platform,
        "format": fmt, "streamer": meta["credit"].split(" (")[0], "vod_id": vod,
        "in_out": f"{m['vod_in']}-{m['vod_out']}", "hook": meta["hook"],
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
.status{float:right;font-weight:700;text-transform:uppercase;font-size:12px;color:#ffe500}
input,select{width:100%;box-sizing:border-box;margin:4px 0;padding:8px;border-radius:8px;border:1px solid #4a3680;background:#120a24;color:#eee}
button{padding:8px 12px;margin:4px 4px 0 0;border:0;border-radius:8px;font-weight:700;cursor:pointer;background:#4a3680;color:#fff}
button.go{background:#ffe500;color:#120a24}
p.t{font-size:13px;opacity:.75;max-height:5.5em;overflow:auto}
</style>
<header>CLIP STUDIO<small>GTA 6 edit desk: watch, fix the hook, approve, post, log</small></header>
<main id=m></main>
<script>
const post=(u,b)=>fetch(u,{method:'POST',body:JSON.stringify(b)}).then(r=>r.json()).then(r=>{if(r.error)alert(r.error);load()});
function card(c){const m=c.moment,d=document.createElement('div');d.className='card '+c.status;
d.innerHTML=`<span class=status>${c.status}</span><b>${c.id}</b> ${m.vod_in}-${m.vod_out}<br>
${(m.reasons||[]).map(r=>`<span class=tag>${r}</span>`).join('')}${c.layout?`<span class=tag>${c.layout}</span>`:''}
${c.skip?`<p style=color:#f66>skip: ${c.skip}</p>`:''}
${c.final?`<video controls preload=metadata poster="/file?p=${encodeURIComponent(c.final.replace(/final\\.mp4$/,'poster.jpg'))}&v=${Date.now()}" src="/file?p=${encodeURIComponent(c.final)}"></video>`:''}
<p class=t>${m.transcript||''}</p>
<label>Hook (6 words max)<input class=h value="${(c.hook||'').replace(/"/g,'&quot;')}"></label>
<label>Credit<input class=c value="${(c.credit||'').replace(/"/g,'&quot;')}"></label>
<button class=rb>Re-render text</button><button class="go ap">Approve</button><button class=rj>Reject</button>
<div style=margin-top:8px><select class=pf><option>tiktok<option>youtube<option>instagram<option>x</select>
<select class=fm><option>single<option>story<option>countdown<option>reaction<option>explainer<option>ranking</select>
<button class=ps>Mark posted</button> ${(c.posts||[]).map(p=>`<span class=tag>${p.platform} ${p.post_id}</span>`).join('')}</div>`;
const q=s=>d.querySelector(s);
q('.rb').onclick=()=>post('/api/finalize',{id:c.id,hook:q('.h').value,credit:q('.c').value});
q('.ap').onclick=()=>{const s=prompt('Slug for the export name',q('.h').value);if(s)post('/api/approve',{id:c.id,slug:s})};
q('.rj').onclick=()=>post('/api/status',{id:c.id,status:'rejected'});
q('.ps').onclick=()=>post('/api/posted',{id:c.id,platform:q('.pf').value,format:q('.fm').value});
return d}
function load(){fetch('/api/clips').then(r=>r.json()).then(cs=>{const m=document.getElementById('m');m.innerHTML='';
if(!cs.length)m.textContent='No drafts yet. Run: python3 clip.py auto PAGE_DIR VOD_URL';cs.forEach(c=>m.appendChild(card(c)))})}
load();
</script>"""


def make_handler(page_dir):
    root = Path(page_dir).resolve()

    def clip_dir(clip_id):
        path = (root / "runs" / clip_id.replace("/", "/clips/", 1)).resolve()
        if root not in path.parents:
            raise ValueError("bad clip id")
        return path

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
                cid = body["id"]
                path = clip_dir(cid)
                if self.path == "/api/finalize":
                    self._json(finalize(path, hook=body.get("hook"), credit=body.get("credit")))
                elif self.path == "/api/approve":
                    self._json(approve(root, cid, body["slug"]))
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
