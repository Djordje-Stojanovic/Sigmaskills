"""Fix round 12, lane F2 (ticket 83, P0.14b.H5): the print gaps of held-out set 11 that gave a wrong answer or a miss, on fixtures built here
(none from a held-out set).

Items: (1) a frequent-word count says what it counts and equals what `--ask` counts (the "Table 20 against 19" wrong answer: a word glued to
digits was counted); (2) the clock of a video: stream starts, the first video frame, black spans counted from it (the "4.8 against 3.4" wrong
answer); (3) paragraph counts and occurrence counts answered together, for every text path; (4) heading counts by underline character;
(5) identifying values (title, head fields, last-record fields) are not cut when short, and a cut says its length; (6) the stored row size of a
raster picture with row padding. Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r11_f3 import R11Base, docx_file, wp  # noqa: E402
from r5_fixtures import odf_zip, ODF_NS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class Base(R11Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r12f2_"))


# ------------------------------------------------------------------ (1) and (3): word counts and paragraph counts
PARAS = ["Table 1 lists the arms. Table: see below.",          # Table x2
         "Tables are listed at the end; Table. Done",          # Table x1 ('Tables' does not count)
         "Table11 Summary of Stability Data",                  # glued to digits: not the word
         "Composition of AB1234Capsules",                      # letters inside a longer word only
         "Dose Capsules: take the Capsules.",                  # Capsules x2 in one paragraph
         "Capsules again.",                                    # Capsules x1
         "a lower table and TABLE in capitals"]


class WordCountFixes(Base):
    def docx(self):
        p = self.tmp / "protocol.docx"
        docx_file(p, "".join(wp(t) for t in PARAS))
        return p

    def test_a_question_that_quotes_the_word_table_is_a_word_count(self):
        import dl_wordcount as W
        q = "How many times does the word 'Table' appear in the text as a whole word with a capital T? (Forms such as 'Table.' or 'Table:' count; 'Tables' does not.)"
        self.assertEqual(W.parse(q), ("Table", None, True, True))
        self.assertIsNone(W.parse("How many times does 'Paris' appear in the city column?"))   # a table question stays a table question

    def test_ask_counts_the_whole_word_table_exactly(self):
        full = "\n".join(PARAS)
        exp = len(re.findall(r"(?<!\w)Table(?!\w)", full))
        self.assertEqual(exp, 3)
        out = self.ask(self.docx(), "How many times does the word 'Table' appear in the text as a whole word with a capital T? (Forms such as 'Table.' or 'Table:' count; 'Tables' does not.)")
        self.assertRegex(out, rf"Answer: {exp} whole-word occurrences of 'Table'")

    def test_the_frequent_word_list_counts_what_ask_counts(self):
        _, both, _ = self.look2(self.docx())
        line = re.search(r"Most frequent capitalised words[^\n]*", both)
        self.assertIsNotNone(line, both[-1500:])
        txt = line.group(0)
        self.assertRegex(txt, r"\bTable 3\b", txt)           # not 4: 'Table11' is not the word
        self.assertRegex(txt, r"\bCapsules 3\b", txt)        # not 4: 'AB1234Capsules' is not the word
        self.assertIn("whole word", txt)
        self.assertIn("case-sensitive", txt)
        self.assertRegex(txt, r"joined to a digit or an underscore")

    def test_paragraph_question_gives_both_figures_when_a_word_sits_inside_another(self):
        out = self.ask(self.docx(), "In how many paragraphs does the word 'Capsules' appear?")
        self.assertRegex(out, r"Answer: 2 paragraphs contain 'Capsules'")
        self.assertRegex(out, r"3 paragraphs hold the letters 'Capsules'")
        self.assertIn("AB1234Capsules", out)
        self.assertIn("3 whole-word occurrences of 'Capsules'", out)

    def test_occurrence_question_also_gives_the_paragraph_count(self):
        out = self.ask(self.docx(), "How many times does the word 'Capsules' appear?")
        self.assertRegex(out, r"Answer: 3 whole-word occurrences of 'Capsules'")
        self.assertRegex(out, r"In 2 of 7 non-empty paragraphs")
        self.assertRegex(out, r"3 paragraphs hold the letters 'Capsules'")

    def test_nothing_extra_when_every_hit_is_a_whole_word(self):
        out = self.ask(self.docx(), "In how many paragraphs does the word 'Dose' appear?")
        self.assertRegex(out, r"Answer: 1 paragraph contains 'Dose'")
        self.assertNotIn("hold the letters", out)

    def test_odt_paragraphs(self):
        body = "".join(f"<text:p>{t}</text:p>" for t in PARAS)
        content = f'<?xml version="1.0"?><office:document-content {ODF_NS}><office:body><office:text>{body}</office:text></office:body></office:document-content>'
        meta = f'<?xml version="1.0"?><office:document-meta {ODF_NS}><office:meta><dc:title>T</dc:title></office:meta></office:document-meta>'
        p = self.tmp / "protocol.odt"
        odf_zip(p, "application/vnd.oasis.opendocument.text", content, meta)
        out = self.ask(p, "In how many paragraphs does the word 'Capsules' appear?")
        self.assertRegex(out, r"Answer: 2 paragraphs contain 'Capsules'")
        self.assertRegex(out, r"3 paragraphs hold the letters 'Capsules'")

    def test_rtf_paragraphs(self):
        bs = chr(92)
        body = ("{@rtf1@ansi@deff0 " + "".join(t + "@par " for t in PARAS) + "}").replace("@", bs)
        p = self.tmp / "protocol.rtf"
        p.write_bytes(body.encode("latin-1"))
        out = self.ask(p, "In how many paragraphs does the word 'Capsules' appear?")
        self.assertRegex(out, r"Answer: 2 paragraphs contain 'Capsules'")
        self.assertRegex(out, r"3 paragraphs hold the letters 'Capsules'")

    def test_plain_text_lines_and_paragraphs(self):
        lines = ["Alpha beta", "beta gamma Beta", "", "Alpha Alpha x", "last beta2", "AlphaBeta", ""]
        for ext in ("txt", "md"):
            p = self.tmp / f"plain.{ext}"
            p.write_text("\n".join(lines), encoding="utf-8")
            out = self.ask(p, "In how many lines does the word 'Alpha' appear?")
            self.assertRegex(out, r"Answer: 2 lines contain 'Alpha'", out)
            self.assertIn("1, 4", out)                                      # the real line numbers of the file
            self.assertRegex(out, r"3 whole-word occurrences of 'Alpha'", out)
            self.assertRegex(out, r"3 lines hold the letters 'Alpha'", out)
            out = self.ask(p, "In how many paragraphs does the word 'Alpha' appear?")   # blank-line separated blocks: 1 (lines 1-2), 2 (4-6)
            self.assertRegex(out, r"Answer: 2 paragraphs contain 'Alpha'", out)
            out = self.ask(p, "How many times does the word 'beta' appear?")
            self.assertRegex(out, r"Answer: 3 whole-word occurrences of 'beta'", out)


class PlainTextReview(Base):
    def test_a_form_feed_is_not_a_line_break(self):   # review: splitlines() broke the line numbers of a file with form feeds
        p = self.tmp / "ff.txt"
        p.write_bytes(b"a\n\x0cb Capsules\nc Capsules\n")
        out = self.ask(p, "In how many lines does the word 'Capsules' appear?")
        self.assertRegex(out, r"Answer: 2 lines contain 'Capsules'", out)
        self.assertIn("2, 3", out)

    def test_the_letters_clause_of_a_plain_file_says_lines(self):
        p = self.tmp / "lets.txt"
        p.write_text("Alpha\nAlphaBeta\n", encoding="utf-8")
        out = self.ask(p, "How many times does the word 'Alpha' appear?")
        self.assertRegex(out, r"2 lines hold the letters 'Alpha'", out)
        self.assertNotIn("paragraphs hold", out)

    def test_cp1251_text_is_counted_in_its_own_encoding(self):
        p = self.tmp / "ru.txt"
        word = "\u0416\u0443\u0440\u043d\u0430\u043b"
        p.write_bytes((word + " \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u0430\n" + word + " \u0437\u0430 \u0441\u0435\u043d\u0442\u044f\u0431\u0440\u044c\n\u043d\u0435\u0442\n").encode("cp1251"))
        out = self.ask(p, f"How many times does the word '{word}' appear?")
        self.assertRegex(out, rf"Answer: 2 whole-word occurrences of '{word}'", out)


# ------------------------------------------------------------------ (4) headings by underline character
RST = """\
==========
Main Title
==========

