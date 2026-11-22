"""The desk runner: the daily schedule (SETUP_PROMPT section 9) without you at the keyboard.

  tick      one pass: new VODs -> drafts, nightly countdown, auto-approve (if on), schedule,
            post URLs, view checkpoints, then one notification with what changed
  run       tick every N minutes until stopped
  list      drafts and their status, best first
  approve   approve a draft (optionally with a new hook) and schedule it with --post
  schedule  post an approved clip to every platform at its next free slot
  stats     fill due 24h / 72h / 7d view checkpoints now
  links     live post URLs for a campaign, ready to paste into its dashboard
  cron      print a crontab line (and a macOS LaunchAgent) that runs `tick` every 15 minutes

Settings live in PAGE/desk.json. Secrets come from the environment: UPLOAD_POST_API_KEY,
DISCORD_WEBHOOK_URL (optional).
"""

import argparse
import fcntl
import json
import os
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import clip  # noqa: E402
import page as pagekit  # noqa: E402
from clipper import notify, publish, sources, stats, studio  # noqa: E402


def _state_path(page):
    p = Path(page) / ".desk" / "state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_state(page):
    p = _state_path(page)
    state = json.loads(p.read_text()) if p.exists() else {}
    for k, empty in (("seen", {}), ("countdowns", []), ("failures", {})):
        state.setdefault(k, empty)
    return state


def save_state(page, state):
    _state_path(page).write_text(json.dumps(state, indent=2))


def new_vods(page, desk, state, lister=sources.latest_vods):
    """(watch entry, vod) pairs not processed yet. A channel seen for the first time only
    contributes its newest VOD, so turning the desk on doesn't clip a whole backlog."""
    out = []
    for w in desk.get("watch", []):
        key = w["url"]
        try:
            vods = lister(key)
        except Exception as exc:
            print(f"watch {w.get('streamer')}: {exc}")
            continue
        seen = state["seen"].setdefault(key, None)
        fresh = [v for v in vods if v["id"] not in (seen or [])]
        if seen is None:
            state["seen"][key] = [v["id"] for v in vods[1:]]
            fresh = vods[:1]
        out += [(w, v) for v in fresh]
    return out


def process_vod(page, desk, w, v):
    credit = f"{w['streamer']} ({w['platform']})" if w.get("platform") else w["streamer"]
    vod = sources.fetch(page, v["url"], streamer=w["streamer"], platform=w.get("platform"))
    n = desk.get("clips_per_vod", 4)
    online = not Path(v["url"]).exists()
    clip.scan(page, vod, top=max(10, n * 2), model=desk.get("model", "base.en"),
              chat=bool(desk.get("chat")) and online)
    layout = "stack" if w.get("facecam") else "auto"
    facecam = ",".join(map(str, w["facecam"])) if w.get("facecam") else None
    metas = clip.render(page, vod, top=n, layout=layout, facecam=facecam, credit=credit,
                        model=desk.get("model", "base.en"), jobs=desk.get("jobs"))
    return [m for m in metas if m["status"] == "draft"]


def auto_approve(page, desk, today):
    cfg = desk.get("auto_approve", {})
    if not cfg.get("enabled") or today < date.fromisoformat(cfg.get("after", "2999-01-01")):
        return []
    done = []
    for c in studio.clips(page):
        if c["status"] == "draft" and not c.get("skip") and c["moment"].get("score", 0) >= cfg.get("min_score", 60):
            studio.approve(page, c["id"], c["hook"])
            done.append(c["id"])
    return done


def maybe_countdown(page, desk, state, now):
    cfg = desk.get("countdown", {})
    if not cfg.get("enabled"):
        return None
    today = now.date().isoformat()
    h, m = map(int, cfg.get("at", "20:00").split(":"))
    if (now.hour, now.minute) < (h, m) or today in state["countdowns"]:
        return None
    from clipper.countdown import build, pick
    fresh = [d for d in pick(page, 20)
             if date.fromtimestamp((d / "base.mp4").stat().st_mtime).isoformat() == today]
    if len(fresh) < cfg.get("min_new_clips", 4):
        return None
    meta = build(page, fresh[:5], slug=f"{today}-top{min(5, len(fresh))}")
    state["countdowns"].append(today)
    return meta


