"""Bookkeeping for a GTA 6 edit page: board.csv, reports, campaign math, export names, cuts.

Stdlib only. Claude Code (or you) runs these; nothing here signs in, spends or posts.
"""

import argparse
import csv
import re
import shutil
import statistics
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template"

BOARD_COLUMNS = [
    "post_id", "date", "platform", "format", "streamer", "vod_id", "in_out", "hook",
    "cold_open", "caption_look", "length_sec", "project_url", "views_24h", "views_72h",
    "views_7d", "likes", "shares", "saves", "comments", "campaign", "test", "notes", "post_url",
]
CHECKPOINTS = {"24h": timedelta(hours=24), "72h": timedelta(hours=72), "7d": timedelta(days=7)}
PLATFORMS = {"tiktok", "youtube", "instagram", "x"}
FORMATS = {"countdown", "reaction", "explainer", "story", "ranking", "single"}
PLACEHOLDERS = {
    "[PAGE NAME]": "name", "[HANDLE]": "handle", "[PLATFORMS]": "platforms",
    "[TIME ZONE]": "timezone", "[ANGLE]": "angle", "[STREAMERS]": "streamers",
}


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def export_name(day, streamer, slug):
    return f"{day}_{slugify(streamer)}_{slugify(slug)}.mp4"


# ---------- board.csv ----------

def board_path(page):
    return Path(page) / "board.csv"


def read_board(page):
    with open(board_path(page), newline="") as f:
        return [{c: row.get(c) or "" for c in BOARD_COLUMNS} for row in csv.DictReader(f)]


def write_board(page, rows):
    tmp = board_path(page).with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BOARD_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(board_path(page))


def next_post_id(rows, day):
    prefix = day.replace("-", "")
    taken = [r["post_id"] for r in rows if r["post_id"].startswith(prefix)]
    return f"{prefix}-{len(taken) + 1:02d}"


def log_post(page, fields):
    rows = read_board(page)
    row = {c: "" for c in BOARD_COLUMNS}
    row.update({k: v for k, v in fields.items() if v is not None})
    if row["platform"] not in PLATFORMS:
        raise ValueError(f"platform must be one of {sorted(PLATFORMS)}")
    if row["format"] not in FORMATS:
        raise ValueError(f"format must be one of {sorted(FORMATS)}")
    datetime.fromisoformat(row["date"])
    row["post_id"] = next_post_id(rows, row["date"][:10])
    rows.append(row)
    write_board(page, rows)
    return row["post_id"]


def set_numbers(page, post_id, checkpoint=None, views=None, **counts):
    rows = read_board(page)
    for row in rows:
        if row["post_id"] == post_id:
            if checkpoint:
                row[f"views_{checkpoint}"] = str(int(views))
            for key, value in counts.items():
                if value is not None:
                    row[key] = str(int(value))
            write_board(page, rows)
            return row
    raise KeyError(f"no post {post_id} in board.csv")


def due_checkpoints(rows, now):
    """Posts whose 24h / 72h / 7d read is due and still blank."""
    due = []
    for row in rows:
        posted = datetime.fromisoformat(row["date"])
        for name, age in CHECKPOINTS.items():
            if not row[f"views_{name}"] and now >= posted + age:
                due.append((row["post_id"], name, row["platform"], row["hook"]))
    return due


def _num(value):
    return int(value) if value not in ("", None) else None


def best_view(row):
    """Latest checkpoint that has a number; posts younger than 24h are never judged."""
    for name in ("7d", "72h", "24h"):
        n = _num(row[f"views_{name}"])
        if n is not None:
            return n
    return None


def nightly(rows):
    judged = [(best_view(r), r) for r in rows if best_view(r) is not None]
    if not judged:
        return None
    judged.sort(key=lambda t: t[0])
    return {"best": judged[-1], "worst": judged[0], "judged": len(judged)}


def weekly(rows, end, days=7):
    start = end - timedelta(days=days)
    week = [r for r in rows
            if start <= datetime.fromisoformat(r["date"]).date() <= end and best_view(r) is not None]
    report = {"posts": len(week), "by": {}}
    if not week:
        return report
    overall = statistics.median(best_view(r) for r in week)
    report["median"] = overall
    for key in ("format", "streamer", "platform", "slot"):
        groups = {}
        for r in week:
            label = (f"{datetime.fromisoformat(r['date']).hour:02d}:00" if key == "slot"
                     else r[key] or "(blank)")
            groups.setdefault(label, []).append(best_view(r))
        report["by"][key] = sorted(
            ((label, statistics.median(v), len(v), statistics.median(v) >= overall)
             for label, v in groups.items()),
            key=lambda t: -t[1])
    ranked = sorted(week, key=best_view)
    report["top"] = ranked[-3:][::-1]
    report["bottom"] = ranked[:3]
    return report


# ---------- campaign math (SETUP_PROMPT section 12) ----------

