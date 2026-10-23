"""Fix round 11, lane F3 (ticket 83, P0.14b.H5): structure and count gaps of held-out set 10, on fixtures built here (none from a held-out set).

Families: (1) the magic bytes of a binary file, in hex, in the identity line (gettext .mo and every family detected by magic);
(2) the comment block of key/value files (.properties, .ini, .conf, YAML, TOML): the leading comment lines whole, how many comment lines
there are and where; (3) whole-word counts over the full text of a document (`--ask`), and the capitalised-word list of a document;
(4) hyperlinks, pictures and notes inside an Office package (odt, docx, pptx); (5) the header facts of a container: cabinet folders and
files, the zip end record, the 7z start header, the ISO volume, the OLE sector layout. Every expected figure is worked out here from the
data this file wrote, never read back from the look.
"""
import gzip
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r9 import doc_paragraphs  # noqa: E402
from test_v2_r10_f1 import cfb  # noqa: E402
from make_fixtures import tiny_png  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
FX = HERE / "fixtures"


class R11Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r11f3_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def base(self, path):
        out = self.tmp / ("out_" + path.name)
        return [str(path), "--out", str(out), "--no-tools"], out

    def look2(self, path, ok=(0,)):
        """Step 1 and the first --more (tier b): -> (step 1, both prints, look.json)."""
        base, out = self.base(path)
        shutil.rmtree(out, ignore_errors=True)
        a = run(base + ["--fresh"])
        self.assertIn(a.returncode, ok, a.stderr[-1500:] + a.stdout[-800:])
        b = run(base + ["--more"])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return a.stdout, a.stdout + "\n" + b.stdout, lj

    def ask(self, path, question):
        base, _ = self.base(path)
        r = run(base + ["--ask", question])
        self.assertEqual(r.returncode, 0, r.stderr[-1500:] + r.stdout[-800:])
        return r.stdout

    def no_crash(self, lj):
        self.assertNotIn("INTERNAL-ERROR", {f["kind"] for f in lj.get("flags", [])}, lj.get("flags"))


def identity_line(step1):
    return step1.splitlines()[1]


# ------------------------------------------------------------------ (1) magic bytes
def mo_bytes(pairs, big):
    """A GNU gettext .mo file: header, the two string tables, the strings (no hash table)."""
    e = ">" if big else "<"
    pairs = sorted(pairs)
    n = len(pairs)
    ids = [k for k, _ in pairs]
    trs = [v for _, v in pairs]
    pos = 28 + 16 * n
    blobs, otab, ttab = b"", [], []
    for s in ids:
        otab.append((len(s), pos + len(blobs)))
        blobs += s + b"\0"
    for s in trs:
        ttab.append((len(s), pos + len(blobs)))
        blobs += s + b"\0"
    head = struct.pack(e + "7I", 0x950412DE, 0, n, 28, 28 + 8 * n, 0, pos)
    return head + b"".join(struct.pack(e + "2I", *t) for t in otab + ttab) + blobs


class MagicBytes(R11Base):
    def test_gettext_mo_prints_its_first_four_bytes_in_file_order(self):
        for big in (True, False):
            raw = mo_bytes([(b"", b"Content-Type: text/plain; charset=UTF-8\n"), (b"Open", b"Aabn"), (b"Close", b"Luk"), (b"Save", b"Gem")], big)
            p = self.tmp / f"cat_{'be' if big else 'le'}.mo"
            p.write_bytes(raw)
            s1, both, lj = self.look2(p)
            self.assertIn(f"magic {raw[:4].hex()}", identity_line(s1), identity_line(s1))
            self.assertEqual(raw[:4].hex(), "950412de" if big else "de120495")
            self.assertIn("gettext", identity_line(s1))
            self.no_crash(lj)

    def test_every_family_found_by_its_magic_prints_it(self):
        files = {"a.png": tiny_png(), "b.gz": gzip.compress(b"hello hello hello\n" * 50), "c.zip": None, "d.bin": None}
        zp = self.tmp / "c.zip"
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("x.txt", "x")
        files["c.zip"] = zp.read_bytes()
        files.pop("d.bin")
        for name, raw in files.items():
            p = self.tmp / ("mg_" + name)
            p.write_bytes(raw)
            s1, _, lj = self.look2(p)
            self.assertIn(f"magic {raw[:4].hex()}", identity_line(s1), (name, identity_line(s1)))

    def test_plain_text_has_no_magic_token(self):
        p = self.tmp / "plain.csv"
        p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        s1, _, _ = self.look2(p)
        self.assertNotIn("magic ", identity_line(s1))


