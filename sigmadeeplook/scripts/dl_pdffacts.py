"""SigmaDeepLook: page-level facts of text PDFs (fix round 5).

The questions people ask about a long PDF are mostly "on which page", "what does the table say" and "what total does it state".
This module answers those from the text layer, every page:

- a page index: each page's first line and word count, so "which page holds X" starts from a map;
- stated figures: every line where a total, sum, balance, amount, count or rate is written next to its number, with the page;
- tables: runs of lines that split into the same number of columns (layout text from pdftotext -layout when it is installed,
  PyMuPDF's table finder otherwise, plain text lines as the last resort), each with its page, size, header and rows, and the
  column sums computed here (labelled as computed, never as stated).
"""
import re

import dl_lex as LEX
import dl_prof as P

STATED_RE = LEX.stated_re()   # English, German and Serbian words for a stated total, sum, balance, amount, rate ... (dl_lex.py)
NUM_RE = re.compile(r"(?<![\w.])[-+(]?[$€£¥]?\s?\d{1,3}(?:[,.' ]\d{3})*(?:[.,]\d+)?\s?%?\)?(?![\w])|(?<![\w.])[-+]?\d+(?:[.,]\d+)?\s?%?(?![\w])")
CELL_SPLIT = re.compile(r"\s{2,}|\t")


def to_num(s):
    t = s.strip().replace("$", "").replace("€", "").replace("£", "").replace("¥", "").replace("%", "").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(" ", "").replace("'", "")
    if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    elif re.fullmatch(r"[-+]?\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[-+]?\d+,\d+", t):
        t = t.replace(",", ".")
    try:
        x = float(t)
    except ValueError:
        return None
    return -x if neg else x


def fitz_layout(doc, max_pages=3000):
    """Lines rebuilt from word positions (PyMuPDF): words on one baseline form a line, a gap wider than about 2.5 characters becomes
    a column break (three spaces). -> list of page texts."""
    out = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        try:
            words = page.get_text("words")
        except Exception:
            return None
        rows = []
        for w in sorted(words, key=lambda w: (round(w[3], 0), w[0])):
            x0, y1, txt = w[0], w[3], w[4]
            cw = (w[2] - w[0]) / max(1, len(txt))
            if rows and abs(rows[-1][0] - y1) <= max(2.0, 0.3 * (w[3] - w[1])):
                rows[-1][1].append((x0, w[2], txt, cw))
            else:
                rows.append([y1, [(x0, w[2], txt, cw)]])
        lines = []
        for _, ws in rows:
            ws.sort()
            s = ws[0][2]
            for a, b in zip(ws, ws[1:]):
                gap = b[0] - a[1]
                s += ("   " if gap > 2.5 * max(1.0, (a[3] + b[3]) / 2) else " ") + b[2]
            lines.append(s)
        out.append("\n".join(lines))
    return out


def layout_pages(look, pages, doc=None):
    """-> list of page texts with columns kept (PyMuPDF word positions, else pdftotext -layout), or None."""
    if doc is not None:
        got = fitz_layout(doc, pages or 3000)
        if got and any(t.strip() for t in got):
            return got
    tool = look.tool("pdftotext")
    if not tool or not pages:
        return None
    tmp = look.path_for("_layout.txt")
    r = look.run([tool, "-layout", "-f", "1", "-l", str(pages), "-enc", "UTF-8", str(look.path), str(tmp)])
    if r is None or r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return None
    t = tmp.read_text(encoding="utf-8", errors="replace")
    tmp.unlink(missing_ok=True)
    return t.split("\f")


def find_tables(page_no, text):
    """Runs of at least 3 lines that split (on 2+ spaces or tabs) into the same 2+ columns, one of them numeric."""
    out, run = [], []

    def flush():
        if len(run) >= 3:
            ncol = max(len(c) for c in run)
            if sum(1 for c in run if len(c) == ncol) >= 0.7 * len(run) and any(to_num(x) is not None for r in run[1:] for x in r):
                out.append({"page": page_no, "rows": [r for r in run], "cols": ncol})
        run.clear()
    for ln in text.splitlines():
        cells = [c.strip() for c in CELL_SPLIT.split(ln.strip()) if c.strip()]
        if len(cells) >= 2 and (not run or abs(len(cells) - len(run[0])) <= 1):
            run.append(cells)
        else:
            flush()
            if len(cells) >= 2:
                run.append(cells)
    flush()
    return out


def fitz_tables(doc, max_pages=400):
    out = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        try:
            tabs = page.find_tables()
        except Exception:
            return out
        for t in tabs.tables:
            rows = [[(c or "").strip() for c in r] for r in t.extract()]
            rows = [r for r in rows if any(r)]
            if len(rows) >= 2:
                out.append({"page": i + 1, "rows": rows, "cols": max(len(r) for r in rows)})
    return out


