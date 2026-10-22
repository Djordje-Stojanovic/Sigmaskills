"""SigmaDeepLook readers for older and niche formats that carry their facts in a header (fix round 8, ticket 83 P0.14b.H8). Stdlib only.

Gettext catalogues (text .po/.pot and binary .mo), PCX pictures, Sun/NeXT .au sound, netCDF classic arrays and SPSS .sav files. Each one
reads the header and the dictionary that the format keeps up front, counts everything the file can state, and prints the last record as
well as the first, so a question about the end of the file or about a total is answered from the first print. A part that is not
decoded is named, never guessed.
"""
import re
import struct

import dl_core as core
import dl_prof as P

short = P.short
fmt = P.fmt


# ---------------------------------------------------------------------------------------------- gettext
def _unq(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")


def parse_po(text):
    """-> (entries, obsolete_count). Entry: dict(line, ctx, id, plural, strs, fuzzy, refs). Entry 0 may be the header (id == "")."""
    entries, cur, field, obsolete = [], None, None, 0
    flags_next, refs_next = False, 0

    def close():
        nonlocal cur
        if cur is not None and (cur["id"] is not None):
            entries.append(cur)
        cur = None

    for no, raw in enumerate(text.splitlines(), 1):
        ln = raw.strip()
        if not ln:
            close()
            field = None
            continue
        if ln.startswith("#~"):
            if ln.startswith("#~ msgid ") and not ln.startswith("#~ msgid_plural"):
                obsolete += 1
            continue
        if ln.startswith("#"):
            if cur is not None and cur["id"] is not None:   # a comment after a finished entry opens the next one
                close()
            if ln.startswith("#,") and "fuzzy" in ln:
                flags_next = True
            elif ln.startswith("#:"):
                refs_next += len(ln[2:].split())
            continue
        m = re.match(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+(".*")\s*$', ln)
        if m:
            key = m.group(1)
            if key in ("msgctxt", "msgid") and cur is not None and cur["strs"]:
                close()
            if cur is None:
                cur = {"line": no, "ctx": None, "id": None, "plural": None, "strs": {}, "fuzzy": flags_next, "refs": refs_next}
                flags_next, refs_next = False, 0
            val = _unq(m.group(3))
            if key == "msgctxt":
                cur["ctx"], field = val, ("ctx",)
            elif key == "msgid":
                cur["id"], field = val, ("id",)
            elif key == "msgid_plural":
                cur["plural"], field = val, ("plural",)
            else:
                k = int(m.group(2) or 0)
                cur["strs"][k], field = val, ("strs", k)
            continue
        if ln.startswith('"') and cur is not None and field:
            val = _unq(ln)
            if field[0] == "strs":
                cur["strs"][field[1]] = cur["strs"].get(field[1], "") + val
            else:
                cur[field[0]] = (cur[field[0]] or "") + val
    close()
    return entries, obsolete


def _header_fields(text):
    out = {}
    for ln in text.split("\n"):
        k, sep, v = ln.partition(":")
        if sep and k.strip():
            out[k.strip()] = v.strip()
    return out


def _header_line(h):
    keep = ("Project-Id-Version", "Language", "Content-Type", "Plural-Forms", "POT-Creation-Date", "PO-Revision-Date", "Content-Transfer-Encoding")
    return "; ".join(f"{k}: {short(h[k], 70)}" for k in keep if k in h)


def _entry_text(e):
    s = e["strs"].get(0, "") if e["strs"] else ""
    return f"msgid '{short(e['id'], 60)}' -> '{short(s, 60)}'" + (" [fuzzy]" if e.get("fuzzy") else "")


def po_facts(look, text):
    """Counts and the first and last entries of a gettext .po/.pot text; -> True when the text holds a catalogue."""
    entries, obsolete = parse_po(text)
    hdr = next((e for e in entries if e["id"] == ""), None)
    body = [e for e in entries if e["id"] != ""]
    if not body and not hdr:
        return False

    def done(e):
        vals = [v for v in e["strs"].values()]
        return bool(vals) and all(v != "" for v in vals)
    tr = [e for e in body if done(e)]
    un = [e for e in body if not done(e)]
    fz = [e for e in body if e["fuzzy"]]
    pl = [e for e in body if e["plural"] is not None]
    cx = [e for e in body if e["ctx"] is not None]
    refs = sum(e["refs"] for e in body)
    P.counts(look, [("entries", len(body)), ("translated", len(tr)), ("untranslated", len(un)), ("fuzzy", len(fz)), ("plural entries", len(pl)), ("with context", len(cx)),
                    ("obsolete", obsolete), ("source references", refs or None)], 96, "Gettext catalogue counts")
    look.fact("gettext_entries", len(body))
    if hdr:
        h = _header_fields(hdr["strs"].get(0, ""))
        if h:
            look.line("Catalogue header: " + _header_line(h), 95, "structure")
    if body:
        pct = 100.0 * len(tr) / len(body)
        look.line(f"Gettext catalogue: {len(body):,} entries, {len(tr):,} translated ({pct:.1f} %), {len(un):,} untranslated, {len(fz):,} fuzzy. "
                  f"First entry (line {body[0]['line']}): {_entry_text(body[0])}. Last entry (line {body[-1]['line']}): {_entry_text(body[-1])}.", 94, "structure")
        for name, grp in (("untranslated", un), ("fuzzy", fz), ("plural", pl), ("with context", cx)):
            if grp:
                lines = [e["line"] for e in grp]
                look.line(f"{name.capitalize()} entries at lines: " + ", ".join(str(x) for x in lines[:12]) + (f" ... last at line {lines[-1]}" if len(lines) > 12 else ""), 80, "structure")
        long_ = max(body, key=lambda e: len(e["id"]))
        look.line(f"Longest msgid: {len(long_['id'])} characters (line {long_['line']}): '{short(long_['id'], 80)}'", 60, "structure")
    return True


def look_gettext(look):
    """A binary .mo catalogue: header, entry table, plurals, contexts, untranslated entries, the first, last and Nth entries, and every
    entry in text.md (fix round 9: each table row is checked against the file size; a damaged one is flagged CORRUPT, never guessed)."""
    raw = look.path.read_bytes()
    size = len(raw)
    if size < 28:
        look.flag("CORRUPT", "header", f"{size} bytes; a .mo header needs 28", "not a readable gettext catalogue")
        look.line(f"Gettext .mo file too short for its header ({size} bytes).")
        return
    m = struct.unpack_from("<I", raw, 0)[0]
    if m not in (0x950412DE, 0xDE120495):
        look.flag("CORRUPT", "magic", f"0x{m:08x}", "not the gettext magic number")
        return
    e = "<" if m == 0x950412DE else ">"
    rev, n, oo, to, hs, ho = struct.unpack_from(e + "6I", raw, 4)
    major, minor = rev >> 16, rev & 0xFFFF
    room = max(0, (size - 28) // 16)
    problems = []
    if n > room:
        problems.append(f"{n:,} entries declared, room for at most {room:,}")
    if oo + 8 * min(n, room) > size or to + 8 * min(n, room) > size:
        problems.append(f"entry tables at {oo:,} and {to:,} run past the end of the {size:,}-byte file")
    if hs and ho + 4 * hs > size:
        problems.append(f"hash table ({hs:,} slots at {ho:,}) runs past the end")
    if major > 1:
        problems.append(f"unknown format revision {major}.{minor}")
    look.headline = f"Gettext binary catalogue: {max(0, n - 1):,} entries"
    look.fact("mo_entries", n)
    ents, bad = [], 0
    for i in range(min(n, room, 5_000_000)):
        if oo + 8 * i + 8 > size or to + 8 * i + 8 > size:
            bad += min(n, room) - i
            break
        ol, op = struct.unpack_from(e + "2I", raw, oo + 8 * i)
        tl, tp = struct.unpack_from(e + "2I", raw, to + 8 * i)
        if op + ol > size or tp + tl > size:
            bad += 1
            continue
        ents.append((raw[op:op + ol], raw[tp:tp + tl]))
    if bad:
        problems.append(f"{bad:,} table rows point outside the file")
    if problems:
        look.flag("CORRUPT", "entry table", "; ".join(problems), "the readable rows are listed; the rest is not guessed")
    enc = "utf-8"
    hdr = next((t for o, t in ents if o == b""), b"")
    h = _header_fields(hdr.decode("utf-8", "replace"))
    mm = re.search(r"charset=([\w-]+)", h.get("Content-Type", ""))
    if mm:
        enc = mm.group(1)

    def dec(b):
        try:
            return b.decode(enc, "replace")
        except LookupError:
            return b.decode("utf-8", "replace")
    body = [(o, t) for o, t in ents if o != b""]
    pl = [x for x in body if b"\0" in x[0]]
    cx = [x for x in body if b"\x04" in x[0]]
    un = [x for x in body if not x[1].replace(b"\0", b"").strip()]
    src_words = sum(len(dec(o.split(b"\x04")[-1]).split()) for o, _ in body)
    tr_words = sum(len(dec(t).replace("\0", " ").split()) for _, t in body)
    P.counts(look, [("entries", len(body)), ("table entries incl. header", n), ("plural entries", len(pl)), ("with context", len(cx)),
                    ("untranslated (empty msgstr)", len(un)), ("source words", src_words), ("translation words", tr_words), ("hash table size", hs)], 96,
             "Gettext binary catalogue counts")
    look.line(f"Gettext binary catalogue: format revision {major}.{minor}, {'little' if e == '<' else 'big'}-endian, {len(body):,} entries ({n:,} in the table with the header), "
              f"{len(pl):,} plural, {len(cx):,} with context, charset {enc}; tables: msgids at byte {oo:,}, translations at {to:,}, hash {hs:,} slots at {ho:,}; "
              f"file {size:,} bytes" + (f"; {bad} unreadable table rows" if bad else "") + ".", 94, "structure")
    if h:
        look.line("Catalogue header: " + _header_line(h), 95, "structure")
    if not body:
        look.step("Gettext .mo header and entries", "stdlib")
        return

    def show(x, w=60):
        o, t = x
        o = dec(o).replace("\x04", " | ").replace("\0", " / ")
        return f"'{short(o, w)}' -> '{short(dec(t).replace(chr(0), ' / '), w)}'"
    hdr_first = bool(ents) and ents[0][0] == b""
    look.line(f"First entry (table order, sorted by msgid; #1 is the first after the header{', which is table row 0' if hdr_first else ''}): {show(body[0])}. "
              f"Last entry (#{len(body):,}): {show(body[-1])}. Last 3 entries: " + "; ".join(show(x) for x in body[-3:]) + ".", 93, "tail")
    if un:
        idx = [i for i, x in enumerate(body, 1) if not x[1].replace(b"\0", b"").strip()]
        look.line(f"Untranslated entries (empty msgstr), by #: " + ", ".join(str(i) for i in idx[:20]) + (f" ... last #{idx[-1]}" if len(idx) > 20 else ""), 80, "structure")
    import dl_textx
    dl_textx.marks_lines(look, len(body), lambda k: f"#{k} {show(body[k - 1], 50)}", "entry", 84, f"Entries at fixed positions ({len(body):,} entries; #k = the k-th entry after the header)")
    look.write_text("text.md", "\n".join(f"#{i} {show(x, 200)}" for i, x in enumerate(body, 1)), "every entry in table order: #, msgid (context | msgid, plural forms split by /) -> msgstr", value=6)
    look.step("Gettext .mo header and entries", "stdlib")


# ---------------------------------------------------------------------------------------------- BMP and PCX pictures
PCX_VERSIONS = {0: "2.5", 2: "2.8 with palette", 3: "2.8 without palette", 4: "Paintbrush for Windows", 5: "3.0 or later"}
BMP_COMPRESSION = {0: "none (BI_RGB)", 1: "RLE 8-bit", 2: "RLE 4-bit", 3: "bit fields", 4: "JPEG", 5: "PNG"}


def bmp_info(raw):
    if len(raw) < 26 or raw[:2] != b"BM":
        return None
    fsize, _r1, _r2, off = struct.unpack_from("<IHHI", raw, 2)
    hs = struct.unpack_from("<I", raw, 14)[0]
    if hs == 12:
        w, h, planes, bpp = struct.unpack_from("<hhHH", raw, 18)
        comp, used, imp, xp, yp, isize = 0, 0, 0, 0, 0, 0
    elif hs >= 40 and len(raw) >= 54:
        w, h, planes, bpp, comp, isize, xp, yp, used, imp = struct.unpack_from("<iiHHIIiiII", raw, 18)
    else:
        return None
    return {"file_size": fsize, "offset": off, "header": hs, "w": w, "h": abs(h), "top_down": h < 0, "planes": planes, "bpp": bpp, "comp": comp, "image_size": isize,
            "xppm": xp, "yppm": yp, "used": used, "important": imp}


def pcx_info(raw):
    if len(raw) < 128 or raw[0] != 10:
        return None
    ver, enc, bpp = raw[1], raw[2], raw[3]
    x0, y0, x1, y1, hd, vd = struct.unpack_from("<6H", raw, 4)
    planes, bpl, pinfo = raw[65], struct.unpack_from("<H", raw, 66)[0], struct.unpack_from("<H", raw, 68)[0]
    if ver not in PCX_VERSIONS or enc != 1 or bpp not in (1, 2, 4, 8) or x1 < x0 or y1 < y0 or planes < 1:
        return None
    return {"version": ver, "bpp": bpp, "w": x1 - x0 + 1, "h": y1 - y0 + 1, "hdpi": hd, "vdpi": vd, "planes": planes, "bpl": bpl, "pinfo": pinfo,
            "has_vga_palette": len(raw) >= 769 and raw[-769] == 12 and ver == 5 and bpp == 8 and planes == 1}


def pcx_plausible(h, size):
    """A header that is internally consistent: the magic byte alone (0x0A) opens too many files."""
    if len(h) < 70 or size < 129:
        return False
    i = pcx_info(h + b"\0" * max(0, 128 - len(h)))
    return bool(i and i["planes"] in (1, 3, 4) and i["bpl"] >= (i["w"] * i["bpp"] + 7) // 8 and i["bpl"] <= i["w"] * 2 + 16)


def decode_bmp(raw, i):
    """-> (w, h, rgb bytes, alpha bytes or None) for uncompressed 1/4/8/24/32-bit bitmaps (top row first); None for other variants."""
    w, h, bpp = i["w"], i["h"], i["bpp"]
    if i["comp"] not in (0, 3) or i["planes"] != 1 or w <= 0 or h <= 0 or w * h > 40_000_000:
        return None
    pal = []
    if bpp <= 8:
        n = i["used"] or (1 << bpp)
        at = 14 + i["header"]
        step = 3 if i["header"] == 12 else 4
        pal = [(raw[at + k * step + 2], raw[at + k * step + 1], raw[at + k * step]) for k in range(n) if at + k * step + 2 < len(raw)]
    stride = ((w * bpp + 31) // 32) * 4
    body = raw[i["offset"]:]
    if len(body) < stride * h:
        return None
    rgb, alpha = bytearray(), bytearray() if bpp == 32 else None
    for y in range(h):
        row = body[(y if i["top_down"] else h - 1 - y) * stride:][:stride]
        if bpp == 24:
            rgb += b"".join(bytes((row[3 * x + 2], row[3 * x + 1], row[3 * x])) for x in range(w))
        elif bpp == 32:
            for x in range(w):
                b, g, r, a = row[4 * x:4 * x + 4]
                rgb += bytes((r, g, b))
                alpha.append(a)
        elif bpp == 8:
            rgb += b"".join(bytes(pal[v]) if v < len(pal) else b"\0\0\0" for v in row[:w])
        elif bpp in (1, 4):
            per = 8 // bpp
            for x in range(w):
                v = (row[x // per] >> (8 - bpp - (x % per) * bpp)) & ((1 << bpp) - 1)
                rgb += bytes(pal[v]) if v < len(pal) else b"\0\0\0"
        else:
            return None
    return w, h, bytes(rgb), (bytes(alpha) if alpha is not None else None)


def decode_pcx(raw, i):
    w, h, planes, bpl, bpp = i["w"], i["h"], i["planes"], i["bpl"], i["bpp"]
    if w * h > 40_000_000 or not ((bpp == 8 and planes in (1, 3)) or (bpp == 1 and planes == 1)):
        return None
    data, pos, end = bytearray(), 128, len(raw) - (769 if i["has_vga_palette"] else 0)
    need = bpl * planes * h
    while pos < end and len(data) < need:
        b = raw[pos]
        pos += 1
        if b >= 0xC0:
            n = b & 0x3F
            if pos >= end:
                break
            data += raw[pos:pos + 1] * n
            pos += 1
        else:
            data.append(b)
    if len(data) < need:
        return None
    pal = []
    if bpp == 8 and planes == 1:
        if not i["has_vga_palette"]:
            pal = [(k, k, k) for k in range(256)]
        else:
            q = len(raw) - 768
            pal = [(raw[q + 3 * k], raw[q + 3 * k + 1], raw[q + 3 * k + 2]) for k in range(256)]
    rgb = bytearray()
    for y in range(h):
        row = data[y * bpl * planes:(y + 1) * bpl * planes]
        if planes == 3:
            r, g, b = row[0:w], row[bpl:bpl + w], row[2 * bpl:2 * bpl + w]
            for x in range(w):
                rgb += bytes((r[x], g[x], b[x]))
        elif bpp == 8:
            rgb += b"".join(bytes(pal[v]) for v in row[:w])
        else:
            for x in range(w):
                v = (row[x // 8] >> (7 - x % 8)) & 1
                rgb += b"\xff\xff\xff" if v else b"\0\0\0"
    return w, h, bytes(rgb), None


def picture_header(look, native_pixels=False):
    """Header facts of a BMP or PCX (bits per pixel, planes, palette, compression, resolution) and, with `native_pixels`, exact pixel facts read without Pillow."""
    st = look.subtype
    if st not in ("bmp", "pcx"):
        return
    try:
        raw = look.path.read_bytes() if look.size <= (256 << 20) else look.path.read_bytes()[:1 << 20]
    except OSError:
        return
    import dl_sig
    if st == "bmp":
        i = bmp_info(raw)
        if not i:
            return
        pal = i["used"] or ((1 << i["bpp"]) if i["bpp"] <= 8 else 0)
        look.line(f"BMP header: {i['w']}x{i['h']} px, {i['bpp']} bits per pixel, {i['planes']} plane, compression {BMP_COMPRESSION.get(i['comp'], i['comp'])}, "
                  f"{pal} colours in the palette" + (f" ({i['important']} important)" if i["important"] else "") + f", {'top-down' if i['top_down'] else 'bottom-up'} rows, "
                  f"info header {i['header']} bytes, pixel data at offset {i['offset']}, resolution {i['xppm']} x {i['yppm']} pixels per metre"
                  + (f" ({i['xppm'] * 0.0254:.0f} dpi)" if i["xppm"] else "") + ".", 93, "header")
        dec = decode_bmp(raw, i) if native_pixels else None
    else:
        i = pcx_info(raw)
        if not i:
            return
        look.line(f"PCX header: version {i['version']} ({PCX_VERSIONS[i['version']]}), {i['w']}x{i['h']} px, {i['bpp']} bits per pixel, {i['planes']} colour plane{'s' if i['planes'] != 1 else ''} "
                  f"(colour depth {i['bpp'] * i['planes']} bits), {i['bpl']} bytes per scan-line plane, RLE compression, resolution {i['hdpi']} x {i['vdpi']} dpi, "
                  + ("256-colour palette at the end of the file" if i["has_vga_palette"] else "16-colour header palette" if i["bpp"] * i["planes"] <= 4 else "no separate palette") + ".", 93, "header")
        look.headline = f"PCX picture {i['w']}x{i['h']}, {i['bpp'] * i['planes']}-bit"
        dec = decode_pcx(raw, i) if native_pixels else None
    if dec:
        w, h, rgb, alpha = dec
        dl_sig.pixel_facts(look, w, h, rgb, alpha, source="decoded with the standard library")
    elif native_pixels:
        look.skip("pixel facts of this variant", f"the {st} variant is not decoded without Pillow", "PIL")


def _guarded(look, name, fn):
    """Run a header reader; a damaged file gives a CORRUPT flag, not an internal error."""
    try:
        fn(look)
    except (ValueError, struct.error, IndexError, OverflowError, MemoryError) as e:
        look.flag("CORRUPT", name, f"{type(e).__name__}: {e}"[:120], f"the {name} file is damaged")


def look_netcdf(look):
    import dl_netcdf
    _guarded(look, "netCDF", dl_netcdf.look_netcdf)


def look_sav(look):
    import dl_sav
    _guarded(look, "SPSS", dl_sav.look_sav)
