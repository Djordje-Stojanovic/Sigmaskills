"""SigmaDeepLook: PDF, Office documents, notebooks, mail and calendars, web pages.

Nothing is opened in an application that can run macros: Office files are read as XML, and LibreOffice (when present) runs headless
with a throwaway profile whose macro security is set to the maximum. Notebooks are never executed. Mail attachments are listed, not opened.
"""
import csv
import hashlib
import html.parser
import io
import json
import math
import os
import random
import re
import sys
import shutil
import struct
import tempfile
import time
import zipfile
import zlib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import dl_core as core
import dl_prof as P
import dl_xl

MAX_XML = 40 << 20
PAGE_CAP = 30
PDF_MAX_PAGES = 3000


def strip(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_xml(look, data):
    """Parse XML bytes safely: entity declarations are refused, defusedxml is used when present."""
    if b"<!ENTITY" in data:
        look.flag("ENTITY-DECLARATION", "xml", "DTD entity declared", "not parsed: entity expansion can exhaust memory")
        return None
    if len(data) > MAX_XML:
        look.flag("TRUNCATED", "xml", f"{len(data)} bytes", "part larger than 40 MB was skipped")
        return None
    dx = look.mod("defusedxml")
    try:
        if dx:
            from defusedxml import ElementTree as DET
            return DET.fromstring(data)
        return ET.fromstring(data)
    except Exception as e:
        look.flag("XML-ERROR", "xml", f"{type(e).__name__}: {str(e)[:80]}", "")
        return None


def attr(el, name):
    for k, v in el.attrib.items():
        if strip(k) == name:
            return v
    return None


def rattr(el, name="id"):
    """The relationship id (r:id), not the plain id attribute that sits beside it."""
    for k, v in el.attrib.items():
        if k.startswith("{") and "relationships" in k.split("}")[0] and strip(k) == name:
            return v
    return None


# ================================================================= PDF
BADFONT = re.compile(r"\(cid:\d+\)|GLYPH<|�")
PDF_KEYS = [(b"/JavaScript", "JAVASCRIPT"), (b"/JS", "JAVASCRIPT"), (b"/OpenAction", "OPEN-ACTION"), (b"/Launch", "LAUNCH"),
            (b"/EmbeddedFile", "EMBEDDED-FILE"), (b"/XFA", "XFA"), (b"/AA", "AUTO-ACTION"), (b"/RichMedia", "RICH-MEDIA")]
PDF_HINTS = {"JAVASCRIPT": "the PDF carries script; it was not run", "OPEN-ACTION": "an action runs when the file is opened",
             "LAUNCH": "can start another program", "EMBEDDED-FILE": "a file is hidden inside the PDF",
             "XFA": "XFA form: page text may be a placeholder", "AUTO-ACTION": "additional actions on events", "RICH-MEDIA": "embedded media or Flash"}


PDF_OBJ_RE = re.compile(rb"(?<!\d)(\d+)\s+0\s+obj\b(.*?)\bendobj\b", re.S)
PDF_REF_RE = re.compile(rb"(\d+)\s+0\s+R")


def pdf_show_text(s):
    """Rough text of one content stream: the Tj and TJ strings in order (no font maps, so no CID or ToUnicode text)."""
    if b"BT" not in s or not (b"Tj" in s or b"TJ" in s):
        return ""
    t = []
    for a, arr in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj|\[(.*?)\]\s*TJ", s, re.S):
        if a:
            t.append(a.decode("latin-1"))
        else:
            t.append("".join(x.decode("latin-1") for x in re.findall(rb"\(((?:\\.|[^\\)])*)\)", arr)))
    return " ".join(t)


def pdf_objects(b):
    """object number -> (dictionary bytes, decoded stream bytes or None). Flate only; object streams are not expanded."""
    import zlib
    objs = {}
    for m in PDF_OBJ_RE.finditer(b):
        body = m.group(2)
        k = re.search(rb"\bstream\r?\n", body)
        if not k:
            objs[int(m.group(1))] = (body, None)
            continue
        head = body[:k.start()]
        end = body.rfind(b"endstream")
        raw = body[k.end():end if end > 0 else len(body)]
        raw = raw[:-2] if raw.endswith(b"\r\n") else raw[:-1] if raw.endswith(b"\n") else raw  # one line break only: it may be data
        if b"FlateDecode" in head:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = None
        objs[int(m.group(1))] = (head, raw)
    return objs


def pdf_page_texts(objs):
    """Text of each page in page-tree order, from the page's own /Contents. None when the tree cannot be walked."""
    root = next((n for n, (d, _) in objs.items() if re.search(rb"/Type\s*/Catalog\b", d)), None)
    m = re.search(rb"/Pages\s+(\d+)\s+0\s+R", objs[root][0]) if root is not None else None
    if not m:
        return None
    order = []

    def walk(num, depth):
        if depth > 40 or num not in objs:
            return False
        d = objs[num][0]
        if b"/Kids" in d:
            km = re.search(rb"/Kids\s*\[(.*?)\]", d, re.S)
            return bool(km) and all(walk(int(r.group(1)), depth + 1) for r in PDF_REF_RE.finditer(km.group(1)))
        if re.search(rb"/Type\s*/Page\b", d):
            order.append(num)
            return True
        return False

    if not walk(int(m.group(1)), 0):
        return None
    texts = []
    for num in order:
        cm = re.search(rb"/Contents\s*(\[.*?\]|\d+\s+0\s+R)", objs[num][0], re.S)
        parts = [pdf_show_text(objs[int(r.group(1))][1] or b"") for r in PDF_REF_RE.finditer(cm.group(1))] if cm else []
        texts.append(" ".join(x for x in parts if x))
    return texts


def pdf_raw(path):
    """Stdlib view of a PDF: page count, risky keys, form field names, and rough text per page (None when the page tree is unreadable)."""
    with open(path, "rb") as fh:
        b = fh.read(80 << 20)
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", b))
    objs = pdf_objects(b)
    flags = {}
    streams = [raw for _, raw in objs.values() if raw]
    blob = b + b"\n".join(s for s in streams if b"/Type" in s[:200])
    for key, kind in PDF_KEYS:
        if re.search(re.escape(key) + rb"(?![A-Za-z])", blob):
            flags[kind] = True
    fields = [m.group(1).decode("latin-1") for m in re.finditer(rb"/T\s*\(([^)]*)\)", blob)]
    try:
        page_texts = pdf_page_texts(objs)
    except Exception:
        page_texts = None
    return {"pages": pages, "flags": sorted(flags), "fields": fields, "page_texts": page_texts, "encrypted": b"/Encrypt" in b}


def look_pdf(look):
    raw = pdf_raw(look.path)
    fitz = look.mod("fitz")
    pages, flags, fields, encrypted = raw["pages"], set(raw["flags"]), list(dict.fromkeys(raw["fields"])), raw["encrypted"]
    per_page, text_pages = [], []
    doc = None
    if fitz:
        try:
            doc = fitz.open(str(look.path))
            if doc.needs_pass:
                encrypted = True
                look.flag("ENCRYPTED", "file", "password required", "pages cannot be read without the password")
                doc = None
        except Exception as e:
            look.flag("PDF-ERROR", "open", f"{type(e).__name__}: {e}"[:100], "")
            doc = None
    if doc is not None:
        pages = doc.page_count
        flags = set()
        for x in range(1, doc.xref_length()):
            try:
                obj = doc.xref_object(x, compressed=False) or ""
            except Exception:
                continue
            for key, kind in PDF_KEYS:
                if re.search(re.escape(key.decode()) + r"(?![A-Za-z0-9+])", obj):   # /AA must not match a subset font name /AAAAAA+Font
                    flags.add(kind)
        try:
            fields = [w.field_name for p in doc for w in (p.widgets() or [])]
        except Exception:
            pass
        for i, p in enumerate(doc):
            if i >= PDF_MAX_PAGES:
                break
            t = p.get_text()
            text_pages.append(t)
            per_page.append({"page": i + 1, "chars": len(t.strip()), "images": len(p.get_images()), "garbled": bool(BADFONT.search(t))})
    else:
        if not fitz:
            look.skip("per-page text layer, page pictures, exact fields", "PyMuPDF (fitz) not importable" if not look.no_tools else "disabled by --no-tools", "fitz")
        if raw["page_texts"] is not None:
            text_pages = raw["page_texts"]
        else:
            look.skip("text per page (the stdlib reader could not walk the page tree, so no page numbers are given)", "page tree not readable without PyMuPDF", "fitz")
    look.fact("pages", pages)
    look.fact("encrypted", bool(encrypted))
    look.fact("fields", fields)
    look.fact("risky_keys", sorted(flags))
    look.headline = f"PDF, {pages} pages" + (", encrypted" if encrypted else "")
    look.dims = f"{pages} pages"
    look.line(f"PDF: {pages} pages" + (", encrypted" if encrypted else "") + (f", form fields: {', '.join(fields)}" if fields else "") + ".")
    for kind in sorted(flags):
        look.flag(kind, "PDF objects", "present", PDF_HINTS.get(kind, ""))
    if per_page:
        verdicts = []
        for pp in per_page:
            v = "garbled-font" if pp["garbled"] else "born-digital" if pp["chars"] >= 100 else "scanned" if pp["chars"] < 20 and pp["images"] else "sparse"
            pp["layer"] = v
            verdicts.append(f"p{pp['page']} {v} ({pp['chars']} chars, {pp['images']} img)")
            if v == "garbled-font":
                look.flag("GARBLED-FONT", f"page {pp['page']}", "cid/GLYPH/replacement characters", "the text layer is unreliable; OCR the rendered page")
            if v == "scanned":
                look.flag("SCANNED", f"page {pp['page']}", "no text layer", "text needs OCR")
        look.fact("layers", {str(pp["page"]): pp["layer"] for pp in per_page})
        kinds = Counter(pp["layer"] for pp in per_page)
        chars = sorted(pp["chars"] for pp in per_page)
        look.line(f"Text layer, {len(per_page)} of {pages} pages checked: " + ", ".join(f"{n} {k}" for k, n in kinds.most_common())
                  + f"; characters per page min {chars[0]}, median {chars[len(chars) // 2]}, max {chars[-1]}; {sum(1 for pp in per_page if pp['images'])} pages hold pictures.")
        runs = layer_runs(per_page)
        if len(runs) > 1 or runs[0][2] != "born-digital":
            look.line("Page layers by run: " + "; ".join(f"p{a}" + (f"-{b}" if b != a else "") + f" {k}" for a, b, k in runs[:10]) + (f"; +{len(runs) - 10} more runs, see layer.json" if len(runs) > 10 else ""))
        look.write_text("layer.json", json.dumps(per_page), "per-page text-layer verdict (born-digital, scanned, garbled)", "json", value=1, inline=False)
    if doc is not None:
        pdf_extras(look, doc, pages)
        try:
            toc = doc.get_toc(simple=True)
        except Exception:
            toc = []
        if toc:
            look.fact("outline_entries", len(toc))
            top = [t for t in toc if t[0] == 1] or toc
            look.line(f"Outline: {len(toc)} bookmarks; top level: " + "; ".join(f"{t[1][:50]} (p{t[2]})" for t in top[:12]) + (f"; +{len(top) - 12} more" if len(top) > 12 else ""))
            look.write_text("outline.txt", "\n".join("  " * (t[0] - 1) + f"{t[1]}  (page {t[2]})" for t in toc), "bookmark outline with page numbers")
        elif pages >= 20:
            look.fact("outline_entries", 0)
            look.flag("NO-OUTLINE", "document", f"{pages} pages, 0 bookmarks", "no table of contents to navigate by: slice with --page A-B or search with --grep")
    body = pdf_text(look, text_pages, pages)
    if body:
        pages_txt = [(int(n), t.strip()) for n, t in re.findall(r"<!-- page (\d+) -->\n(.*?)(?=\n<!-- page \d+ -->|\Z)", body, re.S)]
        has_text = [(n, t) for n, t in pages_txt if len(t) >= 20]
        mostly_empty = pages_txt and len(has_text) <= len(pages_txt) / 2
        look.write_text("text.md", body, "text per page, `<!-- page N -->` markers", value=5, slice_cmd="--page A-B", inline=False if mostly_empty else None)
        if mostly_empty and has_text:
            look.line("Pages with a text layer: " + " | ".join(f"p{n}: {' '.join(t.split())[:150]}" for n, t in has_text[:3]), 76)
        look.fact("text_chars", len(body))
        look.excerpt("First text", re.sub(r"<!-- page \d+ -->\n", "", body), 6, 420)
        try:
            import dl_pdffacts
            dl_pdffacts.page_facts(look, pages_txt, doc, pages)
        except Exception as e:
            look.fail("page index, stated figures and tables", "stdlib", e)
    if fields:
        look.write_text("fields.json", json.dumps(fields), "form field names", "json")
    scanned = [pp["page"] for pp in per_page if pp.get("layer") == "scanned"]
    if scanned:
        ocr_pdf_pages(look, doc, scanned)
    if doc is not None:
        rendered = render_pdf_pages(look, doc, "pages")
        if rendered:
            page_sheets(look, rendered, "sheet-pages", "PDF pages")
        doc.close()
    look.ask_human("Is it a scan or born-digital, and what language?", "Do headers, footers and footnotes matter?", "May the document leave this machine (remote OCR, upload)? Default: no.")


def layer_runs(per_page):
    runs = []
    for pp in per_page:
        if runs and runs[-1][2] == pp["layer"] and runs[-1][1] == pp["page"] - 1:
            runs[-1][1] = pp["page"]
        else:
            runs.append([pp["page"], pp["page"], pp["layer"]])
    return runs


def pdf_date(s):
    m = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", s or "")
    if not m:
        return None
    return tuple(int(x or d) for x, d in zip(m.groups(), (0, 1, 1, 0, 0, 0)))


def pdf_extras(look, doc, pages):
    """Metadata and its date order, embedded files, annotations, links, signatures, invisible or white text, tables. All read-only."""
    md = doc.metadata or {}
    bits = [f"{k} {md[k][:60]!r}" for k in ("title", "author", "creator", "producer") if md.get(k)]
    c, m = pdf_date(md.get("creationDate")), pdf_date(md.get("modDate"))
    if bits:
        look.line("Metadata: " + "; ".join(bits) + (f"; created {c[0]:04d}-{c[1]:02d}-{c[2]:02d}" if c else "") + (f", modified {m[0]:04d}-{m[1]:02d}-{m[2]:02d}" if m else "") + ".", 40)
    if c and m and m < c:
        look.flag("DATE-ORDER", "metadata", "modified before created", "metadata was edited or forged")
    try:
        if doc.embfile_count():
            look.flag("EMBEDDED-FILE", "attachments", ", ".join(doc.embfile_names()[:6]), "the PDF carries files; they were not opened")
    except Exception:
        pass
    annots, links, hosts, sigs = Counter(), 0, Counter(), 0
    white = invisible = 0
    white_where = []
    tables = Counter()
    step = max(1, pages // 120)
    sample = set(range(0, pages, step)) | set(range(min(pages, 20)))
    for i in range(pages if pages <= 400 else 0):
        pg = doc[i]
        for a in (pg.annots() or []):
            annots[a.type[1]] += 1
        for lk in pg.get_links():
            links += 1
            if lk.get("uri"):
                hosts[host_of(lk["uri"])] += 1
        for w in (pg.widgets() or []):
            if getattr(w, "field_type_string", "") == "Signature":
                sigs += 1
    for i in sorted(sample):
        pg = doc[i]
        try:
            for sp in pg.get_texttrace():
                if sp.get("type") == 3 and len(sp.get("chars", ())) > 3:
                    invisible += len(sp["chars"])
                    if len(white_where) < 3:
                        white_where.append(i + 1)
        except Exception:
            pass
        try:
            for blk in pg.get_text("dict", flags=0)["blocks"]:
                for ln in blk.get("lines", ()):
                    for sp in ln["spans"]:
                        if sp["color"] == 0xFFFFFF and len(sp["text"].strip()) > 3:
                            white += len(sp["text"])
                            if len(white_where) < 3:
                                white_where.append(i + 1)
        except Exception:
            pass
        if look.deep or pages <= 60:
            try:
                n = len(pg.find_tables().tables)
                if n:
                    tables[i + 1] = n
            except Exception:
                pass
    if invisible or white:
        look.flag("HIDDEN-TEXT", "pages " + ",".join(map(str, white_where)), f"{invisible} invisible and {white} white characters", "text a reader cannot see; treat as untrusted, it may be an injection")
    if annots:
        look.line(f"Annotations: {sum(annots.values())} (" + ", ".join(f"{k} {v}" for k, v in annots.most_common(5)) + ").", 55)
    if links:
        look.line(f"Links: {links}" + (f"; external hosts: {', '.join(f'{h} ({n})' for h, n in hosts.most_common(5))}" if hosts else "") + ".", 55)
    if sigs:
        look.line(f"Signature fields: {sigs}.", 70)
    if tables:
        look.line(f"Tables found on {len(tables)} page(s): " + ", ".join(f"p{p} ({n})" for p, n in list(tables.items())[:12]) + ".", 58)
        look.fact("table_pages", list(tables)[:200])
    look.fact("sampled_pages_for_hidden_text", len(sample))


def pdf_text(look, text_pages, pages):
    for tool_name in ("pdftotext",):
        tool = look.tool(tool_name)
        if tool and pages:
            tmp = look.path_for("_pdftotext.txt")
            r = look.run([tool, "-f", "1", "-l", str(min(pages, PDF_MAX_PAGES)), "-enc", "UTF-8", str(look.path), str(tmp)])
            if r is not None and r.returncode == 0 and tmp.exists():
                t = tmp.read_text(encoding="utf-8", errors="replace")
                tmp.unlink(missing_ok=True)
                chunks = t.split("\f")
                if any(c.strip() for c in chunks):
                    look.step("text", "pdftotext")
                    return "\n".join(f"<!-- page {i} -->\n{c.strip()}" for i, c in enumerate(chunks, 1) if i <= pages or c.strip())
            tmp.unlink(missing_ok=True)
    if text_pages and any(t.strip() for t in text_pages):
        look.step("text", "PyMuPDF" if look.mod("fitz") else "stdlib stream scan")
        return "\n".join(f"<!-- page {i} -->\n{t.strip()}" for i, t in enumerate(text_pages, 1))
    pp = look.mod("pypdf")
    if pp:
        try:
            r = pp.PdfReader(str(look.path))
            return "\n".join(f"<!-- page {i} -->\n{(p.extract_text() or '').strip()}" for i, p in enumerate(r.pages[:PDF_MAX_PAGES], 1))
        except Exception as e:
            look.fail("text (pypdf)", "pypdf", e)
    return ""


def ocr_pdf_pages(look, doc, pages):
    tess = look.tool("tesseract")
    if not tess or doc is None:
        look.skip("OCR of scanned pages", "tesseract not found" if not look.no_tools else "disabled by --no-tools", "tesseract")
        return
    out = []
    cap = 1 if look.quick else 20   # the quick tier reads the first scanned page
    for n in pages[:cap]:
        png = render_one(look, doc, n - 1, f"_ocr{n}.png")
        if png:
            r, txt, _ = look.run_text([tess, str(png), "stdout", "--psm", "3"])
            if r is not None:
                out.append(f"<!-- page {n} (OCR) -->\n{txt.strip()}")
            png.unlink(missing_ok=True)
    if out:
        look.write_text("ocr.md", "\n".join(out), f"OCR text of scanned pages {pages[:cap]} (tesseract)")
        if len(pages) > cap:
            look.flag("PARTIAL", "OCR", f"{cap} of {len(pages)} scanned pages read", "run --tier standard for more pages, or --page A-B")
        look.fact("ocr_text", "\n".join(out)[:1500])
        look.step("OCR of scanned pages", "tesseract")


def render_one(look, doc, idx, name, edge=None):
    fitz = core.quiet_import("fitz")
    edge = edge or look.reader["edge"]
    p = doc[idx]
    r = p.rect
    z = min(2.6, edge / max(r.width, r.height))
    pm = p.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
    out = look.path_for(name)
    pm.save(str(out))
    return out


def render_pdf_pages(look, doc, folder):
    if not look.mod("PIL") and not look.mod("fitz"):
        return []
    out = []
    n = min(doc.page_count, 9 if look.quick else PAGE_CAP if not look.deep else 200)
    for i in range(n):
        try:
            p = render_one(look, doc, i, f"{folder}/p{i + 1:03d}.png")
            look.add(p, "internal", f"page {i + 1}")
            out.append(p)
        except Exception as e:
            look.flag("RENDER-FAILED", f"page {i + 1}", f"{type(e).__name__}: {e}"[:80], "")
            break
    if doc.page_count > n:
        look.flag("PARTIAL", "render", f"first {n} of {doc.page_count} pages", "use --deep for more pages")
    return out


def page_sheets(look, pngs, prefix, label):
    """3x3 thumbnail pages of rendered pages: layout at a glance. Full-resolution pages stay in pages/ for reading."""
    if not pngs:
        return
    if not look.mod("PIL"):
        look.skip(f"{label} thumbnail sheets", "Pillow not importable", "PIL")
        return
    from PIL import Image, ImageDraw
    cols, rows = 3, 3
    per = cols * rows
    edge = look.reader["edge"]
    for k in range(0, len(pngs), per):
        chunk = pngs[k:k + per]
        ims = [Image.open(p) for p in chunk]
        tw = max(1, min(640, edge // cols - 12))
        th = max(int(tw * im.height / im.width) for im in ims)
        W, H = cols * (tw + 8) + 8, math.ceil(len(chunk) / cols) * (th + 8) + 8
        sheet = Image.new("RGB", (W, H), (60, 60, 60))
        d = ImageDraw.Draw(sheet)
        for i, im in enumerate(ims):
            x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 8)
            sheet.paste(im.convert("RGB").resize((tw, int(tw * im.height / im.width))), (x, y))
            d.rectangle([x, y, x + 78, y + 20], fill=(0, 0, 0))
            d.text((x + 4, y + 3), f"#{k + i + 1}", fill=(255, 235, 59))
        if max(sheet.size) > edge:
            s = edge / max(sheet.size)
            sheet = sheet.resize((int(sheet.width * s), int(sheet.height * s)), Image.LANCZOS)
        p = look.path_for(f"{prefix}-{k // per + 1}.jpg")
        sheet.save(p, quality=86)
        look.add(p, "image", f"{label} {k + 1}-{k + len(chunk)} as thumbnails (full-size pages are in pages/)")
        for im in ims:
            im.close()


# ================================================================= Office
def oo_text(el):
    return "".join(t.text or "" for t in el.iter() if strip(t.tag) == "t" or strip(t.tag) == "delText")


def col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def look_office(look):
    st = look.subtype
    if st in ("doc", "xls", "ppt"):
        return office_legacy(look)
    try:
        z = core.CappedZip(look.path, look=look)
    except zipfile.BadZipFile:
        look.flag("CORRUPT", "package", "not a readable zip", "")
        return
    names = z.namelist()
    look.fact("members", len(names))
    macro = [n for n in names if n.lower().endswith("vbaproject.bin")]
    if macro or st.endswith("m") and st in ("docm", "xlsm", "pptm"):
        look.flag("MACRO", macro[0] if macro else "package", "VBA macro project present", "the macros were not opened or run")
        import dl_adapt
        dl_adapt.olevba_facts(look, z.read(macro[0]) if macro else b"", macro[0] if macro else "vbaProject.bin")
    if any("/embeddings/" in n or n.startswith("embeddings/") for n in names):
        look.flag("EMBEDDED-OBJECT", "package", "embedded objects", "listed only; not opened")
    if any(n.lower().endswith(".bin") and "activex" in n.lower() for n in names):
        look.flag("ACTIVEX", "package", "ActiveX controls", "not run")
    media = [n for n in names if "/media/" in n]
    look.fact("media", len(media))
    package_remote_flags(look, z, names)
    import dl_offx
    if st in ("docx", "docm", "xlsx", "xlsm", "pptx", "pptm"):
        try:
            dl_offx.props(look, z, names)
        except Exception as e:
            look.fail("document properties", "stdlib", e)
    kind = st[:4] if st[:4] in ("docx", "xlsx", "pptx") else st
    if st in ("docx", "docm"):
        office_docx(look, z, names)
    elif st in ("xlsx", "xlsm"):
        office_xlsx(look, z, names)
    elif st in ("pptx", "pptm"):
        office_pptx(look, z, names)
    elif st == "xlsb":
        office_xlsb(look)
    elif st in ("odt", "ods", "odp"):
        office_odf(look, z, names)
    render_office(look)


def office_xlsb(look):
    """An Excel binary workbook: its BIFF12 records are read with the standard library and written as a plain .xlsx, which the xlsx reader then looks at."""
    import dl_xlsb
    tmp = look.out / "_xlsb"
    tmp.mkdir(parents=True, exist_ok=True)
    conv = tmp / "converted.xlsx"
    try:
        info = dl_xlsb.to_xlsx(look.path, conv)
    except (KeyError, zipfile.BadZipFile, struct.error, ValueError, IndexError, OverflowError, zlib.error) as e:
        look.flag("CORRUPT", "xlsb", f"{type(e).__name__}: {e}"[:120], "the binary workbook could not be read")
        shutil.rmtree(tmp, ignore_errors=True)
        return
    keep = (look.subtype, look.path)
    look.subtype, look.path = "xlsx", conv
    try:
        office_xlsx(look, zipfile.ZipFile(conv), zipfile.ZipFile(conv).namelist())
    finally:
        look.subtype, look.path = keep
    n_f = sum(f for _n, _s, _c, f in info["sheets"])
    look.headline = look.headline.replace("xlsx workbook", "xlsb workbook", 1)
    look.line(f"Excel binary workbook (.xlsb): {len(info['sheets'])} sheets, {sum(c for _n, _s, c, _f in info['sheets']):,} non-empty cells, {info['strings']:,} shared strings, read from the BIFF12 records "
              f"with the standard library; {n_f:,} formula cells keep their stored results (formula text is not decoded).", 60)
    look.step("xlsb records to xlsx", "stdlib")
    shutil.rmtree(tmp, ignore_errors=True)
    render_office(look)


def run_hidden(r):
    """True when a Word run carries <w:vanish/> (hidden text), unless it is switched off with w:val=0/false."""
    for rp in r:
        if strip(rp.tag) == "rPr":
            for x in rp:
                if strip(x.tag) == "vanish" and (attr(x, "val") or "1").lower() not in ("0", "false", "off"):
                    return True
    return False


REL_TAG = re.compile(r"<Relationship\b[^>]*>", re.S)
REMOTE_KINDS = ("oleObject", "frame", "subDocument", "externalLinkPath", "package")


def external_targets(z, names):
    """[(part, relationship type tail, target)] for every relationship with TargetMode=External except plain hyperlinks and web images."""
    out = []
    for n in names:
        if not n.endswith(".rels"):
            continue
        try:
            data = z.read(n).decode("utf-8", "replace")
        except (KeyError, zipfile.BadZipFile, RuntimeError):
            continue
        for m in REL_TAG.finditer(data):
            tag = m.group(0)
            if not re.search(r'TargetMode\s*=\s*"External"', tag):
                continue
            ty = re.search(r'\bType\s*=\s*"([^"]*)"', tag)
            tg = re.search(r'\bTarget\s*=\s*"([^"]*)"', tag)
            tail = ty.group(1).rsplit("/", 1)[-1] if ty else ""
            if tail in ("hyperlink", "image"):
                continue
            out.append((n, tail, tg.group(1) if tg else ""))
    return out


def package_remote_flags(look, z, names):
    """Template injection and other remote parts: an attachedTemplate outside the file is fetched when Word opens it (not fetched here)."""
    for part, tail, target in external_targets(z, names)[:20]:
        if tail == "attachedTemplate":
            look.flag("REMOTE-TEMPLATE", part.rsplit("/", 1)[-1][:-5], f"attachedTemplate -> {target[:100]}", "Word loads this template when the file opens (template injection); not fetched")
        elif tail in REMOTE_KINDS:
            look.flag("EXTERNAL-LINK", tail, target[:100], "the file pulls a part from outside; not followed")


def office_docx(look, z, names):
    doc = parse_xml(look, z.read("word/document.xml")) if "word/document.xml" in names else None
    revs = Counter()
    revisions = []
    out = []
    hidden = []
    titles = []   # (style name, text) of paragraphs styled Title or Subtitle
    snames = {}   # style id -> style name (a template can call the Title style by another id)
    if "word/styles.xml" in names:
        sx = parse_xml(look, z.read("word/styles.xml"))
        for el in (sx.iter() if sx is not None else ()):
            if strip(el.tag) == "style" and attr(el, "styleId"):
                for c in el:
                    if strip(c.tag) == "name":
                        snames[attr(el, "styleId")] = attr(c, "val") or ""
    if doc is not None:
        for el in doc.iter():
            t = strip(el.tag)
            if t in ("ins", "del", "moveFrom", "moveTo", "pPrChange", "rPrChange"):
                a = attr(el, "author") or "unknown"
                revs[(t, a)] += 1
                if t in ("ins", "del", "moveFrom", "moveTo") and len(revisions) < 500:
                    revisions.append({"kind": t, "author": a, "date": attr(el, "date"), "text": oo_text(el)[:200]})

        def walk(el, mode):
            for ch in el:
                t = strip(ch.tag)
                if t == "p":
                    para = []

                    def runs(e, m):
                        for c in e:
                            tt = strip(c.tag)
                            if tt == "ins":
                                runs(c, "ins")
                            elif tt in ("del",):
                                runs(c, "del")
                            elif tt == "t":
                                para.append(f"[+{c.text}+]" if m == "ins" and c.text else (c.text or ""))
                            elif tt == "delText":
                                para.append(f"[-{c.text}-]" if c.text else "")
                            elif tt == "r" and run_hidden(c):
                                hid = oo_text(c)
                                if hid.strip():
                                    hidden.append(hid)
                                    para.append(f"[~{hid}~]")
                            elif tt == "tab":
                                para.append("\t")
                            elif tt == "br":
                                para.append("\n")
                            else:
                                runs(c, m)
                    runs(ch, mode)
                    style = ""
                    for pp in ch:
                        if strip(pp.tag) == "pPr":
                            for s in pp:
                                if strip(s.tag) == "pStyle":
                                    style = attr(s, "val") or ""
                    txt = "".join(para).strip()
                    if txt:
                        sname = snames.get(style, style)
                        if sname.replace(" ", "").lower() in ("title", "subtitle") or style.lower() in ("title", "subtitle"):
                            titles.append((sname or style, txt))
                        m = re.match(r"(?i)heading\s*(\d)", style) or re.match(r"(?i)heading\s*(\d)", sname)
                        out.append(("#" * int(m.group(1)) + " " if m else "") + txt)
                elif t in ("tbl", "tr", "tc", "body", "sdt", "sdtContent"):
                    walk(ch, mode)
        walk(doc, None)
    try:
        import dl_offx
        dl_offx.docx_counts(look, z, names, doc)
    except Exception as e:
        look.fail("Word counts", "stdlib", e)
    comments = []
    if "word/comments.xml" in names:
        c = parse_xml(look, z.read("word/comments.xml"))
        if c is not None:
            for el in c:
                if strip(el.tag) == "comment":
                    comments.append({"author": attr(el, "author"), "date": attr(el, "date"), "text": oo_text(el)})
    notes = {}
    for nm in ("footnotes", "endnotes"):
        p = f"word/{nm}.xml"
        if p in names:
            x = parse_xml(look, z.read(p))
            if x is not None:
                notes[nm] = [oo_text(e).strip() for e in x if strip(e.tag) in ("footnote", "endnote") and oo_text(e).strip()]
    hf = {}
    for n in names:
        if re.match(r"word/(header|footer)\d*\.xml", n):
            x = parse_xml(look, z.read(n))
            if x is not None and oo_text(x).strip():
                hf[n] = oo_text(x).strip()
    by_author = Counter()
    for (t, a), n in revs.items():
        by_author[a] += n
    look.fact("revisions", sum(revs.values()))
    look.fact("revision_authors", dict(by_author))
    look.fact("comments", comments)
    look.fact("footnotes", notes.get("footnotes", []))
    look.fact("headings", [l for l in out if l.startswith("#")][:30])
    look.fact("paragraphs", len(out))
    ins_n = sum(n for (t, _a), n in revs.items() if t in ("ins", "moveTo"))
    del_n = sum(n for (t, _a), n in revs.items() if t in ("del", "moveFrom"))
    bits = [f"{len(out)} non-empty paragraphs with table cells (every count in Word counts)"]
    if revs:
        bits.append(f"{sum(revs.values())} tracked changes ({ins_n} inserted, {del_n} deleted) by " + ", ".join(f"{a} {n}" for a, n in by_author.items()))
    for label, n in (("comments", len(comments)), ("footnotes", len(notes.get("footnotes", []))), ("header/footer parts", len(hf)), ("images", len([n for n in names if "/media/" in n]))):
        if n:
            bits.append(f"{n} {label}")
    look.line("Word: " + "; ".join(bits) + ".", 90)
    if titles:
        look.fact("title_paragraphs", [{"style": a, "text": t} for a, t in titles[:10]])
        look.line("Document title paragraphs: " + "; ".join(f"{a}: {P.short(t, 160)}" for a, t in titles[:6]) + ".", 96, "title")
    look.headline = (f"Word document: {sum(1 for l in out if re.match(r'#{1,6} ', l))} headings, {len(out)} non-empty paragraphs"
                     + (f", {sum(revs.values())} tracked changes" if revs else "") + (f", {len(comments)} comments" if comments else ""))
    heads = [(len(l) - len(l.lstrip("#")), l.lstrip("#").strip()) for l in out if re.match(r"#{1,6} ", l)]
    if heads:   # the outline with the words under each heading: section counts and sizes are the most-asked structure facts
        under, cur = [], None
        for l in out:
            if re.match(r"#{1,6} ", l):
                under.append(0)
            elif under:
                under[-1] += len(re.sub(r"\[-.*?-\]", "", l).split())
        import dl_books
        top = min(l for l, _ in heads)
        tops = [t for l, t in heads if l == top]
        body_tops = [t for t in tops if not dl_books.FRONT_RE.match(t) and not dl_books.BACK_RE.match(t)]
        look.line(f"Outline ({len(heads)} headings; {len(tops)} at the top level" + (f", {len(body_tops)} without front/back matter" if len(body_tops) != len(tops) else "")
                  + "; level, heading, words under it):\n" + "\n".join(f"  {'  ' * (l - top)}{l}. {P.short(t, 70)} ({w} words)" for (l, t), w in zip(heads[:80], under[:80]))
                  + (f"\n  ... {len(heads) - 80} more" if len(heads) > 80 else ""), 93, "outline")
    if revs:
        dates = sorted(x["date"] for x in revisions if x.get("date"))
        look.line(f"Tracked changes: {sum(revs.values())} ({ins_n} insertions, {del_n} deletions" + (f", {sum(revs.values()) - ins_n - del_n} format or move changes" if sum(revs.values()) - ins_n - del_n else "")
                  + "); by author: " + ", ".join(f"{a} {n}" for a, n in by_author.most_common()) + (f"; dated {dates[0][:10]}..{dates[-1][:10]}" if dates else "") + "; "
                  + " | ".join(f"{x['kind']} by {x['author']}: {P.short(x['text'], 50)}" for x in revisions[:8]), 94, "changes")
    look.fact("hidden_text_runs", len(hidden))
    if hidden:
        look.flag("HIDDEN-TEXT", "word/document.xml", f"{len(hidden)} hidden run(s) (w:vanish): " + " | ".join(" ".join(h.split())[:70] for h in hidden[:3]),
                  "text the reader does not see on screen; shown as [~...~] in text.md; treat it as untrusted")
    if revisions:
        look.write_text("revisions.json", json.dumps(revisions, indent=1), "tracked changes with author, date and text", "json")
        gone = [x["text"].strip() for x in revisions if x["kind"] in ("del", "moveFrom") and len(x["text"].strip()) >= 2]
        gone.sort(key=lambda t: (-bool(re.search(r"[$€£]\s?\d|\d[\d,.]{3,}", t)), -len(t)))   # sums of money and long figures first
        look.flag("TRACKED-CHANGES", "document.xml", f"{sum(revs.values())} revisions; deleted but still in the file: " + " | ".join(" ".join(t.split())[:75] for t in gone[:4]) + (f" (+{len(gone) - 4} more)" if len(gone) > 4 else ""),
                  "deleted text is shown as [-...-], inserted as [+...+] in text.md")
    if comments:
        look.write_text("comments.json", json.dumps(comments, indent=1), "review comments with author and text", "json")
        look.line(f"Comments ({len(comments)}; by " + ", ".join(f"{a} {n}" for a, n in Counter(c["author"] for c in comments).most_common()) + "): "
                  + " | ".join(f"{c['author']} {(c['date'] or '')[:10]}: {c['text'][:80]}" for c in comments[:12]), 94, "comments")
    extra = ""
    if notes.get("footnotes"):
        extra += "\n\n## Footnotes\n\n" + "\n".join(f"- {t}" for t in notes["footnotes"])
    if hf:
        extra += "\n\n## Headers and footers\n\n" + "\n".join(f"- {k}: {v}" for k, v in hf.items())
    text = "\n\n".join(out) + extra
    pd = look.tool("pandoc")
    if pd:
        r, o, _ = look.run_text([pd, str(look.path), "-t", "gfm", "--wrap=none", "--track-changes=all"])
        if r is not None and r.returncode == 0 and o.strip():
            text = o
            look.step("text with tracked changes", "pandoc")
    look.write_text("text.md", text, "document text: headings, [+inserted+] / [-deleted-] text, footnotes, headers")
    look.excerpt("Text start", text, 10, 900)
    core.scan_injection(look, text, "text")
    look.ask_human("Accepted view or all-changes view?", "Do deleted text and comments count as content?", "Are headers, footers and footnotes in scope?")


def sheet_cells(look, z, sheet_path, shared):
    root = parse_xml(look, z.read(sheet_path))
    cells, merged, formulas, uncached = {}, [], [], []
    hidden_rows = 0
    if root is None:
        return cells, merged, formulas, uncached, 0
    for el in root.iter():
        t = strip(el.tag)
        if t == "mergeCell":
            merged.append(attr(el, "ref"))
        elif t == "row" and attr(el, "hidden") in ("1", "true"):
            hidden_rows += 1
        elif t == "c":
            ref = attr(el, "r")
            ty = attr(el, "t")
            v = f = None
            inl = ""
            for ch in el:
                tc = strip(ch.tag)
                if tc == "v":
                    v = ch.text
                elif tc == "f":
                    f = ch.text or "(shared)"
                elif tc == "is":
                    inl = oo_text(ch)
            if f is not None:
                formulas.append((ref, f))
                if v is None:
                    uncached.append(ref)
            val = shared[int(v)] if ty == "s" and v is not None and int(v) < len(shared) else inl if ty == "inlineStr" else (v if v is not None else "")
            if ty in ("s", "inlineStr", "str", "e") and val != "":
                import dl_xlcalc
                val = dl_xlcalc.Text(val)   # stored as text: the formula evaluator must not read "12" as a number
            if val != "" or f is not None:
                m = re.match(r"([A-Z]+)(\d+)", ref)
                cells[(int(m.group(2)) - 1, col_index(ref))] = val
    return cells, merged, formulas, uncached, hidden_rows


def squeeze_rows(lines):
    """Table rows that differ only in their digits ('| 4 | | |', '| 5 | | |') are shown once, then counted: -> list of lines."""
    out, last, extra = [], None, 0
    for ln in lines:
        key = re.sub(r"\d+", "#", ln)
        if key == last:
            extra += 1
            continue
        if extra:
            out.append(f"| ... {extra} more row(s) like the one above |")
        out.append(ln)
        last, extra = key, 0
    if extra:
        out.append(f"| ... {extra} more row(s) like the one above |")
    return out


def office_xlsx(look, z, names):
    shared = []
    if "xl/sharedStrings.xml" in names:
        ss = parse_xml(look, z.read("xl/sharedStrings.xml"))
        if ss is not None:
            shared = [oo_text(si) for si in ss if strip(si.tag) == "si"]
    wb = parse_xml(look, z.read("xl/workbook.xml"))
    rels = parse_xml(look, z.read("xl/_rels/workbook.xml.rels"))
    rid = {attr(r, "Id"): attr(r, "Target") for r in rels} if rels is not None else {}
    sheets = []
    for el in wb.iter():
        if strip(el.tag) == "sheet":
            target = rid.get(rattr(el), "")
            target = target.lstrip("/")
            path = target if target.startswith("xl/") else "xl/" + target
            sheets.append({"name": attr(el, "name"), "state": attr(el, "state") or "visible", "path": path})
    inv, md = [], []
    total_unc = 0
    xl_store, xl_unc = {}, {}
    for s in sheets:
        if s["path"] not in names:
            continue
        cells, merged, formulas, unc, hidden_rows = sheet_cells(look, z, s["path"], shared)
        s.update(cells=len(cells), merged=len(merged), formulas=len(formulas), uncached=len(unc), hidden_rows=hidden_rows,
                 formula_samples=[f"{r}: ={f}" for r, f in formulas[:3]])
        total_unc += len(unc)
        xl_store[s["name"]] = (cells, formulas)
        if unc:
            xl_unc[s["name"]] = unc
        dl_xl.sheet_report(look, s["name"], cells, formulas, z.read(s["path"]))
        s["kind"] = "chartsheet" if "/chartsheets/" in s["path"] else "dialogsheet" if "/dialogsheets/" in s["path"] else "macrosheet" if "/macrosheets/" in s["path"] else "worksheet"
        try:
            import dl_offx
            s["agg"] = dl_offx.sheet_aggregates(look, s["name"], cells, formulas)
        except Exception as e:
            look.fail(f"sheet aggregates ({s['name']})", "stdlib", e)
        nr = max((r for r, c in cells), default=-1) + 1
        nc = max((c for r, c in cells), default=-1) + 1
        s["rows"], s["cols"] = nr, nc
        grid = [[cells.get((r, c), "") for c in range(nc)] for r in range(nr)]
        safe = re.sub(r"[^\w.-]+", "_", s["name"])
        buf = io.StringIO()
        csv.writer(buf).writerows(grid)
        s["csv"] = look.write_text(f"sheets/{safe}.csv", buf.getvalue(), f"sheet '{s['name']}' as CSV (cached values; recalculated when LibreOffice ran)", value=2, slice_cmd="--sheet NAME --range A1:H40").as_posix()
        inv.append(s)
        head, tail = grid[:5], grid[-5:] if nr > 10 else []
        rnd = random.Random(7).sample(grid[5:-5] if nr > 15 else [], min(10, max(0, nr - 15)))
        def rows_md(rs):
            return "\n".join(squeeze_rows(["| " + " | ".join(str(c)[:40] for c in r) + " |" for r in rs]))
        md.append(f"## Sheet {s['name']} ({s['state']}, {nr} rows x {nc} cols, {len(formulas)} formulas, {len(unc)} uncached, {len(merged)} merged)\n\n" +
                  rows_md(head) +
                  ("\n\n...tail:\n" + rows_md(tail) if tail else "") +
                  ("\n\n...10 random:\n" + rows_md(rnd) if rnd else "") +
                  ("\n\nFormula examples: " + "; ".join(s["formula_samples"]) if s["formula_samples"] else ""))
        if s["state"] not in ("visible", "veryHidden"):
            look.flag("HIDDEN-SHEET", s["name"], s["state"], "a hidden sheet is part of the workbook")
        if merged:
            look.flag("MERGED-CELLS", s["name"], ", ".join(merged[:5]), "only the top-left cell of a merged range holds the text")
        if unc:
            look.flag("UNCACHED-FORMULA", s["name"], f"{len(unc)} formulas without a stored result ({', '.join(unc[:4])})", "the file came from a library, not Excel; values need a recalculation")
    dl_xl.workbook_report(look, z, names, inv, z.read("xl/workbook.xml"))
    try:
        import dl_xlcalc
        dn = {re.search(r'name="([^"]+)"', a).group(1): re.sub(r"<[^>]+>", "", v).strip() for a, v in re.findall(r"<definedName\s([^>]*)>(.*?)</definedName>", z.read("xl/workbook.xml").decode("utf-8", "replace"), re.S)
              if re.search(r'name="([^"]+)"', a) and "_xlnm" not in a}
        dl_xlcalc.report(look, xl_store, dn, xl_unc)
    except Exception as e:
        look.fail("formula evaluation", "stdlib", e)
    look.fact("sheets", [{k: v for k, v in s.items() if k not in ("csv", "path")} for s in inv])
    look.fact("uncached_formulas", total_unc)
    look.fact("hidden_sheets", [s["name"] for s in inv if s["state"] != "visible"])
    look.headline = f"xlsx workbook, {len(inv)} sheets" + (f", {sum(1 for s in inv if s['state'] != 'visible')} hidden" if any(s['state'] != 'visible' for s in inv) else "")
    look.dims = f"{len(inv)} sheets"
    import dl_prof as P
    states = Counter(s["state"] for s in sheets)
    kinds = Counter(s.get("kind", "worksheet") for s in inv)
    aggs = [s["agg"] for s in inv if s.get("agg")]
    P.counts(look, [("sheets in workbook.xml", len(sheets)), ("visible", states.get("visible", 0)), ("hidden", states.get("hidden", 0) or None), ("veryHidden", states.get("veryHidden", 0) or None),
                    ("worksheets", kinds.get("worksheet", 0)), ("chartsheets", kinds.get("chartsheet") or None), ("sheets listed but missing", len(sheets) - len(inv) or None),
                    ("non-empty cells", sum(a["cells"] for a in aggs)), ("number cells", sum(a["numbers"] for a in aggs)), ("text cells", sum(a["text"] for a in aggs)),
                    ("formulas", sum(a["formulas"] for a in aggs)), ("formulas without a cached value", total_unc or None)], 96, "Workbook counts")
    look.line("Sheets in workbook order (state, used rows x columns, formulas): " + "; ".join(f"{i}. {s['name']} [{s['state']}] {s.get('rows', 0)}x{s.get('cols', 0)}, {s.get('formulas', 0)} formulas" for i, s in enumerate(inv, 1)), 92)
    look.line(f"Workbook: {len(inv)} sheets (" + ", ".join(f"{s['name']} [{s['state']}] {s['rows']}x{s['cols']}" for s in inv) + f"); formulas without stored results: {total_unc}.", 70)
    look.write_text("workbook.json", json.dumps([{k: v for k, v in s.items() if k != "path"} for s in inv], indent=1), "sheet inventory: visibility, size, merged, formulas, uncached", "json")
    look.write_text("text.md", "\n\n".join(md), "per sheet: shape, head 5, tail 5, 10 random rows, formula examples", value=6, slice_cmd="--sheet NAME --range A1:H40")
    if total_unc:
        recalc_xlsx(look, inv)
    look.ask_human("Values or formulas?", "Are hidden sheets in scope?", "Which sheet holds the answer?")


def lo_profile(look):
    prof = look.out / "lo_profile" / "user"
    prof.mkdir(parents=True, exist_ok=True)
    (prof / "registrymodifications.xcu").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>\n'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>\n'
        '</oor:items>\n', encoding="utf-8")
    return "-env:UserInstallation=file:///" + str((look.out / "lo_profile").resolve()).replace("\\", "/").lstrip("/")


def soffice_convert(look, args, src, outdir, timeout=180):
    so = look.tool("soffice")
    if not so:
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    r = look.run([so, lo_profile(look), "--headless", "--norestore", "--nolockcheck", *args, "--outdir", str(outdir), str(src)], timeout=timeout, cwd=outdir)
    return r


def recalc_xlsx(look, inv):
    if look.quick:
        look.skip("recalculated values of uncached formulas", "skipped at the quick tier (LibreOffice start-up takes seconds): run again with --tier standard", None, "")
        return
    tmp = look.out / "_lo"
    r = soffice_convert(look, ["--convert-to", "csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false,-1"], look.path, tmp)
    if r is None:
        look.skip("recalculated values of uncached formulas", "LibreOffice not found" if not look.no_tools else "disabled by --no-tools", "soffice")
        return
    got = 0
    for s in inv:
        src = tmp / f"{look.path.stem}-{s['name']}.csv"
        if src.exists():
            rows = list(csv.reader(io.StringIO(src.read_text(encoding="utf-8", errors="replace"))))
            safe = re.sub(r"[^\w.-]+", "_", s["name"])
            look.write_text(f"sheets/{safe}.csv", src.read_text(encoding="utf-8", errors="replace"), f"sheet '{s['name']}' as CSV, recalculated by LibreOffice")
            s["recalc_head"] = rows[:5]
            got += 1
    if got:
        look.step("recalculation (CSV export)", "LibreOffice")
        flat = "; ".join(f"{s['name']}: " + " / ".join(",".join(r) for r in s.get("recalc_head", [])[:3]) for s in inv if s.get("recalc_head") and s["uncached"])
        look.fact("recalculated", flat)
        look.line("Recalculated by LibreOffice (cached values were missing): " + flat[:300])
    else:
        look.flag("RECALC-FAILED", "LibreOffice", (r.stderr.decode('utf-8', 'replace')[-120:] if r is not None else "no output"), "")
    shutil.rmtree(tmp, ignore_errors=True)
    look.artifacts[:] = [a for a in look.artifacts if "lo_profile" not in a["path"]]


def ranges(nums):
    """[1, 2, 3, 5] -> '1-3, 5'."""
    out, nums = [], sorted(nums)
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ", ".join(out)


FIGURE = re.compile(r"\d[\d.,]*\s?(?:%|[MKBkmb]\b|EUR|USD|GBP|million|billion|thousand)?", re.I)


def pptx_outline(recs):
    """-> (key lines, contradictions). The slides are said in few words: titles that stand alone are listed, the ones that repeat
    ('Slide 7 topic') are one range; the notes likewise. A note that gives another figure than its slide is returned for a flag."""
    norm = lambda t: re.sub(r"\d+", "N", t)
    titles, bodies, notes = {}, {}, {}
    for i, paras, note, hid in recs:
        titles.setdefault(norm(paras[0]) if paras else "(no text)", []).append(i)
        for b in paras[1:]:
            bodies.setdefault(norm(b), []).append(i)
        if note:
            notes.setdefault(norm(note), []).append(i)
    by_no = {i: (paras, note, hid) for i, paras, note, hid in recs}
    own = sorted(i for k, v in titles.items() if len(v) < 3 for i in v)
    rep = {k: v for k, v in titles.items() if len(v) >= 3}
    parts = []
    for i in own[:14]:
        paras, _, hid = by_no[i]
        parts.append(f"{i}{' (hidden)' if hid else ''} {(paras[0] if paras else '(no text)')[:60]}")
    if len(own) > 14:
        parts.append(f"+{len(own) - 14} more")
    for k, v in sorted(rep.items(), key=lambda kv: -len(kv[1]))[:2]:
        parts.append(f"slides {ranges(v)} ({len(v)}) are titled '{k[:50].replace('N', 'N')}'")
    common = [(k, v) for k, v in bodies.items() if len(v) >= 3]
    lines = [f"Slides, {len(recs)} in all: " + "; ".join(parts) + (
        "; " + "; ".join(f"{len(v)} slides carry the body '{k[:70]}'" for k, v in sorted(common, key=lambda kv: -len(kv[1]))[:2]) if common else "")
        + ("; other body text is in slides.md" if any(len(v) < 3 for v in bodies.values()) and recs and len(recs) > 3 else "") + "."]
    nsl = sum(1 for _, _, n, _ in recs if n)
    if nsl:
        com = [(k, v) for k, v in notes.items() if len(v) >= 3]
        odd = sorted((i, n) for i, _, n, _ in recs if n and norm(n) not in {k for k, _ in com})
        bits = [f"{len(v)} say '{k[:70]}'" for k, v in sorted(com, key=lambda kv: -len(kv[1]))[:2]]
        bits += [f"{i}: '{n[:100]}'" for i, n in odd[:6]]
        if len(odd) > 6:
            bits.append(f"+{len(odd) - 6} more")
        lines.append(f"Speaker notes on {nsl} slides: " + "; ".join(bits) + ".")
    bad = []
    for i, paras, note, hid in recs:
        if not note or not paras:
            continue
        slide_txt = " ".join(paras)
        sf = {re.sub(r"\s+", "", f.strip().lower()): f.strip() for f in FIGURE.findall(slide_txt) if re.search(r"[%MKBkmb]|EUR|USD|GBP|million|billion|thousand", f, re.I) or "." in f}
        nf = {re.sub(r"\s+", "", f.strip().lower()): f.strip() for f in FIGURE.findall(note) if re.search(r"[%MKBkmb]|EUR|USD|GBP|million|billion|thousand", f, re.I) or "." in f}
        neg = {re.sub(r"\s+", "", m.lower()) for m in re.findall(r"(?i)\bnot\s+(\d[\d.,]*\s?(?:%|[MKBkmb]\b|EUR|USD|million|billion)?)", note)}
        hit = [sf[k] for k in neg if k in sf]
        if not hit and sf and nf and not (set(sf) & set(nf)):
            words = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", slide_txt)} & {w.lower() for w in re.findall(r"[A-Za-z]{5,}", note)}
            hit = [next(iter(sf.values()))] if words else []
        if hit:
            bad.append((i, hit[0], " ".join(note.split())))
    return lines, bad


def office_pptx(look, z, names):
    try:
        import dl_offx
        dl_offx.pptx_counts(look, z, names)
    except Exception as e:
        look.fail("slide counts", "stdlib", e)
    pres = parse_xml(look, z.read("ppt/presentation.xml")) if "ppt/presentation.xml" in names else None
    rels = parse_xml(look, z.read("ppt/_rels/presentation.xml.rels")) if "ppt/_rels/presentation.xml.rels" in names else None
    rid = {attr(r, "Id"): attr(r, "Target") for r in rels} if rels is not None else {}
    order = []
    if pres is not None:
        for el in pres.iter():
            if strip(el.tag) == "sldId":
                t = rid.get(rattr(el), "")
                order.append("ppt/" + t.lstrip("/").replace("ppt/", "", 1) if not t.startswith("/") else t.lstrip("/"))
    if not [s for s in order if s in names]:   # no slide list (or a broken one): the slide parts, in number order
        order = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
    md, hidden, notes_n, pics = [], [], 0, 0
    recs = []   # (number, paragraphs, note, hidden)
    for i, sp in enumerate(order, 1):
        if sp not in names:
            continue
        s = parse_xml(look, z.read(sp))
        if s is None:
            continue
        paras = []
        for p in s.iter():
            if strip(p.tag) == "p" and any(strip(c.tag) == "r" or strip(c.tag) == "fld" for c in p.iter()):
                t = "".join((x.text or "") for x in p.iter() if strip(x.tag) == "t").strip()
                if t:
                    paras.append(t)
        alts = [attr(e, "descr") for e in s.iter() if strip(e.tag) == "cNvPr" and attr(e, "descr")]
        pics += len(alts)
        is_hidden = attr(s, "show") == "0"
        if is_hidden:
            hidden.append(i)
        relp = sp.replace("slides/", "slides/_rels/") + ".rels"
        note = ""
        if relp in names:
            rr = parse_xml(look, z.read(relp))
            for r in rr if rr is not None else []:
                tgt = attr(r, "Target") or ""
                if "notesSlide" in tgt:
                    np_ = "ppt/notesSlides/" + tgt.rsplit("/", 1)[-1]
                    if np_ in names:
                        nx = parse_xml(look, z.read(np_))
                        if nx is not None:
                            nt = [ "".join((x.text or "") for x in p.iter() if strip(x.tag) == "t").strip() for p in nx.iter() if strip(p.tag) == "p"]
                            note = " ".join(t for t in nt if t and not t.isdigit())
        if note:
            notes_n += 1
        recs.append((i, paras, note, is_hidden))
        md.append(f"## Slide {i}{' (HIDDEN)' if is_hidden else ''}\n\n" + "\n".join(f"- {t}" for t in paras) + (f"\n\nNOTES: {note}" if note else "") +
                  (f"\n\nPicture alt text: {'; '.join(alts)}" if alts else ""))
    look.fact("slides", len(order))
    look.fact("hidden_slides", hidden)
    look.fact("slides_with_notes", notes_n)
    look.fact("slide_text", "\n".join(md)[:3000])
    look.headline = (f"Presentation, {len(order)} slides; hidden: {hidden or 'none'}; {notes_n} with speaker notes; {pics} pictures with alt text; "
                     f"{len([n for n in names if n.startswith('ppt/charts/') and n.endswith('.xml')])} charts")
    look.dims = f"{len(order)} slides"
    if hidden:
        look.flag("HIDDEN-SLIDE", ", ".join(map(str, hidden)), "hidden", "hidden slides are exported to the render so they can be seen")
    look.write_text("slides.md", "\n\n".join(md), "text per slide in order, with notes, hidden marks and picture alt text", value=5)
    outline_lines, contradictions = pptx_outline(recs)
    for ln in outline_lines:
        look.line(ln, 72)
    for i, shown, note_ in contradictions:
        look.flag("NOTE-CONTRADICTS-SLIDE", f"slide {i}", f"the slide shows {shown!r}, its speaker note says: {note_[:110]}", "the note and the slide disagree: which figure is right?")
    look.ask_human("Are speaker notes in scope?", "Should charts be read as pictures or as data?", "Are hidden slides in scope?")


def office_odf(look, z, names):
    if look.subtype in ("odt", "ods"):   # text and spreadsheets: structure, comments, changes, sheets (fix round 5)
        import dl_books
        try:
            return (dl_books.look_odt if look.subtype == "odt" else dl_books.look_ods)(look, z, names)
        except Exception as e:
            look.fail(f"OpenDocument {look.subtype} reader", "stdlib", e)
    x = parse_xml(look, z.read("content.xml")) if "content.xml" in names else None
    paras = []
    if x is not None:
        for el in x.iter():
            if strip(el.tag) in ("p", "h"):
                t = "".join(el.itertext()).strip()
                if t:
                    paras.append(t)
    look.line(f"OpenDocument {look.subtype}: {len(paras)} text blocks.")
    look.fact("paragraphs", len(paras))
    look.write_text("text.md", "\n\n".join(paras), "document text")


def office_legacy(look):
    st = look.subtype
    names = core.cfb_streams(look.path)
    look.fact("ole_streams", names[:40])
    look.line(f"Legacy Office file ({st}, OLE compound): streams {', '.join(names[:8])}.")
    if any(n in ("Macros", "_VBA_PROJECT_CUR", "VBA") for n in names):
        look.flag("MACRO", "OLE", "VBA storage present", "the macros were not opened or run")
        import dl_adapt
        dl_adapt.olevba_facts(look, open(look.path, "rb").read(32 << 20), look.path.name)
    import dl_worddoc
    if st == "doc":   # fix round 9: the text, tables, styles and properties from the file's own bytes first; LibreOffice only renders pages
        if dl_worddoc.look_doc(look):
            render_office(look)
            return
    else:   # fix round 10: the saved properties (application, revision, dates, counts) come from the OLE container, with or without LibreOffice
        dl_worddoc.ole_props(look, open(look.path, "rb").read(64 << 20), {"ppt": "PowerPoint", "xls": "Excel"}.get(st, "the app"))
    so = look.tool("soffice")
    done = False
    target = {"doc": "docx", "xls": "xlsx", "ppt": "pptx"}[st]
    if so:
        tmp = look.out / "_conv"
        r = soffice_convert(look, ["--convert-to", target], look.path, tmp)
        conv = tmp / f"{look.path.stem}.{target}"
        if r is not None and conv.exists():
            keep = (look.subtype, look.path)
            look.subtype, look.path = target, conv
            try:
                {"docx": lambda: office_docx(look, zipfile.ZipFile(conv), zipfile.ZipFile(conv).namelist()),
                 "xlsx": lambda: office_xlsx(look, zipfile.ZipFile(conv), zipfile.ZipFile(conv).namelist()),
                 "pptx": lambda: office_pptx(look, zipfile.ZipFile(conv), zipfile.ZipFile(conv).namelist())}[target]()
                look.line(f"Converted to {target} with LibreOffice first (legacy files have no readable XML).")
                look.step("legacy conversion", "LibreOffice")
                done = True
            finally:
                look.subtype, look.path = keep
        shutil.rmtree(tmp, ignore_errors=True)
        if done:
            render_office(look)
    else:
        look.skip(f"text of the {st} file (conversion to {target})", "LibreOffice not found" if not look.no_tools else "disabled by --no-tools", "soffice")
    if not done:
        b = open(look.path, "rb").read(32 << 20)
        st_list = core.strings_of(b, 6, 4000)
        if st_list:
            look.write_text("strings.txt", "\n".join(s for _, _, s in st_list), "printable strings from the legacy file (rough text, not reliable order)")
            look.line("Rough text from strings: " + " | ".join(s for _, _, s in st_list[:5])[:300])
            look.fact("rough_text", " ".join(s for _, _, s in st_list)[:2000])


def render_office(look):
    if look.quick:
        look.skip("rendered pages or slides (the picture of the document)", "skipped at the quick tier (LibreOffice start-up takes seconds): run again with --tier standard", None, "")
        return
    so = look.tool("soffice")
    if not so:
        look.skip("rendered pages or slides (the picture of the document)", "LibreOffice not found" if not look.no_tools else "disabled by --no-tools", "soffice")
        return
    st = look.subtype
    tmp = look.out / "_render"
    flt = "pdf:impress_pdf_Export:{\"ExportHiddenSlides\":{\"type\":\"boolean\",\"value\":\"true\"}}" if st.startswith("ppt") else "pdf"
    src = look.path
    r = soffice_convert(look, ["--convert-to", flt], src, tmp)
    pdf = tmp / f"{Path(src).stem}.pdf"
    if r is None or not pdf.exists():
        look.flag("RENDER-FAILED", "LibreOffice", (r.stderr.decode("utf-8", "replace")[-100:] if r is not None else "no result"), "")
        shutil.rmtree(tmp, ignore_errors=True)
        return
    fitz = look.mod("fitz")
    if not fitz:
        look.skip("pictures of pages (PDF render)", "PyMuPDF not importable", "fitz")
        shutil.rmtree(tmp, ignore_errors=True)
        return
    doc = fitz.open(str(pdf))
    pngs = render_pdf_pages(look, doc, "pages")
    label = "slides" if st.startswith("ppt") else "pages"
    page_sheets(look, pngs, f"sheet-{label}", f"{label} (LibreOffice render)")
    look.step("render to PDF and pictures", "LibreOffice")
    doc.close()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(look.out / "lo_profile", ignore_errors=True)


# ================================================================= notebook
def look_notebook(look):
    raw = open(look.path, "rb").read(200 << 20)
    try:
        nb = json.loads(raw.decode("utf-8", "replace"))
    except ValueError as e:
        look.flag("INVALID-JSON", "notebook", str(e)[:100], "")
        return
    cells = nb.get("cells", [])
    code = [c for c in cells if c.get("cell_type") == "code"]
    md_cells = [c for c in cells if c.get("cell_type") == "markdown"]
    j = lambda s: "".join(s) if isinstance(s, list) else (s or "")
    counts = [c.get("execution_count") for c in code if c.get("execution_count") is not None]
    out_of_order = counts != sorted(counts) or len(set(counts)) != len(counts)
    errors = []
    figs = 0
    pcs = []
    cm = []
    stripped = json.loads(json.dumps(nb))
    for i, c in enumerate(cells):
        src = j(c.get("source"))
        core.scan_injection(look, src, f"cell {i}")
        if c.get("cell_type") == "code":
            pcs.append(f"# %% [cell {i}]\n{src}\n")
            cm.append(f"## Cell {i} (code, run #{c.get('execution_count')})\n\n```python\n{src}\n```")
            for k, o in enumerate(c.get("outputs", [])):
                if o.get("output_type") == "error":
                    errors.append({"cell": i, "ename": o.get("ename"), "evalue": str(o.get("evalue"))[:200]})
                data = o.get("data", {}) if isinstance(o.get("data"), dict) else {}
                if "image/png" in data:
                    import base64
                    try:
                        png = base64.b64decode(j(data["image/png"]))
                        p = look.path_for(f"figs/cell{i}_{k}.png")
                        p.write_bytes(png)
                        wh = core.image_size(p)
                        look.add(p, "image" if wh and max(wh) <= core.MAX_IMG_EDGE else "internal", f"figure from cell {i}")
                        figs += 1
                    except Exception:
                        pass
                txt = j(o.get("text")) or j(data.get("text/plain"))
                if txt:
                    cm.append(f"Output of cell {i} ({core.UNTRUSTED}):\n```text\n{txt[:2000].replace('```', chr(39) * 3)}\n```")
                    core.scan_injection(look, txt[:5000], f"cell {i} output")
            sc = stripped["cells"][i]
            sc["outputs"] = []
            sc["execution_count"] = None
        else:
            cm.append(f"## Cell {i} ({c.get('cell_type')})\n\n{src}")
    look.fact("nbformat", f"{nb.get('nbformat')}.{nb.get('nbformat_minor')}")
    look.fact("cells", len(cells))
    look.fact("code_cells", len(code))
    look.fact("markdown_cells", len(md_cells))
    look.fact("execution_counts", counts)
    look.fact("out_of_order", out_of_order)
    look.fact("error_cells", [e["cell"] for e in errors])
    look.fact("figures", figs)
    look.line(f"Notebook (nbformat {nb.get('nbformat')}.{nb.get('nbformat_minor')}): {len(cells)} cells ({len(code)} code, {len(md_cells)} markdown), run order {counts}, {len(errors)} error output(s), {figs} figure(s). It was never executed.")
    if out_of_order:
        look.flag("HIDDEN-STATE", "execution counts", f"{counts}", "cells were not run top to bottom: results may depend on state that the file does not show")
    for e in errors:
        look.flag("ERROR-OUTPUT", f"cell {e['cell']}", f"{e['ename']}: {e['evalue']}", "the saved output is an exception")
    look.write_text("cells.md", "\n\n".join(cm), "every cell with its saved text output (truncated)")
    look.write_text("code.py", "\n".join(pcs), "code cells as a percent-format script (magics may not run outside Jupyter)")
    look.write_text("stripped.ipynb", json.dumps(stripped, indent=1), f"copy without outputs ({core.human(len(json.dumps(stripped)))} vs {core.human(len(raw))})", "json")
    look.ask_human("Which cell or figure matters?", "Should the notebook be run? This skill never runs it: run it yourself in a place you trust.")


# ================================================================= email and calendars
def look_email(look):
    {"eml": mail_eml, "mbox": mail_mbox, "ics": lambda lk: __import__("dl_geo").look_ics(lk), "vcf": mail_vcf, "msg": mail_msg}[look.subtype](look)


class _Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self._href, self._txt = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._txt = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self._href is not None:
            self._txt.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._txt).strip()))
            self._href = None


