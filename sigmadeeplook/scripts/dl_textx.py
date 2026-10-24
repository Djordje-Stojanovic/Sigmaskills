"""SigmaDeepLook text structure beyond markdown (fix round 8, ticket 83 P0.14b.H8). Stdlib only.

What a careful reader of any plain-text file wants in step 1, whatever the format is called:
- `rst_headings`: section titles underlined (or over- and underlined) with any punctuation character, levels by order of first use.
- `blocks`: paragraphs, the groups of lines between blank lines (the entries of a catalogue, the cues of a subtitle file).
- `line_starts`: how often each first word or marker opens a line (`msgid 121`, `msgstr 121`, `#: 120`), for files built from repeated records.
- `directives`: `.. note::` style directive names with counts.
- `tail`: the last non-blank lines with their numbers, so a question about the end of the file needs no later step.
- `landmarks` / `marks_lines` (fix round 9): records at fixed positions (1-5, then 10, 20, 25, 30, 40, 50, 75, 100 ... and the middle), so a
  question about the Nth line, row, cue, entry or paragraph is answered in step 1 for the round positions a reader asks about most.
- `rst_structure` (fix round 9): reST title, docinfo fields, tables (grid, simple, list-table, csv-table), code and literal blocks, figures,
  footnotes, targets and substitutions.
Every figure is exact over every line. `facts` puts them into a look; `text_profile` in dl_prof calls it.
"""
import re
from collections import Counter

RULE_RE = re.compile(r"^([!-/:-@\[-`{-~])\1{2,}\s*$")        # three or more of one punctuation character
DIRECTIVE_RE = re.compile(r"^\s*\.\.\s+([\w][\w:+-]*)::")
WORD_RE = re.compile(r"\w+", re.U)
START_RE = re.compile(r"^\s*([^\s\"']{1,16})")
TAIL_LINES = 6
MARK_STEPS = (1, 2, 2.5, 3, 4, 5, 7.5)   # x 10^k: the positions a reader asks about ("the 100th row", "line 250")
MARK_MAJOR = (1, 5)                      # x 10^k: printed first, in their own line


def rst_scan(lines):
    """-> ([[level, title, line_number, character, over_and_under]], beyond): the underlined and the over-and-underlined titles of a reST text,
    levels by order of first use of a style; `beyond` is True when the styles go past the plain `=` and `-` underlines."""
    styles, heads, i, n = {}, [], 0, len(lines)
    beyond = False

    def level(ch, over):
        nonlocal beyond
        if ch not in "=-" or over:
            beyond = True
        return styles.setdefault((ch, over), len(styles) + 1)

    while i < n:
        a = lines[i].rstrip()
        if RULE_RE.match(a) and i + 2 < n:
            t, b = lines[i + 1].rstrip(), lines[i + 2].rstrip()
            if t.strip() and not RULE_RE.match(t) and RULE_RE.match(b) and b[0] == a[0] and len(a) >= len(t.strip()) and len(t) <= 100:
                heads.append([level(a[0], True), t.strip(), i + 2, a[0], True])
                i += 3
                continue
        if a.strip() and not RULE_RE.match(a) and not a[0].isspace() and len(a) <= 100 and i + 1 < n and RULE_RE.match(lines[i + 1].rstrip()):
            u = lines[i + 1].rstrip()
            if (len(u) >= len(a) or len(a) < 4) and (i == 0 or not lines[i - 1].strip()):
                heads.append([level(u[0], False), a.strip(), i + 1, u[0], False])
                i += 2
                continue
        i += 1
    return heads, beyond


def rst_headings(lines):
    """-> [[level, title, line_number]] for underlined and over-and-underlined titles of any punctuation character, or None when the text
    holds no style beyond the `=` and `-` underlines that the markdown reader already handles. Level = order of first use of a style."""
    heads, beyond = rst_scan(lines)
    return [h[:3] for h in heads] if heads and beyond else None


