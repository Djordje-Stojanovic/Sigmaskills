"""SigmaDeepLook --ask "how many pixels have the colour RGB (r, g, b)": an exact colour count over a still picture (fix round 14). Pillow, or the
standard library for BMP and PCX.

A colour is named three ways: RGB numbers (`RGB (30, 170, 180)`, `rgb(30,170,180)`, `colour (30, 170, 180)`), a hex code (`#1eaab4`), or a
palette index (`palette index 8`). Every pixel of the first frame is counted (alpha is ignored and said so). The answer is the count, the
share of all pixels, the hex code and the palette index; a colour that does not occur is answered with 0. "colour table" lists every colour of a
picture that has up to 256, largest first, with its exact count. A pixel position (`pixel 30,17`, `x=5, y=9`) is not a colour: dl_pixel answers it.
"""
import re
from collections import Counter

import dl_core as core

COUNT_WORDS = re.compile(r"\b(how many|number of|count|total|share|percent\w*|proportion|fraction)\b", re.I)
COLOUR_WORDS = re.compile(r"\b(colou?rs?|rgb|hex|palette|shade)\b", re.I)
TUPLE = re.compile(r"\(\s*(\d{1,3})\s*[,;]\s*(\d{1,3})\s*[,;]\s*(\d{1,3})\s*\)")
AFTER_WORD = re.compile(r"\b(?:rgb|colou?r)\b\W{0,3}(\d{1,3})\s*[,;/ ]\s*(\d{1,3})\s*[,;/ ]\s*(\d{1,3})\b", re.I)
HEX = re.compile(r"(?:#|\b0x|\bhex\w*\W{0,3}#?|\bcolou?r\W{0,3}#?)([0-9a-f]{6})\b", re.I)
INDEX = re.compile(r"\b(?:palette|colou?r)\s+(?:index|entry|slot|number|no\.?|position)\s*[=:#]?\s*(\d+)\b|\b(?:index|entry)\s*[=:#]?\s*(\d+)\s+of\s+the\s+palette\b", re.I)
TABLE = re.compile(r"\b(?:colou?r|palette)\s+(?:table|histogram|list|counts|usage|summary)\b|\b(?:list|show)\s+(?:all|every|each)\s+(?:the\s+)?(?:palette\s+)?colou?rs?\b", re.I)
PIXEL_POS = re.compile(r"\bpixel\s*\(?\s*\d+\s*[,;/]\s*\d+|\b(?:x|col|column)\s*[=:]\s*\d+\b.*\b(?:y|row)\s*[=:]\s*\d+", re.I)
CAP_PIXELS = 100_000_000
PURE_CAP = 4_000_000


def hexc(c):
    return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"


def parse(q):
    """-> {'kind': 'rgb'|'hex'|'index'|'table', ...} when the question names a colour to count or asks for the colour table, else None."""
    if not COLOUR_WORDS.search(q) and not HEX.search(q):
        return None
    m = INDEX.search(q)
    if m:
        return {"kind": "index", "index": int(m.group(1) or m.group(2))}
    m = AFTER_WORD.search(q) or TUPLE.search(q)
    if m:
        rgb = tuple(int(g) for g in m.groups())
        if max(rgb) <= 255:
            return {"kind": "rgb", "rgb": rgb}
    for m in HEX.finditer(q):
        h = m.group(1)
        coded = m.group(0).startswith(("#", "0x")) or "hex" in m.group(0).lower()
        if not coded and (h.isdigit() or h.isalpha()):
            continue   # after the bare word "colour", six digits are a number and six letters a word (decade, facade), not a code
        return {"kind": "hex", "rgb": tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))}
    if TABLE.search(q):
        return {"kind": "table"}
    return None


def wants_colour(q):
    """True when the question is a colour count or table (not the colour of one pixel position)."""
    spec = parse(q)
    if not spec:
        return None
    if PIXEL_POS.search(q) and not COUNT_WORDS.search(q):
        return None
    return spec


