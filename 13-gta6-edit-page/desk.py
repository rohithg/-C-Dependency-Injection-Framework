"""The desk runner: the daily schedule (SETUP_PROMPT section 9) without you at the keyboard.

  tick      one pass: new VODs -> drafts, nightly countdown, auto-approve, book slots, post
            what's due, view checkpoints, nightly/weekly report, one notification
  run       tick every N minutes until stopped
  list      drafts and their status, best first
  approve   approve a draft (optionally with a new hook) and schedule it with --post
  schedule  post an approved clip to every platform at its next free slot
  stats     fill due 24h / 72h / 7d view checkpoints now
  links     live post URLs for a campaign, ready to paste into its dashboard
  login     connect YouTube / Instagram (free APIs) or TikTok / X (saved browser session) once
  outbox    posts waiting for their slot, posted, failed (--retry ID)
  setup     one command from a fresh computer to a running desk (--yes: all defaults)
  doctor    check that every part can run unattended
  cron      print a crontab line (and a macOS LaunchAgent) that runs `tick` every 15 minutes

Settings live in PAGE/desk.json. Platform logins live in ~/.config/clipper (desk.py login).
Optional environment: DISCORD_WEBHOOK_URL, and UPLOAD_POST_API_KEY only for the paid provider.
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
from clipper import notify, outbox, posters, publish, sources, stats, studio  # noqa: E402


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
    n = w.get("clips_per_vod") or desk.get("clips_per_vod", 4)
    online = not Path(v["url"]).exists()
    clip.scan(page, vod, top=max(10, n * 2), model=desk.get("model", "base.en"),
              chat=bool(desk.get("chat")) and online)
    layout = "stack" if w.get("facecam") else "auto"
    facecam = ",".join(map(str, w["facecam"])) if w.get("facecam") else None
    metas = clip.render(page, vod, top=n, layout=layout, facecam=facecam, credit=credit,
                        model=desk.get("model", "base.en"), jobs=desk.get("jobs"))
    return [m for m in metas if m["status"] == "draft"]


def quality_problem(c, min_score):
    """Why a draft can't go out unseen, or None. Slurs are already skipped at render time."""
    if c.get("skip"):
        return c["skip"]
    if c.get("kind") != "countdown" and c["moment"].get("score", 0) < min_score:
        return f"score {c['moment'].get('score', 0)} < {min_score}"
    longest = 180 if c.get("kind") == "countdown" else 60
    if not 12 <= (c.get("duration") or 0) <= longest:
        return f"length {c.get('duration')}s"
    if c.get("lufs") is not None and abs(c["lufs"] + 14) > 1.5:
        return f"loudness {c['lufs']} LUFS"
    if not c.get("hook") or not c.get("credit"):
        return "no hook or credit"
    if c.get("footage") not in (None, "ok"):
        return f"footage {c['footage']}"
    return None


def check_footage(page, c):
    """Black or frozen picture, checked once per clip with ffmpeg and remembered in meta.json."""
    from clipper.media import footage_problem
    if c.get("footage"):
        return c["footage"]
    clip_dir = studio.clip_path(page, c["id"])
    video = next((p for p in (clip_dir / "base.mp4", clip_dir / "final.mp4") if p.exists()), None)
    try:
        result = (footage_problem(video) if video else None) or "ok"
    except Exception as exc:
        print(f"footage check {c['id']}: {exc}")
        return "ok"
    studio.set_fields(page, c["id"], footage=result)
    c["footage"] = result
    return result


def _judge_for(desk, opener=None):
    """(review function, required?) or (None, required?)."""
    from clipper import judge
    cfg = desk.get("judge", {"enabled": "auto"})
    mode, model = cfg.get("enabled", "auto"), cfg.get("model", judge.DEFAULT_MODEL)
    if mode is False:
        return None, False
    kw = {"opener": opener} if opener else {}
    if judge.available(model, **kw):
        return (lambda clip_dir, meta: judge.review(clip_dir, meta, model, **kw)), mode is True
    return None, mode is True


