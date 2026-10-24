"""SigmaDeepLook pixel and signal facts (fix round 8, ticket 83 P0.14b.H8).

What a person asks of a picture or a sound that no caption answers, computed exactly:
- `pixel_facts`: distinct colours (exact), the most frequent colours with their share, the mean colour, a few named pixels (corners,
  centre, thirds), the whole grid of a tiny picture, the number of transparent pixels.
- `sound_events`: bursts of sound over a quiet floor (beeps, knocks, words, alarms): how many, when each starts and ends, how long,
  the strongest frequency of each, the gaps between them, and the time the last one ends.
Both work on plain bytes or samples. numpy is used when present; a pure-Python path covers pictures up to a few million pixels
and sounds up to ten minutes, and past that the missing part is a "Not looked at" row.
"""
import array
import math
from collections import Counter

import dl_prof as P

fmt = P.fmt
PIXEL_PURE_CAP = 4_000_000
SOUND_PURE_CAP_S = 600
FRAME_S = 0.02


def _hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"


# ------------------------------------------------------------------------------------------ pictures
def pixel_facts(look, w, h, rgb, alpha=None, pri=87, source=""):
    """rgb: bytes, 3 per pixel, row by row; alpha: optional bytes, 1 per pixel."""
    n = w * h
    if not n or len(rgb) < 3 * n:
        return
    np = look.mod("numpy")
    if np is not None:
        a = np.frombuffer(rgb, dtype=np.uint8, count=3 * n).reshape(n, 3).astype(np.uint32)
        packed = (a[:, 0] << 16) | (a[:, 1] << 8) | a[:, 2]
        vals, cnt = np.unique(packed, return_counts=True)
        order = np.argsort(-cnt, kind="stable")[:8]
        top = [(int(vals[i]), int(cnt[i])) for i in order]
        distinct = len(vals)
        mean = tuple(float(a[:, k].mean()) for k in range(3))
        get = lambda x, y: tuple(int(v) for v in a[y * w + x])    # noqa: E731
    else:
        if n > PIXEL_PURE_CAP:
            look.skip(f"exact colour count of a {w}x{h} picture", f"{n:,} pixels is over the {PIXEL_PURE_CAP:,} the standard library reads in reasonable time", "numpy")
            return
        c = Counter(zip(rgb[0:3 * n:3], rgb[1:3 * n:3], rgb[2:3 * n:3]))
        top = [((r << 16) | (g << 8) | b, k) for (r, g, b), k in c.most_common(8)]
        distinct = len(c)
        mean = tuple(sum(rgb[k:3 * n:3]) / n for k in range(3))
        get = lambda x, y: (rgb[3 * (y * w + x)], rgb[3 * (y * w + x) + 1], rgb[3 * (y * w + x) + 2])    # noqa: E731
    look.fact("distinct_colours", int(distinct))
    P.counts(look, [("pixels", n), ("distinct colours", int(distinct))], pri + 8, "Picture counts")
    tops = ", ".join(f"{_hex(v >> 16, (v >> 8) & 255, v & 255)} {100.0 * k / n:.1f} % ({k:,})" for v, k in top)
    look.line(f"Pixels (every one of the {w} x {h} = {n:,} read{'; ' + source if source else ''}): {distinct:,} distinct colours; most frequent: {tops}; mean colour {_hex(*(int(round(m)) for m in mean))}.", pri, "pixels")
    if distinct <= 256 and top:   # fix round 14: a palette-like picture: the exact count of any colour is one --ask away
        r0, g0, b0 = top[0][0] >> 16, (top[0][0] >> 8) & 255, top[0][0] & 255
        look.line(f'Ask a colour count: --ask "how many pixels have colour RGB ({r0}, {g0}, {b0})" (also {_hex(r0, g0, b0)} or palette index N; "colour table" lists all {distinct} colours with counts).', pri + 1, "pixels")
    if alpha is not None:
        z = sum(1 for v in alpha if v == 0) if np is None else int((np.frombuffer(alpha, dtype=np.uint8) == 0).sum())
        look.line(f"Transparency: {z:,} of {n:,} pixels fully transparent ({100.0 * z / n:.1f} %).", pri - 1, "pixels")
    xs = sorted({0, w // 3, w // 2, (2 * w) // 3, w - 1})
    ys = sorted({0, h // 3, h // 2, (2 * h) // 3, h - 1})
    pts = [(x, y) for y in ys for x in xs]
    look.line("Named pixels (x,y from the top left): " + "; ".join(f"({x},{y}) {_hex(*get(x, y))}" for x, y in pts[:25]), pri - 2, "pixels")
    if n <= 256:
        rows = [" ".join(_hex(*get(x, y))[1:] for x in range(w)) for y in range(h)]
        look.line("Every pixel (rrggbb, one row per line):\n" + "\n".join(rows), pri - 1, "pixels")
    else:
        boxes = colour_boxes(w, h, rgb, top, n)
        if boxes:
            look.line("Where the most frequent colours sit (the box each one spans, x and y from the top left, inclusive, and the share of the box it fills): "
                      + "; ".join(boxes), pri - 3, "pixels")
        g = gradient_line(w, h, rgb, top, n)
        if g:
            look.line(g, pri - 3, "pixels")


def colour_boxes(w, h, rgb, top, n, least=0.005, fill_min=0.2):
    """'#c81e1e x 40-119, y 50-99 (100 %)' for each frequent colour (at least `least` of the picture) that fills at least `fill_min` of
    the box it spans: a solid block, bar or panel, so a pixel inside the box can be named without a pixel dump. Byte searches per row."""
    out = []
    stride = 3 * w
    for v, k in top:
        if k < least * n:
            continue
        pat = bytes((v >> 16, (v >> 8) & 255, v & 255))
        y0 = y1 = x0 = x1 = None
        for y in range(h):
            row = rgb[y * stride:(y + 1) * stride]
            i = row.find(pat)
            while i != -1 and i % 3:
                i = row.find(pat, i + 1)
            if i == -1:
                continue
            j = row.rfind(pat)
            while j != -1 and j % 3:
                j = row.rfind(pat, 0, j + 2)
            y0 = y if y0 is None else y0
            y1 = y
            x0 = i // 3 if x0 is None else min(x0, i // 3)
            x1 = j // 3 if x1 is None else max(x1, j // 3)
        if y0 is None:
            continue
        area = (y1 - y0 + 1) * (x1 - x0 + 1)
        if k >= fill_min * area:
            share = "100" if k == area else str(min(99, int(100 * k / area)))
            out.append(f"{_hex(*pat)} x {x0}-{x1}, y {y0}-{y1} ({share} %)")
    return out


def _term(base, dx, dy, w, h):
    s = str(base) if base or not (dx or dy) else ""
    for d, t in ((dx, f"x/{w - 1}"), (dy, f"y/{h - 1}")):
        if d:
            s += ((" - " if d < 0 else " + ") if s else ("-" if d < 0 else "")) + f"{abs(d)}·{t}"
    return s


def _solve3(m, r):
    """Solve the 3 x 3 system m·c = r (Gaussian elimination with pivoting) -> c, or None when it is singular."""
    a = [list(m[i]) + [r[i]] for i in range(3)]
    for c in range(3):
        p = max(range(c, 3), key=lambda i: abs(a[i][c]))
        if abs(a[p][c]) < 1e-12:
            return None
        a[c], a[p] = a[p], a[c]
        for i in range(3):
            if i != c:
                f = a[i][c] / a[c][c]
                a[i] = [x - f * y for x, y in zip(a[i], a[c])]
    return [a[i][3] / a[i][i] for i in range(3)]


def gradient_line(w, h, rgb, top, n, sample=40_000):
    """A linear colour gradient (channel = a + b·x + c·y) under the solid colours, fitted by least squares on an even sample of the
    other pixels. Printed only when every channel fits within 1 for 95 % of them and the colour changes by 16 or more across the
    picture; whole-number forms (255·x/1599, rounded down) are tried first and kept when they give the exact value for 98 % of them."""
    if w < 8 or h < 8:
        return None
    solid = {bytes((v >> 16, (v >> 8) & 255, v & 255)) for v, k in top if k >= 0.01 * n}
    s = max(1, int(math.sqrt(n / sample)))
    pts = []
    for y in range(0, h, s):
        for x in range(0, w, s):
            q = 3 * (y * w + x)
            px = rgb[q:q + 3]
            if bytes(px) not in solid:
                pts.append((x, y, px[0], px[1], px[2]))
    taken = ((h + s - 1) // s) * ((w + s - 1) // s)
    if len(pts) < 1000 or len(pts) < 0.2 * taken:
        return None
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    m = [[sum(p[0] * p[0] for p in pts), sum(p[0] * p[1] for p in pts), sx], [0, sum(p[1] * p[1] for p in pts), sy], [sx, sy, len(pts)]]
    m[1][0] = m[0][1]
    fits = []
    for c in range(3):
        cf = _solve3(m, [sum(p[0] * p[2 + c] for p in pts), sum(p[1] * p[2 + c] for p in pts), sum(p[2 + c] for p in pts)])
        if cf is None or sum(1 for p in pts if abs(p[2 + c] - cf[0] * p[0] - cf[1] * p[1] - cf[2]) <= 1.0) < 0.95 * len(pts):
            return None
        fits.append(cf)
    if max(max(abs(cf[0]) * (w - 1), abs(cf[1]) * (h - 1)) for cf in fits) < 16:
        return None
    forms, worst = [], 1.0   # (text, rounding or None)
    for c, (name, cf) in enumerate(zip("RGB", fits)):
        dx, dy = int(round(cf[0] * (w - 1))), int(round(cf[1] * (h - 1)))
        lin = [dx * p[0] / (w - 1) + dy * p[1] / (h - 1) for p in pts]
        best = None
        for base in sorted({int(round(cf[2])), int(round(cf[2] + 0.5))}):
            for mode, add in (("rounded down", 1e-9), ("rounded to the nearest whole number", 0.5)):
                share = sum(1 for p, t in zip(pts, lin) if math.floor(base + t + add) == p[2 + c]) / len(pts)
                if best is None or share > best[0]:
                    best = (share, base, mode)
        if best[0] >= 0.98:
            forms.append((f"{name} = {_term(best[1], dx, dy, w, h)}", best[2] if dx or dy else None))
            worst = min(worst, best[0])
        else:
            forms.append((f"{name} ≈ {cf[2]:.1f} {'+' if cf[0] >= 0 else '-'} {abs(cf[0]):.4f}·x {'+' if cf[1] >= 0 else '-'} {abs(cf[1]):.4f}·y (within 1)", None))
            worst = min(worst, sum(1 for p in pts if abs(p[2 + c] - cf[0] * p[0] - cf[1] * p[1] - cf[2]) <= 1.0) / len(pts))
    modes = {md for _, md in forms if md}
    if len(modes) == 1:
        body = ", ".join(t for t, _ in forms) + f", {modes.pop()}"
    else:
        body = ", ".join(t + (f" ({md})" if md else "") for t, md in forms)
    return (f"Colour gradient {'under the solid colours above ' if solid else ''}(x, y from the top left; checked on {len(pts):,} pixels, "
            f"{math.floor(100 * worst)} % or more of them exact, or within 1 where a channel says so): {body}.")


# ------------------------------------------------------------------------------------------ sound
def _stamp(t):
    return f"{int(t // 60)}:{t - 60 * int(t // 60):05.2f}"


def sound_events(look, x, sr, pri=88, drop_below=0.06, merge_gap=0.15, rel_db=30.0, tones=True):
    """Bursts of sound in mono samples x (floats, -1..1; list, array or numpy array) at sample rate sr. Prints one fact and a burst list."""
    np = look.mod("numpy")
    n = len(x)
    if n < sr // 5 or sr <= 0:
        return
    if np is None and n / sr > SOUND_PURE_CAP_S:
        look.skip("sound bursts (counts and times)", f"{n / sr / 60:.0f} minutes is over the {SOUND_PURE_CAP_S // 60} minutes the standard library reads in reasonable time", "numpy")
        return
    if np is not None and tones:
        tone_events(look, x, sr, pri - 1)
    hop = max(1, int(sr * FRAME_S))
    frames = n // hop
    if frames < 5:
        return
    if np is not None:
        xa = np.asarray(x, dtype=np.float32)
        e = xa[:frames * hop].reshape(frames, hop)
        rms = np.sqrt((e.astype(np.float64) ** 2).mean(axis=1))
        db = 20.0 * np.log10(np.maximum(rms, 1e-9))
        db = [float(v) for v in db]
    else:
        db = []
        for i in range(frames):
            seg = x[i * hop:(i + 1) * hop]
            m = sum(v * v for v in seg) / hop
            db.append(20.0 * math.log10(max(math.sqrt(m), 1e-9)))
    peak = max(db)
    if peak < -70:
        look.line(f"Sound activity: no sound above -70 dBFS in {n / sr:.2f} s (digital silence).", pri, "sound")
        return
    thr = max(peak - rel_db, -60.0)
    act = [v >= thr for v in db]
    segs, i = [], 0
    while i < frames:
        if act[i]:
            j = i
            while j + 1 < frames and act[j + 1]:
                j += 1
            segs.append([i, j])
            i = j + 1
        else:
            i += 1
    mg = []
    for s in segs:
        if mg and (s[0] - mg[-1][1] - 1) * FRAME_S < merge_gap:
            mg[-1][1] = s[1]
        else:
            mg.append(s)
    bursts = [(a * FRAME_S, (b + 1) * FRAME_S, max(db[a:b + 1])) for a, b in mg if (b - a + 1) * FRAME_S >= drop_below]
    total = n / sr
    if not bursts:
        look.line(f"Sound activity: no burst of at least {drop_below} s above {thr:.0f} dBFS (peak {peak:.1f} dBFS) in {total:.2f} s.", pri, "sound")
        return
    look.fact("sound_bursts", len(bursts))
    on = sum(b - a for a, b, _ in bursts)
    lens = [b - a for a, b, _ in bursts]
    gaps = [bursts[k + 1][0] - bursts[k][1] for k in range(len(bursts) - 1)]
    freqs = []
    if np is not None and len(bursts) <= 60:
        for a, b, _ in bursts:
            seg = xa[int(a * sr):min(int(b * sr), int(a * sr) + sr)]
            if len(seg) < 16:
                freqs.append(None)
                continue
            sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
            freqs.append(float(np.argmax(sp[1:]) + 1) * sr / len(seg))
    P.counts(look, [("sound bursts", len(bursts)), ("active seconds", f"{on:.2f}"), ("of total seconds", f"{total:.2f}")], pri + 6, "Sound counts")
    head = (f"Sound activity (20 ms frames; a burst is sound within {rel_db:.0f} dB of the peak {peak:.1f} dBFS, so above {thr:.0f} dBFS; gaps under {merge_gap} s join, bursts under {drop_below} s drop): "
            f"{len(bursts)} bursts, active {on:.2f} s of {total:.2f} s ({100 * on / total:.0f} %); first starts at {_stamp(bursts[0][0])} ({bursts[0][0]:.2f} s), "
            f"the last ends at {_stamp(bursts[-1][1])} ({bursts[-1][1]:.2f} s); burst length {min(lens):.2f}-{max(lens):.2f} s, mean {sum(lens) / len(lens):.2f} s")
    if gaps:
        head += f"; gap between bursts {min(gaps):.2f}-{max(gaps):.2f} s, mean {sum(gaps) / len(gaps):.2f} s"
    if freqs and all(f is not None for f in freqs):
        c = Counter(round(f / 10.0) * 10 for f in freqs)
        head += f"; strongest frequency per burst: " + ", ".join(f"{int(k)} Hz x{v}" for k, v in c.most_common(4))
    look.line(head + ".", pri, "sound")
    rows = [f"#{k} {a:.2f}-{b:.2f} s ({b - a:.2f} s, peak {p:.1f} dBFS" + (f", ~{freqs[k - 1]:.0f} Hz" if freqs and freqs[k - 1] else "") + ")" for k, (a, b, p) in enumerate(bursts, 1)]
    if len(rows) <= 40:
        look.line("Bursts, every one: " + "; ".join(rows), pri - 2, "sound")
    else:
        look.line(f"Bursts (first 12 and last 12 of {len(rows)}): " + "; ".join(rows[:12]) + " ... " + "; ".join(rows[-12:]), pri - 2, "sound")
        look.line("Bursts, all: " + "; ".join(rows), 30, "sound")


TONE_DB = 20.0       # a tone frame: one frequency this many dB above its own median level over the file ...
TONE_SHARE = 0.5     # ... holding this share of the frame's power (one frequency dominates)
TONE_FRAMES = 3      # a tone lasts at least this many frames (about 0.15 s)


def _tone_freq(np, seg, sr, f0, width):
    """The frequency of a steady tone in `seg`, to a fraction of a hertz: zero-padded FFT near f0, then a parabola through the peak."""
    nfft = 1 << max(int(math.ceil(math.log2(max(len(seg), sr)))), 4)
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), nfft)) + 1e-20
    lo, hi = max(1, int((f0 - width) * nfft / sr)), min(len(sp) - 2, int((f0 + width) * nfft / sr) + 1)
    if hi <= lo:
        return f0
    k = lo + int(np.argmax(sp[lo:hi + 1]))
    a, b, c = np.log(sp[k - 1:k + 2])
    d = 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0.0
    return (k + d) * sr / nfft


def _tone_edges(np, xa, sr, f, s0, s1, core):
    """Start and end (s) of a tone at f inside samples s0..s1: the points where its amplitude (the signal shifted down by f and averaged
    over about 5 ms) crosses half of its level in the `core` part."""
    seg = xa[s0:s1].astype(np.float64)
    z = seg * np.exp(-2j * np.pi * f * np.arange(s0, s1) / sr)
    wl = max(int(sr * 0.005), int(4 * sr / f), 1)
    env = np.abs(np.convolve(z, np.ones(wl) / wl, "same"))
    a, b = core[0] - s0, core[1] - s0
    level = float(np.median(env[a:b])) if b > a else float(env.max())
    idx = np.flatnonzero(env >= level / 2)
    if not idx.size:
        return None
    return (s0 + int(idx[0])) / sr, (s0 + int(idx[-1]) + 1) / sr


def _mid(xs):
    xs = sorted(xs)
    return (xs[(len(xs) - 1) // 2] + xs[len(xs) // 2]) / 2


def _tone_pass(np, xa, sr, L, min_frames):
    """One pass of the tone finder with frames of L samples: -> (tones as (frequency, start s, end s, dB above usual level), background dBFS), or ([], None)."""
    nf = len(xa) // L
    if nf < 8:
        return [], None
    win = np.hanning(L).astype(np.float32)
    S = np.empty((nf, L // 2 + 1), np.float32)
    power = np.empty(nf, np.float64)
    for a in range(0, nf, 1024):
        b = min(nf, a + 1024)
        blk = xa[a * L:b * L].reshape(b - a, L)
        S[a:b] = np.abs(np.fft.rfft(blk * win, axis=1)) ** 2
        power[a:b] = np.einsum("ij,ij->i", blk, blk, dtype=np.float64) / L
    db = 10.0 * np.log10(S + 1e-20)
    ex = db - np.median(db, axis=0)
    lo = max(3, int(math.ceil(30 * L / sr)))
    hi = S.shape[1] - 3
    if hi <= lo:
        return [], None
    k = lo + np.argmax(ex[:, lo:hi], axis=1)
    rows = np.arange(nf)
    band = sum(S[rows, k + d] for d in range(-2, 3))
    ton = (ex[rows, k] >= TONE_DB) & (band >= TONE_SHARE * np.maximum(S.sum(axis=1), 1e-30))
    events, i = [], 0
    while i < nf:
        if not ton[i]:
            i += 1
            continue
        j = i
        while j + 1 < nf and ton[j + 1] and abs(int(k[j + 1]) - int(k[i])) <= 2:
            j += 1
        if j - i + 1 >= min_frames:
            events.append((i, j))
        i = j + 1
    bg = 10.0 * math.log10(max(float(np.median(power)), 1e-18))
    if len(events) > 2000:
        return [], bg
    found = []
    for a, b in events:
        f0 = float(np.median(k[a:b + 1])) * sr / L
        core = (a * L, min((b + 1) * L, a * L + sr))
        f = _tone_freq(np, xa[core[0]:core[1]].astype(np.float64), sr, f0, 3 * sr / L)
        t0, t1 = a * L / sr, (b + 1) * L / sr
        if (b - a + 3) * L <= 30 * sr:
            got = _tone_edges(np, xa, sr, f, max(0, (a - 1) * L), min(len(xa), (b + 2) * L), (a * L, (b + 1) * L))
            if got:
                t0, t1 = got
        found.append((f, t0, t1, float(ex[a:b + 1][np.arange(b - a + 1), k[a:b + 1]].max())))
    return found, bg


def _narrow(np, xa, sr, ev, share=0.7):
    """True when the stretch of a short tone holds `share` of its power within the main lobe around its frequency: a pure pip, not a gliding pitch,
    a vowel (harmonics 100+ Hz apart) or noise."""
    a, b = int(ev[1] * sr), int(ev[2] * sr)
    seg = xa[a:b].astype(np.float64)
    if len(seg) < 16:
        return False
    nfft = 1 << int(math.ceil(math.log2(len(seg) * 8)))
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), nfft)) ** 2
    fr = np.arange(len(sp)) * sr / nfft
    near = np.abs(fr - ev[0]) <= 2.5 * sr / len(seg)
    return float(sp[near].sum()) >= share * float(sp[fr >= 30].sum())


def tone_scan(np, x, sr):
    """All tones of one channel: frames of about 50 ms (a tone of 0.15 s or more), then frames of about 10 ms (a short pip of 30 ms or more) for the
    pips the long frames cannot see. -> (tones sorted by frequency, background dBFS), or None when the signal is too short or the rate too low."""
    if np is None or sr < 400:
        return None
    xa = np.asarray(x, dtype=np.float32)
    L = 1 << max(6, int(round(math.log2(sr * 0.05))))
    found, bg = _tone_pass(np, xa, sr, L, TONE_FRAMES)
    if bg is None:
        return None
    Lf = 1 << max(5, int(round(math.log2(sr * 0.01))))
    if Lf < L:
        for ev in _tone_pass(np, xa, sr, Lf, TONE_FRAMES)[0]:
            if not any(ev[1] < o[2] + 0.05 and ev[2] > o[1] - 0.05 for o in found) and _narrow(np, xa, sr, ev):
                found.append(ev)
    return sorted(found), bg


def _tone_groups(found, side):
    groups = []
    for ev in found:
        g = groups[-1] if groups else None
        d = min(ev[2] - ev[1], g[0][2] - g[0][1]) if g else 1.0
        if g and abs(ev[0] - g[0][0]) <= max(2.0, 0.003 * ev[0], 0.5 / max(d, 0.02) if d < 0.1 else 0.0):   # good to a fraction of a hertz: 1000 and 1015 Hz stay apart
            g.append(ev)
        else:
            groups.append([ev])
    groups.sort(key=lambda g: (-len(g), g[0][0]))
    parts = []
    for g in groups[:side]:
        g.sort(key=lambda e: e[1])
        f = _mid(e[0] for e in g)
        starts = [f"{e[1]:.2f}" for e in g]
        if len(starts) > 24:
            starts = starts[:12] + ["..."] + starts[-12:]
        lens = [e[2] - e[1] for e in g]
        ln = f"each {sum(lens) / len(lens):.2f} s" if max(lens) - min(lens) < 0.02 else f"{min(lens):.2f}-{max(lens):.2f} s long"
        parts.append(f"{int(round(f))} Hz: {len(g)} tone{'s' if len(g) != 1 else ''}, starts {', '.join(starts)} s (the last at {g[-1][1]:.2f} s), {ln}, "
                     + ("over digital silence" if max(e[3] for e in g) > 150 else f"{max(e[3] for e in g):.0f} dB above its usual level"))
    more = f"; {len(groups) - side} more frequencies" if len(groups) > side else ""
    return groups, "; ".join(parts) + more


def _bg(bg):
    return "background below -180 dBFS (digital silence)" if bg is None or bg <= -179 else f"background {bg:.1f} dBFS"


def _tone_rule(what, sr):
    short = TONE_FRAMES * (1 << max(5, int(round(math.log2(sr * 0.01))))) / sr
    return (f"one frequency at least {TONE_DB:.0f} dB above its usual level in this {what} and most of the sound's power, for {short:.2f} s or more; "
            "every whole frame read, start times to about 5 ms")


def tone_events(look, x, sr, pri=87, side=6):
    """Tones: stretches where one frequency dominates the sound and stands far above its own usual level (alarm beeps, calibration tones,
    a test signal), found in every sample with short spectra: how many per frequency, when each starts, how long. A steady hum that
    lasts most of the file is its own usual level, so it is not a tone event. Needs numpy (no-op without it)."""
    got = tone_scan(look.mod("numpy"), x, sr)
    if not got or not got[0]:
        return
    found, bg = got
    groups, body = _tone_groups(found, side)
    look.fact("tone_events", {str(int(round(_mid(e[0] for e in g)))): len(g) for g in groups[:20]})
    look.line(f"Tones ({_tone_rule('file', sr)}): {len(found)} tone{'s' if len(found) != 1 else ''} at {len(groups)} "
              f"frequenc{'ies' if len(groups) != 1 else 'y'}. {body}; {_bg(bg)}.", pri, "sound")


def channel_label(k, n):
    return f"{('LEFT', 'RIGHT')[k]} (channel {k + 1})" if k < 2 else f"channel {k + 1}"


def tone_events_channels(look, chans, sr, pri=87, side=6):
    """Tones of every channel on its own (a recording with two or more channels: left and right can carry different tones). One channel: `tone_events`."""
    if len(chans) == 1:
        return tone_events(look, chans[0], sr, pri, side)
    np = look.mod("numpy")
    out, total, facts = [], 0, {}
    for k, x in enumerate(chans[:8]):
        got = tone_scan(np, x, sr)
        if not got:
            continue
        found, bg = got
        if not found:
            out.append(f"{channel_label(k, len(chans))}: no tone, {_bg(bg)}")
            continue
        groups, body = _tone_groups(found, side)
        total += len(found)
        facts[f"channel {k + 1}"] = {str(int(round(_mid(e[0] for e in g)))): len(g) for g in groups[:20]}
        out.append(f"{channel_label(k, len(chans))}: {len(found)} tone{'s' if len(found) != 1 else ''} at {len(groups)} frequenc{'ies' if len(groups) != 1 else 'y'}. {body}; {_bg(bg)}")
    if not total:
        return
    look.fact("tone_events", facts)
    look.line(f"Tones per channel ({_tone_rule('channel', sr)}): " + ". ".join(out) + ".", pri, "sound")


def _fft(a):
    """Radix-2 FFT of a list of complex numbers (length a power of two): pure Python, for the few windows the no-numpy path reads."""
    import cmath
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        w = cmath.exp(-2j * math.pi / size)
        for s in range(0, n, size):
            t = 1 + 0j
            for k in range(size // 2):
                u, v = a[s + k], a[s + k + size // 2] * t
                a[s + k], a[s + k + size // 2] = u + v, u - v
                t *= w
        size <<= 1
    return a


def tone_summary(look, x, sr, window=8192):
    """The pitch of one sound: -> {freq (Hz of the strongest steady frequency), share (its part of the power, 0-1), tones (bursts found), tone_freq},
    or None when the sound is too short. numpy: the average power spectrum of the windows; without it, four windows spread over the sound."""
    n = len(x)
    if n < 512 or sr < 100:
        return None
    np = look.mod("numpy")
    out = {"freq": None, "share": 0.0, "tones": 0, "tone_freq": None}
    if np is not None:
        xa = np.asarray(x, dtype=np.float32)
        w = min(window, 1 << int(math.log2(n)))
        nw = n // w
        step = max(1, nw // 600)
        win = np.hanning(w).astype(np.float32)
        power = np.zeros(w // 2 + 1)
        for a in range(0, nw, step):
            power += np.abs(np.fft.rfft(xa[a * w:(a + 1) * w] * win)) ** 2
        got = tone_scan(np, xa, sr)
        if got and got[0]:
            out["tones"] = len(got[0])
            out["tone_freq"] = _mid(e[0] for e in _tone_groups(got[0], 6)[0][0])
        seq = [float(v) for v in power]
    else:
        w = min(window // 2, 1 << int(math.log2(n)))
        win = [0.5 - 0.5 * math.cos(2 * math.pi * i / (w - 1)) for i in range(w)]
        seq = [0.0] * (w // 2 + 1)
        for t in range(4):
            a = (n - w) * t // 3
            sp = _fft([complex(x[a + i] * win[i]) for i in range(w)])
            for i in range(w // 2 + 1):
                seq[i] += abs(sp[i]) ** 2
    lo = max(2, int(math.ceil(20 * w / sr)))
    if len(seq) - 3 <= lo:
        return None
    tot = sum(seq[lo:]) or 1e-30
    k = max(range(lo, len(seq) - 1), key=seq.__getitem__)
    la, lb, lc = (math.log(seq[k + d] + 1e-30) for d in (-1, 0, 1))
    d = 0.5 * (la - lc) / (la - 2 * lb + lc) if la - 2 * lb + lc else 0.0
    out["freq"] = (k + d) * sr / w
    out["share"] = sum(seq[max(lo, k - 3):k + 4]) / tot
    return out


def summary_text(s):
    """One short phrase for `tone_summary`: a steady tone, bursts of a tone, or no tone."""
    if not s or s["freq"] is None:
        return "too short for a pitch"
    if s["share"] >= 0.5:
        return f"steady tone {s['freq']:.1f} Hz ({100 * s['share']:.0f} % of the power)" + (f", {s['tones']} tone bursts" if s["tones"] else "")
    if s["tones"]:
        return f"{s['tones']} tone burst{'s' if s['tones'] != 1 else ''} near {s['tone_freq']:.0f} Hz; strongest steady frequency {s['freq']:.0f} Hz ({100 * s['share']:.0f} % of the power)"
    return f"no steady tone (strongest frequency {s['freq']:.0f} Hz holds {100 * s['share']:.0f} % of the power)"


def sound_events_channels(look, chans, sr, bursts=True):
    """The sound passes for a recording with channels: bursts of the mix (all channels averaged), tones of each channel."""
    if len(chans) == 1:
        if bursts:
            sound_events(look, chans[0], sr)
        else:
            tone_events(look, chans[0], sr)
        return
    np = look.mod("numpy")
    if bursts:
        mix = sum(np.asarray(c, dtype=np.float32) for c in chans) / len(chans) if np is not None else chans[0]
        sound_events(look, mix, sr, tones=False)
    tone_events_channels(look, chans, sr)


def pcm16_to_floats(raw):
    """Little-endian 16-bit PCM bytes -> array('f') in -1..1 (pure Python; numpy callers use frombuffer instead)."""
    a = array.array("h")
    a.frombytes(raw[:len(raw) // 2 * 2])
    return array.array("f", (v / 32768.0 for v in a))


def decode_ffmpeg(look, cap_s=1800, sr=8000, channels=1, stream=None):
    """The first `cap_s` seconds of the file's audio (stream number `stream` among the audio streams, default the first) as 16-bit samples at `sr`:
    -> (floats, sr), or ([floats of channel 1, channel 2, ...], sr) when `channels` is above 1, or None. Needs ffmpeg."""
    ff = look.tool("ffmpeg")
    if not ff:
        return None
    channels = max(1, min(int(channels or 1), 8))
    r = look.run([ff, "-v", "error", "-nostdin", "-i", str(look.path), "-t", str(cap_s), "-vn"] + (["-map", f"0:a:{stream}"] if stream is not None else [])
                 + ["-ac", str(channels), "-ar", str(sr), "-f", "s16le", "-"], timeout=300)
    if r is None or r.returncode != 0 or len(r.stdout) < sr * channels:
        return None
    raw = r.stdout[:len(r.stdout) // (2 * channels) * 2 * channels]
    np = look.mod("numpy")
    if np is not None:
        a = np.frombuffer(raw, dtype="<i2")
        if channels == 1:
            return a.astype(np.float32) / 32768.0, sr
        return [a[k::channels].astype(np.float32) / 32768.0 for k in range(channels)], sr
    if channels == 1:
        return pcm16_to_floats(raw), sr
    a = array.array("h")
    a.frombytes(raw)
    return [array.array("f", (v / 32768.0 for v in a[k::channels])) for k in range(channels)], sr


def bursts_of_file(look, dur=None, cap_s=1800):
    """Decode the file's sound and print its bursts (of the mix) and its tones (of each channel); a file over `cap_s` seconds says how much was read."""
    ch = look.facts.get("channels") or 1
    ch = ch if isinstance(ch, int) and ch > 0 else 1
    if ch > 2:
        cap_s = cap_s * 2 // min(ch, 8)   # the samples held stay about the same as for a stereo file
    got = decode_ffmpeg(look, cap_s, channels=ch)
    if got is None:
        return False
    x, sr = got
    if dur and dur > cap_s + 1:
        look.line(f"Sound bursts below cover the first {cap_s // 60} minutes of {dur / 60:.0f} (PARTIAL): later bursts are not counted.", 89, "sound")
    sound_events_channels(look, x if isinstance(x, list) else [x], sr)
    return True


def pcm16_channels(look, data, ch):
    """Interleaved 16-bit samples (array('h')) -> one float sequence in -1..1 per channel (up to 8; the first only without numpy)."""
    np = look.mod("numpy")
    if np is not None:
        a = np.frombuffer(data, dtype=np.int16)
        return [a[k::ch].astype(np.float32) / 32768.0 for k in range(min(ch, 8))]
    return [array.array("f", (v / 32768.0 for v in data[::ch]))]


def palette_line(look, pal, pri=55):
    """Every palette entry as 'index=rrggbb', 16 per line (index from 0), so a question about entry N is answered from a print."""
    if not pal:
        return
    ents = [f"{i}={r:02x}{g:02x}{b:02x}" for i, (r, g, b) in enumerate(pal)]
    look.line(f"Palette, every entry ({len(ents)}; index from 0 = rrggbb, 16 per line):\n" + "\n".join(" ".join(ents[k:k + 16]) for k in range(0, len(ents), 16)), pri, "pixels")


def pil_pixel_facts(look, im):
    """Exact pixel facts of the first frame of a Pillow image (palette size, colours, transparency); a picture over 40 megapixels is a Not-looked-at row."""
    w, h = im.size
    if w * h > 40_000_000:
        look.skip(f"exact colour count of a {w}x{h} picture", f"{w * h / 1e6:.0f} megapixels is over the 40 the look decodes", "PIL")
        return
    pal = None
    if im.mode == "P":
        try:
            pal = len(im.getpalette() or []) // 3
        except Exception:
            pal = None
        if pal:
            look.line(f"Palette picture: {pal} palette entries ({len(set(im.getdata())):,} of them used)" + (f"; transparent index {im.info['transparency']}" if isinstance(im.info.get("transparency"), int) else "") + ".", 90, "pixels")
            pl = im.getpalette()[:3 * pal]
            palette_line(look, [tuple(pl[k:k + 3]) for k in range(0, len(pl) - 2, 3)])
    rgba = im.convert("RGBA") if ("A" in im.mode or "transparency" in im.info) else None
    rgb = (rgba or im).convert("RGB")
    alpha = rgba.getchannel("A").tobytes() if rgba is not None else None
    pixel_facts(look, w, h, rgb.tobytes(), alpha)