# ---------------------------------------------------------------------------------------------- reading
def pillow_counts(path, spec):
    """-> dict(w, h, mode, frames, alpha, idx, pal, table, target) read with Pillow. `table` is {rgb: count} for a picture of up to 256 colours else None;
    `target` is the count of spec['rgb'] when the question names an RGB colour."""
    from PIL import Image, ImageChops
    with Image.open(path) as im:
        w, h = im.size
        if w * h > CAP_PIXELS:
            raise ValueError(f"{w * h:,} pixels is over the {CAP_PIXELS:,} that are counted")
        mode, frames = im.mode, getattr(im, "n_frames", 1)
        alpha = "A" in mode or "transparency" in im.info
        im.load()
        idx = pal = table = None
        if mode == "P":
            raw_pal = im.getpalette() or []
            pal = [tuple(raw_pal[k:k + 3]) for k in range(0, len(raw_pal) - 2, 3)]
            hist = im.histogram()[:256]
            idx = Counter({i: c for i, c in enumerate(hist) if c})
            pal += [(0, 0, 0)] * (max(idx, default=-1) + 1 - len(pal))
            table = Counter()
            for i, c in idx.items():
                table[pal[i]] += c
        else:
            rgb = im.convert("RGB")
            got = rgb.getcolors(maxcolors=256)
            table = Counter({c: n for n, c in got}) if got is not None else None
        target = None
        if spec.get("rgb") is not None:
            if table is not None:
                target = table.get(spec["rgb"], 0)
            else:   # a photograph-like picture: three channel masks multiplied, counted by the histogram
                masks = [ch.point(lambda v, t=t: 255 if v == t else 0) for ch, t in zip(rgb.split(), spec["rgb"])]
                both = ImageChops.multiply(ImageChops.multiply(masks[0], masks[1]), masks[2])
                target = both.histogram()[255]
    return {"w": w, "h": h, "mode": mode, "frames": frames, "alpha": alpha, "idx": idx, "pal": pal, "table": table, "target": target, "via": "Pillow"}


def stdlib_counts(path, subtype, spec):
    """BMP and PCX without Pillow -> the same dict as pillow_counts (no index counts)."""
    import dl_legacy as L
    raw = path.read_bytes() if path.stat().st_size <= (256 << 20) else None
    if raw is None:
        raise ValueError("the file is over 256 MB: Pillow is needed")
    if subtype == "bmp":
        i = L.bmp_info(raw)
        dec = L.decode_bmp(raw, i) if i else None
        pal = L.bmp_palette(raw, i) if i else []
    else:
        i = L.pcx_info(raw)
        dec = L.decode_pcx(raw, i) if i else None
        pal = (L.pcx_palette(raw, i) or ([tuple(raw[16 + 3 * k:19 + 3 * k]) for k in range(16)] if i["bpp"] * i["planes"] <= 4 else [])) if i else []
    if not dec:
        raise ValueError(f"this {subtype} variant is not decoded without Pillow")
    w, h, rgb, alpha = dec
    if w * h > PURE_CAP:
        raise ValueError(f"{w * h:,} pixels is over the {PURE_CAP:,} the standard library counts in reasonable time: Pillow is needed")
    full = Counter(zip(rgb[0::3], rgb[1::3], rgb[2::3]))
    target = full.get(spec["rgb"], 0) if spec.get("rgb") is not None else None
    return {"w": w, "h": h, "mode": f"{i['bpp']}-bit {subtype.upper()}" if subtype == "bmp" else f"{i['bpp'] * i['planes']}-bit PCX", "frames": 1, "alpha": alpha is not None,
            "idx": None, "pal": pal or None, "table": full if len(full) <= 256 else None, "target": target, "via": "the standard library"}


def read(path, subtype, spec, no_tools):
    if not no_tools and core.have_module("PIL"):
        return pillow_counts(path, spec)
    if subtype in ("bmp", "pcx"):
        return stdlib_counts(path, subtype, spec)
    raise ValueError(f"a {subtype} picture needs Pillow ({'disabled by --no-tools' if no_tools else 'not installed'}): pip install pillow")