def host_of(u):
    m = re.match(r"(?i)^(?:https?://)?([^/\s:?#]+)", u.strip())
    h = m.group(1).lower() if m else ""
    return h[4:] if h.startswith("www.") else h


def html_to_text(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    import html as _h
    return re.sub(r"[ \t]+", " ", _h.unescape(s)).strip()


def mail_eml(look):
    from email import policy
    from email.parser import BytesParser
    with open(look.path, "rb") as f:
        m = BytesParser(policy=policy.default).parse(f)
    hdr = {k: str(m[k]) for k in ("From", "To", "Cc", "Date", "Subject", "Message-ID", "Reply-To", "Return-Path") if m[k]}
    recv = [str(r)[:200] for r in (m.get_all("Received") or [])]
    auth = str(m["Authentication-Results"]) if m["Authentication-Results"] else ""
    body = m.get_body(preferencelist=("plain", "html"))
    btxt, kind = "", "none"
    if body is not None:
        try:
            raw = body.get_content()
        except Exception:
            raw = ""
        kind = body.get_content_type()
        btxt = html_to_text(raw) if kind == "text/html" else raw
        if kind == "text/html":
            lk = _Links()
            lk.feed(raw)
            for href, txt in lk.links:
                th = host_of(txt) if re.search(r"[a-z0-9-]+\.[a-z]{2,}", txt, re.I) else ""
                if th and host_of(href) and th != host_of(href):
                    look.flag("LINK-MISMATCH", "html body", f"text shows {th}, link goes to {host_of(href)}", "possible phishing: the visible address and the real target differ")
    atts = []
    for part in m.iter_attachments():
        data = part.get_payload(decode=True) or b""
        atts.append({"name": part.get_filename() or "(none)", "type": part.get_content_type(), "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "_data": data})
    ctypes = {p.get_content_type() for p in m.walk()}
    for t, hint in (("multipart/signed", "signed message (S/MIME or PGP)"), ("application/pgp-encrypted", "OpenPGP-encrypted: the body is not readable without the key"),
                    ("application/pkcs7-mime", "S/MIME encrypted or signed")):
        if t in ctypes:
            look.flag("CRYPTO", t, hint, "ask the owner to export a decrypted copy; never ask for keys or passwords")
    if kind == "text/html":
        look.flag("HTML-ONLY", "body", "no plain-text part", "the text shown is converted from HTML")
    look.fact("from", hdr.get("From"))
    look.fact("subject", hdr.get("Subject"))
    look.fact("attachments", [{k: v for k, v in a.items() if k != "_data"} for a in atts])
    look.line(f"Email: from {hdr.get('From')}, to {hdr.get('To')}, {hdr.get('Date')}, subject {hdr.get('Subject')!r}; body {kind}; {len(atts)} attachment(s): " +
              ", ".join(f"{a['name']} ({a['type']}, {a['size']} B)" for a in atts) + (f"; {len(recv)} Received hops" if recv else "") + ".")
    if auth:
        look.line(f"Authentication-Results: {auth[:200]}")
        if re.search(r"(spf|dkim|dmarc)=(fail|softfail|none)", auth, re.I):
            look.flag("AUTH-FAIL", "Authentication-Results", re.search(r"(spf|dkim|dmarc)=(fail|softfail|none)", auth, re.I).group(0), "the sender could not be verified")
    look.write_text("message.md", "\n".join(f"{k}: {v}" for k, v in hdr.items()) + f"\n\n--- body ({kind}; {core.UNTRUSTED}) ---\n" + btxt[:60000], "headers and body text")
    look.write_text("headers.json", json.dumps({"headers": hdr, "received": recv, "authentication": auth}, indent=1), "headers, Received chain, authentication", "json")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "type", "size", "sha256"])
    for a in atts:
        w.writerow([a["name"], a["type"], a["size"], a["sha256"]])
    look.write_text("attachments.csv", buf.getvalue(), "attachment list (not opened)")
    core.scan_injection(look, btxt, "body")
    if atts and (look.extract or look.recurse):
        d = look.out / "attachments"
        d.mkdir(exist_ok=True)
        for i, a in enumerate(atts):
            safe = re.sub(r"[^\w.\- ]", "_", os.path.basename(a["name"].replace("\\", "/")))[:80] or f"att{i}"
            p = d / f"{i:02d}_{safe}"
            p.write_bytes(a["_data"])
            if look.recurse and i < look.recurse:
                core.recurse_into(look, p, a["name"])
        look.line(f"Attachments written to `{d}` (never executed).")
    elif atts:
        look.skip("attachment contents", "listed only; pass --extract or --recurse N to write and look at them", None, "python look.py FILE --recurse 3")
    look.ask_human("Do you trust the sender, and should the attachments be opened (never run) with --recurse?", "May the message text leave this machine?")


def _norm_subject(s):
    s = re.sub(r"(?i)^\s*((re|fwd?|aw|wg)\s*:\s*)+", "", s or "").strip()
    return re.sub(r"\d{3,}", "#", s)[:70] or "(no subject)"


def _addr(s):
    m = re.search(r"[\w.+-]+@[\w.-]+", s or "")
    return m.group(0).lower() if m else (s or "(none)")[:40]


def mail_mbox(look):
    """A whole-mailbox profile: dates, senders, subjects, attachments, authentication failures, link mismatches. One pass, no message is opened twice."""
    import mailbox
    from email import utils
    box = mailbox.mbox(str(look.path), create=False)
    rows, flagged = [], []
    senders, subjects, months, atypes = Counter(), Counter(), Counter(), Counter()
    dates, att_total, att_bytes, nauth, nlink, nhtml, ncrypto = [], 0, 0, 0, 0, 0, 0
    msgs_with_att = 0
    t0 = time.time()
    done = 0
    for key, msg in box.items():
        done += 1
        frm, subj = _addr(str(msg["From"])), str(msg["Subject"])
        when = None
        try:
            when = utils.parsedate_to_datetime(str(msg["Date"]))
        except (TypeError, ValueError, IndexError):
            pass
        if when:
            dates.append(when)
            months[when.strftime("%Y-%m")] += 1
        senders[frm] += 1
        subjects[_norm_subject(subj)] += 1
        notes, natt, nbytes = [], 0, 0
        auth = str(msg["Authentication-Results"] or "")
        if re.search(r"(spf|dkim|dmarc)=(fail|softfail)", auth, re.I):
            notes.append("AUTH-FAIL " + re.search(r"(spf|dkim|dmarc)=(fail|softfail)", auth, re.I).group(0))
            nauth += 1
        parts = list(msg.walk()) if msg.is_multipart() else [msg]
        for part in parts:
            ct = part.get_content_type()
            if ct.startswith("multipart/"):
                continue
            fn = part.get_filename()
            if fn or part.get("Content-Disposition", "").lower().startswith("attachment"):
                natt += 1
                atypes[ct] += 1
                try:
                    nbytes += len(part.get_payload(decode=True) or b"")
                except Exception:
                    pass
            elif ct == "text/html" and done <= 20000:
                nhtml += 1
                try:
                    raw = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", "replace")
                    lk = _Links()
                    lk.feed(raw)
                    for href, txt in lk.links:
                        th = host_of(txt) if re.search(r"[a-z0-9-]+\.[a-z]{2,}", txt, re.I) else ""
                        if th and host_of(href) and th != host_of(href):
                            notes.append(f"LINK-MISMATCH shows {th}, goes to {host_of(href)}")
                            nlink += 1
                            break
                except Exception:
                    pass
            if ct in ("application/pgp-encrypted", "application/pkcs7-mime"):
                ncrypto += 1
                notes.append("CRYPTO " + ct)
        if natt:
            msgs_with_att += 1
            att_total += natt
            att_bytes += nbytes
        rows.append([done, key, when.date().isoformat() if when else str(msg["Date"])[:30], frm, subj[:120], natt, nbytes, "; ".join(notes)])
        if notes:
            flagged.append(rows[-1])
        if time.time() - t0 > 60:
            look.flag("PARTIAL", "mailbox", f"stopped after {done} messages", "time cap; counts are lower bounds")
            break
    box.close()
    n = len(rows)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["n", "key", "date", "from", "subject", "attachments", "attachment_bytes", "notes"])
    w.writerows(rows)
    look.write_text("index.csv", buf.getvalue(), f"all {n} messages: date, sender, subject, attachment count and bytes, notes (search it, do not read it whole)")
    if flagged:
        buf2 = io.StringIO()
        w2 = csv.writer(buf2)
        w2.writerow(["n", "key", "date", "from", "subject", "attachments", "attachment_bytes", "notes"])
        w2.writerows(flagged[:500])
        look.write_text("flagged.csv", buf2.getvalue(), f"{len(flagged)} messages with a note (failed authentication, link mismatch, encryption)")
    look.fact("messages", n)
    look.fact("senders", len(senders))
    look.fact("with_attachments", msgs_with_att)
    look.fact("auth_failures", nauth)
    look.fact("link_mismatches", nlink)
    look.line(f"mbox: {n} messages from {len(senders)} senders" + (f", dated {min(dates).date()} to {max(dates).date()}" if dates else "") + f", {core.human(look.size)}.")
    if months:
        look.line("Messages per month: " + ", ".join(f"{k} {v}" for k, v in sorted(months.items())[:14]) + (" ..." if len(months) > 14 else ""))
    look.line("Top senders: " + "; ".join(f"{k} ({v})" for k, v in senders.most_common(6)))
    look.line("Top subjects: " + "; ".join(f"{k} ({v})" for k, v in subjects.most_common(6)))
    look.line(f"Attachments: {att_total} in {msgs_with_att} messages ({core.human(att_bytes)} decoded)" + (": " + ", ".join(f"{k} {v}" for k, v in atypes.most_common(5)) if atypes else "") + " (not opened).")
    look.line(f"Authentication failures: {nauth}. Links whose text names another site than they open: {nlink} (of {nhtml} HTML parts checked).")
    for r in [x for x in flagged if "AUTH-FAIL" in x[7]][:4]:
        look.flag("AUTH-FAIL", f"message {r[0]}", r[7], "the sender could not be verified; see flagged.csv for the rest")
    for r in [x for x in flagged if "LINK-MISMATCH" in x[7]][:4]:
        look.flag("LINK-MISMATCH", f"message {r[0]}", r[7], "possible phishing: the visible address and the real target differ")
    if nauth > 4 or nlink > 4:
        look.flag("MORE-IN-FLAGGED", "flagged.csv", f"{len(flagged)} messages with notes", "only the first 4 of each kind are listed here")
    look.ask_human("Which message matters? Each can be exported as .eml for a closer look.", "Should the attachments of the flagged messages be extracted (never run)?")


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def ics_recurrence(look, events):
    """Rules in words, the next occurrences, and the traps: forever-repeating events, floating times, rules this look cannot expand."""
    import datetime as dt
    import dl_cal
    now = dt.datetime.now()
    lines, unsupported = [], 0
    for e in events:
        if "RRULE" not in e:
            if e.get("DTSTART") and not e["DTSTART"].endswith("Z") and e.get("DTSTART_TZ") == "floating" and "T" in e["DTSTART"]:
                look.flag("FLOATING-TIME", e.get("SUMMARY") or e.get("UID", "?"), e["DTSTART"], "no time zone: it means a different instant in each viewer's zone")
            continue
        rule = dl_cal.parse_rrule(e["RRULE"])
        txt = dl_cal.describe(rule)
        if "COUNT" not in rule and "UNTIL" not in rule:
            look.flag("UNBOUNDED-RECURRENCE", e.get("SUMMARY") or "?", txt, "repeats forever: any count of events depends on the horizon you pick")
        try:
            start, kind = dl_cal.parse_dt(e["DTSTART"])
        except (KeyError, ValueError):
            continue
        if kind == "floating" and e.get("DTSTART_TZ") == "floating":
            look.flag("FLOATING-TIME", e.get("SUMMARY") or "?", e["DTSTART"], "no time zone: it means a different instant in each viewer's zone")
        ex = []
        for x in (e.get("EXDATE") or "").split(","):
            try:
                ex.append(dl_cal.parse_dt(x)[0])
            except ValueError:
                pass
        occ, ok = dl_cal.expand(start, rule, limit=400, exdates=ex)
        if not ok:
            unsupported += 1
            lines.append(f"{e.get('SUMMARY') or '?'}: {txt} (rule too complex to expand here)")
            continue
        nxt = [o for o in occ if o >= now][:3] or occ[:3]
        lines.append(f"{e.get('SUMMARY') or '?'}: {txt}; " + ("next " if any(o >= now for o in occ) else "first ") + ", ".join(f"{o:%Y-%m-%d %H:%M}" for o in nxt) + (f"; {len(ex)} excluded date(s)" if ex else ""))
    if lines:
        look.line("Recurring events: " + " | ".join(lines[:6]), 72)
    if unsupported or any(e.get("DTSTART_TZ") not in (None, "UTC", "floating") for e in events):
        ic = look.mod("icalendar") and look.mod("recurring_ical_events")
        if not ic:
            look.skip("exact recurrence expansion and time-zone transitions (daylight saving)", "python packages icalendar and recurring-ical-events not importable" if not look.no_tools else "disabled by --no-tools", "icalendar")