ATX_RE = re.compile(r"^(#{1,6})\s+\S")
SETEXT_RE = re.compile(r"^(=+|-+)\s*$")
LISTITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+\S")


def lines_of(text):
    """The lines of a text as a file's own line numbers count them: a line ends at LF, CR LF or (alone) CR, not at a form feed or U+2028."""
    if "\n" not in text and "\r" in text:
        return text.split("\r")
    return text.replace("\r\n", "\n").split("\n")


def front_matter_end(lines):
    """Index of the line that closes a YAML front matter block (`---` first line, then `---` or `...`), else -1."""
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 200)):
            if lines[i].strip() in ("---", "..."):
                return i
    return -1


def heading_styles(lines, rst=False):
    """-> [(kind, character, count)] in order of first use: kind 'mark' (hashes before the title), 'underline' or 'both' (a line above and below).
    A reST text (`rst`: a .rst file, or directives in it) reads every punctuation character; other text reads `#` marks outside code fences and the
    `=` and `-` underlines of a title, and reads reST underlines only when it has no `#` heading."""
    heads, beyond = rst_scan(lines)
    out = {}

    def from_rst():
        for h in heads:
            k = ("both" if h[4] else "underline", h[3])
            out[k] = out.get(k, 0) + 1
        return [(k, c, n) for (k, c), n in out.items()]
    if heads and rst:
        return from_rst()
    in_code = False
    start = front_matter_end(lines) + 1
    for i, ln in enumerate(lines, 1):
        if i <= start:
            continue
        s = ln.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = ATX_RE.match(ln)
        if m:
            k = ("mark", m.group(1))
        elif i > 1 and SETEXT_RE.match(ln) and len(s) >= 3 and lines[i - 2].strip() and not ATX_RE.match(lines[i - 2]) and not LISTITEM_RE.match(lines[i - 2]):
            k = ("underline", s[0])
        else:
            continue
        out[k] = out.get(k, 0) + 1
    if heads and beyond and not any(k[0] == "mark" for k in out):   # no # heading: a text that uses ~ ^ " underlines is reST whatever its name
        out = {}
        return from_rst()
    return [(k, c, n) for (k, c), n in out.items()]


def styles_text(styles):
    """The print line for heading_styles()."""
    word = {"mark": "", "underline": " underline", "both": " over and under"}
    return ("Heading styles (the character of the line under a title, or the # marks before it; one count per style): "
            + ", ".join(f"'{c}'{word[k]} x{n}" for k, c, n in styles) + ".")


def blocks(lines):
    """Groups of consecutive non-blank lines -> [(first_line, last_line)]."""
    out, start = [], None
    for i, ln in enumerate(lines, 1):
        if ln.strip():
            if start is None:
                start = i
        elif start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(lines)))
    return out


def line_starts(lines, minimum=5, share=0.35):
    """Top first words of non-blank lines when the file is built from repeated markers (the top three open at least `share` of the lines);
    [] for prose. -> [(token, count)]."""
    c = Counter()
    total = 0
    for ln in lines:
        if not ln.strip():
            continue
        total += 1
        m = START_RE.match(ln)
        if m:
            c[m.group(1)] += 1
    top = c.most_common(12)
    if not top or top[0][1] < minimum or sum(x for _, x in top[:3]) < share * total:
        return []
    return [(t, k) for t, k in top if k >= 2]


def directives(lines):
    c = Counter()
    for ln in lines:
        m = DIRECTIVE_RE.match(ln)
        if m:
            c[m.group(1)] += 1
    return c.most_common(12)


def tail(lines, n=TAIL_LINES, width=120):
    """The last `n` non-blank lines as [(line_number, text)], oldest first."""
    out = []
    for i in range(len(lines), 0, -1):
        if lines[i - 1].strip():
            out.append((i, " ".join(lines[i - 1].split())[:width]))
            if len(out) == n:
                break
    return out[::-1]


