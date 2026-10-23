"""SigmaDeepLook: Rich Text Format (.rtf) documents, read from their own bytes with the standard library (fix round 11).

The body text (control words dropped; hex bytes decoded with the code page the file names; Unicode escapes kept), its paragraphs, the
table rows, the saved properties of the info group, and the picture, field and footnote counts. The text is written as text.md, so
`--ask` counts words over the whole text like it does for Word files. A group the reader does not know is skipped, never guessed.
"""
import re

import dl_prof as P

TOKEN = re.compile(r"\\([a-zA-Z]{1,32})(-?\d{1,10})? ?|\\'([0-9a-fA-F]{2})|\\([^a-zA-Z])|([{}])|([^\\{}]+)|\\")
SKIP = {"fonttbl", "colortbl", "stylesheet", "pict", "themedata", "colorschememapping", "latentstyles", "datastore", "listtable", "listoverridetable", "rsidtbl",
        "generator", "xmlnstbl", "fldinst", "header", "headerl", "headerr", "headerf", "footer", "footerl", "footerr", "footerf", "private", "bkmkstart",
        "bkmkend", "objdata", "blipuid", "shpinst", "pgptbl", "revtbl", "falt", "panose", "footnote", "nonshppict"}
INFO_FIELDS = {"title": "Title", "subject": "Subject", "author": "Author", "manager": "Manager", "company": "Company", "operator": "Last saved by",
               "keywords": "Keywords", "doccomm": "Comments"}
SPECIAL = {"tab": "\t", "line": " ", "emdash": "\u2014", "endash": "\u2013", "bullet": "\u2022", "lquote": "\u2018", "rquote": "\u2019", "ldblquote": "\u201c",
           "rdblquote": "\u201d", "enspace": " ", "emspace": " ", "~": "\u00a0", "_": "-"}
CODEPAGES = {437: "cp437", 850: "cp850", 932: "cp932", 936: "gbk", 949: "cp949", 950: "big5", 1250: "cp1250", 1251: "cp1251", 1252: "cp1252", 1253: "cp1253",
             1254: "cp1254", 1255: "cp1255", 1256: "cp1256", 1257: "cp1257", 1258: "cp1258", 10000: "mac_roman", 65001: "utf-8"}


def without_binary(raw):
    """Drop the n raw bytes that follow a bin<n> control word: they may hold braces and backslashes that would break the group structure."""
    if b"\\bin" not in raw:
        return raw
    parts, at = [], 0
    for m in re.finditer(rb"\\bin(\d{1,9}) ?", raw):
        if m.start() < at:
            continue
        parts.append(raw[at:m.start()])
        at = m.end() + int(m.group(1))
    parts.append(raw[at:])
    return b"".join(parts)


