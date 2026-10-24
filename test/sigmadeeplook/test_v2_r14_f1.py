"""Fix round 14, lane F1 (ticket 83, P0.14b.H5 gate): four causes from held-out set 13, on fixtures built here (none from a held-out set).

Each cause is tested at the cause and never at a file name, value or question text:
1. a paged fixed-width text report (title block and header repeated on every page, a rule line of dashes that marks the columns, form feeds, a
   page marker, a totals block, comma decimals) is read as a table: `--ask` counts over a threshold and finds one record by its code;
   a pure aligned block without a rule line is read too, prose and decoration are not;
2. gettext .mo / .po and every other table: the unit noun ("messages", "cases") is never a value filter; "have a <column>" counts non-empty cells;
   "longer than N bytes / characters" counts by text length (a .mo counts the original as the file stores it: context, msgid, plural);
3. a scope word is honoured: "speaker notes" counts notes only, "slide text" slide text only, "title" titles only (pptx and odp), a scope the
   file cannot give is refused; step 1 names the last slide and `--ask` answers "title of the last slide / slide N";
4. a netCDF char variable: "how many entries of <var> are the letter 'S'" counts characters (says so), a multi-character target counts entries.
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import re
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r10_f2 import nc_file  # noqa: E402
from test_v2_r11_f1 import mo_bytes, po_text  # noqa: E402
from test_v2_r11_f3 import OD, REL_NS  # noqa: E402
from test_v2_r12_f1 import R12Base, ask_line  # noqa: E402
from r5_fixtures import odf_zip  # noqa: E402

sys.path.insert(0, str(SCRIPTS))


class R14Base(R12Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r14f1_"))

    def answer_of(self, path, question, tools=False, env=None):
        out = self.raw(path, question, tools=tools, env=env)
        line = next((x for x in out.splitlines() if x.startswith("Answer")), None)
        self.assertIsNotNone(line, "no Answer line:\n" + out[:1500])
        return line, out


# ------------------------------------------------------------------ 1. a paged fixed-width report
COLS = [("Код", 9, "l"), ("Дата", 10, "l"), ("Участок", 18, "l"), ("Тариф", 6, "l"), ("Показание", 10, "r"), ("Расход", 8, "r"), ("Сумма", 9, "r"), ("Статус", 10, "l")]
PLACES = ["Лесная, дом 15", "Школьная, дом 2", "Заречная, дом 4", "Кооператив «Заря»"]


def report_rows(n=45):
    rows = []
    for k in range(1, n + 1):
        use = (k * 37) % 600
        rows.append([f"ЭС-{k:04d}", f"{(k % 28) + 1:02d}.11.2025", PLACES[k % 4], ("ночь", "день", "сутки")[k % 3], str(1000 + (k * 7919) % 90000), str(use),
                     f"{(k * 53) % 9000 / 100:.2f}".replace(".", ","), "перерасход" if use > 500 else "норма"])
    return rows


def cell(v, w, al):
    return v.ljust(w) if al == "l" else v.rjust(w)


def report_bytes(rows, per_page=20, rule=True, enc="cp1251", footer=False):
    lines = []
    pages = [rows[i:i + per_page] for i in range(0, len(rows), per_page)]
    for no, page in enumerate(pages, 1):
        if no > 1:
            lines.append("\f")
        lines.append("ВЕДОМОСТЬ ПОКАЗАНИЙ СЧЁТЧИКОВ".ljust(60) + f"Стр. {no} из {len(pages)}")
        lines.append("Район: Северный, ноябрь 2025 г. (тест)")
        lines.append("")
        lines.append("  ".join(cell(c, w, "l" if a == "l" else "r") for c, w, a in COLS))
        if rule:
            lines.append("  ".join("-" * w for _, w, _ in COLS))
        for r in page:
            lines.append("  ".join(cell(v, w, a) for v, (_, w, a) in zip(r, COLS)))
        if footer:
            lines.append(f"- {no} -")
        else:
            lines.append("")
    total = sum(int(r[5]) for r in rows)
    lines += ["Итого записей: %d" % len(rows), "Суммарный расход, кВт·ч: %d" % total, "", "Контролёр: смена 2", ""]
    return "\r\n".join(lines).encode(enc)


class FixedWidthReport(R14Base):
    def make(self, name="vedomost.txt", **kw):
        rows = report_rows(kw.pop("n", 45))
        p = self.tmp / name
        p.write_bytes(report_bytes(rows, **kw))
        return p, rows

    def test_step1_names_the_table_with_its_real_columns(self):
        p, rows = self.make()
        text = self.step1(p)
        ln = next((x for x in text.splitlines() if "Find one record:" in x), None)
        self.assertIsNotNone(ln, "no 'Find one record' line:\n" + text[:2500])
        self.assertIn("45 rows", ln)
        self.assertIn("Код", ln)
        self.assertIn("ЭС-0001 .. ЭС-0045", ln)
        ac = ask_line(text)
        self.assertIsNotNone(ac, text[:2500])
        self.assertIn("Расход", ac)

    def test_a_threshold_count_leaves_out_headers_markers_and_totals(self):
        p, rows = self.make()
        self.step1(p)
        want = sum(1 for r in rows if int(r[5]) > 400)
        line, out = self.answer_of(p, "For how many records is the consumption (the 'Расход' column, in kWh) greater than 400?")
        self.assertIn(f"Answer: {want} ", line, out)
        line, out = self.answer_of(p, "How many records have Расход over 100?")
        self.assertIn(f"Answer: {sum(1 for r in rows if int(r[5]) > 100)} ", line, out)

    def test_one_record_by_its_code(self):
        p, rows = self.make()
        self.step1(p)
        for k in (17, 45, 1):
            line, out = self.answer_of(p, f"What meter reading (the 'Показание' column) is recorded for the record ЭС-{k:04d}?")
            self.assertIn(rows[k - 1][4], line, out)

    def test_comma_decimals_are_numbers(self):
        p, rows = self.make()
        self.step1(p)
        want = sum(1 for r in rows if float(r[6].replace(",", ".")) > 50)
        line, out = self.answer_of(p, "How many records have Сумма over 50?")
        self.assertIn(f"Answer: {want} ", line, out)

    def test_it_reads_the_rows_of_the_last_page_and_counts_a_status(self):
        p, rows = self.make()
        self.step1(p)
        want = sum(1 for r in rows if r[7] == "перерасход")
        line, out = self.answer_of(p, "How many records have Статус = 'перерасход'?")
        self.assertIn(f"Answer: {want} ", line, out)

    def test_a_footer_page_marker_after_the_rows_is_not_a_row(self):
        p, rows = self.make("vedomost_footer.txt", footer=True)
        text = self.step1(p)
        self.assertIn("45 rows", next((x for x in text.splitlines() if "Find one record:" in x), text[:2000]))
        line, out = self.answer_of(p, "How many records have Расход over 400?")
        self.assertIn(f"Answer: {sum(1 for r in rows if int(r[5]) > 400)} ", line, out)

    def test_one_page_in_latin_letters_and_utf8(self):
        rows = [[f"INV-{k:03d}", f"2026-02-{k % 28 + 1:02d}", ("Oslo", "Rome", "Graz")[k % 3], f"{k * 7 % 90 + 10},{k % 10}"] for k in range(1, 26)]
        cols = [("Invoice", 9), ("Day", 11), ("City", 6), ("Amount", 8)]
        lines = ["SALES LEDGER", "", "  ".join(c.ljust(w) for c, w in cols), "  ".join("=" * w for _, w in cols)]
        lines += ["  ".join(v.ljust(w) if i < 3 else v.rjust(w) for i, (v, (_, w)) in enumerate(zip(r, cols))) for r in rows]
        lines += ["", "Total rows: 25"]
        p = self.tmp / "ledger.txt"
        p.write_bytes("\n".join(lines).encode("utf-8"))
        self.step1(p)
        want = sum(1 for r in rows if float(r[3].replace(",", ".")) > 50)
        line, out = self.answer_of(p, "How many rows have Amount over 50?")
        self.assertIn(f"Answer: {want} ", line, out)
        line, out = self.answer_of(p, "Amount of the invoice INV-007")
        self.assertIn(rows[6][3].replace(",", "."), line, out)

    def test_an_aligned_block_without_a_rule_line_is_read(self):
        names = ["Anders Holm", "Berit Nygaard", "Carl Dahl", "Dina Berg", "Erik Lund", "Frida Moe"]
        cols = [("Name", 16), ("City", 12), ("Qty", 5), ("Price", 8)]
        rows = [[names[k % 6], ("New York", "Oslo", "Bergen")[k % 3], str(10 + (k * 17) % 90), f"{(k * 13) % 500 / 10:.1f}"] for k in range(30)]
        lines = ["  ".join(c.ljust(w) for c, w in cols)] + ["  ".join(v.ljust(w) if i < 2 else v.rjust(w) for i, (v, (_, w)) in enumerate(zip(r, cols))) for r in rows]
        p = self.tmp / "aligned.txt"
        p.write_bytes(("\n".join(lines) + "\n").encode())
        text = self.step1(p)
        self.assertIn("Find one record:", text)
        want = sum(1 for r in rows if int(r[2]) > 50)
        line, out = self.answer_of(p, "How many rows have Qty over 50?")
        self.assertIn(f"Answer: {want} ", line, out)

    def test_prose_and_a_decorative_rule_are_not_a_table(self):
        para = ("The meeting opened at nine and the chair thanked everyone for coming so early in the week.\n"
                "Items were taken in the order printed on the agenda that was sent round last Friday.\n")
        text = "MINUTES OF THE MEETING\n" + "-" * 20 + "  " + "-" * 20 + "  " + "-" * 20 + "\n" + para * 3 + "\n" + para * 2
        p = self.tmp / "minutes.txt"
        p.write_text(text, encoding="utf-8")
        out = self.step1(p)
        self.assertNotIn("Find one record:", out)
        self.assertNotIn("Ask a count:", out)


# ------------------------------------------------------------------ 2. unit nouns, "have a <column>", text length
def r14_catalogue():
    rows = []
    for k in range(1, 41):
        mid = f"Please confirm item {k:02d} of the list" + " – Überprüfung" * (k % 5)
        ctx = "menu" if k % 5 == 0 else ("toolbar" if k % 11 == 0 else None)
        plural = f"{mid}s" if k % 7 == 0 else None
        msgstr = f"Bekræft alle numre i listen {k}\0Bekræft alle numrene {k}" if plural else f"Bekræft nummer {k}"   # a plural message has long forms: joined or alone, it is over the limit
        rows.append((mid, msgstr, plural, ctx, k % 6 == 0))
    rows.append(("Messages", "Beskeder", None, None, False))
    rows.append(("Rows", "Rækker", None, None, False))
    return sorted(rows, key=lambda r: ((r[3] + "\x04" if r[3] else "") + r[0]))


def stored(r):
    return ((r[3] + "\x04") if r[3] else "") + r[0] + (("\0" + r[2]) if r[2] else "")


class Gettext(R14Base):
    def files(self):
        rows = r14_catalogue()
        mo, po = self.tmp / "app.mo", self.tmp / "app.po"
        mo.write_bytes(mo_bytes(rows))
        po.write_bytes(po_text(rows))
        for p in (mo, po):
            self.prints(p)
        return rows, mo, po

    def test_a_word_that_is_only_the_unit_noun_is_not_a_value_filter(self):
        rows, mo, po = self.files()
        for p in (mo, po):
            with self.subTest(p.name):
                line, out = self.answer_of(p, "How many messages have a context (msgctxt)?")
                want = sum(1 for r in rows if r[3])
                self.assertIn(f"Answer: {want} ", line, out)
                self.assertNotRegex(out, r"(?<!\d)1 messages match")

    def test_have_a_plural_and_are_fuzzy(self):
        rows, mo, po = self.files()
        for p in (mo, po):
            line, out = self.answer_of(p, "How many messages have a plural form?")
            self.assertIn(f"Answer: {sum(1 for r in rows if r[2])} ", line, out)
        line, out = self.answer_of(po, "How many messages are fuzzy?")
        self.assertIn(f"Answer: {sum(1 for r in rows if r[4])} ", line, out)

    def test_the_stored_original_of_a_mo_counts_context_and_plural_in_bytes(self):
        rows, mo, po = self.files()
        by_bytes = sum(1 for r in rows if len(stored(r).encode()) > 80)
        by_chars = sum(1 for r in rows if len(stored(r)) > 80)
        self.assertNotEqual(by_bytes, by_chars, "the fixture must tell bytes from characters")
        line, out = self.answer_of(mo, "How many original strings are longer than 80 bytes? (Use the lengths in the table of original strings; context and plural parts count.)")
        self.assertIn(f"Answer: {by_bytes} ", line, out)
        self.assertIn("byte", out)

    def test_length_in_characters_and_the_other_direction(self):
        rows, mo, po = self.files()
        for p in (mo, po):
            n = sum(1 for r in rows if len(r[0]) > 60)
            line, out = self.answer_of(p, "How many messages have an original text longer than 60 characters?")
            self.assertIn(f"Answer: {n} ", line, out)
            n = sum(1 for r in rows if len(r[0]) < 45)
            line, out = self.answer_of(p, "How many messages have an original text shorter than 45 characters?")
            self.assertIn(f"Answer: {n} ", line, out)
            n = sum(1 for r in rows if len(r[0]) >= 70)
            line, out = self.answer_of(p, "How many messages have an original text of at least 70 characters?")
            self.assertIn(f"Answer: {n} ", line, out)

    def test_a_length_question_names_its_column_and_says_so(self):
        rows, mo, po = self.files()
        n = sum(1 for r in rows if len(r[1].split("\0")[0]) > 22)
        line, out = self.answer_of(po, "How many translations are longer than 22 characters?")
        self.assertIn(f"Answer: {n} ", line, out)
        self.assertIn("translation", out)

    def test_step1_advertises_the_forms(self):
        rows, mo, po = self.files()
        for p in (mo, po):
            ln = ask_line(self.step1(p))
            self.assertIsNotNone(ln)
            self.assertIn("longer than", ln)
            self.assertIn("have a", ln)
            self.assertLess(len(ln), 800)


class AnyTable(R14Base):
    def test_a_unit_noun_that_is_also_a_cell_value_does_not_filter(self):
        rows = [(1000 + k, ("Cases", "Staff", "Budget")[k % 3], 20 + (k * 7) % 50) for k in range(60)]
        p = self.tmp / "work.csv"
        p.write_text("case_id,topic,age\n" + "\n".join(f"{a},{b},{c}" for a, b, c in rows) + "\n", encoding="utf-8")
        self.step1(p)
        line, out = self.answer_of(p, "How many cases have age over 40?")
        self.assertIn(f"Answer: {sum(1 for r in rows if r[2] > 40)} ", line, out)

    def test_have_a_column_counts_cells_that_are_not_empty(self):
        rows = [(f"T-{k:03d}", ("amy", "bo", "")[k % 3] if k % 4 else "", "open" if k % 2 else "done") for k in range(1, 61)]
        p = self.tmp / "tickets.csv"
        p.write_text("ticket,assignee,state\n" + "\n".join(",".join(r) for r in rows) + "\n", encoding="utf-8")
        self.step1(p)
        line, out = self.answer_of(p, "How many tickets have an assignee?")
        self.assertIn(f"Answer: {sum(1 for r in rows if r[1])} ", line, out)

    def test_length_filter_on_a_text_column_of_a_csv(self):
        texts = ["short note", "a somewhat longer note about the visit", "x" * 55, "naïve café résumé überlang " * 2]
        rows = [(k, texts[k % 4]) for k in range(1, 41)]
        p = self.tmp / "notes.csv"
        p.write_text("visit,description\n" + "\n".join(f"{a},{b}" for a, b in rows) + "\n", encoding="utf-8")
        self.step1(p)
        line, out = self.answer_of(p, "How many rows have a description longer than 30 characters?")
        self.assertIn(f"Answer: {sum(1 for r in rows if len(r[1]) > 30)} ", line, out)
        line, out = self.answer_of(p, "How many rows have a description longer than 50 bytes?")
        self.assertIn(f"Answer: {sum(1 for r in rows if len(r[1].encode()) > 50)} ", line, out)


# ------------------------------------------------------------------ 3. presentations: a scope word, the last slide
P_NS = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="' + OD + '"'
SLIDES = [   # (title, body, notes)
    ("Signal basics", "How the receiver picks up the carrier", ""),
    ("Receiver design", "The signal path from antenna to correlator", "Walk through the signal chain slowly"),
    ("Timing", "Clock error and drift", "Remember the signal delay here"),
    ("Orbits", "Six planes of satellites", "Many signals share one band"),
    ("Errors", "Multipath and the signal it distorts", ""),
    ("Integrity", "Alarm limits", "Explain why a signal fault matters"),
    ("The Signal Plan", "Next steps", ""),
    ("Closing thoughts", "Questions", "Final signal check before we stop"),
]


def pptx_deck(path, slides=SLIDES, with_ph=True):
    def sp(i, name, ph, text):
        nv = f'<p:nvPr><p:ph type="{ph}"/></p:nvPr>' if (ph and with_ph) else "<p:nvPr/>"
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name}"/><p:cNvSpPr/>{nv}</p:nvSpPr><p:spPr/>'
                f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US"/><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>')

    def sld(body):
        return (f'<?xml version="1.0"?><p:sld {P_NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
                f'{body}</p:spTree></p:cSld></p:sld>')
    n = len(slides)
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
    pres = f'<?xml version="1.0"?><p:presentation {P_NS}><p:sldIdLst>' + "".join(f'<p:sldId id="{256 + i}" r:id="rId{i + 1}"/>' for i in range(n)) + "</p:sldIdLst></p:presentation>"
    prels = f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}">' + "".join(f'<Relationship Id="rId{i + 1}" Type="{OD}/slide" Target="slides/slide{i + 1}.xml"/>' for i in range(n)) + "</Relationships>"
    rels = (f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}"><Relationship Id="rId1" Type="{OD}/officeDocument" Target="ppt/presentation.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("ppt/presentation.xml", pres)
        z.writestr("ppt/_rels/presentation.xml.rels", prels)
        for i, (title, body, note) in enumerate(slides, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", sld(sp(2, "Title", "title", title) + sp(3, "Body", "body", body)))
            extra = ""
            if note:
                extra = f'<Relationship Id="rId2" Type="{OD}/notesSlide" Target="../notesSlides/notesSlide{i}.xml"/>'
                z.writestr(f"ppt/notesSlides/notesSlide{i}.xml",
                           f'<?xml version="1.0"?><p:notes {P_NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
                           + sp(2, "Notes", "body", note) + "</p:spTree></p:cSld></p:notes>")
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}">{extra}</Relationships>')


def odp_deck(path, slides=SLIDES):
    ns = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0" '
          'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"')
    pages = []
    for i, (title, body, note) in enumerate(slides, 1):
        notes = (f'<presentation:notes><draw:frame presentation:class="notes"><draw:text-box><text:p>{note}</text:p></draw:text-box></draw:frame></presentation:notes>' if note else "")
        pages.append(f'<draw:page draw:name="page{i}"><draw:frame presentation:class="title"><draw:text-box><text:p>{title}</text:p></draw:text-box></draw:frame>'
                     f'<draw:frame presentation:class="outline"><draw:text-box><text:list><text:list-item><text:p>{body}</text:p></text:list-item></text:list></draw:text-box></draw:frame>{notes}</draw:page>')
    content = f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {ns}><office:body><office:presentation>' + "".join(pages) + "</office:presentation></office:body></office:document-content>"
    meta = f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta {ns}><office:meta><dc:title>Talk</dc:title></office:meta></office:document-meta>'
    odf_zip(path, "application/vnd.oasis.opendocument.presentation", content, meta)


def has_word(text, word="signal"):
    return re.search(r"(?<!\w)" + word + r"(?!\w)", text, re.I) is not None


class Presentations(R14Base):
    def decks(self):
        out = []
        for name, fn in (("talk.pptx", pptx_deck), ("talk.odp", odp_deck)):
            p = self.tmp / name
            fn(p)
            self.prints(p)
            out.append(p)
        return out

    def test_notes_only_counts_notes(self):
        want = [i for i, (_, _, n) in enumerate(SLIDES, 1) if has_word(n)]
        self.assertEqual(len(want), 4)
        for p in self.decks():
            with self.subTest(p.name):
                line, out = self.answer_of(p, "On how many slides do the speaker notes contain the word 'signal'? (Whole word, any capitalisation; 'signals' does not count.)")
                self.assertIn(f"Answer: {len(want)} slide", line, out)
                self.assertIn(", ".join(str(i) for i in want), line, out)

    def test_slide_text_only_counts_slide_text(self):
        want = [i for i, (t, b, _) in enumerate(SLIDES, 1) if has_word(t + " " + b)]
        for p in self.decks():
            with self.subTest(p.name):
                line, out = self.answer_of(p, "On how many slides does the slide text (not the speaker notes) contain the word 'signal'?")
                self.assertIn(f"Answer: {len(want)} slide", line, out)

    def test_titles_only_counts_titles(self):
        want = [i for i, (t, _, _) in enumerate(SLIDES, 1) if has_word(t)]
        for p in self.decks():
            with self.subTest(p.name):
                line, out = self.answer_of(p, "On how many slides does the title contain the word 'signal'?")
                self.assertIn(f"Answer: {len(want)} slide", line, out)
                self.assertIn(", ".join(str(i) for i in want), line, out)

    def test_no_scope_still_counts_everything(self):
        want = [i for i, (t, b, n) in enumerate(SLIDES, 1) if has_word(" ".join((t, b, n)))]
        for p in self.decks():
            with self.subTest(p.name):
                line, out = self.answer_of(p, "On how many slides does the word 'signal' appear?")
                self.assertIn(f"Answer: {len(want)} slide", line, out)

    def test_a_deck_without_notes_has_none_to_count(self):
        p = self.tmp / "nonotes.pptx"
        pptx_deck(p, [(t, b, "") for t, b, _ in SLIDES])
        self.prints(p)
        line, out = self.answer_of(p, "On how many slides do the speaker notes contain the word 'signal'?")
        self.assertIn("Answer: 0 slide", line, out)
        self.assertIn("no speaker notes", out)

    def test_a_document_without_slides_refuses_a_speaker_notes_question(self):
        p = self.tmp / "memo.txt"
        p.write_text("The signal is strong.\n\nA second signal paragraph.\n", encoding="utf-8")
        line, out = self.answer_of(p, "In how many paragraphs do the speaker notes contain the word 'signal'?")
        self.assertIn("not answered", line, out)

    def test_step1_names_the_last_and_first_slide(self):
        for p in self.decks():
            with self.subTest(p.name):
                text = self.step1(p)
                ln = next((x for x in text.splitlines() if "Last slide" in x), None)
                self.assertIsNotNone(ln, text[:2500])
                self.assertIn("8", ln)
                self.assertIn("Closing thoughts", ln)
                self.assertIn("Signal basics", ln)

    def test_title_of_the_last_slide_and_of_slide_n(self):
        for p in self.decks():
            with self.subTest(p.name):
                line, out = self.answer_of(p, "What is the title text on the final slide?")
                self.assertIn("Closing thoughts", line, out)
                line, out = self.answer_of(p, "What is the title of slide 4?")
                self.assertIn("Orbits", line, out)
                line, out = self.answer_of(p, "title of the first slide")
                self.assertIn("Signal basics", line, out)
                line, out = self.answer_of(p, "What is the title of slide 99?")
                self.assertNotIn("Closing", line)


# ------------------------------------------------------------------ 4. netCDF char variables
NT, NS = 30, 8


def flag_at(t, s):
    return "GGGSMGGSGM"[(t * 7 + s * 3 + (t // 3)) % 10]


class NetcdfChar(R14Base):
    def make(self):
        flags = b"".join(flag_at(t, s).encode() for t in range(NT) for s in range(NS))
        codes = [("ALD", "ROW", "NRT", "SOU")[s % 4] for s in range(NS)]
        code_bytes = b"".join(c.encode().ljust(4, b"\0") for c in codes)
        nc = nc_file([("time", 0), ("station", NS), ("codelen", 4)], [("title", "r14 flags")],
                     [("time", [0], 4, [("units", "hours since 2025-01-01")], b"".join(struct.pack(">i", t) for t in range(NT))),
                      ("region_code", [1, 2], 2, [], code_bytes),
                      ("quality_flag", [0, 1], 2, [("long_name", "G good, S suspect, M missing")], flags)], NT)
        p = self.tmp / "gauges.nc"
        p.write_bytes(nc)
        self.prints(p)
        return p, flags.decode(), codes

    def test_count_of_one_letter_over_a_char_variable(self):
        p, flags, codes = self.make()
        for ch in "SMG":
            line, out = self.answer_of(p, f"How many entries of the variable quality_flag are the letter '{ch}'?")
            self.assertIn(f"Answer: {flags.count(ch)} ", line, out)
            self.assertIn(f"{NT * NS:,}", out)
            self.assertIn("character", out)

    def test_other_wordings(self):
        p, flags, codes = self.make()
        for q in ("How often does 'S' appear in quality_flag?", "count of S in quality_flag", "number of 'S' values in quality_flag", "how many characters of quality_flag equal S"):
            with self.subTest(q):
                line, out = self.answer_of(p, q)
                self.assertIn(f"Answer: {flags.count('S')} ", line, out)

    def test_the_case_is_as_written(self):
        p, flags, codes = self.make()
        line, out = self.answer_of(p, "How many entries of quality_flag are the letter 's'?")
        self.assertIn("Answer: 0 ", line, out)

    def test_a_string_target_counts_entries_of_a_string_variable(self):
        p, flags, codes = self.make()
        line, out = self.answer_of(p, "How many entries of the variable region_code are 'ALD'?")
        self.assertIn(f"Answer: {codes.count('ALD')} ", line, out)

    def test_step1_has_a_count_form_for_a_char_variable(self):
        p, flags, codes = self.make()
        text = self.step1(p)
        ln = ask_line(text)
        self.assertIsNotNone(ln, text[:2500])
        self.assertIn("quality_flag", ln)
        self.assertIn("letter", ln)


if __name__ == "__main__":
    unittest.main()
