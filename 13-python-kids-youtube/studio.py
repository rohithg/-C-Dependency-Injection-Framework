#!/usr/bin/env python3
"""Run the Little Lantern studio from the command line."""

from __future__ import annotations

import argparse
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from channel import art, catalog
from channel.config import ConfigError, load_config
from channel.pipeline import (
    daily,
    output_dir,
    refresh_studio,
    render_batch,
    render_episode,
    render_next,
    upload_pending,
    write_brand,
)
from channel.store import load
from channel.upload import CredentialsError, authenticate

ROOT = Path(__file__).resolve().parent

STILLS = (
    ("title", "bee", "garden", "Why Bees Buzz"),
    ("teach", "bee", "garden", "Fast wings push the air, and our ears hear a buzz."),
    ("teach", "flower", "garden", "The water moves up the stem, like a straw."),
    ("teach", "moon", "night", "The moon does not make its own light."),
    ("teach", "phases", "night", "We see only the bright part."),
    ("teach", "rain", "sky", "Drops in the cloud grow heavy and fall."),
    ("teach", "rocket", "space", "When the gas goes down, the rocket goes up."),
    ("teach", "whale", "sea", "A whale breathes through a blowhole on top."),
    ("teach", "train", "cozy", "A train rolls on two steel rails."),
    ("teach", "snow", "snow", "Water drops freeze into tiny crystals."),
    ("teach", "n5", "night", "Five little stars."),
    ("teach", "rainbow", "sky", "The light splits into many colors."),
    ("teach", "book", "cozy", "A book holds words and pictures."),
    ("thumb", "bee", "garden", "Why Bees Buzz"),
    ("bye", "lantern", "garden", "Bye for now."),
)


def _config(args: argparse.Namespace) -> dict:
    overrides = {}
    if getattr(args, "tiny", False):
        overrides.update(width=640, height=360, fps=8, preset="ultrafast", crf=30)
    if getattr(args, "engine", None):
        overrides["engine"] = args.engine
    return load_config(ROOT / "config.json", overrides)


def _finish(result) -> int:
    print(result.message)
    if result.status == "exhausted":
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Little Lantern, a faceless kids learning channel")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("catalog", help="List the reviewed stories")
    sub.add_parser("stills", help="Draw one still of each sample scene")
    sub.add_parser("brand", help="Draw the avatar, banner, and About text")
    sub.add_parser("status", help="Show what has been rendered")

    render = sub.add_parser("render", help="Render one story")
    render.add_argument("--id", required=True)
    render.add_argument("--force", action="store_true")
    render.add_argument("--tiny", action="store_true")
    render.add_argument("--engine", choices=("auto", "edge", "espeak"))

    nxt = sub.add_parser("next", help="Render the next story that is not done")
    nxt.add_argument("--tiny", action="store_true")
    nxt.add_argument("--engine", choices=("auto", "edge", "espeak"))

    batch = sub.add_parser("batch", help="Render several new stories")
    batch.add_argument("--count", type=int, default=3)
    batch.add_argument("--tiny", action="store_true")
    batch.add_argument("--engine", choices=("auto", "edge", "espeak"))

    day = sub.add_parser("daily", help="Render today's story if it is not done yet")
    day.add_argument("--force", action="store_true")
    day.add_argument("--tiny", action="store_true")
    day.add_argument("--engine", choices=("auto", "edge", "espeak"))

    sub.add_parser("upload", help="Upload rendered stories that are not on YouTube yet")
    sub.add_parser("auth", help="Sign in to YouTube once, in a browser")

    serve = sub.add_parser("serve", help="Open the local studio page")
    serve.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    try:
        config = _config(args)
    except ConfigError as exc:
        print(exc)
        return 1

    if args.cmd == "catalog":
        for topic in catalog.TOPICS:
            print(f"{topic.id:28} {topic.title}")
        print(f"{len(catalog.TOPICS)} stories")
        return 0

    if args.cmd == "stills":
        dest = output_dir(config, ROOT) / "stills"
        for kind, motif, theme, caption in STILLS:
            image = art.render_frame(
                kind=kind,
                motif=motif,
                theme=theme,
                caption=caption,
                title=caption,
                size=(1280, 720),
                t=0.7,
            )
            art.save_image(image, dest / f"{kind}-{motif}-{theme}.jpg")
        print(f"Stills in {dest}")
        return 0

    if args.cmd == "brand":
        print(write_brand(config, ROOT))
        return 0

    if args.cmd == "status":
        data = load(output_dir(config, ROOT) / "queue.json")
        if not data["episodes"]:
            print("Nothing rendered yet.")
        for item in data["episodes"]:
            state = item.get("youtube_id") or ("uploaded" if item.get("uploaded") else "local")
            print(f"{item.get('date', ''):12} {item['title']:32} {state}")
        print(refresh_studio(config, ROOT))
        return 0

    if args.cmd == "render":
        topic = catalog.by_id(args.id)
        return _finish(render_episode(topic, config, ROOT, force=args.force))

    if args.cmd == "next":
        return _finish(render_next(config, ROOT))

    if args.cmd == "batch":
        results = render_batch(config, ROOT, args.count)
        for result in results:
            print(result.message)
        if results and results[-1].status == "exhausted":
            return 2
        return 0

    if args.cmd == "daily":
        return _finish(daily(config, ROOT, force=args.force))

    if args.cmd == "auth":
        try:
            path = authenticate(config, ROOT)
        except CredentialsError as exc:
            print(exc)
            return 1
        print(f"Saved YouTube token to {path}")
        return 0

    if args.cmd == "upload":
        try:
            results = upload_pending(config, ROOT)
        except (CredentialsError, Exception) as exc:
            print(exc)
            return 1
        if not results:
            print("No episodes are waiting to upload.")
        return 0

    if args.cmd == "serve":
        out = output_dir(config, ROOT)
        refresh_studio(config, ROOT)
        port = args.port or int(config["port"])
        handler = SimpleHTTPRequestHandler
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        print(f"Studio at http://127.0.0.1:{port}/studio.html")
        import os

        os.chdir(out)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
