"""SigmaDeepLook: what makes a workbook wrong rather than merely big.

Read straight from the OOXML (no Excel, no macros run): very hidden sheets, named ranges and broken names, external links, XLM macro
sheets, tables and pivots, formula shapes per column (a hardcoded number inside a formula column, one odd formula among thousands),
numbers embedded in formulas, volatile functions, error values. The checks come from spreadsheet-audit practice: the cell that breaks
a column pattern is where the mistake is.
"""
import re
from collections import Counter

REF = re.compile(r"(?<![A-Za-z0-9_.!'\"])(\$?)([A-Z]{1,3})(\$?)(\d{1,7})(?![\d(A-Za-z_])")
NUM = re.compile(r"(?<![A-Za-z0-9_.$])(\d+\.\d+|\d{2,})(?![\d.A-Za-z_(])")
VOLATILE = re.compile(r"\b(NOW|TODAY|RAND|RANDBETWEEN|OFFSET|INDIRECT|INFO|CELL)\(", re.I)
ERR = re.compile(rb'<c r="([A-Z]+\d+)"[^>]*?\bt="e"[^>]*>\s*(?:<f>.*?</f>\s*)?<v>([^<]*)</v>', re.S)
SKIP_NUMS = {"100", "1000", "12", "24", "60", "365", "10"}


