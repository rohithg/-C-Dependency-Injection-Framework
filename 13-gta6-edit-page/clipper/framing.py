"""Turn a 16:9 cut into a 1080x1920 base clip (no captions yet).

Layouts, picked per clip from face detections unless forced:
  stack  small steady face (a streamer's facecam overlay): facecam on top, gameplay below
  track  big face that moves (IRL / camera footage): a 9:16 window that follows the face
  fit    no face: gameplay full width over a blurred copy of itself
"""

import subprocess
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from .media import encoder_args, probe

W, H = 1080, 1920
CAM_MAX = 768


YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")
YUNET = Path.home() / ".cache" / "clipper" / "yunet.onnx"


def _yunet_model():
    if not YUNET.exists():
        YUNET.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(YUNET_URL, YUNET)
    return str(YUNET)


def detect_faces(src, every=0.25, width=640, min_score=0.8):
    """[(t, (x, y, w, h) or None)] in source pixels, sampled every `every` seconds."""
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(fps * every)))
    det = None
    out, idx = [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            scale = width / frame.shape[1]
            small = cv2.resize(frame, None, fx=scale, fy=scale)
            if det is None:
                det = cv2.FaceDetectorYN.create(_yunet_model(), "", (small.shape[1], small.shape[0]),
                                                min_score, 0.3, 50)
            _, found = det.detect(small)
            boxes = [] if found is None else [f[:4] for f in found]
            best = max(boxes, key=lambda b: b[2] * b[3], default=None)
            out.append((idx / fps, tuple(int(v / scale) for v in best) if best is not None else None))
        idx += 1
    cap.release()
    return out


def motion_map(src, samples=40, width=640):
    """Per-pixel std of brightness over the clip, at `width` px. Gameplay moves, a facecam's room doesn't."""
    cap = cv2.VideoCapture(str(src))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    frames, scale = [], 1.0
    for i in np.linspace(0, total - 1, min(samples, total)).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = cap.read()
        if not ok:
            continue
        scale = width / frame.shape[1]
        frames.append(cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale),
                                   cv2.COLOR_BGR2GRAY).astype(np.float32))
    cap.release()
    if len(frames) < 3:
        return None, scale
    return np.std(np.stack(frames), axis=0), scale


