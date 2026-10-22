"""Fix round 8, part 2: header and structure fields of binary and legacy formats (category 3), on files built here.
Every expected figure is worked out from the data the test wrote, never read back from the look.
"""
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2_r8 import R8Base  # noqa: E402


def mo_bytes(entries, big=False):
    """A GNU gettext .mo file: entries = [(msgid_bytes, msgstr_bytes)] (the header entry has msgid b"")."""
    e = sorted(entries)
    f = ">" if big else "<"
    n = len(e)
    off_o, off_t = 28, 28 + 8 * n
    pos = off_t + 8 * n
    ob, tb, oi, ti = b"", b"", [], []
    for a, _ in e:
        oi.append((len(a), pos + len(ob)))
        ob += a + b"\0"
    pos += len(ob)
    for _, b in e:
        ti.append((len(b), pos + len(tb)))
        tb += b + b"\0"
    head = struct.pack(f + "7I", 0x950412DE, 0, n, off_o, off_t, 0, 0)
    return head + b"".join(struct.pack(f + "2I", *x) for x in oi) + b"".join(struct.pack(f + "2I", *x) for x in ti) + ob + tb


class Gettext(R8Base):
    def po(self):
        L = ["# Translation file", 'msgid ""', 'msgstr ""', r'"Project-Id-Version: demo 1.2\n"', r'"Language: sr_Latn\n"',
             r'"Content-Type: text/plain; charset=UTF-8\n"', r'"Plural-Forms: nplurals=3; plural=(n%10==1 ? 0 : 1);\n"', ""]
        for i in range(90):
            if i % 10 == 3:
                L.append("#, fuzzy")
            L += [f"#: src/mod{i % 6}.py:{i}", f"#: src/other.py:{i}"]
            if i % 15 == 0:
                L.append('msgctxt "menu"')
            L.append(f'msgid "Entry number {i}"')
            if i % 20 == 5:
                L += ['msgid_plural "Entries"', f'msgstr[0] "Unos {i}"', 'msgstr[1] "Unosa"', 'msgstr[2] "Unosa"']
            else:
                L.append(f'msgstr "{"" if i % 7 == 0 else "Unos %d" % i}"')
            L.append("")
        L += ['#~ msgid "Old one"', '#~ msgstr "Stari"', ""]
        p = self.tmp / "demo.po"
        p.write_text("\n".join(L) + "\n", encoding="utf-8")
        return p

    def test_po_catalogue_counts_and_last_entry(self):
        p = self.po()
        out, _, lj, _ = self.look(p)
        untrans = sum(1 for i in range(90) if i % 7 == 0 and i % 20 != 5)
        fuzzy = sum(1 for i in range(90) if i % 10 == 3)
        plural = sum(1 for i in range(90) if i % 20 == 5)
        ctx = sum(1 for i in range(90) if i % 15 == 0)
        self.assertIn("Gettext catalogue", out)
        self.assertIn("entries 90", out)
        self.assertIn(f"untranslated {untrans}", out)
        self.assertIn(f"translated {90 - untrans}", out)
        self.assertIn(f"fuzzy {fuzzy}", out)
        self.assertIn(f"plural entries {plural}", out)
        self.assertIn(f"with context {ctx}", out)
        self.assertIn("obsolete 1", out)
        self.assertIn("sr_Latn", out)
        self.assertIn("nplurals=3", out)
        self.assertIn("Entry number 89", out, "the last entry")

    def test_mo_header_and_entries(self):
        ent = [(b"", b"Project-Id-Version: demo 1.2\nLanguage: de\nContent-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=2; plural=(n != 1);\n")]
        for i in range(40):
            ent.append((f"Key {i:02d}".encode(), f"Wert {i}".encode()))
        ent.append((b"One file\0%d files", b"Eine Datei\0%d Dateien"))
        ent.append((b"menu\x04Open", b"Oeffnen"))
        for big in (False, True):
            p = self.tmp / f"demo{int(big)}.mo"
            p.write_bytes(mo_bytes(ent, big))
            out, _, lj, _ = self.look(p)
            self.assertIn("Gettext binary catalogue", out)
            self.assertIn("entries 42", out)
            self.assertIn("plural entries 1", out)
            self.assertIn("with context 1", out)
            self.assertIn("Language: de", out)
            self.assertIn("nplurals=2", out)
            self.assertIn("Eine Datei", out)
            self.assertIn("Oeffnen", out)
            self.assertEqual(lj["type"], "data")


