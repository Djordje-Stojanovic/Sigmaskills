"""SigmaDeepLook v2 fix round 2 (ticket 83 P0.14): information per token.

Ends-first recap, concise default with --detail, windowed reads and search caps, signature skeletons, column legend, frame picks with
a spread, folded stack traces, and the vision-tier token estimate. Everything is generated here; nothing is downloaded or executed.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "sigmadeeplook" / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))
import dl_core as core  # noqa: E402
import dl_logs  # noqa: E402
import dl_pick  # noqa: E402
import dl_skel  # noqa: E402
import dl_util  # noqa: E402
import dl_write as W  # noqa: E402
from test_v2 import big_csv, footer_of, run  # noqa: E402


class Recap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(prefix="sdl-r2-"))
        cls.f = d / "orders.csv"
        cls.f.write_bytes(big_csv(9000))
        cls.out = Path(tempfile.mkdtemp(prefix="sdl-r2o-"))
        cls.r1 = run([str(cls.f), "--out", str(cls.out), "--no-tools", "--fresh"])

    def test_every_print_ends_with_a_recap_line_before_the_footer(self):
        lines = self.r1.stdout.rstrip("\n").splitlines()
        self.assertTrue(lines[-1].startswith("-- chunks"), lines[-1])
        self.assertTrue(lines[-2].startswith("Recap: 1) "), lines[-2])
        self.assertRegex(lines[-2], r"2\) .* \| 3\) ")
        more = run([str(self.f), "--out", str(self.out), "--no-tools", "--more"])
        lines = more.stdout.rstrip("\n").splitlines()
        self.assertTrue(lines[-2].startswith("Recap: 1) "), lines[-2])

    def test_recap_restates_the_traps_first(self):
        recap = [l for l in self.r1.stdout.splitlines() if l.startswith("Recap:")][0]
        self.assertRegex(recap, r"DUPLICATE-KEYS|REPEATED-HEADER|MIXED|REJECT|OUTLIER")
        self.assertLessEqual(dl_util.est_tokens(recap), W.RECAP_RESERVE)

    def test_step_one_is_under_a_thousand_tokens_recap_and_footer_included(self):
        self.assertLessEqual(dl_util.est_tokens(self.r1.stdout), 1000)

    def test_ladder_is_a_hard_cap_per_step(self):
        out = Path(tempfile.mkdtemp(prefix="sdl-r2c-"))
        r = run([str(self.f), "--out", str(out), "--no-tools", "--fresh"])
        total = dl_util.est_tokens(r.stdout)
        r2 = run([str(self.f), "--out", str(out), "--no-tools", "--more"])
        total += dl_util.est_tokens(r2.stdout)
        self.assertLessEqual(total, 3000)
        self.assertGreater(total, 2200)

    def test_printed_figure_counts_the_recap(self):
        _, _, _, printed, _, _ = footer_of(self.r1.stdout)
        actual = dl_util.est_tokens(self.r1.stdout)
        self.assertLessEqual(abs(actual - printed) / printed, 0.10, (actual, printed))


class Concise(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(prefix="sdl-r2d-"))
        cls.f = d / "orders.csv"
        cls.f.write_bytes(big_csv(3000))
        cls.out = Path(tempfile.mkdtemp(prefix="sdl-r2do-"))
        cls.r1 = run([str(cls.f), "--out", str(cls.out), "--no-tools", "--fresh"])

    def test_default_has_no_ids_or_timings(self):
        self.assertNotRegex(self.r1.stdout.splitlines()[1], r"sha |\d+\.\ds")

    def test_detail_adds_sha_and_timing_on_a_cached_look(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--detail"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.splitlines()[1], r"\d+\.\ds · sha [0-9a-f]{12}")
        self.assertIn("Recap:", r.stdout)

    def test_hidden_chunks_keep_the_range_contiguous_and_cost_nothing(self):
        stream = [{"id": i, "sec": "read", "pri": 45, "tag": "file", "text": f"row {i}", "tok": 10} for i in range(6)]
        for c in stream[3:5]:
            c["only"] = "detail"
        stream[5]["only"] = "concise"
        got, nxt = W.window(stream, 0, 1000)
        self.assertEqual([c["id"] for c in got], [0, 1, 2, 5])
        self.assertEqual(nxt, 6)
        got, nxt = W.window(stream, 0, 1000, detail=True)
        self.assertEqual([c["id"] for c in got], [0, 1, 2, 3, 4])
        self.assertEqual(W.cost(stream), 40)
        self.assertEqual(W.cost(stream, True), 50)

    def test_read_next_keeps_six_file_rows_by_default(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-r2z-"))
        import zipfile
        z = d / "many.zip"
        with zipfile.ZipFile(z, "w") as zf:
            for k in range(12):
                zf.writestr(f"d{k}/f{k}.txt", "x" * 50)
        out = Path(tempfile.mkdtemp(prefix="sdl-r2zo-"))
        run([str(z), "--out", str(out), "--no-tools", "--fresh"])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        files = [c for c in lj["stream"] if c.get("tag") == "file"]
        shown = [c for c in files if c.get("only") != "detail"]
        self.assertLessEqual(len([c for c in shown if c.get("only") != "concise"]), W.READ_VISIBLE)


class Windows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(prefix="sdl-r2w-"))
        cls.f = d / "orders.csv"
        cls.f.write_bytes(big_csv(9000))
        cls.out = Path(tempfile.mkdtemp(prefix="sdl-r2wo-"))
        run([str(cls.f), "--out", str(cls.out), "--no-tools", "--fresh"])

    def test_grep_over_the_cap_gives_a_count_and_a_hint_not_the_list(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--grep", "name"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"\d{2,} hits for /name/")
        self.assertIn("too many to list", r.stdout)
        self.assertIn("Narrow the pattern", r.stdout)
        hit_lines = [l for l in r.stdout.splitlines() if re.match(r"\S+:\d+: ", l)]
        self.assertLessEqual(len(hit_lines), 5)

    def test_grep_under_the_cap_lists_every_hit(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--grep", "REJECT-ROW|rejects"])
        self.assertNotIn("too many to list", r.stdout)

    def test_grep_with_no_hit_says_nothing_relevant(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--grep", "zzzqqq-not-there"])
        self.assertIn("0 hits", r.stdout)
        self.assertIn("nothing relevant", r.stdout)

    def test_lines_window_is_capped_at_a_hundred_and_names_the_next(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--lines", "sample.md:1-500"])
        self.assertEqual(r.returncode, 0, r.stderr)
        m = re.search(r"sample\.md lines 1-(\d+) of (\d+)", r.stdout)
        self.assertTrue(m, r.stdout[:200])
        self.assertLessEqual(int(m.group(1)), 100)
        if int(m.group(2)) > 100:
            self.assertIn("window capped at 100 lines", r.stdout)
            self.assertIn("next: --lines sample.md:101-200", r.stdout)

    def test_lines_rejects_bad_specs(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--lines", "abc"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("--lines takes", r.stdout)


PY_SRC = '''"""module doc"""
import os


def top(a, b=2, *rest, key: int = 3) -> str:
    """Top level. Second sentence."""
    def inner():
        return 1
    return str(a)


class Thing(Base):
    """A thing."""

    def method(self, x):
        return x

    async def amethod(self):
        pass
''' + "\n".join(f"# filler {i}" for i in range(90))


class Skeleton(unittest.TestCase):
    def test_python_signatures_with_a_doc_line_and_no_nested_functions(self):
        rows = dl_skel.python_skeleton(PY_SRC)
        names = [r[2] for r in rows]
        self.assertIn("def top(a, b=2, *rest, key: int=3) -> str", names)
        self.assertIn("class Thing(Base)", names)
        self.assertIn("def method(self, x)", names)
        self.assertIn("async def amethod(self)", names)
        self.assertFalse(any("inner" in n for n in names), "a function nested in a function is body, not skeleton")
        self.assertEqual(next(r for r in rows if r[2].startswith("def top"))[3], "Top level. Second sentence.")
        depth = {r[2].split("(")[0]: r[1] for r in rows}
        self.assertEqual(depth["def method"], 1)

    def test_regex_skeleton_for_other_languages(self):
        js = "// make it\nexport async function foo(a, b) {\n  return 1\n}\nclass Foo extends Bar {\n  render(props) {\n    return 1;\n  }\n}\nfunc Add(a int) int {\n"
        rows, how = dl_skel.skeleton(js, ".js")
        self.assertEqual(how, "regex")
        text = [r[2] for r in rows]
        self.assertIn("export async function foo(a, b)", text)
        self.assertIn("class Foo extends Bar", text)
        self.assertIn("render(props)", text)
        self.assertEqual(rows[0][3], "make it")

    def test_a_big_source_file_gets_a_skeleton_instead_of_its_head(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-r2s-"))
        f = d / "mod.py"
        f.write_text(PY_SRC, encoding="utf-8")
        out = Path(tempfile.mkdtemp(prefix="sdl-r2so-"))
        r = run([str(f), "--out", str(out), "--no-direct", "--fresh"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("skeleton.md", r.stdout)
        self.assertIn("def top(a, b=2", r.stdout)
        self.assertFalse((out / "head.txt").exists())
        body = run([str(f), "--out", str(out), "--func", "top"])
        self.assertIn("return str(a)", body.stdout)


class Picks(unittest.TestCase):
    WORDS = [{"w": "money", "s": 700.0, "e": 700.4}, {"w": "capex", "s": 702.0, "e": 702.4}, {"w": "tco", "s": 770.0, "e": 770.3}]

    def test_no_query_means_evenly_spread(self):
        pts = dl_pick.relevance_points(self.WORDS, "", 0, 857)
        got = dl_pick.pick(pts, 9)
        gaps = [b - a for a, b in zip(got, got[1:])]
        self.assertEqual(len(got), 9)
        self.assertLess(max(gaps) / min(gaps), 1.5)

    def test_query_pulls_picks_toward_the_words_but_keeps_a_spread(self):
        pts = dl_pick.relevance_points(self.WORDS, "money capex tco", 0, 857, step=5)
        got = dl_pick.pick(pts, 9)
        near = [t for t in got if 690 <= t <= 780]
        self.assertGreaterEqual(len(near), 2, got)
        n_even = round(9 * dl_pick.FLOOR)
        far = [t for t in got if not 690 <= t <= 780]
        self.assertGreaterEqual(len(far), n_even, "at least the floor stays spread over the film")
        self.assertTrue(min(got) < 300 and max(got) > 600, got)
        self.assertEqual(got, dl_pick.pick(pts, 9), "deterministic")

    def test_picks_are_unique_sorted_and_in_range(self):
        pts = dl_pick.relevance_points(self.WORDS, "money", 100, 400, step=2)
        got = dl_pick.pick(pts, 9)
        self.assertEqual(got, sorted(set(got)))
        self.assertTrue(all(100 <= t <= 400 for t in got))

    def test_stop_words_and_empty_query(self):
        self.assertEqual(dl_pick.query_terms("What is the money of it?"), ["what", "money"])
        self.assertEqual(dl_pick.pick([], 5), [])


class Traces(unittest.TestCase):
    TRACE = ['Traceback (most recent call last):', '  File "/app/svc/pay.py", line 10, in charge', '    x()',
             '  File "/usr/lib/python3/site-packages/requests/api.py", line 5, in get', '    return r',
             '  File "/app/svc/db.py", line 3, in q', '  File "/app/svc/a.py", line 1, in a', '  File "/app/svc/b.py", line 2, in b',
             'Caused by: timeout']

    def test_fold_keeps_three_app_frames_and_counts_the_rest(self):
        s = dl_logs.fold_trace(self.TRACE)
        self.assertEqual(s.count("File "), 3)
        self.assertNotIn("site-packages", s)
        self.assertIn("Caused by: timeout", s)
        self.assertIn("more frame(s), 1 of them library code", s)

    def test_log_errors_md_holds_the_folded_trace_once(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-r2l-"))
        f = d / "app.log"
        lines = []
        for i in range(120):
            lines.append(f"2026-10-16 05:{i % 60:02d}:{i % 60:02d} INFO [api] GET /v1/orders status=200 ms={i}")
            if i % 40 == 5:
                lines.append(f"2026-10-16 05:{i % 60:02d}:{i % 60:02d} ERROR [api] charge failed")
                lines += self.TRACE
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = Path(tempfile.mkdtemp(prefix="sdl-r2lo-"))
        r = run([str(f), "--out", str(out), "--no-direct", "--fresh"])
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (out / "errors.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("pay.py"), 1, "one error template, one folded trace")
        self.assertNotIn("site-packages", text)


class Vision(unittest.TestCase):
    def test_standard_tier_caps_a_sheet_at_about_1_6k(self):
        # the cap prices what the model charges; the sheet itself is not shrunk
        self.assertLessEqual(core.tokens_for_image(2000, 1359), 1568)
        self.assertEqual(core.tokens_for_image(2000, 1500), 1568)
        self.assertEqual(core.tokens_for_image(1568, 1066), 56 * 39 if 56 * 39 <= 1568 else 1568)

    def test_small_images_cost_by_the_28_pixel_grid(self):
        self.assertEqual(core.tokens_for_image(280, 280), 100)
        self.assertEqual(core.tokens_for_image(281, 28), 11)

    def test_high_resolution_tier_is_not_resized_and_capped_at_4784(self):
        self.assertEqual(core.tokens_for_image(2000, 1500, edge=2576, cap=4784), 72 * 54)
        self.assertEqual(core.tokens_for_image(4000, 3000, edge=2576, cap=4784), 4784)

    def test_every_picture_is_priced_for_both_tiers_and_sheets_keep_full_detail(self):
        both = core.image_tokens(2000, 1359)
        self.assertEqual(both["standard"], 1568)
        self.assertEqual(both["high"], 72 * 49)
        r = core.READERS["claude"]
        self.assertEqual((r["width"], r["edge"], r["tier"]), (2000, 2000, "standard"))
        h = core.READERS["claude-hires"]
        self.assertEqual((h["width"], h["tier"]), (2576, "high"))

    def test_read_next_row_names_both_tier_costs(self):
        import dl_write
        look = type("L", (), {"out": Path("/x")})()
        row = dl_write._row_text({"path": "/x/sheet.jpg", "kind": "image", "what": "sheet", "px": "2000x1359", "tokens_est": 1568,
                                  "tokens_std": 1568, "tokens_high": 3528}, look)
        self.assertIn("~1.6k tokens, 3.5k high-res", row)


class Legend(unittest.TestCase):
    def test_csv_columns_come_as_one_legend_and_compact_rows(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-r2g-"))
        f = d / "orders.csv"
        f.write_bytes(big_csv(3000))
        out = Path(tempfile.mkdtemp(prefix="sdl-r2go-"))
        r = run([str(f), "--out", str(out), "--no-tools", "--fresh"])
        self.assertIn("Columns (name: type, null and empty counts, distinct values", r.stdout)
        self.assertRegex(r.stdout, r"(?m)^id: int, ")
        self.assertNotRegex(r.stdout, r"(?m)^- id: ")


if __name__ == "__main__":
    unittest.main()
