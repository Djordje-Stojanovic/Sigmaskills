"""SigmaDeepLook Excel binary workbook (.xlsb) reader, standard library only (fix round 8, ticket 83 P0.14b.H8).

An .xlsb file is a zip of BIFF12 record streams (xl/workbook.bin, xl/worksheets/sheetN.bin, xl/sharedStrings.bin). This module reads the
sheet list (name, visibility), the shared strings and every cell value (numbers, text, booleans, errors and the cached result of
formulas), and writes them as a plain .xlsx next to the look, so the workbook reader of the look (sheet counts, per-sheet profile,
head and tail rows, hidden sheets) runs unchanged. Formula text is not decoded: a formula cell is counted and keeps its cached value.
"""
import re
import struct
import zipfile
from xml.sax.saxutils import escape

ERRORS = {0x00: "#NULL!", 0x07: "#DIV/0!", 0x0F: "#VALUE!", 0x17: "#REF!", 0x1D: "#NAME?", 0x24: "#NUM!", 0x2A: "#N/A", 0x2B: "#GETTING_DATA"}
REC_CELLS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
MAX_CELLS = 5_000_000


def records(data):
    """Yield (record id, payload) from a BIFF12 stream."""
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        i += 1
        rid = b
        if b & 0x80:
            if i >= n:
                return
            rid = (b & 0x7F) | ((data[i] & 0x7F) << 7)
            i += 1
        ln, shift = 0, 0
        for _ in range(4):
            if i >= n:
                return
            c = data[i]
            i += 1
            ln |= (c & 0x7F) << shift
            shift += 7
            if not c & 0x80:
                break
        yield rid, data[i:i + ln]
        i += ln


def wstr(p, at=0):
    """XLWideString at `at`: -> (text, next offset)."""
    n = struct.unpack_from("<I", p, at)[0]
    if n == 0xFFFFFFFF:
        return "", at + 4
    return p[at + 4:at + 4 + 2 * n].decode("utf-16-le", "replace"), at + 4 + 2 * n


def rk_value(v):
    if v & 2:
        x = v >> 2
        x = x - (1 << 30) if x & (1 << 29) else x
        x = float(x)
    else:
        x = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return x / 100.0 if v & 1 else x


def read_sheets(z):
    """-> [(name, state, target path)] in workbook order."""
    wb = z.read("xl/workbook.bin")
    rels = z.read("xl/_rels/workbook.bin.rels").decode("utf-8", "replace") if "xl/_rels/workbook.bin.rels" in z.namelist() else ""
    rid = {}
    for m in re.finditer(r"<Relationship\b[^>]*>", rels):
        t = m.group(0)
        a, b = re.search(r'\bId="([^"]*)"', t), re.search(r'\bTarget="([^"]*)"', t)
        if a and b:
            rid[a.group(1)] = b.group(1)
    out = []
    for rec, p in records(wb):
        if rec == 156 and len(p) >= 12:
            state = struct.unpack_from("<I", p, 0)[0]
            rel, at = wstr(p, 8)
            name, _ = wstr(p, at)
            tgt = rid.get(rel, "").lstrip("/")
            out.append((name, {0: "visible", 1: "hidden", 2: "veryHidden"}.get(state, "visible"), tgt if tgt.startswith("xl/") else "xl/" + tgt))
    return out


def read_strings(z):
    if "xl/sharedStrings.bin" not in z.namelist():
        return []
    out = []
    for rec, p in records(z.read("xl/sharedStrings.bin")):
        if rec == 19 and len(p) >= 5:
            out.append(wstr(p, 1)[0])
    return out