# ---------------------------------------------------------------------------------------------- the answer
def answer(q, spec, data):
    n = data["w"] * data["h"]
    pal, idx, table = data["pal"], data["idx"], data["table"]
    head = f"Colour count (every pixel of the first frame counted with {data['via']}; picture is {data['w']} x {data['h']} px = {n:,} pixels, mode {data['mode']}"
    head += f"; frame 1 of {data['frames']}" if data["frames"] > 1 else ""
    head += "; alpha ignored)" if data["alpha"] else ")"
    lines = [head + ":"]
    kind = spec["kind"]
    if kind == "table":
        if table is None:
            return lines + ["Answer: more than 256 distinct colours: no colour table (ask for one colour: \"how many pixels have colour RGB (r, g, b)\")."]
        rows = sorted(table.items(), key=lambda kv: (-kv[1], kv[0]))
        index_of = {}
        if pal:
            for i, c in enumerate(pal):
                index_of.setdefault(c, []).append(i)
        lines.append(f"Answer: {len(rows):,} distinct colours in {n:,} pixels; the table below lists them largest first (index = palette index when the picture is indexed).")
        for c, k in rows[:256]:
            at = index_of.get(c)
            lines.append(f"  {hexc(c)} RGB ({c[0]}, {c[1]}, {c[2]})" + (f" index {', '.join(map(str, at))}" if at else "") + f": {k:,} pixels ({100.0 * k / n:.2f} %)")
        return lines
    if kind == "index":
        i = spec["index"]
        if not pal:
            return lines + [f"Answer: not answered: this picture has no palette (mode {data['mode']}); name the colour as RGB or hex instead."]
        if i >= len(pal):
            return lines + [f"Answer: none: palette index {i} is outside the palette, which has {len(pal)} entries (0-{len(pal) - 1})."]
        c = pal[i]
        if idx is not None:
            k = idx.get(i, 0)
            same = [j for j, x in enumerate(pal) if x == c and j != i and idx.get(j)]
            note = f"; other palette indexes with the same colour: {', '.join(map(str, same))}" if same else ""
            lines.append(f"Answer: {k:,} pixels ({100.0 * k / n:.2f} %) use palette index {i} = RGB ({c[0]}, {c[1]}, {c[2]}) = {hexc(c)}{note}")
            return lines
        k = table.get(c, 0) if table is not None else 0
        lines.append(f"Answer: {k:,} pixels ({100.0 * k / n:.2f} %) have the colour of palette index {i} = RGB ({c[0]}, {c[1]}, {c[2]}) = {hexc(c)} "
                     "(counted by colour: every palette entry with this colour is included)")
        return lines
    c = spec["rgb"]
    k = data["target"] or 0
    which = ""
    if pal and idx is not None:
        at = [j for j, x in enumerate(pal) if x == c and idx.get(j)]
        which = f"; palette index {', '.join(map(str, at))}" if at else ""
    if k:
        lines.append(f"Answer: {k:,} pixels ({100.0 * k / n:.2f} %) have exactly the colour RGB ({c[0]}, {c[1]}, {c[2]}) = {hexc(c)}{which}; of {n:,} pixels in all")
    else:
        near = f"; the picture holds {len(table):,} distinct colours (ask \"colour table\" to list them)" if table is not None else "; the picture holds more than 256 distinct colours"
        lines.append(f"Answer: 0 pixels (0.00 %) have exactly the colour RGB ({c[0]}, {c[1]}, {c[2]}) = {hexc(c)}; of {n:,} pixels in all{near}")
    return lines


def try_ask(q, path, lj, no_tools=False):
    """-> the answer text for a colour count question about a still picture, or None when the question is something else."""
    if lj.get("type") != "image" or lj.get("subtype") in (None, "svg"):
        return None
    spec = wants_colour(q)
    if not spec:
        return None
    head = f"--ask {q!r}"
    try:
        data = read(path, lj.get("subtype"), spec, no_tools)
    except Exception as e:   # a damaged picture, or a variant this reader does not decode: named, never a guess
        return "\n".join([head, f"Answer: not read: {type(e).__name__}: {e}"[:300]])
    return "\n".join([head] + answer(q, spec, data))