def auto_approve(page, desk, today, judge_opener=None):
    cfg = desk.get("auto_approve", {})
    if not cfg.get("enabled") or (cfg.get("after") and today < date.fromisoformat(cfg["after"])):
        return []
    review, required = _judge_for(desk, judge_opener)
    if required and not review:
        print("judge required but Ollama/model not available; not auto-approving")
        return []
    budget = cfg.get("max_per_day", 8) - sum(
        1 for c in studio.clips(page) if c.get("approved_on") == today.isoformat())
    drafts = sorted((c for c in studio.clips(page) if c["status"] == "draft"),
                    key=lambda c: (c.get("kind") != "countdown", -c["moment"].get("score", 0), c["id"]))
    done = []
    for c in drafts:
        if budget <= 0:
            break
        if c.get("judged") == "rejected" or quality_problem(c, cfg.get("min_score", 60)):
            continue
        if c.get("kind") != "countdown" and check_footage(page, c) != "ok":
            continue
        hook = c["hook"]
        if review:
            clip_dir = studio.clip_path(page, c["id"])
            try:
                verdict = review(clip_dir, c)
            except Exception as exc:
                print(f"judge {c['id']}: {exc}")
                continue
            if not verdict["ok"]:
                studio.set_fields(page, c["id"], judged="rejected", judge_reason=verdict["reason"])
                continue
            if verdict["hook"] and verdict["hook"] != hook:
                from clipper.pipeline import finalize
                finalize(clip_dir, hook=verdict["hook"])
                hook = verdict["hook"]
        studio.approve(page, c["id"], hook)
        studio.set_fields(page, c["id"], approved_on=today.isoformat(), auto_approved=True,
                          judged="ok" if review else "")
        done.append(c["id"])
        budget -= 1
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


def autotune(page, desk, rows, today, low=0.6, high=1.25, min_posts=4):
    """Weekly: give streamers whose clips beat the median one more clip per VOD (up to 6),
    and the ones far under it one fewer (down to 1). Returns what changed."""
    wk = pagekit.weekly(rows, today)
    if not wk.get("posts"):
        return []
    by = {label: (med, n) for label, med, n, _ in wk["by"].get("streamer", [])}
    changes = []
    for w in desk.get("watch", []):
        med, n = by.get(w["streamer"], (None, 0))
        if n < min_posts:
            continue
        cur = w.get("clips_per_vod") or desk.get("clips_per_vod", 4)
        new = min(6, cur + 1) if med >= high * wk["median"] else max(1, cur - 1) if med <= low * wk["median"] else cur
        if new != cur:
            w["clips_per_vod"] = new
            changes.append(f"{w['streamer']} {cur}\u2192{new} clips per VOD")
    if changes:
        (Path(page) / "desk.json").write_text(json.dumps(desk, indent=2) + "\n")
    return changes


def maybe_reports(page, desk, state, now):
    """The section 13 nightly (and Sunday weekly) report, pushed once a day after reports.at."""
    cfg = desk.get("reports", {"at": "23:30"})
    if not cfg:
        return []
    h, m = map(int, cfg.get("at", "23:30").split(":"))
    today = now.date().isoformat()
    sent = state.setdefault("reports", [])
    if (now.hour, now.minute) < (h, m) or today in sent:
        return []
    rows = pagekit.read_board(page)
    out = []
    night = pagekit.nightly(rows)
    if night:
        (bv, b), (wv, w) = night["best"], night["worst"]
        out.append(f"Nightly: best {b['post_id']} {b['platform']} \u201c{b['hook']}\u201d {bv:,} views; "
                   f"worst {w['post_id']} {w['platform']} {wv:,}")
    if now.strftime("%a").lower() == cfg.get("weekly_day", "sun")[:3].lower():
        wk = pagekit.weekly(rows, now.date())
        if wk.get("posts"):
            keep = [f"{k}={label}" for k, groups in wk["by"].items() for label, med, n, up in groups[:1] if up]
            out.append(f"Weekly: {wk['posts']} posts, median {int(wk['median']):,} views. "
                       f"Best: {', '.join(keep)}")
            if cfg.get("autotune", True):
                tuned = autotune(page, desk, rows, now.date())
                if tuned:
                    out.append("Tuned: " + "; ".join(tuned))
    sent.append(today)
    del sent[:-30]
    return out