def mail_vcf(look):
    text = unfold(open(look.path, "rb").read(5 << 20).decode("utf-8", "replace"))
    cards = re.findall(r"BEGIN:VCARD(.*?)END:VCARD", text, re.S)
    look.fact("contacts", len(cards))
    look.fact("contact_names_private", re.findall(r"(?m)^FN[^:]*:(.*)$", text))
    look.line(f"Contact file: {len(cards)} cards (names, numbers and addresses are in look.json only; they are personal data).")
    look.flag("PERSONAL-DATA", "vcf", f"{len(cards)} contacts", "ask before quoting names, phone numbers or addresses")


def mail_msg(look):
    names = core.cfb_streams(look.path)
    look.fact("ole_streams", names[:30])
    em = look.mod("extract_msg")
    if em:
        try:
            m = em.Message(str(look.path))
            look.line(f"Outlook message: from {m.sender}, subject {m.subject!r}, {len(m.attachments)} attachments.")
            look.write_text("message.md", f"Subject: {m.subject}\nFrom: {m.sender}\n\n{m.body}", "message text")
            return
        except Exception as e:
            look.fail("Outlook .msg", "extract_msg", e)
    look.line(f"Outlook .msg (OLE compound file) with {len(names)} streams: {', '.join(names[:6])}. No reader is built in: export it to .eml from Outlook.")
    look.skip("Outlook .msg content", "no .msg reader (extract-msg) available" if not look.no_tools else "disabled by --no-tools", "extract_msg", "pip install extract-msg, or export the message to .eml from Outlook")
    look.ask_human("Can you export the message to .eml from Outlook?")