def facts(look, lines, short, pri=84):
    """Put the structure facts of `lines` into the look; -> the paragraph count (for the Counts line)."""
    n = len(lines)
    bl = blocks(lines)
    ls = line_starts(lines)
    if ls:
        look.line("Line starts (first word of each non-blank line, most frequent): " + "; ".join(f"{t} {k:,}" for t, k in ls), pri - 2, "structure")
    dr = directives(lines)
    if dr:
        look.line("Directives (.. name::): " + "; ".join(f"{t}:: ({k:,})" for t, k in dr), pri - 3, "structure")
    if len(bl) > 1:
        sizes = [b - a + 1 for a, b in bl]
        a, b = bl[-1]
        look.line(f"Paragraphs (blank-line separated blocks): {len(bl):,}; block sizes {min(sizes)}-{max(sizes)} lines, mean {sum(sizes) / len(sizes):.1f}; "
                  f"first block lines {bl[0][0]}-{bl[0][1]}, last block lines {a}-{b}: '{short(' '.join(lines[a - 1:b]), 90)}'", pri - 4, "structure")
    w = Counter(x.lower() for ln in lines for x in WORD_RE.findall(ln))
    if w:
        common = [(x, k) for x, k in w.most_common(60) if len(x) >= 4 and not x.isdigit()][:12]
        look.line(f"Words: {len(w):,} distinct (case-folded), {sum(w.values()):,} in all; most frequent of 4 or more letters: " + ", ".join(f"{x} ({k:,})" for x, k in common), pri - 5, "structure")
    t = tail(lines)
    if t:
        look.line(f"Last lines (the file ends at line {n:,}; the last {len(t)} non-blank lines):\n" + "\n".join(f"{i}: {x}" for i, x in t), pri, "tail")
    if n > TAIL_LINES:
        marks_lines(look, n, lambda k: numbered_line(k, lines[k - 1]), "line", pri - 10, f"Lines at fixed positions ({n:,} lines; blank lines count)")
    return len(bl)


