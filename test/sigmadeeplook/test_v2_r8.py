"""Fix round 8 (ticket 83, P0.14b.H8): the failure categories of held-out set 7, on fixtures built here (none from a held-out set).

The categories (from the grader's category list, never the questions): (1) whole-file counts and statistics missing at the smallest budget,
(2) the end of the file and single records not reached, (3) header, structure and metadata fields of binary and legacy formats,
(4) pixel and signal facts, (5) a visible sample read as the whole file (no "not shown" flag).
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import json
import os
import shutil
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

sys.path.insert(0, str(SCRIPTS))


class R8Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r8_"))

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
        stream = "\n".join(x["text"] for x in lj["stream"])
        return r.stdout, stream, lj, out


class TextStructure(R8Base):
    """Category 1, 2 and 5 on plain text: every structure count and the end of the file in step 1, a partial view says so."""

    def rst(self):
        L = ["=========", "Big Title", "=========", ""]
        last = None
        for i in range(30):
            L += [f"Chapter {i}", "=" * 12, "", f"Text of chapter {i}.", ""]
            for j in range(2):
                L += [f"Part {i}.{j}", "~" * 12, "", ".. note::" if (i + j) % 2 else ".. warning::", "", "   body", ""]
                last = f"Part {i}.{j}"
        L += ["Closing words", "^^^^^^^^^^^^^", "", "The very last sentence of the file."]
        p = self.tmp / "doc.rst"
        p.write_text("\n".join(L) + "\n", encoding="utf-8")
        return p, L

    def test_rst_headings_of_any_underline_and_the_last_one(self):
        p, L = self.rst()
        out, _, lj, _ = self.look(p)
        last_line = L.index("Closing words") + 1
        self.assertIn(f"last 'Closing words' (line {last_line}", out)
        self.assertIn("The very last sentence of the file.", out, "the end of the file is in step 1")
        n_notes = sum(1 for x in L if x == ".. note::")
        n_warn = sum(1 for x in L if x == ".. warning::")
        self.assertIn(f"note ({n_notes})", out.replace("::", ""), "directive counts")
        self.assertIn(f"warning ({n_warn})", out.replace("::", ""))
        # three underline styles = three levels, counted
        self.assertIn("level-4 headings 1", out)
        self.assertIn("level-2 headings 30", out)
        self.assertIn("level-3 headings 60", out)

    def test_line_start_histogram_and_paragraph_blocks(self):
        L = ['msgid ""', 'msgstr ""', ""]
        for i in range(120):
            L += [f"#: src/f{i % 7}.c:{i}", f'msgid "Text {i}"', f'msgstr "{"" if i % 4 == 0 else "Tekst %d" % i}"', ""]
        p = self.tmp / "cat.txt"
        p.write_text("\n".join(L) + "\n", encoding="utf-8")
        out, _, _, _ = self.look(p)
        self.assertIn("msgid 121", out)
        self.assertIn("msgstr 121", out)
        self.assertIn("paragraphs 121", out)
        self.assertIn("Line starts", out)

    def test_head_view_says_it_is_partial(self):
        L = [f"row {i} of a long plain file" for i in range(900)]
        p = self.tmp / "long.txt"
        p.write_text("\n".join(L) + "\n", encoding="utf-8")
        out, _, _, _ = self.look(p, "--budget", "3000")
        self.assertIn("row 899 of a long plain file", out)
        self.assertRegex(out, r"(?i)first 200 of 900 lines|lines 1-\d+ of 900")

    def test_cp1251_text_tail_and_paragraphs(self):
        paras = [f"Пасус број {i}. Ово је текст." for i in range(60)]
        p = self.tmp / "cyr.txt"
        p.write_bytes("\n\n".join(paras).encode("cp1251"))
        out, _, _, _ = self.look(p)
        self.assertIn("paragraphs 60", out)
        self.assertIn("Пасус број 59", out)


class LastRecord(R8Base):
    def test_table_profiles_print_the_last_record(self):
        p = self.tmp / "t.csv"
        p.write_text("id,name,qty\n" + "\n".join(f"{i},n{i % 5},{i % 9}" for i in range(1, 801)) + "\n")
        out, _, _, _ = self.look(p)
        self.assertRegex(out, r"Last row.*id=800")
        j = self.tmp / "t.jsonl"
        j.write_text("\n".join(json.dumps({"id": i, "tag": f"k{i % 3}"}) for i in range(1, 301)) + "\n")
        out, _, _, _ = self.look(j)
        self.assertRegex(out, r"Last (row|record).*id=300")


if __name__ == "__main__":
    unittest.main()
