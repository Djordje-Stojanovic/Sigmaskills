"""SigmaDeepLook text structure beyond markdown (fix round 8, ticket 83 P0.14b.H8). Stdlib only.

What a careful reader of any plain-text file wants in step 1, whatever the format is called:
- `rst_headings`: section titles underlined (or over- and underlined) with any punctuation character, levels by order of first use.
- `blocks`: paragraphs, the groups of lines between blank lines (the entries of a catalogue, the cues of a subtitle file).
- `line_starts`: how often each first word or marker opens a line (`msgid 121`, `msgstr 121`, `#: 120`), for files built from repeated records.
- `directives`: `.. note::` style directive names with counts.
- `tail`: the last non-blank lines with their numbers, so a question about the end of the file needs no later step.
Every figure is exact over every line. `facts` puts them into a look; `text_profile` in dl_prof calls it.
"""
import re
from collections import Counter

RULE_RE = re.compile(r"^([!-/:-@\[-`{-~])\1{2,}\s*$")        # three or more of one punctuation character
DIRECTIVE_RE = re.compile(r"^\s*\.\.\s+([\w][\w:+-]*)::")
WORD_RE = re.compile(r"\w+", re.U)
START_RE = re.compile(r"^\s*([^\s\"']{1,16})")
TAIL_LINES = 6


def rst_headings(lines):
    """-> [[level, title, line_number]] for underlined and over-and-underlined titles of any punctuation character, or None when the text
    holds no style beyond the `=` and `-` underlines that the markdown reader already handles. Level = order of first use of a style."""
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
                heads.append([level(a[0], True), t.strip(), i + 2])
                i += 3
                continue
        if a.strip() and not RULE_RE.match(a) and not a[0].isspace() and len(a) <= 100 and i + 1 < n and RULE_RE.match(lines[i + 1].rstrip()):
            u = lines[i + 1].rstrip()
            if (len(u) >= len(a) or len(a) < 4) and (i == 0 or not lines[i - 1].strip()):
                heads.append([level(u[0], False), a.strip(), i + 1])
                i += 2
                continue
        i += 1
    return heads if heads and beyond else None


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
    return len(bl)
