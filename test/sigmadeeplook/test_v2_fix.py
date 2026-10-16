"""SigmaDeepLook v2 fix round (ticket 83 P0.14): traps that must be in the first print, on generated files.

Every fixture is made here (nothing downloaded, nothing executed). A trap counts as caught when the FIRST print (step 1) says it.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "sigmadeeplook" / "scripts"
LOOK = SCRIPTS / "look.py"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))


def run(args, hide=""):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    if hide:
        e["SIGMADEEPLOOK_HIDE"] = hide
    return subprocess.run([sys.executable, str(LOOK), *args], capture_output=True, text=True, encoding="utf-8", env=e, timeout=600)


def make(name, data):
    d = Path(tempfile.mkdtemp(prefix="sdl-fix-"))
    f = d / name
    f.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return f


def look(f, *extra):
    out = tempfile.mkdtemp(prefix="sdl-fixout-")
    t = time.time()
    r = run([str(f), "--out", out, "--fresh", "--no-direct", *extra])
    lj = json.loads((Path(out) / "look.json").read_text(encoding="utf-8")) if (Path(out) / "look.json").exists() else None
    return r, Path(out), lj, time.time() - t


def kinds(lj):
    return {x["kind"] for x in lj["flags"]}


def have(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ subtitles
def srt_text():
    cues = []
    t = 0.0

    def ts(x):
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x % 1 * 1000):03d}"
    for i in range(1, 61):
        a, b = t, t + 2.0
        text = f"Line number {i} of the test captions."
        if i == 10:
            a, b = t + 2.0, t + 0.5          # ends before it starts
        if i == 20:
            a = t - 1.2                       # starts before the previous cue ends
        if i == 30:
            text = "cafÃ© â€™ broken"
        cues.append(f"{i}\n{ts(max(0, a))} --> {ts(max(0, b))}\n{text}\n")
        t += 3.0
        if i == 40:
            t += 50
    return "\n".join(cues)


class Subtitles(unittest.TestCase):
    def test_defects_have_cue_numbers_in_the_first_print(self):
        r, out, lj, _ = look(make("t.srt", srt_text()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue({"INVERTED-CUE", "OVERLAPPING-CUES", "MOJIBAKE"} <= kinds(lj), kinds(lj))
        head = r.stdout.split("## Content")[0]
        self.assertRegex(head, r"INVERTED-CUE\*\* @ #10 ")
        self.assertRegex(head, r"OVERLAPPING-CUES\*\* @ #20 ")
        self.assertRegex(head, r"MOJIBAKE\*\* @ #30 ")
        self.assertRegex(head, r"longest 5\d s before cue #41")


# ------------------------------------------------------------------------------------------------ docx
def docx_bytes(vanish=True, template=True):
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    hid = '<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>SECRET margin is forty percent</w:t></w:r></w:p>' if vanish else ""
    body = (f'<w:document {W}><w:body><w:p><w:r><w:t>Visible paragraph.</w:t></w:r></w:p>{hid}'
            '<w:p><w:ins w:id="1" w:author="Ann" w:date="2026-01-01T00:00:00Z"><w:r><w:t>added</w:t></w:r></w:ins>'
            '<w:del w:id="2" w:author="Bob" w:date="2026-01-02T00:00:00Z"><w:r><w:delText>$250,000</w:delText></w:r></w:del></w:p></w:body></w:document>')
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    srel = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" '
            'Target="https://templates.example.net/corp.dotm" TargetMode="External"/></Relationships>')
    import io
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", body)
        if template:
            z.writestr("word/settings.xml", f'<w:settings {W}/>')
            z.writestr("word/_rels/settings.xml.rels", srel)
    return bio.getvalue()


class Docx(unittest.TestCase):
    def test_hidden_text_remote_template_and_counts(self):
        r, out, lj, _ = look(make("a.docx", docx_bytes()), "--tier", "quick")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue({"HIDDEN-TEXT", "REMOTE-TEMPLATE", "TRACKED-CHANGES"} <= kinds(lj), kinds(lj))
        head = r.stdout.split("## Content")[0]
        self.assertIn("SECRET margin is forty percent", head)
        self.assertIn("templates.example.net", head)
        self.assertRegex(head, r"2 tracked changes \(1 inserted, 1 deleted\)")

    def test_clean_docx_has_no_such_flags(self):
        r, out, lj, _ = look(make("b.docx", docx_bytes(vanish=False, template=False)), "--tier", "quick")
        self.assertFalse({"HIDDEN-TEXT", "REMOTE-TEMPLATE"} & kinds(lj), kinds(lj))


# ------------------------------------------------------------------------------------------------ pdf
class Pdf(unittest.TestCase):
    @unittest.skipUnless(have("fitz"), "PyMuPDF not installed")
    def test_long_pdf_without_outline_is_flagged(self):
        import fitz
        doc = fitz.open()
        for i in range(25):
            p = doc.new_page()
            p.insert_text((72, 72), f"Plain text page number {i + 1} " * 3)
        d = Path(tempfile.mkdtemp(prefix="sdl-fix-")) / "flat.pdf"
        doc.save(str(d))
        r, out, lj, _ = look(d, "--tier", "quick")
        self.assertIn("NO-OUTLINE", kinds(lj))
        self.assertIn("0 bookmarks", r.stdout.split("## Read next")[0])
        doc = fitz.open()
        for i in range(25):
            doc.new_page().insert_text((72, 72), f"Chapter {i}")
        doc.set_toc([[1, "Chapter 1", 1], [1, "Chapter 2", 5]])
        d2 = Path(tempfile.mkdtemp(prefix="sdl-fix-")) / "toc.pdf"
        doc.save(str(d2))
        r2, out2, lj2, _ = look(d2, "--tier", "quick")
        self.assertNotIn("NO-OUTLINE", kinds(lj2))


# ------------------------------------------------------------------------------------------------ sqlite
def make_db(declared_fk, orphans=False):
    d = Path(tempfile.mkdtemp(prefix="sdl-fix-"))
    f = d / "x.sqlite"
    con = sqlite3.connect(f)
    fk = ", FOREIGN KEY(customer_id) REFERENCES customers(id)" if declared_fk else ""
    con.execute("create table customers(id integer primary key, name text, created_at integer)")
    con.execute(f"create table orders(id integer primary key, customer_id integer, total real{fk})")
    con.execute("create table items(id integer primary key, order_id integer, sku text)")
    con.executemany("insert into customers values (?,?,?)", [(i, f"c{i}", 1760000000 + i * 3600) for i in range(1, 51)])
    con.executemany("insert into orders values (?,?,?)", [(i, 1 + i % 50, i * 1.5) for i in range(1, 301)])
    if orphans:
        con.executemany("insert into orders values (?,?,?)", [(1000 + i, 9000 + i, 1.0) for i in range(4)])
    con.executemany("insert into items values (?,?,?)", [(i, 1 + i % 300, f"sku{i}") for i in range(1, 1001)])
    con.commit()
    con.close()
    return f


class Sqlite(unittest.TestCase):
    def test_no_foreign_keys_and_row_counts_in_step_one(self):
        r, out, lj, _ = look(make_db(False))
        head = r.stdout.split("## Content")[0]
        self.assertIn("Foreign keys: none declared in 3 tables", head)
        self.assertIn("orders.customer_id~customers", head)
        self.assertIn("NO-FOREIGN-KEYS", kinds(lj))
        self.assertRegex(head, r"items 1000; orders 300; customers 50")
        self.assertIn("Time range", head)
        self.assertTrue((out / "tables.md").exists())
        self.assertIn("customers: 50 rows", (out / "tables.md").read_text(encoding="utf-8"))

    def test_declared_keys_and_orphan_check(self):
        r, out, lj, _ = look(make_db(True, orphans=True))
        head = r.stdout.split("## Content")[0]
        self.assertIn("Foreign keys: 1 declared (orders.customer_id->customers", head)
        self.assertIn("ORPHAN-ROWS", kinds(lj))
        self.assertRegex(head, r"ORPHAN-ROWS\*\* @ orders->customers: 4 child rows")
        r2, out2, lj2, _ = look(make_db(True, orphans=False))
        self.assertNotIn("ORPHAN-ROWS", kinds(lj2))
        self.assertIn("every declared key resolves", r2.stdout)

    def test_table_drill_says_none_declared(self):
        f = make_db(False)
        out = tempfile.mkdtemp(prefix="sdl-fixout-")
        run([str(f), "--out", out, "--fresh", "--no-direct"])
        r = run([str(f), "--out", out, "--table", "orders"])
        self.assertIn("foreign keys: none declared", r.stdout)


# ------------------------------------------------------------------------------------------------ parquet
class Parquet(unittest.TestCase):
    @unittest.skipUnless(have("pyarrow"), "pyarrow not installed")
    def test_statistics_nulls_and_outliers_in_step_one(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        n = 20000
        temp = [20.0 + (i % 50) / 10 for i in range(n)]
        for i in (5, 77, 901):
            temp[i] = 999.9
        batt = [None if i % 3 == 0 else 3.5 + (i % 10) / 100 for i in range(n)]
        t = pa.table({"id": list(range(n)), "temp_c": temp, "battery_v": batt})
        d = Path(tempfile.mkdtemp(prefix="sdl-fix-")) / "s.parquet"
        pq.write_table(t, str(d), write_statistics=False, row_group_size=5000)
        r, out, lj, _ = look(d)
        head = r.stdout.split("## Read next")[0]
        self.assertTrue({"NO-STATISTICS", "NULL-HEAVY", "OUTLIER"} <= kinds(lj), kinds(lj))
        self.assertRegex(head, r"OUTLIER\*\* @ temp_c: 3 value")
        self.assertRegex(head, r"battery_v[^;]*3[34]% null")
        pq.write_table(t, str(d.with_name("ok.parquet")), write_statistics=True, row_group_size=5000)
        r2, out2, lj2, _ = look(d.with_name("ok.parquet"))
        self.assertNotIn("NO-STATISTICS", kinds(lj2))


if __name__ == "__main__":
    unittest.main()
