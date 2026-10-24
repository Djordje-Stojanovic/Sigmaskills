"""Fix round 15, lane F2 (ticket 83, P0.14b.H5): two causes of held-out set 14, on fixtures built here (none from a held-out set).

1. A statistical file keeps a dataset label and, for each variable, a label, a format (name, width, decimals) and an informat. They are not rows, so
   the table machinery never saw them. The look prints the dataset label and the formats, and `--ask` answers "dataset label", "label of variable X",
   "format of variable X", "which variables have a date format" and "value labels of X" for SAS (sas7bdat, XPORT), SPSS and Stata.
2. A question can carry a clause that the engine has no filter for ("values declared missing do not count", "whole word, any capitalisation",
   "greater than 22,50", "between 3 and 7", "excluding Berlin"). The number is still given, and a `Not applied:` line follows it.
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS  # noqa: E402
from test_v2_r12_f1 import R12Base  # noqa: E402
from test_v2_r11_f1 import ibm  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
HAVE_PANDAS = importlib.util.find_spec("pandas") is not None

MAGIC = bytes.fromhex("000000000000000000000000c2ea8160b31411cfbd92080009c7318c181f1011")


class Base(R12Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r15f2_"))

    def answer(self, out):
        ln = next((x for x in out.splitlines() if x.startswith("Answer")), None)
        self.assertIsNotNone(ln, out[:1500])
        return ln


# ------------------------------------------------------------------ fixture writers
def sas7bdat(cols, rows, label="", u64=True, name="ORDERS"):
    """A sas7bdat file: one meta page (row size, column size, text, names, attributes, one format record per column) and one data page.
    cols: dicts name, kind 'n'|'c', width (chars), label, fmt, fw, fd, inf."""
    il, pbo, ptr = (8, 32, 24) if u64 else (4, 16, 12)
    hl, pl = 1024, 8192
    a = 4 if u64 else 0
    h = bytearray(hl)
    h[:32] = MAGIC
    h[32] = h[35] = 0x33 if u64 else 0x22
    h[37], h[39], h[70] = 1, ord("1"), 20
    h[84:92] = b"SAS FILE"
    h[92:156] = name.encode().ljust(64)
    h[156:164] = b"DATA".ljust(8)
    struct.pack_into("<dd", h, 164 + a, 2_000_000_000.0, 2_000_000_100.0)
    struct.pack_into("<ii", h, 196 + a, hl, pl)
    struct.pack_into("<q" if u64 else "<i", h, 204 + a, 2)
    h[216 + 2 * a:224 + 2 * a] = b"9.0401M6 "[:8]
    h[224 + 2 * a:240 + 2 * a] = b"Linux".ljust(16, b"\0")
    # text pool: every string once, each located by (blob index 0, offset, length)
    blob = bytearray(b"\0\0" + b" " * 26)

    def add(s):
        if not s:
            return (0, 0, 0)
        b = s.encode("utf-8")
        at = len(blob)
        blob.extend(b)
        return (0, at, len(b))
    lab_t = add(label)
    ptrs = []
    for c in cols:
        ptrs.append({"name": add(c["name"]), "lab": add(c.get("label", "")), "fmt": add(c.get("fmt", "")), "inf": add(c.get("inf", ""))})
    struct.pack_into("<H", blob, 0, len(blob))

    def sig(kind):
        base = {"row": b"\xf7\xf7\xf7\xf7", "col": b"\xf6\xf6\xf6\xf6", "text": b"\xfd\xff\xff\xff", "name": b"\xff\xff\xff\xff", "attr": b"\xfc\xff\xff\xff",
                "fmt": b"\xfe\xfb\xff\xff"}[kind]
        return base + ((b"\0" * 4 if kind in ("row", "col") else b"\xff" * 4) if u64 else b"")
    n = len(cols)
    offs, pos = [], 0
    for c in cols:
        w = 8 if c["kind"] == "n" else c["width"]
        offs.append((pos, w))
        pos += w
    row = bytearray(808)
    row[:il] = sig("row")
    for k, v in ((5, pos), (6, len(rows)), (9, n)):
        row[il * k:il * k + il] = v.to_bytes(il, "little")
    lcs = 682 if u64 else 354
    struct.pack_into("<HHH", row, lcs - 4, *lab_t)
    colsz = bytearray(sig("col") + n.to_bytes(il, "little") + b"\0" * il)
    text = bytearray(sig("text")) + blob + b"\0" * 12
    names = bytearray(2 * il + 12 + 8 * n)
    names[:il] = sig("name")
    attrs = bytearray(2 * il + 12 + n * (il + 8))
    attrs[:il] = sig("attr")
    for k, c in enumerate(cols):
        struct.pack_into("<HHH", names, il + 8 + 8 * k, *ptrs[k]["name"])
        e = il + 8 + k * (il + 8)
        attrs[e:e + il] = offs[k][0].to_bytes(il, "little")
        struct.pack_into("<I", attrs, e + il, offs[k][1])
        attrs[e + il + 6] = 1 if c["kind"] == "n" else 2
    subs = [row, colsz, text, names, attrs]
    g = 3 * il
    for k, c in enumerate(cols):
        f = bytearray(g + 40)
        f[:il] = sig("fmt")
        struct.pack_into("<HH", f, g, c.get("fw", 0), c.get("fd", 0))
        struct.pack_into("<HHH", f, g + 16, *ptrs[k]["inf"])
        struct.pack_into("<HHH", f, g + 22, *ptrs[k]["fmt"])
        struct.pack_into("<HHH", f, g + 28, *ptrs[k]["lab"])
        subs.append(f)
    page = bytearray(pl)
    struct.pack_into("<HHH", page, pbo, 0, len(subs), len(subs))
    end = pl
    for i, s in enumerate(subs):
        end -= len(s)
        page[end:end + len(s)] = s
        at = pbo + 8 + ptr * i
        page[at:at + il] = end.to_bytes(il, "little")
        page[at + il:at + 2 * il] = len(s).to_bytes(il, "little")
        page[at + 2 * il] = 0
    data = bytearray(pl)
    struct.pack_into("<HHH", data, pbo, 0x100, len(rows), 0)
    p = pbo + 8
    for r in rows:
        for c, v, (o, w) in zip(cols, r, offs):
            if c["kind"] == "n":
                data[p + o:p + o + 8] = struct.pack("<d", v)
            else:
                data[p + o:p + o + w] = str(v).encode("utf-8").ljust(w)[:w]
        p += pos
    return bytes(h) + bytes(page) + bytes(data)


ORDER_COLS = [
    {"name": "ORDER_ID", "kind": "n", "label": "Order number"},
    {"name": "ORDER_DATE", "kind": "n", "label": "Date the order was placed", "fmt": "DATE", "fw": 9, "inf": "DATE"},
    {"name": "AMOUNT", "kind": "n", "label": "Amount in euro, tax included", "fmt": "COMMA", "fw": 12, "fd": 2},
    {"name": "CITY", "kind": "c", "width": 10, "label": "Delivery city"},
    {"name": "NOTE", "kind": "c", "width": 6},
    {"name": "SHIPPED", "kind": "n", "fmt": "DATETIME", "inf": "ANYDTDTM"},
]
ORDER_ROWS = [(k, 22000.0 + k, 10.5 * k, ["Paris", "Rome", "Oslo"][k % 3], "", 1.9e9 + k) for k in range(1, 13)]
DATASET_LABEL = "Orders of the autumn test"


def xpt_labeled(label, cols, rows):
    """A SAS XPORT v5 file. cols: dicts name, kind, width, label, fmt, fw, fd, inf."""
    def rec(s):
        return s.ljust(80).encode()
    stamp = "01JAN26:00:00:00"
    out = rec("HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!000000000000000000000000000000  ")
    out += rec("SAS     SAS     SASLIB  9.4     X64_7PRO" + " " * 24 + stamp) + rec(stamp)
    out += rec("HEADER RECORD*******MEMBER  HEADER RECORD!!!!!!!000000000000000001600000000140  ")
    out += rec("HEADER RECORD*******DSCRPTR HEADER RECORD!!!!!!!000000000000000000000000000000  ")
    out += rec("SAS     VISITS  SASDATA 9.4     X64_7PRO" + " " * 24 + stamp) + rec(stamp + " " * 16 + label.ljust(40) + "DATA".ljust(8))
    out += rec(f"HEADER RECORD*******NAMESTR HEADER RECORD!!!!!!!000000{len(cols):04d}00000000000000000000  ")
    ns, pos = b"", 0
    for i, c in enumerate(cols, 1):
        w = 8 if c["kind"] == "n" else c["width"]
        ns += struct.pack(">hhhh8s40s8shhh2s8shhl52s", 1 if c["kind"] == "n" else 2, 0, w, i, c["name"].ljust(8).encode(), c.get("label", "").ljust(40).encode(),
                          c.get("fmt", "").ljust(8).encode(), c.get("fw", 0), c.get("fd", 0), 0, b"  ", c.get("inf", "").ljust(8).encode(), 0, 0, pos, b"\0" * 52)
        pos += w
    out += ns + b" " * (-len(ns) % 80)
    out += rec("HEADER RECORD*******OBS     HEADER RECORD!!!!!!!000000000000000000000000000000  ")
    body = b""
    for r in rows:
        for c, v in zip(cols, r):
            body += ibm(v) if c["kind"] == "n" else str(v).encode().ljust(c["width"])
    return out + body + b" " * (-len(body) % 80)


def sav_labeled(label, vars_, value_labels, rows):
    """An uncompressed SPSS file. vars_: dicts name, label, print (type, width, decimals) or None, string (bool). value_labels: {var index (0-based): {code: text}}."""
    nv = len(vars_)
    h = b"$FL2" + b"@(#) SPSS DATA FILE - r15 test".ljust(60) + struct.pack("<iiiii", 2, nv, 0, 0, len(rows)) + struct.pack("<d", 100.0)
    h += b"01 Jan 26" + b"00:00:00" + label.encode().ljust(64) + b"\0\0\0"
    for v in vars_:
        t, w, d = v.get("print") or ((1, 8, 0) if v.get("string") else (5, 8, 2))
        code = (t << 16) | (w << 8) | d
        lab = v.get("label", "").encode()
        h += struct.pack("<iiiiii", 2, 8 if v.get("string") else 0, 1 if lab else 0, 0, code, code) + v["name"].ljust(8).encode()
        if lab:
            h += struct.pack("<i", len(lab)) + lab.ljust((len(lab) + 3) // 4 * 4, b"\0")
    for k, labs in value_labels.items():
        h += struct.pack("<ii", 3, len(labs))
        for code, text in labs.items():
            b = text.encode()
            h += struct.pack("<d", float(code)) + bytes([len(b)]) + b.ljust((1 + len(b) + 7) // 8 * 8 - 1, b"\0")
        h += struct.pack("<iii", 4, 1, k + 1)
    h += struct.pack("<ii", 999, 0)
    body = b""
    for r in rows:
        for v, x in zip(vars_, r):
            body += str(x).encode().ljust(8)[:8] if v.get("string") else struct.pack("<d", x)
    return h + body


# ------------------------------------------------------------------ 1. SAS dataset label, variable labels and formats
class SasLabelsFormats(Base):
    def make(self, u64, name="orders"):
        p = self.tmp / f"{name}_{'64' if u64 else '32'}.sas7bdat"
        p.write_bytes(sas7bdat(ORDER_COLS, ORDER_ROWS, label=DATASET_LABEL, u64=u64))
        return p

    def test_print_has_the_dataset_label_and_the_formats_in_both_layouts(self):
        for u64 in (True, False):
            with self.subTest(u64=u64):
                s1 = self.step1(self.make(u64))
                self.assertIn(f"Dataset label: '{DATASET_LABEL}'", s1)
                self.assertIn("ORDER_DATE DATE9.", s1)
                self.assertIn("AMOUNT COMMA12.2", s1)
                self.assertIn("SHIPPED DATETIME", s1)
                self.assertIn("Order number", s1, "the variable labels are in the first print")
                self.assertLess(len(s1), 7000, "the first print stays small")

    def test_ask_answers_the_dataset_label(self):
        p = self.make(True)
        self.step1(p)
        for q in ("What label (dataset label) does the file carry for the whole dataset?", "What is the dataset label?", "label of the file",
                  "Which label does the whole data set carry?"):
            with self.subTest(q=q):
                self.assertEqual(self.answer(self.raw(p, q)), f"Answer: {DATASET_LABEL}")

    def test_ask_answers_the_format_of_a_variable_by_name_only(self):
        for u64 in (True, False):
            p = self.make(u64)
            self.step1(p)
            with self.subTest(u64=u64):
                self.assertEqual(self.answer(self.raw(p, "Which SAS format is attached to the variable 'ORDER_DATE'? Give the format name only.")), "Answer: DATE")
                self.assertEqual(self.answer(self.raw(p, "what is the format of variable order_date")), "Answer: DATE")
                out = self.raw(p, "format of variable AMOUNT")
                self.assertEqual(self.answer(out), "Answer: COMMA")
                self.assertIn("width 12, decimals 2 (COMMA12.2)", out)
                self.assertIn("none", self.answer(self.raw(p, "format of variable CITY")))
                self.assertEqual(self.answer(self.raw(p, "Which informat does the variable SHIPPED have?")), "Answer: ANYDTDTM")

    def test_ask_answers_the_label_of_a_variable_and_lists_by_format(self):
        p = self.make(True)
        self.step1(p)
        self.assertEqual(self.answer(self.raw(p, "What is the label of variable AMOUNT?")), "Answer: Amount in euro, tax included")
        self.assertEqual(self.answer(self.raw(p, "label of the column 'CITY'")), "Answer: Delivery city")
        self.assertIn("no label", self.answer(self.raw(p, "label of variable NOTE")))
        dates = self.answer(self.raw(p, "Which variables have a date format?"))
        self.assertIn("ORDER_DATE", dates)
        self.assertIn("SHIPPED", dates)
        self.assertNotIn("AMOUNT", dates)
        self.assertIn("3 of 6 variables", self.answer(self.raw(p, "How many variables have a format?")))

    def test_rows_still_read_and_counted(self):
        if not HAVE_PANDAS:
            self.skipTest("pandas reads the rows")
        p = self.make(True)
        self.step1(p, tools=True)
        want = sum(1 for r in ORDER_ROWS if r[2] > 60)
        out = self.raw(p, "How many rows have AMOUNT over 60?", tools=True)
        self.assertIn(str(want), self.answer(out))

    def test_a_file_without_labels_or_formats_prints_nothing_extra(self):
        cols = [{"name": "A", "kind": "n"}, {"name": "B", "kind": "c", "width": 4}]
        p = self.tmp / "plain.sas7bdat"
        p.write_bytes(sas7bdat(cols, [(1.0, "x"), (2.0, "y")]))
        s1 = self.step1(p)
        self.assertNotIn("Formats (", s1)
        self.assertNotIn("Variable labels", s1)
        self.assertNotIn("Dataset label", s1)
        self.assertIn("no label", self.answer(self.raw(p, "label of variable A")))
        self.assertIn("none", self.answer(self.raw(p, "dataset label")))


class VariableNameUnit(unittest.TestCase):
    def test_a_variable_called_date_is_not_the_word_in_a_date_format_question(self):
        import dl_varmeta
        meta = {"kind": "SAS", "label": "", "vars": [{"name": "date", "label": "", "format": "DATE", "fw": 9, "fd": 0, "informat": ""},
                                                       {"name": "stamp", "label": "", "format": "DATETIME", "fw": 0, "fd": 0, "informat": ""},
                                                       {"name": "qty", "label": "", "format": "", "fw": 0, "fd": 0, "informat": ""}]}
        lj = {"facts": {"var_meta": meta}}
        got = dl_varmeta.try_ask("Which variables have a date format?", lj)
        self.assertIn("2 variables", got)
        self.assertIn("stamp", got)
        self.assertIn("Answer: DATE", dl_varmeta.try_ask("format of variable date", lj))
        self.assertIsNone(dl_varmeta.try_ask("How many rows have a format of 5?", lj), "no variable word: a data question")
        self.assertIsNone(dl_varmeta.try_ask("How many rows have qty over 5?", lj))


class XportLabelsFormats(Base):
    COLS = [{"name": "PATID", "kind": "n", "label": "Patient identifier"},
            {"name": "VISITDT", "kind": "n", "label": "Date of the visit", "fmt": "YYMMDD", "fw": 10, "inf": "YYMMDD"},
            {"name": "SITE", "kind": "c", "width": 6}]

    def test_label_formats_and_variable_labels(self):
        p = self.tmp / "visits.xpt"
        p.write_bytes(xpt_labeled("Clinic visits of the test study", self.COLS, [(1, 22000, "AB"), (2, 22010, "CD")]))
        s1 = self.step1(p)
        self.assertIn("Dataset label: 'Clinic visits of the test study'", s1)
        self.assertIn("VISITDT YYMMDD10.", s1)
        self.assertEqual(self.answer(self.raw(p, "What is the dataset label?")), "Answer: Clinic visits of the test study")
        self.assertEqual(self.answer(self.raw(p, "Which format is attached to the variable VISITDT? Name only.")), "Answer: YYMMDD")
        self.assertEqual(self.answer(self.raw(p, "label of variable PATID")), "Answer: Patient identifier")
        self.assertIn("none", self.answer(self.raw(p, "format of variable PATID")))


class SpssLabelsFormats(Base):
    VARS = [{"name": "age", "label": "Age in years", "print": (5, 3, 0)}, {"name": "sex", "label": "Sex of the respondent", "print": (5, 1, 0)},
            {"name": "intdate", "label": "Date of the interview", "print": (22, 20, 0)}, {"name": "town", "string": True}]
    LABELS = {1: {1: "Female", 2: "Male", 9: "No answer"}}

    def test_formats_and_value_labels(self):
        p = self.tmp / "survey.sav"
        p.write_bytes(sav_labeled("Test survey file", self.VARS, self.LABELS, [(30, 1, 1.9e9, "Oslo"), (41, 2, 1.9e9, "Rome")]))
        s1 = self.step1(p)
        self.assertIn("intdate DATETIME20.", s1)
        self.assertEqual(self.answer(self.raw(p, "What is the dataset label?")), "Answer: Test survey file")
        self.assertEqual(self.answer(self.raw(p, "Which format is attached to the variable intdate?")), "Answer: DATETIME")
        self.assertEqual(self.answer(self.raw(p, "label of variable age")), "Answer: Age in years")
        out = self.answer(self.raw(p, "value labels of sex"))
        self.assertIn("1 = Female", out)
        self.assertIn("2 = Male", out)
        self.assertIn("9 = No answer", out)
        self.assertIn("no value labels", self.answer(self.raw(p, "value labels of age")))
        self.assertEqual(self.answer(self.raw(p, "format of variable age")), "Answer: F")


@unittest.skipUnless(HAVE_PANDAS, "pandas writes a Stata file")
class StataLabelsFormats(Base):
    def test_formats_and_value_labels(self):
        import pandas as pd
        df = pd.DataFrame({"born": pd.to_datetime(["1990-05-01", "1985-07-09"]), "score": [3.5, 4.0], "grade": pd.Categorical(["low", "high"], categories=["low", "high"])})
        p = self.tmp / "grades.dta"
        df.to_stata(p, write_index=False, convert_dates={"born": "td"}, data_label="Grades of the test class", variable_labels={"score": "Test score", "born": "Date of birth"},
                    version=118)
        self.step1(p, tools=True)
        self.assertEqual(self.answer(self.raw(p, "What is the dataset label?", tools=True)), "Answer: Grades of the test class")
        self.assertEqual(self.answer(self.raw(p, "Which format is attached to the variable born?", tools=True)), "Answer: %td")
        self.assertEqual(self.answer(self.raw(p, "label of variable score", tools=True)), "Answer: Test score")
        out = self.answer(self.raw(p, "value labels of grade", tools=True))
        self.assertIn("low", out)
        self.assertIn("high", out)


# ------------------------------------------------------------------ 2. a clause the engine did not apply is named
class NotAppliedGuard(Base):
    CITIES = ["Paris", "Berlin", "Rome", "Oslo", "paris"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lines = ["id,city,qty,price,shipped"]
        for i in range(60):
            lines.append(f"{i + 1},{cls.CITIES[i * 7 % 5]},{'' if i % 11 == 0 else 1 + i * 5 % 9},{(100 + i * 37 % 2900) / 100:.2f},2024-0{1 + i % 9}-1{i % 9}")
        cls.path = cls.tmp / "items.csv"
        cls.path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        cls.first = None

    def ask(self, q):
        if NotAppliedGuard.first is None:
            self.step1(self.path)
            NotAppliedGuard.first = True
        return self.raw(self.path, q)

    def na(self, q):
        out = self.ask(q)
        self.answer(out)
        return next((x for x in out.splitlines() if x.startswith("Not applied:")), None), out

    def test_declared_missing_values_that_the_engine_cannot_exclude_are_named(self):
        na, out = self.na("How many rows have qty over 5? Values declared as missing (code 999) do not count.")
        self.assertIsNotNone(na, out)
        self.assertIn("declared as missing", na)
        self.assertLess(out.splitlines().index(na) - [i for i, x in enumerate(out.splitlines()) if x.startswith("Answer:")][0], 2, "the line follows the Answer line")

    def test_whole_word_and_capitalisation_in_an_equality_filter_are_named(self):
        na, out = self.na("How many rows have city = 'Paris'? (Whole word, any capitalisation.)")
        self.assertIsNotNone(na, out)
        self.assertIn("Whole word", na)
        self.assertIn("any capitalisation", na)

    def test_a_decimal_comma_number_the_engine_reads_is_not_flagged_and_one_it_misreads_is(self):
        na, out = self.na("How many rows have price greater than 12,50?")
        self.assertIsNone(na, out)   # the engine reads 12,50 as 12.5 and says so in its Filters line
        import dl_r15f2
        misread = "--ask 'q'" + chr(10) + "Read as: operation count" + chr(10) + "Answer: 0 lines match" + chr(10) + "Filters: price > 1,250 -> 0 lines"
        self.assertEqual(dl_r15f2.check("How many rows have price greater than 12,50?", misread), ["greater than 12,50"])

    def test_between_after_and_excluding_are_named_when_no_filter_shows_them(self):
        for q, clause in (("How many rows have qty between 3 and 7?", "between 3 and 7"), ("How many rows shipped after 2024-05-01?", "after 2024-05-01"),
                          ("How many rows have city = 'Paris', excluding Berlin?", "excluding Berlin")):
            with self.subTest(q=q):
                na, out = self.na(q)
                self.assertIsNotNone(na, out)
                self.assertIn(clause, na)

    def test_a_clause_the_engine_applied_is_not_flagged(self):
        for q in ("How many rows have qty over 5? Missing values do not count.", "How many rows have qty over 5?", "How many rows have price greater than 12.5?",
                  "How many rows have city = 'Oslo'? (answer as a number)", "How many distinct cities are there?", "How many rows have qty over 5 (a whole number)?",
                  "How many rows have city = 'Rome'? Give only the number."):
            with self.subTest(q=q):
                na, out = self.na(q)
                self.assertIsNone(na, out)

    def test_the_number_is_still_given(self):
        na, out = self.na("How many rows have qty between 3 and 7?")
        self.assertRegex(self.answer(out), r"Answer: \d+")

    def test_the_guard_unit(self):
        import dl_r15f2
        text = "--ask 'q'\nRead as: operation count\nAnswer: 3 lines match\nFilters: qty > 5 -> 3 lines"
        self.assertEqual(dl_r15f2.check("How many have qty over 5?", text), [])
        self.assertEqual(len(dl_r15f2.check("How many have qty over 6?", text)), 1)
        neg = "--ask 'q'\nRead as: operation count\nAnswer: 3 lines match\nFilters: city != 'berlin' -> 3 lines"
        self.assertEqual(dl_r15f2.check("How many rows, excluding Berlin?", neg), [])
        self.assertEqual(len(dl_r15f2.check("How many rows, excluding Rome?", neg)), 1)
        none = "--ask 'q'\nRead as: operation count\nAnswer: 9 lines match\nFilters: none -> 9 lines"
        self.assertEqual(len(dl_r15f2.check("How many rows are there? Empty rows do not count.", none)), 1, "no filter at all: nothing excludes the empty rows")
        self.assertEqual(dl_r15f2.check("How many rows have qty over 5? Empty cells do not count.", text), [], "a comparison never matches an empty cell")
        eq = "--ask 'q'\nRead as: operation count\nAnswer: 3 lines match\nFilters: city = 'Paris' (case as written) -> 3 lines"
        self.assertEqual(dl_r15f2.check("How many rows have city = 'Paris'? (case-sensitive)", eq), [], "the engine counts case as written")
        self.assertEqual(dl_r15f2.check("How many rows have a different city than Paris?", eq), [], "one different city is not a distinct count")
        self.assertEqual(len(dl_r15f2.check("How many rows have city = 'Paris', ignoring case?", eq)), 1)
        self.assertEqual(dl_r15f2.number("22,50"), 22.5)
        self.assertEqual(dl_r15f2.number("1,234"), 1234.0)
        self.assertEqual(dl_r15f2.number("1.234,5"), 1234.5)
        self.assertEqual(dl_r15f2.guard("q", "Answer: not answered: x"), "Answer: not answered: x")
        self.assertEqual(dl_r15f2.guard("excluding Rome", "Answer: Windows code page 1254\nSource: x"), "Answer: Windows code page 1254\nSource: x", "other routes state their own scope")


if __name__ == "__main__":
    unittest.main()
