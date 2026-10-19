"""SigmaDeepLook shared helpers: token estimate, sparklines, event clustering, stratified + anomaly-first sampling,
near-duplicate removal (perceptual hash, fuzzy text) and a Drain log-template miner.

Stdlib only. rapidfuzz, Pillow and numpy are used when present and replaced by stdlib code when not.
"""
import difflib
import math
import os
import random
import re
from collections import Counter

BARS = "▁▂▃▄▅▆▇█"


def byte_cap(name, default):
    """A read cap in bytes. SIGMADEEPLOOK_<NAME>_CAP lowers or raises it (the tests use it to reach the over-the-cap path with a small file)."""
    try:
        return int(os.environ.get("SIGMADEEPLOOK_%s_CAP" % name, default))
    except ValueError:
        return default


# ---------------------------------------------------------------- tokens
def est_tokens(text):
    """Rough token count: 4 ASCII characters per token, one token per non-ASCII character (sparklines, box characters)."""
    if not text:
        return 0
    na = sum(1 for c in text if ord(c) > 127)
    return max(1, math.ceil((len(text) - na) / 4) + na)


# ---------------------------------------------------------------- compact numbers
def compact(n):
    """620000 -> 620k, 1250000 -> 1.2M. Small numbers stay exact."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    a = abs(n)
    if a >= 1e9:
        return f"{n / 1e9:.1f}G".replace(".0G", "G")
    if a >= 1e6:
        return f"{n / 1e6:.1f}M".replace(".0M", "M")
    if a >= 1e4:
        return f"{n / 1e3:.0f}k"
    return f"{int(n)}" if n == int(n) else f"{n:.1f}"


def pct(x, digits=1):
    return f"{x:.{digits}f} %".replace(".0 %", " %") if digits else f"{x:.0f} %"


# ---------------------------------------------------------------- sparklines
def sparkline(values, width=40, lo=None, hi=None):
    """One character per bucket (mean of the bucket), at most `width` characters. '' when there is nothing to draw."""
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return ""
    if len(vals) > width:
        step = len(vals) / width
        vals = [sum(vals[int(i * step):max(int(i * step) + 1, int((i + 1) * step))]) / max(1, len(vals[int(i * step):max(int(i * step) + 1, int((i + 1) * step))])) for i in range(width)]
    lo = min(vals) if lo is None else lo
    hi = max(vals) if hi is None else hi
    if hi - lo < 1e-12:
        return BARS[0 if hi <= 0 else 3] * len(vals)
    return "".join(BARS[min(7, max(0, int((v - lo) / (hi - lo) * 7.999)))] for v in vals)


def per_bucket(times, total, buckets):
    """Count events (times in seconds, or any 0..total scale) per bucket -> list of ints."""
    out = [0] * max(1, buckets)
    if total <= 0:
        return out
    for t in times:
        i = min(len(out) - 1, max(0, int(t / total * len(out))))
        out[i] += 1
    return out


# ---------------------------------------------------------------- clustering of repeated events
def median(xs):
    s = sorted(xs)
    return s[len(s) // 2] if s else 0.0


def cluster_events(events, anchors=(), tol=0.4, key=lambda e: e[0]):
    """Split events (tuples whose key() is a time) into those within `tol` of an anchor (explained) and the rest.

    -> dict(count, explained, unexplained (list), median_len, min_len, max_len). Lengths use e[1]-e[0] when events are (start, end).
    """
    anchors = sorted(anchors)
    exp, rest = [], []
    for e in events:
        t = key(e)
        near = any(abs(t - a) <= tol for a in anchors)
        (exp if near else rest).append(e)
    lens = [e[1] - e[0] for e in events if len(e) > 1 and isinstance(e[1], (int, float))]
    return {"count": len(events), "explained": len(exp), "unexplained": rest, "median_len": median(lens), "min_len": min(lens) if lens else 0.0,
            "max_len": max(lens) if lens else 0.0}


# ---------------------------------------------------------------- stratified + anomaly-first sampling
def sample_plan(n, anomalies=(), head=3, tail=3, strata=10, seed=7):
    """Choose row/frame/page positions in three labelled groups, anomalies first, anchors last.

    n: item count. anomalies: [(index, why)]. -> list of (index, label) with label 'anomaly: why' | 'stratum k/10' | 'head' | 'tail',
    no index twice.
    """
    rng = random.Random(seed)
    out, seen = [], set()

    def add(i, label):
        if 0 <= i < n and i not in seen:
            seen.add(i)
            out.append((i, label))
    for i, why in anomalies:
        add(i, f"anomaly: {why}")
    if n > 0:
        for k in range(strata):
            lo, hi = k * n // strata, max(k * n // strata + 1, (k + 1) * n // strata)
            add(rng.randrange(lo, min(hi, n)), f"stratum {k + 1}/{strata}")
        for i in range(min(head, n)):
            add(i, "head")
        for i in range(max(0, n - tail), n):
            add(i, "tail")
    return out


# ---------------------------------------------------------------- near-duplicates
def fuzzy_ratio(a, b):
    """0..100 similarity of two short strings (rapidfuzz when present, difflib otherwise)."""
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b)
    except ImportError:
        return 100.0 * difflib.SequenceMatcher(None, a, b).ratio()


def dedupe_text(items, ratio=90, key=lambda s: s):
    """Drop items whose text is >= `ratio` similar to one already kept (keeps the first). -> (kept, dropped_count)."""
    kept, dropped = [], 0
    for it in items:
        k = key(it).strip().lower()
        if any(fuzzy_ratio(k, key(x).strip().lower()) >= ratio for x in kept[-40:]):
            dropped += 1
        else:
            kept.append(it)
    return kept, dropped


def phash(gray_rows):
    """64-bit perceptual hash of a small grayscale picture given as a list of rows (any size >= 8x8): mean-threshold of an 8x8 average-pool.

    Stdlib only (the DCT version needs numpy; the mean hash is enough for 'same shot' tests with Hamming <= 6).
    """
    h, w = len(gray_rows), len(gray_rows[0])
    cells = []
    for by in range(8):
        for bx in range(8):
            ys, ye = by * h // 8, max(by * h // 8 + 1, (by + 1) * h // 8)
            xs, xe = bx * w // 8, max(bx * w // 8 + 1, (bx + 1) * w // 8)
            block = [gray_rows[y][x] for y in range(ys, ye) for x in range(xs, xe)]
            cells.append(sum(block) / len(block))
    m = sum(cells) / 64
    bits = 0
    for i, c in enumerate(cells):
        if c > m:
            bits |= 1 << i
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------- Drain log-template miner
_VAR = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<UUID>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<IP>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "<HEX>"),
    (re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])"), "<NUM>"),
]


def mask_line(s):
    for rx, rep in _VAR:
        s = rx.sub(rep, s)
    return s


class Drain:
    """Fixed-depth parse tree log-template mining (He et al., ICWS 2017), a compact stdlib port. depth 4, similarity 0.4."""

    def __init__(self, depth=4, sim=0.4, max_children=100):
        self.depth, self.sim, self.maxc = depth, sim, max_children
        self.root = {}
        self.clusters = []

    def add(self, line, ordinal=0):
        """-> cluster dict(tokens, count, first, last, example) the line was merged into (first/last = caller's ordinal, e.g. line number)."""
        toks = mask_line(line).split()
        if not toks:
            return None
        node = self.root.setdefault(len(toks), {})
        for tok in toks[:self.depth - 2]:
            key = tok if not any(ch.isdigit() for ch in tok) and tok != "<NUM>" else "<*>"
            if key in node:
                node = node[key]
            elif "<*>" in node and len(node) >= self.maxc:
                node = node["<*>"]
            else:
                node = node.setdefault(key, {})
        leaf = node.setdefault("__c__", [])
        best, best_s = None, -1.0
        for c in leaf:
            same = sum(1 for a, b in zip(c["tokens"], toks) if a == b)
            s = same / len(toks)
            if s > best_s:
                best, best_s = c, s
        if best is not None and best_s >= self.sim:
            best["tokens"] = [a if a == b else "<*>" for a, b in zip(best["tokens"], toks)]
            best["count"] += 1
            best["last"] = ordinal
            return best
        c = {"tokens": toks, "count": 1, "first": ordinal, "last": ordinal, "example": line[:300]}
        leaf.append(c)
        self.clusters.append(c)
        return c

    @staticmethod
    def template(c):
        return " ".join(c["tokens"])
