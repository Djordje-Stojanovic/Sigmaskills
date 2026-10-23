"""SigmaDeepLook: legacy Word .doc files read with the standard library (fix round 9, ticket 83 P0.14b). Nothing is run or converted.

A Word 97-2003 file is an OLE compound file. Its `WordDocument` stream starts with the File Information Block (FIB: version, language,
flags, the character counts of each text part, and where the tables live); the `0Table`/`1Table` stream holds the piece table (which
bytes of WordDocument hold which characters, 8-bit or UTF-16), the paragraph property pages (style, in-table, row-end marks) and the
style sheet (which style is "heading 1" ... "heading 9"). The `SummaryInformation` property sets hold title, author, dates and the counts
Word saved. Word 6 and Word 95 files keep their text as 8-bit bytes between two offsets of the FIB.

`read(data)` -> a dict with the text parts, paragraphs (text, style, level, in table, row end), tables, header fields and properties;
raises `DocError` on a file it cannot read. `look_doc(look)` puts the facts into a look and -> True when the text was read.
"""
import bisect
import re
import struct
from datetime import datetime, timedelta, timezone

import dl_prof as P
import dl_vba

short = P.short


class DocError(Exception):
    pass


LANG = {0x0409: "en-US", 0x0809: "en-GB", 0x0407: "de-DE", 0x040C: "fr-FR", 0x0410: "it-IT", 0x0C0A: "es-ES", 0x040A: "es-ES (traditional)", 0x0419: "ru-RU",
        0x0415: "pl-PL", 0x0405: "cs-CZ", 0x041A: "hr-HR", 0x081A: "sr-Latn", 0x0C1A: "sr-Cyrl", 0x0413: "nl-NL", 0x0416: "pt-BR", 0x0816: "pt-PT",
        0x0411: "ja-JP", 0x0804: "zh-CN", 0x0404: "zh-TW", 0x0412: "ko-KR", 0x041D: "sv-SE", 0x0406: "da-DK", 0x0414: "nb-NO", 0x040B: "fi-FI",
        0x040E: "hu-HU", 0x0418: "ro-RO", 0x0402: "bg-BG", 0x0408: "el-GR", 0x041F: "tr-TR", 0x0422: "uk-UA", 0x0400: "none"}
NFIB_NEW = {0x00D9: "Word 2000", 0x0101: "Word 2002", 0x010C: "Word 2003", 0x0112: "Word 2007 or later"}
PIDSI = {2: "Title", 3: "Subject", 4: "Author", 5: "Keywords", 6: "Comments", 7: "Template", 8: "Last saved by", 9: "Revision", 10: "Total editing time",
         11: "Last printed", 12: "Created", 13: "Last saved", 14: "Pages", 15: "Words", 16: "Characters", 18: "Application", 19: "Security"}
PIDDSI = {2: "Category", 3: "Presentation format", 5: "Lines", 6: "Paragraphs", 7: "Slides", 8: "Notes", 9: "Hidden slides", 10: "Multimedia clips",
          14: "Manager", 15: "Company", 23: "Application version"}
SPLIT_RE = re.compile(r"[\r\x07]")


