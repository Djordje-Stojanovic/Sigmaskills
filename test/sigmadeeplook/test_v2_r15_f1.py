"""Fix round 15, lane F1 (ticket 83, P0.14b.H5 gate): three causes from held-out set 14, on fixtures built here (none from a held-out set).

Each cause is tested at the cause and never at a file name, value or question text:
1. a value that the file declares missing is not a value: in an SPSS file the user-defined missing codes (discrete, ranges, strings) and the
   system-missing cases drop out of every comparison, count, sum, mean, extreme and group; the answer says how many cases it left out and which
   codes; step 1 lists the declared codes; a question that asks for the raw values keeps them;
2. "any capitalisation" (and its other wordings) means the whole-word match ignores case; a quoted word inside a bracketed aside is an example, not
   a filter; a case-sensitive count says how many more match ignoring case;
3. a report with columns between pipes and a '---+---' rule, a header and a subtotal line per section, and decimal commas is one table; a number
   written with a comma in the question is a decimal when the table writes decimals so; a column named "Reading, m3" is found by its words; a
   decimal comma comes back as the file writes it.
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r9 import sbv_stamp  # noqa: E402
from test_v2_r11_f1 import HAVE_PANDAS  # noqa: E402
from test_v2_r12_f1 import R12Base, ask_line  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

SYSMIS = -1.7976931348623157e308


class R15Base(R12Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r15f1_"))

    def answer_of(self, path, question, tools=False, env=None):
        out = self.raw(path, question, tools=tools, env=env)
        line = next((x for x in out.splitlines() if x.startswith("Answer")), None)
        self.assertIsNotNone(line, "no Answer line:\n" + out[:1500])
        return line, out


# ------------------------------------------------------------------ 1. SPSS: declared missing values are not values
def sav_missing(vars_, rows):
    """An uncompressed SPSS file. vars_: (name, kind, missing) with kind 'n' (numeric) or 's' (8-byte string); missing: ('d', [codes]) discrete,
    ('r', lo, hi) a range, ('rd', lo, hi, code) a range and one code, or None. A numeric None is system-missing."""
    nv = len(vars_)
    h = b"$FL2" + b"@(#) SPSS DATA FILE - r15 test".ljust(60) + struct.pack("<iiiii", 2, nv, 0, 0, len(rows)) + struct.pack("<d", 100.0)
    h += b"01 Jan 26" + b"00:00:00" + b"r15 test".ljust(64) + b"\0\0\0"
    for name, kind, miss in vars_:
        codes = []
        nmiss = 0
        if miss:
            if miss[0] == "d":
                codes, nmiss = list(miss[1]), len(miss[1])
            elif miss[0] == "r":
                codes, nmiss = [miss[1], miss[2]], -2
            else:
                codes, nmiss = [miss[1], miss[2], miss[3]], -3
        fmt = 0x050800 if kind == "n" else 0x010800
        h += struct.pack("<iiiiii", 2, 0 if kind == "n" else 8, 0, nmiss, fmt, fmt) + name.ljust(8).encode()
        for c in codes:
            h += struct.pack("<d", c) if kind == "n" else str(c).encode().ljust(8)[:8]
    h += struct.pack("<ii", 999, 0)
    body = b""
    for r in rows:
        for (name, kind, miss), v in zip(vars_, r):
            if kind == "s":
                body += str(v).encode().ljust(8)[:8]
            else:
                body += struct.pack("<d", SYSMIS if v is None else v)
    return h + body


class SpssMissing(R15Base):
    VARS = [("resp_id", "n", None), ("commute", "n", ("d", [998, 999])), ("income", "n", ("rd", -9, -1, 99999)), ("region", "s", ("d", ["UNK"])),
            ("health", "n", ("r", 8, 9))]

    @staticmethod
    def rows(n=240):
        out = []
        for k in range(1, n + 1):
            commute = 999 if k % 11 == 0 else 998 if k % 13 == 0 else None if k % 17 == 0 else (k * 7) % 100
            income = -5 if k % 19 == 0 else 99999 if k % 23 == 0 else 1000 + (k * 31) % 900
            region = "UNK" if k % 7 == 0 else ("north", "south", "east")[k % 3]
            health = 9 if k % 29 == 0 else 8 if k % 31 == 0 else 1 + k % 5
            out.append((k, commute, income, region, health))
        return out

    def make(self, name="panel.sav"):
        rows = self.rows()
        p = self.tmp / name
        p.write_bytes(sav_missing(self.VARS, rows))
        self.step1(p)
        return p, rows

    @staticmethod
    def valid(v, col):
        if v is None:
            return False
        return {1: v not in (998, 999), 2: not (-9 <= v <= -1 or v == 99999), 4: not (8 <= v <= 9)}.get(col, True)

    def test_a_comparison_leaves_out_the_declared_codes_and_says_so(self):
        p, rows = self.make()
        want = sum(1 for r in rows if self.valid(r[1], 1) and r[1] > 45)
        raw_count = sum(1 for r in rows if r[1] is not None and r[1] > 45)
        self.assertNotEqual(want, raw_count)
        line, out = self.answer_of(p, "How many respondents have a commute of more than 45? Values that the file declares as missing do not count.")
        self.assertIn(f"Answer: {want} ", line, out)
        left_out = sum(1 for r in rows if r[1] in (998, 999))
        self.assertRegex(out, rf"(?i)user-defined missing values excluded: {left_out} cases?")
        self.assertIn("998, 999", out)

    def test_the_default_without_a_word_about_missing_is_the_same(self):
        p, rows = self.make("panel_b.sav")
        want = sum(1 for r in rows if self.valid(r[1], 1) and r[1] > 70)
        line, out = self.answer_of(p, "In how many cases is commute greater than 70?")
        self.assertIn(f"Answer: {want} ", line, out)

    def test_a_range_and_a_code_beside_it_are_declared_missing_too(self):
        p, rows = self.make("panel_c.sav")
        want = sum(1 for r in rows if self.valid(r[2], 2) and r[2] < 1100)
        line, out = self.answer_of(p, "How many cases have income below 1100?")
        self.assertIn(f"Answer: {want} ", line, out)
        self.assertRegex(out, r"(?i)user-defined missing values excluded")

    def test_sums_means_and_extremes_skip_the_declared_codes(self):
        p, rows = self.make("panel_d.sav")
        vals = [r[1] for r in rows if self.valid(r[1], 1)]
        line, out = self.answer_of(p, "What is the average commute?")
        self.assertIn(f"{sum(vals) / len(vals):.2f}"[:5], out, out)
        line, out = self.answer_of(p, "What is the maximum commute?")
        self.assertIn(f"{max(vals)}", line, out)
        self.assertNotIn("999", line)
        line, out = self.answer_of(p, "What is the total commute?")
        self.assertIn(f"{sum(vals):,}".replace(",", ""), out.replace(",", ""), out)

    def test_a_string_code_is_declared_missing_and_a_group_leaves_it_out(self):
        p, rows = self.make("panel_e.sav")
        line, out = self.answer_of(p, "How many cases are there per region?")
        for reg in ("north", "south", "east"):
            n = sum(1 for r in rows if r[3] == reg)
            self.assertRegex(out, rf"{reg}\W+{n}\b", out)
        self.assertNotRegex(out, r"UNK\W+\d")

    def test_a_question_for_the_raw_values_keeps_the_codes(self):
        p, rows = self.make("panel_f.sav")
        want = sum(1 for r in rows if r[1] is not None and r[1] > 45)
        for q in ("How many respondents have a commute of more than 45, including the missing codes?",
                  "How many respondents have a commute of more than 45? Count the raw values, missing codes too."):
            with self.subTest(q=q):
                line, out = self.answer_of(p, q)
                self.assertIn(f"Answer: {want} ", line, out)
                self.assertRegex(out, r"(?i)user-defined missing values (?:included|kept|counted)")

    def test_step_one_lists_what_each_variable_declares_missing(self):
        p, rows = self.make("panel_g.sav")
        out = self.step1(p)
        m = re.search(r"(?im)^.*declared missing.*$", out)
        self.assertIsNotNone(m, out[:3000])
        ln = m.group(0)
        self.assertIn("commute", ln)
        self.assertIn("998", ln)
        self.assertIn("999", ln)
        self.assertRegex(ln, r"-9\W+(?:to|thru|\.\.|-)\W*-1")
        self.assertIn("UNK", ln)
        self.assertRegex(ln, r"8\W+(?:to|thru|\.\.|-)\W*9")

    def test_a_variable_without_declared_codes_is_untouched(self):
        p, rows = self.make("panel_h.sav")
        want = sum(1 for r in rows if r[0] > 200)
        line, out = self.answer_of(p, "How many respondents have resp_id greater than 200?")
        self.assertIn(f"Answer: {want} ", line, out)
        self.assertNotRegex(out, r"(?i)user-defined missing values excluded: [1-9]")


# ------------------------------------------------------------------ 2. case, asides and a word that differs only by case
LINES = [
    ("Latarnia stoi na brzegu.", "Widać ją z daleka."),
    ("Ta stara latarnia ma dwie wieże.", "Wejście jest od północy."),
    ("Przewodnik opowiada o latarni morskiej.", "Zapraszamy do środka."),
    ("LATARNIA jest otwarta codziennie.", "Bilety kupujemy w kasie."),
    ("Syn latarnika lubił mewy.", "Mieszkał obok latarnię."),
    ("Zobaczymy latarnię i port.", "Potem idziemy na obiad."),
    ("Nowa latarnia, stara latarnia.", "Obie świecą nocą."),
    ("Dziś nie ma nic o tym.", "Pogoda jest ładna."),
    ("W niedzielę Latarnia jest zamknięta.", "Zapraszamy w poniedziałek."),
    ("Rodzina mieszkała obok,", "latarnika."),
]


def sbv_file(n=90):
    cues = []
    for k in range(n):
        a, b = LINES[k % len(LINES)]
        cues.append((k * 6.0, k * 6.0 + 4.5, [a, b]))
    txt = "\n".join(f"{sbv_stamp(s)},{sbv_stamp(e)}\n" + "\n".join(ls) + "\n" for s, e, ls in cues)
    return txt.encode("utf-8"), cues


def whole_word(cue, ci):
    return re.search(r"(?<!\w)latarnia(?!\w)", " ".join(cue[2]), re.I if ci else 0) is not None


class CaseWords(R15Base):
    def make(self, name="trip.sbv"):
        data, cues = sbv_file()
        p = self.tmp / name
        p.write_bytes(data)
        self.step1(p)
        return p, cues

    ASIDE = " (Whole word, {case}; forms such as 'latarni', 'latarnię' or 'latarnika' do not count; a cue counts once however often the word occurs.)"

    def test_any_capitalisation_with_an_aside_that_quotes_other_words(self):
        p, cues = self.make()
        want = sum(1 for c in cues if whole_word(c, True))
        as_written = sum(1 for c in cues if whole_word(c, False))
        self.assertNotEqual(want, as_written)
        for phrase in ("any capitalisation", "any capitalization", "any case", "regardless of case", "case-insensitive", "ignoring case", "whatever the capitalisation",
                       "no matter the case", "irrespective of capitalisation", "upper or lower case"):
            with self.subTest(phrase=phrase):
                line, out = self.answer_of(p, "How many cues contain the word 'latarnia'?" + self.ASIDE.format(case=phrase))
                self.assertIn(f"Answer: {want} ", line, out)
                self.assertNotIn("fourth line", out)
                self.assertNotIn("latarnika", out.split("Table:", 1)[-1].split("Cues:", 1)[0])

    def test_quoted_words_in_an_aside_are_not_filters_even_without_a_case_phrase(self):
        p, cues = self.make("trip_b.sbv")
        as_written = sum(1 for c in cues if whole_word(c, False))
        line, out = self.answer_of(p, "How many cues contain the word 'latarnia'? (Forms such as 'latarni' or 'latarnika' do not count.)")
        self.assertIn(f"Answer: {as_written} ", line, out)

    def test_a_case_sensitive_count_says_how_many_match_ignoring_case(self):
        p, cues = self.make("trip_c.sbv")
        as_written = sum(1 for c in cues if whole_word(c, False))
        ci = sum(1 for c in cues if whole_word(c, True))
        line, out = self.answer_of(p, "How many cues contain the word 'latarnia'?")
        self.assertIn(f"Answer: {as_written} ", line, out)
        self.assertRegex(out, rf"{as_written} cues contain it as written; {ci} ignoring case")

    def test_when_the_case_makes_no_difference_nothing_is_added(self):
        p, cues = self.make("trip_d.sbv")
        line, out = self.answer_of(p, "How many cues contain the word 'Zobaczymy'?")
        self.assertNotIn("ignoring case", out)

    def test_a_text_column_of_a_csv_follows_the_same_rule(self):
        rows = [(k, LINES[k % len(LINES)][0]) for k in range(80)]
        p = self.tmp / "notes.csv"
        p.write_text("id,note\n" + "\n".join(f'{a},"{b}"' for a, b in rows) + "\n", encoding="utf-8")
        self.step1(p)
        want = sum(1 for a, b in rows if re.search(r"(?<!\w)latarnia(?!\w)", b, re.I))
        line, out = self.answer_of(p, "How many notes contain the word 'latarnia'? (Whole word, any capitalisation; 'latarni' does not count.)")
        self.assertIn(f"Answer: {want} ", line, out)

    def test_a_text_document_counts_ignoring_case_on_the_same_phrases(self):
        p = self.tmp / "notes.txt"
        p.write_text("\n\n".join(a + " " + b for a, b in LINES * 3) + "\n", encoding="utf-8")
        self.step1(p)
        want = sum(1 for a, b in LINES * 3 if re.search(r"(?<!\w)latarnia(?!\w)", a + " " + b, re.I))
        line, out = self.answer_of(p, "In how many paragraphs does the word 'Latarnia' appear? (Whole word, any capitalisation; 'latarni' does not count.)")
        self.assertRegex(line, rf"Answer: {want} ")
        self.assertIn("any case", line)


# ------------------------------------------------------------------ 3. a pipe-and-rule report with sections, subtotals and decimal commas
def dec(x, places):
    return f"{x:.{places}f}".replace(".", ",")


def pipe_report(sections=3, per=14):
    """-> (cp1251 bytes, records) for a report: a title block, then per district a 'РАЙОН:' line, a header, a '----+----' rule, the rows and a subtotal."""
    widths = [7, 10, 24, 13, 10, 9]
    heads = ["Код", "Дата", "Адрес", "Показание, м3", "Разход, м3", "Състояние"]
    out = ["СПРАВКА ЗА ПОКАЗАНИЯТА НА ВОДОМЕРИТЕ, ОКТОМВРИ 2025 (синтетични данни за тест)", "Общински оператор „Водоснабдяване Север“",
           "Десетичният знак е запетая; обемите са в кубически метра.", ""]
    recs = []
    street = ["ул. Опълченска", "ул. Места", "ул. Рила", "бул. Витоша"]
    k = 0
    for s in range(sections):
        out.append(f"РАЙОН: {('Център', 'Север', 'Юг')[s % 3]}")
        out.append(" | ".join(h.ljust(w) if i < 3 or i == 5 else h.rjust(w) for i, (h, w) in enumerate(zip(heads, widths))))
        out.append("-" * (widths[0] + 1) + "+" + "+".join("-" * (w + 2) for w in widths[1:]))
        total = 0.0
        for j in range(per):
            k += 1
            code = f"ВМ-{k:04d}"
            reading = 500 + (k * 7919) % 6500 / 1.0 + (k % 7) / 1000 * 3
            use = round(5 + (k * 137) % 3200 / 100, 2)
            state = "ок" if k % 6 else "без достъп"
            addr = f"{street[k % 4]} № {(k * 13) % 90 + 1}"
            cells = [code.ljust(7), f"{(k % 28) + 1:02d}.10.2025".ljust(10), addr.ljust(24), dec(reading, 3).rjust(13), dec(use, 2).rjust(10), state.ljust(9)]
            out.append(" | ".join(cells))
            recs.append({"code": code, "reading": round(reading, 3), "reading_text": dec(reading, 3), "use": use, "state": state})
            total += use
        out.append(f"Общо за района: {per} записа, разход {dec(total, 2)} м3")
        out.append("")
    out += ["=" * 40, f"ОБЩО ЗА ОПЕРАТОРА: {len(recs)} записа", "Общ разход: 1,00 м3", "Съставил: отдел „Отчитане“"]
    return "\r\n".join(out).encode("cp1251"), recs


class PipeReport(R15Base):
    def make(self, name="vodomeri.txt"):
        data, recs = pipe_report()
        p = self.tmp / name
        p.write_bytes(data)
        self.step1(p)
        return p, recs

    def test_the_report_is_one_table_of_its_records_with_the_subtotals_left_out(self):
        p, recs = self.make()
        out = self.step1(p)
        head = out.splitlines()[0]
        self.assertIn(f"{len(recs)} rows", head + out[:400], out[:600])
        self.assertIn("6 columns", head + out[:400])

    def test_a_decimal_comma_number_in_the_question_is_a_decimal(self):
        p, recs = self.make("v2.txt")
        want = sum(1 for r in recs if r["use"] > 22.5)
        wrong = sum(1 for r in recs if r["use"] > 2250)
        self.assertNotEqual(want, wrong)
        line, out = self.answer_of(p, "How many records have Разход, м3 greater than 22,50?")
        self.assertIn(f"Answer: {want} ", line, out)
        self.assertRegex(out, r"22,50.{0,60}22\.5|22\.5.{0,60}22,50")   # the reading is stated

    def test_the_same_number_in_the_words_of_a_long_question(self):
        p, recs = self.make("v3.txt")
        want = sum(1 for r in recs if r["use"] > 22.5)
        line, out = self.answer_of(p, "For how many records is the consumption (the 'Разход, м3' column, in cubic metres, written with a decimal comma) greater than 22,50?")
        self.assertIn(f"Answer: {want} ", line, out)

    def test_three_digits_after_the_comma_follow_the_table_not_the_thousands_rule(self):
        p, recs = self.make("v4.txt")
        want = sum(1 for r in recs if r["use"] > 22.5)
        line, out = self.answer_of(p, "How many records have Разход, м3 greater than 22,500?")
        self.assertIn(f"Answer: {want} ", line, out)
        self.assertRegex(out, r"(?i)decimal")

    def test_a_thousands_comma_stays_a_thousands_comma_in_a_table_without_decimal_commas(self):
        rows = [(k, 500 + (k * 137) % 4000) for k in range(1, 61)]
        p = self.tmp / "plain.csv"
        p.write_text("id,metres\n" + "\n".join(f"{a},{b}" for a, b in rows) + "\n", encoding="utf-8")
        self.step1(p)
        for text, thr in (("2,250", 2250), ("1,000", 1000), ("2,250.5", 2250.5)):
            with self.subTest(text=text):
                want = sum(1 for a, b in rows if b > thr)
                line, out = self.answer_of(p, f"How many rows have metres greater than {text}?")
                self.assertIn(f"Answer: {want} ", line, out)

    def test_a_column_named_with_a_unit_is_found_and_the_decimal_comma_comes_back(self):
        p, recs = self.make("v5.txt")
        r = recs[17]
        for q in (f"Показание, м3 of {r['code']}", f"What meter reading (the 'Показание, м3' column) is recorded for the record {r['code']}? Give it exactly as written, with its decimal comma."):
            with self.subTest(q=q):
                line, out = self.answer_of(p, q)
                self.assertIn(r["reading_text"], out, out)
                self.assertNotIn(f"{r['reading']:g}", out.replace(r["reading_text"], ""))

    def test_a_bare_code_without_its_prefix_finds_the_record(self):
        p, recs = self.make("v6.txt")
        r = recs[9]
        line, out = self.answer_of(p, f"Разход, м3 of {r['code']}")
        self.assertIn(dec(r["use"], 2), out, out)


# ------------------------------------------------------------------ 1b. Stata / SAS: a missing value (extended missing .a-.z) is not a number
@unittest.skipUnless(HAVE_PANDAS, "pandas needed")
class FrameMissing(R15Base):
    def test_a_stata_column_with_many_missing_values_still_counts_and_sums(self):
        import pandas as pd
        vals = [None if k % 3 == 0 else (k * 7) % 100 for k in range(1, 61)]
        df = pd.DataFrame({"id": range(1, 61), "commute": [float("nan") if v is None else float(v) for v in vals], "grp": ["a", "b"] * 30})
        p = self.tmp / "frame.dta"
        df.to_stata(str(p), write_index=False)
        self.step1(p)
        ok = [v for v in vals if v is not None]
        line, out = self.answer_of(p, "How many rows have commute greater than 45?")
        self.assertIn(f"Answer: {sum(1 for v in ok if v > 45)} ", line, out)
        line, out = self.answer_of(p, "What is the average commute?")
        self.assertIn(f"{sum(ok) / len(ok):g}", line, out)
        line, out = self.answer_of(p, "What is the maximum commute?")
        self.assertIn(f"{max(ok)}", line, out)


class NumberReading(unittest.TestCase):
    def test_the_reading_of_a_number_with_a_comma(self):
        import dl_r15
        cases = {"22,50": (22.5, None), "12,5": (12.5, None), "0,250": (0.25, None), "1,234,567": (1234567.0, None), "400": (400.0, None), "2,250.5": (2250.5, None),
                 "2,250": (2250.0, 2.25), "1,5": (1.5, None), "1.234,5": (1234.5, None)}
        for text, (value, alt) in cases.items():
            with self.subTest(text=text):
                got = dl_r15.number_value(text)
                self.assertAlmostEqual(got[0], value)
                self.assertEqual(got[1], alt)


if __name__ == "__main__":
    unittest.main()
