"""Fix round 11, lane F1 (ticket 83, P0.14b.H5): single-record lookups, on fixtures built here (none from a held-out set).

The method: an agent reads the print, then runs ONE `--ask`. A lookup (one record id, one key, one cue, one cell) counts as answered when
(a) the first two prints say where the record lives (a `Find one record:` line with the table, the row count, the unique key column and
its range, and the route) and (b) one `--ask` returns the exact answer. Both halves are tested for every family: delimited text under a
title block, gettext .po/.mo, Java .properties, .sbv/.srt/.vtt cues, SAS, SPSS, netCDF grids, SQLite/GeoPackage, worksheets, JSON Lines.
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import importlib.util
import io
import json
import shutil
import sqlite3
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r8b import xlsb_bytes  # noqa: E402
from test_v2_r9 import sbv_stamp  # noqa: E402
from test_v2_r10_f2 import nc_file, mutants  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

HAVE_PANDAS = importlib.util.find_spec("pandas") is not None


class R11Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r11f1_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def out_of(self, path):
        return self.tmp / ("out_" + path.name)

    def prints(self, path, tools=False, ok=(0,)):
        """Step 1 and the first --more (tier b) -> (both prints, look.json)."""
        out = self.out_of(path)
        shutil.rmtree(out, ignore_errors=True)
        base = [str(path), "--out", str(out)] + ([] if tools else ["--no-tools"])
        a = run(base + ["--fresh"])
        self.assertIn(a.returncode, ok, a.stderr[-1500:] + a.stdout[-800:])
        b = run(base + ["--more"])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return a.stdout + "\n" + b.stdout, lj

    def find_line(self, text):
        ln = next((x for x in text.splitlines() if "Find one record:" in x), None)
        self.assertIsNotNone(ln, "no 'Find one record' line in the first two prints:\n" + text[:1500])
        return ln

    def ask(self, path, question, tools=False, env=None, full=False):
        """One --ask on a look already made by prints() -> the 'Answer' lines (with `full`: everything printed from the first one on)."""
        r = run([str(path), "--out", str(self.out_of(path)), "--ask", question] + ([] if tools else ["--no-tools"]), env=env)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        lines = r.stdout.splitlines()
        first = next((k for k, x in enumerate(lines) if x.startswith("Answer")), None)
        self.assertIsNotNone(first, "no Answer line:\n" + r.stdout[:2000])
        return "\n".join(lines[first:] if full else [x for x in lines if x.startswith("Answer")])

    def no_crash(self, lj):
        self.assertNotIn("INTERNAL-ERROR", {f["kind"] for f in lj.get("flags", [])}, lj.get("flags"))


# ------------------------------------------------------------------ cp1251 text: a title block, a tab table, decimal commas
def milk_volume(k):
    return round(18.5 + (k * 37 % 4000) / 10, 1)


def milk_txt(n=70):
    cols = ["Запис", "Дата", "Постачальник", "Жирність, %", "Об'єм, л", "Ціна, грн/л", "Примітка"]
    rows = []
    for k in range(1, n + 1):
        rows.append("\t".join([f"МЗ-{k:04d}", f"{k % 28 + 1:02d}.03.2025", f"Коваленко {chr(0x410 + k % 20)}.", f"{3 + k % 150 / 100:.2f}".replace(".", ","),
                               f"{milk_volume(k):.1f}".replace(".", ","), f"{16 + k % 5 * 0.5:.2f}".replace(".", ","), "відхилено" if k % 6 == 0 else ""]))
    head = ["ЖУРНАЛ ПРИЙМАННЯ МОЛОКА", "Пункт «Тест», ваги №3", "Період: з 01.03.2025 по 31.03.2025", "Журнал №: 614", "Приймальник: Олена, зміна Б", ""]
    tail = ["", f"Усього записів: {n}", "Підпис приймальника: ______"]
    return "\r\n".join(head + ["\t".join(cols)] + rows + tail).encode("cp1251")


class TextRecords(R11Base):
    def test_a_record_id_in_a_titled_table_is_located_and_answered(self):
        p = self.tmp / "journal.txt"
        p.write_bytes(milk_txt(70))
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("70 rows", ln)
        self.assertIn("Запис", ln)
        self.assertIn("МЗ-0001 .. МЗ-0070", ln)
        self.assertIn("--ask", ln)
        ans = self.ask(p, "What volume in litres (Об'єм, л) is recorded for the record МЗ-0038? One decimal.")
        self.assertIn(f"{milk_volume(38):.1f}".replace(".", ","), ans)   # the decimal comma comes back as the file writes it (fix round 15)
        self.assertNotIn("matching rows", ans.replace("1 matching row", ""), "one record, not a list")

    def test_the_record_id_without_a_hyphen_or_in_latin_letters_still_hits_one_row(self):
        p = self.tmp / "journal2.txt"
        p.write_bytes(milk_txt(70))
        self.prints(p)
        ans = self.ask(p, "Об'єм, л of the record mz0007")
        self.assertIn(f"{milk_volume(7):.1f}".replace(".", ","), ans)   # the decimal comma comes back as the file writes it (fix round 15)


# ------------------------------------------------------------------ gettext .mo and .po
WEEK = [("Monday", "mandag"), ("Tuesday", "tirsdag"), ("Wednesday", "onsdag"), ("Thursday", "torsdag"), ("Friday", "fredag"), ("Saturday", "lørdag"), ("Sunday", "søndag")]


def catalogue(n=40):
    """-> [(msgid, msgstr, plural msgid or None, context or None, fuzzy)] sorted by msgid."""
    rows = [(w, d, None, None, False) for w, d in WEEK]
    rows += [(f"Sentence number {k}", f"Sætning nummer {k}", None, None, k % 11 == 0) for k in range(1, n - 10)]
    rows += [("%d file", "%d fil\0%d filer", "%d files", None, False), ("Close", "Luk", None, "button", False)]
    return sorted(rows, key=lambda r: ((r[3] + "\x04" if r[3] else "") + r[0]))


def mo_bytes(rows):
    ents = [(b"", "Content-Type: text/plain; charset=UTF-8\nLanguage: da\nPlural-Forms: nplurals=2; plural=(n != 1);\n".encode())]
    for msgid, msgstr, plural, ctx, _ in rows:
        o = ((ctx + "\x04") if ctx else "") + msgid + (("\0" + plural) if plural else "")
        ents.append((o.encode(), msgstr.encode()))
    n = len(ents)
    oo, to = 28, 28 + 8 * n
    pos = to + 8 * n
    otab, ttab, blob = b"", b"", b""
    for o, t in ents:
        otab += struct.pack("<II", len(o), pos + len(blob))
        blob += o + b"\0"
        ttab += struct.pack("<II", len(t), pos + len(blob))
        blob += t + b"\0"
    return struct.pack("<7I", 0x950412DE, 0, n, oo, to, 0, 0)[:28] + otab + ttab + blob


def po_text(rows):
    out = ['msgid ""', 'msgstr ""', '"Content-Type: text/plain; charset=UTF-8\\n"', '"Language: da\\n"', '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"', ""]
    for msgid, msgstr, plural, ctx, fuzzy in rows:
        out.append("#: app/views.py:%d" % (len(msgid) + 3))
        if fuzzy:
            out.append("#, fuzzy")
        if ctx:
            out.append(f'msgctxt "{ctx}"')
        out.append(f'msgid "{msgid}"')
        if plural:
            a, b = msgstr.split("\0")
            out += [f'msgid_plural "{plural}"', f'msgstr[0] "{a}"', f'msgstr[1] "{b}"']
        else:
            out.append(f'msgstr "{msgstr}"')
        out.append("")
    return "\n".join(out).encode()


class Gettext(R11Base):
    def test_mo_translation_of_a_quoted_original_text(self):
        p = self.tmp / "da.mo"
        p.write_bytes(mo_bytes(catalogue()))
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("msgid", ln)
        self.assertIn("--ask", ln)
        ans = self.ask(p, "What is the translation stored for the original text 'Friday'?")
        self.assertIn("fredag", ans)
        self.assertNotIn("mandag", ans)

    def test_po_translation_plural_forms_and_fuzzy_flag(self):
        p = self.tmp / "da.po"
        p.write_bytes(po_text(catalogue()))
        text, lj = self.prints(p)
        self.no_crash(lj)
        self.find_line(text)
        self.assertIn("fredag", self.ask(p, "translation for the original text 'Friday'"))
        plural = self.ask(p, "translation for the original text '%d file'")
        self.assertIn("%d fil", plural)
        self.assertIn("%d filer", plural)
        fz = self.ask(p, "translation of the original text 'Sentence number 11'", full=True)   # entry 11 is flagged fuzzy
        self.assertIn("Sætning nummer 11", fz.splitlines()[0])
        self.assertIn("flags = fuzzy", fz)

    def test_damaged_catalogues_never_crash(self):
        for k, b in enumerate(mutants(mo_bytes(catalogue()), 6, 31)):
            p = self.tmp / f"fz{k}.mo"
            p.write_bytes(b)
            _, lj = self.prints(p, ok=(0, 1, 3))
            self.no_crash(lj)
            run([str(p), "--out", str(self.out_of(p)), "--ask", "translation for the original text 'Friday'", "--no-tools"])


# ------------------------------------------------------------------ Java .properties
def properties_text(n=36):
    lines = ["# message catalogue", "app.title = Meu Aplicativo", ""]
    for k in range(1, n + 1):
        if k % 9 == 0:
            lines += [f"menu.msg.{k:03d} = Primeira parte da frase {k}, \\", "    segunda parte com acentua\\u00e7\\u00e3o \\", f"    e fim {k}."]
        else:
            lines.append(f"menu.msg.{k:03d} = Mensagem simples n.º {k}")
    return ("\n".join(lines) + "\n").encode("utf-8")


class Properties(R11Base):
    def test_value_of_a_quoted_key_after_continuations_and_escapes(self):
        p = self.tmp / "mensagens.properties"
        p.write_bytes(properties_text())
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("37 keys", ln)
        self.assertIn("first app.title", ln)
        self.assertIn("last menu.msg.036", ln)
        ans = self.ask(p, "value of key 'menu.msg.018' after line continuations are joined")
        self.assertIn("Primeira parte da frase 18, segunda parte com acentuação e fim 18.", ans)
        self.assertIn("Mensagem simples n.º 20", self.ask(p, "what is the value of key 'menu.msg.020'"))


# ------------------------------------------------------------------ subtitles
def cues(n=60):
    out = []
    for k in range(1, n + 1):
        a = 2 + k * 4.5
        lines = [f"- Frase numero {k}!"] + ([f"- Seconda riga {k}"] if k % 3 == 0 else [])
        out.append((a, a + 3.2, lines))
    return out


def vtt_stamp(t):
    return f"{int(t // 3600):02d}:{int(t // 60) % 60:02d}:{t % 60:06.3f}"


class Subtitles(R11Base):
    def write(self, kind):
        cs = cues()
        if kind == "sbv":
            txt = "\n".join(f"{sbv_stamp(a)},{sbv_stamp(b)}\n" + "\n".join(ls) + "\n" for a, b, ls in cs)
        elif kind == "srt":
            txt = "\n".join(f"{k}\n{vtt_stamp(a).replace('.', ',')} --> {vtt_stamp(b).replace('.', ',')}\n" + "\n".join(ls) + "\n" for k, (a, b, ls) in enumerate(cs, 1))
        else:
            txt = "WEBVTT\n\n" + "\n".join(f"{vtt_stamp(a)} --> {vtt_stamp(b)}\n" + "\n".join(ls) + "\n" for a, b, ls in cs)
        p = self.tmp / f"talk.{kind}"
        p.write_bytes(txt.encode("utf-8"))
        return p, cs

    def test_cue_number_selects_that_cue_in_sbv_srt_and_vtt(self):
        for kind in ("sbv", "srt", "vtt"):
            with self.subTest(kind=kind):
                p, cs = self.write(kind)
                text, lj = self.prints(p)
                self.no_crash(lj)
                ln = self.find_line(text)
                self.assertIn("60 cues", ln)
                self.assertIn("--ask", ln)
                ans = self.ask(p, "first line of cue number 42")
                self.assertIn(cs[41][2][0], ans)
                self.assertNotIn(cs[0][2][0], ans, "cue 1 is not cue 42")
                when = self.ask(p, "start time of cue 7")
                self.assertIn(sbv_stamp(cs[6][0]).split(":", 1)[1], when.replace(",", "."))


# ------------------------------------------------------------------ SAS transport (the same reader path as .sas7bdat)
def ibm(x):
    if x == 0:
        return b"\0" * 8
    sign = 0x80 if x < 0 else 0
    x = abs(x)
    e = 0
    while x >= 1:
        x /= 16
        e += 1
    while x < 1 / 16:
        x *= 16
        e -= 1
    m = int(round(x * (1 << 56)))
    if m >= 1 << 56:
        m >>= 4
        e += 1
    return bytes([sign | (e + 64)]) + m.to_bytes(7, "big")


def xpt_bytes(name, cols, rows):
    """cols [(name, 'n' or 'c', width)]; rows list of tuples. A SAS XPORT v5 file."""
    def rec(s):
        return s.ljust(80).encode()
    stamp = "01JAN26:00:00:00"
    out = rec("HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!000000000000000000000000000000  ")
    out += rec("SAS     SAS     SASLIB  9.4     X64_7PRO" + " " * 24 + stamp) + rec(stamp)
    out += rec("HEADER RECORD*******MEMBER  HEADER RECORD!!!!!!!000000000000000001600000000140  ")
    out += rec("HEADER RECORD*******DSCRPTR HEADER RECORD!!!!!!!000000000000000000000000000000  ")
    out += rec(f"SAS     {name:<8}SASDATA 9.4     X64_7PRO" + " " * 24 + stamp) + rec(stamp)
    out += rec(f"HEADER RECORD*******NAMESTR HEADER RECORD!!!!!!!000000{len(cols):04d}00000000000000000000  ")
    ns, pos = b"", 0
    for i, (nm, kind, w) in enumerate(cols, 1):
        w = 8 if kind == "n" else w
        ns += struct.pack(">hhhh8s40s8shhh2s8shhl52s", 1 if kind == "n" else 2, 0, w, i, nm.ljust(8).encode(), nm.ljust(40).encode(), b" " * 8, 0, 0, 0, b"  ", b" " * 8, 0, 0, pos, b"\0" * 52)
        pos += w
    out += ns + b" " * (-len(ns) % 80)
    out += rec("HEADER RECORD*******OBS     HEADER RECORD!!!!!!!000000000000000000000000000000  ")
    body = b""
    for r in rows:
        for (nm, kind, w), v in zip(cols, r):
            body += ibm(v) if kind == "n" else str(v).encode().ljust(w)
    return out + body + b" " * (-len(body) % 80)


def petal_rows(n=150):
    return [(k + 1, round(1 + (k * 17 % 60) / 10, 1), round(0.1 + (k * 7 % 25) / 10, 1), ("setosa", "versicolor", "virginica")[k % 3]) for k in range(n)]


@unittest.skipUnless(HAVE_PANDAS, "pandas reads SAS files")
class Sas(R11Base):
    def test_rows_of_a_sas_file_are_counted_by_ask(self):
        rows = petal_rows()
        p = self.tmp / "petals.xpt"
        p.write_bytes(xpt_bytes("PETALS", [("OBSNO", "n", 8), ("PETALLEN", "n", 8), ("PETALWID", "n", 8), ("SPECIES", "c", 12)], rows))
        text, lj = self.prints(p, tools=True)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("150 rows", ln)
        self.assertIn("OBSNO (unique, 1 .. 150)", ln)
        want = sum(1 for r in rows if r[1] > 5.0)
        ans = self.ask(p, "In how many rows is PETALLEN greater than 5.0?", tools=True)
        self.assertIn(f"{want}", ans.split("Answer:", 1)[1].split()[0])
        self.assertIn(f"{rows[76][1]:g}", self.ask(p, "PETALLEN of the row with OBSNO 77", tools=True))


# ------------------------------------------------------------------ SPSS .sav
def sav_bytes(names, rows, strcols=(), label="r11 test"):
    """An uncompressed SPSS system file. names: 8-letter variable names; strcols: indexes of 8-byte string variables."""
    nv = len(names)
    h = b"$FL2" + b"@(#) SPSS DATA FILE - r11 test".ljust(60) + struct.pack("<iiiii", 2, nv, 0, 0, len(rows)) + struct.pack("<d", 100.0)
    h += b"01 Jan 26" + b"00:00:00" + label.encode().ljust(64) + b"\0\0\0"
    for i, nm in enumerate(names):
        h += struct.pack("<iiiiii", 2, 8 if i in strcols else 0, 0, 0, 0x050800 if i not in strcols else 0x010800, 0x050800 if i not in strcols else 0x010800) + nm.ljust(8).encode()
    h += struct.pack("<ii", 999, 0)
    body = b""
    for r in rows:
        for i, v in enumerate(r):
            body += str(v).encode().ljust(8)[:8] if i in strcols else struct.pack("<d", v)
    return h + body


class SavRecords(R11Base):
    NAMES = ["visit_id", "clinic", "age", "cost_eur"]

    def rows(self, n):
        return [(7_000_000 + k, f"CL-{k % 40:04d}", 18 + k % 70, round(5 + (k * 13 % 40000) / 100, 2)) for k in range(1, n + 1)]

    def check(self, n, env=None):
        rows = self.rows(n)
        p = self.tmp / f"visits{n}.sav"
        p.write_bytes(sav_bytes(self.NAMES, rows, strcols=(1,)))
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("visit_id", ln)
        self.assertIn(f"{rows[0][0]:,} .. {rows[-1][0]:,}", ln)
        target = rows[n // 2 + 3]
        t0 = time.time()
        ans = self.ask(p, f"cost_eur of the visit with visit_id {target[0]}", env=env)
        self.assertIn(f"{target[3]:g}", ans)
        self.assertLess(time.time() - t0, 30)

    def test_visit_id_lookup_in_a_small_sav(self):
        self.check(300)

    def test_visit_id_lookup_streams_a_big_sav_without_loading_it(self):
        self.check(4000, env={"SIGMADEEPLOOK_ASK_STREAM_CAP": "2000"})


# ------------------------------------------------------------------ netCDF grid cell by index
def packed_nc(nt=40, ns=20):
    raw = [[(t * 31 + s * 17) % 3000 - 1500 for s in range(ns)] for t in range(nt)]
    raw[nt - 1][5] = -32767   # a fill value
    q = b"".join(struct.pack(">h", v) for row in raw for v in row)
    nc = nc_file([("time", 0), ("station", ns)], [("title", "r11 grid")],
                 [("time", [0], 4, [("units", "days since 2020-01-01")], b"".join(struct.pack(">i", t) for t in range(nt))),
                  ("station_id", [1], 4, [], b"".join(struct.pack(">i", 900 + s) for s in range(ns))),
                  ("discharge", [0, 1], 3, [("units", "m3 s-1"), ("scale_factor", 0.01), ("add_offset", 700.0), ("_FillValue", (3, [-32767]))], q)], nt)
    return nc, raw


class NetcdfCells(R11Base):
    def test_cell_by_index_unpacked_and_a_fill_value_named(self):
        nc, raw = packed_nc()
        p = self.tmp / "gauges.nc"
        p.write_bytes(nc)
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("discharge", ln)
        self.assertIn("time", ln)
        self.assertIn("station", ln)
        self.assertIn("40", ln)
        self.assertIn("20", ln)
        want = raw[39][17] * 0.01 + 700.0
        ans = self.ask(p, "discharge at the last time index (day 39, counting from 0) for station index 17, 2 decimals")
        self.assertIn(f"{want:.2f}", ans)
        want = raw[12][3] * 0.01 + 700.0
        self.assertIn(f"{want:.2f}", self.ask(p, "discharge at time index 12 and station index 3"))
        self.assertIn("fill", self.ask(p, "discharge at time index 39 and station index 5").lower())

    def test_cell_by_coordinate_value(self):
        nc, raw = packed_nc()
        p = self.tmp / "gauges2.nc"
        p.write_bytes(nc)
        self.prints(p)
        want = raw[25][7] * 0.01 + 700.0
        self.assertIn(f"{want:.2f}", self.ask(p, "discharge on time 25 at station_id 907"))

    def test_damaged_files_never_crash(self):
        nc, _ = packed_nc()
        for k, b in enumerate(mutants(nc, 6, 12)):
            p = self.tmp / f"fz{k}.nc"
            p.write_bytes(b)
            _, lj = self.prints(p, ok=(0, 1, 3))
            self.no_crash(lj)
            run([str(p), "--out", str(self.out_of(p)), "--ask", "discharge at time index 3 and station index 2", "--no-tools"])


# ------------------------------------------------------------------ SQLite / GeoPackage
class GpkgRecords(R11Base):
    def test_unique_text_key_in_a_database_table(self):
        p = self.tmp / "registry.gpkg"
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE survey_marks (fid INTEGER PRIMARY KEY, mark_code TEXT, mark_type TEXT, elevation_m REAL, checked INTEGER)")
        con.execute("CREATE TABLE owners (id INTEGER PRIMARY KEY, full_name TEXT, share_pct REAL)")
        con.executemany("INSERT INTO survey_marks VALUES (?,?,?,?,?)", [(k, f"SM-{k:05d}", ("pillar", "bolt", "stone")[k % 3], round(100 + k * 0.37 % 900, 2), k % 2) for k in range(1, 401)])
        con.executemany("INSERT INTO owners VALUES (?,?,?)", [(k, f"Owner {k}", k % 100) for k in range(1, 3000)])
        con.commit()
        con.close()
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("survey_marks", ln)
        self.assertIn("400 rows", ln)
        self.assertIn("mark_code", ln)
        self.assertIn("SM-00001 .. SM-00400", ln)
        self.assertIn("--sql", ln)
        want = round(100 + 321 * 0.37 % 900, 2)
        ans = self.ask(p, "elevation_m of the survey mark with mark_code 'SM-00321'")
        self.assertIn(f"{want:g}", ans)
        self.assertNotIn("Owner", ans)


# ------------------------------------------------------------------ worksheets and JSON Lines
class SheetsAndLines(R11Base):
    def test_worksheet_key_is_located_and_answered(self):
        rows = [["order_id", "region", "total"]] + [[f"B-{1000 + i}", ("north", "south", "east")[i % 3], 10 + i * 3 % 97] for i in range(1, 61)]
        strings = sorted({v for r in rows for v in r if isinstance(v, str)})
        p = self.tmp / "orders.xlsb"
        p.write_bytes(xlsb_bytes([("Orders", 0, rows)], strings))
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("Orders", ln)
        self.assertIn("order_id", ln)
        self.assertIn("B-1001 .. B-1060", ln)
        self.assertIn(f"{rows[33][2]}", self.ask(p, "total of the order with order_id 'B-1033'"))

    def test_jsonl_key_is_located_and_answered(self):
        recs = [{"ticket": f"T-{k:04d}", "who": f"user{k % 9}", "minutes": k * 7 % 90} for k in range(1, 81)]
        p = self.tmp / "tickets.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
        text, lj = self.prints(p)
        self.no_crash(lj)
        ln = self.find_line(text)
        self.assertIn("ticket", ln)
        self.assertIn("T-0001 .. T-0080", ln)
        self.assertIn(f"{recs[54]['minutes']}", self.ask(p, "minutes of the ticket 'T-0055'").split("Answer:", 1)[1].split("\n")[0])

    def test_a_table_without_a_unique_key_prints_no_find_line(self):
        p = self.tmp / "nokey.csv"
        p.write_text("a,b\n" + "\n".join(f"{k % 5},{k % 7}" for k in range(60)) + "\n", encoding="utf-8")
        text, _ = self.prints(p)
        self.assertNotIn("Find one record", text)


class AskReview(R11Base):
    def test_a_comparison_names_the_column_whose_whole_name_stands_before_it(self):
        rows = [(k, 1 + k * 17 % 60 / 10, 2 + k * 7 % 40 / 10) for k in range(1, 61)]
        p = self.tmp / "twins.csv"
        p.write_text("id,petal_length,sepal_length\n" + "\n".join(f"{a},{b:.1f},{c:.1f}" for a, b, c in rows) + "\n", encoding="utf-8")
        self.prints(p)
        want = sum(1 for r in rows if float(f"{r[1]:.1f}") > 5.0)
        self.assertNotEqual(want, sum(1 for r in rows if float(f"{r[2]:.1f}") > 5.0), "the two columns must differ")
        self.assertIn(f"Answer: {want} ", self.ask(p, "In how many rows is petal_length greater than 5.0?"))

    def test_a_bare_number_in_a_comparison_is_not_taken_for_a_text_key(self):
        p = self.tmp / "mixed.csv"
        p.write_text("code,qty\n" + "\n".join(f"{50 if k == 3 else 100 + k},{k}" for k in range(1, 40)) + "\n", encoding="utf-8")
        self.prints(p)
        self.assertIn("Answer: 34 ", self.ask(p, "How many rows have qty over 5.0?"))

    def test_a_year_after_a_measure_column_is_not_taken_for_a_key(self):
        p = self.tmp / "years.csv"
        p.write_text("year,region,sales\n" + "\n".join(f"{y},{r},{100 + y % 7 * 10 + i}" for y in (2020, 2021, 2022) for i, r in enumerate("NSEW")) + "\n", encoding="utf-8")
        self.prints(p)
        want = sum(100 + y % 7 * 10 + i for y in (2020, 2021, 2022) for i in range(4))
        self.assertIn(f"{want:,} over 12", self.ask(p, "total sales 2021"))

    def test_secret_like_property_values_stay_hidden(self):
        p = self.tmp / "secrets.properties"
        p.write_text("\n".join(f"key.{k:02d} = value {k}" for k in range(12)) + "\ndb.password = hunter2hunter\n", encoding="utf-8")
        self.prints(p)
        r = self.ask(p, "value of key 'db.password'", full=True)
        self.assertNotIn("hunter2", r)


class Fuzz(R11Base):
    def test_damaged_copies_never_crash_the_look_or_the_ask(self):
        sbv = "\n".join(f"{sbv_stamp(a)},{sbv_stamp(b)}\n" + "\n".join(ls) + "\n" for a, b, ls in cues(30)).encode()
        sources = {"journal.txt": milk_txt(40), "da.po": po_text(catalogue()), "m.properties": properties_text(), "t.sbv": sbv,
                   "v.sav": sav_bytes(SavRecords.NAMES, SavRecords().rows(60), strcols=(1,)),
                   "p.xpt": xpt_bytes("PETALS", [("OBSNO", "n", 8), ("PETALLEN", "n", 8), ("PETALWID", "n", 8), ("SPECIES", "c", 12)], petal_rows(40))}
        for name, data in sources.items():
            for k, b in enumerate(mutants(data, 6, 21)):
                p = self.tmp / f"fz{k}_{name}"
                p.write_bytes(b)
                _, lj = self.prints(p, ok=(0, 1, 3), tools=name.endswith("xpt") and HAVE_PANDAS)
                self.no_crash(lj)
                r = run([str(p), "--out", str(self.out_of(p)), "--ask", "value of key 'menu.msg.003' and first line of cue number 3 for visit_id 7000003", "--no-tools"])
                self.assertEqual(r.returncode, 0, name + r.stderr[-800:])
                self.assertNotIn("Traceback", r.stdout + r.stderr, name)


if __name__ == "__main__":
    unittest.main()
