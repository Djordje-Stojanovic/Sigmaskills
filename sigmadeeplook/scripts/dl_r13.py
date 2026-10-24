"""SigmaDeepLook: facts the first print must carry, and the `--ask` routes that answer them (fix round 13, ticket 83 P0.14b.H5). Stdlib only.

Four things a reader needs from step 1 that held-out set 12 showed only in the 10k print:
- Link and anchor definitions of a markup file: the count, the first and the last, with line numbers (reST `.. _label:`, Markdown `[id]: url`, AsciiDoc
  `[[id]]`, org `<<id>>`, LaTeX `\\label{id}`), and `--ask "the last explicit target"`.
- The depth of a tree: the elements per level of an XML document, the levels of an element that nests in itself (OPML `<outline>`), the nesting depth
  of JSON, YAML and TOML, and `--ask "deepest nesting level"`.
- A pointer line `Ask a word count:` with the right unit (slides, pages, paragraphs, cues), so a reader knows `--ask` counts a word in a document.
- The `gpkg_contents` table of a GeoPackage, in full when short and as counts per data_type when long.
Every figure is exact over the whole file; a cut or capped read says so.
"""
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import dl_textx

READ_CAP = 8 << 20
TABLE_WORDS = re.compile(r"(?i)\b(?:column|field|row|record|cell|sheet|table)s?\b")


QUOTED = re.compile(r"'[^'\n]{1,80}'|\"[^\"\n]{1,80}\"|\u201c[^\u201d\n]{1,80}\u201d|\u2018[^\u2019\n]{1,80}\u2019")


def sid(v, n=60):
    from dl_prof import short_id
    return short_id(v, n, 200)


# ---------------------------------------------------------------- link and anchor definitions
FAMILIES = {   # key: (print head, singular, plural)
    "rst": ("Explicit targets (.. _label:)", "explicit target", "explicit targets"),
    "md": ("Link definitions ([id]: url)", "link definition", "link definitions"),
    "adoc": ("Anchors ([[id]])", "anchor", "anchors"),
    "org": ("Targets (<<id>>)", "target", "targets"),
    "tex": ("Labels (\\label{id})", "label", "labels"),
}
EXT = {".rst": "rst", ".rest": "rst", ".md": "md", ".markdown": "md", ".mdx": "md", ".txt": "md", ".text": "md", ".adoc": "adoc", ".asciidoc": "adoc",
       ".asc": "adoc", ".org": "org", ".tex": "tex", ".ltx": "tex", ".latex": "tex"}
MD_DEF = re.compile(r"^ {0,3}\[(?!\^)([^\]\n]+)\]:[ \t]*\S")
ADOC = re.compile(r"\[\[([A-Za-z_:][\w:.-]*)(?:,[^\]]*)?\]\]|^\[#([A-Za-z_:][\w:.-]*)[^\]]*\]\s*$|\banchor:([\w:.-]+)\[")
ORG = re.compile(r"(?<!<)<<([^<>\n]+)>>(?!>)")
TEX = re.compile(r"\\label\{([^}\n]+)\}")
TEX_COMMENT = re.compile(r"(?<!\\)%.*$")


def family(path, lines):
    suffix = Path(path).suffix.lower()
    f = EXT.get(suffix)
    return "rst" if (f == "md" or not suffix) and len(dl_textx.directives(lines)) >= 2 else f


def defs(lines, fam):
    """-> [(line number, label)] in file order, for the family's definition syntax."""
    out, fence = [], False
    for i, ln in enumerate(lines, 1):
        if fam == "rst":
            lab = dl_textx.rst_target(ln.strip())
            if lab:
                out.append((i, lab))
        elif fam == "md":
            s = ln.lstrip()
            if s[:3] in ("```", "~~~") and len(ln) - len(s) <= 3:
                fence = not fence
            elif not fence:
                m = MD_DEF.match(ln)
                if m:
                    out.append((i, m.group(1).strip()))
        elif fam == "adoc":
            out += [(i, next(g for g in m.groups() if g)) for m in ADOC.finditer(ln)]
        elif fam == "org":
            out += [(i, m.group(1).strip()) for m in ORG.finditer(ln)]
        elif fam == "tex":
            out += [(i, m.group(1).strip()) for m in TEX.finditer(TEX_COMMENT.sub("", ln))]
    return out