def tick(page, now=None, lister=sources.latest_vods, client=None, counts=None, sender=notify.send,
         get_poster=None):
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
        return _tick(page, now, lister, client, counts, sender, get_poster)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _tick(page, now, lister, client, counts, sender, get_poster):
    desk = publish.load_desk(page)
    if desk.get("cookies_from_browser"):
        os.environ["CLIPPER_COOKIES_FROM_BROWSER"] = desk["cookies_from_browser"]
    tz = desk.get("timezone", "UTC")
    now = now or datetime.now(ZoneInfo(tz))
    state = load_state(page)
    report = {"drafts": [], "countdown": None, "approved": [], "scheduled": [], "urls": 0, "stats": [],
              "failed": [], "posted": [], "post_failed": [], "reports": []}
    get_poster = get_poster or (lambda platform: posters.get_poster(platform, desk))

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

    free = publish.provider(desk) != "upload-post"
    if free or os.environ.get("UPLOAD_POST_API_KEY") or client is not None:
        for c in studio.clips(page):
            if c["status"] == "approved" and (c["id"] in report["approved"] or c.get("queue")):
                try:
                    report["scheduled"] += publish.schedule(page, c["id"], client=client, now=now)
                except Exception as exc:
                    print(f"schedule {c['id']}: {exc}")
    if free:
        report["posted"], report["post_failed"] = outbox.flush(page, now, get_poster)
    else:
        try:
            report["urls"] = publish.resolve_urls(page, client)
        except Exception as exc:
            print(f"resolve urls: {exc}")
    report["stats"] = stats.pull(page, now.replace(tzinfo=None), counts=counts,
                                 cookies_from_browser=desk.get("cookies_from_browser"),
                                 get_poster=get_poster)
    report["reports"] = maybe_reports(page, desk, state, now)
    save_state(page, state)

    lines = []
    if report["drafts"]:
        best = max(report["drafts"], key=lambda m: m["moment"].get("score", 0))
        lines.append(f"{len(report['drafts'])} new drafts. Best: {_quoted(best['hook'])}")
    if report["countdown"]:
        lines.append(f"Countdown ready: {_quoted(report['countdown']['hook'])}")
    if report["approved"]:
        lines.append(f"{len(report['approved'])} auto-approved")
    if report["scheduled"]:
        lines.append(f"{len(report['scheduled'])} posts scheduled")
    if report["posted"]:
        lines.append("Posted: " + ", ".join(f"{e['platform']} {e['url'] or e['id']}" for e in report["posted"]))
    if report["post_failed"]:
        lines.append("Couldn't post (gave up after 3 tries): " + "; ".join(
            f"{e['platform']} {e['id']}: {e.get('error', '')}" for e in report["post_failed"]))
    if report["stats"]:
        top = max(report["stats"], key=lambda s: s[2])
        lines.append(f"{len(report['stats'])} view checkpoints read. Top: {top[0]} {top[2]:,} at {top[1]}")
    if report["failed"]:
        lines.append(f"Gave up after {MAX_FAILURES} tries: " + "; ".join(report["failed"]))
    lines += report["reports"]
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
    path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    cron = f"*/15 * * * * cd {HERE} && PATH={path} {py} desk.py tick {page} >> {log} 2>&1"
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.gta6desk.tick</string>
  <key>ProgramArguments</key><array><string>{py}</string><string>{HERE / 'desk.py'}</string><string>tick</string><string>{page}</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{path}</string></dict>
  <key>StartInterval</key><integer>900</integer><key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{log}</string><key>StandardErrorPath</key><string>{log}</string>