# ================================================================= web
class _Page(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "head"}
    BOILER = {"nav", "header", "footer", "aside", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.main, self.all, self.hidden = [], [], [], []
        self.meta, self.title, self.links, self.forms, self.scripts, self.lang = {}, "", [], [], [], ""
        self.inline_scripts, self.in_title, self.headings = 0, False, []
        self._href, self._ltxt, self._h = None, [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        st = (a.get("style") or "").replace(" ", "").lower()
        hidden = ("hidden" in a or a.get("aria-hidden") == "true" or "display:none" in st or "visibility:hidden" in st or "opacity:0" in st or "font-size:0" in st)
        self.stack.append((tag, hidden))
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            n = a.get("name") or a.get("property") or ""
            if n and a.get("content"):
                self.meta[n] = a["content"]
        if tag == "a" and a.get("href") is not None:
            self._href, self._ltxt = a["href"], []
        if tag == "form":
            self.forms.append({"action": a.get("action", ""), "method": a.get("method", "get")})
        if tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
            else:
                self.inline_scripts += 1
        if tag in ("h1", "h2", "h3"):
            self._h = [tag, []]

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._ltxt).strip()))
            self._href = None
        if tag in ("h1", "h2", "h3") and self._h:
            self.headings.append((self._h[0], "".join(self._h[1]).strip()))
            self._h = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self._href is not None:
            self._ltxt.append(data)
        if self._h:
            self._h[1].append(data)
        tags = [t for t, _ in self.stack]
        t = data.strip()
        if not t or any(x in self.SKIP for x in tags):
            return
        if any(h for _, h in self.stack):
            self.hidden.append(t)
            return
        self.all.append(t)
        if not any(x in self.BOILER for x in tags):
            self.main.append(t)