def clip_payout(views, rate_per_1k, min_payout=0.0, cap=None, fee=0.10):
    """Net payout for one clip: nothing below the brief's minimum, capped, minus the fee."""
    gross = views / 1000 * rate_per_1k
    if gross < min_payout:
        return 0.0
    if cap is not None:
        gross = min(gross, cap)
    return round(gross * (1 - fee), 2)


def needed_for_target(target, rate_per_1k, min_payout=0.0, cap=None, fee=0.10):
    net_per_1k = rate_per_1k * (1 - fee)
    paid_views = target / net_per_1k * 1000
    out = {
        "paid_views": paid_views,
        "views_to_clear_min": min_payout / rate_per_1k * 1000 if min_payout else 0,
    }
    if cap is not None:
        out["views_to_hit_cap"] = cap / rate_per_1k * 1000
        out["min_clips_all_capped"] = target / (cap * (1 - fee))
    return out


# ---------- ffmpeg fallback cut (SETUP_PROMPT section 6, step 2) ----------

def cut_command(src, start, end, out, facecam=None, bleeps=()):
    """1080x1920 H.264/AAC 30 fps. With a facecam rect: facecam on top, gameplay below."""
    if facecam:
        x, y, w, h = facecam
        # The facecam band is capped at 40% of the frame so gameplay keeps the payoff visible.
        cam_h = min(768, round(1080 * h / w / 2) * 2)
        game_h = 1920 - cam_h
        vf = (f"[0:v]crop={w}:{h}:{x}:{y},scale=1080:{cam_h}:force_original_aspect_ratio=increase,"
              f"crop=1080:{cam_h},setsar=1[cam];"
              f"[0:v]scale=-2:{game_h},crop=1080:{game_h},setsar=1[game];"
              f"[cam][game]vstack=inputs=2,fps=30[v]")
    else:
        vf = "[0:v]scale=-2:1920,crop=1080:1920,setsar=1,fps=30[v]"
    af = "[0:a]anull"
    for b_start, b_end in bleeps:
        af += f",volume=enable='between(t,{b_start},{b_end})':volume=0"
    af += "[a]"
    return ["ffmpeg", "-y", "-ss", str(start), "-to", str(end), "-i", str(src),
            "-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]


def parse_ts(text):
    parts = [float(p) for p in str(text).split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


# ---------- init ----------

def init_page(dest, values):
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"{dest} is not empty")
    shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True)
    shutil.copy(HERE / "SETUP_PROMPT.md", dest / "SETUP_PROMPT.md")
    for path in dest.rglob("*.md"):
        text = path.read_text()
        for placeholder, key in PLACEHOLDERS.items():
            if values.get(key):
                text = text.replace(placeholder, values[key])
        path.write_text(text)
    return dest


# ---------- CLI ----------

def _fmt(n):
    return f"{n:,.0f}"


