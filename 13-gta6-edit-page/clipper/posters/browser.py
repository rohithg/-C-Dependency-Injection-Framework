"""Post through your own logged-in browser session (Playwright). Needed for TikTok and X
(no free public-posting API); optional for YouTube and Instagram ("quick" setup: just log in,
no developer apps).

`desk.py login <platform>` opens a normal browser window with a profile kept in
~/.config/clipper/browser/<platform>; log in once and close it. Every post after that reuses
the session.

Each site is a list of steps, so a changed upload page is fixed in desk.json
(publish.browser.steps.<platform>) instead of in code:
  ["goto", path-or-url]          open a page ("{handle}" is filled from publish.browser.handles;
                                 steps using it are skipped when there's no handle)
  ["upload", selector]           put the video in a file input
  ["type", selector, field]      replace the text in a box with entry[field] (caption, title...)
  ["click", selector]            click; ["click?", selector] = only if it shows up within 5 s
  ["wait_enabled", selector]     wait until a button is clickable (upload processed)
  ["wait", selector]             wait for something to appear; "url:<glob>" waits for a redirect
  ["link", selector]             read the post URL from a link's href (skipped if not found)

Automating the web uploader is against some platforms' terms; the account is yours to risk.
"""

from pathlib import Path

from . import config_dir

SITES = {
    "tiktok": {
        "base": "https://www.tiktok.com",
        "login": "/login",
        "steps": [
            ["goto", "/tiktokstudio/upload"],
            ["upload", "input[type=file]"],
            ["type", "div[contenteditable='true']", "caption"],
            ["wait_enabled", "button[data-e2e='post_video_button']"],
            ["click", "button[data-e2e='post_video_button']"],
            ["click?", "div[role='dialog'] button:has-text('Post now')"],
            ["wait", "url:**/tiktokstudio/content**"],
            ["link", "a[href*='/video/']"],
        ],
    },
    "x": {
        "base": "https://x.com",
        "login": "/i/flow/login",
        "steps": [
            ["goto", "/compose/post"],
            ["upload", "input[data-testid='fileInput']"],
            ["type", "div[data-testid='tweetTextarea_0']", "caption"],
            ["wait_enabled", "button[data-testid='tweetButton']"],
            ["click", "button[data-testid='tweetButton']"],
            ["wait", "[data-testid='toast']"],
            ["link", "[data-testid='toast'] a[href*='/status/']"],
        ],
    },
    "youtube": {
        "base": "https://studio.youtube.com",
        "login": "https://accounts.google.com/ServiceLogin?service=youtube&continue=https://studio.youtube.com",
        "steps": [
            ["goto", "https://www.youtube.com/upload"],
            ["upload", "input[type=file]"],
            ["type", "#title-textarea #textbox", "title"],
            ["type", "#description-textarea #textbox", "description"],
            ["click", "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"],
            ["click", "#next-button"],
            ["click", "#next-button"],
            ["click", "#next-button"],
            ["click", "tp-yt-paper-radio-button[name='PUBLIC']"],
            ["link", ".video-url-fadeable a, a.ytcp-video-info"],
            ["wait_enabled", "#done-button"],
            ["click", "#done-button"],
            ["click?", "#close-button"],
        ],
    },
    "instagram": {
        "base": "https://www.instagram.com",
        "login": "/accounts/login/",
        "steps": [
            ["goto", "/"],
            ["click", "svg[aria-label='New post']"],
            ["click?", "a:has(svg[aria-label='Post'])"],
            ["upload", "input[type=file]"],
            ["click?", "button:has-text('OK')"],
            ["click", "div[role='dialog'] div[role='button']:has-text('Next')"],
            ["click", "div[role='dialog'] div[role='button']:has-text('Next')"],
            ["type", "div[aria-label='Write a caption...']", "caption"],
            ["click", "div[role='dialog'] div[role='button']:has-text('Share')"],
            ["wait", "text=/has been shared/i"],
            ["goto", "/{handle}/reels/"],
            ["link", "a[href*='/reel/']"],
        ],
    },
}