def look_web(look):
    raw = open(look.path, "rb").read(10 << 20)
    text, enc = core.decode_text(raw)
    text = text or raw.decode("latin-1")
    p = _Page()
    try:
        p.feed(text)
    except Exception as e:
        look.flag("HTML-PARSE", "html", str(e)[:80], "")
    main = "\n\n".join(p.main)
    tf = look.mod("trafilatura")
    how = "html.parser boilerplate heuristic"
    if tf:
        try:
            t = tf.extract(raw, output_format="markdown", with_metadata=False, favor_recall=True)
            if t and len(t) > 30:
                main, how = t, "trafilatura"
        except Exception:
            pass
    else:
        look.skip("main-text extraction with trafilatura", "trafilatura not importable" if not look.no_tools else "disabled by --no-tools", "trafilatura")
    look.fact("title", p.title.strip())
    look.fact("lang", p.lang)
    look.fact("main_chars", len(main))
    look.fact("forms", len(p.forms))
    look.fact("external_scripts", p.scripts)
    look.fact("links", len(p.links))
    look.line(f"Web page {p.title.strip()!r} (lang {p.lang or '?'}): main text {len(main)} chars via {how}; {len(p.links)} links; {len(p.forms)} forms; {len(p.scripts)} external scripts + {p.inline_scripts} inline.")
    if p.meta.get("description"):
        look.line("Description: " + p.meta["description"][:200])
    look.write_text("text.md", f"# {p.title.strip()}\n\n{main}", f"main text of the page ({how}); navigation and footers left out")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["href", "text"])
    w.writerows(p.links[:2000])
    look.write_text("links.csv", buf.getvalue(), f"{len(p.links)} links")
    look.write_text("page.json", json.dumps({"title": p.title.strip(), "lang": p.lang, "meta": p.meta, "headings": p.headings, "forms": p.forms, "scripts": p.scripts}, indent=1), "metadata, headings, forms, scripts", "json")
    for hid in p.hidden:
        look.flag("HIDDEN-TEXT", "display:none / hidden", hid[:60] + ("..." if len(hid) > 60 else ""), "text a reader does not see; may be an injection aimed at an AI")
    core.scan_injection(look, text, "html")
    if p.forms:
        look.flag("FORM", "html", f"{len(p.forms)} form(s)", "never submit a form on the user's behalf from a file")
    if p.scripts:
        look.flag("EXTERNAL-SCRIPT", "script src", ", ".join(p.scripts[:3]), "not loaded by this look")
    if len(main) < 200 and (p.scripts or p.inline_scripts > 2):
        look.flag("JS-ONLY?", "html", "little text but scripts", "the content is probably built in the browser: use the host's browser tool for the rendered page")
    screenshot(look)
    look.ask_human("Is this the page you meant, and is its date and author what you expect?", "Should the rendered picture be checked for layout?")


