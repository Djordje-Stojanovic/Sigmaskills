"""SigmaDeepLook variable metadata of statistical files (fix round 15): the dataset label, and for each variable its label, its format
(name, width, decimals) and informat. Standard library only.

A statistical file keeps these beside the data, and a user asks for them by name: "the dataset label", "the label of variable X", "which SAS format
is attached to the variable dates". They are not rows, so the table machinery does not see them. This module reads them from the file's own bytes
(SAS sas7bdat and XPORT, the SPSS dictionary, the Stata header), keeps them in look.json (`facts.var_meta`) and answers those questions from there.

var_meta = {"kind": "SAS", "label": "<dataset label>", "vars": [{"name", "label", "format", "fw", "fd", "informat", "iw", "id", "values": [[code, text], ...]}]}
"""
import re
import struct

SAS_MAGIC = bytes.fromhex("000000000000000000000000c2ea8160b31411cfbd92080009c7318c181f1011")
SUBS = {0xF7F7F7F7: "rowsize", 0xF6F6F6F6: "colsize", 0xFFFFFC00: "counts", 0xFFFFFFFD: "text", 0xFFFFFFFF: "name", 0xFFFFFFFC: "attr",
        0xFFFFFBFE: "format", 0xFFFFFFFE: "list"}
MAX_PAGES = 4096          # meta pages are the first ones; a file whose pages hold no more subheaders is not scanned to its end
MAX_VARS = 5000
MAX_VALUES = 200          # value labels kept per variable


def _enc(code_name):
    try:
        "".encode(code_name)
        return code_name
    except (LookupError, TypeError):
        return "latin-1"


