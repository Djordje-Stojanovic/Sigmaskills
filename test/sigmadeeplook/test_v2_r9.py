"""Fix round 9 (ticket 83, P0.14b): the miss categories of held-out set 8, on fixtures built here (none from a held-out set).

Categories (from the grader's category list, never the questions): (1) the tail and single records: the last record and the Nth record;
(2) exact counts; (3) header and structure; (4) signal facts. Weak families: legacy Word .doc, reStructuredText, YouTube .sbv, gettext .mo,
Cyrillic code-page text, Sun .au. Every expected figure is worked out here from the data this file wrote, never read back from the look.
`r9_report.doc` was written by LibreOffice from an HTML page this round made (130 numbered paragraphs, 4 part headings, one 6 x 3 table).
"""
import json
import math
import os
import random
import shutil
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

sys.path.insert(0, str(SCRIPTS))
FX = HERE / "fixtures"


class R9Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r9_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look(self, path, *extra, tools=False, ok=(0,)):
        out = self.tmp / ("out_" + path.name)
        shutil.rmtree(out, ignore_errors=True)
        args = [str(path), "--out", str(out), "--fresh", *extra] + ([] if tools else ["--no-tools"])
        r = run(args)
        self.assertIn(r.returncode, ok, r.stderr[-1500:] + r.stdout[-800:])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return r.stdout, lj, out

    def kinds(self, lj):
        return {f["kind"] for f in lj.get("flags", [])}

    def no_crash(self, lj):
        self.assertNotIn("INTERNAL-ERROR", self.kinds(lj), lj.get("flags"))


# ------------------------------------------------------------------ legacy Word .doc, read without LibreOffice
def doc_paragraphs():
    """The non-empty paragraphs outside the table, in order, as the HTML source wrote them."""
    out = ["Quarterly Review"]
    for i in range(1, 131):
        if i % 40 == 1:
            out.append(f"Part {i // 40 + 1}")
        out.append(f"Paragraph {i}: alpha beta gamma {i * 7}.")
    out.append("Signed: the board, end of document.")
    return out


