# Little Lantern

A faceless YouTube channel for young children. The stories are written in advance. The studio draws the pictures, speaks the lines, mixes a short piece of original music, and can hand the finished file to YouTube.

Luma, a little lantern, is on every scene. There is no camera and no photo of a child.

## Make one episode

```bash
cd 13-python-kids-youtube
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You also need `ffmpeg` and `espeak-ng` on the machine. The offline voice uses espeak. The default voice is Microsoft's Jenny neural voice through the `edge-tts` package, and the studio falls back to espeak if that service cannot be reached.

```bash
python studio.py render --id why-bees-buzz
python studio.py serve
```

Open http://127.0.0.1:8766/studio.html and press play. The package for each story is a video, a thumbnail, the script, and the YouTube title, description, and made-for-kids flag.

```bash
python studio.py catalog          # the 21 stories
python studio.py next             # the next story that is not rendered
python studio.py batch --count 7  # a week of new stories
python studio.py stills           # one still of each sample scene
python studio.py brand            # avatar, banner, and About text
python studio.py status
```

`--engine espeak` keeps the episode fully offline. `--tiny` renders a 640×360 preview.

## The daily job

```bash
python studio.py daily
```

This renders at most one new story per calendar day in `America/Los_Angeles`. When every story in the catalog has been rendered, the command stops and asks for a new topic. It does not publish the same video again.

A cron line for 6:00am Pacific, which is 14:00 UTC in standard time:

```bash
0 14 * * * cd /path/to/13-python-kids-youtube && .venv/bin/python studio.py daily >> output/daily.log 2>&1
```

## Connect YouTube

Upload stays off until you turn it on. Nothing in this folder contains a Google token.

1. In Google Cloud, turn on the YouTube Data API and create an OAuth desktop client.
2. Save that client file as `secrets/client_secret.json`.
3. `pip install -r requirements-upload.txt`
4. `python studio.py auth` and sign in to the channel you own.
5. In YouTube Studio, set the channel itself to made for kids.
6. In `config.json`, set `"upload_enabled": true`.

`schedule_hour_local` is 7. Each upload is private, and YouTube publishes it at 7:00 in the channel timezone. Set `schedule_hour_local` to `null` and `privacy` to `private` if you want to watch every file before it can be seen.

Every upload is sent with `selfDeclaredMadeForKids`. The narration does not ask a child for a name, an age, or a place. The studio page stays on this computer.

Custom thumbnails and scheduled publishing need a verified YouTube channel.

## Add a story

Put a new `Topic` in `channel/catalog.py`. Keep each spoken sentence to 18 words or fewer. The tests reject personal questions, scary wording, links, and subscribe-style lines in the script. After it is in the catalog, `python studio.py daily` will pick it up on its own.

## Tests

```bash
python -m pytest -q tests
```
