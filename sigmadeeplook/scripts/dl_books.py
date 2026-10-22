"""SigmaDeepLook: rich documents with their most-asked facts first (fix round 5): EPUB, OpenDocument text and spreadsheets.

Stdlib only. What people ask about a book or a document is its structure (how many chapters or sections, front matter left out),
who wrote it and when, its length, its longest and shortest parts, comments and tracked changes. Those lead the first print here;
the package listing and raw text follow.

- EPUB: every Dublin Core field, spine documents classed front / body / back (epub:type, landmarks, guide, linear="no", titles),
  chapter count without front and back matter, chapter headings in the body text, table-of-contents entries, words per chapter.
- ODT: headings per level with the outline, paragraphs, lists, tables, comments (annotations) with author and date, tracked
  changes (insertions, deletions, format changes) with author and date, notes, images, meta.xml properties and stored statistics.
- ODS: every sheet's cells (repeated rows and columns expanded, empty runs skipped), formulas with cached values, per-sheet
  aggregates and a column profile (the same reader the xlsx path uses).
"""
import os
import re
import zipfile
from collections import Counter

import dl_core as core
import dl_lex as LEX
import dl_prof as P

FRONT_TYPES = {"cover", "titlepage", "title-page", "frontmatter", "toc", "copyright-page", "dedication", "epigraph", "foreword", "preface", "halftitlepage",
               "halftitle", "seriespage", "imprint", "contributors", "other-credits", "landmarks", "loi", "lot", "errata", "frontispiece"}
BACK_TYPES = {"backmatter", "appendix", "glossary", "index", "colophon", "afterword", "acknowledgments", "acknowledgements", "notes", "endnotes", "rearnotes",
              "bibliography", "biblioentry", "conclusion", "credits", "copyright", "about-the-author", "aboutauthor", "afterword"}
FRONT_RE = LEX.front_re()   # headings of front matter, back matter and closing sections in English, German and Serbian (dl_lex.py)
BACK_RE = LEX.back_re()
TAIL_RE = LEX.tail_re()
CHAPTER_HEAD_RE = re.compile(r"^\s*(chapter|chapitre|kapitel|cap[ií]tulo|capitolo|hoofdstuk|rozdział|глава|part|book)\s+([\divxlcdm]+|[a-z-]+)\b", re.I)


def strip_tags(html):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;|&#160;|&#xa0;", " ", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"&[a-z]+;|&#\d+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def classify(label, etype, linear, landmark):
    """-> front | body | back."""
    types = {x.split(":")[-1].lower() for x in (etype or "").split()} | ({landmark} if landmark else set())
    if types & FRONT_TYPES:
        return "front"
    if types & BACK_TYPES:
        return "back"
    if types & {"bodymatter", "chapter", "part", "division", "volume", "prologue", "epilogue", "introduction"}:
        return "body"
    if FRONT_RE.match(label or ""):
        return "front"
    if BACK_RE.match(label or ""):
        return "back"
    if linear == "no":
        return "front"
    return "body"


def opf_meta(opf):
    meta = {}
    for m in re.finditer(r"<dc:(\w+)([^>]*)>(.*?)</dc:\1>", opf, re.S):
        tag, attrs, val = m.group(1), m.group(2), strip_tags(m.group(3))
        if not val:
            continue
        role = re.search(r'role="([^"]+)"', attrs)
        key = tag + (f" ({role.group(1)})" if role else "")
        meta.setdefault(key, []).append(val[:200])
    for m in re.finditer(r'<meta\s+[^>]*property="([^"]+)"[^>]*>(.*?)</meta>', opf, re.S):
        if m.group(1) in ("dcterms:modified", "belongs-to-collection", "group-position", "schema:accessMode", "rendition:layout"):
            meta.setdefault(m.group(1), []).append(strip_tags(m.group(2))[:120])
    for m in re.finditer(r'<meta\s+name="(calibre:series|calibre:series_index|calibre:timestamp|cover)"\s+content="([^"]*)"', opf):
        meta.setdefault(m.group(1), []).append(m.group(2)[:120])
    return meta


