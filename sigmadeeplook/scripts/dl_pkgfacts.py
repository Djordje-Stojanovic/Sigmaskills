"""SigmaDeepLook: what an Office package holds besides its text (fix round 11). Stdlib only, regular expressions over the XML parts.

One fact line for docx, xlsx, pptx, odt, ods and odp: the hyperlinks of the body (count and targets, in document order), the pictures and
media files inside the package with their paths and sizes, and the footnote, endnote and comment counts when the format keeps them in
separate parts. The text of the document stays in text.md; these facts are not in the text.
"""
import html
import re

SHOW_LINKS = 8       # link targets printed
SHOW_MEDIA = 8       # media paths printed
ATTR = r'\b{}\s*=\s*"([^"]*)"'
REL_RE = re.compile(r"<Relationship\b[^>]*>", re.S)
NOTE_SKIP = ("separator", "continuationSeparator", "continuationNotice")


def attr(tag, name):
    m = re.search(ATTR.format(re.escape(name)), tag)
    return html.unescape(m.group(1)) if m else None


def part(z, name):
    try:
        return z.read(name).decode("utf-8", "replace")
    except Exception:   # a missing, damaged or over-cap part reads as empty
        return ""


def rels(z, names, owner):
    """{relationship id: (type tail, target)} of the .rels file that belongs to the part `owner`."""
    d, _, f = owner.rpartition("/")
    path = (d + "/" if d else "") + "_rels/" + f + ".rels"
    if path not in names:
        return {}
    out = {}
    for m in REL_RE.finditer(part(z, path)):
        t = m.group(0)
        rid, ty, tg = attr(t, "Id"), attr(t, "Type"), attr(t, "Target")
        if rid:
            out[rid] = ((ty or "").rsplit("/", 1)[-1], tg or "")
    return out


def sort_key(n):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)]


def ooxml_links(z, names, kind):
    """Hyperlink targets in document order: docx w:hyperlink and HYPERLINK fields, xlsx sheet hyperlinks, pptx hlinkClick."""
    out = []
    if kind == "docx":
        doc = next((n for n in names if n in ("word/document.xml",)), None)
        if not doc:
            return out
        r = rels(z, names, doc)
        x = part(z, doc)
        for m in re.finditer(r'<w:hyperlink\b([^>]*)>|<w:instrText\b[^>]*>\s*HYPERLINK\s+(?:\\l\s+)?"([^"]*)"', x):
            if m.group(2) is not None:
                out.append(html.unescape(m.group(2)))
                continue
            rid, anc = attr(m.group(1), "r:id"), attr(m.group(1), "w:anchor")
            out.append(r.get(rid, ("", ""))[1] if rid else "#" + anc if anc else "(no target)")
    elif kind == "xlsx":
        for n in sorted((n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)), key=sort_key):
            r = rels(z, names, n)
            for m in re.finditer(r"<hyperlink\b([^>]*)>", part(z, n)):
                rid, loc = attr(m.group(1), "r:id"), attr(m.group(1), "location")
                out.append(r.get(rid, ("", ""))[1] if rid else "#" + loc if loc else "(no target)")
    elif kind == "pptx":
        for n in sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=sort_key):
            r = rels(z, names, n)
            for m in re.finditer(r"<a:hlink(?:Click|Hover)\b([^>]*)>", part(z, n)):
                rid = attr(m.group(1), "r:id")
                ty, tg = r.get(rid, ("", "")) if rid else ("", "")
                if ty == "hyperlink":
                    out.append(tg)
    return out


def odf_links(z):
    x = part(z, "content.xml")
    return [html.unescape(m.group(1)) for m in re.finditer(r"<text:a\b[^>]*?\bxlink:href\s*=\s*\"([^\"]*)\"", x)]


def media_files(z, names):
    out = []
    for n in names:
        low = n.lower()
        if ("/media/" in low or low.startswith(("pictures/", "media/"))) and not n.endswith("/"):
            try:
                out.append((n, z.getinfo(n).file_size))
            except KeyError:
                continue
    return sorted(out, key=lambda t: sort_key(t[0]))


def note_counts(z, names):
    """Footnotes, endnotes and comments kept in their own parts (docx; xlsx comments)."""
    out = []
    for label, part_name, tag in (("footnotes", "word/footnotes.xml", "w:footnote"), ("endnotes", "word/endnotes.xml", "w:endnote")):
        if part_name in names:
            n = sum(1 for m in re.finditer(rf"<{tag}\b([^>]*)>", part(z, part_name)) if (attr(m.group(1), "w:type") or "") not in NOTE_SKIP)
            out.append((label, n))
    if "word/comments.xml" in names:
        out.append(("comments", len(re.findall(r"<w:comment\b", part(z, "word/comments.xml")))))
    xc = [n for n in names if re.match(r"xl/comments\d*\.xml$", n)]
    if xc:
        out.append(("cell comments", sum(len(re.findall(r"<comment\b", part(z, n))) for n in xc)))
    return out


def package_facts(look, z, names):
    names = set(names)
    st = look.subtype
    kind = {"docm": "docx", "xlsm": "xlsx", "pptm": "pptx"}.get(st, st)
    if kind in ("odt", "ods", "odp"):
        links = odf_links(z)
    elif kind in ("docx", "xlsx", "pptx"):
        links = ooxml_links(z, names, kind)
    else:
        return
    media = media_files(z, names)
    bits = [f"Hyperlinks: {len(links):,}" + (": " + "; ".join(t[:90] for t in links[:SHOW_LINKS]) + (f"; +{len(links) - SHOW_LINKS} more" if len(links) > SHOW_LINKS else "") if links else "")]
    bits.append(f"media files in the package: {len(media):,}" + (" (" + ", ".join(f"{n} ({s} bytes)" for n, s in media[:SHOW_MEDIA])
                                                                           + (f", +{len(media) - SHOW_MEDIA} more" if len(media) > SHOW_MEDIA else "") + ")" if media else ""))
    notes = note_counts(z, names) if kind in ("docx", "xlsx") else []
    bits += [f"{label} {n}" for label, n in notes]
    look.fact("hyperlinks", links[:100])
    look.fact("package_media", [n for n, _ in media[:100]])
    look.line("; ".join(bits) + ".", 91, "structure")