def refine_cam(guess, face, motion, scale, band=4):
    """Snap each side of the guessed facecam box to where still pixels meet moving gameplay."""
    if motion is None:
        return guess
    mh, mw = motion.shape
    gx, gy, gw, gh = (v * scale for v in guess)
    fx, fy, fw, fh = (v * scale for v in face)
    thr = max(4.0, 0.35 * float(np.percentile(motion, 90)))
    cols = slice(int(max(0, fx - fw * 0.5)), int(min(mw, fx + fw * 1.5)))
    rows = slice(int(max(0, fy - fh * 0.3)), int(min(mh, fy + fh * 1.3)))

    def best(lo, hi, limit, contrast):
        lo, hi = int(max(band, lo)), int(min(hi, limit - band))
        score, i = max(((contrast(i), i) for i in range(lo, hi)), default=(0, None))
        return i if score > thr else None

    def row(y, sign=1):
        return sign * (motion[y - band:y, cols].mean() - motion[y:y + band, cols].mean())

    def col(x, sign=1):
        return sign * (motion[rows, x - band:x].mean() - motion[rows, x:x + band].mean())

    top = best(fy - fh * 1.6, fy - fh * 0.05, mh, row)
    bottom = best(fy + fh * 1.3, fy + fh * 3.0, mh, lambda y: row(y, -1))
    left = best(fx - fw * 2.0, fx - fw * 0.05, mw, col)
    right = best(fx + fw * 1.05, fx + fw * 3.0, mw, lambda x: col(x, -1))
    x0 = left if left is not None else gx
    y0 = top if top is not None else gy
    x1 = right if right is not None else gx + gw
    y1 = bottom if bottom is not None else gy + gh
    return tuple(int(round(v / scale)) // 2 * 2 for v in (x0, y0, x1 - x0, y1 - y0))


def choose_layout(faces, frame_w, frame_h, motion=None, scale=1.0):
    hits = [b for _, b in faces if b]
    if len(hits) < max(3, 0.35 * len(faces)):
        return "fit", None
    cx = np.array([x + w / 2 for x, y, w, h in hits])
    cy = np.array([y + h / 2 for x, y, w, h in hits])
    size = np.median([h for *_, h in hits])
    steady = cx.std() < 0.04 * frame_w and cy.std() < 0.04 * frame_h
    if size < 0.2 * frame_h and steady:
        face = tuple(float(np.median([b[i] for b in hits])) for i in range(4))
        fw = face[2]
        bw, bh = fw * 3.2, fw * 2.4
        x = int(np.clip(np.median(cx) - bw / 2, 0, frame_w - bw))
        y = int(np.clip(np.median(cy) - bh / 2.4, 0, frame_h - bh))
        cam = refine_cam((x, y, bw, bh), face, motion, scale)
        return "stack", cam
    return "track", None


def track_path(faces, duration, fps, frame_w, frame_h, crop_w):
    """Per-output-frame crop x: follow the face with a dead zone and smoothing."""
    n = int(round(duration * fps))
    times = np.arange(n) / fps
    pts = [(t, b[0] + b[2] / 2) for t, b in faces if b]
    if not pts:
        return np.full(n, (frame_w - crop_w) / 2)
    raw = np.interp(times, [p[0] for p in pts], [p[1] for p in pts])
    xs, cur = np.empty(n), raw[0]
    dead = 0.08 * crop_w
    for i, target in enumerate(raw):
        if abs(target - cur) > dead:
            cur += (target - cur - np.sign(target - cur) * dead) * 0.08
        xs[i] = cur
    return np.clip(xs - crop_w / 2, 0, frame_w - crop_w)


def punch(peak, w, h, length=1.5, amount=0.12):
    """zoompan filter (input already at 30 fps) that punches in on the peak, fixed output size."""
    if peak is None:
        return "null"
    z = f"if(between(in/30,{peak:.2f},{peak + length:.2f}),{1 + amount},1)"
    return f"zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps=30"


def filter_for(layout, cam, src_w, src_h, peak):
    if layout == "stack":
        x, y, w, h = cam
        cam_h = min(CAM_MAX, round(W * h / w / 2) * 2)
        game_h = H - cam_h
        return (f"[0:v]fps=30,split[c][g];"
                f"[c]crop={w}:{h}:{x}:{y},scale={W}:{cam_h}:force_original_aspect_ratio=increase,"
                f"crop={W}:{cam_h},setsar=1[cam];"
                f"[g]scale=-2:{game_h},crop={W}:{game_h},{punch(peak, W, game_h)},setsar=1[game];"
                f"[cam][game]vstack=inputs=2[v]"), cam_h
    if layout == "fit":
        fg_w = W * 135 // 100 // 2 * 2
        fg_h = fg_w * src_h // src_w // 2 * 2
        return (f"[0:v]fps=30,split[a][b];"
                f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur=24:2,eq=brightness=-0.08[bg];"
                f"[b]scale={fg_w}:{fg_h},crop={W}:{fg_h},{punch(peak, W, fg_h)},setsar=1[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"), None
    raise ValueError(layout)


def render_base(src, out, layout="auto", cam=None, peak=None, audio_filter="anull"):
    """Writes the 1080x1920 30 fps base clip. Returns layout info for captions."""
    info = probe(src)
    sw, sh = info["width"], info["height"]
    faces = []
    if layout == "auto" or layout == "track":
        faces = detect_faces(src)
    if layout == "auto":
        motion, scale = motion_map(src)
        layout, cam = choose_layout(faces, sw, sh, motion, scale)
    elif layout == "stack" and not cam:
        raise ValueError("stack layout needs a facecam rect")

    if layout == "track":
        _render_track(src, out, faces, info, peak, audio_filter)
        return {"layout": layout, "cam": None, "seam": None}

    vf, cam_h = filter_for(layout, cam, sw, sh, peak)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
                    "-filter_complex", f"{vf};[0:a]{audio_filter}[a]", "-map", "[v]", "-map", "[a]",
                    *encoder_args(final=False), "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return {"layout": layout, "cam": list(cam) if cam else None, "seam": cam_h}


def _render_track(src, out, faces, info, peak, audio_filter):
    sw, sh, fps = info["width"], info["height"], 30.0
    crop_w = min(sw, int(sh * W / H))
    xs = track_path(faces, info["duration"], fps, sw, sh, crop_w)
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
         "-i", str(src), "-filter_complex", f"[1:a]{audio_filter}[a]", "-map", "0:v", "-map", "[a]",
         *encoder_args(final=False), "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)],
        stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(str(src))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or fps
    frame, src_idx = None, -1
    for i, x in enumerate(xs):
        want = int(i / fps * src_fps)
        while src_idx < want:
            ok, nxt = cap.read()
            if not ok:
                break
            frame, src_idx = nxt, src_idx + 1
        if frame is None:
            break
        zoom = 1.12 if peak is not None and peak <= i / fps <= peak + 1.5 else 1.0
        cw, ch = int(crop_w / zoom), int(sh / zoom)
        cx = int(x + (crop_w - cw) / 2)
        cy = (sh - ch) // 2
        tile = cv2.resize(frame[cy:cy + ch, cx:cx + cw], (W, H), interpolation=cv2.INTER_LINEAR)
        enc.stdin.write(tile.tobytes())
    cap.release()
    enc.stdin.close()
    if enc.wait():
        raise RuntimeError("ffmpeg failed while encoding the tracked clip")