def look_epub(look):
    try:
        z = zipfile.ZipFile(look.path)
    except zipfile.BadZipFile:
        return
    names = set(z.namelist())
    opf_name = None
    try:
        cont = z.read("META-INF/container.xml").decode("utf-8", "replace")
        m = re.search(r'full-path="([^"]+)"', cont)
        opf_name = m.group(1) if m else None
    except KeyError:
        pass
    if not opf_name or opf_name not in names:
        look.flag("CORRUPT", "container.xml", "no package document", "not a valid EPUB")
        return
    opf = z.read(opf_name).decode("utf-8", "replace")
    base = os.path.dirname(opf_name)

    def resolve(href):
        p = (base + "/" + href.split("#")[0]).lstrip("/") if base else href.split("#")[0]
        while re.search(r"[^/]+/\.\./", p):
            p = re.sub(r"[^/]+/\.\./", "", p, count=1)
        return p
    items = {}
    for m in re.finditer(r"<item\b([^>]*)/?>", opf):
        a = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1)))
        if "id" in a and "href" in a:
            items[a["id"]] = a
    spine = [dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1))) for m in re.finditer(r"<itemref\b([^>]*)/?>", opf)]
    meta = opf_meta(opf)
    landmarks = {}
    toc_entries, toc_titles, page_list = 0, [], 0
    nav = next((a for a in items.values() if "nav" in a.get("properties", "").split()), None)
    if nav and resolve(nav["href"]) in names:
        navx = z.read(resolve(nav["href"])).decode("utf-8", "replace")
        for blk in re.finditer(r'<nav\b[^>]*epub:type="([^"]+)"[^>]*>(.*?)</nav>', navx, re.S):
            kind, body = blk.group(1), blk.group(2)
            links = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
            if "toc" in kind:
                toc_entries = len(links)
                toc_titles = [strip_tags(t) for _, t in links]
            elif "landmarks" in kind:
                for href, _t in links:
                    lt = re.search(rf'href="{re.escape(href)}"[^>]*epub:type="([^"]+)"|epub:type="([^"]+)"[^>]*href="{re.escape(href)}"', body)
                    if lt:
                        landmarks[resolve(href)] = (lt.group(1) or lt.group(2)).split(":")[-1]
            elif "page-list" in kind:
                page_list = len(links)
    ncx = next((a for a in items.values() if a.get("media-type") == "application/x-dtbncx+xml"), None)
    if not toc_entries and ncx and resolve(ncx["href"]) in names:
        nx = z.read(resolve(ncx["href"])).decode("utf-8", "replace")
        toc_titles = [strip_tags(t) for t in re.findall(r"<navLabel>\s*<text>(.*?)</text>", nx, re.S)]
        toc_entries = len(toc_titles)
    for m in re.finditer(r'<reference\b([^>]*)/?>', opf):   # EPUB 2 guide
        a = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1)))
        if a.get("href") and a.get("type"):
            landmarks.setdefault(resolve(a["href"]), a["type"].lower())
    docs = []
    for it in spine:
        a = items.get(it.get("idref", ""))
        if not a:
            continue
        p = resolve(a["href"])
        if p not in names:
            continue
        if z.getinfo(p).file_size > 8 << 20:
            look.flag("TRUNCATED", p, "document larger than 8 MB not read", "")
            continue
        html = z.read(p).decode("utf-8", "replace")
        t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        h = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.S)
        et = re.search(r'<(?:body|section)\b[^>]*epub:type="([^"]+)"', html)
        heads = [strip_tags(x) for x in re.findall(r"<h[1-2][^>]*>(.*?)</h[1-2]>", html, re.S)]
        txt = strip_tags(re.sub(r"<head>.*?</head>", " ", html, flags=re.S))
        label = (strip_tags(h.group(1)) if h else "") or (strip_tags(t.group(1)) if t else "") or p
        kind = classify(label, et.group(1) if et else "", it.get("linear"), landmarks.get(p))
        docs.append({"path": p, "label": label[:80], "kind": kind, "etype": (et.group(1) if et else ""), "words": len(txt.split()), "text": txt, "heads": heads, "images": len(re.findall(r"<img\b|<image\b", html))})
    body = [d for d in docs if d["kind"] == "body"]
    front = [d for d in docs if d["kind"] == "front"]
    back = [d for d in docs if d["kind"] == "back"]
    words = sum(d["words"] for d in docs)
    bwords = sum(d["words"] for d in body)
    chap_heads = [hh for d in body for hh in d["heads"] if CHAPTER_HEAD_RE.match(hh)]
    title = (meta.get("title") or [""])[0]
    author = next((v[0] for k, v in meta.items() if k.startswith("creator")), "")
    look.fact("chapters", len(body))
    closing = [d for d in docs if d["kind"] in ("body", "back") and (TAIL_RE.match(d["label"]) or d["etype"].split(":")[-1].lower() in ("conclusion", "epilogue", "afterword"))]
    if closing:   # whether a conclusion, epilogue or summary is a chapter is a choice: print the count both ways
        base = len([d for d in body if d not in closing])
        look.fact("chapters_without_closing_sections", base)
        look.fact("chapters_with_closing_sections", base + len(closing))
        look.line(f"Chapter count both ways: {base} without the closing sections ({', '.join(d['label'] for d in closing[:4])}), {base + len(closing)} when they count as chapters.", 96, "structure")
    look.fact("spine_documents", len(docs))
    look.fact("words", words)
    look.fact("metadata", {k: v for k, v in meta.items()})
    look.headline = f"EPUB \"{title[:60]}\" by {author[:40] or 'unknown'}, {len(body)} chapters (front and back matter left out), {words:,} words"
    look.dims = f"{len(body)} chapters"
    look.line("Book metadata (package document): " + "; ".join(f"{k} {', '.join(v[:4])}" for k, v in meta.items() if k not in ("description",))
              + (f"; description {P.short(meta['description'][0], 160)}" if meta.get("description") else ""), 98, "props")
    P.counts(look, [("chapters (body documents, front and back matter left out)", len(body)), ("spine documents", len(docs)), ("front matter documents", len(front)),
                    ("back matter documents", len(back)), ("chapter headings in the body text", len(chap_heads) or None), ("table of contents entries", toc_entries or None),
                    ("print pages listed (page-list)", page_list or None), ("words in all", words), ("words in the chapters", bwords),
                    ("images", sum(d["images"] for d in docs) or None)], 97)
    if body:
        lg = max(body, key=lambda d: d["words"])
        sh = min(body, key=lambda d: d["words"])
        look.line(f"Chapters: {len(body)}, from {body[0]['label']!r} to {body[-1]['label']!r}; longest chapter {body.index(lg) + 1} {lg['label']!r} ({lg['words']:,} words), "
                  f"shortest chapter {body.index(sh) + 1} {sh['label']!r} ({sh['words']:,} words), mean {bwords / len(body):,.0f} words. "
                  f"Front matter: {', '.join(d['label'] for d in front) or 'none'}. Back matter: {', '.join(d['label'] for d in back) or 'none'}.", 96, "structure")
    rows = []
    k = 0
    for i, d in enumerate(docs, 1):
        if d["kind"] == "body":
            k += 1
        rows.append(f"  {i}. [{d['kind']}{' ' + str(k) if d['kind'] == 'body' else ''}] {d['label']} ({d['words']:,} words)")
    look.line("Spine in reading order (document, class, chapter number, words):\n" + "\n".join(rows[:60]) + (f"\n  ... {len(rows) - 60} more" if len(rows) > 60 else ""), 93, "outline")
    if toc_titles and [t for t in toc_titles] != [d["label"] for d in docs]:
        look.line(f"Table of contents ({toc_entries} entries): " + "; ".join(P.short(t, 50) for t in toc_titles[:80]), 60, "outline")
    if "META-INF/encryption.xml" in names:
        enc = z.read("META-INF/encryption.xml").decode("utf-8", "replace")
        if re.search(r"EncryptionMethod[^>]*Algorithm=\"(?!http://www.idpf.org/2008/embedding|http://ns.adobe.com/pdf/enc)", enc):
            look.flag("DRM", "META-INF/encryption.xml", "content is encrypted", "the text cannot be read without the license")
    if 'rendition:layout">pre-paginated' in opf:
        look.flag("FIXED-LAYOUT", "package", "pre-paginated book", "pages are pictures or fixed boxes; text order may differ from reading order")
    look.write_text("chapters.md", "\n\n".join(f"## {i + 1}. [{d['kind']}] {d['label']} ({d['words']} words)\n{' '.join(re.split(r'(?<=[.!?]) ', d['text'])[:3])[:500]}" for i, d in enumerate(docs)),
                    "each spine document with its class and first sentences", value=6)
    look.write_text("text.md", "\n\n".join(f"<!-- chapter {i + 1}: {d['label']} -->\n{d['text']}" for i, d in enumerate(docs)), "the whole text, one block per spine document",
                    value=1, slice_cmd="--page A-B (chapters) or --grep REGEX")
    look.step("book structure", "stdlib")