def screenshot(look):
    ch = look.tool("chrome")
    if not ch:
        look.skip("rendered picture of the page", "Chrome / Edge not found" if not look.no_tools else "disabled by --no-tools", "chrome")
        return
    out = look.path_for("screenshot.png")
    prof = look.out / "chrome_profile"
    # Chrome cannot screenshot with scripting switched off, so JavaScript is removed from a copy of the page instead
    # (script elements, inline handlers) and a content-security-policy forbids the rest; no network either.
    raw = look.path.read_bytes()[:5 << 20].decode("utf-8", "replace")
    raw = re.sub(r"<script\b.*?</script\s*>", "", raw, flags=re.I | re.S)
    raw = re.sub(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", raw, flags=re.I)
    safe = look.path_for("_render.html")
    csp = "script-src 'none'; connect-src 'none'; object-src 'none'; frame-src 'none'"
    safe.write_text(f'<meta http-equiv="Content-Security-Policy" content="{csp}">' + raw, encoding="utf-8")
    url = safe.resolve().as_uri()
    r = look.run([ch, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", f"--user-data-dir={prof}",
                  "--host-resolver-rules=MAP * ~NOTFOUND", "--window-size=1280,1600", "--hide-scrollbars",
                  f"--screenshot={out}", url], timeout=60)
    shutil.rmtree(prof, ignore_errors=True)
    safe.unlink(missing_ok=True)
    if r is not None and out.exists() and out.stat().st_size > 0:
        look.add(out, "image", "page as a browser draws it (JavaScript off, no network)")
        look.step("render", "Chrome headless")
    else:
        look.flag("RENDER-FAILED", "chrome", (r.stderr.decode("utf-8", "replace")[-100:] if r is not None else "no result"), "")


def fetch_url(url, opts):
    """Only with --allow-network: save one page to a temp file and return its path."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (sigmadeeplook; read-only)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(5 << 20)
    except Exception as e:
        print(f"Fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None
    d = core.cache_root() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    p = d / (hashlib.sha256(url.encode()).hexdigest()[:12] + ".html")
    p.write_bytes(data)
    return str(p)
