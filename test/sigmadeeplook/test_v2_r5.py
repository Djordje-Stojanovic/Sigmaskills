"""Fix round 5: the 12 generic failure categories, on fixtures built here (r5_fixtures.py) with answers worked out independently.

Each test reads step 1 (what a reader sees first) or the whole stored stream, and checks the exact figures against the truth.
--no-tools wherever the fact must come from the standard library; tool-gated tests skip when the tool is missing.
"""
import importlib.util
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
import r5_fixtures as F  # noqa: E402
from test_v2 import SCRIPTS, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import dl_asr  # noqa: E402
import dl_prof as P  # noqa: E402

TIMES = {}


def have(mod):
    return importlib.util.find_spec(mod) is not None


class R5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r5_"))
        cls.fx = cls.tmp / "fx"
        cls.fx.mkdir()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        if TIMES:
            print("\nfirst-print seconds: " + ", ".join(f"{k} {v:.1f}" for k, v in sorted(TIMES.items())), file=sys.stderr)

    def look(self, builder, *extra, tools=False):
        p, truth = builder(self.fx)
        out = self.tmp / ("out_" + p.name + ("_t" if tools else ""))
        t0 = time.time()
        r = run([str(p), "--out", str(out), *([] if tools else ["--no-tools"]), *extra])
        TIMES[p.name] = time.time() - t0
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        stream = "\n".join(x["text"] for x in lj["stream"])
        return r.stdout, lj, stream, truth, p, out

    def ask(self, p, out, q, tools=False):
        r = run([str(p), "--out", str(out), *([] if tools else ["--no-tools"]), "--ask", q])
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return r.stdout

    # ------------------------------------------------------------ 1. delimited text
    def test_cp1252_semicolon_decimal_comma(self):
        out, lj, stream, t, p, o = self.look(F.csv_semicolon_cp1252)
        self.assertIn("encoding cp1252, delimiter semicolon", out)
        self.assertIn("decimal comma in Betrag", out)
        self.assertIn(f"sum {P.fmt(t['sum_amount'])}", out)
        self.assertIn(f"max {P.fmt(t['max_amount'])} (line {t['max_line']})", out)
        self.assertIn(f"data rows {t['rows']}", out)
        a = self.ask(p, o, "What is the total Betrag in Wien?")
        rows = [r for r in F.semicolon_rows(t["rows"], 51)[1] if r[1] == "Wien"]
        want = round(sum(float(r[2].replace(".", "").replace(",", ".")) for r in rows), 2)
        self.assertIn(f"Answer: sum of Betrag = {P.fmt(want)}", a)
        self.assertIn(f"-> {len(rows)} lines", a)

    def test_utf16_tab(self):
        out, lj, stream, t, p, o = self.look(F.tsv_utf16)
        self.assertIn("delimiter tab", out)
        self.assertIn("utf-16", out)
        self.assertIn(f"sum {P.fmt(t['sum_amount'])}", out)

    def test_csv_gz_unwrapped(self):
        out, lj, stream, t, p, o = self.look(F.csv_gz)
        self.assertIn("One gzip member, werte.csv", out)
        self.assertIn(f"data rows {t['rows']}", out)
        self.assertIn(f"sum {P.fmt(t['sum_amount'])}", stream)
        a = self.ask(p, o, "How many rows per Stadt?")
        for city, n in t["city_counts"].items():
            self.assertIn(f"{city} {n}", a)

    # ------------------------------------------------------------ 2. nested JSON
    def test_nested_json_paths(self):
        out, lj, stream, t, p, o = self.look(F.nested_json)
        self.assertIn(f"regions[].stores[].orders[].items[] {t['items']} records", out)
        self.assertIn(t["max_price_path"], stream)
        self.assertIn(f"sum {P.fmt(t['sum_qty'])}", stream)
        a = self.ask(p, o, "What is the total qty of items?")
        self.assertIn(f"Answer: sum of qty = {P.fmt(t['sum_qty'])} over {t['items']} numbers", a)
        a = self.ask(p, o, "How many orders are cancelled?")
        self.assertIn(f"Answer: {t['cancelled']} records match", a)

    # ------------------------------------------------------------ 3. pcap
    def test_pcap_and_pcapng(self):
        for b in (F.pcap_file, F.pcapng_file):
            out, lj, stream, t, p, o = self.look(b)
            c = lj["facts"]["counts"]
            self.assertEqual(c["packets"], t["packets"])
            self.assertEqual(c["DNS queries"], t["dns_queries"])
            self.assertIn(f"TCP {t['tcp']}", out)
            self.assertIn(f"UDP {t['udp']}", out)
            self.assertIn(f"ICMP {t['icmp']}", out)
            self.assertIn(t["sni"], out)
            for n in t["dns_names"]:
                self.assertIn(n, stream)
        a = self.ask(p, o, "How many DNS queries?")
        self.assertIn(f"Answer: DNS queries {t['dns_queries']}", a)

    # ------------------------------------------------------------ 4. INI
    def test_ini_complete(self):
        out, lj, stream, t, p, o = self.look(F.ini_file)
        self.assertIn(f"sections {len(t['sections'])}; keys {t['total']}", out)
        for s, kv in t["values"].items():
            for k, v in kv.items():
                if k == "password":
                    self.assertNotIn(v, out)
                    continue
                self.assertIn(f"{k} = {v}", out)
        a = self.ask(p, o, "What is the port of the database?")
        self.assertIn("value = 5432", a)

    def test_properties(self):
        out, lj, stream, t, p, o = self.look(F.properties_file)
        self.assertIn(f"keys {t['keys']}", out)
        self.assertIn("app.version = 4.2.0", out)

    # ------------------------------------------------------------ 5. documents
    def test_docx_structure_first(self):
        out, lj, stream, t, p, o = self.look(F.docx_rich)
        self.assertIn(f"{t['h1'] + t['h2']} headings", out)
        self.assertIn(f"Tracked changes: {t['insertions'] + t['deletions']} ({t['insertions']} insertions, {t['deletions']} deletions)", out)
        self.assertIn(f"Comments ({t['comments']}; by Lena Ortiz 1, Tom Reyes 1)", out)

    def test_odt(self):
        out, lj, stream, t, p, o = self.look(F.odt_file)
        c = lj["facts"]["counts"]
        self.assertEqual(c["comments"], t["comments"])
        self.assertEqual(c["tracked changes"], t["changes"])
        self.assertIn("TRACKED-CHANGES", out)

    def test_epub_chapters(self):
        out, lj, stream, t, p, o = self.look(F.epub_file)
        self.assertIn(f"chapters (body documents, front and back matter left out) {t['chapters']}", out)
        self.assertIn(f"longest chapter {t['longest']}", out)
        self.assertIn(t["title"], out)

    # ------------------------------------------------------------ 6. calendar, track, geo
    def test_ics(self):
        out, lj, stream, t, p, o = self.look(F.ics_file)
        self.assertIn(f"events {t['events']}; recurring events {t['recurring']}; occurrences (bounded rules expanded) {t['occurrences']}", out)
        self.assertIn(f"cancelled {t['cancelled']}", out)
        a = self.ask(p, o, "How many events are cancelled?")
        self.assertIn("cancelled 1", a)

    def test_gpx(self):
        out, lj, stream, t, p, o = self.look(F.gpx_file)
        self.assertIn(f"distance {t['distance_km']:.3f} km", out)
        m, s = divmod(t["moving_s"], 60)
        self.assertIn(f"moving 0:{m:02d}:{s:02d}", out)

    def test_geojson(self):
        out, lj, stream, t, p, o = self.look(F.geojson_file)
        self.assertIn(f"features {t['features']}", out)
        self.assertIn(P.fmt(t["sum_pop"]), stream)
        a = self.ask(p, o, "What is the total pop?")
        self.assertIn(f"= {P.fmt(t['sum_pop'])}", a)

    # ------------------------------------------------------------ 7. ods (images: tool-gated below)
    def test_ods(self):
        out, lj, stream, t, p, o = self.look(F.ods_file)
        self.assertIn("Orders", out)
        self.assertIn(f"sum {P.fmt(t['sum_qty'])}", stream)
        self.assertIn(f"sum {P.fmt(t['sum_total'])}", stream)

    @unittest.skipUnless(have("PIL") and (have("rapidocr_onnxruntime") or have("rapidocr") or shutil.which("tesseract")), "needs Pillow and an OCR engine")
    def test_image_text_step1(self):
        out, lj, stream, t, p, o = self.look(F.text_image, tools=True)
        self.assertIn("Text in the picture", out)
        for w in t["words"]:
            self.assertIn(w, out)

    # ------------------------------------------------------------ 8. columnar metadata
    @unittest.skipUnless(have("pyarrow"), "pyarrow writes the fixture")
    def test_parquet_kv_bare(self):
        out, lj, stream, t, p, o = self.look(F.parquet_meta)
        for k, v in t["keys"].items():
            self.assertIn(f"{k} = {v}", out)

    # ------------------------------------------------------------ 9. PDF pages
    @unittest.skipUnless(have("fitz"), "PyMuPDF reads the text layer")
    def test_pdf_page_facts(self):
        out, lj, stream, t, p, o = self.look(F.pdf_text, tools=True)
        self.assertIn(f"p{t['lease_page']}:", stream)
        self.assertIn(f"Total revenue: {t['total_revenue']}", stream)
        self.assertIn(f"Revenue {t['total_revenue']}", stream)   # the column sum, computed and labelled as computed
        a = self.ask(p, o, "What is the total revenue?", tools=True)
        self.assertIn(f"Answer: sum of Revenue = {t['total_revenue']}", a)
        self.assertIn(f"Total revenue: {t['total_revenue']}", a)

    # ------------------------------------------------------------ 10. spreadsheet formulas and per-sheet facts
    def test_xlsx_formulas_and_totals(self):
        out, lj, stream, t, p, o = self.look(F.xlsx_formulas)
        for name, s in t["sheets"].items():
            self.assertIn(f"Formulas on {name} ({s['formulas']} cells", out)
            self.assertIn(f"-> {s['total']}", out)
            self.assertIn(f"Total rows on {name}", out)
            self.assertIn(f"max {P.fmt(s['max_pay'])}", out)
            self.assertIn(f"sum {P.fmt(s['total'])}, mean", out)   # the data rows only: the total row is not counted twice
            a = self.ask(p, o, f"What is the total pay on {name}?")
            self.assertIn(f"Answer: sum of Pay = {P.fmt(s['total'])}", a)

    # ------------------------------------------------------------ 11. ASR names
    def test_asr_uncertain_names(self):
        def seg(st, ws):
            return {"start": st, "end": st + 3, "text": " ".join(w for w, _ in ws),
                    "words": [{"w": w, "s": st + i * 0.3, "e": st + i * 0.3 + 0.2, "p": q} for i, (w, q) in enumerate(ws)]}
        segs = [seg(0, [("Today", .9), ("we", .9), ("met", .9), ("Kathryn", .41), ("Szabo", .35), ("in", .9), ("Vienna.", .95)]),
                seg(4, [("Then", .9), ("Catherine", .88), ("said", .9), ("hello.", .9)]),
                seg(8, [("The", .9), ("team", .9), ("thanked", .9), ("Mr.", .9), ("Szabo.", .92)])]
        r = dl_asr.name_report(segs)
        self.assertEqual(r["marked"][0], "Today we met Kathryn(?) Szabo(?) in Vienna.")
        names = {u[0]: u for u in r["uncertain"]}
        self.assertEqual(set(names), {"Kathryn", "Szabo"})
        self.assertEqual([a[0] for a in names["Kathryn"][3]], ["Catherine"])
        self.assertEqual(names["Szabo"][4][1], 0.92)
        self.assertNotIn("Vienna", names)   # heard clearly: not marked
        self.assertNotIn(1, r["marked"])
        self.assertEqual(dl_asr.phonetic_key("Jon"), dl_asr.phonetic_key("John"))
        self.assertTrue(any({"Kathryn", "Catherine"} <= set(g) for g in r["variants"]))

    # ------------------------------------------------------------ 12. step 1 order
    def test_step1_counts_before_note(self):
        out, lj, stream, t, p, o = self.look(F.ini_file)
        self.assertLess(out.index("Counts: sections"), out.index("Small text file"))

    def test_first_print_times(self):
        for b in (F.csv_semicolon_cp1252, F.nested_json, F.pcap_file, F.ics_file, F.gpx_file, F.xlsx_formulas):
            self.look(b)
        slow = {k: v for k, v in TIMES.items() if v > 20}
        self.assertFalse(slow, slow)


if __name__ == "__main__":
    unittest.main()