# ------------------------------------------------------------------ (2) comment blocks
class CommentBlocks(R11Base):
    def test_properties_comment_block_whole_and_where_the_rest_sit(self):
        lines = ["# Mensagens da aplicação, região portuguesa", "# Versão do ficheiro: 3.7", "# Codificação: ISO-8859-1", "! Caracteres fora de Latin-1",
                 "", "a.one=Olá", "a.two=Dois", "# nota no meio", "a.three=Três", "", "b.four=Quatro", "! fim"]
        p = self.tmp / "msg.properties"
        p.write_bytes(("\n".join(lines) + "\n").encode("latin-1"))
        s1, both, lj = self.look2(p)
        marks = [i for i, x in enumerate(lines, 1) if x.startswith(("#", "!"))]
        self.assertEqual(marks, [1, 2, 3, 4, 8, 12])
        self.assertIn("Comment lines: 6", both)
        self.assertIn("# Versão do ficheiro: 3.7", both)
        self.assertRegex(both, r"lines 1-4")
        self.assertIn("8", re.search(r"Comment lines: 6[^\n]*", both).group(0))
        self.assertIn("12", re.search(r"Comment lines: 6[^\n]*", both).group(0))
        self.no_crash(lj)

    def test_ini_and_yaml_and_toml_comments(self):
        ini = self.tmp / "c.ini"
        ini.write_text("; Config version: 9.1\n; maintained by ops\n[main]\nkey = 1\n# later note\nother = 2\n", encoding="utf-8")
        _, both, _ = self.look2(ini)
        self.assertIn("Comment lines: 3", both)
        self.assertIn("; Config version: 9.1", both)
        ym = self.tmp / "c.yaml"
        ym.write_text("# Schema version: 4.2\n# owner: platform\nname: demo\nitems:\n  - a\n  - b\n# trailing\n", encoding="utf-8")
        _, both, _ = self.look2(ym)
        self.assertIn("Comment lines: 3", both)
        self.assertIn("# Schema version: 4.2", both)
        tm = self.tmp / "c.toml"
        tm.write_text("# Release: 2.4.1\n# generated file\ntitle = 'x'\n[a]\nb = 1\n", encoding="utf-8")
        _, both, _ = self.look2(tm)
        self.assertIn("Comment lines: 2", both)
        self.assertIn("# Release: 2.4.1", both)

    def test_a_file_without_comments_prints_no_comment_line(self):
        p = self.tmp / "nc.properties"
        p.write_text("a=1\nb=2\n", encoding="utf-8")
        _, both, _ = self.look2(p)
        self.assertNotIn("Comment lines:", both)