MAX_FAILURES = 3


def _quoted(hook):
    return hook if hook.startswith("\u201c") else f"\u201c{hook}\u201d"


def tick(page, now=None, lister=sources.latest_vods, client=None, counts=None, sender=notify.send):
    """One pass. Returns None without doing anything if another tick still holds the lock
    (a long VOD can outlast the 15-minute cron interval)."""
    page = Path(page)
    lock = open(_state_path(page).with_name("tick.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another tick is still running")
        lock.close()
        return None
    try:
        return _tick(page, now, lister, client, counts, sender)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _tick(page, now, lister, client, counts, sender):
    desk = publish.load_desk(page)
    if desk.get("cookies_from_browser"):
        os.environ["CLIPPER_COOKIES_FROM_BROWSER"] = desk["cookies_from_browser"]
    tz = desk.get("timezone", "UTC")
    now = now or datetime.now(ZoneInfo(tz))
    state = load_state(page)
    report = {"drafts": [], "countdown": None, "approved": [], "scheduled": [], "urls": 0, "stats": [],
              "failed": []}

    for w, v in new_vods(page, desk, state, lister):
        try:
            report["drafts"] += process_vod(page, desk, w, v)
        except Exception as exc:
            print(f"{w['streamer']} {v['id']}: {str(exc).splitlines()[0][:300]}")
            tries = state["failures"][v["id"]] = state["failures"].get(v["id"], 0) + 1
            if tries < MAX_FAILURES:
                save_state(page, state)
                continue
            report["failed"].append(f"{w['streamer']}: {v.get('title') or v['id']} ({exc})")
        state["seen"].setdefault(w["url"], []).append(v["id"])
        save_state(page, state)

    try:
        report["countdown"] = maybe_countdown(page, desk, state, now)
    except Exception:
        traceback.print_exc()
    report["approved"] = auto_approve(page, desk, now.date())

    can_publish = bool(os.environ.get("UPLOAD_POST_API_KEY")) or client is not None
    if can_publish:
        for c in studio.clips(page):
            if c["status"] == "approved" and (c["id"] in report["approved"] or c.get("queue")):
                try:
                    report["scheduled"] += publish.schedule(page, c["id"], client=client, now=now)
                except Exception as exc:
                    print(f"schedule {c['id']}: {exc}")
        try:
            report["urls"] = publish.resolve_urls(page, client)
        except Exception as exc:
            print(f"resolve urls: {exc}")
    report["stats"] = stats.pull(page, now.replace(tzinfo=None), counts=counts,
                                 cookies_from_browser=desk.get("cookies_from_browser"))
    save_state(page, state)

    lines = []
    if report["drafts"]:
        best = max(report["drafts"], key=lambda m: m["moment"].get("score", 0))
        lines.append(f"{len(report['drafts'])} new drafts. Best: {_quoted(best['hook'])}")
    if report["countdown"]:
        lines.append(f"Countdown ready: {_quoted(report['countdown']['hook'])}")
    if report["scheduled"]:
        lines.append(f"{len(report['scheduled'])} posts scheduled")
    if report["stats"]:
        top = max(report["stats"], key=lambda s: s[2])
        lines.append(f"{len(report['stats'])} view checkpoints read. Top: {top[0]} {top[2]:,} at {top[1]}")
    if report["failed"]:
        lines.append(f"Gave up after {MAX_FAILURES} tries: " + "; ".join(report["failed"]))
    if lines:
        try:
            sender(desk, "GTA 6 edit desk", "\n".join(lines) + "\nReview: python3 clip.py studio")
        except Exception as exc:
            print(f"notify: {exc}")
        print("\n".join(lines))
    return report


def campaign_links(page, campaign, since=None):
    return [r["post_url"] for r in pagekit.read_board(page)
            if r["campaign"].lower() == campaign.lower() and r["post_url"]
            and (not since or r["date"][:10] >= since)]


def cron_lines(page):
    page = Path(page).resolve()
    py = sys.executable
    log = page / ".desk" / "desk.log"
    cron = f"*/15 * * * * cd {HERE} && {py} desk.py tick {page} >> {log} 2>&1"
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.gta6desk.tick</string>
  <key>ProgramArguments</key><array><string>{py}</string><string>{HERE / 'desk.py'}</string><string>tick</string><string>{page}</string></array>
  <key>StartInterval</key><integer>900</integer>
  <key>StandardOutPath</key><string>{log}</string><key>StandardErrorPath</key><string>{log}</string>
</dict></plist>"""
    return cron, plist


def main(argv=None):
    p = argparse.ArgumentParser(prog="desk.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("tick")
    s.add_argument("page")
    s = sub.add_parser("run")
    s.add_argument("page")
    s.add_argument("--every", type=int, default=15, help="minutes between ticks")
    s = sub.add_parser("schedule")
    s.add_argument("page")
    s.add_argument("clip", help="<vod>/<id> or countdown/<slug>")
    s.add_argument("--platforms", nargs="*")
    s.add_argument("--campaign", help="campaign name: adds #ad and the paid-partnership label")
    s = sub.add_parser("list")
    s.add_argument("page")
    s = sub.add_parser("approve")
    s.add_argument("page")
    s.add_argument("clip")
    s.add_argument("--hook")
    s.add_argument("--post", action="store_true", help="schedule to every platform right away")
    s = sub.add_parser("stats")
    s.add_argument("page")
    s = sub.add_parser("links")
    s.add_argument("page")
    s.add_argument("--campaign", required=True)
    s.add_argument("--since", help="YYYY-MM-DD")
    s = sub.add_parser("cron")
    s.add_argument("page")
    a = p.parse_args(argv)

    if a.cmd == "tick":
        tick(a.page)
    elif a.cmd == "run":
        while True:
            try:
                tick(a.page)
            except Exception:
                traceback.print_exc()
            time.sleep(a.every * 60)
    elif a.cmd == "schedule":
        for d in publish.schedule(a.page, a.clip, a.platforms, campaign=a.campaign):
            print(f"{d['platform']:<9} {d['when']}  {d['post_id']}  job {d['job']}")
    elif a.cmd == "list":
        for c in studio.clips(a.page):
            m = c["moment"]
            print(f"{c['id']:<28} {c['status']:<9} score {m.get('score', 0):>6}  "
                  f"{c.get('duration', '')}s  \u201c{c['hook']}\u201d  {', '.join(c.get('hooks', [])[1:])}")
    elif a.cmd == "approve":
        from clipper.pipeline import finalize
        clip_dir = studio.clip_path(a.page, a.clip)
        if a.hook:
            finalize(clip_dir, hook=a.hook)
        meta = studio.approve(a.page, a.clip, a.hook or json.loads((clip_dir / "meta.json").read_text())["hook"])
        print(f"approved: exports/{meta['export']}")
        if a.post:
            meta = studio.queue_post(a.page, a.clip)
            print("scheduled" if meta["status"] == "scheduled" else "queued for the next tick")
    elif a.cmd == "stats":
        desk = publish.load_desk(a.page)
        for post_id, cp, views in stats.pull(a.page, cookies_from_browser=desk.get("cookies_from_browser")):
            print(f"{post_id} {cp} {views:,}")
    elif a.cmd == "links":
        for url in campaign_links(a.page, a.campaign, a.since):
            print(url)
    elif a.cmd == "cron":
        cron, plist = cron_lines(a.page)
        print("crontab -e, then add:\n" + cron)
        print("\nmacOS: save as ~/Library/LaunchAgents/com.gta6desk.tick.plist, then "
              "`launchctl load ~/Library/LaunchAgents/com.gta6desk.tick.plist`\n" + plist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
