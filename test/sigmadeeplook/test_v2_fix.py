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


# ------------------------------------------------------------------------------------------------ audio: speech over a bed
def synth_pcm(bed_db=None, seconds=40, seed=3):
    """16 kHz mono 16-bit: word-like noise bursts with pauses, optionally over a steady tonal pad. -> bytes"""
    import numpy as np
    rng = np.random.default_rng(seed)
    sr = 16000
    n = seconds * sr
    x = rng.normal(0, 1e-4, n)                       # room floor near -80 dB
    t = 0
    while t < n - sr:
        L = int(sr * rng.uniform(0.25, 0.6))
        env = np.hanning(L)
        tt = np.arange(L) / sr
        burst = sum(np.sin(2 * np.pi * f * tt + rng.uniform(0, 6)) * rng.uniform(0.3, 1) for f in rng.uniform(150, 3000, 12))
        x[t:t + L] += 0.04 * env * burst / 4
        t += L + int(sr * rng.uniform(0.2, 0.45))
    if bed_db is not None:
        tt = np.arange(n) / sr
        amp = 10 ** (bed_db / 20)
        x += amp * (np.sin(2 * np.pi * 110 * tt) + 0.7 * np.sin(2 * np.pi * 165 * tt) + 0.5 * np.sin(2 * np.pi * 220 * tt))
    return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()


