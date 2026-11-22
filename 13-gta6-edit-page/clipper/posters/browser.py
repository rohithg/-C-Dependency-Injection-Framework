"""Post through your own logged-in browser session (Playwright), for platforms with no free
public-posting API: TikTok and X.

`desk.py login tiktok` (or x) opens a normal browser window with a profile kept in
~/.config/clipper/browser/<platform>; log in once and close it. Every post after that reuses
the session. The "done" entry is a selector, or "url:<glob>" to wait for a redirect. If a
site changes its upload page, override a selector in desk.json under
publish.browser.selectors.<platform>.<name> instead of editing code.

Automating the web uploader is against some platforms' terms; the account is yours to risk.
"""

from pathlib import Path

from . import config_dir

SITES = {
    "tiktok": {
        "base": "https://www.tiktok.com",
        "login": "/login",
        "upload": "/tiktokstudio/upload",
        "file": "input[type=file]",
        "caption": "div[contenteditable='true']",
        "post": "button[data-e2e='post_video_button']",
        "confirm": "div[role='dialog'] button:has-text('Post now')",
        "done": "url:**/tiktokstudio/content**",
        "link": None,
    },
    "x": {
        "base": "https://x.com",
        "login": "/i/flow/login",
        "upload": "/compose/post",
        "file": "input[data-testid='fileInput']",
        "caption": "div[data-testid='tweetTextarea_0']",
        "post": "button[data-testid='tweetButton']",
        "confirm": None,
        "done": "[data-testid='toast']",
        "link": "[data-testid='toast'] a[href*='/status/']",
    },
}


def profile_dir(platform):
    d = config_dir() / "browser" / platform
    d.mkdir(parents=True, exist_ok=True)
    return d


def _launch(pw, platform, headless, channel=None):
    kw = {"headless": headless, "viewport": {"width": 1280, "height": 900},
          "args": ["--disable-blink-features=AutomationControlled"]}
    if channel:
        kw["channel"] = channel
    return pw.chromium.launch_persistent_context(str(profile_dir(platform)), **kw)


def login(platform, channel=None):
    from playwright.sync_api import sync_playwright

    site = SITES[platform]
    with sync_playwright() as pw:
        ctx = _launch(pw, platform, headless=False, channel=channel)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(site["base"] + site["login"])
        print(f"Log in to {platform} in the window that opened, then close it.")
        page.wait_for_event("close", timeout=0)
        ctx.close()


class BrowserPoster:
    def __init__(self, platform, options=None):
        options = options or {}
        self.platform = platform
        self.site = {**SITES[platform], **options.get("selectors", {}).get(platform, {})}
        if options.get("base_url"):
            self.site["base"] = options["base_url"]
        self.headless = options.get("headless", True)
        self.channel = options.get("channel")
        self.handle = options.get("handles", {}).get(platform)
        self.timeout_ms = int(options.get("upload_timeout_s", 600) * 1000)

    def post(self, video, entry):
        from playwright.sync_api import TimeoutError as PwTimeout
        from playwright.sync_api import sync_playwright

        s = self.site
        with sync_playwright() as pw:
            ctx = _launch(pw, self.platform, self.headless, self.channel)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(s["base"] + s["upload"], wait_until="domcontentloaded")
                if "login" in page.url:
                    raise RuntimeError(f"{self.platform} session expired: run `python3 desk.py login {self.platform}`")
                page.locator(s["file"]).first.set_input_files(str(Path(video).resolve()))
                box = page.locator(s["caption"]).first
                box.wait_for(timeout=self.timeout_ms)
                box.click()
                page.keyboard.press("ControlOrMeta+A")
                page.keyboard.press("Backspace")
                for i, line in enumerate(entry["caption"].split("\n")):
                    if i:
                        page.keyboard.press("Shift+Enter")
                    page.keyboard.type(line, delay=15)
                page.keyboard.press("Escape")  # closes hashtag/mention suggestion popups
                page.wait_for_function(
                    """sel => { const b = document.querySelector(sel);
                                return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true'; }""",
                    arg=s["post"], timeout=self.timeout_ms)
                page.locator(s["post"]).first.click()
                if s.get("confirm"):
                    try:
                        page.locator(s["confirm"]).first.click(timeout=5000)
                    except PwTimeout:
                        pass
                if s["done"].startswith("url:"):
                    page.wait_for_url(s["done"][4:], timeout=180_000)
                else:
                    page.locator(s["done"]).first.wait_for(timeout=180_000)
                url = ""
                if s.get("link"):
                    try:
                        href = page.locator(s["link"]).first.get_attribute("href", timeout=15_000) or ""
                        url = href if href.startswith("http") else s["base"] + href
                    except PwTimeout:
                        pass
            finally:
                ctx.close()
        if not url and self.handle:
            url = newest_post(self.platform, self.handle)
        return {"url": url, "ref": url.rstrip("/").rsplit("/", 1)[-1] if url else ""}


def newest_post(platform, handle):
    """The account's newest post URL, read with yt-dlp (TikTok's uploader doesn't show it)."""
    from yt_dlp import YoutubeDL

    from ..sources import ydl_opts

    profile = {"tiktok": f"https://www.tiktok.com/@{handle.lstrip('@')}"}.get(platform)
    if not profile:
        return ""
    try:
        with YoutubeDL(ydl_opts(extract_flat="in_playlist", playlistend=1)) as ydl:
            info = ydl.extract_info(profile, download=False)
        entries = info.get("entries") or []
        return entries[0].get("url", "") if entries else ""
    except Exception:
        return ""
