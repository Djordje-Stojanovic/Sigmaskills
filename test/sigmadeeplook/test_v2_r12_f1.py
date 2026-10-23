"""Fix round 12, lane F1 (ticket 83, P0.14b.H5): the lookups and conditional counts that `--ask` missed in held-out set 11, on fixtures built here
(none from a held-out set).

Seven causes, each tested at the cause and never at a file name, value or question text:
1. a big .sav: a number that asks for rounding ("to 1 decimal") was taken for a key and filled the 5,000-row keep list, so the real key was never
   reached and the answer said "0 matching case(s)"; a keep list that overflows must say PARTIAL, never a confident 0;
2. a number in quotes ("3287", curly quotes, backticks) parsed as nothing in a netCDF question;
3. the same for a pixel question on a BMP;
4. step 1 of every table-like file says which `--ask` forms count rows (with the file's real column names);
5. a word or text-contains question over cue text is a real filter (whole word, case as written), and a count question that matched no filter
   refuses instead of answering the total row count;
6. a question that names a table of the file (gpkg_contents) is answered from that table.
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import importlib.util
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r8b import xlsb_bytes  # noqa: E402
from test_v2_r9 import sbv_stamp  # noqa: E402
from test_v2_r11_f1 import R11Base, packed_nc, sav_bytes, xpt_bytes, petal_rows, vtt_stamp, HAVE_PANDAS  # noqa: E402
from test_v2_r11_f2 import bmp24_bottom_up, bmp8, rgb_at, PAL, idx_at, W, H  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

HAVE_PIL = importlib.util.find_spec("PIL") is not None


class R12Base(R11Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r12f1_"))

    def step1(self, path, tools=False):
        """The first print only (step 1) of a fresh look."""
        out = self.out_of(path)
        shutil.rmtree(out, ignore_errors=True)
        r = run([str(path), "--out", str(out), "--fresh"] + ([] if tools else ["--no-tools"]))
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        return r.stdout

    def raw(self, path, question, tools=False, env=None):
        r = run([str(path), "--out", str(self.out_of(path)), "--ask", question] + ([] if tools else ["--no-tools"]), env=env)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        return r.stdout


# ------------------------------------------------------------------ 1. a big .sav: the key route reads every case
class BigSav(R12Base):
    NAMES = ["hh_id", "kwh_mont", "region", "flag"]
    N = 8000

    def make(self, name="panel.sav"):
        rows = [(3_000_000 + k, round(80 + (k * 7919 % 90000) / 100, 1), 1 + k % 3, 1) for k in range(1, self.N + 1)]
        p = self.tmp / name
        p.write_bytes(sav_bytes(self.NAMES, rows))
        self.prints(p)
        return p, rows

    ENV = {"SIGMADEEPLOOK_ASK_STREAM_CAP": "2000"}

    def test_a_rounding_number_is_not_a_key_and_the_late_case_is_found(self):
        p, rows = self.make()
        target = rows[self.N - 40]   # past the 5,000th case that holds a 1 (flag is 1 in every case)
        out = self.raw(p, f"What is the kwh_mont value (1 decimal) of the household with hh_id {target[0]}?", env=self.ENV)
        self.assertIn(f"{target[1]:g}", out, out)
        self.assertNotIn("0 matching", out)

    def test_rounding_words_in_other_forms_do_not_widen_the_key_test(self):
        p, rows = self.make("panel2.sav")
        target = rows[self.N - 7]
        for q in (f'kwh_mont of hh_id "{target[0]}", to 1 decimal', f"hh_id {target[0]} kwh_mont rounded to 2 decimals", f"kwh_mont for hh_id {target[0]} with 1 digit after the point"):
            with self.subTest(q=q):
                out = self.raw(p, q, env=self.ENV)
                self.assertIn(f"{target[1]:g}", out, out)

    def test_a_keep_list_that_overflows_says_partial_never_a_confident_zero(self):
        p, rows = self.make("panel3.sav")
        out = self.raw(p, "kwh_mont of region 1", env=dict(self.ENV, SIGMADEEPLOOK_ASK_KEEP_CAP="100"))
        self.assertIn("PARTIAL", out, out)
        self.assertNotIn("Answer: 0 ", out)


# ------------------------------------------------------------------ 2. quoted numbers in a netCDF question
class QuotedNetcdf(R12Base):
    def test_quoted_indexes_parse_like_unquoted_ones(self):
        nc, raw = packed_nc()
        p = self.tmp / "gauges.nc"
        p.write_bytes(nc)
        self.prints(p)
        want = f"{raw[38][17] * 0.01 + 700.0:.2f}"
        forms = ['discharge at time index "38" and station index "17", 2 decimals',
                 "discharge at time index '38' and station index '17', 2 decimals",
                 "discharge at time index “38” and station index “17”, 2 decimals",
                 "discharge at time index `38` and station index `17`, 2 decimals",
                 "What is the 'discharge' value at the last time index (day \"38\", counting from 0) for station index \"17\"?".replace("last time index (day \"38\", counting from 0)", "time index \"38\""),
                 "discharge at time index «38», station index „17“ to 2 decimals",
                 "discharge at time index 38 and station index 17, 2 decimals"]
        for q in forms:
            with self.subTest(q=q):
                self.assertIn(want, self.raw(p, q), q)

    def test_the_last_index_with_a_quoted_station(self):
        nc, raw = packed_nc()
        p = self.tmp / "gauges_last.nc"
        p.write_bytes(nc)
        self.prints(p)
        want = f"{raw[39][17] * 0.01 + 700.0:.2f}"
        q = "What is the 'discharge' value at the last time index (day 39, counting from 0) for station index \"17\", to 2 decimals?"
        self.assertIn(want, self.raw(p, q))


# ------------------------------------------------------------------ 3. quoted pixel coordinates
class QuotedPixel(R12Base):
    SPOTS = [(0, 0), (W - 1, H - 1), (17, 23), (41, 5)]
    FORMS = ['What is the RGB colour at pixel "{x},{y}"? Give R,G,B.', "colour at pixel '{x},{y}'", "pixel “{x},{y}”", "RGB of the pixel `{x},{y}`",
             'pixel x="{x}", y="{y}"', "pixel x={x}, y={y}", "at ({x},{y})", "colour at pixel {x},{y}", "pixel ({x}, {y})", 'the pixel at "{x}","{y}"',
             "What is the RGB colour at pixel x={x}, y={y}, counted from the top-left corner of the picture as displayed? Give R,G,B."]

    def check(self, p, fn, tools=False):
        for x, y in self.SPOTS:
            for f in self.FORMS:
                q = f.format(x=x, y=y)
                with self.subTest(file=p.name, q=q):
                    r, g, b = fn(x, y)
                    out = self.raw(p, q, tools=tools)
                    self.assertIn(f"Answer: {r},{g},{b}", out, out)

    def test_bmp24_bottom_up(self):
        p = self.tmp / "bu24.bmp"
        p.write_bytes(bmp24_bottom_up())
        self.check(p, rgb_at)

    def test_bmp8_top_down_and_bottom_up(self):
        for top in (False, True):
            p = self.tmp / f"pal8_{int(top)}.bmp"
            p.write_bytes(bmp8(top))
            self.check(p, lambda x, y: PAL[idx_at(x, y)])

    @unittest.skipUnless(HAVE_PIL, "Pillow")
    def test_bmp24_through_pillow(self):
        p = self.tmp / "bu24p.bmp"
        p.write_bytes(bmp24_bottom_up())
        self.check(p, rgb_at, tools=True)


# ------------------------------------------------------------------ 4. step 1 says which --ask forms count rows
def ask_line(text):
    return next((x for x in text.splitlines() if x.lstrip("- ").startswith("Ask a count")), None)


class RouteLine(R12Base):
    def check(self, path, cols, tools=False, forms=("--ask", "how many")):
        text = self.step1(path, tools)
        ln = ask_line(text)
        self.assertIsNotNone(ln, "no 'Ask a count' line in step 1:\n" + text[:2500])
        for c in cols:
            self.assertIn(c, ln, ln)
        for f in forms:
            self.assertIn(f, ln, ln)
        self.assertLess(len(ln), 700, "one or two short lines")
        return ln

    def test_csv_with_and_without_a_key(self):
        p = self.tmp / "nokey.csv"
        p.write_text("size_mm,species\n" + "\n".join(f"{k % 17},{('oak', 'elm', 'ash')[k % 3]}" for k in range(80)) + "\n", encoding="utf-8")
        ln = self.check(p, ["size_mm", "species"])
        self.assertNotIn("Find one record", ln)
        q = self.tmp / "key.csv"
        q.write_text("tag,size_mm,species\n" + "\n".join(f"T{k:04d},{k % 17},{('oak', 'elm', 'ash')[k % 3]}" for k in range(80)) + "\n", encoding="utf-8")
        self.check(q, ["size_mm", "species", "tag"])

    @unittest.skipUnless(HAVE_PANDAS, "pandas reads SAS files")
    def test_sas(self):
        p = self.tmp / "petals.xpt"
        p.write_bytes(xpt_bytes("PETALS", [("OBSNO", "n", 8), ("PETALLEN", "n", 8), ("PETALWID", "n", 8), ("SPECIES", "c", 12)], petal_rows()))
        self.check(p, ["PETALLEN", "SPECIES"], tools=True)

    def test_sav(self):
        p = self.tmp / "panel.sav"
        p.write_bytes(sav_bytes(["hh_id", "region", "kwh_mont"], [(k, f"R-{k % 4}", k * 3 % 91) for k in range(1, 61)], strcols=(1,)))
        self.check(p, ["hh_id", "region", "kwh_mont"])

    def test_sqlite_with_several_tables_names_the_tables(self):
        p = self.tmp / "multi.gpkg"
        p.unlink(missing_ok=True)
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE land_parcels (fid INTEGER PRIMARY KEY, parcel_no TEXT, land_use TEXT, area_m2 REAL)")
        con.execute("CREATE TABLE owners (id INTEGER PRIMARY KEY, full_name TEXT, share_pct REAL)")
        con.executemany("INSERT INTO land_parcels VALUES (?,?,?,?)", [(k, f"K{k:05d}", ("vineyard", "forest", "arable")[k % 3], k * 3.5) for k in range(1, 301)])
        con.executemany("INSERT INTO owners VALUES (?,?,?)", [(k, f"Owner {k}", k % 100) for k in range(1, 201)])
        con.commit()
        con.close()
        self.check(p, ["land_parcels", "land_use", "area_m2", "owners", "share_pct"])

    def test_worksheet_jsonl_and_cues(self):
        rows = [["order_id", "region", "total"]] + [[f"B-{1000 + i}", ("north", "south", "east")[i % 3], 10 + i * 3 % 97] for i in range(1, 61)]
        p = self.tmp / "orders.xlsb"
        p.write_bytes(xlsb_bytes([("Orders", 0, rows)], sorted({v for r in rows for v in r if isinstance(v, str)})))
        self.check(p, ["order_id", "region", "total"])
        recs = [{"ticket": f"T-{k:04d}", "who": f"user{k % 9}", "minutes": k * 7 % 90} for k in range(1, 81)]
        q = self.tmp / "tickets.jsonl"
        q.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
        self.check(q, ["ticket", "who", "minutes"])
        s = self.tmp / "talk.sbv"
        s.write_bytes(cue_file("sbv")[0])
        self.check(s, ["cues", "word"], forms=("--ask", "how many"))


# ------------------------------------------------------------------ 5. a word in cue text is a filter; no filter -> refuse
WORDS = ["riego", "Riego", "riegos", "el riego, hoy", "sin riego.", "RIEGO", "regar", "riegoá"]


def cue_text(k):
    """-> (lines, hit) where hit is True when the cue holds the whole word riego in lower case."""
    if k % 7 == 0:
        return [f"Primera linea {k}", f"hay {WORDS[3]} aqui"], True
    if k % 11 == 0:
        return [f"Cue {k}: {WORDS[1]} de la huerta"], False
    if k % 13 == 0:
        return [f"Cue {k}: los {WORDS[2]} nuevos"], False
    if k % 17 == 0:
        return [f"Cue {k}: {WORDS[5]} total", f"y mas {WORDS[4]}"], True
    if k % 19 == 0:
        return [f"Cue {k}: {WORDS[7]} extra"], False
    return [f"Cue {k}: plantas y {WORDS[6]} el jardin"], False


def cue_file(kind, n=160):
    cs = [(2 + k * 4.5, 2 + k * 4.5 + 3.2, *cue_text(k)) for k in range(1, n + 1)]
    if kind == "sbv":
        txt = "\n".join(f"{sbv_stamp(a)},{sbv_stamp(b)}\n" + "\n".join(ls) + "\n" for a, b, ls, _ in cs)
    elif kind == "srt":
        txt = "\n".join(f"{k}\n{vtt_stamp(a).replace('.', ',')} --> {vtt_stamp(b).replace('.', ',')}\n" + "\n".join(ls) + "\n" for k, (a, b, ls, _) in enumerate(cs, 1))
    else:
        txt = "WEBVTT\n\n" + "\n".join(f"{vtt_stamp(a)} --> {vtt_stamp(b)}\n" + "\n".join(ls) + "\n" for a, b, ls, _ in cs)
    return txt.encode("utf-8"), cs


def count_riego(cs, ignore_case=False):
    rx = re.compile(r"(?<!\w)riego(?!\w)", re.I if ignore_case else 0)
    return sum(1 for *_, ls, _ in cs if any(rx.search(x) for x in ls))


class WordInCues(R12Base):
    def test_whole_word_case_as_written_in_sbv_srt_vtt(self):
        for kind in ("sbv", "srt", "vtt"):
            data, cs = cue_file(kind)
            p = self.tmp / f"huerta.{kind}"
            p.write_bytes(data)
            self.prints(p)
            want = count_riego(cs)
            self.assertNotEqual(want, count_riego(cs, True), "the fixture must tell the cases apart")
            for q in ("How many cues contain the word 'riego' (lower case)?", 'how many cues contain the word "riego"', "How many cues contain the word riego?",
                      "Count the cues that mention the word 'riego'", "number of cues containing the phrase 'riego'"):
                with self.subTest(kind=kind, q=q):
                    out = self.raw(p, q)
                    ans = next(x for x in out.splitlines() if x.startswith("Answer"))
                    self.assertTrue(re.match(rf"Answer: {want} cue", ans), ans + "\n" + out[:800])
                    self.assertNotIn("every row", out)

    def test_ignoring_case_is_honoured_when_asked(self):
        data, cs = cue_file("sbv")
        p = self.tmp / "huerta_ic.sbv"
        p.write_bytes(data)
        self.prints(p)
        out = self.raw(p, "How many cues contain the word 'riego', ignoring case?")
        self.assertRegex(out, rf"Answer: {count_riego(cs, True)} cue")

    def test_a_plain_cue_count_still_answers(self):
        data, cs = cue_file("sbv")
        p = self.tmp / "huerta_all.sbv"
        p.write_bytes(data)
        self.prints(p)
        out = self.raw(p, "How many cues are there in the file?")
        self.assertTrue(answer_has(out, len(cs)), out)
        self.assertNotIn("no filter matched", out)

    def test_a_cue_number_lookup_still_works(self):
        data, cs = cue_file("sbv")
        p = self.tmp / "huerta_n.sbv"
        p.write_bytes(data)
        self.prints(p)
        self.assertIn(cs[41][2][0], self.raw(p, "first line of cue number 42"))


def answer_has(out, n):
    """True when the first Answer line holds the number n as a whole number (1,240 or 1240)."""
    ans = next((x for x in out.splitlines() if x.startswith("Answer")), "")
    return any(t.replace(",", "") == str(n) for t in re.findall(r"\d[\d,]*", ans))


def no_total_answer(testcase, out, total):
    """The output refuses (no filter matched, or no table answers) and gives no 'Answer: <total> ...' figure."""
    testcase.assertTrue("no filter matched" in out or "No table answers this exactly" in out, out)
    testcase.assertNotRegex(out, rf"Answer: {total:,}\b", out)
    testcase.assertNotRegex(out, rf"Answer: {total}\b", out)


class RefuseWithoutFilter(R12Base):
    def tables(self):
        csvp = self.tmp / "orders.csv"
        csvp.write_text("order_id,region,qty\n" + "\n".join(f"A{k:04d},{('north', 'south', 'east')[k % 3]},{k % 9 + 1}" for k in range(1, 121)) + "\n", encoding="utf-8")
        jl = self.tmp / "orders.jsonl"
        jl.write_text("\n".join(json.dumps({"order": f"A{k:04d}", "region": ("north", "south", "east")[k % 3], "qty": k % 9 + 1}) for k in range(1, 121)) + "\n", encoding="utf-8")
        db = self.tmp / "orders.sqlite"
        db.unlink(missing_ok=True)
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, qty INTEGER)")
        con.executemany("INSERT INTO orders VALUES (?,?,?)", [(k, ("north", "south", "east")[k % 3], k % 9 + 1) for k in range(1, 121)])
        con.commit()
        con.close()
        sav = self.tmp / "orders.sav"
        sav.write_bytes(sav_bytes(["order_id", "qty"], [(k, k % 9 + 1) for k in range(1, 121)]))
        return [csvp, jl, db, sav]

    def test_a_count_with_an_unmatched_condition_refuses_on_every_table_path(self):
        for p in self.tables():
            self.prints(p)
            for q in ("How many orders were shipped late?", "how many rows are damaged", "How many orders contain the word 'urgent'?" if p.suffix == ".sav" else "How many orders were cancelled by the client?"):
                with self.subTest(file=p.name, q=q):
                    no_total_answer(self, self.raw(p, q), 120)

    def test_a_plain_whole_table_count_still_answers(self):
        for p in self.tables():
            self.prints(p)
            for q in ("How many orders are there in the file?", "How many orders?"):
                with self.subTest(file=p.name, q=q):
                    out = self.raw(p, q)
                    self.assertTrue(answer_has(out, 120), out)
                    self.assertNotIn("no filter matched", out)

    def test_a_filtered_count_still_answers(self):
        csvp = self.tmp / "orders_f.csv"
        csvp.write_text("order_id,region,qty\n" + "\n".join(f"A{k:04d},{('north', 'south', 'east')[k % 3]},{k % 9 + 1}" for k in range(1, 121)) + "\n", encoding="utf-8")
        self.prints(csvp)
        want = sum(1 for k in range(1, 121) if ('north', 'south', 'east')[k % 3] == "south")
        self.assertRegex(self.raw(csvp, "How many orders are in region south?"), rf"Answer: {want} ")
        want = sum(1 for k in range(1, 121) if k % 9 + 1 > 6)
        self.assertRegex(self.raw(csvp, "How many orders have qty over 6?"), rf"Answer: {want} ")

    def test_a_word_filter_over_a_text_column_gives_an_honest_zero(self):
        p = self.tmp / "notes.csv"
        p.write_text("order_id,note" + chr(10) + chr(10).join(f"A{k:04d},{'rush job' if k % 10 == 0 else 'normal'}" for k in range(1, 101)) + chr(10), encoding="utf-8")
        self.prints(p)
        self.assertRegex(self.raw(p, "How many orders contain the word 'rush'?"), r"Answer: 10 ")
        self.assertRegex(self.raw(p, "How many orders contain the word 'urgent'?"), r"Answer: 0 ")

    def test_a_column_called_word_count_is_not_a_word_filter(self):
        p = self.tmp / "essays.csv"
        p.write_text("essay_id,word_count" + chr(10) + chr(10).join(f"E{k:03d},{k * 7 % 50}" for k in range(1, 81)) + chr(10), encoding="utf-8")
        self.prints(p)
        want = sum(1 for k in range(1, 81) if k * 7 % 50 > 20)
        out = self.raw(p, "How many rows with word count over 20?")
        self.assertTrue(answer_has(out, want), out)

    def test_the_refusal_lists_what_it_can_do(self):
        p = self.tmp / "orders_r.csv"
        p.write_text("order_id,region,qty\n" + "\n".join(f"A{k:04d},{('north', 'south', 'east')[k % 3]},{k % 9 + 1}" for k in range(1, 121)) + "\n", encoding="utf-8")
        self.prints(p)
        out = self.raw(p, "How many orders were shipped late?")
        self.assertIn("region", out)
        self.assertIn("qty", out)
        self.assertIn("contain the word", out)


# ------------------------------------------------------------------ 6. the table the question names wins
class NamedTable(R12Base):
    def gpkg(self):
        p = self.tmp / "layers.gpkg"
        p.unlink(missing_ok=True)
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT, srs_id INTEGER)")
        con.execute("CREATE TABLE gpkg_ogr_contents (table_name TEXT PRIMARY KEY, feature_count INTEGER)")
        con.execute("CREATE TABLE land_parcels (fid INTEGER PRIMARY KEY, parcel_no TEXT, land_use TEXT)")
        con.executemany("INSERT INTO gpkg_contents VALUES (?,?,?,?)", [("land_parcels", "features", "parcels", 3035), ("owners", "attributes", "owners", 0), ("road_edges", "features", "roads", 3035),
                                                                      ("survey_marks", "features", "marks", 3035), ("water_bodies", "features", "water", 3035), ("ortho", "tiles", "ortho", 3035)])
        con.executemany("INSERT INTO gpkg_ogr_contents VALUES (?,?)", [("land_parcels", 11500), ("road_edges", 36000), ("survey_marks", 4800), ("water_bodies", 2400), ("owners", 13000)])
        con.executemany("INSERT INTO land_parcels VALUES (?,?,?)", [(k, f"K{k:05d}", ("vineyard", "forest", "arable")[k % 3]) for k in range(1, 301)])
        con.commit()
        con.close()
        self.prints(p)
        return p

    def test_a_question_that_names_gpkg_contents_is_answered_from_it(self):
        p = self.gpkg()
        for q in ("How many feature layers does the GeoPackage list in its gpkg_contents table? (Rows with data_type 'features'.)",
                  "How many rows of gpkg_contents have data_type 'features'?", "Count the rows in gpkg_contents where data_type = features",
                  "In gpkg_contents, how many rows have data_type 'features'?"):
            with self.subTest(q=q):
                out = self.raw(p, q)
                self.assertIn("SQLite table gpkg_contents", out, out)
                self.assertRegex(out, r"Answer: 4 ", out)

    def test_a_decoy_with_matching_column_words_does_not_win_over_the_named_table(self):
        p = self.gpkg()
        out = self.raw(p, "How many feature layers are listed in gpkg_contents?")
        self.assertNotIn("feature_count", out.split("Other tables")[0], out)
        self.assertNotRegex(out, r"Answer: sum of", out)

    def test_a_table_name_inside_a_longer_name_is_not_a_hit(self):
        p = self.gpkg()
        out = self.raw(p, "How many parcels have land_use = 'vineyard'?")
        want = sum(1 for k in range(1, 301) if k % 3 == 0)
        self.assertRegex(out, rf"Answer: {want} ", out)


if __name__ == "__main__":
    unittest.main()
