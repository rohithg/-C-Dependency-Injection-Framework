"""Hook suggestions, from SETUP_PROMPT section 7: 6 words or fewer, no invented claims.

Every suggestion is built from something that was actually said on stream (an event word or a
direct quote), so the page never puts words in a streamer's mouth.
"""

from . import words as W

NICKNAMES = {"kai cenat": "Kai", "ishowspeed": "Speed", "speed": "Speed", "xqc": "xQc"}
# phrase heard on stream -> how a hook names it
EVENTS = [
    (("six stars", "6 stars"), "6 stars"),
    (("five stars", "5 stars"), "5 stars"),
    (("mission failed",), "mission failed"),
    (("busted",), "busted"),
    (("wasted",), "wasted"),
    (("alligator", "gator"), "the gator"),
    (("helicopter",), "the helicopter"),
    (("plane",), "the plane"),
    (("cops", "police"), "the cops"),
]


def short_name(credit_or_name):
    name = (credit_or_name or "").split(" (")[0].strip()
    return NICKNAMES.get(name.lower(), name.split()[0] if name else "")


def heard_event(words, center=None, radius=10.0):
    text = " ".join(W.norm(w["word"]) for w in words
                    if center is None or abs(w["start"] - center) <= radius)
    for phrases, event in EVENTS:
        if any(p in text for p in phrases):
            return event
    return ""


def best_quote(words, center, max_words=6):
    """Highest-hype run of up to `max_words` spoken words near the peak, profanity masked."""
    near = [w for w in words if abs(w["start"] - center) <= 5]
    best, best_score = [], -1
    for i in range(len(near)):
        run = near[i:i + max_words]
        score = W.hype_score(run) * 10 - abs(run[0]["start"] - center)
        if score > best_score:
            best, best_score = run, score
    text = " ".join(W.mask(w["word"]).strip(",.") for w in best)
    return text[:1].upper() + text[1:] if text else ""


def _cap(text, n=6):
    return " ".join(text.split()[:n])


def _fit(*options, n=6):
    """First option that fits in n words without truncation."""
    for text in options:
        if len(text.split()) <= n:
            return text
    return _cap(options[-1], n)


def suggest(words, peak, streamer="", label=""):
    name = short_name(streamer)
    event = heard_event(words, peak)
    out = []
    if label:
        out.append(_cap(label))
    if name and event:
        if event == "mission failed":
            out.append(_fit(f"{name}'s GTA 6 mission goes wrong", f"{name}'s mission goes wrong"))
        elif event in ("busted", "wasted"):
            out.append(_fit(f"{name} gets {event} in GTA 6", f"{name} gets {event}"))
        else:
            out.append(_fit(f"{name} vs {event} in GTA 6", f"{name} vs {event}"))
    quote = best_quote(words, peak)
    if quote:
        out.append(f"\u201c{_cap(quote, 5)}\u201d")
    if name and not event:
        out.append(_cap(f"{name} was not ready for this"))
    seen, unique = set(), []
    for h in out:
        if h.lower() not in seen:
            seen.add(h.lower())
            unique.append(h)
    return unique[:3]
