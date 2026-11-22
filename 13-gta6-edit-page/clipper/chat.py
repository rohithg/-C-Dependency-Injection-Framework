"""Chat replay as a moment signal: a burst of messages or laugh/hype emotes marks a moment
even when the streamer is quiet. Uses chat-downloader (Twitch VODs, YouTube live replays)."""

import numpy as np

HYPE_TOKENS = {"lul", "lmao", "lmfao", "omegalul", "kekw", "icant", "w", "ww", "www", "no way",
               "pog", "poggers", "😂", "💀", "🤣", "6 stars", "six stars", "busted", "wasted"}


def download(url, max_messages=None):
    from chat_downloader import ChatDownloader

    chat = ChatDownloader().get_chat(url, max_messages=max_messages)
    return [(m["time_in_seconds"], m.get("message", "")) for m in chat
            if m.get("time_in_seconds") is not None and m["time_in_seconds"] >= 0]


def spikes(messages, bin_s=10, window_s=300, threshold=2.5, min_gap=30):
    """[(time, z)] where messages per bin (hype tokens count double) jump over the local norm."""
    if not messages:
        return []
    end = max(t for t, _ in messages)
    counts = np.zeros(int(end // bin_s) + 1)
    for t, text in messages:
        low = text.lower()
        counts[int(t // bin_s)] += 2 if any(tok in low for tok in HYPE_TOKENS) else 1
    k = max(3, int(window_s / bin_s))
    pad = np.pad(counts, k // 2, mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(pad, k)[: len(counts)]
    mean, std = view.mean(axis=1), view.std(axis=1) + 1.0
    z = (counts - mean) / std
    out, last = [], -1e9
    for i in np.argsort(-z):
        if z[i] < threshold:
            break
        t = i * bin_s
        if all(abs(t - p) >= min_gap for p, _ in out):
            out.append((float(t), float(z[i])))
    # Chat reacts a few seconds after the moment.
    return [(max(0.0, t - 8), round(zz, 1)) for t, zz in sorted(out)]