def profile_dir(platform):
    d = config_dir() / "browser" / platform
    d.mkdir(parents=True, exist_ok=True)
    return d


def has_session(platform):
    d = config_dir() / "browser" / platform
    return d.exists() and any(d.iterdir())


def _launch(pw, platform, headless, channel=None):
    kw = {"headless": headless, "viewport": {"width": 1280, "height": 900},
          "args": ["--disable-blink-features=AutomationControlled"]}
    if channel:
        kw["channel"] = channel
    return pw.chromium.launch_persistent_context(str(profile_dir(platform)), **kw)


def _url(base, path):
    return path if path.startswith("http") else base + path


def login(platform, channel=None):
    from playwright.sync_api import sync_playwright

    site = SITES[platform]
    with sync_playwright() as pw:
        ctx = _launch(pw, platform, headless=False, channel=channel)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(_url(site["base"], site["login"]))
        print(f"Log in to {platform} in the window that opened, then close it.")
        page.wait_for_event("close", timeout=0)
        ctx.close()


class BrowserPoster:
    def __init__(self, platform, options=None):
        options = options or {}
        self.platform = platform
        site = SITES[platform]
        self.base = options.get("base_url") or site["base"]
        self.steps = options.get("steps", {}).get(platform) or site["steps"]
        self.headless = options.get("headless", True)
        self.channel = options.get("channel")
        self.handle = (options.get("handles", {}).get(platform) or "").lstrip("@")
        if self.handle.startswith("YOUR_"):
            self.handle = ""
        self.timeout_ms = int(options.get("upload_timeout_s", 600) * 1000)

    def _run(self, page, step, entry, video):
        from playwright.sync_api import TimeoutError as PwTimeout

        kind, target = step[0], step[1]
        if "{handle}" in target:
            if not self.handle:
                return None
            target = target.replace("{handle}", self.handle)
        loc = None if kind == "goto" or target.startswith("url:") else page.locator(target).first
        if kind == "goto":
            page.goto(_url(self.base, target), wait_until="domcontentloaded")
            if "login" in page.url or "ServiceLogin" in page.url:
                raise RuntimeError(f"{self.platform} session expired: run `python3 desk.py login {self.platform}`")
        elif kind == "upload":
            loc.set_input_files(str(Path(video).resolve()), timeout=60_000)
        elif kind == "type":
            loc.wait_for(timeout=self.timeout_ms)
            loc.click()
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            for i, line in enumerate(str(entry.get(step[2], "")).split("\n")):
                if i:
                    page.keyboard.press("Shift+Enter")
                page.keyboard.type(line, delay=15)
            page.keyboard.press("Escape")  # closes hashtag/mention suggestion popups
        elif kind == "click":
            loc.click(timeout=60_000)
        elif kind == "click?":
            try:
                loc.click(timeout=5000)
            except PwTimeout:
                pass
        elif kind == "wait_enabled":
            page.wait_for_function(
                """sel => { const b = document.querySelector(sel);
                            return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true'; }""",
                arg=target, timeout=self.timeout_ms)
        elif kind == "wait":
            if target.startswith("url:"):
                page.wait_for_url(target[4:], timeout=180_000)
            else:
                loc.wait_for(timeout=180_000)
        elif kind == "link":
            try:
                href = loc.get_attribute("href", timeout=15_000) or ""
                return href if href.startswith("http") else self.base + href
            except PwTimeout:
                return None
        else:
            raise ValueError(f"unknown step {kind}")
        return None

    def post(self, video, entry):
        from playwright.sync_api import sync_playwright

        url = ""
        with sync_playwright() as pw:
            ctx = _launch(pw, self.platform, self.headless, self.channel)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                for step in self.steps:
                    try:
                        got = self._run(page, step, entry, video)
                    except RuntimeError:
                        raise
                    except Exception as exc:
                        raise RuntimeError(f"{self.platform} step {step[0]} {step[1]!r} failed: "
                                           f"{str(exc).splitlines()[0][:160]}") from exc
                    url = got or url
            finally:
                ctx.close()
        return {"url": url, "ref": url.rstrip("/").rsplit("/", 1)[-1] if url else ""}