def _pad4(b):
    return b + b"\0" * (-len(b) % 4)


def _nm(s):
    return struct.pack(">I", len(s)) + _pad4(s.encode())


def _atts(atts):
    if not atts:
        return struct.pack(">II", 0, 0)
    out = struct.pack(">II", 12, len(atts))
    for k, v in atts:
        if isinstance(v, str):
            out += _nm(k) + struct.pack(">II", 2, len(v)) + _pad4(v.encode())
        else:
            out += _nm(k) + struct.pack(">IIf", 5, 1, v)
    return out


def nc_bytes(dims, gatts, variables, numrecs=0):
    """A classic netCDF (CDF-1) file. dims: [(name, size)], size 0 = unlimited; variables: [(name, dimids, code, atts, values)], code 4 = int, 5 = float."""
    fmt = {4: ">i", 5: ">f"}
    rec = next((i for i, (_, s) in enumerate(dims) if s == 0), None)

    def header(begins):
        h = b"CDF\x01" + struct.pack(">I", numrecs)
        h += (struct.pack(">II", 10, len(dims)) + b"".join(_nm(n) + struct.pack(">I", s) for n, s in dims)) if dims else struct.pack(">II", 0, 0)
        h += _atts(gatts)
        h += struct.pack(">II", 11, len(variables))
        for (name, ids, code, atts, vals), (vsize, begin) in zip(variables, begins):
            h += _nm(name) + struct.pack(">I", len(ids)) + b"".join(struct.pack(">I", d) for d in ids) + _atts(atts) + struct.pack(">III", code, vsize, begin)
        return h
    vsizes = []
    for name, ids, code, atts, vals in variables:
        per = 1
        for d in (ids[1:] if ids and ids[0] == rec else ids):
            per *= dims[d][1]
        vsizes.append(_pad4(b"".join(struct.pack(fmt[code], 0) for _ in range(per))).__len__())
    hl = len(header([(0, 0)] * len(variables)))
    fixed = [(i, v) for i, v in enumerate(variables) if not (v[1] and v[1][0] == rec)]
    recs = [(i, v) for i, v in enumerate(variables) if v[1] and v[1][0] == rec]
    begins, pos, data = [None] * len(variables), hl, b""
    for i, (name, ids, code, atts, vals) in fixed:
        blob = _pad4(b"".join(struct.pack(fmt[code], x) for x in vals))
        begins[i] = (len(blob), pos + len(data))
        data += blob
    recsize = sum(vsizes[i] for i, _ in recs)
    first = pos + len(data)
    off = 0
    for i, _ in recs:
        begins[i] = (vsizes[i], first + off)
        off += vsizes[i]
    for r in range(numrecs):
        for i, (name, ids, code, atts, vals) in recs:
            per = vsizes[i] // 4
            data += _pad4(b"".join(struct.pack(fmt[code], x) for x in vals[r * per:(r + 1) * per]))
    assert recsize * numrecs == len(data) - (first - pos)
    return header(begins) + data


class Netcdf(R8Base):
    def test_damaged_header_is_a_corrupt_flag_not_an_internal_error(self):
        data = bytearray(nc_bytes([("lat", 5)], [("title", "x")], [("lat", [0], 5, [], [1.0, 2.0, 3.0, 4.0, 5.0])]))
        data[12:16] = bytes([0x7F, 0xFF, 0xFF, 0xF0])          # the dimension list claims two billion entries
        p = self.tmp / "damaged.nc"
        p.write_bytes(bytes(data))
        out, _, _, _ = self.look(p, ok=(0, 1))
        self.assertNotIn("INTERNAL-ERROR", out)
        self.assertIn("CORRUPT", out)

    def test_dimensions_attributes_variables_and_values(self):
        lat = [10.0 + 2 * i for i in range(5)]
        temp = [float(i % 11) - 3.5 for i in range(3 * 5)]
        time = [100, 101, 102]
        data = nc_bytes([("time", 0), ("lat", 5)], [("title", "Grid test"), ("version", 2.0)],
                        [("lat", [1], 5, [("units", "degrees_north")], lat), ("time", [0], 4, [("units", "days since 1979-01-01")], time),
                         ("temp", [0, 1], 5, [("units", "K"), ("long_name", "air temperature")], temp)], numrecs=3)
        p = self.tmp / "grid.nc"
        p.write_bytes(data)
        out, _, lj, _ = self.look(p)
        self.assertEqual(lj["type"], "data")
        self.assertIn("time = 3 (unlimited)", out)
        self.assertIn("lat = 5", out)
        self.assertIn("title (char) = Grid test", out)
        self.assertIn("dimensions 2", out)
        self.assertIn("variables 3", out)
        self.assertIn("Variable temp (float, time 3 x lat 5, 15 values)", out)
        self.assertIn("units = K", out)
        self.assertIn(f"min {min(temp):g}", out.replace(".0,", ","))
        self.assertIn(f"max {max(temp):g}", out.replace(".0,", ","))
        self.assertIn("last 102", out, "the last time step")
        self.assertIn("first 10, 12, 14, 16", out)