def table_text(t, max_rows=14):
    rows = t["rows"]
    head = rows[0]
    body = rows[1:]
    sums = []
    for c in range(t["cols"]):
        vals = [to_num(r[c]) for r in body if c < len(r)]
        nums = [v for v in vals if v is not None]
        if len(nums) >= 2 and len(nums) >= 0.6 * len(body):
            name = head[c] if c < len(head) else f"column {c + 1}"
            sums.append(f"{name} {P.fmt(round(sum(nums), 6))} (min {P.fmt(min(nums))}, max {P.fmt(max(nums))})")
    s = f"Table on page {t['page']} ({len(rows)} rows x {t['cols']} columns):\n" + "\n".join("  " + " | ".join(r) for r in rows[:max_rows])
    if len(rows) > max_rows:
        s += f"\n  ... {len(rows) - max_rows} more rows"
    if sums:
        s += "\n  Column sums over every row of the table, computed here (not stated in the PDF): " + "; ".join(sums)
    return s


def page_facts(look, pages_txt, doc=None, n_pages=0):
    """pages_txt: [(page number, text)] from the text layer."""
    pages_txt = [(n, t) for n, t in pages_txt if t.strip()]
    if not pages_txt:
        return
    lay = layout_pages(look, n_pages or max(n for n, _ in pages_txt), doc)
    if lay:   # lines rebuilt from positions: one printed line per visual line, columns kept apart
        look.write_text("layout.txt", "\n".join(f"<!-- page {i} -->\n{t}" for i, t in enumerate(lay, 1)), "text per page with visual lines and columns kept (for tables)", value=2, inline=False)
        by_no = dict(pages_txt)
        pages_txt = [(i, t) for i, t in enumerate(lay, 1) if t.strip() or by_no.get(i, "").strip()]
    rows = []
    for n, t in pages_txt:
        first = next((x.strip() for x in t.splitlines() if x.strip()), "")
        rows.append(f"p{n}: {P.short(first, 70)} ({len(t.split())} words)")
    look.line("Page index (first line of each page with text, words):\n" + "\n".join(rows[:40]) + (f"\n... {len(rows) - 40} more pages below" if len(rows) > 40 else ""),
              91 if len(rows) <= 40 else 85, "pages")
    for k in range(40, len(rows), 80):
        look.line("Page index (continued):\n" + "\n".join(rows[k:k + 80]), 30, "pages")
    stated = []
    for n, t in pages_txt:
        for ln in t.splitlines():
            s = " ".join(ln.split())
            if len(s) <= 200 and STATED_RE.search(s) and NUM_RE.search(s):
                stated.append(f"p{n}: {s}")
    if stated:
        look.fact("stated_figures", stated[:400])
        look.line(f"Figures stated in the text ({len(stated)} lines naming a total, sum, amount, rate or count next to a number; page: line):\n" + "\n".join(stated[:30])
                  + (f"\n... {len(stated) - 30} more below" if len(stated) > 30 else ""), 93, "stated")
        for k in range(30, min(len(stated), 2000), 60):
            look.line("Figures stated in the text (continued):\n" + "\n".join(stated[k:k + 60]), 32, "stated")
    tables = []
    for n, t in pages_txt:
        tables += find_tables(n, t)
    if not tables and doc is not None and not lay:
        tables = fitz_tables(doc)
    if tables:
        look.fact("tables", [{"page": t["page"], "rows": len(t["rows"]), "cols": t["cols"]} for t in tables[:200]])
        look.line(f"Tables found: {len(tables)} on pages " + ", ".join(str(p) for p in sorted({t['page'] for t in tables})[:60]) + " (rows x columns: "
                  + ", ".join(f"p{t['page']} {len(t['rows'])}x{t['cols']}" for t in tables[:30]) + ")", 90, "tables")
        for k, t in enumerate(tables[:200]):
            look.line(table_text(t), 86 - min(40, 4 * k) if k < 6 else 34, "tables")
            try:   # each table as rows for --ask, numbers in plain form (1,234.50 -> 1234.5)
                import dl_ask
                body = [[f"p{t['page']} row {i}", [(lambda x: x if x is None else repr(x))(to_num(c)) if to_num(c) is not None else c for c in r]]
                        for i, r in enumerate(t["rows"][1:], 1)]
                dl_ask.store_table(look, f"table {k + 1} on page {t['page']}", t["rows"][0], body, f"the PDF text layer, page {t['page']}", "table row")
            except OSError as e:
                look.fail("table for --ask", "stdlib", e)
