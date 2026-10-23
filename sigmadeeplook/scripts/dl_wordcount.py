"""SigmaDeepLook: whole-word counts over the full text of a document, and its capitalised-word list (fix round 11). Stdlib only.

`--ask "How many times does the word 'Iraq' appear ...?"` and `--ask "In how many paragraphs does the word 'Saddam' appear?"` are text
questions, not table questions. The answer counts the target as a whole word over the whole extracted text of the look (text.md or
slides.md: Word, OpenDocument, PDF, PowerPoint), so a count never rests on a clipped print. The target is the quoted word or phrase of the
question. The count is case-sensitive when the target holds a capital letter, as the question wrote it, and ignores case otherwise.
A form such as "Iraq's" counts as the word; "Iraqi" does not. The answer names the text it counted and what it took for a paragraph.

Fix round 12: a plain text file (txt, md, rst) is counted too, with its real line numbers (a paragraph is a block between blank lines); a question
about a table ("column", "row", ...) is judged without the quoted word, so `'Table'` is a word to count, not a table to read; when the letters of the
target also sit inside a longer word ("AB1234Capsules"), the answer gives both figures; the frequent-word list uses the same whole-word rule as `--ask`.

`vocab_line(look)` adds one fact line to a document's look: the ten most frequent capitalised words (names, places, terms) with counts.
"""
import re
from collections import Counter
from pathlib import Path

import dl_textx

PRIMARY = ("text.md", "slides.md")        # the artifacts that hold the whole text of a document
DOC_TYPES = ("office", "pdf", "book")
QUOTED = re.compile(r"(?<!\w)(?:'([^'\n]{1,80})'|\"([^\"\n]{1,80})\"|“([^”\n]{1,80})”|‘([^’\n]{1,80})’|«([^»\n]{1,80})»)(?!\w)")
LEAD = re.compile(r"(?i)\b(?:word|term|phrase|name|string|text|expression)s?\s*$")
OCC = re.compile(r"(?i)\bhow many (?:times|occurrences|instances|mentions|appearances)\b|\bhow often\b|\bnumber of (?:times|occurrences|instances|mentions|appearances)\b"
                 r"|\b(?:count|tally|total)(?: of)? (?:the )?(?:times|occurrences|instances|mentions|appearances)\b")
UNIT = re.compile(r"(?i)\bhow many (paragraph|line|page|slide)s?\b|\bnumber of (paragraph|line|page|slide)s?\b")
TABLE_WORDS = re.compile(r"(?i)\b(?:column|field|row|table|sheet|cell|record)s?\b")   # a question about a table's cells is the table path's
PAGE_RE = re.compile(r"^<!--\s*page\s+(\d+)\b[^>]*-->$", re.I)
SLIDE_RE = re.compile(r"^##\s+Slide\s+(\d+)\b", re.I)
WORD = re.compile(r"(?<!\w)[^\W\d_]{3,}(?!\w)")   # a word of letters, not joined to a digit or an underscore: the same rule as pattern() with whole=True
PLAIN = (".txt", ".text", ".md", ".markdown", ".rst", ".rest", ".mdx")
READ_CAP = 2 << 20


def target_of(q):
    """The quoted word or phrase of the question (the one that follows 'the word' when several are quoted), else a capitalised word after 'word'."""
    found = [(m.start(), next(g for g in m.groups() if g)) for m in QUOTED.finditer(q)]
    if found:
        for at, t in found:
            if LEAD.search(q[:at]):
                return t.strip()
        return found[0][1].strip()
    for rx in (r"\b(?:word|name|term)\s+([A-Z][\w’'-]*[\w])",
               r"\b(?:does|do)\s+(?:the\s+)?(?:(?:word|name|term)\s+)?([A-Z][\w’'-]*[\w])\s+(?:appear|occur|show up|come up)",
               r"\b(?:mention|contain|include|use)s?\s+(?:the\s+)?(?:(?:word|name|term)\s+)?([A-Z][\w’'-]*[\w])"):
        m = re.search(rx, q)
        if m:
            return m.group(1)
    return None


