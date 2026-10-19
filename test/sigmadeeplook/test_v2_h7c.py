"""Fix round H7, part 3: findings 6-16 of the generalisation review, on fixtures built here (none from a held-out set).

Every expected figure is worked out in the test from the data it wrote, never read back from the look.
Caps are lowered with SIGMADEEPLOOK_<NAME> variables so the over-the-cap path runs on a small file (a real one would be hundreds of MB).
"""
import importlib.util
import io
import json
import os
import shutil
import struct
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import dl_asklang  # noqa: E402
import dl_books  # noqa: E402
import dl_core as core  # noqa: E402
import dl_lex  # noqa: E402
import dl_logs  # noqa: E402
import dl_media  # noqa: E402
import dl_misc  # noqa: E402
import dl_pdffacts  # noqa: E402
import dl_util as U  # noqa: E402


def have(mod):
    return importlib.util.find_spec(mod) is not None


class H7c(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_h7c_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look(self, path, *extra, env=None, ok=(0,)):
        out = self.tmp / ("out_" + path.name)
        if out.exists():
            shutil.rmtree(out, ignore_errors=True)
        r = run([str(path), "--out", str(out), "--fresh", "--no-tools", *extra], env=env)
        self.assertIn(r.returncode, ok, r.stderr[-1500:] + r.stdout[-800:])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        stream = "\n".join(x["text"] for x in lj["stream"])
        return r.stdout, stream, lj, out

    def ask(self, path, out, q, env=None):
        r = run([str(path), "--out", str(out), "--no-tools", "--ask", q], env=env)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        return r.stdout

    # ------------------------------------------------------------ 16. token estimate
    def test_token_estimate_is_fair_to_non_ascii_letters(self):
        ascii_text = "x" * 400
        self.assertEqual(U.est_tokens(ascii_text), 100)
        german = "Größenvergleich der Straßenbahnen in München " * 10
        serbian = "Đorđe Šćekić živi u Čačku i radi u školi " * 10
        cyr = "Ђорђе Шћекић живи у Чачку и ради у школи " * 10
        for text, share in ((german, 0.99), (serbian, 0.8), (cyr, 0.5)):
            old = -(-sum(1 for c in text if ord(c) < 128) // 4) + sum(1 for c in text if ord(c) > 127)
            self.assertLess(U.est_tokens(text), old * share, text[:20])
            self.assertGreater(U.est_tokens(text), len(text) / 4 * 0.9)
        self.assertEqual(U.est_tokens("▁▂▃▄" * 10), 40, "sparkline characters stay one token each")
        self.assertEqual(U.est_tokens("中文文本" * 10), 40, "CJK stays one token per character")

    # ------------------------------------------------------------ 14. a syslog line has no year
    def test_syslog_years_follow_the_file_time_and_the_new_year(self):
        p = self.tmp / "auth.log"
        lines = []
        for d, mo in ((29, "Dec"), (30, "Dec"), (31, "Dec"), (1, "Jan"), (2, "Jan")):
            for h in range(3):
                lines.append(f"{mo} {d:2d} {h:02d}:10:0{h} host sshd[12]: Accepted password for user{h}")
        p.write_text("\n".join(lines) + "\n")
        import datetime
        t = datetime.datetime(2026, 1, 3, 12).timestamp()
        os.utime(p, (t, t))
        out, stream, lj, _ = self.look(p)
        self.assertIn("2025-12-29 00:10:00 to 2026-01-02 02:10:02", out)
        self.assertEqual([f for f in lj["flags"] if f["kind"] == "TIME-BACKWARDS"], [])
        # an old archive: the same lines, last written in March 2019, are 2019 and 2018
        t2 = datetime.datetime(2019, 1, 3, 12).timestamp()
        os.utime(p, (t2, t2))
        out2, _, _, _ = self.look(p)
        self.assertIn("2018-12-29 00:10:00 to 2019-01-02 02:10:02", out2)

    def test_sysyear_unit(self):
        p = self.tmp / "u.log"
        p.write_text("Nov 30 10:00:00 a\nDec 31 10:00:00 a\nJan  1 10:00:00 a\nMar  1 10:00:00 a\n")
        import datetime
        t = datetime.datetime(2024, 3, 2).timestamp()
        os.utime(p, (t, t))
        y = dl_logs.SysYear(p)
        self.assertEqual([y.at(11), y.at(12), y.at(1), y.at(3)], [2023, 2023, 2024, 2024])

    # ------------------------------------------------------------ 15. a type is committed to only after the parse is checked
    def test_type_detection_validates_before_it_commits(self):
        bad = self.tmp / "notes.torrent"
        bad.write_text("these are my notes about torrents, not a metainfo file\n")
        self.assertNotEqual(core.detect(bad)["subtype"], "torrent")
        good = self.tmp / "good.torrent"
        good.write_bytes(self.bencode({"announce": "udp://t.example:80/a", "info": {"name": "pack", "length": 5}}))
        self.assertEqual(core.detect(good)["subtype"], "torrent")
        dta = self.tmp / "table.dta"
        dta.write_bytes(b"plain text that happens to start with a p" * 20)
        self.assertNotEqual(core.detect(dta)["subtype"], "stata")
        # a real old Stata header: format 114 ('r'), byte order 2, file type 1, then 0
        good_dta = self.tmp / "ok.dta"
        good_dta.write_bytes(bytes([114, 2, 1, 0]) + b"\0" * 200)
        self.assertEqual(core.detect(good_dta)["subtype"], "stata")

    def test_binary_stl_needs_real_triangles_not_only_the_size(self):
        zero = self.tmp / "zero.stl"
        zero.write_bytes(b"\0" * 80 + struct.pack("<I", 3) + b"\0" * 150)
        self.assertNotEqual(core.detect(zero)["subtype"], "stl")
        junk = self.tmp / "junk.stl"
        junk.write_bytes(b"\0" * 80 + struct.pack("<I", 2) + b"\xff" * 100)   # NaN coordinates
        self.assertNotEqual(core.detect(junk)["subtype"], "stl")
        real = self.tmp / "real.stl"
        tri = struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0)
        real.write_bytes(b"\0" * 80 + struct.pack("<I", 3) + tri * 3)
        self.assertEqual(core.detect(real)["subtype"], "stl")

    # ------------------------------------------------------------ 9 + 12. the archive screen names the member, not the archive
    def tar_file(self, name, members, mode="w"):
        p = self.tmp / name
        with tarfile.open(p, mode) as t:
            for m in members:
                ti = tarfile.TarInfo(m[0])
                ti.mtime = 1767225600
                if len(m) == 3:   # (name, type, target)
                    ti.type, ti.linkname = m[1], m[2]
                    t.addfile(ti)
                else:
                    ti.size = len(m[1])
                    t.addfile(ti, io.BytesIO(m[1]))
        return p

    def test_relative_link_inside_the_archive_does_not_refuse_it(self):
        p = self.tar_file("src.tar", [("pkg/README.md", b"# Pkg\nA small package.\n"), ("pkg/main.py", b"print('hi')\n"),
                                      ("pkg/link.py", tarfile.SYMTYPE, "main.py"), ("pkg/lib/up.py", tarfile.SYMTYPE, "../main.py")])
        out, stream, lj, o = self.look(p)
        self.assertEqual([f for f in lj["flags"] if f["kind"] == "REFUSED"], [])
        self.assertIn("Safety screen: passed", stream)
        self.assertTrue(json.loads((o / "screen.json").read_text(encoding="utf-8"))["extract"])

    def test_link_that_leaves_the_archive_still_refuses_it(self):
        p = self.tar_file("evil.tar", [("a.txt", b"hi"), ("l1", tarfile.SYMTYPE, "../../etc/passwd"), ("l2", tarfile.SYMTYPE, "/etc/passwd")])
        out, stream, lj, o = self.look(p, "--extract", ok=(2,))
        self.assertIn("REFUSED", out)
        self.assertFalse((o / "extract").exists())

    def test_duplicate_names_leave_only_those_members_out(self):
        p = self.tar_file("dup.tar", [("notes.txt", b"first version\n"), ("keep.txt", b"kept member text, long enough to quote whole.\n"), ("notes.txt", b"second version\n")])
        out, stream, lj, o = self.look(p, "--extract")
        self.assertEqual(lj["flags"] and [f for f in lj["flags"] if f["kind"] == "REFUSED"], [])
        self.assertIn("left out of member looks and extraction: notes.txt (duplicate-name)", stream)
        self.assertTrue((o / "extract" / "keep.txt").exists())
        self.assertFalse((o / "extract" / "notes.txt").exists())

    def test_one_high_ratio_member_is_left_out_and_the_rest_is_read(self):
        p = self.tmp / "mixed.zip"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("zeros.bin", b"\0" * (12 << 20))
            z.writestr("readme.txt", "Readme: this archive holds a log and a zero-filled block.\n" * 3)
        out, stream, lj, o = self.look(p, "--extract")
        refused = [f for f in lj["flags"] if f["kind"] == "REFUSED"]
        self.assertEqual([f["where"] for f in refused], ["zeros.bin"])
        self.assertIn("zeros.bin (ratio)", stream)
        self.assertTrue((o / "extract" / "readme.txt").exists())
        self.assertFalse((o / "extract" / "zeros.bin").exists())

    def test_zip_slip_still_refuses_the_whole_archive(self):
        p = self.tmp / "slip2.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("../evil.txt", "x")
            z.writestr("fine.txt", "ok")
        out, stream, lj, o = self.look(p, "--extract", ok=(2,))
        self.assertIn("REFUSED", out)
        self.assertFalse((o / "extract").exists())

    def test_many_members_refuse_extraction_but_not_the_look(self):
        import dl_bins
        p = self.tar_file("many.tar", [(f"d/f{i:05d}.txt", b"x") for i in range(dl_bins.MAX_MEMBERS + 20)])
        out, stream, lj, o = self.look(p)
        self.assertEqual([f for f in lj["flags"] if f["kind"] == "REFUSED"], [])
        self.assertIn("extraction refused (too-many-members", stream)
        self.assertFalse(json.loads((o / "screen.json").read_text(encoding="utf-8"))["extract"])
        out, stream, lj, o = self.look(p, "--extract", ok=(2,))
        self.assertFalse((o / "extract").exists())

    def test_tar_listing_stops_at_the_time_cap_and_says_partial(self):
        p = self.tar_file("long.tar", [(f"f{i}.txt", b"data") for i in range(400)])
        out, stream, lj, o = self.look(p, env={"SIGMADEEPLOOK_TARLIST_CAP": "0"})
        partial = [f for f in lj["flags"] if f["kind"] == "PARTIAL" and f["where"] == "listing"]
        self.assertEqual(len(partial), 1)
        self.assertIn("PARTIAL", out)
        full = self.look(p)[2]
        self.assertEqual([f for f in full["flags"] if f["kind"] == "PARTIAL" and f["where"] == "listing"], [])

    # ------------------------------------------------------------ 11. records after a header, windows for dates
    @unittest.skipUnless(have("numpy"), "numpy missing")
    def test_records_after_a_header_get_a_layout(self):
        hdr = b"RECS1.0 " + struct.pack("<II", 3000, 16) + b"\0\0\0\0"   # 20 bytes
        body = b"".join(struct.pack("<IIHHI", i, 800000000 + i * 60, i % 5, 0, 1000 + (i % 7)) for i in range(1, 3001))
        lines = dl_misc.record_layout(hdr + body, len(hdr) + len(body))
        self.assertTrue(lines)
        self.assertIn("after a 20-byte header", lines[0])
        self.assertIn("3,000 records of 16 bytes", lines[0])
        self.assertIn("strictly increasing", lines[0])
        self.assertIn("timestamp (uint32 epoch seconds) 1995-", lines[0], "1995 is inside the widened date window")

    @unittest.skipUnless(have("numpy"), "numpy missing")
    def test_headerless_records_keep_their_layout_and_offset_zero(self):
        body = b"".join(struct.pack("<IfHH", i, 20.0 + (i % 7) * 0.5, i % 3, 0) for i in range(1, 2001))
        lines = dl_misc.record_layout(body, len(body))
        self.assertIn("2,000 records of 12 bytes", lines[0])
        self.assertNotIn("byte header", lines[0])

    # ------------------------------------------------------------ 13. readers that need a whole structure have a size guard
    @staticmethod
    def bencode(o):
        if isinstance(o, int):
            return b"i%de" % o
        if isinstance(o, bytes):
            return b"%d:%s" % (len(o), o)
        if isinstance(o, str):
            return H7c.bencode(o.encode())
        if isinstance(o, list):
            return b"l" + b"".join(H7c.bencode(x) for x in o) + b"e"
        return b"d" + b"".join(H7c.bencode(k) + H7c.bencode(v) for k, v in sorted(o.items())) + b"e"

    def test_torrent_over_the_whole_file_cap_is_named_not_loaded(self):
        p = self.tmp / "big.torrent"
        p.write_bytes(self.bencode({"announce": "udp://t.example:80/a", "info": {"name": "pack", "piece length": 16384, "pieces": b"\0" * 20, "length": 5}}))
        out, stream, lj, o = self.look(p, env={"SIGMADEEPLOOK_WHOLE_CAP": "10"})
        steps = json.dumps(lj.get("steps") or lj)
        self.assertIn("this reader holds in memory", steps)
        ok, stream2, _, _ = self.look(p)
        self.assertNotIn("this reader holds in memory", ok)

    def test_deb_members_are_mapped_and_a_huge_one_is_not_opened(self):
        def member(name, data):
            return name.ljust(16).encode() + b"0".ljust(12) + b"0".ljust(6) + b"0".ljust(6) + b"100644".ljust(8) + str(len(data)).ljust(10).encode() + b"`\n" + data + (b"\n" if len(data) % 2 else b"")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            ti = tarfile.TarInfo("control")
            body = b"Package: demo\nVersion: 1.2\nArchitecture: all\nDescription: a demo\n"
            ti.size = len(body)
            t.addfile(ti, io.BytesIO(body))
        data_buf = io.BytesIO()
        with tarfile.open(fileobj=data_buf, mode="w:gz") as t:
            for i in range(30):
                ti = tarfile.TarInfo(f"usr/share/demo/f{i}.txt")
                ti.size = 2000
                t.addfile(ti, io.BytesIO(os.urandom(1000).hex().encode()))
        p = self.tmp / "demo.deb"
        p.write_bytes(b"!<arch>\n" + member("debian-binary", b"2.0\n") + member("control.tar.gz", buf.getvalue()) + member("data.tar.gz", data_buf.getvalue()))
        out, stream, lj, o = self.look(p)
        self.assertIn("Package: demo", stream)
        self.assertIn("usr/share/demo/f0.txt", stream)
        out, stream, lj, o = self.look(p, env={"SIGMADEEPLOOK_AR_MEMBER_CAP": "3000"})
        self.assertIn("Package: demo", stream)
        self.assertIn("data.tar.gz: ", stream)
        self.assertIn("so its file list is not read (PARTIAL)", stream)
        self.assertNotIn("usr/share/demo/f0.txt", stream)

    def test_lines_window_streams_and_counts_like_grep(self):
        import argparse
        import dl_drill
        p = self.tmp / "long.txt"
        p.write_text("".join(f"line {i} — š\n" for i in range(1, 5001)), encoding="utf-8")
        o = argparse.Namespace(lines="4990-4995")
        text, code = dl_drill.do_lines(o, p, self.tmp, {"artifacts": []})
        self.assertEqual(code, 0, text)
        self.assertIn("lines 4990-4995 of 5000", text)
        self.assertIn("line 4995 ", text)
        self.assertNotIn("line 4996 ", text)
        self.assertIn("next: --lines long.txt:4996-5095", text)
        text, code = dl_drill.do_lines(argparse.Namespace(lines="9000-9001"), p, self.tmp, {"artifacts": []})
        self.assertEqual(code, 1)
        self.assertIn("has only 5000 lines", text)

    # ------------------------------------------------------------ 10. word lists in more than one language
    def test_claims_follow_the_speech_language(self):
        de = "Das kostet vierzig Millionen Euro im Jahr, fünfmal mehr als früher."
        self.assertEqual(dl_media.claim_score("Das war schön und lang.", "de"), 0)
        self.assertGreater(dl_media.claim_score(de, "de"), dl_media.claim_score(de, "en"))
        sr = "To košta četrdeset miliona evra godišnje, tri puta više nego pre."
        self.assertGreater(dl_media.claim_score(sr, "sr"), dl_media.claim_score(sr, "en"))
        self.assertGreater(dl_media.claim_score(sr, "hr"), dl_media.claim_score(sr, "en"), "Croatian uses the same list")
        en = "It costs forty million dollars a year, five times more than before."
        self.assertEqual(dl_media.claim_score(en), dl_media.claim_score(en, "en"))
        self.assertGreaterEqual(dl_media.claim_score(en, "de"), dl_media.claim_score(en, "en"), "English always counts")

    def test_section_turns_in_german_and_serbian(self):
        de = [{"start": 100.0, "text": "Jetzt, die Zahlen, werden interessant."}, {"start": 200.0, "text": "Zuletzt, das Fazit, ist klar."}]
        self.assertEqual(dl_media.section_turns(de, lang="de"), ["[1:40] die Zahlen", "[3:20] das Fazit"])
        sr = [{"start": 65.0, "text": "Sada, o novcu, razgovaramo kasnije."}]
        self.assertEqual(dl_media.section_turns(sr, lang="sr"), ["[1:05] o novcu"])
        self.assertEqual(dl_media.section_turns(sr, lang="en"), [])

    def test_stated_totals_in_german_and_serbian_pdfs(self):
        for line in ("Gesamtsumme 1.234,50", "Umsatz 2024: 88.000", "Ukupno 12.500,00", "Укупно 450", "Total 5,000"):
            self.assertTrue(dl_pdffacts.STATED_RE.search(line), line)
        self.assertFalse(dl_pdffacts.STATED_RE.search("Nothing here 12"))

    def test_front_and_back_matter_in_german_and_serbian(self):
        for label in ("Inhaltsverzeichnis", "Vorwort", "Impressum", "Sadržaj", "Predgovor", "Садржај"):
            self.assertEqual(dl_books.classify(label, "", None, None), "front", label)
        for label in ("Danksagung", "Anhang", "Literaturverzeichnis", "Zahvalnica", "Dodatak", "Захвалница"):
            self.assertEqual(dl_books.classify(label, "", None, None), "back", label)
        self.assertEqual(dl_books.classify("Kapitel 1", "", None, None), "body")

    def test_chapters_are_counted_with_and_without_the_closing_section(self):
        files, manifest, spine = {}, [], []
        docs = [("v.xhtml", "Vorwort"), ("k1.xhtml", "Kapitel 1"), ("k2.xhtml", "Kapitel 2"), ("k3.xhtml", "Kapitel 3"), ("f.xhtml", "Fazit"), ("d.xhtml", "Danksagung")]
        for k, (fn, title) in enumerate(docs):
            files[f"OEBPS/{fn}"] = f'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head><body><h1>{title}</h1><p>{"wort " * 120}</p></body></html>'
            manifest.append(f'<item id="i{k}" href="{fn}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="i{k}"/>')
        opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
               '<dc:title>Ein Buch</dc:title><dc:creator>A. Autor</dc:creator><dc:language>de</dc:language><dc:identifier id="uid">urn:x</dc:identifier></metadata>'
               f'<manifest>{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>')
        p = self.tmp / "buch.epub"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
            z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                       '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            z.writestr("OEBPS/content.opf", opf)
            for k, v in files.items():
                z.writestr(k, v)
        out, stream, lj, o = self.look(p)
        self.assertIn("Chapter count both ways: 3 without the closing sections (Fazit), 4 when they count as chapters.", stream)
        self.assertEqual(lj["facts"]["chapters_without_closing_sections"], 3)
        self.assertEqual(lj["facts"]["chapters_with_closing_sections"], 4)

    def test_language_table_is_one_place_and_extensible(self):
        self.assertEqual(dl_lex.langs("hr"), ("sr", "en"))
        self.assertEqual(dl_lex.langs("fr"), ("en",))
        self.assertEqual(dl_lex.langs(None), ("en",))
        self.assertEqual(dl_lex.langs("de"), ("de", "en"))

    # ------------------------------------------------------------ 8. --ask in German, Serbian, and without the noun list
    def orders_csv(self):
        p = self.tmp / "orders.csv"
        regions = ["Nord", "Süd", "Ost", "West"]
        lines = ["id,region,last_name,amount,weight,units"]
        self.orders = []
        for i in range(1, 41):
            row = (i, regions[i % 4], f"Müller{i}", 10 + i, 2.5 + (i % 5), 1 + i % 9)
            self.orders.append(row)
            lines.append(",".join(str(x) for x in row))
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_ask_in_german_and_serbian(self):
        p = self.orders_csv()
        out, _, _, o = self.look(p)
        by = {}
        for r in self.orders:
            by.setdefault(r[1], []).append(r)
        a = self.ask(p, o, "Wie viele Zeilen pro region?")
        self.assertIn("language de", a)
        for reg, rs in by.items():
            self.assertIn(f"{reg} {len(rs)}", a)
        want = sum(r[3] for r in by["Süd"])
        a = self.ask(p, o, "Wie hoch ist die Summe von amount in Süd?")
        self.assertIn(f"Answer: sum of amount = {want}", a)
        wsum = sum(r[4] for r in by["Ost"])
        a = self.ask(p, o, "Wie viel weight insgesamt in Ost?")
        self.assertIn("Answer: sum of weight", a)
        self.assertIn(f"{wsum:g}", a)
        a = self.ask(p, o, "Koliko je ukupno weight u regionu Ost?")
        self.assertIn("language sr", a)
        self.assertIn("Answer: sum of weight", a)
        a = self.ask(p, o, "Колико је укупно weight у Ost?")
        self.assertIn("language sr", a)
        self.assertIn("Answer: sum of weight", a)
        top = max(self.orders, key=lambda r: r[3])
        a = self.ask(p, o, "Was ist der höchste amount?")
        self.assertIn(f"Answer: max of amount = {top[3]}", a)
        low = min(self.orders, key=lambda r: r[3])
        a = self.ask(p, o, "Koji je najmanji amount?")
        self.assertIn(f"Answer: min of amount = {low[3]}", a)
        n = sum(1 for r in self.orders if r[5] >= 5)
        a = self.ask(p, o, "Wie viele Zeilen mit units mindestens 5?")
        self.assertIn(f"Answer: {n} lines match", a)

    def test_ask_count_or_total_is_decided_by_the_columns_named_not_a_noun_list(self):
        p = self.orders_csv()
        out, _, _, o = self.look(p)
        want = sum(r[4] for r in self.orders if r[1] == "West")
        a = self.ask(p, o, "How many in total weight does West have?")
        self.assertIn("Answer: sum of weight", a)
        self.assertIn(f"{want:g}", a)
        n = sum(1 for r in self.orders if r[1] == "West")
        a = self.ask(p, o, "How many lines are there in total in West?")
        self.assertIn(f"Answer: {n} lines match", a)

    def test_ask_at_most_is_a_comparison_and_last_name_is_a_column(self):
        p = self.orders_csv()
        out, _, _, o = self.look(p)
        n = sum(1 for r in self.orders if r[5] <= 3)
        a = self.ask(p, o, "How many lines have units at most 3?")
        self.assertIn("units <= 3", a)
        self.assertIn(f"Answer: {n} lines match", a)
        a = self.ask(p, o, "Show the last name of the customer in Ost")
        self.assertNotIn("file order", a)
        self.assertIn("matching line(s)", a)

    def test_ask_first_and_last_rows_by_position(self):
        p = self.orders_csv()
        out, _, _, o = self.look(p)
        ost = [r for r in self.orders if r[1] == "Ost"]
        a = self.ask(p, o, "Show the first row in Ost")
        self.assertIn("Answer: the first line(s) in file order", a)
        self.assertIn(f"last_name = Müller{ost[0][0]}", a)
        a = self.ask(p, o, "Show the last 2 rows in Ost")
        self.assertIn("Answer: the last 2 line(s) in file order", a)
        self.assertIn(f"Müller{ost[-1][0]}", a)
        self.assertIn(f"Müller{ost[-2][0]}", a)

    def test_ask_fold_matches_accents_and_cyrillic(self):
        self.assertEqual(dl_asklang.fold("Größe ĐORĐE Čačak"), "grosse djordje cacak")
        self.assertEqual(dl_asklang.fold("Цена љубав"), "cena ljubav")
        self.assertEqual(dl_asklang.detect(dl_asklang.fold("Wie viele Zeilen pro Stadt?")), "de")
        self.assertEqual(dl_asklang.detect(dl_asklang.fold("Koliko ima redova po gradu?")), "sr")
        self.assertEqual(dl_asklang.detect(dl_asklang.fold("How many rows per city?")), "en")

    # ------------------------------------------------------------ 7. --ask holds a bounded table and says so
    def test_ask_over_the_row_budget_says_partial_with_both_counts(self):
        p = self.tmp / "big_orders.csv"
        p.write_text("id,region,amount\n" + "".join(f"{i},{['N', 'S'][i % 2]},{i}\n" for i in range(1, 501)), encoding="utf-8")
        out, _, _, o = self.look(p)
        a = self.ask(p, o, "How many rows per region?", env={"SIGMADEEPLOOK_ASK_ROWS_CAP": "100"})
        self.assertIn("PARTIAL: 100 of 500 lines were read", a)
        a = self.ask(p, o, "What is the total amount?", env={"SIGMADEEPLOOK_ASK_ROWS_CAP": "100"})
        self.assertIn("Answer (PARTIAL: 100 of 500 lines were read", a)
        a = self.ask(p, o, "What is the total amount?")
        self.assertNotIn("PARTIAL", a)
        self.assertIn(f"sum of amount = {sum(range(1, 501)):,}".replace(",", ""), a.replace(",", ""))
        a = self.ask(p, o, "What is the total amount?", env={"SIGMADEEPLOOK_ASK_CELLS_CAP": "60"})
        self.assertIn("PARTIAL", a)

    def test_ask_streams_a_file_bigger_than_the_sniff_window_in_the_right_code_page(self):
        import dl_ask
        names = ["Đorđe Šćekić", "Žarko Ćirić", "Nenad Đurić"]
        p = self.tmp / "stream1250.csv"
        p.write_bytes(("ime;grad;iznos\n" + "".join(f"{names[i % 3]};Čačak;{i},5\n" for i in range(1, 4001))).encode("cp1250"))
        old = dl_ask.SNIFF_BYTES
        dl_ask.SNIFF_BYTES = 2000   # the first 2 kB decide the encoding and the dialect; the other 80 kB are streamed
        try:
            cols, rows, pos, enc, total = dl_ask.read_delimited(p, ";")
        finally:
            dl_ask.SNIFF_BYTES = old
        self.assertEqual(len(rows), 4000)
        self.assertIsNone(total)
        self.assertEqual(rows[0][0], names[1])
        self.assertEqual(rows[-1][1], "Čačak")
        self.assertEqual(enc, "cp1250")

    def test_ask_json_over_the_document_cap_is_named(self):
        p = self.tmp / "doc.json"
        p.write_text(json.dumps({"items": [{"id": i, "kind": "a" if i % 2 else "b"} for i in range(300)]}), encoding="utf-8")
        out, _, _, o = self.look(p)
        a = self.ask(p, o, "How many items per kind?", env={"SIGMADEEPLOOK_ASK_JSON_CAP": "500"})
        self.assertIn("over the", a)
        self.assertIn("no table was built from it", a)
        a = self.ask(p, o, "How many items per kind?")
        self.assertIn("a 150", a)

    @unittest.skipUnless(have("pyarrow"), "pyarrow missing")
    def test_ask_parquet_is_read_in_batches_and_flags_a_cut(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        p = self.tmp / "t.parquet"
        pq.write_table(pa.table({"id": list(range(1, 1201)), "kind": ["a", "b"] * 600}), p, row_group_size=200)
        out, _, _, o = self.look(p)
        a = self.ask(p, o, "How many rows per kind?")
        self.assertIn("a 600", a)
        a = self.ask(p, o, "How many rows per kind?", env={"SIGMADEEPLOOK_ASK_ROWS_CAP": "300"})
        self.assertIn("PARTIAL", a)
        self.assertIn("of 1,200 rows were read", a)


if __name__ == "__main__":
    unittest.main()