</dict></plist>"""
    return cron, plist


def doctor(page, get_poster=None):
    """One line per check: is every part of the automation able to run unattended?"""
    import shutil
    desk = publish.load_desk(page)
    out = [("ffmpeg", bool(shutil.which("ffmpeg")), "install ffmpeg")]
    out.append(("watch list", bool(desk.get("watch")), "add channels to desk.json watch"))
    notify_ok = bool(desk.get("notify", {}).get("ntfy_topic") or os.environ.get(
        desk.get("notify", {}).get("discord_webhook_env", "DISCORD_WEBHOOK_URL")))
    out.append(("notifications", notify_ok, "set notify.ntfy_topic in desk.json"))
    out.append(("auto-approve", bool(desk.get("auto_approve", {}).get("enabled")),
                "set auto_approve.enabled true (otherwise you approve each clip)"))
    from clipper import judge
    jcfg = desk.get("judge", {"enabled": "auto"})
    if jcfg.get("enabled") is not False:
        out.append(("AI reviewer (optional)", judge.available(jcfg.get("model", judge.DEFAULT_MODEL)),
                    f"ollama pull {jcfg.get('model', judge.DEFAULT_MODEL)} (or python3 desk.py setup)"))
    if publish.provider(desk) == "upload-post":
        out.append(("Upload-Post key", bool(os.environ.get("UPLOAD_POST_API_KEY")), "export UPLOAD_POST_API_KEY"))
        return out
    routes = posters.routes(desk)
    for platform in desk.get("platforms", ["tiktok", "youtube", "instagram", "x"]):
        route = routes[platform]
        if route == "browser":
            from clipper.posters.browser import has_session
            out.append((f"{platform} (browser)", has_session(platform), f"python3 desk.py login {platform}"))
            continue
        try:
            poster = (get_poster or (lambda p: posters.get_poster(p, desk)))(platform)
            if hasattr(poster, "token"):
                poster.token()
            out.append((f"{platform} (api)", True, ""))
        except Exception as exc:
            out.append((f"{platform} (api)", False, str(exc)[:160]))
    return out


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
    s = sub.add_parser("login", help="connect a platform once (youtube, instagram, tiktok, x)")
    s.add_argument("platform", choices=["youtube", "instagram", "tiktok", "x"])
    s.add_argument("--client-secret", help="youtube: the Desktop-app OAuth JSON from Google Cloud")
    s.add_argument("--app-id", help="instagram: your Meta app id")
    s.add_argument("--page-name", help="instagram: which Facebook Page, if you have several")
    s.add_argument("--channel", help="tiktok/x: use an installed browser, e.g. chrome")
    s = sub.add_parser("outbox", help="posts waiting, posted and failed")
    s.add_argument("page")
    s.add_argument("--retry", metavar="POST_ID", help="try a failed post again on the next tick")
    s = sub.add_parser("setup", help="one command from a fresh computer to a running desk")
    s.add_argument("page", nargs="?", help="page folder (default ~/gta6-page)")
    s.add_argument("--yes", "-y", action="store_true", help="accept every default; only the logins need you")
    s = sub.add_parser("doctor", help="check that everything can run unattended")
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
        for post_id, cp, views in stats.pull(a.page, cookies_from_browser=desk.get("cookies_from_browser"),
                                             get_poster=lambda pf: posters.get_poster(pf, desk)):
            print(f"{post_id} {cp} {views:,}")
    elif a.cmd == "links":
        for url in campaign_links(a.page, a.campaign, a.since):
            print(url)
    elif a.cmd == "login":
        if a.platform == "youtube":
            from clipper.posters import youtube
            if not a.client_secret:
                p.error("youtube needs --client-secret (see clipper/posters/youtube.py)")
            youtube.login(a.client_secret)
            print("YouTube connected")
        elif a.platform == "instagram":
            import getpass
            from clipper.posters import instagram
            if not a.app_id:
                p.error("instagram needs --app-id (see clipper/posters/instagram.py)")
            who = instagram.login(a.app_id, getpass.getpass("App secret: "),
                                  getpass.getpass("Access token from Graph API Explorer: "), page_name=a.page_name)
            print(f"Instagram connected: @{who}")
        else:
            from clipper.posters import browser
            browser.login(a.platform, channel=a.channel)
            print(f"{a.platform} session saved")
    elif a.cmd == "outbox":
        entries = outbox.load(a.page)
        if a.retry:
            for e in entries:
                if e["id"] == a.retry:
                    e.update(state="pending", attempts=0, next_try=e["due"])
            outbox.save(a.page, entries)
        for e in entries:
            print(f"{e['id']:<13} {e['platform']:<9} {e['state']:<8} {e['due'][:16]}  "
                  f"{e.get('url') or e.get('error', '')}")
    elif a.cmd == "setup":
        from clipper.wizard import Wizard
        w = Wizard(a.page, yes=a.yes)
        w.go()
        bad = [name for name, ok, _ in doctor(w.page) if not ok]
        print("Everything is ready." if not bad else "Still to do: " + ", ".join(bad) +
              f" (python3 desk.py doctor {w.page})")
    elif a.cmd == "doctor":
        bad = 0
        for name, ok, fix in doctor(a.page):
            print(f"{'ok ' if ok else 'FIX'}  {name:<22} {'' if ok else fix}")
            bad += not ok
        return 1 if bad else 0
    elif a.cmd == "cron":
        cron, plist = cron_lines(a.page)
        print("crontab -e, then add:\n" + cron)
        print("\nmacOS: save as ~/Library/LaunchAgents/com.gta6desk.tick.plist, then "
              "`launchctl load ~/Library/LaunchAgents/com.gta6desk.tick.plist`\n" + plist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
