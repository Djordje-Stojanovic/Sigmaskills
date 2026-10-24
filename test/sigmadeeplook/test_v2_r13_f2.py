"""Fix round 13, lane F2 (ticket 83, P0.14b.H5): facts that held-out set 12 showed only in the 10k print, on fixtures built here
(none from a held-out set). The default print (step 1 and the first --more) must carry them, or point to the `--ask` route that answers them.

Items: (1) the explicit targets / link definitions / anchors / labels of a markup file: count, first and last with line numbers, and
`--ask` for the first or last one; (2) the depth of a tree: levels of an XML document and of a nested element (OPML), the nesting depth of
JSON/YAML/TOML, and `--ask "deepest nesting level"`; (3) a one-line `Ask a word count:` pointer in step 1 of every document-like file, whose
example form works when filled in; (4) the gpkg_contents table of a GeoPackage, and the complete table list of a SQLite file (up to 60 tables).
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import json
import re
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS  # noqa: E402
from test_v2_r12_f1 import R12Base, cue_file  # noqa: E402
from test_v2_r11_f3 import docx_file, wp  # noqa: E402
from r5_fixtures import odf_zip, ODF_NS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))


class Base(R12Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r13f2_"))

    def both(self, path):
        """Step 1 and the first --more, as one text."""
        return self.prints(path)[0]

    def line_of(self, text, head):
        return next((x for x in text.splitlines() if x.lstrip("- ").startswith(head)), None)


DEFS = re.compile(r"(\d+); first '([^']+)' \(line (\d+)\), last '([^']+)' \(line (\d+)\)")


def parts(ln):
    m = DEFS.search(ln or "")
    assert m, ln
    return int(m.group(1)), m.group(2), int(m.group(3)), m.group(4), int(m.group(5))


# ------------------------------------------------------------------ (1) targets, link definitions, anchors, labels
def rst_text(labels, pad=3):
    """A reST file with `.. _label:` lines; -> (text, [(line, label)])."""
    lines, want = ["Title", "=====", ""], []
    for k, lab in enumerate(labels):
        lines.append(f".. _{lab}:")
        want.append((len(lines), lab))
        lines += ["", f"Section {k}", "-" * 10, ""] + [f"Body line {j} of section {k}." for j in range(pad)] + [""]
    return "\n".join(lines) + "\n", want


class MarkupAnchors(Base):
    def test_rst_step_one_has_count_first_and_last_target(self):
        labels = ["intro-part", "mid_part", "tut-codingstyle-x", "aa-last-one"]
        text, want = rst_text(labels)
        p = self.tmp / "guide.rst"
        p.write_text(text, encoding="utf-8")
        step1 = self.step1(p)
        ln = self.line_of(step1, "Explicit targets")
        self.assertIsNotNone(ln, step1[:2500])
        n, first, fl, last, ll = parts(ln)
        self.assertEqual(n, 4)
        self.assertEqual((first, fl), (want[0][1], want[0][0]))
        self.assertEqual((last, ll), (want[-1][1], want[-1][0]), "the last target is the last by line, not by name")

    def test_ask_for_the_last_and_first_explicit_target(self):
        text, want = rst_text(["gamma-one", "alpha-two", "mid-three", "beta-last"])
        p = self.tmp / "ask_targets.rst"
        p.write_text(text, encoding="utf-8")
        for q in ("What is the label of the last explicit target ('.. _label:') in the file?", "Which hyperlink target is the last one defined in the file?",
                  "what is the last explicit target label"):
            with self.subTest(q=q):
                out = self.raw(p, q)
                self.assertRegex(out, rf"Answer: .*'{want[-1][1]}' \(line {want[-1][0]}\)", out)
        out = self.raw(p, "What is the first explicit target in the file?")
        self.assertRegex(out, rf"Answer: .*'{want[0][1]}' \(line {want[0][0]}\)", out)
        out = self.raw(p, "How many explicit targets does the file define?")
        self.assertRegex(out, r"Answer: 4\b", out)

    def test_no_line_when_the_file_has_none(self):
        p = self.tmp / "plain_notes.rst"
        p.write_text("Notes\n=====\n\nJust text.\n\nMore text.\n", encoding="utf-8")
        self.assertIsNone(self.line_of(self.step1(p), "Explicit targets"))
        out = self.raw(p, "What is the last explicit target?")
        self.assertNotIn("Answer: last", out)

    def test_review_a_word_count_about_the_word_target_is_not_an_anchor_question(self):
        text, _ = rst_text(["alpha-one", "beta-two"])
        p = self.tmp / "word_target.rst"
        p.write_text(text + "\nThe target is the target of the target.\n", encoding="utf-8")
        out = self.raw(p, "How many times does the word 'target' appear?")
        self.assertRegex(out, r"Answer: 3 whole-word occurrences of 'target'", out)

    def test_review_anonymous_targets_have_no_label_and_other_suffixes_are_not_markup(self):
        import dl_r13
        self.assertEqual(dl_r13.defs(["", ".. __: http://x.example", ".. _named: http://y.example"], "rst"), [(3, "named")])
        self.assertIsNone(dl_r13.family("memo.docx", [".. note:: a", ".. warning:: b"]))
        self.assertEqual(dl_r13.family("notes.txt", [".. note:: a", ".. warning:: b"]), "rst")

    def test_markdown_reference_definitions(self):
        lines = ["# Notes", "", "See [one][a], [two][b] and [three][zeta].", "", "```", "[fake]: http://in.a.fence", "```", "", "- [x] a task box", "A footnote[^1].", "",
                 "[a]: http://x.example/a", '[b]: http://x.example/b "Title"', "[^1]: the footnote text", "[zeta]: <http://x.example/z>", ""]
        p = self.tmp / "refs.md"
        p.write_text("\n".join(lines), encoding="utf-8")
        ln = self.line_of(self.step1(p), "Link definitions")
        self.assertEqual(parts(ln), (3, "a", 12, "zeta", 15), ln)
        out = self.raw(p, "What is the last link reference definition in the file?")
        self.assertRegex(out, r"Answer: .*'zeta' \(line 15\)", out)

    def test_asciidoc_anchors(self):
        text = "= Title\n\n[[intro]]\n== Intro\nSee <<later>>.\n\n[[later]]\n== Later\nText [[inline-one]] more.\n\n[[final-anchor,Final]]\n== End\n"
        p = self.tmp / "manual.adoc"
        p.write_text(text, encoding="utf-8")
        ln = self.line_of(self.step1(p), "Anchors")
        self.assertEqual(parts(ln), (4, "intro", 3, "final-anchor", 11), ln)
        out = self.raw(p, "What is the last anchor id in the file?")
        self.assertRegex(out, r"Answer: .*'final-anchor' \(line 11\)", out)

    def test_org_targets(self):
        text = "* Heading one\nSome <<target-a>> text, a link <<<radio>>> and [[file:x.org][a link]].\n** Sub\nmore <<target-b>> here\n"
        p = self.tmp / "notes.org"
        p.write_text(text, encoding="utf-8")
        ln = self.line_of(self.step1(p), "Targets")
        self.assertEqual(parts(ln), (2, "target-a", 2, "target-b", 4), ln)

    def test_latex_labels(self):
        text = ("\\documentclass{article}\n\\begin{document}\n\\section{One}\\label{sec:one}\n% \\label{commented}\ntext \\label{eq:a}\n"
                "\\section{Two}\\label{sec:two}\n\\end{document}\n")
        p = self.tmp / "paper.tex"
        p.write_text(text, encoding="utf-8")
        ln = self.line_of(self.step1(p), "Labels")
        self.assertEqual(parts(ln), (3, "sec:one", 3, "sec:two", 6), ln)
        out = self.raw(p, "What is the last \\label in the file?")
        self.assertRegex(out, r"Answer: .*'sec:two' \(line 6\)", out)


# ------------------------------------------------------------------ (2) depth of a tree
def opml_text():
    """An outline tree with 3 categories (level 1), 5 nodes at level 2, 8 at level 3 and 2 at level 4; the head holds other elements."""
    body = ('<outline text="Cat 1"><outline text="b1"><outline text="c1"/><outline text="c2"/><outline text="c3"/></outline>'
            '<outline text="b2"><outline text="c4"/><outline text="c5"/><outline text="c6"><outline text="d1"/><outline text="d2"/></outline></outline></outline>'
            '<outline text="Cat 2"><outline text="b3"/></outline>'
            '<outline text="Cat 3"><outline text="b4"/><outline text="b5"><outline text="c7"/><outline text="c8"/></outline></outline>')
    xml = f'<?xml version="1.0"?><opml version="2.0"><head><title>Feeds</title><ownerName>Desk</ownerName></head><body>{body}</body></opml>'
    return xml, [3, 5, 8, 2]


TREE = '<?xml version="1.0"?>\n<r><a><b><c/><c/></b><b/></a><a><b><c><d/></c></b></a><z/></r>'   # levels from the root (level 0): 1, 3, 3, 3, 1


class TreeDepth(Base):
    def test_opml_nested_levels_line(self):
        xml, per = opml_text()
        p = self.tmp / "feeds.opml"
        p.write_text(xml, encoding="utf-8")
        step1 = self.step1(p)
        ln = self.line_of(step1, "Nested <outline> levels")
        self.assertIsNotNone(ln, step1[:3000])
        self.assertRegex(ln, r"\b4 levels?\b", ln)
        self.assertIn("level 1", ln)
        self.assertIn(", ".join(str(x) for x in per), ln)

    def test_xml_tree_levels_line(self):
        p = self.tmp / "tree.xml"
        p.write_text(TREE, encoding="utf-8")
        ln = self.line_of(self.step1(p), "Tree levels")
        self.assertIsNotNone(ln)
        self.assertIn("level 4", ln)
        self.assertIn("1, 3, 3, 3, 1", ln)
        self.assertIn("root", ln)

    def test_ask_deepest_nesting_level_of_a_named_element(self):
        xml, per = opml_text()
        p = self.tmp / "feeds_ask.opml"
        p.write_text(xml, encoding="utf-8")
        for q in ("What is the deepest nesting level of the outline elements? (A category directly under the body is level 1.)",
                  "How deep do the outline elements nest?", "what is the maximum depth of nesting of the outline elements"):
            with self.subTest(q=q):
                out = self.raw(p, q)
                self.assertRegex(out, r"Answer: 4\b", out)
                self.assertIn(", ".join(str(x) for x in per), out)

    def test_ask_deepest_level_of_the_whole_document(self):
        p = self.tmp / "tree_ask.xml"
        p.write_text(TREE, encoding="utf-8")
        out = self.raw(p, "What is the deepest nesting level of the elements?")
        self.assertRegex(out, r"Answer: .*level 5\b", out)       # root counted as level 1: r > a > b > c > d
        self.assertIn("level 4 with the root as level 0", out)

    def test_json_and_toml_nesting_depth(self):
        p = self.tmp / "deep.json"
        p.write_text(json.dumps({"a": {"b": [{"c": {"d": 1}}, 2]}, "e": [1, 2]}), encoding="utf-8")
        # containers: top object (1) > a (2) > list (3) > object (4) > c (5): five levels
        self.assertRegex(self.step1(p), r"max nesting depth[^;\n]*\b5\b")
        out = self.raw(p, "What is the deepest nesting level?")
        self.assertRegex(out, r"Answer: 5\b", out)
        t = self.tmp / "deep.toml"
        t.write_text('title = "x"\n[a]\nk = 1\n[a.b]\nk = 2\n[a.b.c]\nk = 3\n', encoding="utf-8")
        out = self.raw(t, "What is the deepest nesting level?")
        self.assertRegex(out, r"Answer: 4\b", out)       # top table > a > b > c

    def test_a_table_question_is_still_a_table_question(self):
        p = self.tmp / "levels.csv"
        p.write_text("name,level\n" + "\n".join(f"n{i},{i % 7}" for i in range(1, 60)) + "\n", encoding="utf-8")
        out = self.raw(p, "What is the maximum level?")
        self.assertRegex(out, r"Answer: .*6", out)
        self.assertNotIn("nesting", out)


# ------------------------------------------------------------------ (3) the word-count pointer
WORDS = ["Canada water Canada-Mexico", "No match here", "Canadian only", "Canada again and Canada", "more water"]


def fill(step1, word="Canada"):
    """The printed example of `Ask a word count:` with X replaced by a real word -> (the line, the question)."""
    ln = next((x for x in step1.splitlines() if x.lstrip("- ").startswith("Ask a word count")), None)
    assert ln, step1[:2500]
    m = re.search(r'--ask "([^"]*X[^"]*)"', ln)
    assert m, ln
    return ln, m.group(1).replace("X", word)


class WordCountPointer(Base):
    def check(self, path, unit, want):
        step1 = self.step1(path)
        ln, q = fill(step1)
        self.assertIn(unit, ln, ln)
        self.assertLess(len(ln), 330, ln)       # one short line
        self.assertIn("whole word", ln)
        out = self.raw(path, q)
        self.assertRegex(out, rf"Answer: {want} ", out)

    def test_docx_paragraphs(self):
        p = self.tmp / "memo.docx"
        docx_file(p, "".join(wp(t) for t in WORDS))
        self.check(p, "paragraphs", 2)

    def test_odt_paragraphs(self):
        body = "".join(f"<text:p>{t}</text:p>" for t in WORDS)
        content = f'<?xml version="1.0"?><office:document-content {ODF_NS}><office:body><office:text>{body}</office:text></office:body></office:document-content>'
        meta = f'<?xml version="1.0"?><office:document-meta {ODF_NS}><office:meta><dc:title>T</dc:title></office:meta></office:document-meta>'
        p = self.tmp / "memo.odt"
        odf_zip(p, "application/vnd.oasis.opendocument.text", content, meta)
        self.check(p, "paragraphs", 2)

    def test_rtf_paragraphs(self):
        bs = chr(92)
        p = self.tmp / "memo.rtf"
        p.write_bytes(("{@rtf1@ansi@deff0 " + "".join(t + "@par " for t in WORDS) + "}").replace("@", bs).encode("latin-1"))
        self.check(p, "paragraphs", 2)

    def test_pptx_slides(self):
        P_ = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
        p = self.tmp / "deck.pptx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("[Content_Types].xml", ct)
            z.writestr("ppt/presentation.xml", f'<?xml version="1.0"?><p:presentation {P_}/>')
            for i, t in enumerate(WORDS, 1):
                z.writestr(f"ppt/slides/slide{i}.xml", f'<?xml version="1.0"?><p:sld {P_}><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{t}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
        self.check(p, "slides", 2)

    def test_plain_text_markdown_and_rst(self):
        for ext in ("txt", "md", "rst"):
            p = self.tmp / f"notes.{ext}"
            p.write_text("\n\n".join(WORDS) + "\n", encoding="utf-8")
            with self.subTest(ext=ext):
                ln, q = fill(self.step1(p))
                self.assertRegex(ln, r"paragraphs|lines")
                out = self.raw(p, q)
                self.assertRegex(out, r"Answer: 2 ", out)

    def test_subtitle_cues(self):
        for kind in ("srt", "vtt", "sbv"):
            data, cs = cue_file(kind)
            p = self.tmp / f"talk.{kind}"
            p.write_bytes(data)
            with self.subTest(kind=kind):
                ln, q = fill(self.step1(p), "riego")
                self.assertIn("cues", ln)
                want = sum(1 for *_, ls, _ in cs if any(re.search(r"(?<!\w)riego(?!\w)", x) for x in ls))
                self.assertGreater(want, 0)
                self.assertRegex(self.raw(p, q), rf"Answer: {want} cue")

    def test_no_pointer_for_a_table(self):
        p = self.tmp / "grid.csv"
        p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        self.assertIsNone(self.line_of(self.step1(p), "Ask a word count"))


# ------------------------------------------------------------------ (4) GeoPackage contents, SQLite table list
def make_gpkg(path, n_extra=0):
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT, description TEXT, srs_id INTEGER)")
    rows = [("trail_segments", "features", "trails", "", 3035), ("foresters", "attributes", "foresters", "", 0), ("forest_stands", "features", "stands", "", 3035),
            ("species_codes", "attributes", "species", "", 0), ("observation_points", "features", "obs", "", 3035)]
    rows += [(f"layer_{k:03d}", "features" if k % 3 else "attributes", f"id{k}", "", 3035) for k in range(n_extra)]
    con.executemany("INSERT INTO gpkg_contents VALUES (?,?,?,?,?)", rows)
    for r in rows:
        con.execute(f'CREATE TABLE "{r[0]}" (fid INTEGER PRIMARY KEY, name TEXT)')
        con.execute(f'INSERT INTO "{r[0]}" VALUES (1, \'x\')')
    con.commit()
    con.close()
    return rows


class GeoPackageContents(Base):
    def test_small_gpkg_contents_are_listed_with_counts(self):
        p = self.tmp / "small.gpkg"
        rows = make_gpkg(p)
        step1 = self.step1(p)
        ln = self.line_of(step1, "GeoPackage contents")
        self.assertIsNotNone(ln, step1[:3000])
        self.assertIn("gpkg_contents", ln)
        for name, *_ in rows:
            self.assertIn(name, ln)
        self.assertRegex(ln, r"features 3\b", ln)
        self.assertRegex(ln, r"attributes 2\b", ln)

    def test_a_long_contents_table_gets_counts_only(self):
        p = self.tmp / "big.gpkg"
        rows = make_gpkg(p, 40)
        ln = self.line_of(self.step1(p), "GeoPackage contents")
        self.assertIsNotNone(ln)
        nf = sum(1 for r in rows if r[1] == "features")
        na = sum(1 for r in rows if r[1] == "attributes")
        self.assertRegex(ln, rf"features {nf}\b")
        self.assertRegex(ln, rf"attributes {na}\b")
        self.assertNotIn("layer_020", ln)
        self.assertLess(len(ln), 600, ln)

    def test_plain_sqlite_has_no_contents_line(self):
        p = self.tmp / "plain.db"
        p.unlink(missing_ok=True)
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE t (a INTEGER)")
        con.execute("INSERT INTO t VALUES (1)")
        con.commit()
        con.close()
        self.assertIsNone(self.line_of(self.step1(p), "GeoPackage contents"))

    def test_sqlite_lists_every_table_with_its_rows_up_to_60(self):
        p = self.tmp / "many.db"
        p.unlink(missing_ok=True)
        con = sqlite3.connect(p)
        sizes = {}
        for k in range(45):
            name = f"tbl_{k:02d}_data"
            n = (k * 7) % 11 + 1
            sizes[name] = n
            con.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, v TEXT)")
            con.executemany(f"INSERT INTO {name} VALUES (?, ?)", [(i, f"v{i}") for i in range(1, n + 1)])
        con.commit()
        con.close()
        both = self.both(p)
        for name, n in sizes.items():
            self.assertRegex(both, rf"{name} {n}\b", f"{name} {n} missing from the 1k + 3k print")


if __name__ == "__main__":
    unittest.main()
