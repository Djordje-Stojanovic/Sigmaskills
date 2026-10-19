"""Fix round H7 (generalisation review of held-out set 5): wrong answers stated as certain.

Fixtures are built here with Serbian names; every expected figure comes from the code that wrote the fixture, never from the look.
A read limit is lowered with SIGMADEEPLOOK_<CSV|JSON|XML>_CAP so the over-the-cap path runs on a small file (a real one would be 256 MB+).
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import dl_data  # noqa: E402
import dl_delim  # noqa: E402
import dl_xlcalc as X  # noqa: E402

NAMES = ["Đorđe Šćekić", "Žarko Ćirić", "Nenad Đurić", "Željko Perišić", "Čedomir Pavlović"]


class H7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_h7_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look(self, path, *extra, env=None):
        out = self.tmp / ("out_" + path.name)
        r = run([str(path), "--out", str(out), "--fresh", "--no-tools", *extra], env=env)
        self.assertIn(r.returncode, (0, 2, 3), r.stderr[-1500:])
        return r.stdout, r.returncode

    # ------------------------------------------------------------ 1. CSV: a read limit is never a "full pass"
    def csv_file(self, name, rows, enc="utf-8"):
        lines = ["id,ime,iznos"]
        for i in range(1, rows + 1):
            lines.append(f"{i},{NAMES[i % 5]},{i % 100}.5")
            if i == rows // 2:
                lines.append("id,ime,iznos")   # a repeated header, to be found across the whole file
        p = self.tmp / name
        p.write_bytes(("\n".join(lines) + "\n").encode(enc))
        return p

    def test_csv_over_the_read_limit_is_partial_and_says_how_much(self):
        p = self.csv_file("big.csv", 6000)
        size = p.stat().st_size
        out, _ = self.look(p, env={"SIGMADEEPLOOK_CSV_CAP": "40000"})
        self.assertNotIn("full pass", out)
        self.assertNotIn("Every row was read", out)
        self.assertIn("PARTIAL", out)
        self.assertIn(f"of {size:,} bytes", out)
        self.assertIn("about 6,000 data rows", out)   # the line count of the WHOLE file, header and the repeated header taken off
        self.assertIn("PARTIAL read", out)            # the column legend no longer claims "every row"
        self.assertIn("repeated header rows 1", out)  # found by the whole-file scan, not only in the part read

    def test_csv_under_the_limit_is_still_a_full_pass(self):
        p = self.csv_file("small.csv", 300)
        out, _ = self.look(p)
        self.assertIn("full pass", out)
        self.assertNotIn("PARTIAL", out)

    def test_whole_file_stream_matches_the_in_memory_scan_at_every_chunk_size(self):
        for name, raw in (("a", b"h1,h2\n1,2\nh1,h2\n3,4\n"), ("b", b"\xef\xbb\xbfh1,h2\r\n1,2\r\nh1,h2\r\n3,4"), ("c", b"x\n" * 50 + b"h\n"), ("d", b"")):
            p = self.tmp / f"scan_{name}.csv"
            p.write_bytes(raw)
            want = dl_data.whole_file_scan(raw)
            for chunk in (1, 2, 3, 5, 7, 4096):
                self.assertEqual(dl_data.whole_file_stream(p, chunk), want, (name, chunk))
        big = (b"id,v\n" + b"".join(b"%d,%d\n" % (i, i) for i in range(2000))).replace(b"\n1000,", b"\nid,v\n1000,")
        p = self.tmp / "scan_e.csv"
        p.write_bytes(big)
        self.assertEqual(dl_data.whole_file_stream(p, 1000), dl_data.whole_file_scan(big))

    # ------------------------------------------------------------ 2. JSON and XML larger than the read limit
    def test_json_over_the_limit_is_partial_not_invalid(self):
        recs = [{"id": i, "ime": NAMES[i % 5], "iznos": i * 1.5} for i in range(4000)]
        p = self.tmp / "big.json"
        p.write_text(json.dumps({"meta": {"v": 1}, "items": recs}, ensure_ascii=False, indent=1), encoding="utf-8")
        out, _ = self.look(p, env={"SIGMADEEPLOOK_JSON_CAP": "30000"})
        self.assertNotIn("Invalid JSON", out)
        self.assertNotIn("INVALID-JSON", out)
        self.assertIn("PARTIAL", out)
        self.assertIn(f"of {p.stat().st_size:,} bytes", out)
        self.assertIn(NAMES[1], out)                  # records inside the part were read
        out2, _ = self.look(p)                         # under the limit: the whole document
        self.assertIn("items[] 4,000 records", out2)

    def test_json_really_invalid_stays_invalid(self):
        p = self.tmp / "broken.json"
        p.write_text('{"a": [1, 2, 3,, 4]}', encoding="utf-8")
        out, _ = self.look(p)
        self.assertIn("INVALID-JSON", out)

    def test_salvage_json_keeps_complete_elements(self):
        self.assertEqual(dl_data.salvage_json('[{"a": 1}, {"a": 2}, {"a": 3, "b": [1, 2'), [{"a": 1}, {"a": 2}, {"a": 3, "b": [1, 2]}])
        self.assertEqual(dl_data.salvage_json('{"x": {"y": [1, 2, 3]}, "z": "ab'), {"x": {"y": [1, 2, 3]}})
        self.assertIsNone(dl_data.salvage_json('"abc'))

    def test_xml_over_the_limit_is_partial_not_invalid(self):
        body = "".join(f"<rec id='{i}'><ime>{NAMES[i % 5]}</ime><iznos>{i}.5</iznos></rec>\n" for i in range(3000))
        p = self.tmp / "big.xml"
        p.write_text(f"<?xml version='1.0' encoding='utf-8'?>\n<doc>\n{body}</doc>\n", encoding="utf-8")
        out, _ = self.look(p, env={"SIGMADEEPLOOK_XML_CAP": "30000"})
        self.assertNotIn("INVALID-XML", out)
        self.assertIn("PARTIAL", out)
        self.assertIn("at least", out)
        self.assertIn(NAMES[2], out)

    def test_xml_with_a_harmless_entity_is_parsed(self):
        p = self.tmp / "doc.xml"
        p.write_text('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE doc [<!ENTITY co "Šećerana d.o.o.">]>\n<doc><owner>&co;</owner>'
                     '<rec id="1"><ime>Đorđe</ime></rec><rec id="2"><ime>Žarko</ime></rec></doc>', encoding="utf-8")
        out, rc = self.look(p)
        self.assertEqual(rc, 0)
        self.assertNotIn("ENTITY-DECLARATION", out)
        self.assertIn("rec (2)", out)

    def test_xml_entity_bomb_and_loop_are_refused(self):
        ents, prev = '<!ENTITY a0 "lol">', "a0"
        for i in range(1, 9):
            ents += f'<!ENTITY a{i} "{("&%s;" % prev) * 10}">'
            prev = f"a{i}"
        for name, doc in (("bomb.xml", f'<?xml version="1.0"?><!DOCTYPE d [{ents}]><d>&{prev};</d>'),
                          ("loop.xml", '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x "&y;"><!ENTITY y "&x;">]><d>&x;</d>')):
            p = self.tmp / name
            p.write_text(doc, encoding="utf-8")
            out, rc = self.look(p)
            self.assertEqual(rc, 2, name)
            self.assertIn("ENTITY-DECLARATION", out)

    # ------------------------------------------------------------ 3. the formula evaluator follows Excel
    def ev(self, f, cells=None, names=None):
        book = X.Book({"S": cells or {}}, {"S": {}}, names or {})
        return book.evaluate(f, "S")

    def test_operators_follow_excel_precedence(self):
        self.assertEqual(self.ev("=2^3^2"), 64)            # ^ runs left to right
        self.assertEqual(self.ev("=-2^2"), 4)              # negation binds tighter than ^
        self.assertEqual(self.ev("=2^-1"), 0.5)
        self.assertEqual(self.ev("=-50%"), -0.5)
        self.assertEqual(self.ev("=2*3^2"), 18)
        self.assertEqual(self.ev("=10-2-3"), 5)
        self.assertEqual(self.ev("=1+2&3"), "33")          # & is below +
        self.assertEqual(self.ev('="a"&"b"="ab"'), True)   # and above the comparisons

    def test_text_join_and_case_insensitive_compare(self):
        cells = {(0, 0): "1", (0, 1): "2", (1, 0): X.Text("abc"), (1, 1): X.Text("ABC"), (2, 0): X.Text("12")}
        self.assertEqual(self.ev("=A1&B1", cells), "12")
        self.assertEqual(self.ev('="id-"&A1&"/"&1.5', cells), "id-1/1.5")
        self.assertEqual(self.ev("=A2=B2", cells), True)
        self.assertEqual(self.ev('=IF("Đorđe"="ĐORĐE",1,0)'), 1)
        self.assertEqual(self.ev('=COUNTIF(A2:B2,"abc")', cells), 2)
        self.assertEqual(self.ev("=LEN(A1)", cells), 1)     # not len("1.0")
        self.assertFalse(self.ev("=A3=12", cells))          # text "12" is not the number 12 in a comparison
        self.assertEqual(self.ev("=A3+1", cells), 13)       # but arithmetic converts it, as Excel does

    def test_huge_powers_and_overflow_are_not_evaluated(self):
        for f in ("=9^9^9^9", "=9^9^9^9^9^9", "=10^400", "=1E300*1E300", "=(-8)^(1/3)", "=1/0", "=SQRT(-1)"):
            with self.assertRaises(X.Unsupported, msg=f):
                self.ev(f)

    def test_unsure_values_are_not_printed_as_evaluated(self):
        for f in ('=SUM("3")', "=NOSUCHFUNC(1)", '=COUNTIF(A1:A2,"a*")', "=VLOOKUP(5,A1:B2,2)"):
            with self.assertRaises(X.Unsupported, msg=f):
                self.ev(f, {(0, 0): X.Text("abc"), (1, 0): X.Text("abd")})

    def test_if_is_lazy_and_iferror_catches_errors_only(self):
        self.assertEqual(self.ev("=IF(A1=0,0,1/A1)", {(0, 0): "0"}), 0)
        self.assertEqual(self.ev("=IFERROR(1/0,7)"), 7)
        with self.assertRaises(X.Unsupported):
            self.ev("=IFERROR(NOSUCHFUNC(1),7)")            # a gap in this evaluator is not an Excel error

    def xlsx_uncached(self, formulas):
        """A workbook whose formulas carry no stored result (what a library writes)."""
        S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
        rows = ['<row r="1"><c r="A1" t="inlineStr"><is><t>Đorđe</t></is></c><c r="B1" t="inlineStr"><is><t>ĐORĐE</t></is></c><c r="C1"><v>1</v></c><c r="D1"><v>2</v></c></row>']
        for k, f in enumerate(formulas, 2):
            rows.append(f'<row r="{k}"><c r="A{k}"><f>{f}</f></c></row>')
        sheet = f'<?xml version="1.0" encoding="UTF-8"?><worksheet {S}><sheetData>{"".join(rows)}</sheetData></worksheet>'
        wb = f'<?xml version="1.0" encoding="UTF-8"?><workbook {S} {R}><sheets><sheet name="List" sheetId="1" r:id="rId1"/></sheets></workbook>'
        rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        p = self.tmp / "formulas.xlsx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("[Content_Types].xml", ct)
            z.writestr("xl/workbook.xml", wb)
            z.writestr("xl/_rels/workbook.xml.rels", rels)
            z.writestr("xl/worksheets/sheet1.xml", sheet)
        return p

    def test_workbook_print_uses_excel_values_and_names_what_it_did_not_compute(self):
        p = self.xlsx_uncached(["2^3^2", "-2^2", "C1&amp;D1", 'IF(A1=B1,"same","diff")', "9^9^9^9", "NOSUCHFUNC(C1)"])
        out, _ = self.look(p)
        self.assertIn("= 64 (=2^3^2)", out)
        self.assertIn("= 4 (=-2^2)", out)
        self.assertIn("= 12 (=C1&D1)", out)
        self.assertIn("= same", out)
        self.assertNotIn("not guessed", out)
        self.assertRegex(out, r"Not computed: 2 formula\(s\)")
        self.assertNotIn("(=9^9^9^9)", out)

    # ------------------------------------------------------------ 4. text that is not UTF-8 or Western
    def test_code_page_is_chosen_by_how_real_the_letters_look(self):
        serbian = "Ime;Grad\nĐorđe Šćekić;Čačak\nŽarko Ćirić;Šabac\nNenad Đurić;Kruševac\nŽeljko Perišić;Užice\n"
        cyr = "Ime;Grad\nДраган Ђорђевић;Београд\nМилош Јовановић;Нови Сад\nЈелена Ћирић;Ниш\n"
        french = "Nom;Ville\nFrançois Müller;Besançon\nJosé Núñez;Málaga\nRenée Dupré;Orléans\n"
        german = "Name;Stadt\nJürgen Müller;Köln\nBjörn Größer;Düsseldorf\nStraße 5\n"
        polish = "Imię;Miasto\nŁukasz Żółć;Łódź\nZażółć gęślą jaźń\n"
        for text, enc in ((serbian, "cp1250"), (cyr, "cp1251"), (french, "cp1252"), (german, "cp1252"), (polish, "cp1250"),
                          ("Имя;Город\nИван Петров;Москва\nСергей Иванов;Санкт-Петербург\n", "koi8_r")):
            got, name = dl_delim.sniff_encoding(text.encode(enc))
            self.assertEqual((got, name), (text, enc), enc)

    def test_one_stray_byte_does_not_turn_a_utf8_file_into_cp1252(self):
        raw = (NAMES[0] + ";Čačak\n").encode("utf-8") * 500 + b"bad\xe9byte\n"
        text, enc = dl_delim.sniff_encoding(raw)
        self.assertEqual(enc, "utf-8")
        self.assertIn("Đorđe Šćekić", text)

    def test_serbian_cp1250_csv_reads_with_the_right_letters(self):
        p = self.csv_file("srb1250.csv", 60, enc="cp1250")
        out, _ = self.look(p)
        self.assertIn("Windows-1250", out)
        self.assertIn("Đorđe Šćekić", out)
        self.assertNotIn("Ðorðe", out)

    def test_serbian_cyrillic_cp1251_csv(self):
        p = self.tmp / "cyr1251.csv"
        p.write_bytes(("ime;grad\n" + "".join(f"{n};Београд\n" for n in ("Ђорђе Шћекић", "Жарко Ћирић", "Ненад Ђурић") * 20)).encode("cp1251"))
        out, _ = self.look(p)
        self.assertIn("Windows-1251", out)
        self.assertIn("Ђорђе Шћекић", out)

    # ------------------------------------------------------------ 5. the cache key of a big file is a bounded sample
    def test_big_file_key_changes_with_an_edit_in_place_and_is_not_a_full_read(self):
        import dl_core
        p = self.tmp / "key.bin"
        size = dl_core.FULL_HASH_BYTES + (3 << 20)
        with open(p, "wb") as f:
            f.write(os.urandom(1 << 20) * (size >> 20))
        k1 = dl_core.file_key(p)
        self.assertEqual(k1, dl_core.file_key(p))
        st = os.stat(p)
        with open(p, "r+b") as f:
            f.seek(size // 2)
            f.write(b"edit")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        self.assertNotEqual(k1, dl_core.file_key(p))
        small = self.tmp / "key_small.txt"
        small.write_bytes(b"hello")
        self.assertEqual(dl_core.file_key(small), dl_core.sha256_file(small))

    def test_directory_key_covers_modified_times(self):
        import dl_core
        d = self.tmp / "keydir"
        d.mkdir()
        f = d / "a.txt"
        f.write_text("1234")
        k1 = dl_core.sha256_dir(d)
        st = os.stat(f)
        f.write_text("abcd")   # same size, new content
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 7_000_000_000))
        self.assertNotEqual(k1, dl_core.sha256_dir(d))


if __name__ == "__main__":
    unittest.main()
