"""SigmaDeepLook fix round 14 (ticket 83, P0.14b.H5): fixed-width text tables, and the small exact routes that sets 13's misses showed. Stdlib only.

1. `fixed_table(text)`: a paged report in fixed-width columns is a table. A rule line of dashes split by spaces marks the columns; on every page the
   title block, the header line, the rule line and the page marker repeat and are left out of the rows; a form feed starts a page; a totals block
   follows the last row. A block of at least eight aligned lines without a rule line is read the same way, when it makes up most of the text.
   The table is handed on as tab-separated text with the line of the file for every row, so the delimited-table reader and `--ask` take over.
2. `slide_*`: the title of a slide, scope words for a word count over a presentation (speaker notes, slide text, titles).
3. `char_*`: counting a letter or a value over a netCDF char variable.
"""
import csv
import io
import re

RULE = re.compile(r"^\s*(?:[-=_─━═]{2,}[ \t]+){2,}[-=_─━═]{2,}\s*$")
PAGE_MARK = re.compile(r"(?i)^\s*(?:[-–—]\s*)?(?:(?:стр\w*|page|seite|str|strana|pagina|stranica|p)\.?\s*)?\d+\s*(?:из|of|von|/|od|z|av)\s*\d+\s*(?:[-–—])?\s*$"
                       r"|^\s*[-–—]\s*\d+\s*[-–—]\s*$|^\s*(?:стр\w*|page|seite|str|strana|pagina)\.?\s*\d+\s*$")
PIPE_RULE = re.compile(r"^\s*[-=_─━═]{2,}(?:\s*[+|]\s*[-=_─━═]{2,}){2,}\s*$")   # fix round 15: '-------+--------+-----', columns between pipes
MIN_ROWS = 5
MIN_COLS = 3
SHARE = 0.5            # the rows must be at least this share of the text's non-blank lines


class Fixed:
    """A fixed-width table read from text. rows: cell lists; lines: the line of the file (1-based, as str.splitlines counts) of the header and of each row."""
    def __init__(self, header, rows, lines, spans, head_line, rule_line, pages, before, after, kind):
        self.header, self.rows, self.lines, self.spans = header, rows, lines, spans
        self.head_line, self.rule_line, self.pages, self.before, self.after, self.kind = head_line, rule_line, pages, before, after, kind
        self.ncols = len(header)
        self.between, self.pipe = [], False   # section titles and subtotals between the blocks of rows; a table with pipes between the columns

    @property
    def tsv(self):
        buf = io.StringIO()
        w = csv.writer(buf, delimiter="\t", lineterminator="\n")
        w.writerow(self.header)
        w.writerows(self.rows)
        return buf.getvalue()

    @property
    def linemap(self):
        """For line k of the tab-separated text (1 = the header): the line of the original file."""
        return [self.head_line] + self.lines


def is_rule(line):
    return bool(RULE.match(line) or PIPE_RULE.match(line))


def rule_spans(line):
    return [(m.start(), m.end()) for m in re.finditer(r"[-=_─━═]+" if PIPE_RULE.match(line) else r"\S+", line)]


