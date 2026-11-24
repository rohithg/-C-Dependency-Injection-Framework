"""The free scheduler: posts wait in PAGE/.desk/outbox.json until their slot, and each desk
tick posts the ones that are due with the free posters. If the machine was asleep at slot
time, the post goes out on the next tick and board.csv gets the real time."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import page as pagekit  # noqa: E402

MAX_ATTEMPTS = 3


def _path(page_dir):
    p = Path(page_dir) / ".desk" / "outbox.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load(page_dir):
    p = _path(page_dir)
    return json.loads(p.read_text()) if p.exists() else []


def save(page_dir, entries):
    p = _path(page_dir)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=2))
    tmp.replace(p)


def add(page_dir, entry):
    entries = load(page_dir)
    entries.append({"state": "pending", "attempts": 0, "next_try": entry["due"], **entry})
    save(page_dir, entries)


def _update_board(page_dir, post_id, **fields):
    rows = pagekit.read_board(page_dir)
    for r in rows:
        if r["post_id"] == post_id:
            r.update(fields)
    pagekit.write_board(page_dir, rows)


def flush(page_dir, now, get_poster):
    """Post everything due. `get_poster(platform)` returns a poster. Returns (posted, failed)."""
    page_dir = Path(page_dir)
    entries = load(page_dir)
    posters, posted, failed = {}, [], []
    for e in entries:
        if e["state"] != "pending" or datetime.fromisoformat(e["next_try"]) > now:
            continue
        try:
            poster = posters.get(e["platform"]) or posters.setdefault(e["platform"], get_poster(e["platform"]))
            got = poster.post(page_dir / e["video"], e)
        except Exception as exc:
            e["attempts"] += 1
            e["error"] = str(exc).splitlines()[0][:300] if str(exc) else type(exc).__name__
            if e["attempts"] >= MAX_ATTEMPTS:
                e["state"] = "failed"
                failed.append(e)
                _update_board(page_dir, e["id"], notes=f"post failed: {e['error'][:120]}")
            else:
                e["next_try"] = (now + timedelta(minutes=15 * 2 ** e["attempts"])).isoformat()
            save(page_dir, entries)
            continue
        e.update(state="posted", url=got.get("url", ""), ref=got.get("ref", ""), posted_at=now.isoformat())
        _update_board(page_dir, e["id"], post_url=e["url"], date=now.strftime("%Y-%m-%dT%H:%M"),
                      notes=f"posted {e['platform']}:{e['ref']}" if e["ref"] else "posted")
        save(page_dir, entries)
        posted.append(e)
    return posted, failed


def refs(page_dir):
    """{post_url: (platform, ref)} for posts that went out, for API view counts."""
    return {e["url"]: (e["platform"], e["ref"]) for e in load(page_dir) if e["state"] == "posted" and e.get("url")}
