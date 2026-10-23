"""SigmaDeepLook: exact counts for Office files (fix round 4). Stdlib only; read straight from the OOXML parts.

- `props`: core, app and custom document properties (author, last modified by, created, modified, revision, application, the
  page / word / paragraph counts Word stored the last time it saved).
- `docx_counts`: paragraphs counted on the whole body (every w:p, with the empty ones, the ones in tables, headings per level,
  list items), tables with rows and cells, sections, page breaks, images, links, fields, bookmarks, words and characters.
- `sheet_aggregates`: per sheet, numeric cells with count, sum, min and max with their cell, text cells, formulas by function,
  every formula cell with its cached value, and a column profile when the first row is a header.
- `pptx_counts`: slides, hidden slides, shapes, pictures, tables, charts, notes, words per slide.
"""
import re
from collections import Counter

import dl_prof as P

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def strip(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _xml(z, name):
    import xml.etree.ElementTree as ET
    try:
        data = z.read(name)
        return None if b"<!ENTITY" in data else ET.fromstring(data)
    except Exception:
        return None


def props(look, z, names, pri=96):
    """Core (docProps/core.xml), app (docProps/app.xml) and custom properties -> one fact; returns the app dict."""
    core = {}
    root = _xml(z, "docProps/core.xml") if "docProps/core.xml" in names else None
    if root is not None:
        for el in root:
            t = strip(el.tag)
            if (el.text or "").strip():
                core[t] = el.text.strip()
    app = {}
    root = _xml(z, "docProps/app.xml") if "docProps/app.xml" in names else None
    if root is not None:
        for el in root:
            t = strip(el.tag)
            if len(el) == 0 and (el.text or "").strip():
                app[t] = el.text.strip()
        titles = [x.text for x in root.iter() if strip(x.tag) == "lpstr" and x.text]
        if titles:
            app["TitlesOfParts"] = ", ".join(titles[:40])
    custom = {}
    root = _xml(z, "docProps/custom.xml") if "docProps/custom.xml" in names else None
    if root is not None:
        for el in root:
            nm = el.attrib.get("name")
            val = next((c.text for c in el if c.text), None)
            if nm:
                custom[nm] = val
    order = ("title", "subject", "creator", "lastModifiedBy", "created", "modified", "lastPrinted", "revision", "keywords", "description", "category", "contentStatus", "language", "identifier", "version")
    bits = [f"{k} {core[k]}" for k in order if k in core] + [f"{k} {v}" for k, v in core.items() if k not in order]
    if bits:
        look.line("Document properties (docProps/core.xml): " + "; ".join(bits), pri, "props")
    keep = ("Application", "AppVersion", "Company", "Manager", "Template", "TotalTime", "Pages", "Words", "Characters", "CharactersWithSpaces", "Lines",
            "Paragraphs", "Slides", "Notes", "HiddenSlides", "MMClips", "PresentationFormat", "DocSecurity", "TitlesOfParts")
    abits = [f"{k} {app[k]}" for k in keep if k in app]
    if abits:
        look.line("Application properties (docProps/app.xml, stored by the app at its last save, not recounted): " + "; ".join(abits), pri - 4, "props")
    if custom:
        look.line(f"Custom properties ({len(custom)}): " + "; ".join(f"{k} = {P.short(v, 60)}" for k, v in custom.items()), pri - 10)
    look.fact("core_properties", core)
    look.fact("app_properties", app)
    return app


def docx_counts(look, z, names, doc):
    """Counts over the whole body of word/document.xml (nothing filtered)."""
    if doc is None:
        return
    body = next((el for el in doc if strip(el.tag) == "body"), doc)
    all_p = [el for el in body.iter() if strip(el.tag) == "p"]

    def ptext(p):
        return "".join(t.text or "" for t in p.iter() if strip(t.tag) == "t")
    in_tables = set()
    tables = [el for el in body.iter() if strip(el.tag) == "tbl"]
    for tb in tables:
        for p in tb.iter():
            if strip(p.tag) == "p":
                in_tables.add(id(p))
    top_p = [el for el in body if strip(el.tag) == "p"]
    nonempty = [p for p in all_p if ptext(p).strip()]
    outside = [p for p in all_p if id(p) not in in_tables]
    outside_nonempty = [p for p in outside if ptext(p).strip()]
    styles, heads, lists = Counter(), Counter(), 0
    for p in all_p:
        st = None
        for pp in p:
            if strip(pp.tag) == "pPr":
                for s in pp:
                    if strip(s.tag) == "pStyle":
                        st = s.attrib.get(W + "val")
                    if strip(s.tag) == "numPr":
                        lists += 1
        styles[st or "(default)"] += 1
        m = re.match(r"(?i)(heading|berschrift|titre|t[ií]tulo)\s*(\d)", st or "")
        if m:
            heads[int(m.group(2))] += 1
        elif (st or "").lower() == "title":
            heads[0] += 1
    rows = sum(1 for tb in tables for r in tb.iter() if strip(r.tag) == "tr")
    cells = sum(1 for tb in tables for c in tb.iter() if strip(c.tag) == "tc")
    tags = Counter(strip(el.tag) for el in body.iter())
    page_breaks = sum(1 for el in body.iter() if strip(el.tag) == "br" and el.attrib.get(W + "type") == "page")
    rendered = tags.get("lastRenderedPageBreak", 0)
    text = "\n".join(ptext(p) for p in all_p)
    words = len(re.findall(r"\S+", text))
    imgs = tags.get("drawing", 0) + tags.get("pict", 0)
    links = tags.get("hyperlink", 0)
    fields = tags.get("fldSimple", 0) + sum(1 for el in body.iter() if strip(el.tag) == "fldChar" and el.attrib.get(W + "fldCharType") == "begin")
    sections = tags.get("sectPr", 0)
    P.counts(look, [("paragraphs (every w:p in the body)", len(all_p)), ("non-empty paragraphs", len(nonempty)), ("empty paragraphs", len(all_p) - len(nonempty)),
                    ("paragraphs outside tables", len(outside)), ("non-empty paragraphs outside tables", len(outside_nonempty)),
                    ("top-level body paragraphs", len(top_p)), ("paragraphs inside tables", len(in_tables)), ("tables", len(tables)), ("table rows", rows), ("table cells", cells),
                    ("headings", sum(heads.values()) or None)] + [(f"heading {k}" if k else "title", heads[k]) for k in sorted(heads)]
             + [("list paragraphs", lists or None), ("sections", sections), ("manual page breaks", page_breaks), ("rendered page breaks (Word's last layout)", rendered or None),
                ("images", imgs or None), ("hyperlinks", links or None), ("fields", fields or None), ("bookmarks", tags.get("bookmarkStart", 0) or None),
                ("words", words), ("characters (no spaces)", len(re.sub(r"\s", "", text))), ("characters with spaces", len(text.replace("\n", "")))], 95, "Word counts")
    look.line("Paragraph styles (count): " + ", ".join(f"{k} {v:,}" for k, v in styles.most_common(20)), 46)
    look.fact("paragraphs_all", len(all_p))
    look.fact("paragraphs_nonempty", len(nonempty))
    # per table: shape and first row
    for i, tb in enumerate(tables[:30], 1):
        trs = [r for r in tb if strip(r.tag) == "tr"]
        first = [("".join(t.text or "" for t in c.iter() if strip(t.tag) == "t")).strip() for c in trs[0] if strip(c.tag) == "tc"] if trs else []
        ncol = max((sum(1 for c in r if strip(c.tag) == "tc") for r in trs), default=0)
        last = [("".join(t.text or "" for t in c.iter() if strip(t.tag) == "t")).strip() for c in trs[-1] if strip(c.tag) == "tc"] if trs else []
        look.line(f"Table {i}: {len(trs)} rows x {ncol} columns; first row: " + " | ".join(P.short(x, 30) for x in first) + "; last row: " + " | ".join(P.short(x, 30) for x in last), 90 - min(20, i), "tables")


def sheet_aggregates(look, name, cells, formulas, header_hint=True):
    """cells: {(row, col): value as text}; formulas: [(ref, formula)]. -> dict of counts for the workbook total."""
    from dl_xl import cell_name
    nums, texts = [], 0
    for (r, c), v in cells.items():
        x = P.as_number(v, True) if isinstance(v, str) else (float(v) if isinstance(v, (int, float)) else None)
        if x is not None:
            nums.append((x, r, c))
        elif str(v).strip():
            texts += 1
    fn = Counter()
    for ref, f in formulas:
        for m in re.findall(r"\b([A-Z][A-Z0-9.]{1,20})\(", f or ""):
            fn[m] += 1
    nr = max((r for r, c in cells), default=-1) + 1
    nc = max((c for r, c in cells), default=-1) + 1
    d = {"cells": len(cells), "numbers": len(nums), "text": texts, "formulas": len(formulas), "rows": nr, "cols": nc}
    if nums:
        lo = min(nums, key=lambda t: (t[0], t[1], t[2]))
        hi = max(nums, key=lambda t: (t[0], -t[1], -t[2]))
        tot = sum(t[0] for t in nums)
        d.update(sum=tot, min=lo[0], max=hi[0])
        look.line(f"Sheet {name}: {len(cells):,} non-empty cells ({len(nums):,} numbers, {texts:,} text, {len(formulas):,} formulas); used range A1:{cell_name(nr - 1, nc - 1) if nr and nc else 'A1'}; "
                  f"numbers sum {P.fmt(tot)}, min {P.fmt(lo[0])} at {cell_name(lo[1], lo[2])}, max {P.fmt(hi[0])} at {cell_name(hi[1], hi[2])}, mean {P.fmt(tot / len(nums))}"
                  + (f"; functions: " + ", ".join(f"{k} x{v}" for k, v in fn.most_common(10)) if fn else "") + ".", 91, "profile")
    else:
        look.line(f"Sheet {name}: {len(cells):,} non-empty cells ({texts:,} text, {len(formulas):,} formulas), no numbers.", 89, "profile")
    if formulas:
        formula_patterns(look, name, cells, formulas)
    # a table with a header row: profile by column
    if header_hint and nr >= 3 and nc >= 1:
        hdr_row = min((r for r, c in cells), default=0)
        hdr = [cells.get((hdr_row, c), "") for c in range(nc)]
        if sum(1 for h in hdr if str(h).strip() and P.as_number(h, True) is None) >= max(1, 0.6 * sum(1 for h in hdr if str(h).strip())):
            prof = P.Profiler(True, "row")
            cols = prof.columns([str(h).strip() or f"col {cell_name(0, c).rstrip('0123456789')}" for c, h in enumerate(hdr)])
            totals = summary_rows(cells, formulas, hdr_row, nr, nc)
            for r in range(hdr_row + 1, nr):
                vals = [cells.get((r, c), "") for c in range(nc)]
                if r not in totals and any(str(v).strip() for v in vals):
                    prof.add_row(cols, vals, r + 1)
            if totals:
                look.fact("summary_rows", {name: sorted(r + 1 for r in totals)})
                look.line(f"Total rows on {name} (left out of the column profile below, so sums and maxima cover data rows only): " + "; ".join(
                    f"row {r + 1}: " + ", ".join(f"{str(hdr[c]).strip() or cell_name(0, c).rstrip('0123456789')} = {P.short(cells.get((r, c)), 24)}"
                                                 for c in range(nc) if str(cells.get((r, c), "")).strip()) for r in sorted(totals)[:8]), 90, "profile")
            if prof.n:
                sp = P.SecondPass(prof)
                nm = [f.name for f in cols]
                for r in range(hdr_row + 1, nr):
                    vals = [cells.get((r, c), "") for c in range(nc)]
                    if r not in totals and any(str(v).strip() for v in vals):
                        sp.add_row(nm, vals, r + 1)
                try:
                    import dl_ask
                    dl_ask.store_table(look, f"sheet {name}", [f.name for f in cols], [[r + 1, [cells.get((r, c), "") for c in range(nc)]] for r in range(hdr_row + 1, nr)
                                                                                      if r not in totals and any(str(cells.get((r, c), "")).strip() for c in range(nc))],
                                       f"sheet {name} (total rows left out)", "row")
                except OSError as e:
                    look.fail("table for --ask", "stdlib", e)
                look.line(f"Sheet {name} as a table (header row {hdr_row + 1}, {prof.n:,} data rows; positions are sheet row numbers):\n" + "\n".join("  " + x for x in prof.field_lines()[:40]), 86, "profile")
                for x in prof.stats_lines() + sp.lines():
                    look.line(f"{name}: {x}", 58, "aggregates")
                for x in prof.enum_lines():
                    look.line(f"{name}: {x}", 40, "values")
    if formulas:
        rows = []
        for ref, f in formulas:
            m = re.match(r"([A-Z]+)(\d+)", ref)
            v = None
            if m:
                cn = 0
                for ch in m.group(1):
                    cn = cn * 26 + ord(ch) - 64
                v = cells.get((int(m.group(2)) - 1, cn - 1))
            rows.append(f"{ref} = {P.short(f, 70)} -> {P.short(v, 30) if v not in (None, '') else '(no cached value)'}")
        for k in range(0, min(len(rows), 2000), 60):
            look.line(f"{name} formulas {k + 1}-{min(len(rows), k + 60)} of {len(rows)} (cell = formula -> cached value):\n" + "\n".join(rows[k:k + 60]), 52 if k == 0 else 25, "formulas")
    return d


TOTAL_LABEL_RE = re.compile(r"(?i)^\s*(grand\s+total|sub-?total|totals?|sum|summe|gesamt(summe)?|insgesamt|total général|totale|ukupno|итого|合计|总计)\b[\s:]*")
AGG_RE = re.compile(r"(?i)\b(SUM|SUBTOTAL|AGGREGATE|AVERAGE|COUNTA?|MIN|MAX)\(\s*\$?([A-Z]+)\$?(\d+)\s*:\s*\$?([A-Z]+)\$?(\d+)")


def summary_rows(cells, formulas, hdr_row, nr, nc):
    """Rows (0-based) below the header that total the rows above: a row whose first text cell is a total label, or a row with an
    aggregate formula over a range of its own column that ends above it. -> set of row indexes."""
    from dl_xl import col_num
    out = set()
    for ref, f in formulas:
        m = re.match(r"([A-Z]+)(\d+)", ref)
        a = AGG_RE.search(f or "")
        if m and a and a.group(2) == a.group(4) == m.group(1) and int(a.group(5)) < int(m.group(2)):
            out.add(int(m.group(2)) - 1)
    for r in range(hdr_row + 1, nr):
        first = next((cells.get((r, c)) for c in range(nc) if str(cells.get((r, c), "")).strip()), "")
        if isinstance(first, str) and TOTAL_LABEL_RE.match(first) and P.as_number(first, True) is None:
            out.add(r)
    return {r for r in out if hdr_row < r < nr}


def formula_patterns(look, name, cells, formulas):
    """Formulas grouped by shape (copies of one formula down a column are one pattern), each with its cells, an example and the
    cached values of the one-off formulas (totals): the per-sheet formula facts in one step-1 line."""
    from dl_xl import col_num, norm
    pats = {}
    for ref, f in formulas:
        m = re.match(r"([A-Z]+)(\d+)", ref)
        if not m or f in (None, "(shared)"):
            continue
        r, c = int(m.group(2)), col_num(m.group(1))
        body = f[1:] if f.startswith("=") else f
        pats.setdefault(norm(body, r, c), []).append((ref, body, r - 1, c - 1))
    if not pats:
        return
    parts = []
    for p, lst in sorted(pats.items(), key=lambda kv: (-len(kv[1]), kv[1][0][2], kv[1][0][3]))[:14]:
        rng = lst[0][0] if len(lst) == 1 else f"{lst[0][0]}..{lst[-1][0]} ({len(lst)} cells)"
        s = f"{rng}: ={P.short(lst[0][1], 60)}"
        if len(lst) <= 3:
            vals = [cells.get((r, c)) for _, _, r, c in lst]
            if any(v not in (None, "") for v in vals):
                s += " -> " + ", ".join(P.short(v, 20) if v not in (None, "") else "(no cached value)" for v in vals)
        parts.append(s)
    look.line(f"Formulas on {name} ({len(formulas)} cells, {len(pats)} distinct shapes; cells: example formula -> cached value of one-off formulas): " + "; ".join(parts)
              + (f"; +{len(pats) - 14} more shapes" if len(pats) > 14 else ""), 88, "formulas")


def pptx_counts(look, z, names):
    slides = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
    notes = [n for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)]
    tot = Counter()
    per, tabs = [], []
    hidden = 0
    for n in slides:
        root = _xml(z, n)
        if root is None:
            continue
        if root.attrib.get("show") in ("0", "false"):
            hidden += 1
        tags = Counter(strip(e.tag) for e in root.iter())
        txt = " ".join(t.text or "" for t in root.iter() if strip(t.tag) == "t")
        w = len(txt.split())
        tot.update({"shapes": tags.get("sp", 0), "pictures": tags.get("pic", 0), "tables": tags.get("tbl", 0), "group shapes": tags.get("grpSp", 0),
                    "graphic frames": tags.get("graphicFrame", 0), "words": w, "paragraphs": tags.get("p", 0)})
        per.append((int(re.findall(r"\d+", n)[-1]), w, tags.get("pic", 0)))
        for ti, tb in enumerate([e for e in root.iter() if strip(e.tag) == "tbl"], 1):
            trs = [r for r in tb if strip(r.tag) == "tr"]
            cell = lambda c: " ".join((t.text or "") for t in c.iter() if strip(t.tag) == "t").strip()   # noqa: E731
            ncol = max((sum(1 for c in r if strip(c.tag) == "tc") for r in trs), default=0)
            tabs.append((int(re.findall(r"\d+", n)[-1]), ti, len(trs), ncol, [cell(c) for c in trs[0] if strip(c.tag) == "tc"] if trs else [], [cell(c) for c in trs[-1] if strip(c.tag) == "tc"] if trs else []))
    charts = sum(1 for n in names if re.match(r"ppt/charts/chart\d+\.xml$", n))
    media = sum(1 for n in names if n.startswith("ppt/media/"))
    layouts = sum(1 for n in names if re.match(r"ppt/slideLayouts/slideLayout\d+\.xml$", n))
    masters = sum(1 for n in names if re.match(r"ppt/slideMasters/slideMaster\d+\.xml$", n))
    P.counts(look, [("slides", len(slides)), ("hidden slides", hidden), ("notes pages", len(notes)), ("shapes", tot["shapes"]), ("pictures", tot["pictures"]),
                    ("tables", tot["tables"]), ("charts", charts), ("media files", media), ("words on slides", tot["words"]), ("text paragraphs", tot["paragraphs"]),
                    ("layouts", layouts), ("masters", masters)], 95, "Slide counts")
    for sl, ti, nr, nc, first, last in tabs[:30]:
        look.line(f"Slide {sl} table {ti}: {nr} rows x {nc} columns; first row: " + " | ".join(P.short(x, 30) for x in first) + "; last row: " + " | ".join(P.short(x, 30) for x in last), 88, "tables")
    if per:
        look.line("Words per slide: " + ", ".join(f"{i}: {w}" for i, w, _ in per) + ". Most words: slide " + str(max(per, key=lambda t: t[1])[0]) + ".", 60)