# ================================================================= OpenDocument
NS = {"office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0", "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
      "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0", "dc": "http://purl.org/dc/elements/1.1/", "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
      "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"}


def q(prefix, name):
    return "{%s}%s" % (NS[prefix], name)


def _xml(z, name):
    import xml.etree.ElementTree as ET
    try:
        return ET.fromstring(z.read(name))
    except Exception:
        return None


def odf_meta(look, z, names):
    root = _xml(z, "meta.xml") if "meta.xml" in names else None
    if root is None:
        return {}
    meta, stats = {}, {}
    for el in root.iter():
        t = el.tag.rsplit("}", 1)[-1]
        if t == "document-statistic":
            stats = {k.rsplit("}", 1)[-1]: v for k, v in el.attrib.items()}
        elif t == "user-defined":
            meta[f"custom {el.get(q('meta', 'name'))}"] = (el.text or "").strip()
        elif len(el) == 0 and (el.text or "").strip() and t not in ("meta", "document-meta"):
            meta[{"creator": "last modified by", "date": "modified", "initial-creator": "author (initial creator)"}.get(t, t)] = el.text.strip()
    if meta:
        look.line("Document properties (meta.xml): " + "; ".join(f"{k} {P.short(v, 80)}" for k, v in meta.items()), 95, "props")
    if stats:
        look.line("Statistics stored by the app at its last save (not recounted): " + "; ".join(f"{k} {v}" for k, v in stats.items()), 60, "props")
    look.fact("properties", meta)
    return meta


