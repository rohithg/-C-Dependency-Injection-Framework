"""Kids-channel policy checks.

Narration, titles, and descriptions have to stay short, calm, and free of
personal questions. The studio records no information about children.
"""

from __future__ import annotations

import re


class PolicyError(ValueError):
    """Raised when a line is not safe to put in a kids episode."""


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "personal question",
        re.compile(
            r"\b("
            r"what(?:'s| is) your name|how old are you|where do you live|"
            r"home address|phone number|email address|password|what school|"
            r"send me|tell me your|type your|give me your"
            r")\b",
            re.I,
        ),
    ),
    (
        "violence or fear",
        re.compile(
            r"\b("
            r"kill|kills|killed|blood|gun|guns|weapon|weapons|scary|monster|"
            r"monsters|ghost|ghosts|nightmare|die|dies|died|dead|death|hate|"
            r"hates|stupid|dumb|idiot"
            r")\b",
            re.I,
        ),
    ),
    ("web link", re.compile(r"https?://|www\.|\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.I)),
    (
        "growth nag",
        re.compile(
            r"\b(subscribe|like and subscribe|comment below|link in the description|"
            r"smash that|you won't believe|shocking|gone wrong)\b",
            re.I,
        ),
    ),
)

MAX_WORDS = 18


def check_text(text: str, label: str = "line") -> None:
    cleaned = (text or "").strip()
    if not cleaned:
        raise PolicyError(f"{label} is empty")
    for reason, pattern in _RULES:
        match = pattern.search(cleaned)
        if match:
            raise PolicyError(f"{label} has a {reason}: {match.group(0)}")
    for sentence in re.split(r"[.!?]+", cleaned):
        words = sentence.split()
        if len(words) > MAX_WORDS:
            raise PolicyError(
                f"{label} has a {len(words)}-word sentence (limit is {MAX_WORDS})"
            )


def check_episode(title: str, description: str, narrations: list[str], captions: list[str]) -> None:
    check_text(title, "title")
    check_text(description, "description")
    if len(title) > 100:
        raise PolicyError("title is longer than 100 characters")
    for index, narration in enumerate(narrations, start=1):
        check_text(narration, f"scene {index}")
    for index, caption in enumerate(captions, start=1):
        check_text(caption, f"caption {index}")
