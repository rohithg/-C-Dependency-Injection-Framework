"""The one place an AI model earns its keep: the judgment call a human used to make before
approving. A local vision model (Ollama, free, offline) looks at the clip's frame sheet and
transcript, rejects broken or misleading clips, and picks the best hook.

Everything else in the desk is deterministic code on purpose: an agent per step would be
slower, cost money and fail in new ways each run.

Black and frozen footage are caught before this by ffmpeg (media.footage_problem); a model
is only asked what code can't decide: spoilers, and which hook fits.

desk.json "judge": {"enabled": "auto" | true | false, "model": "qwen2.5vl:3b"}
  auto   use it when Ollama is running with the model, approve on the gates alone otherwise
  true   never auto-approve without the judge's yes
"""

import base64
import json
import os
import re
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "qwen2.5vl:3b"
STOP = {"a", "an", "the", "is", "in", "on", "at", "to", "of", "vs", "and", "his", "her", "gets", "got"}

PROMPT = """You review a vertical short clipped from a {streamer} GTA 6 livestream before it is
posted on a fan page. The image is a sheet of frames from the clip, in order.

Step 1, the frames only. Name what is wrong with the picture, or "none":
- "loading": only a loading or menu screen is visible
- "spoiler": the picture shows an ending screen, credits rolling or a cutscene revealing the
  story
Normal gameplay, a streamer on camera, chases, deaths and swearing are all "none".

Step 2, the hook. Transcript of what was said (automatic, may contain mis-heard words):
\"\"\"{transcript}\"\"\"

Candidate hooks (on-screen title, max 6 words):
{hooks}

Pick the candidate that reads as natural English and fits the frames and what was said.
Skip candidates that are garbled words. If none fit, write a new one of at most 6 words
using only words from the transcript plus the streamer's name. Never invent a quote or a
claim.

Answer in JSON with "problem", a short "reason" and the chosen "hook"."""

PROBLEMS = {"loading", "spoiler"}
SCHEMA = {"type": "object", "required": ["problem", "reason", "hook"], "properties": {
    "problem": {"type": "string", "enum": ["none", *sorted(PROBLEMS)]},
    "reason": {"type": "string"}, "hook": {"type": "string"}}}


def _host():
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def available(model=DEFAULT_MODEL, opener=urllib.request.urlopen):
    try:
        with opener(f"{_host()}/api/tags", timeout=3) as r:
            names = {m.get("name", "") for m in json.loads(r.read()).get("models", [])}
    except Exception:
        return False
    return model in names or f"{model}:latest" in names


def _generate(model, prompt, image, opener):
    body = {"model": model, "prompt": prompt, "stream": False, "format": SCHEMA,
            "options": {"temperature": 0}}
    if image:
        body["images"] = [base64.b64encode(Path(image).read_bytes()).decode()]
    req = urllib.request.Request(f"{_host()}/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with opener(req, timeout=600) as r:
        return json.loads(r.read())["response"]


def _words(text):
    return [w for w in re.findall(r"[a-z0-9']+", text.lower())]


def grounded(hook, transcript, candidates, streamer=""):
    """A hook is usable if it's a candidate, or short and made of words that were said."""
    hook = hook.strip().strip('"')
    if not hook or len(hook.split()) > 6:
        return False
    if hook in candidates:
        return True
    said = set(_words(transcript)) | set(_words(" ".join(candidates))) | set(_words(streamer))
    return all(w in said or w in STOP or w.isdigit() for w in _words(hook))


def review(clip_dir, meta, model=DEFAULT_MODEL, opener=urllib.request.urlopen):
    clip_dir = Path(clip_dir)
    streamer = meta.get("credit", "").split(" (")[0]
    transcript = meta.get("moment", {}).get("transcript", "")[:3000]
    candidates = [h for h in [meta.get("hook", "")] + meta.get("hooks", []) if h]
    candidates = list(dict.fromkeys(candidates))
    prompt = PROMPT.format(streamer=streamer or "streamer", transcript=transcript,
                           hooks="\n".join(f"- {h}" for h in candidates) or "- (none)")
    sheet = clip_dir / "sheet.jpg"
    raw = _generate(model, prompt, sheet if sheet.exists() else None, opener)
    try:
        got = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        got = json.loads(m.group(0)) if m else {}
    hook = str(got.get("hook") or "")
    if not grounded(hook, transcript, candidates, streamer):
        hook = meta.get("hook", "")
    problem = str(got.get("problem", "")).strip().lower()
    if problem not in PROBLEMS | {"none"}:
        problem = "none" if got.get("ok") is True else "unclear"
    return {"ok": problem == "none", "reason": f"{problem}: {got.get('reason', '')}"[:200], "hook": hook}
