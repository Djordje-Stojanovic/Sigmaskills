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


# ------------------------------------------------------------------------------------------ sound
def _stamp(t):
    return f"{int(t // 60)}:{t - 60 * int(t // 60):05.2f}"


def sound_events(look, x, sr, pri=88, drop_below=0.06, merge_gap=0.15, rel_db=30.0):
    """Bursts of sound in mono samples x (floats, -1..1; list, array or numpy array) at sample rate sr. Prints one fact and a burst list."""
    np = look.mod("numpy")
    n = len(x)
    if n < sr // 5 or sr <= 0:
        return
    if np is None and n / sr > SOUND_PURE_CAP_S:
        look.skip("sound bursts (counts and times)", f"{n / sr / 60:.0f} minutes is over the {SOUND_PURE_CAP_S // 60} minutes the standard library reads in reasonable time", "numpy")
        return
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


def pcm16_to_floats(raw):
    """Little-endian 16-bit PCM bytes -> array('f') in -1..1 (pure Python; numpy callers use frombuffer instead)."""
    a = array.array("h")
    a.frombytes(raw[:len(raw) // 2 * 2])
    return array.array("f", (v / 32768.0 for v in a))


def decode_ffmpeg(look, cap_s=1800, sr=8000):
    """The first `cap_s` seconds of the file's audio as mono 16-bit samples at `sr`: -> (floats, sr) or None. Needs ffmpeg."""
    ff = look.tool("ffmpeg")
    if not ff:
        return None
    r = look.run([ff, "-v", "error", "-nostdin", "-i", str(look.path), "-t", str(cap_s), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], timeout=300)
    if r is None or r.returncode != 0 or len(r.stdout) < sr:
        return None
    np = look.mod("numpy")
    if np is not None:
        return np.frombuffer(r.stdout[:len(r.stdout) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0, sr
    return pcm16_to_floats(r.stdout), sr


def bursts_of_file(look, dur=None, cap_s=1800):
    """Decode the file's sound and print its bursts; a file over `cap_s` seconds says how much was read."""
    got = decode_ffmpeg(look, cap_s)
    if got is None:
        return False
    x, sr = got
    if dur and dur > cap_s + 1:
        look.line(f"Sound bursts below cover the first {cap_s // 60} minutes of {dur / 60:.0f} (PARTIAL): later bursts are not counted.", 89, "sound")
    sound_events(look, x, sr)
    return True


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
    rgba = im.convert("RGBA") if ("A" in im.mode or "transparency" in im.info) else None
    rgb = (rgba or im).convert("RGB")
    alpha = rgba.getchannel("A").tobytes() if rgba is not None else None
    pixel_facts(look, w, h, rgb.tobytes(), alpha)