def parse(raw):
    """-> dict(paras, rows, info, counts, codepage): paras are the paragraphs in order (empty ones too), rows are lists of cell texts."""
    text = without_binary(raw).decode("latin-1")
    m = re.search(r"\\ansicpg(\d+)", text[:4000])
    enc = CODEPAGES.get(int(m.group(1)), "cp1252") if m else "cp1252"
    counts = {"pictures": 0, "fields": 0, "footnotes": 0, "table rows": 0, "page breaks": 0, "sections": 0}
    stack, skip, dest, uc, skip_n = [], False, "", 1, 0
    out, pend, paras, cells, rows, info, infobuf = [], bytearray(), [], [], [], {}, []

    def flush():
        if pend:
            out.append(bytes(pend).decode(enc, "replace"))
            pend.clear()

    def end_para():
        flush()
        t = "".join(out).replace("\u00a0", " ").strip()
        out.clear()
        t = t.encode("utf-16", "surrogatepass").decode("utf-16", "replace")   # two escapes for one character above U+FFFF join; a lone half becomes U+FFFD
        paras.append(t)
        return t

    for tok in TOKEN.finditer(text):
        word, num, hx, sym, brace, lit = tok.groups()
        if brace == "{":
            stack.append((skip, dest, uc))
            continue
        if brace == "}":
            if dest in INFO_FIELDS and infobuf:
                info[INFO_FIELDS[dest]] = "".join(infobuf).strip()
                infobuf.clear()
            skip, dest, uc = stack.pop() if stack else (False, "", 1)
            continue
        if skip_n and not skip:   # the plain-text stand-in after a Unicode escape is not text
            if hx:
                skip_n -= 1
                continue
            if lit:
                cut = min(skip_n, len(lit))
                skip_n -= cut
                lit = lit[cut:]
                if not lit:
                    continue
        if word:
            if word in SKIP:
                counts["pictures"] += word == "pict"
                counts["footnotes"] += word == "footnote"
                skip, dest = True, word
                continue
            if skip:
                continue
            if word in INFO_FIELDS:
                dest = word
            elif word == "uc" and num:
                uc = int(num)
            elif word == "u" and num:
                flush()
                v = int(num)
                out.append(chr(v if v >= 0 else v + 65536))
                skip_n = uc
            elif word == "field":
                counts["fields"] += 1
            elif word in ("par", "sect"):
                end_para()
                counts["sections"] += word == "sect"
            elif word == "cell":
                cells.append(end_para())
            elif word == "row":
                rows.append(cells)
                cells = []
                counts["table rows"] += 1
            elif word == "page":
                counts["page breaks"] += 1
            elif word in SPECIAL:
                flush()
                out.append(SPECIAL[word])
            continue
        if skip:
            continue
        if hx:
            pend.append(int(hx, 16))
        elif sym:
            flush()
            if sym in "{}\\":
                out.append(sym)
            elif sym in SPECIAL:
                out.append(SPECIAL[sym])
            elif sym in ("\n", "\r"):   # a backslash before a line break (LF or CR LF) is a paragraph mark
                end_para()
            elif sym == "*":    # an extension destination: its group is skipped whole
                skip = True
        elif lit:
            flush()
            lit = lit.replace("\r", "").replace("\n", "")
            (infobuf if dest in INFO_FIELDS else out).append(lit)
    end_para()
    return {"paras": paras, "rows": rows, "info": info, "counts": counts, "codepage": enc}


def look_rtf(look):
    raw = look.path.read_bytes()[:128 << 20]
    r = parse(raw)
    paras = [p for p in r["paras"] if p]
    words = sum(len(p.split()) for p in paras)
    c = r["counts"]
    look.headline = f"Rich Text Format document: {len(paras):,} non-empty paragraphs, {words:,} words"
    P.counts(look, [("non-empty paragraphs", len(paras)), ("empty paragraphs", len(r["paras"]) - len(paras)), ("words", words),
                    ("characters (no spaces)", sum(len(re.sub(r"\s", "", p)) for p in paras)), ("table rows", c["table rows"] or None),
                    ("pictures", c["pictures"] or None), ("fields", c["fields"] or None), ("footnotes", c["footnotes"] or None),
                    ("page breaks", c["page breaks"] or None), ("sections", c["sections"] or None)], 96, "RTF counts")
    ver = re.match(rb"\{\\rtf(\d)", raw[:20])
    look.line(f"RTF header: version {ver.group(1).decode() if ver else '?'}; code page {r['codepage']}.", 70, "structure")
    if r["info"]:
        look.line("Document properties (info group): " + "; ".join(f"{k}: {P.short(v, 80)}" for k, v in r["info"].items()), 95, "props")
    if paras:
        look.line(f"Last paragraphs (#{max(1, len(paras) - 2)}-#{len(paras)} of {len(paras):,}): " + " | ".join(P.short(p, 160) for p in paras[-3:]), 93, "tail")
        import dl_textx
        dl_textx.marks_lines(look, len(paras), lambda k: f"#{k} {P.short(paras[k - 1], 110)}", "paragraph", 84,
                             f"Paragraphs at fixed positions ({len(paras):,} non-empty paragraphs; #k = the k-th)")
    for i, row in enumerate(r["rows"][:6], 1):
        look.line(f"Table row {i}: " + " | ".join(P.short(x, 30) for x in row), 80 - i, "tables")
    look.fact("paragraphs", len(paras))
    look.write_text("text.md", "\n".join(paras) + "\n", "document text from the RTF control words and text: one paragraph per line", value=6)
    look.step("RTF text, properties and counts", "stdlib")
