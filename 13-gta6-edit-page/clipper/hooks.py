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


LEAD_FILLER = {"okay", "ok", "yeah", "so", "and", "well", "like", "um", "uh", "mm", "hmm", "but"}
# A quote ending on one of these stops mid-thought ("Type in the").
DANGLING = {"the", "a", "an", "to", "of", "on", "in", "at", "for", "is", "and", "or", "but",
            "my", "your", "that", "this", "i", "i'm", "it's", "we", "you", "it", "with", "if"}

# Every streamer says these; a quote made only of them could be any clip.
GENERIC = {"oh", "my", "god", "gosh", "what", "the", "bro", "no", "way", "yo", "hell", "nah",
           "bruh", "wait", "chat", "yeah", "huh", "dude", "man", "lets", "let's", "go", "wow"}


def phrases(words, pause=0.35):
    """Spoken phrases: split after a sentence end or a pause."""
    out, cur = [], []
    for w, nxt in zip(words, words[1:] + [None]):
        cur.append(w)
        if (w["word"].rstrip()[-1:] in ".?!" or nxt is None
                or nxt["start"] - w["end"] > pause):
            out.append(cur)
            cur = []
    return out


def best_quote(words, center, max_words=6, radius=8.0):
    """The best whole short phrase said near the peak, profanity masked. Streamers repeat the
    line that matters ("I don't got no silencer... I don't got no silencer"), so repeats win;
    then complete 3-6 word lines that don't trail off, some hype, closeness to the peak."""
    near = phrases([w for w in words if abs(w["start"] - center) <= radius])
    said = [" ".join(W.norm(w["word"]) for w in ph) for ph in near]
    options = []
    for ph in near:
        while ph and W.norm(ph[0]["word"]) in LEAD_FILLER:
            ph = ph[1:]
        if len(ph) <= max_words:
            options.append((ph, False))
        else:  # the opening, or the payoff at the end of a long sentence
            options += [(ph[:max_words], True), (ph[-max_words:], True)]
    best, best_score = [], None
    for ph, cut in options:
        while len(ph) > 2 and W.norm(ph[-1]["word"]) in DANGLING:
            ph, cut = ph[:-1], True
        if len(ph) < 2:
            continue
        text = " ".join(W.norm(w["word"]) for w in ph)
        repeats = sum(text in s for s in said) >= 2
        score = (3 * min(W.hype_score(ph), 3) + (4 if 3 <= len(ph) else -3)
                 + (6 if repeats else 0) + (2 if ph[-1]["word"].rstrip()[-1:] in "!?" else 0)
                 - (6 if cut else 0) - (6 if W.norm(ph[-1]["word"]) in DANGLING else 0)
                 - (8 if all(W.mask(n) != n or n in GENERIC for n in text.split()) else 0)
                 - 0.3 * abs(ph[0]["start"] - center))
        if best_score is None or score > best_score:
            best, best_score = ph, score
    text = " ".join(t for t in (W.mask(w["word"]).strip(",.-\u2014 ") for w in best) if t)
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
        out.append(f"\u201c{quote}\u201d")
    if name and not event:
        out.append(_cap(f"{name} was not ready for this"))
    seen, unique = set(), []
    for h in out:
        if h.lower() not in seen:
            seen.add(h.lower())
            unique.append(h)
    return unique[:3]
