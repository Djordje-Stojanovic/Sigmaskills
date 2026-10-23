"""SigmaDeepLook --ask "pixel x,y": the exact colour of one pixel of a still picture (fix round 11). Stdlib, plus Pillow when present.

A pixel is a single-record lookup, so the look prints where to ask (`route_line`) and `--ask` answers it. Coordinates count from the top-left
corner of the picture as displayed, from 0 (a JPEG or TIFF with an EXIF orientation is turned first; a bottom-up BMP is read the right way up).
The answer is R,G,B, the hex colour, the alpha when the picture has one, and the palette index when the picture is indexed. A pixel outside the
picture is answered with the size, never with a guess. Pillow reads every format it knows (PNG, GIF, JPEG, TGA, TIFF, WebP, RLE BMP ...); without it
(or with --no-tools) the standard library reads uncompressed BMP and PCX.
"""
import re

import dl_asklang as AL
import dl_core as core

WORDS = re.compile(r"\b(pixel|pixels|px|colou?r|rgb|hex|value)\b", re.I)
AT_PAIR = re.compile(r"(?:\b(?:pixel|px|at)\b|\()\s*\(?\s*(\d+)\s*[,;/]\s*(\d+)", re.I)
LABEL_X = re.compile(r"\b(?:x|col|column)\s*[=:]?\s*(\d+)\b", re.I)
LABEL_Y = re.compile(r"\b(?:y|row)\s*[=:]?\s*(\d+)\b", re.I)
PAIR_ONLY = re.compile(r"\(\s*\d+\s*[,;/]\s*\d+\s*\)")
READ_CAP = 256 << 20


def parse_pixel(q):
    """'colour at x=520, y=600' / 'pixel 5,7' / 'pixel (5, 7)' / 'column 5, row 7' -> (x, y, from_bottom), or None when the question names no pixel."""
    q = AL.unquote_numbers(q)   # pixel "336,519" and x="336" are the numbers without the quotes
    bottom = bool(re.search(r"\bbottom\b", q, re.I))
    mx, my = LABEL_X.search(q), LABEL_Y.search(q)
    if mx and my and WORDS.search(q):
        return int(mx.group(1)), int(my.group(1)), bottom
    m = AT_PAIR.search(q)
    if m and (WORDS.search(q) or PAIR_ONLY.search(q)):   # on a picture "(336,519)" alone names a pixel; a bare "at 3,4" needs a pixel word
        return int(m.group(1)), int(m.group(2)), bottom
    return None


def route_line(look, w, h, orientation=1, indexed=False):
    """The print line that says a pixel can be asked, with the picture size as displayed."""
    if orientation in (5, 6, 7, 8):
        w, h = h, w
    look.line(f'Ask a pixel: --ask "pixel X,Y" returns R,G,B, hex{" and palette index" if indexed else ""} (X 0-{w - 1} from the left, Y 0-{h - 1} from the top; image is {w} x {h} px).',
              90, "pixels")


def _hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------------------------- Pillow
def pil_pixel(path, x, y, bottom):
    """-> (w, h, info) where info is None for a pixel outside the picture, else a dict {rgb, alpha, index, entries, mode, frames}."""
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        frames = getattr(im, "n_frames", 1)
        orient = im.getexif().get(274, 1)
        w, h = im.size
        if orient in (5, 6, 7, 8):
            w, h = h, w
        if bottom:
            y = h - 1 - y
        if not (0 <= x < w and 0 <= y < h):
            return w, h, None
        pic = ImageOps.exif_transpose(im) if orient in (2, 3, 4, 5, 6, 7, 8) else im
        pic.load()
        mode = pic.mode
        one = pic.crop((x, y, x + 1, y + 1))
        info = {"mode": mode, "frames": frames, "alpha": None, "index": None, "entries": None}
        if mode in ("I", "F") or mode.startswith("I;"):
            v = one.getpixel((0, 0))
            info["gray"] = v
            return w, h, info
        if mode == "P":
            info["index"] = one.getpixel((0, 0))
            info["entries"] = len(pic.getpalette() or []) // 3
        rgba = one.convert("RGBA").getpixel((0, 0))
        info["rgb"] = rgba[:3]
        if "A" in mode or "a" in mode or "transparency" in pic.info:
            info["alpha"] = rgba[3]
        return w, h, info


