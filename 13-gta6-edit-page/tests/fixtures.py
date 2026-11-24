"""Synthetic stream VODs for tests: gameplay stand-in, a facecam, quiet talk and one loud reaction."""

import shutil
import subprocess
from pathlib import Path

QUIET = [
    (2, "alright chat we are driving to the next mission now"),
    (12, "this car handles kind of weird ngl"),
    (24, "let me check the map real quick"),
    (36, "okay the mission is across the bridge"),
    (46, "wait who is that guy following us"),
]
LOUD = (55, "no way bro six stars six stars chat what the fuck is happening")
AFTER = [(66, "okay okay we survived that somehow"), (78, "that was crazy let me save the game")]


def available():
    return all(shutil.which(t) for t in ("ffmpeg", "espeak-ng"))


def _say(text, out, amp):
    subprocess.run(["espeak-ng", "-s", "165", "-a", str(amp), "-w", str(out), text], check=True)


def make_vod(out, face_img, duration=90, layout="facecam"):
    """layout 'facecam': small fixed face top-right. 'irl': large face drifting across the frame."""
    out = Path(out)
    work = out.parent / (out.stem + "_parts")
    work.mkdir(parents=True, exist_ok=True)
    inputs, mix = [], []
    lines = [(t, s, 35) for t, s in QUIET + AFTER] + [(LOUD[0], LOUD[1], 200)]
    for i, (t, text, amp) in enumerate(lines):
        wav = work / f"l{i}.wav"
        _say(text, wav, amp)
        inputs += ["-i", str(wav)]
        mix.append(f"[{i + 1}:a]adelay={t * 1000}|{t * 1000},aresample=48000[a{i}]")
    n = len(lines)
    labels = "".join(f"[a{i}]" for i in range(n))
    small_face = work / "face.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(face_img), "-vf", "scale=720:-2",
                    str(small_face)], check=True)
    face = ["-loop", "1", "-framerate", "30", "-i", str(small_face)]
    game = "[0:v]scroll=horizontal=0.004:vertical=0.002"
    if layout == "facecam":
        video = (f"[{n + 1}:v]crop=iw:iw*3/4:0:ih*0.05,scale=420:316[f];"
                 f"{game}[g];[g][f]overlay=1460:40:shortest=1[v]")
    else:
        video = (f"[{n + 1}:v]crop=iw:iw:0:ih*0.08,scale=640:640[f];"
                 f"{game},eq=brightness=-0.3[bg];"
                 f"[bg][f]overlay=x='100+900*(0.5-0.5*cos(t*2*PI/{duration}))':y=220:shortest=1[v]")
    graph = (";".join(mix) + f";{labels}amix=inputs={n}:normalize=0,"
             f"apad=whole_dur={duration}[speech];"
             f"anoisesrc=color=pink:amplitude=0.004:duration={duration}:sample_rate=48000[n];"
             f"[speech][n]amix=inputs=2:normalize=0[a];{video}")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate=30:duration={duration}",
                    *inputs, *face, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", str(out)], check=True)
    shutil.rmtree(work)
    return out