# ------------------------------------------------------------------ (3) word counts over the full text
NS_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
CT = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="png" ContentType="image/png"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
RELS = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OD = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def docx_file(path, body_xml, doc_rels="", extra=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {NS_W}><w:body>{body_xml}</w:body></w:document>')
        if doc_rels:
            z.writestr("word/_rels/document.xml.rels", f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}">{doc_rels}</Relationships>')
        for k, v in (extra or {}).items():
            z.writestr(k, v)


def wp(text):
    return f"<w:p><w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


class WordCounts(R11Base):
    TEXT = ["Iraq’s army met Iraq on Monday.", "The Iraqi press and the Iraqi army.", "Saddam spoke. Saddam left. Then Iraq-based firms replied.",
            "iraq in lower case, IRAQ in capitals.", "Nothing here.", "Saddam again, and Iraq twice: Iraq."]

    def docx(self):
        p = self.tmp / "words.docx"
        docx_file(p, "".join(wp(t) for t in self.TEXT))
        return p

    def test_docx_counts_whole_word_case_sensitive(self):
        full = "\n".join(self.TEXT)
        exp = len(re.findall(r"\bIraq\b", full))
        self.assertEqual(exp, 5)
        out = self.ask(self.docx(), "How many times does the word 'Iraq' appear as a whole word with a capital I? (forms such as 'Iraq’s' count; 'Iraqi' does not)")
        self.assertRegex(out, rf"Answer: {exp} whole-word occurrences of 'Iraq'")
        self.assertIn("case-sensitive", out)

    def test_docx_paragraphs_with_the_word(self):
        exp = sum(1 for t in self.TEXT if re.search(r"\bSaddam\b", t))
        occ = len(re.findall(r"\bSaddam\b", "\n".join(self.TEXT)))
        self.assertEqual((exp, occ), (2, 3))
        out = self.ask(self.docx(), "In how many paragraphs does the word 'Saddam' appear?")
        self.assertRegex(out, rf"Answer: {exp} paragraphs contain 'Saddam'")
        self.assertIn(f"{occ} whole-word occurrences of 'Saddam'", out)

    def test_lower_case_question_is_case_insensitive(self):
        full = "\n".join(self.TEXT)
        exp = len(re.findall(r"\biraq\b", full, re.I))
        out = self.ask(self.docx(), "How many times does the word 'iraq' appear?")
        self.assertRegex(out, rf"Answer: {exp} whole-word occurrences of 'iraq'")
        self.assertIn("any case", out)

    def test_legacy_doc_counts_over_every_paragraph(self):
        paras = doc_paragraphs()
        a = sum(len(re.findall(r"\balpha\b", t)) for t in paras)
        part_paras = sum(1 for t in paras if re.search(r"\bPart\b", t))
        cap = sum(len(re.findall(r"\bParagraph\b", t)) for t in paras)
        self.assertEqual((a, part_paras, cap), (130, 4, 130))
        doc = FX / "r9_report.doc"
        self.assertRegex(self.ask(doc, "How many times does the word 'alpha' appear in the text?"), rf"Answer: {a} whole-word occurrences of 'alpha'")
        self.assertRegex(self.ask(doc, "In how many paragraphs does the word 'Part' appear?"), rf"Answer: {part_paras} paragraphs contain 'Part'")
        self.assertRegex(self.ask(doc, 'How many times does the word "Paragraph" appear as a whole word?'), rf"Answer: {cap} whole-word occurrences of 'Paragraph'")

    def test_page_question_on_text_without_pages(self):
        out = self.ask(self.docx(), "In how many pages does the word 'Saddam' appear?")
        self.assertIn("not countable per page", out)
        self.assertIn("2 of 6 non-empty paragraphs", out)

    def test_ocr_page_markers_are_markers(self):
        import dl_wordcount as W
        text = "<!-- page 1 -->\nfirst Iraq line\n<!-- page 2 (OCR) -->\nsecond Iraq line\nthird line\n"
        got = W.paragraphs(text)
        self.assertEqual([(t, u) for _, t, u in got], [("first Iraq line", 1), ("second Iraq line", 2), ("third line", 2)])

    def test_the_counted_text_is_named(self):
        out = self.ask(FX / "r9_report.doc", "How many times does the word 'gamma' appear?")
        self.assertRegex(out, r"text\.md")
        self.assertRegex(out, r"\d[\d,]* words")

    def test_a_question_without_a_quoted_word_is_left_to_the_old_path(self):
        out = self.ask(self.docx(), "How many paragraphs are there?")
        self.assertNotIn("whole-word occurrences", out)

    def test_capitalised_word_list_is_printed(self):
        s1, both, lj = self.look2(self.docx())
        cap, low = Counter(), Counter()
        for t in self.TEXT:
            for w in re.findall(r"[^\W\d_]{3,}", t):
                if w[0].isupper():
                    cap[w] += 1
                elif w == w.lower():
                    low[w] += 1
        # the rule: a capitalised word counts when it is written in lower case less often than with the capital
        top = sorted(((w, n) for w, n in cap.items() if n > low[w.lower()]), key=lambda t: (-t[1], t[0]))[:10]
        self.assertEqual(top[:3], [("Iraq", 5), ("Saddam", 3), ("Iraqi", 2)])
        line = re.search(r"Most frequent capitalised words[^\n]*", both)
        self.assertIsNotNone(line, both[-1500:])
        self.assertIn(": " + ", ".join(f"{w} {n}" for w, n in top) + ".", line.group(0))
        self.assertNotIn("The ", line.group(0).split("): ")[1])   # 'The' is written in lower case more often

    def test_legacy_doc_capitalised_words(self):
        _, both, _ = self.look2(FX / "r9_report.doc")
        line = re.search(r"Most frequent capitalised words[^\n]*", both)
        self.assertIsNotNone(line)
        self.assertIn("Paragraph 130", line.group(0))
        self.assertIn("Part 4", line.group(0))


class WordQuestionParsing(unittest.TestCase):
    def test_which_questions_are_word_counts(self):
        import dl_wordcount as W
        self.assertEqual(W.parse("How many times does Iraq appear in the text?"), ("Iraq", None, True, True))
        self.assertEqual(W.parse("How many paragraphs mention Saddam?"), ("Saddam", "paragraph", True, True))
        self.assertEqual(W.parse('How many pages contain "annual report"?'), ("annual report", "page", False, True))
        self.assertEqual(W.parse("How many times does 'x' appear, ignoring case?")[2], False)
        self.assertEqual(W.parse("How many times does 'X' appear, ignoring case?")[2], False)
        self.assertEqual(W.parse("How many times does the word 'x' appear as a substring?")[3], False)
        for q in ("How many paragraphs does the document have?", "How many words are in the document?", "What is the title?",
                  "How many times does 'Paris' appear in the city column?", "How many rows contain 'Paris'?"):
            self.assertIsNone(W.parse(q), q)


class RtfText(R11Base):
    PARAS = ["Iraq's report", "Saddam spoke at Café Noir.", "Price €5 and Iraq again.", "Closing line."]

    def rtf(self):
        body = ("{@rtf1@ansi@ansicpg1252@deff0{@fonttbl{@f0 Arial;}}{@colortbl;@red0@green0@blue0;}"
                "{@info{@title Field Notes}{@author Mara Quell}{@operator Ivo B}}"
                "{@header ignored header words}"
                "@pard Iraq's report@par "
                "Saddam spoke at Caf@'e9 Noir.@par "
                "Price @u8364?5 and {@b Iraq} again.{@footnote hidden footnote text}@par "
                "{@field{@*@fldinst HYPERLINK 'http://x.example'}{@fldrslt Closing line.}}@par "
                "{@pict@pngblip 89504e47}"
                "@trowd @intbl cell one@cell cell two@cell@row "
                "}").replace("@", chr(92))
        p = self.tmp / "notes.rtf"
        p.write_bytes(body.encode("latin-1"))
        return p

    def test_rtf_text_properties_and_counts(self):
        s1, both, lj = self.look2(self.rtf())
        self.assertEqual(lj["type"], "office")
        self.assertIn("Title: Field Notes", both)
        self.assertIn("Author: Mara Quell", both)
        paras = self.PARAS + ["cell one", "cell two"]
        self.assertRegex(both, rf"non-empty paragraphs {len(paras)}\b")
        self.assertIn("Café Noir", both)
        self.assertIn("€5", both)
        self.assertNotIn("ignored header words", both)
        self.assertNotIn("hidden footnote text", both)
        self.assertRegex(both, r"table rows 1\b")
        self.assertRegex(both, r"pictures 1\b")
        self.no_crash(lj)

    def test_rtf_emoji_pair_and_crlf_paragraph_break(self):
        bs = chr(92)
        body = ("{@rtf1@ansi Smile @u-10179?@u-8704? done@par first@" + chr(13) + chr(10) + "second@par}").replace("@", bs)
        p = self.tmp / "emoji.rtf"
        p.write_bytes(body.encode("latin-1"))
        _, both, lj = self.look2(p)
        self.assertIn(chr(0x1F600), both)
        paras = [x for x in (self.tmp / "out_emoji.rtf" / "text.md").read_text(encoding="utf-8").splitlines() if x]
        self.assertEqual(paras, ["Smile " + chr(0x1F600) + " done", "first", "second"])
        self.no_crash(lj)

    def test_rtf_word_counts_use_the_whole_text(self):
        out = self.ask(self.rtf(), "How many times does the word 'Iraq' appear?")
        exp = len(re.findall(r"\bIraq\b", "\n".join(self.PARAS)))
        self.assertEqual(exp, 2)
        self.assertRegex(out, rf"Answer: {exp} whole-word occurrences of 'Iraq'")


# ------------------------------------------------------------------ (4) hyperlinks, pictures, notes in packages
ODF_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" '
          'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"')