# ---------------------------------------------------------------------------------------------- standard library: BMP and PCX
def _bmp(raw, x, y, bottom):
    import dl_legacy as L
    i = L.bmp_info(raw)
    if not i:
        return None
    w, h = i["w"], i["h"]
    if bottom:
        y = h - 1 - y
    if not (0 <= x < w and 0 <= y < h):
        return w, h, None
    bpp = i["bpp"]
    if i["comp"] not in (0, 3) or i["planes"] != 1 or bpp not in (1, 4, 8, 24, 32):
        raise ValueError(f"BMP variant (compression {L.BMP_COMPRESSION.get(i['comp'], i['comp'])}, {bpp} bits) needs Pillow")
    stride = ((w * bpp + 31) // 32) * 4
    at = i["offset"] + (y if i["top_down"] else h - 1 - y) * stride
    row = raw[at:at + stride]
    if len(row) < (w * bpp + 7) // 8:
        raise ValueError("the pixel data is cut short before this row")
    info = {"mode": f"{bpp}-bit BMP", "frames": 1, "alpha": None, "index": None, "entries": None}
    if bpp in (24, 32):
        info["rgb"] = (row[bpp // 8 * x + 2], row[bpp // 8 * x + 1], row[bpp // 8 * x])
        if bpp == 32:
            info["alpha"] = row[4 * x + 3]
        return w, h, info
    per = 8 // bpp
    v = (row[x // per] >> (8 - bpp - (x % per) * bpp)) & ((1 << bpp) - 1)
    pal = L.bmp_palette(raw, i)
    info["index"], info["entries"] = v, len(pal)
    info["rgb"] = pal[v] if v < len(pal) else (0, 0, 0)
    return w, h, info


def _pcx(raw, x, y, bottom):
    import dl_legacy as L
    i = L.pcx_info(raw)
    if not i:
        return None
    w, h, planes, bpl, bpp = i["w"], i["h"], i["planes"], i["bpl"], i["bpp"]
    if bottom:
        y = h - 1 - y
    if not (0 <= x < w and 0 <= y < h):
        return w, h, None
    if not ((bpp == 8 and planes in (1, 3)) or (bpp * planes <= 8 and bpp in (1, 2, 4, 8))) or bpl * planes > 1 << 20:
        raise ValueError("PCX variant needs Pillow")
    need = bpl * planes * (y + 1)
    data, pos, end = bytearray(), 128, len(raw) - (769 if i["has_vga_palette"] else 0)
    while pos < end and len(data) < need:
        b = raw[pos]
        pos += 1
        if b >= 0xC0:
            if pos >= end:
                break
            data += raw[pos:pos + 1] * (b & 0x3F)
            pos += 1
        else:
            data.append(b)
    if len(data) < need:
        raise ValueError("the pixel data is cut short before this row")
    row = data[bpl * planes * y:bpl * planes * (y + 1)]
    info = {"mode": f"{bpp * planes}-bit PCX", "frames": 1, "alpha": None, "index": None, "entries": None}
    if planes == 3 and bpp == 8:
        info["rgb"] = (row[x], row[bpl + x], row[2 * bpl + x])
        return w, h, info
    idx = 0
    for p in range(planes):
        byte = row[p * bpl + x * bpp // 8]
        idx |= ((byte >> (8 - bpp - (x * bpp) % 8)) & ((1 << bpp) - 1)) << (p * bpp)
    info["index"] = idx
    if i["has_vga_palette"]:
        pal = L.pcx_palette(raw, i)
        info["entries"], info["rgb"] = len(pal), pal[idx]
    elif bpp * planes <= 4:
        info["entries"], info["rgb"] = 16, tuple(raw[16 + 3 * idx:19 + 3 * idx]) if idx < 16 else (0, 0, 0)
    else:
        info["entries"], info["rgb"] = None, (idx, idx, idx)
    return w, h, info


def std_pixel(path, subtype, x, y, bottom):
    with open(path, "rb") as fh:
        raw = fh.read(READ_CAP)
    got = _bmp(raw, x, y, bottom) if subtype == "bmp" else _pcx(raw, x, y, bottom)
    if got is None:
        raise ValueError(f"the {subtype} header could not be read")
    return got


# ---------------------------------------------------------------------------------------------- the --ask hook
def try_ask(q, path, lj, no_tools=False):
    """-> the answer text for a pixel question about a still picture, or None when the question is something else."""
    if lj.get("type") != "image" or lj.get("subtype") in (None, "svg"):
        return None
    pq = parse_pixel(q)
    if not pq:
        return None
    x, y, bottom = pq
    lines = [f"--ask {q!r}"]
    try:
        if not no_tools and core.have_module("PIL"):
            w, h, info = pil_pixel(path, x, y, bottom)
            via = "Pillow"
        elif lj.get("subtype") in ("bmp", "pcx"):
            w, h, info = std_pixel(path, lj["subtype"], x, y, bottom)
            via = "the standard library"
        else:
            return "\n".join(lines + [f"Answer: not read: a {lj.get('subtype')} picture needs Pillow ({'disabled by --no-tools' if no_tools else 'not installed'}): pip install pillow."])
    except Exception as e:
        return "\n".join(lines + [f"Answer: not read: {type(e).__name__}: {e}"[:300] + " (the picture is damaged or in a variant this reader does not decode)."])
    where = f"counted from the top-left corner of the picture as displayed{' (y from the bottom, as asked)' if bottom else ''}; picture is {w} x {h} px"
    if info is None:
        return "\n".join(lines + [f"Answer: none: x={x}, y={y} is outside the picture, which is {w} x {h} px (x 0-{w - 1} from the left, y 0-{h - 1} from the top)."])
    if "gray" in info:
        return "\n".join(lines + [f"Pixel x={x}, y={y} ({where}; mode {info['mode']}, read with {via}):", f"Answer: gray value {info['gray']}"])
    r, g, b = info["rgb"]
    tail = (f"; alpha {info['alpha']}" if info["alpha"] is not None else "") + (f"; palette index {info['index']}" + (f" of {info['entries']} entries" if info["entries"] else "") if info["index"] is not None else "")
    note = f"; frame 1 of {info['frames']}" if info["frames"] > 1 else ""
    return "\n".join(lines + [f"Pixel x={x}, y={y} ({where}; mode {info['mode']}, read with {via}{note}):", f"Answer: {r},{g},{b} ({_hex(r, g, b)}){tail}"])