def col_num(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


def norm(f, r, c):
    """The formula with every relative reference as an offset (R[-1]C[2]), so copies of one formula look identical."""
    def sub(m):
        cabs, col, rabs, row = m.groups()
        cc, rr = col_num(col), int(row)
        return (f"R{rr}" if rabs else f"R[{rr - r}]") + (f"C{cc}" if cabs else f"C[{cc - c}]")
    return REF.sub(sub, f)


def cell_name(r, c):
    s, n = "", c + 1
    while n:
        n, k = divmod(n - 1, 26)
        s = chr(65 + k) + s
    return f"{s}{r + 1}"


def workbook_report(look, z, names, sheets, wb_xml):
    """Workbook-level facts. sheets: dicts with name, state, path. wb_xml: the bytes of xl/workbook.xml."""
    txt = wb_xml.decode("utf-8", "replace")
    for s in sheets:
        if s["state"] == "veryHidden":
            look.flag("VERYHIDDEN-SHEET", s["name"], "veryHidden", "cannot be unhidden from the Excel menu; only a macro or the file's XML shows it")
    dn = re.findall(r"<definedName\b([^>]*)>(.*?)</definedName>", txt, re.S)
    if dn:
        broken = [(re.search(r'name="([^"]+)"', a).group(1) if re.search(r'name="([^"]+)"', a) else "?", v) for a, v in dn if "#REF!" in v]
        hidden = [a for a, v in dn if 'hidden="1"' in a]
        ext = [v for a, v in dn if "[" in v]
        look.fact("defined_names", len(dn))
        look.line(f"Named ranges: {len(dn)}" + (f", {len(hidden)} hidden" if hidden else "") + (f", {len(broken)} broken (#REF!)" if broken else "") + ".", 52)
        for n, v in broken[:6]:
            look.flag("BROKEN-NAME", n, v[:60], "the named range points at a deleted cell; formulas using it return #REF!")
        for v in ext[:3]:
            look.flag("EXTERNAL-LINK", "named range", v[:80], "a name points into another workbook")
    for n in names:
        if re.match(r"xl/externalLinks/_rels/.+\.rels$", n):
            rel = z.read(n).decode("utf-8", "replace")
            for t in re.findall(r'Target="([^"]+)"', rel)[:4]:
                look.flag("EXTERNAL-LINK", "externalLinks", t[:100], "values are pulled from another file that may be missing or changed; not followed")
    macrosheets = [n for n in names if n.startswith("xl/macrosheets/")]
    if macrosheets:
        look.flag("XLM-MACRO", "macrosheets", f"{len(macrosheets)} Excel 4.0 macro sheet(s)", "legacy macros that run formulas as code; common in malware; not run")
    counts = {k: sum(1 for n in names if n.startswith(p)) for k, p in (("tables", "xl/tables/table"), ("pivot tables", "xl/pivotTables/pivotTable"), ("charts", "xl/charts/chart"),
                                                                          ("comment parts", "xl/comments"), ("drawings", "xl/drawings/drawing"))}
    counts = {k: v for k, v in counts.items() if v}
    if counts:
        look.line("Workbook parts: " + ", ".join(f"{v} {k}" for k, v in counts.items()) + ".", 48)
    for n in names:
        if n.startswith("xl/tables/table") and n.endswith(".xml"):
            t = z.read(n).decode("utf-8", "replace")
            m = re.search(r'<table\b[^>]*\bdisplayName="([^"]+)"[^>]*\bref="([^"]+)"', t) or re.search(r'<table\b[^>]*\bref="([^"]+)"[^>]*\bdisplayName="([^"]+)"', t)
            if m:
                look.mapline(f"Table {m.group(1)} at {m.group(2)}", 40)


def sheet_report(look, name, cells, formulas, raw_xml):
    """Formula shapes and error values of one sheet. cells: {(row, col): value}; formulas: [(ref, formula)]."""
    plain = [(ref, f) for ref, f in formulas if f != "(shared)"]
    if raw_xml:
        errs = ERR.findall(raw_xml[:60 << 20])
        if errs:
            kinds = Counter(v.decode("utf-8", "replace") for _, v in errs)
            look.flag("ERROR-VALUES", name, f"{len(errs)} cells show errors: " + ", ".join(f"{k} x{n}" for k, n in kinds.most_common(4)) + f"; first {errs[0][0].decode()}",
                      "#REF! and #DIV/0! mean a formula lost its inputs")
    if not plain:
        return
    by_col, fcells = {}, set()
    for ref, f in plain:
        m = re.match(r"([A-Z]+)(\d+)", ref)
        c, r = col_num(m.group(1)) - 1, int(m.group(2)) - 1
        fcells.add((r, c))
        by_col.setdefault(c, []).append((r, ref, f, norm(f, r, c)))
    vol = Counter()
    consts = Counter()
    for ref, f in plain:
        for v in VOLATILE.findall(f):
            vol[v.upper()] += 1
        for n in NUM.findall(re.sub(r'"[^"]*"', "", f)):
            if n not in SKIP_NUMS:
                consts[n] += 1
    if vol:
        look.line(f"{name}: volatile functions recalculate on every change: " + ", ".join(f"{k} x{v}" for k, v in vol.most_common(4)) + ".", 50)
    if consts and sum(consts.values()) >= 3:
        look.line(f"{name}: numbers typed inside formulas: " + ", ".join(f"{k} x{v}" for k, v in consts.most_common(5)) + " (assumptions that should sit in a cell).", 52)
    for c, rows in by_col.items():
        if len(rows) < 8:
            continue
        pats = Counter(p for *_, p in rows)
        top, share = pats.most_common(1)[0][0], pats.most_common(1)[0][1] / len(rows)
        col = cell_name(0, c).rstrip("0123456789")
        odd = [x for x in rows if x[3] != top]
        if share >= 0.85 and odd:
            ex = "; ".join(f"{x[1]}: ={x[2][:40]}" for x in odd[:3])
            look.flag("INCONSISTENT-FORMULA", f"{name}!{col}", f"{len(odd)} of {len(rows)} formulas differ from the column pattern: {ex}", "the odd cell is usually the mistake or the hand edit")
        lo, hi = rows[0][0], rows[-1][0]
        hard = [(r, cc) for (r, cc), v in cells.items() if cc == c and lo < r < hi and (r, cc) not in fcells and v not in ("", None)]
        if share >= 0.85 and hard:
            look.flag("HARDCODED-IN-FORMULA-COLUMN", f"{name}!{col}", f"{len(hard)} typed value(s) inside a formula column, e.g. {cell_name(*sorted(hard)[0])}",
                      "a number pasted over a formula stops updating")
