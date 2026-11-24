"""`desk.py setup`: everything from a fresh computer to a running desk, mostly by pressing Enter.

Installs what's missing, creates the page, fills desk.json (time zone detected, a private
notification topic generated), opens each platform's login in a browser window, optionally
installs the free local AI reviewer, and installs the 15-minute schedule (LaunchAgent on
macOS, crontab on Linux). Safe to run again: it skips what's already done.
"""

import json
import os
import platform as _platform
import secrets
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PLIST = Path.home() / "Library" / "LaunchAgents" / "com.gta6desk.tick.plist"


def detect_timezone():
    tz = os.environ.get("TZ")
    if tz and "/" in tz:
        return tz
    try:
        target = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in target:
            return target.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return "UTC"


class Wizard:
    def __init__(self, page=None, yes=False, ask=input, run=subprocess.run, system=None,
                 login=None, home=None, notify=None, judge_available=None):
        self.yes, self._ask, self.run = yes, ask, run
        self.system = system or _platform.system()
        self.home = Path(home or Path.home())
        self.page = Path(page or self.home / "gta6-page").expanduser()
        self._login = login
        self._notify = notify
        self._judge_available = judge_available
        self.done = []

    def ask(self, question, default=""):
        if self.yes:
            return default
        got = self._ask(f"{question} [{default}]: " if default else f"{question}: ").strip()
        return got or default

    def confirm(self, question, default=True):
        got = self.ask(f"{question} (y/n)", "y" if default else "n")
        return got.lower().startswith("y")

    def say(self, text):
        print(text)

    def sh(self, cmd, **kw):
        self.say("  $ " + " ".join(cmd))
        return self.run(cmd, **kw)

    # ---- steps ----

    def deps(self):
        self.sh([sys.executable, "-m", "pip", "install", "-q", "-r", str(HERE / "requirements.txt")])
        self.sh([sys.executable, "-m", "playwright", "install", "chromium"])
        if not shutil.which("ffmpeg"):
            if self.system == "Darwin" and shutil.which("brew"):
                self.sh(["brew", "install", "ffmpeg"])
            elif shutil.which("apt-get"):
                self.sh(["sudo", "apt-get", "install", "-y", "ffmpeg"])
            else:
                self.say("Install ffmpeg (https://ffmpeg.org/download.html), then run setup again.")

    def make_page(self):
        sys.path.insert(0, str(HERE))
        import page as pagekit
        if not (self.page / "desk.json").exists():
            name = self.ask("Page name", "Six Stars Desk")
            pagekit.init_page(self.page, {"name": name})
            self.done.append(f"page folder {self.page}")
        return json.loads((self.page / "desk.json").read_text())

    def configure(self, desk):
        tz = detect_timezone()
        if desk.get("timezone") != tz:
            desk["timezone"] = tz
        extra = self.ask("Extra streamer channel URLs, comma separated (Enter to keep Kai Cenat + IShowSpeed)", "")
        for url in [u.strip() for u in extra.split(",") if u.strip()]:
            if all(w["url"] != url for w in desk["watch"]):
                name = url.rstrip("/").split("/")[-2 if url.rstrip("/").endswith(("streams", "videos")) else -1]
                desk["watch"].append({"streamer": name.lstrip("@"), "url": url})
        n = desk.setdefault("notify", {})
        if not n.get("ntfy_topic"):
            n["ntfy_topic"] = "gta6desk-" + secrets.token_hex(6)
        quick = self.ask("Posting: 1 = just log in to each site (quick), 2 = official APIs for "
                         "YouTube/Instagram (more setup, safer)", "1") != "2"
        routes = desk.setdefault("publish", {}).setdefault("routes", {})
        routes.update({"youtube": "browser" if quick else "api", "instagram": "browser" if quick else "api",
                       "tiktok": "browser", "x": "browser"})
        desk["publish"]["provider"] = "free"
        handles = desk["publish"].setdefault("browser", {}).setdefault("handles", {})
        if str(handles.get("tiktok", "")).startswith("YOUR_"):
            del handles["tiktok"]
        ig = str(handles.get("instagram", "")).lstrip("@")
        if quick and (not ig or ig.startswith("YOUR_")):
            handles["instagram"] = self.ask("Instagram handle (so the desk can find each reel's link)", "").lstrip("@")
        return desk, quick

    def logins(self, desk, quick):
        from .posters import browser
        login = self._login or browser.login
        for p in desk.get("platforms", ["tiktok", "youtube", "instagram", "x"]):
            route = desk["publish"]["routes"].get(p, "browser")
            if route == "api":
                self.say(f"{p}: official API. Follow the steps at the top of clipper/posters/{p}.py, then "
                         f"`python3 desk.py login {p} ...`")
                continue
            if browser.has_session(p) and not self.confirm(f"{p} is already logged in. Log in again?", False):
                continue
            if self.yes or self.confirm(f"Open the {p} login window now?", True):
                login(p)
                self.done.append(f"{p} login")

    def notifications(self, desk):
        topic = desk["notify"]["ntfy_topic"]
        self.say(f"\nPhone notifications: install the free ntfy app and subscribe to  {topic}\n"
                 f"  (or open https://ntfy.sh/{topic} in a browser). Sending a test now.")
        try:
            (self._notify or _ntfy_test)(topic)
        except Exception as exc:
            self.say(f"  test notification failed: {exc}")

    def judge(self, desk):
        from . import judge
        model = desk.setdefault("judge", {"enabled": "auto"}).get("model", judge.DEFAULT_MODEL)
        desk["judge"].setdefault("model", model)
        available = self._judge_available or judge.available
        if available(model):
            self.done.append("AI reviewer")
            return
        if not self.confirm(f"Install the free local AI reviewer (Ollama + {model}, about 3 GB) so "
                            f"nothing posts without a second look?", True):
            desk["judge"]["enabled"] = "auto"
            return
        if not shutil.which("ollama"):
            if self.system == "Darwin" and shutil.which("brew"):
                self.sh(["brew", "install", "ollama"])
                self.sh(["brew", "services", "start", "ollama"])
            elif self.system == "Linux":
                if not shutil.which("zstd") and shutil.which("apt-get"):
                    self.sh(["sudo", "apt-get", "install", "-y", "zstd"])
                self.sh(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])
            else:
                self.say("Install Ollama from https://ollama.com, then run setup again.")
                return
        self.sh(["ollama", "pull", model])
        self.done.append("AI reviewer")

    def schedule(self):
        sys.path.insert(0, str(HERE))
        import desk as deskmod
        cron, plist = deskmod.cron_lines(self.page)
        (self.page / ".desk").mkdir(exist_ok=True)
        if self.system == "Darwin":
            target = self.home / "Library" / "LaunchAgents" / PLIST.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(plist)
            self.sh(["launchctl", "unload", str(target)], capture_output=True)
            self.sh(["launchctl", "load", "-w", str(target)])
            self.say("Keep the Mac awake when plugged in: System Settings > Battery > Options > "
                     "Prevent automatic sleeping when the display is off.")
        else:
            old = self.run(["crontab", "-l"], capture_output=True, text=True)
            lines = [line for line in (old.stdout or "").splitlines() if "desk.py tick" not in line]
            self.sh(["crontab", "-"], input="\n".join(lines + [cron]) + "\n", text=True)
        self.done.append("runs every 15 minutes")

    def go(self):
        self.say("GTA 6 edit desk setup. Press Enter to accept each default.\n")
        self.deps()
        desk = self.make_page()
        desk, quick = self.configure(desk)
        self._save(desk)
        self.logins(desk, quick)
        self.judge(desk)
        self._save(desk)
        self.notifications(desk)
        self.schedule()
        self.say("\nDone: " + ", ".join(self.done))
        return desk

    def _save(self, desk):
        (self.page / "desk.json").write_text(json.dumps(desk, indent=2) + "\n")


def _ntfy_test(topic):
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data="GTA 6 edit desk is set up.".encode(),
                                 headers={"Title": "GTA 6 edit desk"})
    urllib.request.urlopen(req, timeout=10).read()