def span(ds):
    return f"{len(ds):,}; first '{sid(ds[0][1])}' (line {ds[0][0]}), last '{sid(ds[-1][1])}' (line {ds[-1][0]})"


def anchor_line(look, lines, pri):
    """One line in step 1 of a markup file: how many definitions, the first and the last."""
    fam = family(getattr(look, "path", ""), lines)
    ds = defs(lines, fam) if fam else []
    if ds:
        cut = " (first 8 MB only)" if getattr(look, "size", 0) > READ_CAP else ""
        look.line(f"{FAMILIES[fam][0]}: {span(ds)}{cut}.", pri, "structure")


FIRST = re.compile(r"(?i)\b(?:first|earliest|opening)\b")
LAST = re.compile(r"(?i)\b(?:last|final|latest|closing)\b")
COUNTQ = re.compile(r"(?i)\bhow many\b|\bnumber of\b|\bcount\b|\btotal\b")
NOUN = re.compile(r"(?i)\b(?:target|anchor|label|link (?:reference )?definition|reference (?:link )?definition|link reference|reference definition)s?\b|\\label")


def read_text(lj, cap=READ_CAP):
    """-> (path, text, capped) of the look's file as text, or None."""
    p = Path(lj.get("file") or "")
    if not p.is_file():
        return None
    import dl_core as core
    with open(p, "rb") as fh:
        raw = fh.read(cap + 1)
    text, _enc = core.decode_text(raw[:cap])
    return (p, text, len(raw) > cap) if text is not None else None


def anchor_answer(q, lj):
    """`--ask "the last explicit target"` (also first, and how many): over every line of the file, with the same reader as the step 1 line."""
    import dl_wordcount
    bare = QUOTED.sub(" ", q)   # what the question puts in quotes is a sample or a word to count, not a noun of the question
    if not NOUN.search(bare) or not (FIRST.search(q) or LAST.search(q) or COUNTQ.search(q)) or TABLE_WORDS.search(bare) or dl_wordcount.parse(q):
        return None
    if Path(lj.get("file") or "").suffix.lower() not in EXT:
        return None
    src = read_text(lj)
    if not src:
        return None
    p, text, capped = src
    lines = dl_textx.lines_of(text)
    fam = family(p, lines)
    ds = defs(lines, fam) if fam else []
    if not ds:
        return None
    head, one, many = FAMILIES[fam]
    bits = []
    if COUNTQ.search(q):
        bits.append(f"{len(ds):,} {many if len(ds) != 1 else one}")
    if FIRST.search(q):
        bits.append(f"first {one} '{ds[0][1]}' (line {ds[0][0]})")
    if LAST.search(q):
        bits.append(f"last {one} '{ds[-1][1]}' (line {ds[-1][0]})")
    if not bits:
        return None
    out = ["Answer: " + "; ".join(bits)]
    out.append(f"All {many}: {span(ds)}. Counted over every line of {p.name} ({head}).")
    if capped:
        out.append("PARTIAL: only the first 8 MB of the file was read.")
    return out


# ---------------------------------------------------------------- the depth of a tree
def tree_levels(root, local):
    """-> (elements per level with the root at level 0, {tag: Counter(level -> elements)}); the level of an element for its own tag is 1 + the number of
    ancestors with that tag, so the outermost <outline> is level 1. Iterative: a deep tree cannot overflow the stack."""
    levels, nest, path = Counter(), {}, Counter()
    stack = [(root, 0, False)]
    while stack:
        el, d, leaving = stack.pop()
        t = local(el.tag)
        if leaving:
            path[t] -= 1
            continue
        levels[d] += 1
        nest.setdefault(t, Counter())[path[t] + 1] += 1
        path[t] += 1
        stack.append((el, d, True))
        stack.extend((c, d + 1, False) for c in reversed(list(el)))
    return levels, nest


def per_level(counter, first):
    top = max(counter)
    vals = [str(counter.get(k, 0)) for k in range(first, top + 1)]
    return ", ".join(vals[:24]) + (", ..." if len(vals) > 24 else "")