def sas_meta(path):
    """sas7bdat -> var_meta dict, or None when the file is not a readable sas7bdat (its first bytes lack the magic number)."""
    with open(path, "rb") as f:
        head = f.read(1024)
        if len(head) < 288 or head[:32] != SAS_MAGIC:
            return None
        u64, a1 = head[32] == 0x33, (4 if head[35] == 0x33 else 0)
        il = 8 if u64 else 4
        e = "<" if head[37] == 1 else ">"
        hl = struct.unpack_from(e + "i", head, 196 + a1)[0]
        pl = struct.unpack_from(e + "i", head, 200 + a1)[0]
        if not (288 <= hl <= 1 << 20 and 512 <= pl <= 1 << 24):
            return None
        import dl_r14f2
        enc = _enc(dl_r14f2.sas_encoding(head[70])["name"])
        pbo, ptr = (32, 24) if u64 else (16, 12)

        def u(buf, at, n):
            return int.from_bytes(buf[at:at + n], "little" if e == "<" else "big")
        texts, names, attrs, fmts, label = [], [], [], [], ""
        rowsize = None
        f.seek(hl)
        for _ in range(min(MAX_PAGES, (64 << 20) // pl)):
            page = f.read(pl)
            if len(page) < pl:
                break
            ptype = u(page, pbo, 2) & 0xFF00
            if ptype not in (0, 0x4000, 0x400, 0x200):   # the pages that can hold subheaders (meta, meta 2, amd, mix)
                if ptype == 0x100 and texts:
                    break
                continue
            for i in range(u(page, pbo + 4, 2)):
                at = pbo + 8 + ptr * i
                off, ln = u(page, at, il), u(page, at + il, il)
                comp = page[at + 2 * il] if at + 2 * il < len(page) else 0
                if not ln or comp == 1 or off + ln > len(page) or off < 0:
                    continue
                sig = page[off:off + il]
                key = SUBS.get(int.from_bytes(sig[:4] if e == "<" else sig[-4:], "little" if e == "<" else "big")) if len(sig) >= 4 else None
                sub = page[off:off + ln]
                if key == "rowsize":
                    rowsize = sub
                elif key == "text":
                    n = u(sub, il, 2)
                    texts.append(sub[il:il + n])
                elif key == "name":
                    for k in range((ln - 2 * il - 12) // 8):
                        p = il + 8 * (k + 1)
                        names.append((u(sub, p, 2), u(sub, p + 2, 2), u(sub, p + 4, 2)))
                elif key == "attr":
                    for k in range((ln - 2 * il - 12) // (il + 8)):
                        p = il + 8 + k * (il + 8)
                        attrs.append(sub[p + il + 6] if p + il + 6 < len(sub) else 0)
                elif key == "format":
                    g = 3 * il
                    fmts.append({"w": u(sub, g, 2), "d": u(sub, g + 2, 2), "inf": (u(sub, g + 16, 2), u(sub, g + 18, 2), u(sub, g + 20, 2)),
                                 "fmt": (u(sub, g + 22, 2), u(sub, g + 24, 2), u(sub, g + 26, 2)), "lab": (u(sub, g + 28, 2), u(sub, g + 30, 2), u(sub, g + 32, 2))})
            if len(names) >= MAX_VARS:
                break

        def cut(tri):
            idx, off, ln = tri
            if not ln or idx >= len(texts):
                return ""
            return texts[idx][off:off + ln].split(b"\0")[0].decode(enc, "replace").strip()
        if rowsize is not None:
            lcs_at = 682 if u64 else 354
            if len(rowsize) >= lcs_at + 2:
                label = cut((u(rowsize, lcs_at - 4, 2), u(rowsize, lcs_at - 2, 2), u(rowsize, lcs_at, 2)))
        if not names:
            return None
        out = []
        for k, nm in enumerate(names[:MAX_VARS]):
            g = fmts[k] if k < len(fmts) else None
            out.append({"name": cut(nm), "label": cut(g["lab"]) if g else "", "format": cut(g["fmt"]) if g else "", "fw": g["w"] if g else 0, "fd": g["d"] if g else 0,
                        "informat": cut(g["inf"]) if g else "", "numeric": attrs[k] == 1 if k < len(attrs) else None})
        return {"kind": "SAS", "label": label, "vars": out}


def xpt_meta(path):
    """SAS XPORT (transport v5/v6, 80-byte records) -> var_meta dict, or None. The first dataset's dataset label and its variables."""
    with open(path, "rb") as f:
        raw = f.read(2 << 20)
    if not raw.startswith(b"HEADER RECORD*******LIBRARY"):
        return None
    mem = raw.find(b"HEADER RECORD*******MEMBER ")
    nam = raw.find(b"HEADER RECORD*******NAMESTR")
    if mem < 0 or nam < 0 or nam < mem:
        return None
    tail = raw[mem + 48:mem + 80].strip()   # the member header ends with the size of one variable record: 0140 (or 0080 on a VAX)
    size = 80 if tail.endswith(b"0080") else 140
    n = int(raw[nam + 54:nam + 58]) if raw[nam + 54:nam + 58].strip().isdigit() else 0
    # the record before the variable header holds the modified time, then the 40-character dataset label
    lab_rec = raw[nam - 80:nam]
    label = lab_rec[32:72].decode("latin-1").strip() if len(lab_rec) == 80 and not lab_rec.startswith(b"HEADER") else ""
    out = []
    start = nam + 80
    for k in range(min(n, MAX_VARS)):
        s = raw[start + k * size:start + k * size + min(size, 140)]
        if len(s) < 88:
            break

        def t(a, b):
            return s[a:b].decode("latin-1").rstrip("\0 ")
        out.append({"name": t(8, 16), "label": t(16, 56), "format": t(56, 64), "fw": struct.unpack(">h", s[64:66])[0], "fd": struct.unpack(">h", s[66:68])[0],
                    "informat": t(72, 80), "numeric": struct.unpack(">h", s[0:2])[0] == 1})
    return {"kind": "SAS XPORT", "label": label, "vars": out} if out else None


def sav_meta(s):
    """The parsed dictionary of dl_sav.Sav -> var_meta dict."""
    out = []
    for k, v in enumerate(s.vars):
        pf = v.get("print") or 0
        code, w, d = (pf >> 16) & 0xFF, (pf >> 8) & 0xFF, pf & 0xFF
        try:
            vals = [[a, b] for a, b in s.decoded_labels(k)][:MAX_VALUES]
        except Exception:   # a damaged label record: the variable keeps its label and format
            vals = []
        out.append({"name": v["long"], "label": v["label"], "format": SPSS_FORMATS.get(code, f"type {code}") if pf else "", "fw": w, "fd": d, "informat": "",
                    "numeric": v["type"] == 0, "values": vals})
    return {"kind": "SPSS", "label": s.label, "vars": out}


SPSS_FORMATS = {0: "", 1: "A", 2: "AHEX", 3: "COMMA", 4: "DOLLAR", 5: "F", 6: "IB", 7: "PIBHEX", 8: "P", 9: "PIB", 10: "PK", 11: "RB", 12: "RBHEX", 15: "Z", 16: "N",
                17: "E", 20: "DATE", 21: "TIME", 22: "DATETIME", 23: "ADATE", 24: "JDATE", 25: "DTIME", 26: "WKDAY", 27: "MONTH", 28: "MOYR", 29: "QYR", 30: "WKYR",
                31: "PCT", 32: "DOT", 33: "CCA", 34: "CCB", 35: "CCC", 36: "CCD", 37: "CCE", 38: "EDATE", 39: "SDATE"}


def stata_meta(reader, variable_labels, value_labels, data_label):
    """pandas StataReader pieces -> var_meta dict."""
    names = list(getattr(reader, "_varlist", None) or variable_labels)
    fmts = list(getattr(reader, "_fmtlist", None) or [])
    out = []
    sets = list(getattr(reader, "_lbllist", None) or [])   # the value-label set of each variable (its name need not be the variable's name)
    for k, nm in enumerate(names[:MAX_VARS]):
        lab = value_labels.get(sets[k] if k < len(sets) and sets[k] else nm) or {}
        out.append({"name": nm, "label": variable_labels.get(nm) or "", "format": fmts[k] if k < len(fmts) else "", "fw": 0, "fd": 0, "informat": "", "numeric": None,
                    "values": [[a, b] for a, b in list(lab.items())[:MAX_VALUES]]})
    return {"kind": "Stata", "label": data_label or "", "vars": out}


# ------------------------------------------------------------------------------------------------ the print
def fmt_text(v):
    """'COMMA12.2', 'DATE', 'F8.2': the format name with its width and decimals when the file states them."""
    f = v.get("format") or ""
    if not f:
        return ""
    w, d = v.get("fw") or 0, v.get("fd") or 0
    return f + (f"{w}." + (str(d) if d else "") if w else "")


PLAIN = {"SPSS": re.compile(r"^(?:F|A|)$"), "Stata": re.compile(r"^%-?\d+(?:\.\d+)?[gfesx]c?$|^%-?\d+s$|^$")}   # the formats every variable has: not worth a line


def print_lines(meta, max_vars=30, text=48, labels=True):
    """-> [(text, priority)] for step 1: the formats (names only, short) and the labels (cut), for up to `max_vars` variables.
    `labels=False` when the family already prints its labels in full (SPSS, Stata)."""
    vs = meta["vars"]
    plain = PLAIN.get(meta.get("kind"))
    lines = []
    shown = [v for v in vs if (v.get("format") or v.get("informat")) and not (plain and plain.match(v.get("format") or ""))]
    if shown:
        parts = [f"{v['name']} {fmt_text(v)}" + (f" (informat {v['informat']})" if v.get("informat") and v["informat"] != v.get("format") else "") for v in shown[:max_vars]]
        more = f"; +{len(shown) - max_vars} more" if len(shown) > max_vars else ""
        lines.append((f"Formats ({len(shown)} of {len(vs)} variables have one): " + "; ".join(parts) + more
                      + ' | Ask: --ask "format of variable <name>" or "which variables have a date format"', 87))
    lab = [v for v in vs if v.get("label")] if labels else []
    if lab:
        def row(vv, cap):
            return "; ".join(f"{v['name']} = '{v['label'][:cap]}{'…' if len(v['label']) > cap else ''}'" for v in vv)
        first = lab[:12]
        more = f"; +{len(lab) - len(first)} more (next line)" if len(lab) > len(first) else ""
        lines.append((f"Variable labels ({len(lab)} of {len(vs)} variables have one): " + row(first, 34) + more + ' | Ask: --ask "label of variable <name>"', 86))
        if len(lab) > len(first):
            lines.append((f"Variable labels, the rest: " + row(lab[len(first):max_vars], text) + (f"; +{len(lab) - max_vars} more" if len(lab) > max_vars else ""), 60))
    return lines


def attach(look, meta, labels=True):
    """Keep var_meta in look.json (for --ask) and print its short lines."""
    if not meta or not meta.get("vars"):
        return
    look.fact("var_meta", meta)
    for text, pri in print_lines(meta, labels=labels):
        look.line(text, pri, "structure")


# ------------------------------------------------------------------------------------------------ --ask
DATASET_WORD = re.compile(r"\b(?:dataset|data\s*set|data\s*file|file|table|whole|entire)\b", re.I)
VAR_LABEL = re.compile(r"\b(?:variable|column|field)\s+label\b|\blabel\s+(?:of|for)\b|\blabel\b.*\b(?:variable|column|field)\b", re.I)
FORMAT_WORD = re.compile(r"\b(in)?formats?\b", re.I)
DATE_FMT = re.compile(r"^(?:E8601\w*|DATE|DATETIME|TIME|DAY|DDMMYY|MMDDYY|YYMMDD|MONYY|MONTH|YEAR|QTR|WEEK\w*|JULIAN|NENGO|DOWNAME|ADATE|EDATE|SDATE|JDATE|DTIME|MOYR|QYR|WKYR|WKDAY|DTDATE|DTMONTH|DTWKDAT|DTYEAR|DTYYQC|HHMM|MMSS|B8601\w*|\%t[a-z]|\%-t[a-z]|\%d)", re.I)
VALUE_WORD = re.compile(r"\bvalue\s+labels?\b|\bcoded?\s+values?\b|\bcategor(?:y|ies)\s+labels?\b", re.I)
COMMON = {"date", "time", "datetime", "label", "format", "value", "values", "name", "type", "file", "data", "number", "year", "day", "month", "code", "text", "id"}


def _find_var(q, vs):
    """The variable the question names: a quoted name, else a whole-word match of a variable name (the longest wins)."""
    ql = q.lower()
    for m in re.finditer(r"""['"`‘’“”]([^'"`‘’“”]{1,64})['"`‘’“”]""", q):
        for v in vs:
            if v["name"].lower() == m.group(1).strip().lower():
                return v
    hits = [v for v in vs if v["name"] and re.search(r"(?<![\w.])" + re.escape(v["name"].lower()) + r"(?![\w.])", ql)
            and (v["name"].lower() not in COMMON or re.search(r"\b(?:variable|column|field|of|for)\s+['\"`]?" + re.escape(v["name"].lower()) + r"\b", ql))]   # a variable called "date" is not the word in "a date format"
    if not hits:
        return None
    best = max(len(v["name"]) for v in hits)
    top = [v for v in hits if len(v["name"]) == best]
    if len(top) > 1:   # "label of variable dates" also holds the word of a shorter name: prefer the name that follows "variable"/"column"
        m = re.search(r"\b(?:variable|column|field)\s+['\"`]?([\w.]+)", q, re.I)
        if m:
            return next((v for v in top if v["name"].lower() == m.group(1).lower()), top[0])
    return top[0]


def try_ask(q, lj):
    """-> the answer text for a dataset label, variable label, format, informat or value label question, or None when the question is something else."""
    meta = (lj.get("facts") or {}).get("var_meta")
    if not meta or not meta.get("vars"):
        return None
    vs, kind = meta["vars"], meta.get("kind", "")
    head = f"--ask {q!r}"
    src = f"{kind} dictionary (read from the file's own bytes)"
    if re.search(r"\blabel\b", q, re.I) and DATASET_WORD.search(q) and not re.search(r"\b(?:variable|column|field)s?\b", q, re.I) and not _find_var(q, vs):
        lab = meta.get("label") or ""
        return "\n".join([head, f"Answer: {lab}" if lab else "Answer: none: the file carries no dataset label", f"Source: {src}; dataset label {'set' if lab else 'empty'}"])
    wants_fmt, wants_lab, wants_val = bool(FORMAT_WORD.search(q)), bool(VAR_LABEL.search(q)), bool(VALUE_WORD.search(q))
    if not (wants_fmt or wants_lab or wants_val):
        return None
    v = _find_var(q, vs)
    if v is not None:
        if wants_val:
            vals = v.get("values") or []
            if not vals:
                return "\n".join([head, f"Answer: none: variable {v['name']} has no value labels", f"Source: {src}"])
            return "\n".join([head, f"Answer: {len(vals)} value labels of {v['name']}: " + "; ".join(f"{a} = {b}" for a, b in vals), f"Source: {src}"])
        if wants_fmt and wants_lab and re.search(r"\blabels?\b", q, re.I):   # "label and format of variable X": both
            return "\n".join([head, f"Answer: label: {v.get('label') or 'none'}; format: {fmt_text(v) or 'none'}" + (f"; informat: {v['informat']}" if v.get("informat") else ""), f"Source: {src}"])
        if wants_fmt:
            informat = bool(re.search(r"\binformats?\b", q, re.I)) and not re.search(r"(?<!in)\bformats?\b", q, re.I)
            name = v.get("informat") if informat else v.get("format")
            what = "informat" if informat else "format"
            if not name:
                width = (f" (a width of {v['fw']}" + (f" and {v['fd']} decimals" if v.get("fd") else "") + " is stored, no format name)") if (v.get("fw") and not informat) else ""
                return "\n".join([head, f"Answer: none: variable {v['name']} has no {what} name attached{width}", f"Source: {src}"])
            full = f" ({fmt_text(v)})" if (not informat and fmt_text(v) != name) else ""
            extra = f"; width {v.get('fw') or 0}, decimals {v.get('fd') or 0}{full}" if not informat else ""
            other = f"; informat {v['informat']}" if (not informat and v.get("informat")) else (f"; format {v['format']}" if (informat and v.get("format")) else "")
            return "\n".join([head, f"Answer: {name}", f"Detail: {what} of variable {v['name']}{extra}{other}", f"Source: {src}"])
        if wants_lab:
            lab = v.get("label") or ""
            return "\n".join([head, f"Answer: {lab}" if lab else f"Answer: none: variable {v['name']} has no label", f"Source: {src}"])
        return None
    # no single variable: a list question over all of them (it must speak of variables, columns or fields: "rows with a format ..." is a data question)
    if not re.search(r"\b(?:variables?|columns?|fields?)\b", q, re.I):
        return None
    if wants_fmt and re.search(r"\b(?:date|time|datetime)\b", q, re.I):
        hit = [x for x in vs if DATE_FMT.match(x.get("format") or "")]
        return "\n".join([head, f"Answer: {len(hit)} variable{'' if len(hit) == 1 else 's'} {'has' if len(hit) == 1 else 'have'} a date or time format: " + ", ".join(f"{x['name']} ({fmt_text(x)})" for x in hit) if hit
                          else "Answer: none: no variable has a date or time format", f"Source: {src}"])
    if re.search(r"\b(?:which|what|list|how many)\b", q, re.I) and (wants_fmt or wants_lab):
        key = "format" if wants_fmt else "label"
        hit = [x for x in vs if x.get(key)]
        if re.search(r"\bhow many\b", q, re.I):
            return "\n".join([head, f"Answer: {len(hit)} of {len(vs)} variables have a {key}", f"Source: {src}"])
        return "\n".join([head, f"Answer: {len(hit)} of {len(vs)} variables have a {key}: " + "; ".join(f"{x['name']} = {fmt_text(x) if key == 'format' else x['label']}" for x in hit),
                          f"Source: {src}"])
    return None