def sav_bytes(cases, compress=False):
    """An SPSS .sav file with AGE (numeric), CITY (string 10), GENDER (numeric, labelled 1/2) and SCORE (numeric); cases = [(age, city, gender, score)]."""
    def var(name, typ, label=""):
        r = struct.pack("<6i", 2, typ, 1 if label else 0, 0, 0x050800, 0x050800) + name.ljust(8).encode()
        if label:
            r += struct.pack("<i", len(label)) + label.encode() + b"\0" * (-len(label) % 4)
        return r
    d = var("AGE", 0, "Age in years") + var("CITY", 10, "City of residence") + struct.pack("<6i", 2, -1, 0, 0, 0, 0) + b" " * 8
    d += var("GENDER", 0) + var("SCORE", 0, "Test score")
    lab = struct.pack("<ii", 3, 2)   # value labels of GENDER, whose dictionary index is 4 (AGE 1, CITY 2 and its continuation 3)
    for v, t in ((1.0, "Male"), (2.0, "Female")):
        lab += struct.pack("<d", v) + bytes([len(t)]) + t.encode() + b"\0" * (-(1 + len(t)) % 8)
    d += lab + struct.pack("<iii", 4, 1, 4)
    long_names = b"SCORE=score_total"
    d += struct.pack("<4i", 7, 13, 1, len(long_names)) + long_names
    d += struct.pack("<ii", 999, 0)
    slots = []   # ("n", float) or ("s", 8 bytes)
    for age, city, gender, score in cases:
        c = city.encode().ljust(16)
        slots += [("n", float(age)), ("s", c[:8]), ("s", c[8:16]), ("n", float(gender)), ("n", float(score))]
    if compress:
        codes, raw = [], []
        for kind, v in slots:
            if kind == "n" and v == int(v) and -100 <= v <= 151:
                codes.append((int(v) + 100, None))
            elif kind == "s" and v == b" " * 8:
                codes.append((254, None))
            else:
                codes.append((253, struct.pack("<d", v) if kind == "n" else v))
        body = b""
        for i in range(0, len(codes), 8):
            grp = codes[i:i + 8]
            body += bytes([c for c, _ in grp] + [0] * (8 - len(grp))) + b"".join(x for _, x in grp if x is not None)
        body += bytes([252]) + b"\0" * 7
    else:
        body = b"".join(struct.pack("<d", v) if kind == "n" else v for kind, v in slots)
    head = b"$FL2" + b"@(#) test writer".ljust(60) + struct.pack("<5i", 2, 5, 1 if compress else 0, 0, len(cases)) + struct.pack("<d", 100.0)
    head += b"01 Jan 24" + b"12:30:00" + b"Demo survey".ljust(64) + b"\0\0\0"
    return head + d + body