Intro text here.

Section A
---------

Body A.

Section B
---------

Body B.

Section C
---------

Body C.

Sub one
~~~~~~~

Text.

Sub two
~~~~~~~

Text.

Deep
^^^^

Text.

----

A line after a transition, not a heading.

.. code-block:: python

   # not a heading
   x = 1

+-----+-----+
| a   | b   |
+-----+-----+
"""

MD = """\
# Top

Some text.

## Two a

text

## Two b

text

Setext one
==========

text

Setext two
----------

text

Setext three
------------

```
# in a fence
Not
---
```
"""


class HeadingStyles(Base):
    def test_rst_prints_the_headings_per_underline_character(self):
        p = self.tmp / "guide.rst"
        p.write_text(RST, encoding="utf-8")
        _, both, lj = self.look2(p)
        line = re.search(r"Heading styles[^\n]*", both)
        self.assertIsNotNone(line, both[:2500])
        txt = line.group(0)
        self.assertIn("'=' over and under x1", txt)
        self.assertIn("'-' underline x3", txt)
        self.assertIn("'~' underline x2", txt)
        self.assertIn("'^' underline x1", txt)
        self.no_crash(lj)

    def test_ask_headings_underlined_with_hyphens(self):
        p = self.tmp / "guide2.rst"
        p.write_text(RST, encoding="utf-8")
        out = self.ask(p, "How many section headings are underlined with a line of hyphens (-)?")
        self.assertRegex(out, r"Answer: 3 headings are underlined with '-'", out)
        out = self.ask(p, "How many headings are underlined with tildes?")
        self.assertRegex(out, r"Answer: 2 headings are underlined with '~'", out)
        out = self.ask(p, "How many headings have a line of equals signs both above and below?")
        self.assertRegex(out, r"Answer: 1 heading is over- and underlined with '='", out)

    def test_rst_with_only_equals_and_hyphens(self):
        p = self.tmp / "plainrst.rst"
        p.write_text("Doc\n===\n\nOne\n---\n\ntext\n\nTwo\n---\n\ntext\n\nThree\n-----\n\ntext\n\n.. note::\n\n   hi\n", encoding="utf-8")
        _, both, _ = self.look2(p)
        self.assertRegex(both, r"'-' underline x3")
        self.assertRegex(both, r"'=' underline x1")
        out = self.ask(p, "How many headings are underlined with hyphens?")
        self.assertRegex(out, r"Answer: 3 headings are underlined with '-'")

    def test_markdown_marks_and_setext(self):
        p = self.tmp / "doc.md"
        p.write_text(MD, encoding="utf-8")
        _, both, _ = self.look2(p)
        line = re.search(r"Heading styles[^\n]*", both)
        self.assertIsNotNone(line, both[:2500])
        txt = line.group(0)
        self.assertIn("'#' x1", txt)
        self.assertIn("'##' x2", txt)
        self.assertIn("'=' underline x1", txt)
        self.assertIn("'-' underline x2", txt)    # the fence holds a "Not / ---" pair that is not a heading
        out = self.ask(p, "How many headings are underlined with a line of hyphens (-)?")
        self.assertRegex(out, r"Answer: 2 headings are underlined with '-'")
        out = self.ask(p, "How many headings start with '##'?")
        self.assertRegex(out, r"Answer: 2 headings start with exactly '##'")

    def test_a_stray_rest_style_rule_does_not_hide_the_hash_headings(self):   # review: rst_scan saw "OK / ***" and returned only reST styles
        p = self.tmp / "stray.md"
        p.write_text("# One\n\nOK\n**********\n\n## Two\n\ntext\n\n## Three\n\ntext\n", encoding="utf-8")
        out = self.ask(p, "How many headings start with '##'?")
        self.assertRegex(out, r"Answer: 2 headings start with exactly '##'", out)

    def test_yaml_front_matter_is_not_a_heading(self):
        p = self.tmp / "front.md"
        p.write_text("---\ntitle: X\n---\n# One\n\ntext\n", encoding="utf-8")
        out = self.ask(p, "How many headings are underlined with a line of hyphens (-)?")
        self.assertRegex(out, r"Answer: 0 headings are underlined with '-'", out)

    def test_only_a_count_is_answered(self):
        p = self.tmp / "g3.rst"
        p.write_text(RST, encoding="utf-8")
        for q in ("What is the text of the first heading underlined with hyphens (-)?", "On which line is the last section title underlined with '='?",
                  "How many headings are underlined with a line of equal length to the title?"):
            out = self.ask(p, q)
            self.assertNotRegex(out, r"Answer: \d+ headings? (is|are) (over- and )?underlined", out)

    def test_a_file_without_headings_prints_no_styles_line(self):
        p = self.tmp / "none.rst"
        p.write_text("just words\nand more words\n", encoding="utf-8")
        _, both, _ = self.look2(p)
        self.assertNotIn("Heading styles", both)


# ------------------------------------------------------------------ (5) identifying values are not cut
LONG_TITLE = "Reading list subscriptions (synthetic, set 11) kept by the study circle for the autumn term of the second year"
VERY_LONG = "Annual register of subscriptions " * 10 + "end"


def opml(title, texts):
    texts = list(texts) + [f"Filler feed number {k} with a long enough name to make the file big" for k in range(400)]   # a file too big to be printed whole
    outs = "".join(f'<outline text="{t}" title="{t}"/>' for t in texts)
    return (f'<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head><title>{title}</title><dateCreated>Thu, 16 Oct 2025 07:20:00 GMT</dateCreated>'
            f'<ownerName>Study Circle Secretary</ownerName></head><body>{outs}</body></opml>')


class NoCutOfIdentifiers(Base):
    def test_short_helper(self):
        import dl_prof as P
        s = "word " * 30
        self.assertEqual(P.short_meta(s.strip()), s.strip())              # 149 characters: whole
        long = "x " * 150
        cut = P.short_meta(long.strip())
        self.assertTrue(cut.endswith("(cut, 299 chars)"), cut)
        self.assertLess(len(cut), 260)

    def test_opml_head_title_whole(self):
        self.assertGreater(len(LONG_TITLE), 60)
        p = self.tmp / "feeds.opml"
        p.write_text(opml(LONG_TITLE, ["Cooking", "Astronomy"]), encoding="utf-8")
        s1, both, _ = self.look2(p)
        self.assertIn(LONG_TITLE, s1 + both)
        self.assertNotIn("set 11) kept…", both)

    def test_a_very_long_value_is_cut_with_its_length_and_the_way_to_the_rest(self):
        p = self.tmp / "feeds2.opml"
        p.write_text(opml(VERY_LONG, ["Cooking", "Astronomy"]), encoding="utf-8")
        s1, both, _ = self.look2(p)
        self.assertRegex(s1 + both, r"\(cut, %d chars\)" % len(VERY_LONG))
        self.assertRegex(s1 + both, r"--grep")

    def test_a_long_sample_of_a_repeated_path_says_its_length(self):
        texts = ["Feed number %02d about gardening, cooking and many other long named topics" % k for k in range(1, 6)]
        p = self.tmp / "feeds3.opml"
        p.write_text(opml("Short", texts), encoding="utf-8")
        _, both, _ = self.look2(p)
        self.assertRegex(both, r"\(cut, %d chars\)" % len(texts[0]))

    def test_last_record_fields_stay_whole_when_short(self):
        note = "A note about the final shipment that is written in plain words and runs on for a while"
        self.assertGreater(len(note), 60)
        rows = ["id,note"] + [f"{i},short note {i}" for i in range(1, 3000)] + [f"3000,{note}"]
        p = self.tmp / "ledger.csv"
        p.write_text("\n".join(rows) + "\n", encoding="utf-8")
        s1, both, _ = self.look2(p)
        self.assertIn(f"note={note}", s1)

    def test_first_and_last_table_row_cells_of_a_document_stay_whole_when_short(self):
        cell = "The chemical name would be provided here in the final version"
        tbl = ("<w:tbl>" + "".join(f"<w:tr><w:tc>{wp('Name' + str(k))}</w:tc><w:tc>{wp(cell)}</w:tc></w:tr>" for k in range(3)) + "</w:tbl>")
        p = self.tmp / "tbl.docx"
        docx_file(p, wp("Intro") + tbl + "".join(wp(f"Filler paragraph number {k} of the document with some plain words in it.") for k in range(300)))
        s1, _, _ = self.look2(p)
        self.assertIn("last row: Name2 | " + cell, s1)


# ------------------------------------------------------------------ (6) the stored row size of a raster picture
def bmp_bytes(w, h, bpp, top_down=False):
    stride = ((w * bpp + 31) // 32) * 4
    pal = b"".join(bytes((i, i, i, 0)) for i in range(1 << bpp)) if bpp <= 8 else b""
    off = 14 + 40 + len(pal)
    data = b"".join(bytes(((x + y) % 251 for x in range(stride))) for y in range(h))
    head = b"BM" + struct.pack("<IHHI", off + len(data), 0, 0, off)
    info = struct.pack("<IiiHHIIiiII", 40, w, -h if top_down else h, 1, bpp, 0, len(data), 2835, 2835, len(pal) // 4, 0)
    return head + info + pal + data


def pcx_bytes(w, h, planes, bpp=8):
    bpl = ((w * bpp + 7) // 8 + 1) & ~1
    head = struct.pack("<BBBBHHHHHH", 10, 5, 1, bpp, 0, 0, w - 1, h - 1, 72, 72) + bytes(48) + struct.pack("<BBHH", 0, planes, bpl, 1) + bytes(58)
    return head + b"".join(bytes([k % 190 for k in range(planes * bpl)]) for _ in range(h))


def tga_bytes(w, h, bpp, top=True):
    head = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, w, h, bpp, 0x20 if top else 0)
    return head + bytes((k % 251 for k in range(w * h * bpp // 8)))


ROW_Q = "How many bytes does one stored pixel row occupy, including any padding at its end?"


class RowSize(Base):
    def test_bmp_8bit_width_1003(self):
        p = self.tmp / "plate.bmp"
        p.write_bytes(bmp_bytes(1003, 5, 8))
        s1, _, lj = self.look2(p)
        self.assertRegex(s1, r"stored row 1,004 bytes \(1,003 px x 8 bits = 1,003 bytes of pixels \+ 1 padding byte", s1)
        self.assertIn("bottom-up", s1)
        self.assertIn("pixel data at offset 1078", s1)
        out = self.ask(p, ROW_Q)
        self.assertRegex(out, r"Answer: 1,004 bytes per stored pixel row", out)
        self.assertIn("1,003", out)
        self.no_crash(lj)

    def test_bmp_other_depths_and_top_down(self):
        for w, bpp, row, pad in ((5, 24, 16, 1), (33, 1, 8, 3), (8, 32, 32, 0), (7, 4, 4, 0)):
            p = self.tmp / f"b{w}_{bpp}.bmp"
            p.write_bytes(bmp_bytes(w, 4, bpp, top_down=(bpp == 4)))
            s1, _, _ = self.look2(p)
            raw = (w * bpp + 7) // 8
            self.assertEqual(raw + pad, row)
            self.assertIn(f"stored row {row} bytes", s1, s1[:900])
            out = self.ask(p, ROW_Q)
            self.assertRegex(out, rf"Answer: {row} bytes per stored pixel row", out)
        self.assertIn("top-down", self.look2(self.tmp / "b7_4.bmp")[0])

    def test_pcx_three_planes(self):
        p = self.tmp / "seal.pcx"
        p.write_bytes(pcx_bytes(5, 4, 3))
        s1, _, _ = self.look2(p)
        self.assertRegex(s1, r"stored scan line 18 bytes \(3 planes x 6 bytes", s1)
        out = self.ask(p, ROW_Q)
        self.assertRegex(out, r"Answer: 18 bytes per stored pixel row", out)

    def test_tga_has_no_row_padding(self):
        p = self.tmp / "plate.tga"
        p.write_bytes(tga_bytes(5, 4, 24))
        s1, _, _ = self.look2(p)
        self.assertRegex(s1, r"TGA header: 5x4 px, 24 bits per pixel", s1)
        self.assertRegex(s1, r"stored row 15 bytes \(no row padding", s1)
        self.assertIn("top-down", s1)
        out = self.ask(p, ROW_Q)
        self.assertRegex(out, r"Answer: 15 bytes per stored pixel row", out)

    def test_a_header_without_a_pixel_layout_gives_no_row_size(self):   # review: bits per pixel 0 (an embedded JPEG or PNG) printed "0 bytes per stored pixel row"
        raw = bytearray(bmp_bytes(5, 4, 24))
        raw[28:30] = struct.pack("<H", 0)
        p = self.tmp / "nolayout.bmp"
        p.write_bytes(bytes(raw))
        s1, _, lj = self.look2(p)
        self.assertNotIn("stored row", s1)
        self.assertNotIn("bytes per stored pixel row", self.ask(p, ROW_Q))
        self.no_crash(lj)

    def test_a_question_about_rows_in_pixels_is_not_a_byte_question(self):
        p = self.tmp / "dims.bmp"
        p.write_bytes(bmp_bytes(5, 4, 24))
        out = self.ask(p, "What is the pixel size of the image: how many rows high and columns wide?")
        self.assertNotIn("bytes per stored pixel row", out)

    def test_a_pixel_question_still_goes_to_the_pixel_route(self):
        p = self.tmp / "pix.bmp"
        p.write_bytes(bmp_bytes(5, 4, 24))
        out = self.ask(p, "pixel 1,1")
        self.assertNotIn("bytes per stored pixel row", out)


# ------------------------------------------------------------------ (2) the clock of a video
PROBE = {"format": {"start_time": "1.429978"},
         "streams": [{"index": 0, "codec_type": "video", "start_time": "1.440000"}, {"index": 1, "codec_type": "audio", "start_time": "1.429978"},
                     {"index": 2, "codec_type": "audio", "start_time": "1.434667"}]}


class ClockUnits(unittest.TestCase):
    def test_clock_facts(self):
        import dl_mediax as M
        c = M.video_clock(PROBE)
        self.assertAlmostEqual(c["container"], 1.429978, 6)
        self.assertAlmostEqual(c["first_frame"], 1.44, 6)
        self.assertAlmostEqual(c["offset"], 0.010022, 6)

    def test_span_text_names_both_clocks(self):
        import dl_mediax as M
        c = M.video_clock(PROBE)
        # blackdetect counts from the container start: 0.0100222 .. 4.810022 -> 0.0 .. 4.8 after the first video frame
        self.assertEqual(M.span_text(0.0100222, 4.810022, c), "from 0.0 s to 4.8 s after the first video frame (container time 1.44 s to 6.24 s)")

    def test_clock_line_lists_every_start(self):
        import dl_mediax as M
        line = M.clock_line(M.video_clock(PROBE))
        for part in ("first video frame at container time 1.440 s", "container start 1.430 s", "audio #1 1.430 s", "audio #2 1.435 s", "video #0 1.440 s"):
            self.assertIn(part, line)
        self.assertIn("count from the first video frame", line)

    def test_no_offsets_still_says_where_the_spans_start(self):
        import dl_mediax as M
        c = M.video_clock({"format": {"start_time": "0.000000"}, "streams": [{"index": 0, "codec_type": "video", "start_time": "0.000000"}]})
        self.assertEqual(c["offset"], 0.0)
        self.assertEqual(M.span_text(2.0, 3.5, c), "from 2.0 s to 3.5 s after the first video frame (container time 2.00 s to 3.50 s)")

    def test_missing_starts_are_zero(self):
        import dl_mediax as M
        c = M.video_clock({"format": {}, "streams": [{"index": 0, "codec_type": "video"}]})
        self.assertEqual((c["container"], c["first_frame"], c["offset"]), (0.0, 0.0, 0.0))


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
class ClockInAVideo(Base):
    def base(self, path):   # the real tools: the video checks need ffmpeg
        out = self.tmp / ("out_" + path.name)
        return [str(path), "--out", str(out)], out

    def make(self, name, muxer):
        p = self.tmp / name
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=128x96:r=25:d=4.8,format=yuv420p[a];testsrc=s=128x96:r=25:d=3,format=yuv420p[b];[a][b]concat=n=2:v=1:a=0",
               "-f", "lavfi", "-i", "sine=f=700:sample_rate=48000:duration=7.8", "-c:v", "mpeg2video" if muxer == "mpegts" else "mpeg4", "-c:a", "mp2" if muxer == "mpegts" else "aac", "-f", muxer, str(p)]
        subprocess.run(cmd, check=True, capture_output=True)
        return p

    def starts(self, p):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time:format=start_time", "-of", "json", str(p)], capture_output=True, text=True).stdout
        j = json.loads(out)
        v = next(s for s in j["streams"] if s["codec_type"] == "video")
        return float(j["format"]["start_time"]), float(v["start_time"])

    def test_mpegts_black_lead_in_is_counted_from_the_first_video_frame(self):
        p = self.make("lead.ts", "mpegts")
        cs, vs = self.starts(p)
        self.assertGreater(vs, 1.0)
        s1, _, lj = self.look2(p)
        self.assertIn(f"first video frame at container time {vs:.3f} s", s1)
        self.assertIn(f"container start {cs:.3f} s", s1)
        self.assertIn(f"black from 0.0 s to 4.8 s after the first video frame (container time {vs:.2f} s to {vs + 4.8:.2f} s)", s1)
        self.assertRegex(s1, r"first non-black frame at 4\.8 s after the first video frame")
        flag = next(f for f in lj["flags"] if f["kind"] == "BLACK")
        self.assertIn("after the first video frame", flag["value"] if "value" in flag else json.dumps(flag))

    def test_a_video_that_is_black_to_its_end_has_no_first_non_black_frame(self):   # review
        p = self.tmp / "allblack.ts"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=128x96:r=25:d=3", "-f", "lavfi", "-i", "sine=f=700:sample_rate=48000:duration=3",
                        "-c:v", "mpeg2video", "-c:a", "mp2", "-f", "mpegts", str(p)], check=True, capture_output=True)
        s1, _, _ = self.look2(p)
        self.assertRegex(s1, r"black from 0\.0 s to \d\.\d s after the first video frame")
        self.assertNotIn("first non-black", s1)

    def test_mp4_names_its_clock_too(self):
        p = self.make("lead.mp4", "mp4")
        s1, _, _ = self.look2(p)
        self.assertRegex(s1, r"first video frame at container time [\d.]+ s", s1)
        self.assertRegex(s1, r"black from 0\.0 s to 4\.[78] s after the first video frame", s1)


if __name__ == "__main__":
    unittest.main()