class WordBinary(R9Base):
    def test_text_counts_tail_and_nth_paragraph_without_libreoffice(self):
        out, lj, _ = self.look(FX / "r9_report.doc", "--budget", "3000")
        paras = doc_paragraphs()
        self.assertIn(f"non-empty paragraphs outside tables {len(paras)}", out)
        self.assertIn("tables 1", out)
        self.assertIn("table rows 6", out)
        self.assertIn("Signed: the board, end of document.", out, "the last paragraph is in step 1")
        self.assertIn(f"#100 {paras[99]}", out, "the 100th paragraph is printed at a landmark")
        self.assertIn("Paragraph 130: alpha beta gamma 910.", out)
        self.assertIn("Item 5 | 10 | 7.50", out, "the last table row")
        self.no_crash(lj)

    def test_file_header_styles_and_properties(self):
        out, lj, _ = self.look(FX / "r9_report.doc", "--budget", "3000")
        self.assertRegex(out, r"Word binary header: nFib \d+ \(Word 97")
        self.assertIn("heading 2 4", out, "heading levels come from the paragraph styles")
        self.assertIn("heading 1 1", out)
        self.assertIn("Title: Quarterly Review", out)
        self.assertIn("Part 4", out)

    def test_damaged_doc_is_flagged_not_crashed(self):
        raw = (FX / "r9_report.doc").read_bytes()
        cut = self.tmp / "cut.doc"
        cut.write_bytes(raw[:len(raw) // 3])
        _, lj, _ = self.look(cut, ok=(0, 1))
        self.no_crash(lj)
        self.assertIn("CORRUPT", self.kinds(lj))
        rnd = random.Random(9)
        for k in range(6):
            b = bytearray(raw)
            for _ in range(40):
                b[rnd.randrange(512, len(b))] = rnd.randrange(256)
            p = self.tmp / f"fuzz{k}.doc"
            p.write_bytes(bytes(b))
            _, lj, _ = self.look(p, ok=(0, 1))
            self.no_crash(lj)


# ------------------------------------------------------------------ reStructuredText
class Rst(R9Base):
    def make(self):
        L = ["=" * 14, "Field Manual", "=" * 14, "", ":Author: Dev Sample", ":Version: 4.1", ":Date: 2026-09-30", ""]
        code = tables = 0
        for i in range(1, 41):
            t = f"Chapter {i}"
            L += [t, "-" * len(t), "", f"Body of chapter {i}.", ""]
            if i % 4 == 0:
                L += [".. code-block:: python", "", f"   x = {i}", ""]
                code += 1
            if i % 10 == 0:
                L += [".. list-table:: Parts", "   :header-rows: 1", "", "   * - Part", "     - Qty", f"   * - P{i}", "     - {i}", ""]
                tables += 1
            if i % 8 == 0:
                L += ["Example::", "", f"    literal {i}", ""]
                code += 1
        L += ["+-----+-----+", "| a   | b   |", "+=====+=====+", "| 1   | 2   |", "+-----+-----+", ""]
        tables += 1
        L += ["Last words of the manual."]
        p = self.tmp / "manual.rst"
        p.write_text("\n".join(L) + "\n", encoding="utf-8")
        return p, L, code, tables

    def test_docinfo_tables_code_blocks_and_landmark_lines(self):
        p, L, code, tables = self.make()
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn("Title: Field Manual", out)
        self.assertIn("Author: Dev Sample", out)
        self.assertIn("Version: 4.1", out)
        self.assertIn(f"tables {tables}", out)
        self.assertIn(f"code blocks {code}", out)
        self.assertIn(f"line 100: {' '.join(L[99].split())}" if L[99].strip() else "line 100: (blank)", out)
        self.assertIn("Last words of the manual.", out)
        self.no_crash(lj)


# ------------------------------------------------------------------ YouTube .sbv
def sbv_stamp(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


class Sbv(R9Base):
    def make(self, n=300):
        r = random.Random(3)
        t, cues = 1.0, []
        for i in range(1, n + 1):
            lines = [f"cue {i} first line"] + ([f"cue {i} second line"] if i % 3 == 0 else [])
            d = 1.5 + (i % 5) * 0.5
            cues.append((t, t + d, lines))
            t += d + r.choice((0.0, 0.25, 0.5))
        txt = "\n".join(f"{sbv_stamp(a)},{sbv_stamp(b)}\n" + "\n".join(ls) + "\n" for a, b, ls in cues)
        p = self.tmp / "talk.sbv"
        p.write_text(txt, encoding="utf-8")
        return p, cues

    def test_text_lines_two_line_cues_and_nth_cue(self):
        p, cues = self.make()
        out, lj, _ = self.look(p, "--budget", "3000")
        lines = sum(len(c[2]) for c in cues)
        self.assertIn(f"text lines {lines:,}", out)
        self.assertIn(f"two-line cues {sum(1 for c in cues if len(c[2]) == 2)}", out)
        self.assertIn(f"#100 {sbv_stamp(cues[99][0])}-{sbv_stamp(cues[99][1])}", out, "the 100th cue at a landmark")
        self.assertIn("cue 100 first line", out)
        self.assertIn("cue 299 first line", out, "the last cues")
        self.no_crash(lj)

    def test_garbage_sbv_does_not_crash(self):
        p = self.tmp / "bad.sbv"
        p.write_bytes(b"0:00:01.000,0:00:0\nhalf\n\n\xff\xfe junk 9:99:99.999,x\n")
        _, lj, _ = self.look(p, ok=(0, 3))
        self.no_crash(lj)


# ------------------------------------------------------------------ gettext .mo
def write_mo(path, pairs, big=False):
    keys = sorted(pairs)
    ids = strs = b""
    offs = []
    for k in keys:
        kb, vb = k.encode(), pairs[k].encode()
        offs.append((len(ids), len(kb), len(strs), len(vb)))
        ids += kb + b"\0"
        strs += vb + b"\0"
    e = ">" if big else "<"
    n = len(keys)
    ks, vs = 28 + 16 * n, 28 + 16 * n + len(ids)
    kt = [x for o1, l1, _, _ in offs for x in (l1, o1 + ks)]
    vt = [x for _, _, o2, l2 in offs for x in (l2, o2 + vs)]
    path.write_bytes(struct.pack(e + "Iiiiiii", 0x950412DE, 0, n, 28, 28 + 8 * n, 0, 0) + struct.pack(e + f"{2 * n}i", *kt) + struct.pack(e + f"{2 * n}i", *vt) + ids + strs)
    return keys


class Mo(R9Base):
    def make(self, big=True):
        pairs = {"": "Language: sr\nContent-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=3; plural=(n%10==1 ? 0 : 1);\n"}
        for i in range(400):
            pairs[f"Key {i:04d}"] = "" if i % 50 == 7 else f"Vrednost {i:04d}"
        p = self.tmp / ("cat-be.mo" if big else "cat-le.mo")
        keys = write_mo(p, pairs, big)
        return p, keys, pairs

    def test_every_entry_reachable_nth_and_untranslated(self):
        p, keys, pairs = self.make()
        out, lj, d = self.look(p, "--budget", "3000")
        body = [k for k in keys if k]
        self.assertIn(f"untranslated (empty msgstr) {sum(1 for k in body if not pairs[k])}", out)
        self.assertIn(f"#100 '{body[99]}' -> '{pairs[body[99]]}'", out, "the 100th entry at a landmark")
        self.assertIn(f"'{body[-1]}'", out)
        self.assertGreater(len([c for c in lj["stream"] if c.get("sec") == "content"]), 20, "every entry is in the stream for --more")
        self.no_crash(lj)

    def test_damaged_mo_is_flagged(self):
        p, _, _ = self.make(big=False)
        raw = bytearray(p.read_bytes())
        struct.pack_into("<I", raw, 12, 0x7FFFFF00)   # the msgid table points past the end
        bad = self.tmp / "bad.mo"
        bad.write_bytes(bytes(raw))
        _, lj, _ = self.look(bad, ok=(0, 1))
        self.no_crash(lj)
        self.assertIn("CORRUPT", self.kinds(lj))
        short = self.tmp / "short.mo"
        short.write_bytes(bytes(raw[:40]))
        _, lj, _ = self.look(short, ok=(0, 1, 3))
        self.no_crash(lj)


# ------------------------------------------------------------------ Cyrillic code-page text
class Cyrillic(R9Base):
    def test_semicolon_records_in_cp1251_read_as_cyrillic(self):
        names = ["Иванов", "Петрова", "Сидоров", "Ёлкина"]
        L = ["Номер;Сотрудник;Город;Сумма"] + [f"{i};{names[i % 4]};Москва;{i * 3},50" for i in range(1, 801)]
        p = self.tmp / "ledger.txt"
        p.write_bytes(("\r\n".join(L) + "\r\n").encode("cp1251"))
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn("cp1251", out)
        self.assertIn("Сотрудник", out)
        self.assertNotIn("Ñîòð", out)
        self.assertIn("#100 (line 101): Номер=100; Сотрудник=Иванов; Город=Москва", out, "row 100 at a landmark")
        self.no_crash(lj)

    def test_prose_landmark_lines(self):
        words = "город река дом время человек работа день жизнь слово место".split()
        r = random.Random(5)
        L = [" ".join(r.choice(words) for _ in range(8)).capitalize() + "." for _ in range(1500)]
        p = self.tmp / "prose.txt"
        p.write_bytes(("\r\n".join(L) + "\r\n").encode("cp1251"))
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn("cp1251", out)
        self.assertIn(f"line 1,000: {L[999]}", out)
        self.assertIn(f"line 1,500: {L[1499]}", out)


# ------------------------------------------------------------------ Sun .au: header and sample statistics
def make_au(path, enc, rate, ch, frames, ann=b"r9 take\0"):
    vals = []
    for i in range(frames):
        v = 0.0 if i < rate // 4 else 0.5 * math.sin(2 * math.pi * 300 * i / rate)
        vals.append(v)
    body = bytearray()
    ints = [[] for _ in range(ch)]
    for v in vals:
        for c in range(ch):
            x = v * (1.0 if c == 0 else 0.5)
            if enc == 3:
                q = int(round(x * 32767))
                body += struct.pack(">h", q)
            elif enc == 2:
                q = int(round(x * 127))
                body += struct.pack(">b", q)
            elif enc == 6:
                q = struct.unpack(">f", struct.pack(">f", x))[0]
                body += struct.pack(">f", x)
            ints[c].append(q)
    hdr = struct.pack(">4sIIIII", b".snd", 24 + len(ann), len(body), enc, rate, ch) + ann
    path.write_bytes(hdr + bytes(body))
    return ints


class Au(R9Base):
    def test_pcm16_stereo_sample_statistics(self):
        p = self.tmp / "st.au"
        ints = make_au(p, 3, 8000, 2, 16000)
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn("16,000 sample frames", out)
        for c, xs in enumerate(ints, 1):
            self.assertIn(f"channel {c}: min {min(xs):,}, max {max(xs):,}", out)
        self.assertIn(f"zero samples {sum(1 for xs in ints for x in xs if x == 0):,}", out)
        self.assertIn(f"first non-zero sample at frame {next(i for i, x in enumerate(ints[0]) if x):,}", out)
        self.assertIn(f"last frame: {ints[0][-1]:,}, {ints[1][-1]:,}", out)
        self.no_crash(lj)

    def test_float_and_8bit(self):
        p = self.tmp / "f.au"
        ints = make_au(p, 6, 8000, 1, 8000)
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn(f"peak {20 * math.log10(max(abs(x) for x in ints[0])):.2f} dBFS", out)
        p = self.tmp / "b.au"
        ints = make_au(p, 2, 8000, 1, 8000)
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn(f"channel 1: min {min(ints[0]):,}, max {max(ints[0]):,}", out)

    def test_big_pcm_is_fast_and_damaged_header_flagged(self):
        p = self.tmp / "big.au"
        n = 44100 * 60
        frame = struct.pack(">hh", 1000, -1000)
        p.write_bytes(struct.pack(">4sIIIII", b".snd", 24, 0xFFFFFFFF, 3, 44100, 2) + frame * n)
        t = time.time()
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertLess(time.time() - t, 20, "a 10 MB file reads in seconds")
        self.assertIn(f"{n:,} sample frames", out)
        self.assertIn("channel 2: min -1,000, max -1,000", out)
        bad = self.tmp / "bad.au"
        bad.write_bytes(struct.pack(">4sIIIII", b".snd", 9_000_000, 100, 3, 8000, 1) + b"\0" * 64)
        _, lj, _ = self.look(bad, ok=(0, 1))
        self.no_crash(lj)
        self.assertIn("CORRUPT", self.kinds(lj))


# ------------------------------------------------------------------ the step-1 budget is filled
class Budget(R9Base):
    def test_a_bigger_budget_prints_more_content(self):
        L = [f"record {i}: value {i * 11}" for i in range(1, 5001)]
        p = self.tmp / "records.txt"
        p.write_text("\n".join(L) + "\n", encoding="utf-8")
        small, _, _ = self.look(p)
        big, _, _ = self.look(p, "--budget", "3000")
        self.assertGreater(len(big), 2.2 * len(small), "a 3,000-token budget is used, not cut at the 1,000-token content cap")
        self.assertIn("line 5,000: record 5000: value 55000", big)


if __name__ == "__main__":
    unittest.main()
