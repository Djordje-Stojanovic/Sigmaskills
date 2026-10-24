"""Fix round 14, lane F2 (ticket 83, P0.14b.H5): four causes of held-out set 13, on fixtures built here (none from a held-out set).

1. A SAS file declares its text encoding by a code number; the print must say the encoding name and the Windows code page, and `--ask` answers a
   code page / encoding question.
2. A palette picture: "how many pixels have exactly the colour RGB (r, g, b)" is a colour count, not a pixel position; `--ask` counts every pixel
   (RGB tuple, #hex, palette index), and step 1 has an `Ask a colour count:` line.
3. A GeoPackage names the spatial reference system of its feature layers in the first print; a table-like file with a numeric column shows the
   extreme-record form (`which <key> has the largest <number column>`) in its `Ask a count:` line, and that form runs as printed.
4. A cabinet (and a zip) holds small text members, such as a checksum list: the print quotes them, and `--ask` finds a line of a member.
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import hashlib
import importlib.util
import random
import re
import sqlite3
import struct
import sys
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS  # noqa: E402
from test_v2_r12_f1 import R12Base  # noqa: E402
from test_v2_r10_f2 import sas_header  # noqa: E402
from test_v2_r11_f3 import cab_bytes  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
HAVE_PIL = importlib.util.find_spec("PIL") is not None


class Base(R12Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r14f2_"))

    def answer(self, out):
        ln = next((x for x in out.splitlines() if x.startswith("Answer")), None)
        self.assertIsNotNone(ln, out[:1500])
        return ln


# ------------------------------------------------------------------ 1. the SAS code page
SAS_PAGES = {60: 1250, 61: 1251, 62: 1252, 63: 1253, 64: 1254, 65: 1255, 66: 1256, 67: 1257, 68: 1258}


def sas_file(code):
    h = bytearray(sas_header(b"CHARSET_TEST"))
    h[70] = code
    return bytes(h)


class SasCodePage(Base):
    def test_print_names_the_windows_code_page(self):
        for code, page in SAS_PAGES.items():
            with self.subTest(code=code):
                p = self.tmp / f"cp{code}.sas7bdat"
                p.write_bytes(sas_file(code))
                s1 = self.step1(p)
                self.assertIn(f"windows-{page}", s1)
                self.assertIn(f"code page {page}", s1)
                self.assertIn(f"SAS code {code}", s1, "the number the file stores stays in the print")

    def test_ask_answers_a_code_page_question(self):
        p = self.tmp / "cp64.sas7bdat"
        p.write_bytes(sas_file(64))
        self.prints(p, ok=(0, 1))
        for q in ("Which Windows code page (give the number) does the file declare for its text?", "what code page", "Which text encoding does the file use?", "charset"):
            with self.subTest(q=q):
                a = self.answer(self.raw(p, q))
                self.assertIn("1254" if "page" in q.lower() else "windows-1254", a)

    def test_utf8_and_latin1_have_no_wrong_windows_page(self):
        p = self.tmp / "u.sas7bdat"
        p.write_bytes(sas_file(20))
        s1 = self.step1(p)
        self.assertIn("utf-8", s1)
        q = self.tmp / "l.sas7bdat"
        q.write_bytes(sas_file(29))
        s2 = self.step1(q)
        self.assertIn("latin1", s2)
        self.assertNotIn("code page 1252", s2, "latin1 is ISO 8859-1; windows-1252 is code 62")
        a = self.answer(self.raw(q, "Which Windows code page does the file declare?"))
        self.assertNotIn("1252", a)
        self.assertIn("latin1", a)

    def test_an_unknown_code_is_said_as_unknown(self):
        p = self.tmp / "x.sas7bdat"
        p.write_bytes(sas_file(250))
        s1 = self.step1(p)
        self.assertIn("SAS code 250", s1)
        self.assertNotIn("windows-", s1)


# ------------------------------------------------------------------ 2. the exact colour count of a palette picture
PW, PH = 60, 40
PCOUNTS = [500, 400, 330, 280, 240, 200, 170, 140, 88, 20, 10, 8, 6, 4, 3, 1]   # index 8 holds the 9th most pixels: not in the top 8 of the print
assert sum(PCOUNTS) == PW * PH
PPAL = [(250, 248, 240), (22, 30, 74), (190, 40, 36), (36, 150, 74), (241, 190, 32), (60, 110, 200), (120, 60, 140), (240, 130, 40),
        (30, 170, 180), (150, 150, 150), (70, 70, 70), (206, 90, 160), (110, 190, 80), (14, 14, 14), (180, 120, 70), (235, 215, 150)]
TARGET = 8


def palette_pixels():
    idx = [i for i, n in enumerate(PCOUNTS) for _ in range(n)]
    random.Random(14).shuffle(idx)
    return [idx[y * PW:(y + 1) * PW] for y in range(PH)]   # rows, top to bottom


def bmp4(rows):
    pal = b"".join(bytes((b, g, r, 0)) for r, g, b in PPAL)
    stride = ((PW * 4 + 31) // 32) * 4
    body = b""
    for y in range(PH - 1, -1, -1):   # bottom-up
        row = rows[y]
        packed = bytes((row[x] << 4) | (row[x + 1] if x + 1 < PW else 0) for x in range(0, PW, 2))
        body += packed.ljust(stride, b"\0")
    off = 14 + 40 + len(pal)
    return b"BM" + struct.pack("<IHHI", off + len(body), 0, 0, off) + struct.pack("<IiiHHIIiiII", 40, PW, PH, 1, 4, 0, len(body), 2835, 2835, 16, 16) + pal + body


def rle(row):
    out, i = bytearray(), 0
    while i < len(row):
        c, n = row[i], 1
        while i + n < len(row) and row[i + n] == c and n < 63:
            n += 1
        out += bytes([0xC0 | n, c]) if n > 1 or c >= 0xC0 else bytes([c])
        i += n
    return bytes(out)


def pcx4(rows):
    """A 4-plane, 1-bit-per-plane PCX with the 16-colour palette in the header."""
    bpl = ((PW + 7) // 8 + 1) & ~1
    pal = b"".join(bytes(c) for c in PPAL)
    head = struct.pack("<BBBBHHHHHH", 10, 5, 1, 1, 0, 0, PW - 1, PH - 1, 72, 72) + pal + struct.pack("<BBHH", 0, 4, bpl, 1) + bytes(58)
    body = b""
    for row in rows:
        for plane in range(4):
            bits = bytearray(bpl)
            for x, v in enumerate(row):
                if (v >> plane) & 1:
                    bits[x // 8] |= 0x80 >> (x % 8)
            body += rle(bytes(bits))
    return head + body


def picture_files(tmp):
    rows = palette_pixels()
    out = {"scan.bmp": bmp4(rows), "plan.pcx": pcx4(rows)}
    if HAVE_PIL:
        from PIL import Image
        for name, fmt in (("map.gif", "GIF"), ("map.png", "PNG")):
            im = Image.new("P", (PW, PH))
            im.putpalette([v for c in PPAL for v in c])
            im.putdata([v for r in rows for v in r])
            p = tmp / name
            im.save(p, fmt)
            out[name] = p.read_bytes()
    return rows, out


def fmt_rgb(c):
    return f"({c[0]}, {c[1]}, {c[2]})"


class PaletteColourCount(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows, files = picture_files(cls.tmp)
        cls.paths = {}
        for name, raw in files.items():
            p = cls.tmp / name
            p.write_bytes(raw)
            cls.paths[name] = p
        cls.count = Counter(v for r in cls.rows for v in r)
        assert sorted(cls.count.values(), reverse=True).index(cls.count[TARGET]) >= 8

    def each(self):
        for name, p in self.paths.items():
            for tools in ((False,) if name.endswith(("bmp", "pcx")) else (True,)):
                yield name, p, tools

    def test_exact_colour_asked_as_rgb_is_counted_not_read_as_a_pixel(self):
        want = f"{self.count[TARGET]:,}"
        for name, p, tools in self.each():
            for q in ("How many pixels have exactly the colour RGB (30, 170, 180)? (The picture uses a 16-colour palette; count by the colour shown.)",
                      "number of pixels with rgb(30,170,180)", "How many pixels are the colour (30, 170, 180)?", "count the pixels of color RGB 30, 170, 180"):
                with self.subTest(file=name, q=q):
                    self.prints(p, tools=tools)
                    out = self.raw(p, q, tools=tools)
                    a = self.answer(out)
                    self.assertIn(want, a, out)
                    self.assertIn("#1eaab4", out)
                    self.assertIn(f"{100 * self.count[TARGET] / (PW * PH):.2f} %", out, "the share of all pixels")
                    self.assertNotIn("x=30", out)

    def test_hex_and_palette_index_forms(self):
        want = f"{self.count[TARGET]:,}"
        for name, p, tools in self.each():
            for q in ("How many pixels have the colour #1eaab4?", "how many pixels are colour 1EAAB4 (hex)", f"How many pixels use palette index {TARGET}?"):
                with self.subTest(file=name, q=q):
                    self.prints(p, tools=tools)
                    self.assertIn(want, self.answer(self.raw(p, q, tools=tools)))

    def test_a_colour_the_picture_does_not_use_counts_zero(self):
        p = self.paths["scan.bmp"]
        self.prints(p)
        a = self.answer(self.raw(p, "How many pixels have exactly the colour RGB (1, 2, 3)?"))
        self.assertRegex(a, r"\b0\b")
        self.assertNotRegex(a, r"x=1")

    def test_the_pixel_route_still_works(self):
        p = self.paths["scan.bmp"]
        self.prints(p)
        for q, (x, y) in (("pixel 30,17", (30, 17)), ("What colour is the pixel at x=5, y=9?", (5, 9)), ("colour at pixel (12, 3)", (12, 3))):
            with self.subTest(q=q):
                a = self.answer(self.raw(p, q))
                r, g, b = PPAL[self.rows[y][x]]
                self.assertIn(f"{r},{g},{b}", a)

    def test_step_one_has_the_colour_count_line_with_a_working_example(self):
        for name, p, tools in self.each():
            with self.subTest(file=name):
                s1 = self.step1(p, tools=tools)
                ln = next((x for x in s1.splitlines() if "Ask a colour count:" in x), None)
                self.assertIsNotNone(ln, s1[:3000])
                m = re.search(r'--ask "([^"]+)"', ln)
                self.assertIsNotNone(m, ln)
                out = self.raw(p, m.group(1), tools=tools)
                a = self.answer(out)
                self.assertRegex(a, r"\d[\d,]* pixels", a)
                self.assertLess(len(ln), 400, "keep the first print small")

    def test_the_question_parser_tells_a_colour_from_a_position_and_a_word(self):
        import dl_colour
        self.assertEqual(dl_colour.parse("how many pixels have colour RGB (30, 170, 180)")["rgb"], (30, 170, 180))
        self.assertEqual(dl_colour.parse("pixels of colour #1EAAB4")["rgb"], (30, 170, 180))
        self.assertEqual(dl_colour.parse("how many pixels use palette index 8"), {"kind": "index", "index": 8})
        self.assertIsNone(dl_colour.parse("What colour is the pixel at (30, 170)?"), "two numbers are a position")
        self.assertIsNone(dl_colour.parse("how many pixels have colour (300, 170, 180)"), "300 is not a channel value")
        self.assertIsNone(dl_colour.parse("which colour decade is shown"), "six letters after the word colour are a word, not a code")
        self.assertIsNone(dl_colour.parse("the colour 123456 of the sticker"), "six plain digits are a number")
        self.assertEqual(dl_colour.parse("pixels with hex decade")["rgb"], (0xde, 0xca, 0xde))

    def test_colour_table_lists_every_colour_with_its_count(self):
        p = self.paths["scan.bmp"]
        self.prints(p)
        out = self.raw(p, "Show the colour table with the pixel count of every palette colour")
        for i in (0, TARGET, 15):
            r, g, b = PPAL[i]
            self.assertIn(f"#{r:02x}{g:02x}{b:02x}", out)
            self.assertIn(f"{self.count[i]:,}", out)
        order = [m.group(0) for m in re.finditer(r"#[0-9a-f]{6}", out)]
        want = [f"#{PPAL[i][0]:02x}{PPAL[i][1]:02x}{PPAL[i][2]:02x}" for i, _ in self.count.most_common()]
        self.assertEqual(order[:16], want, "sorted by pixel count, largest first")


# ------------------------------------------------------------------ 3. the GeoPackage spatial reference system, and the extreme-record form
def gpkg_file(path, layers):
    """layers: [(table, geometry type, srs_id, [(feature id, area)])]. A GeoPackage with the three standard metadata tables."""
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT, srs_id INTEGER PRIMARY KEY, organization TEXT, organization_coordsys_id INTEGER, definition TEXT, description TEXT)")
    con.executemany("INSERT INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)", [("Undefined cartesian SRS", -1, "NONE", -1, "undefined", None), ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
                                                                              ("WGS 84", 4326, "EPSG", 4326, "GEOGCS[...]", None), ("CH1903+ / LV95", 2056, "EPSG", 2056, "PROJCS[...]", None),
                                                                              ("ETRS89 / LAEA Europe", 3035, "EPSG", 3035, "PROJCS[...]", None)])
    con.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT, description TEXT, last_change TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)")
    con.execute("CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, geometry_type_name TEXT, srs_id INTEGER, z TINYINT, m TINYINT)")
    for k, (table, gtype, srs, feats) in enumerate(layers):
        con.execute(f'CREATE TABLE "{table}" (fid INTEGER PRIMARY KEY, geom BLOB, feature_id TEXT, area_m2 REAL)')
        con.executemany(f'INSERT INTO "{table}" VALUES (?,?,?,?)', [(i, b"\x47\x50", fid, area) for i, (fid, area) in enumerate(feats, 1)])
        con.execute("INSERT INTO gpkg_contents VALUES (?,?,?,?,?,?,?,?,?,?)", (table, "features", table, "", "2026-01-01", 2600000.0 + k, 1200000.0, 2700000.0, 1300000.0 + k, srs))
        con.execute("INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,?,?)", (table, "geom", gtype, srs, 0, 0))
    con.execute("CREATE TABLE codes (code TEXT, label TEXT)")
    con.execute("INSERT INTO gpkg_contents VALUES ('codes','attributes','codes','', '2026-01-01', NULL,NULL,NULL,NULL, 0)")
    con.commit()
    con.close()


def feats(prefix, n, seed):
    rnd = random.Random(seed)
    return [(f"{prefix}-{k:04d}", round(rnd.uniform(100, 9000), 1)) for k in range(1, n + 1)]


class GpkgSrs(Base):
    def test_first_print_names_the_srs_of_the_feature_layers(self):
        p = self.tmp / "ch.gpkg"
        gpkg_file(p, [("parcels", "POLYGON", 2056, feats("PC", 40, 1)), ("roads", "LINESTRING", 2056, feats("RD", 30, 2))])
        s1 = self.step1(p)
        ln = next((x for x in s1.splitlines() if x.lstrip("- ").startswith("Feature layers")), None)
        self.assertIsNotNone(ln, s1[:3500])
        self.assertIn("parcels POLYGON srs 2056 (EPSG:2056", ln)
        self.assertIn("roads LINESTRING srs 2056 (EPSG:2056", ln)
        self.assertIn("CH1903+ / LV95", ln)

    def test_ask_for_the_srs_or_epsg_code(self):
        p = self.tmp / "ch2.gpkg"
        gpkg_file(p, [("parcels", "POLYGON", 2056, feats("PC", 40, 1)), ("roads", "LINESTRING", 2056, feats("RD", 30, 2))])
        self.prints(p)
        for q in ("Which spatial reference system (EPSG code) do the feature layers use?", "what epsg code do the layers use", "which CRS is used by the geopackage"):
            with self.subTest(q=q):
                a = self.answer(self.raw(p, q))
                self.assertIn("2056", a)

    def test_a_geopackage_without_the_srs_table_still_names_the_srs_ids(self):
        p = self.tmp / "nosrs.gpkg"
        gpkg_file(p, [("parcels", "POLYGON", 2056, feats("PC", 10, 3))])
        con = sqlite3.connect(p)
        con.execute("DROP TABLE gpkg_spatial_ref_sys")
        con.commit()
        con.close()
        s1 = self.step1(p)
        self.assertIn("parcels POLYGON srs 2056", s1)
        self.prints(p)
        self.assertIn("2056", self.answer(self.raw(p, "which srs do the layers use")))

    def test_a_path_with_spaces_and_url_characters_is_opened(self):
        d = self.tmp / "dir #1 %x"
        d.mkdir(exist_ok=True)
        p = d / "ch 100%.gpkg"
        gpkg_file(p, [("parcels", "POLYGON", 2056, feats("PC", 10, 3))])
        self.prints(p)
        self.assertIn("2056", self.answer(self.raw(p, "which EPSG code do the layers use")))

    def test_layers_with_different_systems_are_all_named(self):
        p = self.tmp / "mixed.gpkg"
        gpkg_file(p, [("parcels", "POLYGON", 2056, feats("PC", 10, 3)), ("wells", "POINT", 4326, feats("WE", 10, 4)), ("zones", "MULTIPOLYGON", 3035, feats("ZO", 10, 5))])
        s1 = self.step1(p)
        for frag in ("parcels POLYGON srs 2056", "wells POINT srs 4326", "zones MULTIPOLYGON srs 3035"):
            self.assertIn(frag, s1)
        self.prints(p)
        out = self.raw(p, "Which spatial reference system do the feature layers use?")
        for code in ("2056", "4326", "3035"):
            self.assertIn(code, out)


def extreme_form(text, which="largest"):
    m = re.search(r'"(which [^"]+ has the ' + which + r' [^"]+)"', text)
    return m.group(1) if m else None


class ExtremeRecordForm(Base):
    def table_case(self, p):
        text, _ = self.prints(p)
        return text

    def test_gpkg_line_shows_the_largest_form_and_it_answers_with_the_record(self):
        fs = feats("PC", 300, 7)
        p = self.tmp / "big.gpkg"
        gpkg_file(p, [("parcels", "POLYGON", 2056, fs), ("roads", "LINESTRING", 2056, feats("RD", 200, 8))])
        text = self.table_case(p)
        ln = next((x for x in text.splitlines() if "Ask a count:" in x), None)
        self.assertIsNotNone(ln, text[:3000])
        form = extreme_form(ln)
        self.assertIsNotNone(form, ln)
        self.assertRegex(form, r"which \w+ has the largest area_m2")
        q = form.replace("<table>", "parcels")
        out = self.raw(p, q + " in the parcels table")
        top = max(fs, key=lambda f: f[1])
        self.assertIn(top[0], self.answer(out), out)

    def test_csv_line_shows_the_form_built_from_its_own_columns(self):
        rnd = random.Random(9)
        rows = [(f"M-{k:05d}", rnd.choice(["north", "south", "east"]), round(rnd.uniform(5, 900), 2), rnd.randint(1, 50)) for k in range(1, 400)]
        p = self.tmp / "meters.csv"
        p.write_text("meter_id,zone,usage_kwh,age_years\n" + "\n".join(",".join(map(str, r)) for r in rows) + "\n", encoding="utf-8")
        text = self.table_case(p)
        ln = next((x for x in text.splitlines() if "Ask a count:" in x), None)
        self.assertIsNotNone(ln, text[:3000])
        big, small = extreme_form(ln, "largest"), extreme_form(ln, "smallest")
        self.assertIsNotNone(big, ln)
        self.assertRegex(big, r"which meter_id has the largest (usage_kwh|age_years)")
        col = re.search(r"largest (\w+)", big).group(1)
        idx = {"usage_kwh": 2, "age_years": 3}[col]
        top = max(rows, key=lambda r: r[idx])
        self.assertIn(top[0], self.answer(self.raw(p, big)))
        if small:
            low = min(rows, key=lambda r: r[idx])
            self.assertIn(low[0], self.answer(self.raw(p, small)))

    def test_a_number_column_named_like_an_operation_word_still_answers(self):
        rnd = random.Random(11)
        rows = [(8000 + k, rnd.choice(["north", "south"]), rnd.randint(1, 900)) for k in range(1, 80)]
        rows[17] = (rows[17][0], rows[17][1], 5000)   # one clear maximum
        p = self.tmp / "orders.csv"
        p.write_text("ticket_no,region,total\n" + "\n".join(",".join(map(str, r)) for r in rows) + "\n", encoding="utf-8")
        text = self.table_case(p)
        ln = next((x for x in text.splitlines() if "Ask a count:" in x), None)
        self.assertIsNotNone(ln, text[:3000])
        form = extreme_form(ln)
        if form:   # the form is only shown when it runs as printed
            self.assertIn(str(rows[17][0]), self.answer(self.raw(p, form)))

    def test_a_file_without_a_numeric_column_has_no_extreme_form(self):
        p = self.tmp / "names.csv"
        p.write_text("name,city\n" + "\n".join(f"n{k},c{k % 4}" for k in range(60)) + "\n", encoding="utf-8")
        text = self.table_case(p)
        self.assertNotIn("has the largest", text)


# ------------------------------------------------------------------ 4. small text members of a cabinet or a zip
CHECK_FILES = {
    "data\\branches.csv": b"branch_id;name;shelves;opened\nLB01;Branch A;15;1963\nLB02;Branch B;18;1966\nLB03;Branch C;21;1969\n",
    "data\\opening_hours.csv": b"branch_id,weekday,opens\n" + b"".join(f"LB{k:02d},Mon,09:00\n".encode() for k in range(1, 12)),
    "data\\member_stats.csv": b"branch_id,members\nLB01,1530\nLB02,1620\n",
    "reports\\totals.txt": b"Grand total of loans: 4711\nOverdue items: 38\n",
}


def sums_text(files):
    return "".join(f"{hashlib.sha256(d).hexdigest()}  {n}\n" for n, d in files.items()).encode()


def cab_case():
    sums = sums_text(CHECK_FILES)
    index = b"Library loan export, third quarter 2025 (synthetic).\ndata\\loans.zip holds the loan records and a branch summary.\n"
    f0 = [("INDEX.txt", index), ("checksums\\sha256sums.txt", sums), ("docs\\export_log.txt", b"export finished without errors\n")]
    f1 = [(n, d) for n, d in CHECK_FILES.items()]
    f2 = [("data\\loans.bin", bytes(range(256)) * 20)]
    return [(0, f0), (1, f1), (0, f2)], sums


class ArchiveTextMembers(Base):
    KEY_Q = "What SHA-256 hash does the checksum file inside the cabinet list for branches.csv?"

    def cab(self, name="loans.cab", folders=None):
        folders, sums = cab_case() if folders is None else (folders, b"")
        p = self.tmp / name
        p.write_bytes(cab_bytes(folders, block=300))
        return p, sums

    def test_the_checksum_member_is_quoted_in_the_first_two_prints(self):
        p, sums = self.cab()
        both, lj = self.prints(p)
        want = hashlib.sha256(CHECK_FILES["data\\branches.csv"]).hexdigest()
        self.assertIn(want, both)
        self.assertNotIn("INTERNAL-ERROR", {f["kind"] for f in lj.get("flags", [])})

    def test_ask_for_the_hash_of_a_file_from_the_checksum_member(self):
        p, _ = self.cab()
        self.prints(p)
        want = hashlib.sha256(CHECK_FILES["data\\branches.csv"]).hexdigest()
        for q in (self.KEY_Q, "which sha256 checksum is listed for opening_hours.csv", "line of sha256sums.txt for branches.csv", "what does sha256sums.txt say about branches.csv"):
            with self.subTest(q=q):
                out = self.raw(p, q)
                a = self.answer(out)
                target = "opening_hours.csv" if "opening_hours" in q else "branches.csv"
                got = hashlib.sha256(CHECK_FILES["data\\" + target]).hexdigest()
                self.assertIn(got, a, out)
                self.assertNotIn(hashlib.sha256(CHECK_FILES["data\\member_stats.csv"]).hexdigest(), a, "only the asked line")
        self.assertIn(want, self.raw(p, self.KEY_Q))

    def test_ask_reads_a_line_of_a_member_in_a_deflated_folder(self):
        p, _ = self.cab()
        self.prints(p)
        a = self.answer(self.raw(p, "what does totals.txt say about grand total"))
        self.assertIn("4711", a)
        a = self.answer(self.raw(p, "line of INDEX.txt for records"))
        self.assertIn("loan records", a)

    def test_a_folder_that_cannot_be_decoded_is_said_so_never_guessed(self):
        folders, _ = cab_case()
        f3 = [("late\\notes.txt", b"the secret word is pelican\n")]
        raw = cab_bytes(folders + [(0, f3)], block=300)
        # make the last folder LZX (type 3): the data is not LZX, so a reader that guessed would print garbage
        p = self.tmp / "lzx.cab"
        data = bytearray(raw)
        nfold = struct.unpack_from("<H", data, 26)[0]
        last = 36 + 8 * (nfold - 1)
        struct.pack_into("<H", data, last + 6, 0x1503)
        p.write_bytes(bytes(data))
        both, lj = self.prints(p)
        self.assertNotIn("pelican", both)
        self.assertIn("LZX", both)
        out = self.raw(p, "what does notes.txt say about the secret word")
        self.assertNotIn("pelican", out)
        self.assertRegex(out, r"(?i)not decoded|cannot be (read|decoded)|could not be decoded|needs 7-Zip")

    def test_zip_checksum_member_is_found_the_same_way(self):
        p = self.tmp / "loans.zip"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for n, d in CHECK_FILES.items():
                z.writestr(n.replace("\\", "/"), d)
            z.writestr("checksums/sha256sums.txt", sums_text({n.replace("\\", "/"): d for n, d in CHECK_FILES.items()}))
        both, _ = self.prints(p)
        want = hashlib.sha256(CHECK_FILES["data\\branches.csv"]).hexdigest()
        self.assertIn(want, both)
        self.prints(p)
        self.assertIn(want, self.answer(self.raw(p, self.KEY_Q)))

    def test_a_question_that_names_no_member_and_no_hash_is_left_to_the_other_routes(self):
        p = self.tmp / "plain.zip"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("data.csv", "id,qty\n" + "\n".join(f"{k},{k * 3}" for k in range(1, 30)) + "\n")
        self.prints(p)
        out = self.raw(p, "On which line is the value 33?")
        self.assertNotIn("Member data.csv,", out)

    def test_binary_members_are_not_printed_as_text(self):
        p, _ = self.cab()
        both, _ = self.prints(p)
        self.assertNotIn("\x00\x01\x02", both)


class StoredLookFromOlderScripts(Base):
    """A look stored by other scripts is not served again: after an upgrade the same file gets the new print and the new answers (the real t10 file
    was served its old `encoding code 64` line from a stored look)."""

    def test_a_stored_look_of_another_engine_is_rebuilt(self):
        import json
        p = self.tmp / "stale.sas7bdat"
        p.write_bytes(sas_file(64))
        self.step1(p)
        stored = self.out_of(p) / "look.json"
        j = json.loads(stored.read_text(encoding="utf-8"))
        self.assertTrue(j.get("engine"), "a stored look names the scripts that wrote it")
        j["engine"] = "other-scripts"
        stored.write_text(json.dumps(j), encoding="utf-8")
        (self.out_of(p) / "LOOK.md").write_text("old print: encoding code 64\n", encoding="utf-8")
        out = self.raw(p, "Which Windows code page does the file declare?")   # no --fresh
        self.assertIn("1254", self.answer(out))
        self.assertNotEqual(json.loads(stored.read_text(encoding="utf-8"))["engine"], "other-scripts")


if __name__ == "__main__":
    unittest.main()