def parse(q):
    """-> (target, unit or None, case_sensitive, whole_word) or None when this is not a word-count question."""
    t = target_of(q)
    if not t or not 1 <= len(t) <= 80 or TABLE_WORDS.search(QUOTED.sub(" ", q)):
        return None
    u = UNIT.search(q)
    if not u and not OCC.search(q):
        return None
    sub = bool(re.search(r"(?i)\bsubstring\b|\banywhere in\b|\bpart of (?:a|any|another) word\b|\binside other words\b", q))
    if re.search(r"(?i)\bcase[- ]insensitive\b|\bignor\w* (?:the )?case\b|\bany case\b", q):
        cs = False
    else:
        cs = any(c.isupper() for c in t) or bool(re.search(r"(?i)\bcase[- ]sensitive\b|\bexact case\b", q))
    return t, (u.group(1) or u.group(2)).lower() if u else None, cs, not sub


def pattern(target, cs, whole):
    body = r"\s+".join(re.escape(x) for x in target.split())
    return re.compile((r"(?<!\w)" + body + r"(?!\w)") if whole else body, 0 if cs else re.I)


def primary_text(lj):
    """-> (name, text, capped, plain) of the artifact that holds the document's whole text, or None."""
    capped = {f.get("where") for f in lj.get("flags", []) if f.get("kind") == "TRUNCATED"}
    for a in lj.get("artifacts", []):
        p = Path(a["path"])
        if p.name in PRIMARY and p.is_file() and a.get("kind") == "text":
            return p.name, p.read_text(encoding="utf-8", errors="replace"), p.name in capped, False
    return None


def plain_text(lj):
    """A plain text file (txt, md, rst) read whole (up to 2 MB) in its own encoding -> (name, text, capped, True), or None."""
    p = Path(lj.get("file") or "")
    if p.suffix.lower() not in PLAIN or not p.is_file():
        return None
    import dl_core as core
    with open(p, "rb") as fh:
        raw = fh.read(READ_CAP + 1)
    text, _enc = core.decode_text(raw[:READ_CAP])
    return (p.name, text, len(raw) > READ_CAP, True) if text is not None else None


def paragraphs(text):
    """Non-empty lines of the extracted text, markers and slide headings left out -> [(number, text, page or slide)]."""
    out, unit = [], None
    for ln in text.splitlines():
        s = ln.strip()
        m = PAGE_RE.match(s) or SLIDE_RE.match(s)
        if m:
            unit = int(m.group(1))
            continue
        if s:
            out.append((len(out) + 1, s, unit))
    return out


def plain_units(text, unit):
    """The lines of a plain text file with their own line numbers, or (unit 'paragraph') its blocks between blank lines numbered by their first line."""
    lines = [(i, ln.strip()) for i, ln in enumerate(dl_textx.lines_of(text), 1)]
    if unit != "paragraph":
        return [(i, s, None) for i, s in lines if s]
    out, block = [], []
    for i, s in lines + [(0, "")]:
        if s:
            block.append((i, s))
        elif block:
            out.append((block[0][0], " ".join(x for _, x in block), None))
            block = []
    return out


def inside_example(units, rx_whole, rx_letters, target):
    """A longer word that holds the target's letters where no whole-word hit sits ('AB1234Capsules'), or ''."""
    body = r"\s+".join(re.escape(x) for x in target.split())
    for _, p, _ in units:
        if rx_letters.search(p) and not rx_whole.search(p):
            m = re.search(r"[\w’'-]*" + body + r"[\w’'-]*", p, rx_letters.flags & re.I)
            return m.group(0) if m else ""
    return ""