def text_of(el):
    """Visible text of an element: annotations, deleted text and note bodies left out."""
    out = []

    def walk(e):
        t = e.tag.rsplit("}", 1)[-1]
        if t in ("annotation", "tracked-changes", "note-body"):
            return
        if e.text:
            out.append(e.text)
        for c in e:
            ct = c.tag.rsplit("}", 1)[-1]
            if ct == "s":
                out.append(" " * int(c.get(q("text", "c")) or 1))
            elif ct == "tab":
                out.append("\t")
            elif ct == "line-break":
                out.append("\n")
            else:
                walk(c)
            if c.tail:
                out.append(c.tail)
    walk(el)
    return "".join(out)


def odf_tables(body):
    """Every table of an OpenDocument text body: rows and columns (repeat counts expanded), first and last row text, cells and the paragraphs in them."""
    tt, rr, cc = q("table", "table"), q("table", "table-row"), q("table", "table-cell")
    rep_r, rep_c = q("table", "number-rows-repeated"), q("table", "number-columns-repeated")
    out, rows_all, cells_all, paras = [], 0, 0, 0
    for tb in body.iter(tt):
        rows = []
        for r in tb.iter(rr):
            cells = [x for x in r if x.tag == cc or x.tag == q("table", "covered-table-cell")]
            texts = []
            for c in cells:
                n = min(int(c.get(rep_c) or 1), 200)
                texts += [" ".join(text_of(p) for p in c.iter(q("text", "p"))).strip()] * n
            rows.append((int(r.get(rep_r) or 1), texts))
        nr = sum(min(n, 100000) for n, _ in rows)
        nc = max((len(t) for _, t in rows), default=0)
        rows_all += nr
        cells_all += sum(n * len(t) for n, t in rows)
        paras += sum(1 for _ in tb.iter(q("text", "p")))
        out.append({"name": tb.get(q("table", "name")) or "?", "rows": nr, "cols": nc, "first": rows[0][1] if rows else [], "last": rows[-1][1] if rows else []})
    return {"tables": out, "rows": rows_all, "cells": cells_all, "paras": paras}