def fits(line, spans, pipe=False):
    """The line has only spaces between the columns (the last column may run on). A pipe table: a pipe stands in every gap the line reaches, so a
    subtotal line that runs through the columns is no row."""
    reached = 0
    for (a, b), (c, d) in zip(spans, spans[1:]):
        gap = line[b:c]
        if gap.strip(" |+"):
            return False
        if pipe and len(line) > c:
            if "|" not in gap:
                return False
            reached += 1
    if pipe and reached < max(1, (len(spans) - 1) // 2):
        return False
    return not line[:spans[0][0]].strip() if spans[0][0] else True


def cells(line, spans):
    out = []
    for k, (a, b) in enumerate(spans):
        end = len(line) if k == len(spans) - 1 else b
        out.append(line[a:end].strip().replace("\t", " "))
    return out


def blank(s):
    return not s.replace("\f", "").strip()


def ruled(lines):
    """Tables whose columns a rule line of dashes marks (dashes split by spaces, or by '+' / '|' for a table with pipes between the columns). -> Fixed or None."""
    rules = [i for i, ln in enumerate(lines) if is_rule(ln.replace("\f", ""))]
    if len(rules) < 1:
        return None
    sig = {}
    for i in rules:
        sig.setdefault(tuple(rule_spans(lines[i].replace("\f", ""))), []).append(i)
    spans, at = max(sig.items(), key=lambda kv: (len(kv[1]), len(kv[0])))
    spans = list(spans)
    if len(spans) < MIN_COLS:
        return None
    pipe = bool(PIPE_RULE.match(lines[at[0]].replace("\f", "")))
    rows, rline, header, head_line, pages, first_rule = [], [], None, None, 0, at[0]
    for r in at:
        h = r - 1   # the header is the line right above the rule
        if h < 0 or blank(lines[h]) or is_rule(lines[h]):
            continue
        names = cells(lines[h].replace("\f", ""), spans)
        if sum(1 for c in names if c) < max(2, len(spans) // 2):
            continue
        if header is None:
            header, head_line = names, h + 1
        pages += 1
        k = r + 1
        while k < len(lines):
            ln = lines[k]
            if blank(ln) or "\f" in ln or is_rule(ln) or PAGE_MARK.match(ln) or not fits(ln, spans, pipe):
                break
            rows.append(cells(ln, spans))
            rline.append(k + 1)
            k += 1
    if header is None or len(rows) < MIN_ROWS:
        return None
    nonblank = sum(1 for ln in lines if not blank(ln))
    if len(rows) < SHARE * nonblank:
        return None
    first_h = head_line - 1
    before = [(i + 1, lines[i].replace("\f", "").strip()) for i in range(first_h) if not blank(lines[i])]
    last_row = rline[-1] - 1
    after = [(i + 1, lines[i].replace("\f", "").strip()) for i in range(last_row + 1, len(lines)) if not blank(lines[i]) and not PAGE_MARK.match(lines[i])]
    header = [h or f"column {i + 1}" for i, h in enumerate(header)]
    fw = Fixed(header, rows, rline, spans, head_line, first_rule + 1, pages, before, after, "rule")
    if pipe:
        skip = set(rline) | {r + 1 for r in at} | {r for r in at}   # 1-based file lines of the rows, the rule lines and the header lines above them
        fw.between = [(i + 1, lines[i].replace("\f", "").strip()) for i in range(first_h + 1, last_row + 1)
                      if not blank(lines[i]) and (i + 1) not in skip and not PAGE_MARK.match(lines[i])]   # section titles and subtotals between the blocks of rows
        fw.pipe = True
    return fw


def aligned(lines):
    """The biggest block of consecutive non-blank lines whose columns line up without any rule line: at least eight lines, three columns, every gap
    between columns at least two spaces wide and empty in every line. -> Fixed or None."""
    blocks, cur = [], []
    for i, ln in enumerate(lines):
        if blank(ln):
            if cur:
                blocks.append(cur)
            cur = []
        else:
            cur.append((i, ln.replace("\f", "").rstrip()))
    if cur:
        blocks.append(cur)
    nonblank = sum(1 for ln in lines if not blank(ln))
    best = max((b for b in blocks if len(b) >= 8), key=len, default=None)
    if best is None or len(best) < SHARE * nonblank:
        return None
    width = max(len(ln) for _, ln in best)
    occupied = [any(p < len(ln) and ln[p] != " " for _, ln in best) for p in range(width)]
    spans, p = [], 0
    while p < width:
        if occupied[p]:
            q = p
            while q < width and occupied[q]:
                q += 1
            spans.append([p, q])
            p = q
        else:
            p += 1
    merged = []
    for a, b in spans:   # a gap of one space is not a column break
        if merged and a - merged[-1][1] < 2:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    spans = [tuple(x) for x in merged]
    if len(spans) < MIN_COLS:
        return None
    rows = [cells(ln, spans) for _, ln in best]
    head, body = rows[0], rows[1:]
    if sum(1 for c in head if c) < max(MIN_COLS, len(spans) - 1):
        return None
    for k in range(len(spans)):
        if sum(1 for r in rows if r[k]) < 0.6 * len(rows):
            return None
    start_last = spans[-1][0]
    if sum(1 for _, ln in best if len(ln) > start_last) < 0.7 * len(best):
        return None
    i0 = best[0][0]
    before = [(i + 1, lines[i].replace("\f", "").strip()) for i in range(i0) if not blank(lines[i])]
    after = [(i + 1, lines[i].replace("\f", "").strip()) for i in range(best[-1][0] + 1, len(lines)) if not blank(lines[i])]
    return Fixed([h or f"column {i + 1}" for i, h in enumerate(head)], body, [i + 1 for i, _ in best[1:]], spans, i0 + 1, i0 + 1, 1, before, after, "aligned")


def fixed_table(text):
    """-> Fixed when the text is a table in fixed-width columns (a rule line of dashes, or eight aligned lines), else None."""
    lines = text.splitlines()
    if len(lines) < MIN_ROWS + 2:
        return None
    return ruled(lines) or aligned(lines)


def describe(fw, cap=60):
    """The lines that say how the table was read, and the lines around it (title block above, totals below), as (priority, section, text)."""
    nl = chr(10)
    out = []
    unit = "sections" if fw.pipe else "pages"
    pg = f"{fw.pages} {unit} (the title block, header and rule line repeat on each and are left out of the rows)" if fw.pages > 1 else "1 page"
    how = f"rule line {fw.rule_line} marks the columns" if fw.kind == "rule" else "the columns line up (no rule line)"
    out.append((95, "structure", f"Fixed-width table: header at line {fw.head_line}, {how}; {fw.ncols} columns, {len(fw.rows):,} rows over {pg}; page markers and form feeds left out. "
                                  f"Rows, columns and counts below are the table's; the lines around it are printed whole."))

    def show(items, cap=cap):
        return nl.join(f"{i}: {t[:240]}" for i, t in items[:cap]) + (f"{nl}... {len(items) - cap} more lines" if len(items) > cap else "")
    if fw.after:
        out.append((94, "tail", f"Lines after the table ({len(fw.after)} non-blank; totals and notes as the file states them):{nl}" + show(fw.after)))
    if fw.between:
        out.append((91, "structure", f"Lines between the blocks of rows ({len(fw.between)} non-blank: section titles and subtotals as the file states them, left out of the rows):{nl}" + show(fw.between, 12)))
    if fw.before:
        out.append((92, "structure", f"Lines before the table ({len(fw.before)} non-blank; title block of the first page):{nl}" + show(fw.before)))
    return out


# ---------------------------------------------------------------- presentations: a scope word and the title of a slide
QUOTED = re.compile(r"(?<!\w)(?:'[^'\n]{1,80}'|\"[^\"\n]{1,80}\"|“[^”\n]{1,80}”|‘[^’\n]{1,80}’|«[^»\n]{1,80}»)(?!\w)")
NOT_NOTES = re.compile(r"(?i)\b(?:not|excluding|without|ignoring|except|apart\s+from|other\s+than)\s+(?:in\s+|on\s+|from\s+)?(?:the\s+)?(?:speaker\s+|presenter\s+)?notes?\b|\bslide\s+(?:text|body|bodies|content|contents)\b|\bon\s+the\s+slides?\s+themselves\b")
NOTES = re.compile(r"(?i)\b(?:speaker|presenter)\s+notes?\b|\bnotes?\s+(?:pages?|text|sections?|fields?)\b|\bin\s+(?:the\s+)?notes\b|\bnotes?\b")
TITLES = re.compile(r"(?i)\b(?:slide\s+)?titles?\b|\bheadlines?\b|\bheadings?\b")
SPEAKER = re.compile(r"(?i)\b(?:speaker|presenter)\s+notes?\b")


def scope_of(q):
    """The scope words of a word-count question over a presentation -> 'slides' (slide text, not the notes), 'notes' (speaker notes only), 'titles', or None.
    The quoted target is left out first, so a counted word 'notes' or 'title' names no scope."""
    rest = QUOTED.sub(" ", q)
    if NOT_NOTES.search(rest):
        return "slides"
    if NOTES.search(rest):
        return "notes"
    if TITLES.search(rest):
        return "titles"
    return None


def wants_speaker_notes(q):
    return bool(SPEAKER.search(QUOTED.sub(" ", q)))


ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}
TITLE_Q = re.compile(r"(?i)\b(?:titles?|headlines?|headings?)\b")
LAST_SLIDE = re.compile(r"(?i)\b(?:last|final|closing)\s+slide\b")
FIRST_SLIDE = re.compile(r"(?i)\bfirst\s+slide\b|\b(?:opening|title)\s+slide\b")
NTH_SLIDE = re.compile(r"(?i)\bslide\s+(?:number\s+|no\.?\s*|#\s*|nr\.?\s*)?(\d+)\b|\b(\d+)(?:st|nd|rd|th)\s+slide\b|\b(" + "|".join(ORD) + r")\s+slide\b")


def slide_answer(q, lj):
    """'What is the title of the last slide?' / 'title of slide 4' -> the answer lines from the titles the look kept, or None."""
    titles = (lj.get("facts") or {}).get("slide_titles")
    if not titles or not TITLE_Q.search(q) or re.search(r"(?i)\bhow\s+many\b|\bnumber\s+of\b", q):
        return None
    if LAST_SLIDE.search(q):
        n = len(titles)
    elif FIRST_SLIDE.search(q) and not NTH_SLIDE.search(q):
        n = 1
    else:
        m = NTH_SLIDE.search(q)
        if not m:
            return None
        n = int(m.group(1) or m.group(2)) if (m.group(1) or m.group(2)) else ORD[m.group(3).lower()]
    if not 1 <= n <= len(titles):
        return [f"Answer: there is no slide {n}: the presentation has {len(titles)} slides."]
    t = titles[n - 1]
    return [f"Answer: {t or '(the slide has no text)'} (the title of slide {n} of {len(titles)}; read from the slide's title placeholder, else its first text)"]