# ---------------------------------------------------------------- property sets (SummaryInformation)
def _filetime(v, duration=False):
    if not v:
        return None
    if duration:   # a duration in 100 ns steps
        mins = v // 600_000_000
        return f"{mins // 60} h {mins % 60} min" if mins >= 60 else f"{mins} min"
    try:
        return (datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=v // 10)).strftime("%Y-%m-%d %H:%M UTC")
    except OverflowError:
        return None


def property_set(data, names):
    """The first section of an OLE property-set stream -> {name: value} for the property ids in `names`. Never raises."""
    out = {}
    try:
        if len(data) < 48 or struct.unpack_from("<H", data, 0)[0] != 0xFFFE:
            return out
        off = struct.unpack_from("<I", data, 44)[0]
        _size, count = struct.unpack_from("<II", data, off)
        codepage = "cp1252"
        props = []
        for i in range(min(count, 200)):
            pid, po = struct.unpack_from("<II", data, off + 8 + 8 * i)
            props.append((pid, off + po))
        for pid, p in props:
            if pid == 1:
                cp = struct.unpack_from("<H", data, p + 4)[0]
                codepage = "utf-8" if cp == 65001 else "utf-16-le" if cp == 1200 else f"cp{cp}"
        for pid, p in props:
            if pid not in names:
                continue
            vt = struct.unpack_from("<H", data, p)[0]
            if vt in (2, 18):
                v = struct.unpack_from("<h" if vt == 2 else "<H", data, p + 4)[0]
            elif vt in (3, 19, 22, 23):
                v = struct.unpack_from("<i" if vt in (3, 22) else "<I", data, p + 4)[0]
            elif vt == 30:
                n = struct.unpack_from("<I", data, p + 4)[0]
                raw = data[p + 8:p + 8 + min(n, 4096)]
                try:
                    v = raw.decode(codepage, "replace")
                except LookupError:
                    v = raw.decode("cp1252", "replace")
                v = v.split("\0")[0].strip()
            elif vt == 31:
                n = struct.unpack_from("<I", data, p + 4)[0]
                v = data[p + 8:p + 8 + 2 * min(n, 2048)].decode("utf-16-le", "replace").split("\0")[0].strip()
            elif vt == 64:
                v = _filetime(struct.unpack_from("<Q", data, p + 4)[0], duration=(pid == 10 and names is PIDSI))
            elif vt == 11:
                v = bool(struct.unpack_from("<H", data, p + 4)[0])
            else:
                continue
            if v not in (None, ""):
                out[names[pid]] = v
    except (struct.error, IndexError):
        pass
    return out


def props_line(look, props, dprops, app="the app"):
    """The SummaryInformation and DocumentSummaryInformation values as one step-1 fact (every field, labelled, never cut short)."""
    props = dict(props)
    props.update(dprops)
    v = props.get("Application version")
    if isinstance(v, int) and not isinstance(v, bool):
        props["Application version"] = f"{v >> 16}.{v & 0xFFFF}"
    if not props:
        return
    look.line(f"Document properties (as {app} saved them): " + "; ".join(f"{k}: {short(v, 200) if isinstance(v, str) else (f'{v:,}' if isinstance(v, int) and not isinstance(v, bool) else v)}"
                                                                     for k, v in props.items()), 95, "props")
    look.fact("doc_properties", props)


def ole_props(look, data, app):
    """Document properties of any legacy Office file (PowerPoint, Excel): the two property-set streams of its OLE container."""
    st = dl_vba.read_cfb(data)
    props_line(look, property_set(st.get("\x05SummaryInformation", b""), PIDSI), property_set(st.get("\x05DocumentSummaryInformation", b""), PIDDSI), app)


# ---------------------------------------------------------------- File Information Block
def fib(wd):
    if len(wd) < 0x80:
        raise DocError(f"WordDocument stream is {len(wd)} bytes, too short for its header")
    ident, nfib, _, lid, _, flags = struct.unpack_from("<HHHHHH", wd, 0)
    if ident not in (0xA5EC, 0xA5DC):
        raise DocError(f"WordDocument does not start with the Word signature (0x{ident:04x})")
    f = {"ident": ident, "nfib": nfib, "lid": lid, "flags": flags, "dot": bool(flags & 1), "complex": bool(flags & 4), "has_pic": bool(flags & 8),
         "quick_saves": (flags >> 4) & 0xF, "encrypted": bool(flags & 0x100), "table": "1Table" if flags & 0x200 else "0Table",
         "readonly_rec": bool(flags & 0x400), "far_east": bool(flags & 0x4000), "obfuscated": bool(flags & 0x8000), "word97": nfib > 105}
    if f["word97"]:
        csw = struct.unpack_from("<H", wd, 32)[0]
        p = 34 + 2 * csw
        cslw = struct.unpack_from("<H", wd, p)[0]
        lw = struct.unpack_from(f"<{min(cslw, 22)}I", wd, p + 2)
        p2 = p + 2 + 4 * cslw
        cb = struct.unpack_from("<H", wd, p2)[0]
        pairs = struct.unpack_from(f"<{2 * min(cb, 93)}I", wd, p2 + 2)
        f["fclcb"] = [(pairs[2 * i], pairs[2 * i + 1]) for i in range(len(pairs) // 2)]
        f["ccp"] = {"text": lw[3], "footnotes": lw[4], "headers": lw[5], "macro": lw[6], "comments": lw[7], "endnotes": lw[8], "text boxes": lw[9], "header text boxes": lw[10]}
        p3 = p2 + 2 + 8 * cb
        if p3 + 4 <= len(wd):
            csw_new = struct.unpack_from("<H", wd, p3)[0]
            if csw_new:
                f["nfib_new"] = struct.unpack_from("<H", wd, p3 + 2)[0]
    else:
        fc_min, fc_mac = struct.unpack_from("<II", wd, 0x18)
        f["fc_min"], f["fc_mac"] = fc_min, fc_mac
        f["ccp"] = dict(zip(("text", "footnotes", "headers", "macro", "comments", "endnotes", "text boxes", "header text boxes"), struct.unpack_from("<8I", wd, 0x34)))
    return f


def version_label(f):
    if not f["word97"]:
        return {101: "Word 6.0 or Word 95", 103: "Word 95", 104: "Word 95", 105: "Word 95"}.get(f["nfib"], "Word 6/95")
    lab = "Word 97-2003 binary format"
    if f.get("nfib_new") in NFIB_NEW:
        lab += f", saved by {NFIB_NEW[f['nfib_new']]}"
    return lab


# ---------------------------------------------------------------- piece table and text
def pieces(clx):
    """The piece table of a Clx -> [(cp_start, cp_end, byte offset in WordDocument, bytes per character)]."""
    pos = 0
    while pos < len(clx) and clx[pos] == 1:
        pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
    if pos >= len(clx) or clx[pos] != 2:
        raise DocError("the piece table (Clx) is missing or damaged")
    lcb = struct.unpack_from("<I", clx, pos + 1)[0]
    plc = clx[pos + 5:pos + 5 + lcb]
    n = (lcb - 4) // 12
    if n <= 0 or len(plc) < 4 * (n + 1) + 8 * n:
        raise DocError("the piece table is cut short")
    cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
    out = []
    for i in range(n):
        fc = struct.unpack_from("<I", plc, 4 * (n + 1) + 8 * i + 2)[0]
        if cps[i + 1] < cps[i]:
            raise DocError("piece table positions run backwards")
        if fc & 0x40000000:
            out.append((cps[i], cps[i + 1], (fc & 0x3FFFFFFF) // 2, 1))
        else:
            out.append((cps[i], cps[i + 1], fc, 2))
    return out


def text_of(wd, pcs, codepage="cp1252", limit=50_000_000):
    parts = []
    for cp0, cp1, off, w in pcs:
        n = min(cp1 - cp0, limit)
        b = wd[off:off + n * w]
        if len(b) < n * w:
            raise DocError(f"a text piece points past the end of WordDocument (byte {off:,})")
        parts.append(b.decode(codepage, "replace") if w == 1 else b.decode("utf-16-le", "replace"))
    return "".join(parts)


def cp_to_fc(pcs, starts, cp):
    i = bisect.bisect_right(starts, cp) - 1
    if i < 0:
        return None
    cp0, cp1, off, w = pcs[i]
    return off + (cp - cp0) * w if cp < cp1 else None


# ---------------------------------------------------------------- paragraph properties and styles
SPRM_SIZE = {0: 1, 1: 1, 2: 2, 3: 4, 4: 2, 5: 2, 7: 3}


def papx_props(grpprl):
    """-> (in_table, row_end, depth) from a paragraph's property list."""
    intable = ttp = False
    itap = 0
    i, n = 0, len(grpprl)
    while i + 2 <= n:
        sprm = struct.unpack_from("<H", grpprl, i)[0]
        i += 2
        spra = sprm >> 13
        if spra == 6:
            if sprm == 0xD608 and i + 2 <= n:
                size = struct.unpack_from("<H", grpprl, i)[0] - 1 + 2
            elif i < n:
                size = grpprl[i] + 1
            else:
                break
        else:
            size = SPRM_SIZE[spra]
        op = grpprl[i:i + size]
        if sprm == 0x2416 and op:
            intable = bool(op[0])
        elif sprm in (0x2417, 0x244C) and op:
            ttp = ttp or bool(op[0])
        elif sprm == 0x6649 and len(op) >= 4:
            itap = struct.unpack_from("<i", op, 0)[0]
        i += size
    return intable or itap > 0, ttp, itap


def papx_runs(wd, tbl, fc, lcb):
    """The paragraph property pages -> sorted [(fc_start, fc_end, istd, in_table, row_end)]."""
    if not lcb or fc + lcb > len(tbl):
        return []
    plc = tbl[fc:fc + lcb]
    n = (lcb - 4) // 8
    pns = struct.unpack_from(f"<{n}I", plc, 4 * (n + 1))
    runs = []
    for pn in pns:
        page = wd[(pn & 0x3FFFFF) * 512:(pn & 0x3FFFFF) * 512 + 512]
        if len(page) < 512:
            continue
        crun = page[511]
        if not crun or 4 * (crun + 1) + 13 * crun > 511:
            continue
        rgfc = struct.unpack_from(f"<{crun + 1}I", page, 0)
        for k in range(crun):
            boff = page[4 * (crun + 1) + 13 * k] * 2
            istd, props = 0, (False, False, 0)
            if boff:
                cb = page[boff]
                data = page[boff + 2:boff + 2 + 2 * page[boff + 1]] if cb == 0 else page[boff + 1:boff + 1 + 2 * cb - 1]
                if len(data) >= 2:
                    istd = struct.unpack_from("<H", data, 0)[0]
                    props = papx_props(data[2:])
            runs.append((rgfc[k], rgfc[k + 1], istd) + props[:2])
    runs.sort()
    return runs


def styles(tbl, fc, lcb):
    """The style sheet -> {istd: (sti, name)}; sti 1-9 are the built-in headings 1-9 in every language."""
    out = {}
    if not lcb or fc + lcb > len(tbl):
        return out
    st = tbl[fc:fc + lcb]
    cb_stshi = struct.unpack_from("<H", st, 0)[0]
    cstd, cb_base = struct.unpack_from("<HH", st, 2)
    pos = 2 + cb_stshi
    for i in range(min(cstd, 4000)):
        if pos + 2 > len(st):
            break
        cb = struct.unpack_from("<H", st, pos)[0]
        if cb:
            std = st[pos + 2:pos + 2 + cb]
            sti = struct.unpack_from("<H", std, 0)[0] & 0x0FFF if len(std) >= 2 else 4095
            name = ""
            if cb_base + 2 <= len(std):
                ln = struct.unpack_from("<H", std, cb_base)[0]
                name = std[cb_base + 2:cb_base + 2 + 2 * ln].decode("utf-16-le", "replace")
            out[i] = (sti, name)
        pos += 2 + cb
    return out


def heading_level(style):
    if not style:
        return 0
    sti, name = style
    if 1 <= sti <= 9:
        return sti
    m = re.match(r"(?i)(?:heading|überschrift|titre|titolo|t[ií]tulo|заголовок|naslov)\s*(\d)$", name.strip())
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------- the whole read
def clean(s):
    """Field codes out (instructions between 0x13 and 0x14 dropped, results kept), Word's special characters to plain text."""
    out, depth, skip = [], 0, []
    for ch in s:
        o = ord(ch)
        if o == 0x13:
            skip.append(True)
            continue
        if o == 0x14:
            if skip:
                skip[-1] = False
            continue
        if o == 0x15:
            if skip:
                skip.pop()
            continue
        if any(skip):
            continue
        if o in (0x01, 0x02, 0x03, 0x04, 0x05, 0x08, 0x1F):
            continue
        out.append({0x0B: " ", 0x1E: "-", 0x0C: " ", 0xA0: " ", 0x09: "\t"}.get(o, ch))
    return "".join(out).strip()


def read(data):
    st = dl_vba.read_cfb(data)
    if not st:
        raise DocError("not a readable OLE compound file (cut short or damaged)")
    wd = st.get("WordDocument")
    if wd is None:
        raise DocError("no WordDocument stream")
    f = fib(wd)
    res = {"fib": f, "props": property_set(st.get("\x05SummaryInformation", b""), PIDSI), "dprops": property_set(st.get("\x05DocumentSummaryInformation", b""), PIDDSI)}
    if f["encrypted"] or f["obfuscated"]:
        res["encrypted"] = True
        return res
    ccp = f["ccp"]
    if f["word97"]:
        tbl = st.get(f["table"])
        if tbl is None:
            raise DocError(f"the {f['table']} stream named by the header is missing")
        fc, lcb = f["fclcb"][33] if len(f["fclcb"]) > 33 else (0, 0)
        if not lcb or fc + lcb > len(tbl):
            raise DocError("the piece table offset in the header points outside the table stream")
        pcs = pieces(tbl[fc:fc + lcb])
        full = text_of(wd, pcs)
        sfc, slcb = f["fclcb"][1] if len(f["fclcb"]) > 1 else (0, 0)
        res["styles"] = styles(tbl, sfc, slcb)
        bfc, blcb = f["fclcb"][13] if len(f["fclcb"]) > 13 else (0, 0)
        runs = papx_runs(wd, tbl, bfc, blcb)
    else:
        pcs, runs, res["styles"] = None, [], {}
        a, b = f["fc_min"], f["fc_mac"]
        if not (0 < a <= b <= len(wd)):
            raise DocError(f"text bounds {a:,}-{b:,} lie outside the {len(wd):,}-byte WordDocument stream")
        full = wd[a:b].decode("cp1252", "replace")
        if f["complex"]:
            res["note"] = "fast-saved Word 6/95 file: the text is read in stored order, later edits may sit at the end"
    if ccp["text"] > len(full):
        raise DocError(f"the header counts {ccp['text']:,} characters of text, {len(full):,} were found")
    parts, pos = {}, 0
    for k in ("text", "footnotes", "headers", "macro", "comments", "endnotes", "text boxes", "header text boxes"):
        parts[k] = full[pos:pos + ccp[k]]
        pos += ccp[k]
    res["parts"], res["pieces"] = parts, len(pcs) if pcs else 0
    main = parts["text"]
    starts = [p[0] for p in pcs] if pcs else []
    rstarts = [r[0] for r in runs]
    paras, cp = [], 0
    for m in SPLIT_RE.finditer(main):
        raw = main[cp:m.start()]
        istd, intable, ttp = 0, m.group() == "\x07", False
        if runs and pcs:
            fcm = cp_to_fc(pcs, starts, m.start())
            if fcm is not None:
                j = bisect.bisect_right(rstarts, fcm) - 1
                if 0 <= j < len(runs) and runs[j][0] <= fcm < runs[j][1]:
                    istd, intable, ttp = runs[j][2], runs[j][3] or intable, runs[j][4]
        paras.append({"raw": raw, "text": clean(raw), "istd": istd, "cell": m.group() == "\x07", "intable": intable, "ttp": ttp, "cp": cp})
        cp = m.end()
    tail = main[cp:]
    if clean(tail):
        paras.append({"raw": tail, "text": clean(tail), "istd": 0, "cell": False, "intable": False, "ttp": False, "cp": cp})
    if not runs:   # no property pages (Word 6/95): a cell mark right after a cell mark ends a row
        prev_cell = False
        for p in paras:
            if p["cell"]:
                p["intable"] = True
                if prev_cell and not p["raw"]:
                    p["ttp"] = True
            prev_cell = p["cell"] and not p["ttp"]
    sty = res["styles"]
    for p in paras:
        p["level"] = heading_level(sty.get(p["istd"])) if not p["intable"] else 0
        p["style"] = sty.get(p["istd"], (None, ""))[1]
    res["paras"] = paras
    tables, cur, row, buf = [], None, [], []
    for p in paras:
        if p["intable"]:
            if cur is None:
                cur = []
                tables.append(cur)
            if p["ttp"]:
                cur.append(row)
                row, buf = [], []
            elif p["cell"]:   # the cell mark ends the cell's last paragraph; earlier paragraphs of the cell end in a paragraph mark
                row.append(" / ".join(x for x in buf + [p["text"]] if x))
                buf = []
            elif p["text"]:
                buf.append(p["text"])
        else:
            if row:
                cur.append(row)
                row = []
            cur, buf = None, []
    if row and cur is not None:
        cur.append(row)
    res["tables"] = tables   # in document order, empty ones too (text.md walks them by position)
    return res


# ---------------------------------------------------------------- the look
def look_doc(look):
    """Facts of a legacy .doc from its own bytes. -> True when the text was read (the caller may still render pages)."""
    try:
        r = read(look.path.read_bytes()[:256 << 20])
    except DocError as e:
        look.flag("CORRUPT", "Word binary", str(e), "the text could not be read from the file's own structure")
        return False
    except (struct.error, IndexError, ValueError, KeyError, OverflowError, MemoryError) as e:
        look.flag("CORRUPT", "Word binary", f"{type(e).__name__}: {e}"[:160], "the text could not be read from the file's own structure")
        return False
    f = r["fib"]
    lang = LANG.get(f["lid"], f"0x{f['lid']:04x}")
    flags = [x for x, on in (("template (.dot)", f["dot"]), ("fast-saved (complex)", f["complex"]), ("encrypted", f["encrypted"]), ("read-only recommended", f["readonly_rec"]),
                             ("pictures", f["has_pic"]), ("East Asian", f["far_east"])) if on]
    ccp = f["ccp"]
    look.line(f"Word binary header: nFib {f['nfib']} ({version_label(f)}); language {lang}; " + (f"flags: {', '.join(flags)}; " if flags else "flags: none set; ")
              + (f"table stream {f['table']}; " if f["word97"] else "") + f"quick saves {f['quick_saves']}; characters stored: "
              + ", ".join(f"{k} {v:,}" for k, v in ccp.items() if v or k == "text") + (f"; text pieces {r['pieces']}" if r.get("pieces") else "") + ".", 94, "structure")
    props_line(look, r["props"], r["dprops"], "Word")
    if r.get("encrypted"):
        look.flag("ENCRYPTED", "Word binary", "the document is encrypted or obfuscated", "the text cannot be read without the password")
        return True
    paras = r["paras"]
    body = [p for p in paras if not p["intable"]]
    ne = [p for p in body if p["text"]]
    cells = [p for p in paras if p["intable"] and p["cell"] and not p["ttp"]]
    heads = [p for p in ne if p["level"]]
    per = {}
    for p in heads:
        per[p["level"]] = per.get(p["level"], 0) + 1
    main = r["parts"]["text"]
    plain = "\n".join(p["text"] for p in paras if p["text"])
    words = len(plain.split())
    all_tables = r["tables"]
    tables = [t for t in all_tables if t]
    pairs = [("paragraph and cell marks", main.count(chr(13)) + main.count(chr(7))), ("non-empty paragraphs", len(ne) + sum(1 for c in cells if c["text"])),
             ("non-empty paragraphs outside tables", len(ne)), ("empty paragraphs outside tables", len(body) - len(ne)), ("tables", len(tables)),
             ("table rows", sum(len(t) for t in tables)), ("table cells", len(cells)), ("headings", len(heads))]
    pairs += [(f"heading {k}", per[k]) for k in sorted(per)]
    pairs += [("page or section breaks", main.count("\x0c") or None), ("fields", main.count("\x13") or None), ("pictures and objects", (main.count("\x01") + main.count("\x08")) or None),
              ("footnotes", r["parts"]["footnotes"].count("\x02") or None), ("comments", r["parts"]["comments"].count("\x05") or None),
              ("words", words), ("characters (no spaces)", len(re.sub(r"\s+", "", plain))), ("characters with spaces", len(plain.replace("\n", "")))]
    P.counts(look, pairs, 96, "Word counts")
    look.fact("paragraphs", len(ne))
    look.headline = f"Word document ({version_label(f)}): {len(ne):,} non-empty paragraphs, {len(heads)} headings, {len(tables)} tables"
    if ne:
        last3 = ne[-3:]
        look.line(f"Last paragraphs (#{len(ne) - len(last3) + 1}-#{len(ne)} of {len(ne):,} non-empty paragraphs outside tables): "
                  + " | ".join(short(p["text"], 160) for p in last3), 93, "tail")
        import dl_textx
        dl_textx.marks_lines(look, len(ne), lambda k: f"#{k} {short(ne[k - 1]['text'], 110)}", "paragraph", 84,
                             f"Paragraphs at fixed positions ({len(ne):,} non-empty paragraphs outside tables; #k = the k-th)")
    for i, t in enumerate(tables[:12], 1):
        ncol = max(len(x) for x in t)
        look.line(f"Table {i}: {len(t)} rows x {ncol} columns; first row: " + " | ".join(short(x, 30) for x in t[0]) + "; last row: " + " | ".join(short(x, 30) for x in t[-1]),
                  90 - min(20, i), "tables")
        full = P.table_rows(f"Table {i} rows", t)
        if full:
            look.line(full, 79 - min(20, 2 * i), "tables")
    if heads:
        idx = {id(p): k for k, p in enumerate(ne, 1)}
        rows = [f"{'  ' * (p['level'] - 1)}{p['level']}. {short(p['text'], 80)} (#{idx[id(p)]})" for p in heads]
        look.line(f"Outline ({len(heads)} headings from the heading styles; level, text, paragraph #):\n" + "\n".join(rows[:40]) + (f"\n... {len(rows) - 40} more" if len(rows) > 40 else ""), 86, "outline")
    sty = {}
    for p in paras:
        if p["text"] and p["style"]:
            sty[p["style"]] = sty.get(p["style"], 0) + 1
    if sty:
        look.line("Paragraph styles (count): " + ", ".join(f"{k} {v:,}" for k, v in sorted(sty.items(), key=lambda kv: -kv[1])[:12]), 60, "structure")
    for k in ("headers", "footnotes", "comments", "endnotes"):
        t = clean(r["parts"][k])
        if t:
            look.line(f"{k.capitalize()} text ({len(r['parts'][k]):,} characters): " + short(" | ".join(x for x in SPLIT_RE.split(t) if x.strip()), 300), 70, "structure")
    if r.get("note"):
        look.line(r["note"], 70)
    md = []
    seen_table = None
    ti = 0
    for p in paras:
        if p["intable"]:
            if seen_table is None:
                seen_table = all_tables[ti] if ti < len(all_tables) else []
                ti += 1
                md += [""] + ["| " + " | ".join(c.replace("|", "/") for c in row) + " |" for row in seen_table] + [""]
            continue
        seen_table = None
        if p["text"]:
            md.append(("#" * p["level"] + " " if p["level"] else "") + p["text"])
    look.write_text("text.md", "\n".join(md).strip() + "\n", "document text from the file's own bytes: headings (#), paragraphs, tables as | rows", value=6)
    look.step("Word binary text, styles and properties", "stdlib")
    return True