def look_odt(look, z, names):
    root = _xml(z, "content.xml") if "content.xml" in names else None
    meta = odf_meta(look, z, names)
    if root is None:
        look.flag("CORRUPT", "content.xml", "missing or not XML", "")
        return
    body = root.find(f".//{q('office', 'text')}")
    if body is None:
        body = root
    heads, paras, lines = [], 0, []
    lists = tables = images = notes = 0
    words_under = []
    comments, changes = [], []
    for el in body.iter():
        t = el.tag.rsplit("}", 1)[-1]
        if t == "annotation":
            who = next((x.text for x in el if x.tag == q("dc", "creator")), None)
            when = next((x.text for x in el if x.tag == q("dc", "date")), None)
            comments.append({"author": who, "date": when, "text": " ".join(text_of(p) for p in el if p.tag == q("text", "p")).strip()})
        elif t == "changed-region":
            for kind in el:
                k = kind.tag.rsplit("}", 1)[-1]
                info = kind.find(q("office", "change-info"))
                who = info.find(q("dc", "creator")).text if info is not None and info.find(q("dc", "creator")) is not None else None
                when = info.find(q("dc", "date")).text if info is not None and info.find(q("dc", "date")) is not None else None
                gone = " ".join(text_of(p) for p in kind if p.tag == q("text", "p")).strip()
                changes.append({"kind": k, "author": who, "date": when, "text": gone})
        elif t == "list":
            lists += 1
        elif t == "table" and el.tag == q("table", "table"):
            tables += 1
        elif t in ("image",) and el.tag == q("draw", "image"):
            images += 1
        elif t == "note":
            notes += 1
    in_table = set()   # paragraphs inside tables, comments, deleted text and note bodies are not body paragraphs
    for tag in (q("table", "table"), q("office", "annotation"), q("text", "tracked-changes"), q("text", "note-body")):
        for tb in body.iter(tag):
            for x in tb.iter():
                in_table.add(id(x))
    for el in body.iter():
        if el.tag == q("text", "h"):
            lvl = int(el.get(q("text", "outline-level")) or 1)
            txt = text_of(el).strip()
            heads.append((lvl, txt))
            words_under.append(0)
            lines.append("#" * min(6, lvl) + " " + txt)
        elif el.tag == q("text", "p") and id(el) not in in_table:
            txt = text_of(el).strip()
            if txt:
                paras += 1
                lines.append(txt)
                if words_under:
                    words_under[-1] += len(txt.split())
    lvls = Counter(l for l, _ in heads)
    h1 = [t for l, t in heads if l == 1]
    body_h1 = [t for t in h1 if not FRONT_RE.match(t) and not BACK_RE.match(t)]
    words = sum(len(x.split()) for x in lines if not x.startswith("#"))
    tinfo = odf_tables(body)
    items = sum(1 for _ in body.iter(q("text", "list-item")))
    look.headline = f"OpenDocument text: {len(heads)} headings ({len(h1)} top level), {paras} paragraphs, {words:,} words"
    P.counts(look, [("headings", len(heads))] + [(f"heading {k}", lvls[k]) for k in sorted(lvls)] + [("top-level sections without front/back matter", len(body_h1) if len(body_h1) != len(h1) else None),
                    ("paragraphs (non-empty, outside tables)", paras), ("words", words), ("tables", tables), ("lists", lists or None), ("comments", len(comments)),
                    ("tracked changes", len(changes)), ("insertions", sum(1 for c in changes if c["kind"] == "insertion") or None),
                    ("deletions", sum(1 for c in changes if c["kind"] == "deletion") or None), ("format changes", sum(1 for c in changes if c["kind"] == "format-change") or None),
                    ("notes", notes or None), ("images", images or None), ("table rows", tinfo["rows"] or None), ("table cells", tinfo["cells"] or None),
                    ("paragraphs inside tables", tinfo["paras"] or None), ("list items", items or None), ("last paragraph", f"'{P.short(lines[-1], 80)}'" if lines else None)], 97, "Document counts")
    for k, t in enumerate(tinfo["tables"][:30], 1):
        look.line(f"Table {k} '{t['name']}': {t['rows']} rows x {t['cols']} columns; first row: " + " | ".join(P.short(x, 30) for x in t["first"])
                  + f"; last row: " + " | ".join(P.short(x, 30) for x in t["last"]), 90 - min(k, 20) // 2, "tables")
    if heads:
        look.line("Outline (level, heading, words under it):\n" + "\n".join(f"  {'  ' * (l - 1)}{l}. {P.short(t, 70)} ({w} words)" for (l, t), w in zip(heads[:80], words_under[:80]))
                  + (f"\n  ... {len(heads) - 80} more" if len(heads) > 80 else ""), 94, "outline")
    if comments:
        look.line(f"Comments ({len(comments)}; by {', '.join(f'{a} {n}' for a, n in Counter(c['author'] for c in comments).most_common())}): "
                  + " | ".join(f"{c['author']} {(c['date'] or '')[:16]}: {P.short(c['text'], 80)}" for c in comments[:12]), 94, "comments")
    if changes:
        look.line(f"Tracked changes ({len(changes)}; by {', '.join(f'{a} {n}' for a, n in Counter(c['author'] for c in changes).most_common())}): "
                  + " | ".join(f"{c['kind']} by {c['author']} {(c['date'] or '')[:16]}" + (f": {P.short(c['text'], 60)}" if c["text"] else "") for c in changes[:12]), 94, "changes")
        gone = [c["text"] for c in changes if c["kind"] == "deletion" and c["text"]]
        look.flag("TRACKED-CHANGES", "content.xml", f"{len(changes)} tracked changes" + (f"; deleted but still in the file: {' | '.join(P.short(g, 60) for g in gone[:3])}" if gone else ""), "accept or reject them before quoting the text as final")
    look.fact("headings", [t for _, t in heads][:60])
    look.fact("comments", comments[:100])
    look.fact("paragraphs", paras)
    look.write_text("text.md", "\n\n".join(lines), "document text with # headings (comments and deleted text left out; see the facts)")


def odf_cells(table):
    """-> ({(row, col): text value}, [(A1 ref, formula)], hidden) for one table:table, repeated rows/columns expanded where they hold content."""
    from dl_xl import cell_name
    cells, formulas = {}, []
    r = 0
    for row in table.iter(q("table", "table-row")):
        rrep = int(row.get(q("table", "number-rows-repeated")) or 1)
        rowcells = []
        c = 0
        for cell in row:
            if cell.tag not in (q("table", "table-cell"), q("table", "covered-table-cell")):
                continue
            crep = int(cell.get(q("table", "number-columns-repeated")) or 1)
            vt = cell.get(q("office", "value-type"))
            val = cell.get(q("office", "value")) or cell.get(q("office", "date-value")) or cell.get(q("office", "time-value")) or cell.get(q("office", "boolean-value"))
            if val is None:
                txt = "\n".join(text_of(p) for p in cell if p.tag == q("text", "p"))
                val = txt if txt.strip() else None
            f = cell.get(q("table", "formula"))
            if val is not None or f:
                for k in range(min(crep, 1024)):
                    rowcells.append((c + k, val if val is not None else "", f, vt))
            c += crep
        if rowcells:
            for k in range(min(rrep, 10000)):
                for cc, val, f, vt in rowcells:
                    cells[(r + k, cc)] = val
                    if f:
                        formulas.append((cell_name(r + k, cc), re.sub(r"^of:=?", "=", f).replace("[.", "").replace("]", "")))
        r += rrep
    return cells, formulas


def look_ods(look, z, names):
    import dl_offx
    root = _xml(z, "content.xml") if "content.xml" in names else None
    odf_meta(look, z, names)
    if root is None:
        look.flag("CORRUPT", "content.xml", "missing or not XML", "")
        return
    tables = list(root.iter(q("table", "table")))
    per = []
    tot = Counter()
    for tb in tables:
        name = tb.get(q("table", "name")) or f"Sheet{len(per) + 1}"
        cells, formulas = odf_cells(tb)
        d = dl_offx.sheet_aggregates(look, name, cells, formulas)
        per.append((name, d))
        for k in ("cells", "numbers", "text", "formulas"):
            tot[k] += d.get(k, 0)
    look.headline = f"OpenDocument spreadsheet, {len(tables)} sheets"
    look.dims = f"{len(tables)} sheets"
    look.fact("sheets", [n for n, _ in per])
    P.counts(look, [("sheets", len(tables)), ("non-empty cells", tot["cells"]), ("number cells", tot["numbers"]), ("text cells", tot["text"]), ("formulas", tot["formulas"])], 97, "Workbook counts")
    look.line("Sheets in order (used rows x columns, formulas, sum of numbers): " + "; ".join(f"{i}. {n} {d['rows']}x{d['cols']}, {d['formulas']} formulas" + (f", sum {P.fmt(d['sum'])}" if "sum" in d else "")
                                                                                       for i, (n, d) in enumerate(per, 1)), 96, "sheets")