def main(argv=None):
    p = argparse.ArgumentParser(prog="page.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create the page folder (SETUP_PROMPT section 15)")
    s.add_argument("dest")
    for key in ("name", "handle", "platforms", "timezone", "angle", "streamers"):
        s.add_argument(f"--{key}")

    s = sub.add_parser("log", help="add a post to board.csv")
    s.add_argument("page")
    s.add_argument("--date", default=datetime.now().strftime("%Y-%m-%dT%H:%M"),
                   help="local post time, e.g. 2026-11-22T19:30")
    s.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    s.add_argument("--format", required=True, choices=sorted(FORMATS))
    for key in ("streamer", "vod_id", "in_out", "hook", "cold_open", "caption_look",
                "length_sec", "project_url", "campaign", "test", "notes"):
        s.add_argument(f"--{key.replace('_', '-')}", dest=key)

    s = sub.add_parser("views", help="record a checkpoint; never guess a missing number")
    s.add_argument("page")
    s.add_argument("post_id")
    s.add_argument("--at", choices=sorted(CHECKPOINTS))
    s.add_argument("--views", type=int)
    for key in ("likes", "shares", "saves", "comments"):
        s.add_argument(f"--{key}", type=int)

    s = sub.add_parser("due", help="checkpoints due now")
    s.add_argument("page")

    s = sub.add_parser("nightly", help="best and worst edit so far")
    s.add_argument("page")

    s = sub.add_parser("weekly", help="medians by format, streamer, slot, platform")
    s.add_argument("page")
    s.add_argument("--end", default=date.today().isoformat())

    s = sub.add_parser("money", help="campaign math: per-clip payouts or views for a target")
    s.add_argument("--rate", type=float, default=1.0, help="$ per 1,000 views (median ~1)")
    s.add_argument("--min", type=float, default=0.0, help="minimum $ per clip before it pays")
    s.add_argument("--cap", type=float, help="max $ per clip")
    s.add_argument("--fee", type=float, default=0.10)
    s.add_argument("--target", type=float, help="monthly $ goal, e.g. 10000")
    s.add_argument("--views", type=int, nargs="*", help="views per clip to price")
    s.add_argument("--board", help="price every post in this page's board.csv")

    s = sub.add_parser("name", help="export filename: date_streamer_slug.mp4")
    s.add_argument("streamer")
    s.add_argument("slug")
    s.add_argument("--date", default=date.today().isoformat())

    s = sub.add_parser("cut", help="ffmpeg fallback: cut and frame to 1080x1920")
    s.add_argument("src")
    s.add_argument("start", help="HH:MM:SS")
    s.add_argument("end", help="HH:MM:SS")
    s.add_argument("out")
    s.add_argument("--facecam", help="x,y,w,h of the facecam in the source")
    s.add_argument("--bleep", action="append", default=[], help="start-end seconds in the cut")
    s.add_argument("--dry-run", action="store_true")

    a = p.parse_args(argv)

    if a.cmd == "init":
        dest = init_page(a.dest, vars(a))
        print(f"created {dest}. Next: open Claude Code there and paste SETUP_PROMPT.md")

    elif a.cmd == "log":
        fields = {k: getattr(a, k) for k in BOARD_COLUMNS if hasattr(a, k)}
        print(log_post(a.page, fields))

    elif a.cmd == "views":
        if (a.at is None) != (a.views is None):
            p.error("--at and --views go together")
        row = set_numbers(a.page, a.post_id, a.at, a.views, likes=a.likes,
                          shares=a.shares, saves=a.saves, comments=a.comments)
        print(f"{row['post_id']}: 24h={row['views_24h'] or '-'} 72h={row['views_72h'] or '-'} "
              f"7d={row['views_7d'] or '-'}")

    elif a.cmd == "due":
        due = due_checkpoints(read_board(a.page), datetime.now())
        for post_id, cp, platform, hook in due:
            print(f"{post_id}  {cp:>3}  {platform:<9}  {hook}")
        if not due:
            print("nothing due")

    elif a.cmd == "nightly":
        result = nightly(read_board(a.page))
        if not result:
            print("nothing to judge yet (no post has a 24h number)")
        else:
            for label in ("best", "worst"):
                views, r = result[label]
                print(f"{label}: {r['post_id']} {r['platform']} {r['format']} "
                      f"{_fmt(views)} views  \"{r['hook']}\"  test={r['test'] or '-'}")
            print("write one rule into LEARNED_RULES.md")

    elif a.cmd == "weekly":
        rep = weekly(read_board(a.page), date.fromisoformat(a.end))
        if not rep["posts"]:
            print("no judged posts this week")
            return 0
        print(f"{rep['posts']} judged posts, median {_fmt(rep['median'])} views")
        for key, groups in rep["by"].items():
            print(f"\nby {key}:")
            for label, med, n, keep in groups:
                print(f"  {'keep' if keep else 'cut '}  {label:<14} median {_fmt(med):>10}  ({n})")
        for label in ("top", "bottom"):
            print(f"\n{label} 3:")
            for r in rep[label]:
                print(f"  {r['post_id']} {r['format']:<9} {_fmt(best_view(r)):>10}  {r['hook']}")

    elif a.cmd == "money":
        if a.target:
            need = needed_for_target(a.target, a.rate, a.min, a.cap, a.fee)
            print(f"${_fmt(a.target)}/month at ${a.rate}/1k, {a.fee:.0%} fee:")
            print(f"  paid views needed:          {_fmt(need['paid_views'])}")
            if a.min:
                print(f"  views before a clip pays:   {_fmt(need['views_to_clear_min'])}")
            if a.cap is not None:
                print(f"  views where a clip caps:    {_fmt(need['views_to_hit_cap'])}")
                print(f"  clips needed if ALL capped: {need['min_clips_all_capped']:.0f}")
            print("  views under the minimum and above the cap earn nothing")
        views = list(a.views or [])
        if a.board:
            views += [best_view(r) or 0 for r in read_board(a.board) if r["campaign"]]
        if views:
            pays = [clip_payout(v, a.rate, a.min, a.cap, a.fee) for v in views]
            for v, pay in zip(views, pays):
                print(f"  {_fmt(v):>12} views -> ${pay:,.2f}")
            print(f"  total ${sum(pays):,.2f} from {len(views)} clips, "
                  f"{sum(1 for x in pays if x == 0)} paid $0")

    elif a.cmd == "name":
        print(export_name(a.date, a.streamer, a.slug))

    elif a.cmd == "cut":
        facecam = tuple(int(v) for v in a.facecam.split(",")) if a.facecam else None
        bleeps = [tuple(float(x) for x in b.split("-")) for b in a.bleep]
        cmd = cut_command(a.src, parse_ts(a.start), parse_ts(a.end), a.out, facecam, bleeps)
        if a.dry_run:
            print(" ".join(cmd))
        else:
            return subprocess.call(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