def tree_lines(look, root, local, total, pri):
    """Step 1 of an XML document: elements per level, and the levels of every element that nests in itself."""
    if total > 1_000_000:
        return
    levels, nest = tree_levels(root, local)
    top = max(levels)
    look.line(f"Tree levels: the root <{local(root.tag)}> is level 0 and the deepest element is at level {top}; elements per level 0..{top}: {per_level(levels, 0)}.", pri - 5, "structure")
    nested = sorted(((t, c) for t, c in nest.items() if max(c) >= 2), key=lambda tc: -sum(tc[1].values()))
    for t, c in nested[:2]:
        mx = max(c)
        look.line(f"Nested <{t}> levels: {mx} levels (a <{t}> inside no other <{t}> is level 1); <{t}> elements per level 1..{mx}: {per_level(c, 1)}.", pri, "structure")


DEEP = re.compile(r"(?i)\bdeepest\b|\bhow deep\b|\b(?:max(?:imum)?|greatest|highest|largest)\s+(?:nesting\s+)?(?:depth|nesting)\b|\bnesting\s+(?:depth|level)s?\b|\bdepth\s+of\s+nesting\b"
                  r"|\bhow many\s+levels\b|\blevels?\s+deep\b|\bdepth\s+of\s+the\s+(?:tree|document|file|hierarchy|outline)\b")
SKIP_TAGS = {"the", "and", "what", "level", "levels", "nesting", "deepest", "element", "elements", "file", "document", "tag", "tags", "node", "nodes", "item", "items"}
AMBIGUOUS = {"depth", "level", "levels", "nesting", "deep"}


def load_xml(path):
    """-> (root, local-name function) or (None, reason)."""
    import dl_data
    import xml.etree.ElementTree as ET
    with open(path, "rb") as fh:
        raw = fh.read(dl_data.XML_READ_CAP + 1)
    if len(raw) > dl_data.XML_READ_CAP:
        return None, f"the file is larger than the {dl_data.XML_READ_CAP:,} bytes read for an XML look"
    danger = dl_data.xml_entity_danger(raw)
    if danger:
        return None, f"not parsed: DTD entity expansion ({danger})"
    try:
        try:
            from defusedxml import ElementTree as DET
            root = DET.fromstring(raw, forbid_dtd=False, forbid_entities=False, forbid_external=False)
        except ImportError:
            root = ET.fromstring(raw)
    except Exception as e:
        return None, f"not parsed: {type(e).__name__}: {str(e)[:100]}"
    return root, lambda t: t.rsplit("}", 1)[-1] if isinstance(t, str) else str(t)


def xml_depth_answer(q, lj):
    root, local = load_xml(lj["file"])
    if root is None:
        return [f"Answer: not answered: {local}."]
    names = {local(e.tag).lower() for e in root.iter()} | {local(a).lower() for e in root.iter() for a in e.attrib}
    if names & AMBIGUOUS:
        return None   # the file has an element or attribute named like the question: a table question
    levels, nest = tree_levels(root, local)
    top = max(levels)
    words = set(re.findall(r"[a-z][\w:.-]*", q.lower()))
    named = [t for t in nest if len(t) >= 3 and t.lower() not in SKIP_TAGS and (t.lower() in words or t.lower() + "s" in words)]
    out = []
    if named:
        t = max(named, key=lambda x: max(nest[x]))
        mx = max(nest[t])
        out.append(f"Answer: {mx} level{'s' if mx != 1 else ''} of nested <{t}> (a <{t}> inside no other <{t}> is level 1; the deepest one has {mx - 1} <{t}> ancestor{'s' if mx != 2 else ''}).")
        out.append(f"<{t}> elements per level 1..{mx}: {per_level(nest[t], 1)}.")
        out.append(f"The whole document: the deepest element is at level {top} with the root as level 0 (level {top + 1} with the root as level 1); elements per level 0..{top}: {per_level(levels, 0)}.")
    else:
        out.append(f"Answer: the deepest element is at level {top + 1} counting the root <{local(root.tag)}> as level 1.")
        out.append(f"The same element is at level {top} with the root as level 0; elements per level 0..{top}: {per_level(levels, 0)}.")
        nested = sorted(((t, c) for t, c in nest.items() if max(c) >= 2), key=lambda tc: -sum(tc[1].values()))
        for t, c in nested[:2]:
            out.append(f"<{t}> nests in itself: {max(c)} levels (outermost = level 1); per level: {per_level(c, 1)}.")
    return out