@unittest.skipUnless(have("numpy"), "numpy not installed")
class MusicBed(unittest.TestCase):
    def test_voice_over_a_tonal_bed_is_told_from_clean_speech(self):
        import dl_mediax as M
        clean = M.bed_features(synth_pcm(None))
        bed = M.bed_features(synth_pcm(-34))
        self.assertEqual(M.bed_verdict(clean, True), "clean", clean)
        self.assertEqual(M.bed_verdict(bed, True), "bed", bed)
        self.assertGreater(bed["floor"], clean["floor"] + 20)

    def test_music_alone_is_not_called_speech_over_music(self):
        import numpy as np
        import dl_mediax as M
        n = 40 * 16000
        tt = np.arange(n) / 16000
        x = 0.05 * (np.sin(2 * np.pi * 110 * tt) * (1 + 0.3 * np.sin(2 * np.pi * 0.5 * tt)) + np.sin(2 * np.pi * 220 * tt))
        f = M.bed_features((x * 32767).astype("<i2").tobytes())
        self.assertEqual(M.bed_verdict(f, False), "music", f)

    def test_wav_end_to_end_reports_the_bed_fact(self):
        import shutil
        import wave
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg not installed")
        raw = synth_pcm(-34, seconds=45)
        d = Path(tempfile.mkdtemp(prefix="sdl-fix-")) / "vb.wav"
        with wave.open(str(d), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(raw)
        r, out, lj, _ = look(d, "--tier", "quick")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sound_bed", lj["facts"])


# ------------------------------------------------------------------------------------------------ quick tier
def csv_big(repeat_at=60000, rows=130000):
    lines = ["id,name,amount,status"]
    for i in range(1, rows + 1):
        if i == repeat_at:
            lines.append("id,name,amount,status")
        lines.append(f"{i},customer number {i % 977},{(i * 7) % 1000}.5,{'shipped' if i % 3 else 'pending'}")
    return "\n".join(lines) + "\n"


class QuickTier(unittest.TestCase):
    def test_big_csv_is_counted_whole_and_profiled_on_a_sample(self):
        f = make("big.csv", csv_big())
        import dl_data
        self.assertGreater(f.stat().st_size, dl_data.QUICK_BYTES)
        r, out, lj, secs = look(f, "--tier", "quick")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("REPEATED-HEADER", kinds(lj))
        self.assertIn("QUICK-SAMPLE", kinds(lj))
        self.assertIn("130,000 data rows", r.stdout)
        self.assertRegex(r.stdout, r"REPEATED-HEADER\*\* @ line 60001")
        self.assertLess(secs, 20)

    def test_whole_file_scan_counts_lines_and_repeated_header(self):
        import dl_data
        raw = b"\xef\xbb\xbfa,b\n1,2\n3,4\na,b\n5,6\n"
        lines, rep = dl_data.whole_file_scan(raw)
        self.assertEqual(lines, 5)
        self.assertEqual(rep, [4])

    def test_sample_windows_and_gist(self):
        import dl_media as DM
        self.assertEqual(DM.sample_windows(60.0), [(0.0, 60.0)])
        w = DM.sample_windows(600.0)
        self.assertEqual(len(w), 3)
        self.assertTrue(all(0 <= a and a + ln <= 600.0 for a, ln in w))
        segs = [{"start": 0.0, "end": 4.0, "text": "This film asks whether one pod of power decides the whole race.", "words": []},
                {"start": 100.0, "end": 106.0, "text": "Huawei stacks eight thousand chips in one domain at enormous cost today.", "words": []},
                {"start": 500.0, "end": 507.0, "text": "In the end power is the limit but density decides the building you need.", "words": []}]
        g = DM.gist_lines(segs, 520.0, None)
        self.assertGreaterEqual(len(g), 2)
        self.assertTrue(g[0].startswith("[0:00] This film asks"))
        g2 = DM.gist_lines(segs, 520.0, [(90.0, 25.0), (490.0, 25.0)])
        self.assertEqual(len(g2), 2)

    def test_part_cache_round_trip_and_fresh_bypass(self):
        import types
        import dl_core as core
        old = os.environ.get("LOCALAPPDATA"), os.environ.get("XDG_CACHE_HOME")
        tmp = tempfile.mkdtemp(prefix="sdl-cache-")
        os.environ["LOCALAPPDATA"] = tmp
        os.environ["XDG_CACHE_HOME"] = tmp
        try:
            lk = types.SimpleNamespace(sha="ab" * 32, no_tools=False, opts=types.SimpleNamespace(fresh=False))
            self.assertIsNone(core.cache_get(lk, "asr-base"))
            core.cache_put(lk, "asr-base", {"segs": [1, 2]})
            self.assertEqual(core.cache_get(lk, "asr-base"), {"segs": [1, 2]})
            lk.opts.fresh = True
            self.assertIsNone(core.cache_get(lk, "asr-base"))
        finally:
            for k, v in zip(("LOCALAPPDATA", "XDG_CACHE_HOME"), old):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


# ------------------------------------------------------------------------------------------------ writer
class Writer(unittest.TestCase):
    def test_duplicate_rows_siblings_and_excerpts_are_merged(self):
        import argparse
        import dl_core as core
        import dl_write as W
        out = Path(tempfile.mkdtemp(prefix="sdl-w-"))
        lk = core.Look(out / "x.bin", out, argparse.Namespace(tier="standard"))
        lk.type, lk.subtype, lk.sha, lk.size = "data", "csv", "0" * 64, 10
        body = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma"
        lk.write_text("text.md", body, "the text", value=6)
        lk.excerpt("Text start", body, 3, 500)
        for i in (1, 2, 3, 4):
            (out / "sheets").mkdir(exist_ok=True)
            lk.write_text(f"sheets/S{i}.csv", "a,b\n1,2\n", f"sheet {i} as CSV")
        lk.write_text("sheets/S1.csv", "a,b\n1,2\n", "sheet S1 again")
        stream = W.build_stream(lk)
        text = "\n".join(c["text"] for c in stream)
        self.assertIn("`sheets/` (4 files", text)
        self.assertEqual(sum(1 for c in stream if c["sec"] == "key" and "Text start" in c["text"]), 0)
        self.assertEqual(sum(1 for c in stream if c["sec"] == "content" and "alpha beta" in c["text"]), 1)



# ------------------------------------------------------------------------------------------------ speakers
class Speakers(unittest.TestCase):
    def test_speaker_line_renames_and_counts(self):
        import types
        import dl_core as core
        import dl_mediax as MX
        lk = core.Look.__new__(core.Look)
        lines, facts = [], {}
        lk.line = lambda text, pri=50, *a, **k: lines.append(text)
        lk.fact = lambda k, v: facts.__setitem__(k, v)
        turns = [{"speaker": "SPEAKER_07", "start": 0, "end": 30}, {"speaker": "SPEAKER_02", "start": 30, "end": 40}, {"speaker": "SPEAKER_07", "start": 40, "end": 70}]
        MX.speaker_line(lk, turns)
        self.assertEqual(facts["speakers"], 2)
        self.assertEqual([t["speaker"] for t in turns], ["S1", "S2", "S1"])
        self.assertIn("2 voices", lines[0])
        self.assertIn("S1 86%", lines[0])
        self.assertIn("2 changes of speaker", lines[0])

    def test_pyannote_needs_config_not_just_a_readme(self):
        import dl_models as M
        hub = Path(tempfile.mkdtemp(prefix="sdl-hf-"))
        snap = hub / "hub" / M.HF_DIRS["pyannote"] / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "README.md").write_text("gated")
        old = os.environ.get("HF_HOME")
        os.environ["HF_HOME"] = str(hub)
        try:
            self.assertFalse(M.have_model("pyannote"))
            (snap / "config.yaml").write_text("pipeline: {}")
            self.assertTrue(M.have_model("pyannote"))
        finally:
            if old is None:
                os.environ.pop("HF_HOME", None)
            else:
                os.environ["HF_HOME"] = old

if __name__ == "__main__":
    unittest.main()
