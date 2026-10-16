"""SigmaDeepLook: which frames (or pages, shots) to show: relevance with a spread, never top-K alone.

BOLT (arXiv 2503.21483) found that picking the K most relevant frames is about as weak as picking evenly (16 frames, Video-MME:
uniform 56.9, top-K 57.1, relevance-weighted sampling 57.8; multi-source 47.8 / 48.5 / 53.4). The cure is to sample over the whole
relevance distribution, so the picks follow the question but still cover the film. This module does that deterministically:
inverse-transform sampling at evenly spaced quantiles of a sharpened relevance curve, plus a floor of evenly spread picks.

    pick(points, k)  ->  k times, sorted, at least `floor` of them evenly spread, the rest where the question points
"""
import re

WORD_RE = re.compile(r"[\w']+", re.U)
STOP = set("the a an and or of to in on for with is are was were be it this that at by as from".split())
FLOOR = 0.34   # share of the picks that stay evenly spread whatever the query says
ALPHA = 3.0    # sharpness of the relevance curve (BOLT: 2.5 to 3.5 works)


def query_terms(query):
    return [w for w in (m.lower() for m in WORD_RE.findall(query or "")) if len(w) > 2 and w not in STOP]


def relevance_points(words, query, lo, hi, step=2.0, window=4.0):
    """-> [(t, score 0..1)] on a grid of `step` seconds between lo and hi. The score of t is the share of query terms spoken within
    `window` seconds of t (`words`: dicts with w, s, e as faster-whisper words.json). No query or no match -> all zero."""
    terms = set(query_terms(query))
    n = max(2, int((hi - lo) / step) + 1)
    pts = [(lo + (hi - lo) * i / (n - 1), 0.0) for i in range(n)]
    if not terms or not words:
        return pts
    hits = [(0.5 * (w.get("s", 0) + w.get("e", 0)), t) for w in words for t in [re.sub(r"\W", "", str(w.get("w", "")).lower())] if t in terms]
    if not hits:
        return pts
    out = []
    for t, _ in pts:
        got = {term for ts, term in hits if abs(ts - t) <= window}
        out.append((t, len(got) / len(terms)))
    return out


def pick(points, k, floor=FLOOR, alpha=ALPHA, min_gap=None):
    """points: [(t, relevance)] sorted by t. -> k times (fewer if the grid is smaller), sorted.

    1. floor * k picks are evenly spread: the stratum centres of the time range (the diversity floor).
    2. The rest sit at evenly spaced quantiles of the cumulative curve of relevance**alpha (inverse-transform sampling, deterministic).
    3. Picks closer than min_gap seconds merge: the next unused point of the grid takes the place (coverage, not repeats).
    With no relevance at all, every pick is evenly spread."""
    pts = sorted(points)
    if k <= 0 or not pts:
        return []
    k = min(k, len(pts))
    lo, hi = pts[0][0], pts[-1][0]
    span = max(1e-9, hi - lo)
    min_gap = span / (4.0 * k) if min_gap is None else min_gap
    n_even = k if not any(s > 0 for _, s in pts) else max(1, round(k * floor))
    chosen = []
    for i in range(n_even):
        c = lo + span * (i + 0.5) / n_even
        chosen.append(min(pts, key=lambda p: abs(p[0] - c))[0])
    rest = k - n_even
    if rest > 0:
        w = [max(0.0, s) ** alpha for _, s in pts]
        tot = sum(w)
        cum, run = [], 0.0
        for x in w:
            run += x
            cum.append(run)
        for j in range(rest):
            target = tot * (j + 0.5) / rest
            idx = next((i for i, c in enumerate(cum) if c >= target), len(pts) - 1)
            chosen.append(pts[idx][0])
    chosen = sorted(set(chosen))
    # merge near-duplicates: move a pick to the nearest free grid point that is at least min_gap from every other pick
    out = []
    for t in chosen:
        if all(abs(t - u) >= min_gap for u in out):
            out.append(t)
    free = [p[0] for p in pts if p[0] not in out]
    while len(out) < k and free:
        best = max(free, key=lambda f: min([abs(f - u) for u in out] or [span]))
        if out and min(abs(best - u) for u in out) < min_gap * 0.5:
            break
        out.append(best)
        free.remove(best)
    return sorted(out)[:k]