def nest_depth(v):
    """-> (levels of objects and arrays, the top-level container = level 1; every key name seen up to 5000)."""
    best, keys, stack = 0, set(), [(v, 1)]
    while stack:
        x, d = stack.pop()
        if isinstance(x, dict):
            best = max(best, d)
            if len(keys) < 5000:
                keys.update(str(k).lower() for k in x)
            stack.extend((y, d + 1) for y in x.values())
        elif isinstance(x, list):
            best = max(best, d)
            stack.extend((y, d + 1) for y in x)
    return best, keys


def json_depth_answer(q, lj):
    src = read_text(lj, 64 << 20)
    if not src or src[2]:
        return None
    p, text, _ = src
    sub = lj.get("subtype")
    try:
        if sub == "json":
            docs = [json.loads(text)]
        elif sub == "toml":
            import tomllib
            docs = [tomllib.loads(text)]
        else:
            import yaml
            docs = list(yaml.safe_load_all(text))
    except Exception:
        return None
    res = [nest_depth(d) for d in docs]
    if not res or any(k & AMBIGUOUS for _, k in res):
        return None
    mx = max(b for b, _ in res)
    return [f"Answer: {mx} level{'s' if mx != 1 else ''} of nesting (the top-level object or array is level 1; a plain value adds no level).",
            f"Counted over the whole parsed document of {p.name}" + (f" ({len(docs)} YAML documents)" if len(docs) > 1 else "") + "."]


def depth_answer(q, lj):
    if not DEEP.search(q) or re.search(r"(?i)\b(?:folder|directory|path)s?\b", q):
        return None
    sub = lj.get("subtype")
    if sub == "xml":
        return xml_depth_answer(q, lj)
    if sub in ("json", "toml", "yaml"):
        return json_depth_answer(q, lj)
    return None


def answer(q, lj):
    return anchor_answer(q, lj) or depth_answer(q, lj)


# ---------------------------------------------------------------- the word-count pointer
def word_pointer(look, pri=89):
    """'Ask a word count: --ask "on how many <unit> does the word 'X' appear" ...': a reader of step 1 learns that `--ask` counts a word in a document.
    Subtitle files have it already, in their `Find one record` line ("how many cues contain the word 'X'")."""
    import dl_wordcount as W
    unit = None
    if look.type in W.DOC_TYPES:
        names = {Path(a["path"]).name for a in look.artifacts if a.get("kind") == "text"}
        unit = "slides" if "slides.md" in names else ("pages" if look.type == "pdf" else "paragraphs") if "text.md" in names else None
    elif Path(look.path).suffix.lower() in W.PLAIN and look.type != "data" and not getattr(look, "ask_forms_done", False):
        unit = "paragraphs"
    if not unit:
        return
    look.line(f"Ask a word count: --ask \"on how many {unit} does the word 'X' appear\" (whole word, capitals as written); \"how many times does the word 'X' appear\" counts occurrences.", pri, "locate")


# ---------------------------------------------------------------- GeoPackage
def gpkg_rows(con):
    """The rows of gpkg_contents -> [(table_name, data_type, identifier)], or None when the file has no such table."""
    try:
        return [tuple("" if v is None else str(v) for v in r) for r in con.execute("select table_name, data_type, identifier from gpkg_contents")]
    except sqlite3.Error:
        return None


def gpkg_line(rows):
    kinds = Counter(r[1] for r in rows)
    note = {"features": " (feature layers)", "attributes": " (attribute tables)"}
    counts = ", ".join(f"{k or '(none)'} {v}{note.get(k, '')}" for k, v in kinds.most_common())
    if len(rows) <= 25:
        listing = "; ".join(f"{n} {t}" + (f" '{sid(i, 30)}'" if i and i != n else "") for n, t, i in rows)
        return f"GeoPackage contents (gpkg_contents, {len(rows)} rows; table_name data_type, 'identifier' when it differs): {listing}. Rows per data_type: {counts}."
    return f"GeoPackage contents (gpkg_contents, {len(rows):,} rows): rows per data_type: {counts}."