# ---------------------------------------------------------------- records at fixed positions (fix round 9)
def landmarks(n):
    """-> (major, minor): sorted record positions 1..n worth printing. Major: 1, 5, 10, 50, 100, 500 ... the middle and the last record; minor: 2, 3, 4,
    20, 25, 30, 40, 75, 200, 250 ... (positions over n dropped)."""
    if n <= 0:
        return [], []
    major, minor = set(), set()
    for k in range(1, 6):
        (major if k in (1, 5) else minor).add(k)
    e = 10
    while e <= n:
        for m in MARK_STEPS:
            v = int(m * e)
            (major if m in MARK_MAJOR else minor).add(v)
        e *= 10
    major.add((n + 1) // 2)
    major.add(n)
    major = sorted(x for x in major if x <= n)
    minor = sorted(x for x in minor if x <= n and x not in major)
    return major, minor


def is_landmark(k):
    """True when position k (1-based) is one `landmarks` would print for some n >= k (the middle aside): for streams of unknown length."""
    if k <= 5:
        return True
    e = 10
    while e * 10 <= k:
        e *= 10
    return any(int(m * e) == k for m in MARK_STEPS)


def marks_lines(look, n, show, noun, pri=72, title=None, keep=None):
    """Two facts with the records at fixed positions: `show(k)` -> the text of record k (1-based), or None to leave it out. `keep`: the
    positions available (for a stream that kept only some). -> nothing; the facts go into the look."""
    major, minor = landmarks(n)
    if keep is not None:
        major = [k for k in major if k in keep]
        minor = [k for k in minor if k in keep]
    head = title or f"{noun.capitalize()}s at fixed positions ({n:,} in all; #k = the k-th {noun})"
    for part, ks, p in (("", major, pri), (" (more positions)", minor, pri - 8)):
        rows = []
        for k in ks:
            t = show(k)
            if t is not None:
                rows.append(t)
        if rows:
            look.line(f"{head}{part}:" + chr(10) + chr(10).join(rows), p, "marks")


def numbered_line(k, text, width=110):
    t = " ".join(text.split())
    return f"line {k:,}: {t[:width] if t else '(blank)'}"


# ---------------------------------------------------------------- reStructuredText structure (fix round 9)
DOCINFO_RE = re.compile(r"^:([A-Za-z][\w -]{0,30}):\s+(\S.*)$")
GRID_RE = re.compile(r"^\s*\+[-=+]{3,}\+\s*$")
SIMPLE_RE = re.compile(r"^\s*={2,}(\s+={2,})+\s*$")
CODE_DIRECTIVES = {"code-block", "code", "sourcecode", "highlight-block", "doctest", "testcode", "ipython"}
TABLE_DIRECTIVES = {"list-table", "csv-table", "table", "flat-table"}


def rst_structure(lines, heads):
    """-> dict of reST facts: title, docinfo fields, tables, code blocks, figures, footnotes, citations, targets, substitutions, comments."""
    out = {"fields": [], "tables": 0, "code": 0, "figures": 0, "images": 0, "footnotes": 0, "citations": 0, "targets": 0, "substitutions": 0, "toctree": 0}
    if heads:
        out["title"] = heads[0][1]
    for ln in lines[:80]:
        m = DOCINFO_RE.match(ln)
        if m:
            out["fields"].append((m.group(1), m.group(2).strip()))
    n = len(lines)
    in_grid = False
    simple_rules = -1   # rule lines in the current block when the block opened with a rule line, else -1
    for i, ln in enumerate(lines):
        s = ln.strip()
        g = bool(GRID_RE.match(ln))
        if g and not in_grid:
            out["tables"] += 1
        in_grid = g or (in_grid and s.startswith("|"))
        if not s:
            simple_rules = -1
        elif SIMPLE_RE.match(ln):
            if i == 0 or not lines[i - 1].strip():
                simple_rules = 0
            if simple_rules >= 0:
                simple_rules += 1
                if simple_rules == 2:
                    out["tables"] += 1
        m = DIRECTIVE_RE.match(ln)
        if m:
            name = m.group(1).lower()
            if name in TABLE_DIRECTIVES:
                out["tables"] += 1
            elif name in CODE_DIRECTIVES:
                out["code"] += 1
            elif name == "figure":
                out["figures"] += 1
            elif name == "image":
                out["images"] += 1
            elif name == "toctree":
                out["toctree"] += 1
            continue
        if s.startswith(".. [#") or re.match(r"^\.\.\s+\[\d+\]", s):
            out["footnotes"] += 1
        elif re.match(r"^\.\.\s+\[[A-Za-z][\w.-]*\]", s):
            out["citations"] += 1
        elif re.match(r"^\.\.\s+_[^:]+:", s):
            out["targets"] += 1
        elif re.match(r"^\.\.\s+\|[^|]+\|", s):
            out["substitutions"] += 1
        elif s.endswith("::") and not s.startswith(".."):
            j = i + 1   # a literal block: '::' at the end of a paragraph, then a blank line and an indented block
            while j < n and not lines[j].strip():
                j += 1
            if j < n and lines[j][:1].isspace() and j > i + 1:
                out["code"] += 1
    return out


def rst_facts(look, lines, heads, short, pri=86):
    """The reST facts in the look; -> (tables, code blocks) for the counts line."""
    r = rst_structure(lines, heads)
    bits = []
    if r.get("title"):
        bits.append(f"Title: {short(r['title'], 80)}")
    bits += [f"{k}: {short(v, 60)}" for k, v in r["fields"][:12]]
    if bits:
        look.line("Document title and fields: " + "; ".join(bits), pri, "structure")
    extra = [(k, r[k]) for k in ("figures", "images", "footnotes", "citations", "targets", "substitutions", "toctree") if r[k]]
    if extra:
        look.line("reST parts: " + "; ".join(f"{k} {v:,}" for k, v in extra) + f"; tables {r['tables']:,}; code and literal blocks {r['code']:,}", pri - 6, "structure")
    return r["tables"], r["code"]