class Spss(R8Base):
    def cases(self):
        return [(20 + i % 50, f"City{i % 7}", 1 + i % 2, round(i * 1.5, 2)) for i in range(60)]

    def test_header_dictionary_labels_and_cases(self):
        cs = self.cases()
        for compress in (False, True):
            p = self.tmp / f"survey{int(compress)}.sav"
            p.write_bytes(sav_bytes(cs, compress))
            out, _, lj, _ = self.look(p)
            self.assertEqual(lj["type"], "data")
            self.assertIn("cases 60", out)
            self.assertIn("variables 4", out)
            self.assertIn("Demo survey", out)
            self.assertIn("City of residence", out)
            self.assertIn("1 = Male; 2 = Female", out)
            self.assertIn("score_total", out, "the long variable name")
            self.assertIn(f"{len({c[1] for c in cs})} distinct", out)
            self.assertIn(f"max {max(c[3] for c in cs):g}", out)
            self.assertIn("Last case", out)
            self.assertIn(cs[-1][1], out, "the last case")


def _rec(rid, payload):
    """One BIFF12 record: 1-2 byte id, 1-4 byte length, payload."""
    head = bytes([rid]) if rid < 0x80 else bytes([(rid & 0x7F) | 0x80, rid >> 7])
    n, ln = len(payload), b""
    while True:
        b = n & 0x7F
        n >>= 7
        ln += bytes([b | (0x80 if n else 0)])
        if not n:
            break
    return head + ln + payload


def _ws(s):
    return struct.pack("<I", len(s)) + s.encode("utf-16-le")


def xlsb_bytes(sheets, strings):
    """An .xlsb. sheets: [(name, state 0/1/2, rows)] where a row is a list of cells: None, int, float or str (index into `strings` when the str is in it)."""
    import io
    import zipfile
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, "w")
    z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="bin" ContentType="application/octet-stream"/></Types>')
    wb, rels = b"", ['<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for k, (name, state, rows) in enumerate(sheets, 1):
        wb += _rec(156, struct.pack("<II", state, k) + _ws(f"rId{k}") + _ws(name))
        rels.append(f'<Relationship Id="rId{k}" Type="x" Target="worksheets/sheet{k}.bin"/>')
        body = _rec(129, b"\0" * 4) + _rec(145, b"")
        for r, row in enumerate(rows):
            body += _rec(0, struct.pack("<I", r) + b"\0" * 14)
            for c, v in enumerate(row):
                head = struct.pack("<II", c, 0)
                if v is None:
                    continue
                if isinstance(v, str):
                    body += _rec(7, head + struct.pack("<I", strings.index(v)))
                elif isinstance(v, int):
                    body += _rec(2, head + struct.pack("<I", (v << 2) | 2))
                else:
                    body += _rec(5, head + struct.pack("<d", v))
        body += _rec(146, b"") + _rec(130, b"")
        z.writestr(f"xl/worksheets/sheet{k}.bin", body)
    z.writestr("xl/workbook.bin", _rec(131, b"") + wb + _rec(132, b""))
    z.writestr("xl/_rels/workbook.bin.rels", "".join(rels) + "</Relationships>")
    z.writestr("xl/sharedStrings.bin", _rec(159, struct.pack("<II", len(strings), len(strings))) + b"".join(_rec(19, b"\0" + _ws(s)) for s in strings) + _rec(160, b""))
    z.close()
    return buf.getvalue()


class Xlsb(R8Base):
    def test_sheets_cells_and_hidden_state(self):
        strings = ["name", "qty", "price", "alpha", "beta", "gamma", "Hidden note"]
        rows = [["name", "qty", "price"]] + [[["alpha", "beta", "gamma"][i % 3], i, i * 0.5] for i in range(1, 41)]
        p = self.tmp / "book.xlsb"
        p.write_bytes(xlsb_bytes([("Orders", 0, rows), ("Notes", 1, [["Hidden note"], [None, 7]])], strings))
        out, _, lj, _ = self.look(p)
        self.assertEqual(lj["subtype"], "xlsb")
        self.assertNotIn("INTERNAL-ERROR", out)
        self.assertIn("Orders", out)
        self.assertIn("Notes", out)
        self.assertIn("hidden", out.lower())
        self.assertIn("sheets in workbook.xml 2", out)
        self.assertIn("41x3", out.replace(" ", ""), "rows x columns of the first sheet")
        self.assertIn("xlsb", out)
        # the cell values are in the stored text of the sheet
        txt = (self.tmp / "out_book.xlsb" / "text.md").read_text(encoding="utf-8")
        self.assertIn("gamma", txt)
        self.assertIn("| 40 | 20 |", txt)


if __name__ == "__main__":
    unittest.main()