def read_cells(data, sst):
    """-> (cells {(row, col): (kind, value)}, formulas count). kind: n number, s text, b boolean, e error."""
    cells, formulas, row = {}, 0, 0
    for rec, p in records(data):
        if rec == 0 and len(p) >= 4:
            row = struct.unpack_from("<I", p, 0)[0]
            continue
        if rec not in REC_CELLS or len(p) < 8 or len(cells) >= MAX_CELLS:
            continue
        col = struct.unpack_from("<I", p, 0)[0]
        v = p[8:]
        try:
            if rec == 2:
                cells[(row, col)] = ("n", rk_value(struct.unpack_from("<I", v, 0)[0]))
            elif rec == 5:
                cells[(row, col)] = ("n", struct.unpack_from("<d", v, 0)[0])
            elif rec == 6:
                cells[(row, col)] = ("s", wstr(v, 0)[0])
            elif rec == 7:
                i = struct.unpack_from("<I", v, 0)[0]
                cells[(row, col)] = ("s", sst[i] if i < len(sst) else "")
            elif rec == 4:
                cells[(row, col)] = ("b", v[0])
            elif rec == 3:
                cells[(row, col)] = ("e", ERRORS.get(v[0], f"#ERR{v[0]}"))
            elif rec == 9:
                formulas += 1
                cells[(row, col)] = ("nf", struct.unpack_from("<d", v, 0)[0])
            elif rec == 8:
                formulas += 1
                cells[(row, col)] = ("sf", wstr(v, 0)[0])
            elif rec == 10:
                formulas += 1
                cells[(row, col)] = ("bf", v[0])
            elif rec == 11:
                formulas += 1
                cells[(row, col)] = ("ef", ERRORS.get(v[0], f"#ERR{v[0]}"))
        except (struct.error, IndexError):
            continue
    return cells, formulas


def col_letters(c):
    s, n = "", c + 1
    while n:
        n, k = divmod(n - 1, 26)
        s = chr(65 + k) + s
    return s


def _num(x):
    return repr(int(x)) if x == int(x) and abs(x) < 1e15 else repr(x)


def sheet_xml(cells):
    rows = {}
    for (r, c), kv in cells.items():
        rows.setdefault(r, []).append((c, kv))
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for r in sorted(rows):
        out.append(f'<row r="{r + 1}">')
        for c, (kind, val) in sorted(rows[r]):
            ref = f"{col_letters(c)}{r + 1}"
            f = "<f></f>" if kind.endswith("f") and len(kind) == 2 else ""
            k = kind[0]
            if k == "n":
                out.append(f'<c r="{ref}">{f}<v>{_num(val)}</v></c>')
            elif k == "b":
                out.append(f'<c r="{ref}" t="b">{f}<v>{int(bool(val))}</v></c>')
            elif k == "e":
                out.append(f'<c r="{ref}" t="e">{f}<v>{escape(val)}</v></c>')
            else:
                out.append(f'<c r="{ref}" t="inlineStr">{f}<is><t xml:space="preserve">{escape(val)}</t></is></c>' if not f else f'<c r="{ref}" t="str">{f}<v>{escape(val)}</v></c>')
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def to_xlsx(src, dst):
    """Write `dst` (.xlsx) holding the sheets, values and visibility of the .xlsb at `src`. -> dict(sheets [(name, state, cells, formulas)])."""
    info = []
    with zipfile.ZipFile(src) as z, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as o:
        sst = read_strings(z)
        sheets = read_sheets(z)
        names = set(z.namelist())
        wbx = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
        rel = ['<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
        ct = ['<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
        for k, (name, state, path) in enumerate(sheets, 1):
            cells, formulas = ({}, 0)
            if path in names:
                cells, formulas = read_cells(z.read(path), sst)
            info.append((name, state, len(cells), formulas))
            o.writestr(f"xl/worksheets/sheet{k}.xml", sheet_xml(cells))
            wbx.append(f'<sheet name="{escape(name, {chr(34): "&quot;"})}" sheetId="{k}"' + (f' state="{state}"' if state != "visible" else "") + f' r:id="rId{k}"/>')
            rel.append(f'<Relationship Id="rId{k}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{k}.xml"/>')
            ct.append(f'<Override PartName="/xl/worksheets/sheet{k}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        o.writestr("xl/workbook.xml", "".join(wbx) + "</sheets></workbook>")
        o.writestr("xl/_rels/workbook.xml.rels", "".join(rel) + "</Relationships>")
        o.writestr("[Content_Types].xml", "".join(ct) + "</Types>")
        o.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    return {"sheets": info, "strings": len(sst)}
