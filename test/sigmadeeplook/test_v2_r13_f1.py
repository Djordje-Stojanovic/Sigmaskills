"""Fix round 13, lane F1 (ticket 83, P0.14b.H5 gate): the routes the print advertises must work, on fixtures built here (none from a held-out set).

Gate method v2: an agent reads the print, then may run ONE `--ask` per question when the print shows the answer needs a count or a lookup.
So every `--ask` form a print shows has to work, and the engine has to answer the forms people write.

Three causes, each tested at the cause and never at a file name, value or question text:
1. `Find one record: ... ask "<measure> of <key value>"`: a bare number that lies in the range of a unique key column is a lookup on that
   column ("cost_eur of 7512345"). The printed example now names the file's real columns and a real key, and that exact text is run here;
2. "in how many paragraphs / lines / pages / slides / cues does the word 'X' appear? (Each table cell counts as its own paragraph.)" is a text
   count: words inside a bracketed aside do not send it to the table route;
3. a sweep over every family: each `--ask` text the step 1 print advertises (Ask a count, Find one record, Ask a pixel), filled with real
   names and values, returns a real answer: no refusal, no "No table answers".
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import json
import re
import sqlite3
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r8b import xlsb_bytes  # noqa: E402
from test_v2_r11_f1 import (HAVE_PANDAS, catalogue, mo_bytes, packed_nc, petal_rows, po_text, properties_text, sav_bytes, xpt_bytes)  # noqa: E402
from test_v2_r11_f2 import bmp24_bottom_up  # noqa: E402
from test_v2_r11_f3 import docx_file, wp, FX  # noqa: E402
from test_v2_r12_f1 import R12Base, count_riego, cue_file  # noqa: E402
from r5_fixtures import ODF_NS, odf_zip  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

STREAM = {"SIGMADEEPLOOK_ASK_STREAM_CAP": "2000"}   # a source over 2,000 cells is searched for the key, not held whole


def fill_form(tc, form, fills):
    """An advertised form with its placeholders (`<name>`, and the single capitals N, M, X, Y) replaced by real values; none may be left."""
    out = form
    for ph, v in fills.items():
        for one in (v if isinstance(v, list) else [v]):   # a list fills the same placeholder one after the other
            out = out.replace(ph, one, 1) if ph.startswith("<") else re.sub(rf"(?<![\w<]){ph}(?![\w>])", one, out, count=1)
        if not isinstance(v, list):
            out = out.replace(ph, v) if ph.startswith("<") else re.sub(rf"(?<![\w<]){ph}(?![\w>])", v, out)
    tc.assertNotRegex(out, r"<[^>]+>", f"an advertised placeholder nobody filled: {form}")
    tc.assertNotRegex(out, r"(?<![\w<])[NMXY](?![\w>])", f"an advertised capital placeholder nobody filled: {form}")
    return out


class R13Base(R12Base):
    def advertised(self, text):
        """Every double-quoted `--ask` text of the 'Find one record', 'Ask a count' and 'Ask a pixel' lines of a print -> [(line name, text)]."""
        out = []
        for ln in text.splitlines():
            name = next((n for n in ("Find one record", "Ask a count", "Ask a pixel") if ln.lstrip("- ").startswith(n)), None)
            if name:
                out += [(name, m) for m in re.findall(r'"([^"]+)"', ln)]
        return out

    def answer_line(self, out):
        return next((x for x in out.splitlines() if x.startswith("Answer")), "")

    def real_answer(self, out, what=""):
        """The output holds a real `Answer:` line: no refusal, no 'No table answers', no PARTIAL."""
        ans = self.answer_line(out)
        self.assertTrue(ans, f"no Answer line for {what}:\n{out[:1200]}")
        self.assertNotIn("not answered", ans, out[:1200])
        self.assertNotIn("No table answers", out, out[:1200])
        self.assertNotIn("PARTIAL", out, out[:1200])
        return ans


# ------------------------------------------------------------------ the table-like families (a unique key column and a measure)
def table_of(cols, rows, keyidx=0):
    """{key text: {column: value text}} of the rows a fixture wrote: the expected figures, worked out from the data and never read back from the look."""
    return {str(r[keyidx]): {c: (f"{v:g}" if isinstance(v, float) else str(v)) for c, v in zip(cols, r)} for r in rows}


def csv_rows():
    return [(4_100_000 + k, round(10 + (k * 37 % 9000) / 100, 2), 18 + k % 60, ("oak", "elm", "ash")[k % 3]) for k in range(1, 91)]


class Families(R13Base):
    """One method per family -> dict(path, tools, env, key, measure, keys {key text: measure text}, fills {placeholder: value})."""

    def csv(self):
        rows = csv_rows()
        p = self.tmp / "trees.csv"
        p.write_text("case_no,cost_eur,age,species\n" + "\n".join(f"{a},{b},{c},{d}" for a, b, c, d in rows) + "\n", encoding="utf-8")
        return dict(path=p, key="case_no", measure="cost_eur", vals=table_of(["case_no", "cost_eur", "age", "species"], rows), fills={"N": "50", "<value>": "oak"})

    def titled_txt(self):
        """A tab-separated table under a title block, numeric key, Latin letters."""
        rows = [(610_000 + k, round(18.5 + (k * 37 % 4000) / 10, 1), ("north", "south", "east")[k % 3]) for k in range(1, 71)]
        head = ["MILK INTAKE LOG", "Station 3, scale 7", "Period: 2025-03", "", ""]
        lines = head + ["\t".join(("lot_no", "volume_l", "route"))] + ["\t".join(str(x) for x in r) for r in rows] + ["", "Records: 70"]
        p = self.tmp / "intake.txt"
        p.write_bytes("\r\n".join(lines).encode("utf-8"))
        return dict(path=p, key="lot_no", measure="volume_l", vals=table_of(["lot_no", "volume_l", "route"], rows), fills={"N": "100", "<value>": "south"})

    def sav_rows(self, n):
        return [(7_000_000 + k, f"CL-{k % 40:04d}", 18 + k % 70, round(5 + (k * 13 % 40000) / 100, 2)) for k in range(1, n + 1)]

    def sav(self, n=300, env=None, name="visits.sav"):
        rows = self.sav_rows(n)
        p = self.tmp / name
        p.write_bytes(sav_bytes(["pt_id", "clinic", "age", "cost_eur"], rows, strcols=(1,)))
        return dict(path=p, env=env, key="pt_id", measure="cost_eur", vals=table_of(["pt_id", "clinic", "age", "cost_eur"], rows), fills={"N": "40", "<value>": "CL-0003"})

    def sav_big(self):
        return self.sav(8000, STREAM, "visits_big.sav")

    def sas(self):
        rows = petal_rows()
        p = self.tmp / "petals.xpt"
        p.write_bytes(xpt_bytes("PETALS", [("OBSNO", "n", 8), ("PETALLEN", "n", 8), ("PETALWID", "n", 8), ("SPECIES", "c", 12)], rows))
        return dict(path=p, tools=True, key="OBSNO", measure="PETALLEN", vals=table_of(["OBSNO", "PETALLEN", "PETALWID", "SPECIES"], rows), fills={"N": "3", "<value>": "setosa"})

    def stata(self):
        import pandas as pd
        rows = [(2_200_000 + k, round(1 + (k * 17 % 600) / 10, 1), ("a", "b", "c")[k % 3]) for k in range(1, 101)]
        p = self.tmp / "grades.dta"
        pd.DataFrame(rows, columns=["stud_id", "score_pts", "grp"]).to_stata(p, write_index=False)
        return dict(path=p, tools=True, key="stud_id", measure="score_pts", vals=table_of(["stud_id", "score_pts", "grp"], rows), fills={"N": "20", "<value>": "b"})

    def jsonl(self):
        recs = [{"call_no": 910_000 + k, "who": f"user{k % 9}", "minutes": round(k * 7 % 90 + 0.25, 2)} for k in range(1, 81)]
        p = self.tmp / "calls.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
        return dict(path=p, key="call_no", measure="minutes", vals=table_of(["call_no", "who", "minutes"], [(r["call_no"], r["who"], r["minutes"]) for r in recs]), fills={"N": "30", "<value>": "user3"})

    def sqlite_int(self, name="visits.sqlite"):
        p = self.tmp / name
        p.unlink(missing_ok=True)
        rows = [(k, round(100 + k * 0.37 % 900, 2), ("pillar", "bolt", "stone")[k % 3]) for k in range(1, 401)]
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE marks (mark_no INTEGER PRIMARY KEY, elevation_m REAL, kind TEXT)")
        con.executemany("INSERT INTO marks VALUES (?,?,?)", rows)
        con.commit()
        con.close()
        return dict(path=p, key="mark_no", measure="elevation_m", vals=table_of(["mark_no", "elevation_m", "kind"], rows), fills={"N": "500", "<value>": "bolt"})

    def gpkg_text(self):
        """Two tables, a text key and an integer row id in the first: the print names the text key; the row id is a unique key too."""
        p = self.tmp / "marks.gpkg"
        p.unlink(missing_ok=True)
        rows = [(k, f"SM-{k:05d}", round(100 + k * 0.37 % 900, 2), ("pillar", "bolt", "stone")[k % 3]) for k in range(1, 401)]
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE survey_marks (fid INTEGER PRIMARY KEY, mark_code TEXT, elevation_m REAL, kind TEXT)")
        con.execute("CREATE TABLE owners (id INTEGER PRIMARY KEY, full_name TEXT, share_pct REAL)")
        con.executemany("INSERT INTO survey_marks VALUES (?,?,?,?)", rows)
        con.executemany("INSERT INTO owners VALUES (?,?,?)", [(k, f"Owner {k}", k % 100) for k in range(1, 301)])
        con.commit()
        con.close()
        return dict(path=p, key="mark_code", measure="elevation_m", vals=table_of(["fid", "mark_code", "elevation_m", "kind"], rows, 1), fills={"N": "500", "<value>": "bolt"},
                    ids=table_of(["fid", "mark_code", "elevation_m", "kind"], rows))

    def xlsb(self):
        rows = [["ticket_no", "region", "total"]] + [[8_000 + i, ("north", "south", "east")[i % 3], 10 + i * 3 % 41] for i in range(1, 61)]
        strings = sorted({v for r in rows for v in r if isinstance(v, str)})
        p = self.tmp / "orders.xlsb"
        p.write_bytes(xlsb_bytes([("Orders", 0, rows)], strings))
        return dict(path=p, key="ticket_no", measure="total", vals=table_of(["ticket_no", "region", "total"], rows[1:]), fills={"N": "50", "<value>": "south"})

    ALL = ["csv", "titled_txt", "sav", "sav_big", "sas", "stata", "jsonl", "sqlite_int", "gpkg_text", "xlsb"]

    def fam(self, name):
        if name in ("sas", "stata") and not HAVE_PANDAS:
            self.skipTest("pandas reads SAS and Stata files")
        f = getattr(self, name)()
        f.setdefault("tools", False)
        f.setdefault("env", None)
        return f

    def ask(self, f, q):
        return self.raw(f["path"], q, tools=f["tools"], env=f["env"])

    def check_answer(self, f, out, key, what, measure=None, vals=None):
        measure = measure or f["measure"]
        want = (vals or f["vals"])[key][measure]
        ans = self.answer_line(out)
        self.assertRegex(ans, rf"\b{re.escape(measure)} = {re.escape(want)}\b", f"{what}\n{out[:1500]}")
        self.assertNotIn("PARTIAL", out, what)

    # ---- 1. the printed example
    def test_the_printed_find_example_runs_as_printed(self):
        for name in self.ALL:
            with self.subTest(family=name):
                f = self.fam(name)
                text = self.step1(f["path"], f["tools"])
                ln = self.find_line(text)
                m = re.search(r'ask "([^"]+)"', ln)
                self.assertIsNotNone(m, ln)
                form = m.group(1)
                self.assertNotRegex(form, r"<|>", "the printed example holds real names, not placeholders: " + ln)
                measure = form.split(" of ", 1)[0]
                key = form.rsplit(" ", 1)[1].strip("'\"")
                self.assertIn(key, f["vals"], f"the example key must be a real key: {form}")
                self.assertIn(measure, f["vals"][key], f"the example measure must be a real column: {form}")
                self.check_answer(f, self.ask(f, form), key, form, measure)

    def find_line(self, text):
        ln = next((x for x in text.splitlines() if x.lstrip("- ").startswith("Find one record")), None)
        self.assertIsNotNone(ln, "no 'Find one record' line in step 1:\n" + text[:2500])
        return ln

    # ---- 1. the form an answerer writes: the measure, "of", the bare key value
    def test_a_bare_key_value_is_a_lookup_on_the_key_column(self):
        for name in self.ALL:
            with self.subTest(family=name):
                f = self.fam(name)
                self.prints(f["path"], tools=f["tools"])
                ks = list(f["vals"])
                for key in (ks[len(ks) // 2], ks[-3], ks[0]):
                    for q in (f"{f['measure']} of {key}", f"What is the {f['measure']} of {key}?", f"{f['measure']} for {key}, to 2 decimals"):
                        with self.subTest(q=q):
                            self.check_answer(f, self.ask(f, q), key, q)

    def test_the_row_id_of_a_text_keyed_table_is_a_key_too(self):
        f = self.fam("gpkg_text")
        self.prints(f["path"])
        ids = list(f["ids"])
        self.check_answer(f, self.ask(f, f"{f['measure']} of {ids[16]}"), ids[16], "row id", vals=f["ids"])
        # no wrong answer: a number that is no key of the table never turns into one row of some other column
        out = self.ask(f, f"{f['measure']} of 987654321")
        self.assertNotRegex(self.answer_line(out), rf"{f['measure']} = \d", out)

    def test_a_number_outside_the_key_range_is_not_a_record(self):
        f = self.fam("csv")
        self.prints(f["path"])
        out = self.ask(f, "cost_eur of 123")
        self.assertNotRegex(self.answer_line(out), r"cost_eur = \d", out)

    def test_a_value_of_a_column_or_a_number_that_names_no_column_is_not_a_key(self):
        f = self.fam("sqlite_int")   # keys 1 .. 400: the small numbers below lie in the key range
        self.prints(f["path"])
        for q in ("show the rows with elevation_m 22", "rows with 22 widgets", "which kind has elevation_m 22", "elevation_m 22 and kind"):
            with self.subTest(q=q):
                out = self.ask(f, q)
                self.assertNotIn("mark_no = 22", out, out)
                self.assertNotRegex(self.answer_line(out), r"elevation_m = ", out)

    def test_a_threshold_count_is_not_a_key_lookup(self):
        f = self.fam("csv")
        self.prints(f["path"])
        rows = csv_rows()
        want = sum(1 for r in rows if r[1] > 50)
        self.assertIn(f"Answer: {want} ", self.ask(f, "How many rows have cost_eur over 50?"))
        self.assertIn(f"Answer: {sum(1 for r in rows if r[2] >= 30)} ", self.ask(f, "How many rows have age at least 30?"))

    # ---- 3. the sweep: every advertised form, filled, answers
    def test_every_advertised_form_of_a_table_family_answers(self):
        for name in self.ALL:
            with self.subTest(family=name):
                f = self.fam(name)
                text = self.step1(f["path"], f["tools"])
                forms = self.advertised(text)
                self.assertTrue([1 for n, _ in forms if n == "Ask a count"], f"no Ask a count form:\n{text[:2000]}")
                for line_name, form in forms:
                    q = fill_form(self, form, f["fills"])
                    with self.subTest(line=line_name, form=form):
                        self.real_answer(self.ask(f, q), q)


# ------------------------------------------------------------------ the families that word their own forms
class OwnForms(R13Base):
    def sweep(self, path, fills, tools=False, expect_lines=("Find one record",)):
        text = self.step1(path, tools)
        forms = self.advertised(text)
        seen = {n for n, _ in forms}
        for n in expect_lines:
            self.assertIn(n, seen, f"{n!r} line has no quoted form:\n{text[:2500]}")
        for line_name, form in forms:
            q = fill_form(self, form, fills)
            with self.subTest(file=path.name, line=line_name, form=form):
                self.real_answer(self.raw(path, q, tools=tools), q)

    def test_subtitle_cues(self):
        for kind in ("sbv", "srt", "vtt"):
            data, cs = cue_file(kind)
            p = self.tmp / f"huerta.{kind}"
            p.write_bytes(data)
            with self.subTest(kind=kind):
                self.sweep(p, {"N": "42", "X": "riego"}, expect_lines=("Find one record",))

    def test_a_bare_cue_number_is_a_cue(self):
        data, cs = cue_file("srt")
        p = self.tmp / "huerta_n.srt"
        p.write_bytes(data)
        self.prints(p)
        out = self.raw(p, "first line of 42")
        self.assertIn(cs[41][2][0], self.answer_line(out), out)
        self.assertNotIn(cs[0][2][0], self.answer_line(out), out)

    def test_gettext(self):
        rows = catalogue()
        for name, data in (("da.po", po_text(rows)), ("da.mo", mo_bytes(rows))):
            p = self.tmp / name
            p.write_bytes(data)
            with self.subTest(file=name):
                self.sweep(p, {"<msgid>": "Friday", "X": "Sentence", "<value>": "fuzzy"})

    def test_properties(self):
        p = self.tmp / "mensagens.properties"
        p.write_bytes(properties_text())
        self.sweep(p, {"<key>": "menu.msg.020"})

    def test_netcdf(self):
        nc, _ = packed_nc()
        p = self.tmp / "gauges.nc"
        p.write_bytes(nc)
        self.sweep(p, {"<variable>": "discharge", "<dim>": ["time", "station"], "N": "12", "M": "3"})

    def test_pixel(self):
        p = self.tmp / "scan.bmp"
        p.write_bytes(bmp24_bottom_up())
        self.sweep(p, {"X": "17", "Y": "23"}, expect_lines=("Ask a pixel",))


# ------------------------------------------------------------------ 2. a text count with an aside about tables
Q_PAR = "In how many paragraphs does the word 'Patentjahr' appear? (Each table cell counts as its own paragraph.)"
CELLS = [["Patentjahr 3", "Jahresgebuehr"], ["Patentjahr 4", "Patentjahr 5"], ["nichts", "Patentjahr"]]   # a row with the word in two cells: two paragraphs
PARAS = ["Das Patentjahr beginnt am Tag der Anmeldung.", "Im Patentjahr 5 gilt eine neue Gebuehr.", "Patentjahre sind kein Patentjahr.", "Ohne Treffer."]
WANT_PARAS = sum(1 for t in PARAS if re.search(r"(?<!\w)Patentjahr(?!\w)", t)) + sum(1 for r in CELLS for c in r if re.search(r"(?<!\w)Patentjahr(?!\w)", c))


class ParagraphCounts(R13Base):
    def docx(self):
        p = self.tmp / "gebuehren.docx"
        tbl = "<w:tbl>" + "".join("<w:tr>" + "".join(f"<w:tc>{wp(c)}</w:tc>" for c in r) + "</w:tr>" for r in CELLS) + "</w:tbl>"
        docx_file(p, "".join(wp(t) for t in PARAS) + tbl)
        return p

    def odt(self):
        p = self.tmp / "gebuehren.odt"
        tbl = "<table:table>" + "".join("<table:table-row>" + "".join(f"<table:table-cell><text:p>{c}</text:p></table:table-cell>" for c in r) + "</table:table-row>" for r in CELLS) + "</table:table>"
        body = "".join(f"<text:p>{t}</text:p>" for t in PARAS) + tbl
        content = f'<?xml version="1.0"?><office:document-content {ODF_NS}><office:body><office:text>{body}</office:text></office:body></office:document-content>'
        meta = f'<?xml version="1.0"?><office:document-meta {ODF_NS}><office:meta><dc:title>T</dc:title></office:meta></office:document-meta>'
        odf_zip(p, "application/vnd.oasis.opendocument.text", content, meta)
        return p

    def rtf(self):
        bs = chr(92)
        body = ("{@rtf1@ansi@deff0 " + "".join(t + "@par " for t in PARAS + [c for r in CELLS for c in r]) + "}").replace("@", bs)
        p = self.tmp / "gebuehren.rtf"
        p.write_bytes(body.encode("latin-1"))
        return p

    def plain(self, ext):
        p = self.tmp / f"gebuehren.{ext}"
        p.write_text("\n".join(PARAS + [c for r in CELLS for c in r]) + "\n", encoding="utf-8")
        return p

    def check(self, p, q=Q_PAR, want=WANT_PARAS, **kw):
        out = self.raw(p, q, **kw)
        self.assertRegex(self.answer_line(out), rf"Answer: {want} (paragraph|line)s? contains?\b|Answer: {want} (paragraph|line)s? contain\b", out)
        self.assertNotIn("No table answers", out)
        return out

    def test_the_aside_about_table_cells_does_not_send_the_question_to_the_table_route(self):
        self.assertEqual(WANT_PARAS, 7)
        self.check(self.docx())
        self.check(self.odt())
        self.check(self.rtf())

    def test_plain_text_files(self):
        for ext in ("txt", "md"):
            with self.subTest(ext=ext):
                self.check(self.plain(ext), "In how many lines does the word 'Patentjahr' appear? (A table row counts as one line.)", want=WANT_PARAS)

    def test_the_old_doc_format(self):
        doc = FX / "r9_report.doc"
        out = self.raw(doc, "In how many paragraphs does the word 'Part' appear? (Each table cell counts as its own paragraph.)")
        self.assertRegex(self.answer_line(out), r"Answer: 4 paragraphs contain 'Part'", out)

    def test_pptx_and_pdf_by_unit(self):
        import zipfile
        P_ = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        p = self.tmp / "deck.pptx"
        texts = ["Canada and Mexico", "Canada-Mexico trade", "nothing", "canada in lower case", "CANADA", "Canada again"]
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
            z.writestr("ppt/presentation.xml", f'<?xml version="1.0"?><p:presentation {P_}/>')
            for i, t in enumerate(texts, 1):
                z.writestr(f"ppt/slides/slide{i}.xml", f'<?xml version="1.0"?><p:sld {P_}><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{t}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
        want = sum(1 for t in texts if re.search(r"(?<!\w)Canada(?!\w)", t))
        self.assertEqual(want, 3)
        for q in ("On how many slides does the text contain 'Canada'? (Exact capitals; 'Canada-Mexico' counts.)",
                  "On how many slides does the word 'Canada' appear? (Every shape and table cell counts.)"):
            out = self.raw(p, q)
            self.assertRegex(self.answer_line(out), rf"Answer: {want} slides contain 'Canada'", out)

    def test_pdf_pages_and_paragraphs(self):
        from make_fixtures import build_pdf, stream
        pages = [["Patentjahr eins", "kein Treffer"], ["nur Text"], ["Das Patentjahr zaehlt"]]
        objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 2: b"<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R] /Count 3 >>", 9: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
        for i, lines in enumerate(pages):
            objs[3 + 2 * i] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 9 0 R >> >> /Contents {4 + 2 * i} 0 R >>".encode()
            objs[4 + 2 * i] = stream(b"", b"BT /F1 12 Tf 50 740 Td 14 TL " + b" T* ".join(b"(" + x.encode() + b") Tj" for x in lines) + b" ET\n")
        p = self.tmp / "gebuehren.pdf"
        p.write_bytes(build_pdf(objs))
        out = self.raw(p, "On how many pages does the word 'Patentjahr' appear? (A table cell counts as part of its page.)")
        self.assertRegex(self.answer_line(out), r"Answer: 2 pages contain 'Patentjahr'", out)
        out = self.raw(p, Q_PAR)
        self.assertRegex(self.answer_line(out), r"Answer: \d+ paragraphs? contains? 'Patentjahr'|Answer: \d+ paragraphs contain 'Patentjahr'", out)
        self.assertNotIn("No table answers", out)

    def test_cues_of_a_subtitle_file(self):
        for kind in ("sbv", "srt", "vtt"):
            data, cs = cue_file(kind)
            p = self.tmp / f"huerta.{kind}"
            p.write_bytes(data)
            want = count_riego(cs)
            for q in ("In how many cues does the word 'riego' appear?", "In how many cues does the word 'riego' appear? (Each table row of the file is one cue.)",
                      'On how many cues does the word "riego" show up?'):
                with self.subTest(kind=kind, q=q):
                    self.assertRegex(self.answer_line(self.raw(p, q)), rf"Answer: {want} cue", q)

    def test_the_occurrence_form_with_an_aside(self):
        out = self.raw(self.docx(), "How many times does the word 'Patentjahr' appear in the text? (Table cells count too.)")
        self.assertRegex(self.answer_line(out), r"Answer: 7 whole-word occurrences of 'Patentjahr'", out)

    def test_a_question_about_a_column_is_still_a_table_question(self):
        p = self.tmp / "cities.csv"
        p.write_text("city,country\n" + "\n".join(f"{c},X{k}" for k, c in enumerate(["Paris"] * 3 + ["Rome"] * 4)) + "\n", encoding="utf-8")
        out = self.raw(p, "How many rows contain the word 'Paris' in the city column?")
        self.assertRegex(self.answer_line(out), r"Answer: 3 ", out)
        import dl_wordcount as W
        self.assertIsNone(W.parse("How many times does 'Paris' appear in the city column?"))
        self.assertIsNone(W.parse("How many rows contain 'Paris' (in the table)?"))


if __name__ == "__main__":
    unittest.main()