LINKS = ["https://example.org/a", "https://example.org/b?x=1&y=2", "mailto:ops@example.org"]


class PackageFacts(R11Base):
    def odt(self):
        png = tiny_png()
        body = ("<text:p>See <text:a xlink:href=\"https://example.org/a\">the audit</text:a> and <text:a xlink:href=\"https://example.org/b?x=1&amp;y=2\">more</text:a>.</text:p>"
                "<text:p>Mail <text:a xlink:href=\"mailto:ops@example.org\">ops</text:a>.</text:p>"
                "<text:p><draw:frame><draw:image xlink:href=\"Pictures/findings_chart.png\"/></draw:frame></text:p>")
        content = f'<?xml version="1.0"?><office:document-content {ODF_NS}><office:body><office:text>{body}</office:text></office:body></office:document-content>'
        p = self.tmp / "links.odt"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text")
            z.writestr("content.xml", content)
            z.writestr("Pictures/findings_chart.png", png)
        return p, len(png)

    def test_odt_hyperlinks_and_picture_path(self):
        p, size = self.odt()
        s1, both, lj = self.look2(p)
        self.assertRegex(both, r"Hyperlinks: 3\b")
        for t in LINKS:
            self.assertIn(t.replace("&", "&"), both)
        self.assertIn(f"Pictures/findings_chart.png ({size} bytes)", both)
        self.no_crash(lj)

    def test_docx_hyperlinks_media_and_notes(self):
        png = tiny_png()
        rels = "".join(f'<Relationship Id="rId{10 + i}" Type="{OD}/hyperlink" Target="{t.replace("&", "&amp;")}" TargetMode="External"/>' for i, t in enumerate(LINKS))
        rels += f'<Relationship Id="rId20" Type="{OD}/image" Target="media/image1.png"/>'
        body = "".join(f'<w:p><w:hyperlink r:id="rId{10 + i}"><w:r><w:t>link {i}</w:t></w:r></w:hyperlink></w:p>' for i in range(3)) + wp("closing")
        foot = (f'<?xml version="1.0"?><w:footnotes {NS_W}><w:footnote w:type="separator" w:id="-1"><w:p/></w:footnote><w:footnote w:type="continuationSeparator" w:id="0"><w:p/></w:footnote>'
                '<w:footnote w:id="1"><w:p><w:r><w:t>one</w:t></w:r></w:p></w:footnote><w:footnote w:id="2"><w:p><w:r><w:t>two</w:t></w:r></w:p></w:footnote></w:footnotes>')
        p = self.tmp / "links.docx"
        docx_file(p, body, rels, {"word/media/image1.png": png, "word/footnotes.xml": foot})
        s1, both, lj = self.look2(p)
        self.assertRegex(both, r"Hyperlinks: 3\b")
        for t in LINKS:
            self.assertIn(t, both)
        self.assertIn(f"word/media/image1.png ({len(png)} bytes)", both)
        self.assertRegex(both, r"[Ff]ootnotes 2\b")
        self.no_crash(lj)

    def test_pptx_hyperlinks_come_from_slide_relationships(self):
        p = self.tmp / "links.pptx"
        sl = ('<?xml version="1.0"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
              f'xmlns:r="{OD}"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:rPr><a:hlinkClick r:id="rId2"/></a:rPr><a:t>one</a:t></a:r></a:p>'
              '<a:p><a:r><a:rPr><a:hlinkClick r:id="rId3"/></a:rPr><a:t>two</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
        pres = ('<?xml version="1.0"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                f'xmlns:r="{OD}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>')
        ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("[Content_Types].xml", ct)
            z.writestr("_rels/.rels", RELS.replace("word/document.xml", "ppt/presentation.xml"))
            z.writestr("ppt/presentation.xml", pres)
            z.writestr("ppt/_rels/presentation.xml.rels", f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}"><Relationship Id="rId1" Type="{OD}/slide" Target="slides/slide1.xml"/></Relationships>')
            z.writestr("ppt/slides/slide1.xml", sl)
            z.writestr("ppt/slides/_rels/slide1.xml.rels", f'<?xml version="1.0"?><Relationships xmlns="{REL_NS}">'
                       f'<Relationship Id="rId2" Type="{OD}/hyperlink" Target="https://example.org/s1" TargetMode="External"/>'
                       f'<Relationship Id="rId3" Type="{OD}/hyperlink" Target="https://example.org/s2" TargetMode="External"/></Relationships>')
            z.writestr("ppt/media/image1.png", tiny_png())
        _, both, lj = self.look2(p)
        self.assertRegex(both, r"Hyperlinks: 2\b")
        self.assertIn("https://example.org/s2", both)
        self.assertIn("ppt/media/image1.png", both)
        self.no_crash(lj)


# ------------------------------------------------------------------ (5) container header facts
def cab_bytes(folders, block=64, set_id=4711, icab=2, prev=None, nxt=None, reserve=None):
    """A Microsoft cabinet: folders = [(type, [(name, data)])]. Type 0 stores, type 1 (MSZIP) deflates each data block.
    prev / nxt: (cabinet name, disk name) of the neighbour cabinets. reserve: (header bytes, folder bytes, data bytes) of reserved space."""
    cffile, cfdata, cffolder = b"", [], []
    start_of_data = 0
    nfiles = 0
    fdata_blocks = []
    for fi, (ctype, files) in enumerate(folders):
        blob = b"".join(d for _, d in files)
        blocks = [blob[i:i + block] for i in range(0, len(blob), block)] or [b""]
        enc = []
        for b in blocks:
            if ctype == 1:
                co = zlib.compressobj(9, zlib.DEFLATED, -15)
                body = b"CK" + co.compress(b) + co.flush()
            else:
                body = b
            enc.append(struct.pack("<IHH", 0, len(body), len(b)) + body)
        fdata_blocks.append(enc)
        off = 0
        for name, d in files:
            cffile += struct.pack("<IIHHHH", len(d), off, fi, 0x5A21, 0x6000, 0x20) + name.encode() + b"\0"
            off += len(d)
            nfiles += 1
    n_folders = len(folders)
    flags = (1 if prev else 0) | (2 if nxt else 0) | (4 if reserve else 0)
    mid = b""
    if reserve:
        mid += struct.pack("<HBB", *reserve) + bytes(reserve[0])
    for pair in (prev, nxt):
        if pair:
            mid += pair[0].encode() + bytes(1) + pair[1].encode() + bytes(1)
    fres = reserve[1] if reserve else 0
    coff_files = 36 + len(mid) + (8 + fres) * n_folders
    first_data = coff_files + len(cffile)
    cur = first_data
    folder_bytes = b""
    for (ctype, _), enc in zip(folders, fdata_blocks):
        folder_bytes += struct.pack("<IHH", cur, len(enc), ctype) + bytes(fres)
        cur += sum(len(x) for x in enc)
    total = cur
    head = b"MSCF" + struct.pack("<IIIIIBBHHHHH", 0, total, 0, coff_files, 0, 3, 1, n_folders, nfiles, flags, set_id, icab)
    return head + mid + folder_bytes + cffile + b"".join(b"".join(e) for e in fdata_blocks)


class ContainerHeaders(R11Base):
    def cab(self):
        f0 = [("docs\\a.txt", b"alpha " * 40), ("docs\\b.txt", b"beta " * 30)]
        f1 = [("data\\c.csv", b"x,y\n1,2\n" * 50)]
        f2 = [("d.bin", bytes(range(256)) * 2), ("e.txt", b"end"), ("f.txt", b"fin")]
        folders = [(0, f0), (1, f1), (0, f2)]
        return cab_bytes(folders, block=64), folders

    def test_cab_header_folders_files_and_blocks(self):
        raw, folders = self.cab()
        p = self.tmp / "three.cab"
        p.write_bytes(raw)
        s1, both, lj = self.look2(p)
        nfiles = sum(len(f) for _, f in folders)
        self.assertEqual(nfiles, 6)
        self.assertRegex(both, r"folders \(compression groups\) 3\b")
        self.assertRegex(both, rf"files {nfiles}\b")
        self.assertIn(f"cabinet size {len(raw):,} bytes", both)
        self.assertRegex(both, r"set id 4711\b")
        self.assertRegex(both, r"cabinet index 2\b")
        for i, (ctype, files) in enumerate(folders):
            blob = b"".join(d for _, d in files)
            blocks = max(1, -(-len(blob) // 64))
            name = {0: "stored", 1: "MSZIP"}[ctype]
            self.assertIn(f"folder {i}: {name}, {blocks} data blocks, {len(files)} files", both)
        self.assertIn("docs\\a.txt", both)
        self.no_crash(lj)

    def test_cab_with_neighbours_and_reserved_space(self):
        folders = [(0, [("a.txt", b"one" * 30)]), (1, [("b.txt", b"two" * 90), ("c.txt", b"three")])]
        raw = cab_bytes(folders, prev=("disk1.cab", "Disk One"), nxt=("disk3.cab", "Disk Three"), reserve=(6, 4, 2))
        p = self.tmp / "chain.cab"
        p.write_bytes(raw)
        _, both, lj = self.look2(p)
        self.assertRegex(both, r"folders \(compression groups\) 2\b")
        self.assertIn("flags 0x0007 (previous cabinet, next cabinet, reserve area)", both)
        self.assertIn("continues from cabinet 'disk1.cab' (disk 'Disk One')", both)
        self.assertIn("continues in cabinet 'disk3.cab' (disk 'Disk Three')", both)
        self.assertIn("folder 1: MSZIP, 5 data blocks, 2 files (b.txt, c.txt)", both)
        self.no_crash(lj)

    def test_cab_header_in_step_one(self):
        raw, _ = self.cab()
        p = self.tmp / "three_s1.cab"
        p.write_bytes(raw)
        s1, _, _ = self.look2(p)
        self.assertRegex(s1, r"folders \(compression groups\) 3\b")

    def test_zip_end_record(self):
        p = self.tmp / "ender.zip"
        with zipfile.ZipFile(p, "w") as z:
            for i in range(4):
                z.writestr(f"m{i}.txt", "x" * (10 + i))
            z.comment = b"build 2026-10-23 nightly"
        with zipfile.ZipFile(p) as z:
            n, off, size = len(z.namelist()), z.start_dir, p.stat().st_size - z.start_dir - 22 - len(z.comment)
        _, both, lj = self.look2(p)
        self.assertIn(f"Zip end record: {n} entries declared", both)
        self.assertIn(f"central directory {size:,} bytes at byte {off:,}", both)
        self.assertIn("comment 24 bytes: 'build 2026-10-23 nightly'", both)
        self.no_crash(lj)

    def test_7z_start_header(self):
        body = b"\0" * 200
        nh_off, nh_size = len(body) - 60, 60
        start = struct.pack("<QQI", nh_off, nh_size, 0)
        raw = b"7z\xbc\xaf\x27\x1c" + bytes([0, 4]) + struct.pack("<I", zlib.crc32(start)) + start + body
        p = self.tmp / "head.7z"
        p.write_bytes(raw)
        _, both, lj = self.look2(p)
        self.assertIn("7z start header: format version 0.4", both)
        self.assertIn(f"next header ({nh_size} bytes) at byte {32 + nh_off}", both)
        self.no_crash(lj)

    def test_rar_versions_and_flags(self):
        sig4 = b"Rar!" + bytes([0x1A, 7, 0])
        main4 = struct.pack("<HBHH", 0x1234, 0x73, 0x0008 | 0x0080, 13) + bytes(6)   # solid, encrypted headers
        p4 = self.tmp / "v4.rar"
        p4.write_bytes(sig4 + main4 + bytes(64))
        _, both, lj = self.look2(p4)
        self.assertIn("RAR 4.x archive", both)
        self.assertIn("solid, encrypted headers", both)
        self.no_crash(lj)
        sig5 = b"Rar!" + bytes([0x1A, 7, 1, 0])
        main5 = struct.pack("<I", 0xDEADBEEF) + bytes([8, 1, 0, 0x04]) + bytes(40)     # size 8, type 1 (main), flags 0, archive flags 4 (solid)
        p5 = self.tmp / "v5.rar"
        p5.write_bytes(sig5 + main5)
        _, both, lj = self.look2(p5)
        self.assertIn("RAR 5.x archive", both)
        self.assertIn("(solid)", both)
        self.no_crash(lj)

    def test_iso_volume_descriptor(self):
        raw = bytearray(0x8800 + 2048)
        pvd = 0x8000
        raw[pvd:pvd + 7] = b"\x01CD001\x01"
        raw[pvd + 8:pvd + 40] = b"LINUX".ljust(32)
        raw[pvd + 40:pvd + 72] = b"BACKUP_2026".ljust(32)
        blocks, bs = 1234, 2048
        raw[pvd + 80:pvd + 88] = struct.pack("<I", blocks) + struct.pack(">I", blocks)
        raw[pvd + 128:pvd + 132] = struct.pack("<H", bs) + struct.pack(">H", bs)
        p = self.tmp / "vol.iso"
        p.write_bytes(bytes(raw))
        _, both, lj = self.look2(p)
        self.assertIn("volume id 'BACKUP_2026'", both)
        self.assertIn(f"{blocks:,} blocks of {bs:,} bytes", both)
        self.no_crash(lj)

    def test_ole_version_4_sectors_and_a_difat_chain(self):
        end, nostream, fatsec, difsec = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD, 0xFFFFFFFC
        ssz, sig = 4096, bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])

        def entry(name, typ, right=nostream, child=nostream):
            nm = (name + chr(0)).encode("utf-16-le")
            return nm.ljust(64, bytes(1)) + struct.pack("<HBB", len(nm), typ, 1) + struct.pack("<III", nostream, right, child) + bytes(36) + struct.pack("<IQ", 0, 0)
        hdr = bytearray(ssz)
        hdr[0:8] = sig
        struct.pack_into("<HHHHH", hdr, 24, 0x3E, 4, 0xFFFE, 12, 6)
        struct.pack_into("<9I", hdr, 40, 1, 1, 1, 0, 4096, end, 0, end, 0)
        struct.pack_into("<109I", hdr, 76, 0, *([nostream] * 108))
        fat = struct.pack("<1024I", fatsec, end, *([nostream] * 1022))   # sector 0 is the FAT, sector 1 the directory
        n = 30
        d = entry("Root Entry", 5, child=1) + b"".join(entry(f"S{i}", 2, right=i + 1 if i < n else nostream) for i in range(1, n + 1))
        raw = bytes(hdr) + fat + d.ljust(ssz, bytes(1))
        p = self.tmp / "v4.bin"
        p.write_bytes(raw)
        _, both, lj = self.look2(p)
        self.assertIn("OLE compound file header: version 4.", both)
        self.assertIn("sector size 4096 bytes", both)
        self.assertIn(f"directory: {n} streams, 0 storages", both)
        self.no_crash(lj)

    def test_ole_sector_layout(self):
        p = self.tmp / "layout.bin"
        raw = cfb({"One": b"a" * 5000, "Two": b"b" * 100, "Three": b"c" * 9000})
        p.write_bytes(raw)
        nfat = struct.unpack_from("<I", raw, 44)[0]
        first_dir = struct.unpack_from("<I", raw, 48)[0]
        cutoff = struct.unpack_from("<I", raw, 56)[0]
        _, both, lj = self.look2(p)
        self.assertIn(f"OLE compound file header: version 3.", both)
        self.assertIn("sector size 512 bytes", both)
        self.assertIn(f"{nfat} FAT sector", both)
        self.assertIn(f"first directory sector {first_dir}", both)
        self.assertIn(f"mini stream cutoff {cutoff}", both)
        self.assertIn("directory: 3 streams", both)
        self.no_crash(lj)

    def test_damaged_containers_never_crash(self):
        from test_v2_r10_f2 import mutants
        raw, _ = self.cab()
        zp = self.tmp / "z.zip"
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("a.txt", "a" * 100)
            z.comment = b"hello"
        pf, wc, rt = PackageFacts("odt"), WordCounts("docx"), RtfText("rtf")
        for o in (pf, wc, rt):
            o.tmp = self.tmp
        cases = (("m.cab", raw), ("m.zip", zp.read_bytes()), ("m.ole", cfb({"One": b"a" * 5000})), ("m.mo", mo_bytes([(b"", b"x"), (b"a", b"b")], True)),
                 ("m.properties", b"# c\n# d\na=1\n"), ("m.odt", pf.odt()[0].read_bytes()), ("m.docx", wc.docx().read_bytes()), ("m.rtf", rt.rtf().read_bytes()),
                 ("m.doc", (FX / "r9_report.doc").read_bytes()))
        for name, data in cases:
            for k, m in enumerate(mutants(data, 9, seed=11)):
                p = self.tmp / f"{k}_{name}"
                p.write_bytes(m)
                base, out = self.base(p)
                shutil.rmtree(out, ignore_errors=True)
                r = run(base + ["--fresh"])
                self.assertIn(r.returncode, (0, 1, 2, 3), r.stderr[-800:])
                lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
                self.no_crash(lj)
                a = run(base + ["--ask", "How many times does the word 'a' appear?"])
                self.assertIn(a.returncode, (0, 1, 2, 3), a.stderr[-800:])
                self.assertNotIn("Traceback", a.stderr)


if __name__ == "__main__":
    unittest.main()