def answer(q, lj):
    """-> the answer lines, or None when the question is not a word count or the look holds no whole text."""
    import dl_askx   # fix round 12: headings by underline character, bytes per stored picture row
    extra = dl_askx.answer(q, lj)
    if extra:
        return extra
    pq = parse(q)
    if not pq:
        return None
    src = primary_text(lj) if lj.get("type") in DOC_TYPES else plain_text(lj)
    if not src:
        return None
    target, unit, cs, whole = pq
    name, text, capped, plain = src
    paras = plain_units(text, unit) if plain else paragraphs(text)
    noun_all = "non-empty lines" if plain and unit != "paragraph" else "non-empty paragraphs" if not plain else "paragraphs (blocks between blank lines)"
    rx = pattern(target, cs, whole)
    hits = [(n, p, u) for n, p, u in paras if rx.search(p)]
    occ = sum(len(rx.findall(p)) for _, p, _ in paras)
    words = sum(len(p.split()) for _, p, _ in paras)
    mode = ("case-sensitive" if cs else "any case") + ("" if whole else ", also inside longer words")
    lets = ""   # the letters of the target also sit inside a longer word: both figures are given (a count of "the word" may mean either)
    if whole and unit not in ("page", "slide"):
        rl = pattern(target, cs, False)
        sub = [(n, p, u) for n, p, u in paras if rl.search(p)]
        if len(sub) > len(hits):
            ex = inside_example(paras, rx, rl, target)
            lets = (f"{len(sub):,} {unit or ('line' if plain else 'paragraph')}s hold the letters '{target}' ({len(sub) - len(hits):,} only inside a longer word"
                    + (f", e.g. '{ex}'" if ex else "") + ")")
    lines = []
    if unit in ("page", "slide") and not any(u is not None for _, _, u in paras):
        lines.append(f"Answer: not countable per {unit}: {name} has no {unit} markers (only PDF text keeps pages, only PowerPoint files keep slides). "
                     f"The word appears in {len(hits):,} of {len(paras):,} {noun_all}.")
    elif unit in ("page", "slide"):
        keys = sorted({u for _, _, u in hits if u is not None})
        lines.append(f"Answer: {len(keys):,} {unit}{' contains' if len(keys) == 1 else 's contain'} '{target}' ({mode}): numbers {', '.join(str(k) for k in keys[:40])}" + (f" ... +{len(keys) - 40} more" if len(keys) > 40 else ""))
    elif unit:
        numbering = "numbered from 1" if not plain else "numbered by its first line" if unit == "paragraph" else "numbered by line"
        lines.append(f"Answer: {len(hits):,} {unit}{' contains' if len(hits) == 1 else 's contain'} '{target}' ({mode})" + (f"; {lets}" if lets else "")
                     + f"; {numbering} in {name}: " + ", ".join(str(n) for n, _, _ in hits[:40]) + (f" ... +{len(hits) - 40} more" if len(hits) > 40 else ""))
    else:
        lines.append(f"Answer: {occ:,} whole-word occurrences of '{target}' ({mode})" if whole else f"Answer: {occ:,} occurrences of '{target}' ({mode})")
    if unit:
        lines.append(f"In all: {occ:,} {'whole-word ' if whole else ''}occurrences of '{target}'.")
    else:
        lines.append(f"In {len(hits):,} of {len(paras):,} {noun_all}" + (f"; {lets}" if lets else "") + ".")
    if cs and whole:
        lines.append(f"Ignoring case: {sum(len(pattern(target, False, True).findall(p)) for _, p, _ in paras):,} occurrences. Inside longer words too (case-sensitive): "
                     f"{sum(len(pattern(target, True, False).findall(p)) for _, p, _ in paras):,}.")
    what = "the full extracted text of the document" if not plain else "the whole file"
    lines.append(f"Counted over {name}, {what} ({words:,} words, {len(paras):,} {noun_all}); a table row is one paragraph."
                 if not plain else f"Counted over {name}, {what} ({words:,} words, {len(paras):,} {noun_all}).")
    if capped:
        lines[-1] += " PARTIAL: that file is capped at 2 MB, the text has more."
    return lines


def vocab_line(look):
    """The ten most frequent capitalised words of the document with counts: a capitalised word that is written in lower case less often."""
    if look.type not in DOC_TYPES:
        return
    src = next((Path(a["path"]) for a in look.artifacts if Path(a["path"]).name in PRIMARY and a.get("kind") == "text"), None)
    if src is None or not src.is_file():
        return
    paras = paragraphs(src.read_text(encoding="utf-8", errors="replace"))
    cap, low = Counter(), Counter()
    for _, p, _ in paras:
        for w in WORD.findall(p):
            if w[0].isupper():
                cap[w] += 1
            elif w == w.lower():
                low[w] += 1
    top = sorted(((w, n) for w, n in cap.items() if n > low[w.lower()]), key=lambda t: (-t[1], t[0]))[:10]
    if top:
        look.line(f"Most frequent capitalised words (case-sensitive counts of whole words over {src.name}, the full text: {sum(len(p.split()) for _, p, _ in paras):,} words, "
                  f"{len(paras):,} non-empty paragraphs; a word joined to a digit or an underscore, such as Table11, is not counted): " + ", ".join(f"{w} {n}" for w, n in top) + ".", 82, "vocabulary")
