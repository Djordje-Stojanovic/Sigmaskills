"""SigmaDeepLook fix round 4 (ticket 83 P0.14b.H7): generalisation.

Property tests per family on files synthesised here (r4_fixtures.py), each count checked against ground truth worked out by the
fixture builder, not by the tool. No file of the dev set or of any held-out set is used. The checks are on look.json (facts and the
whole stored stream), so they hold whatever the step-1 budget is.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "sigmadeeplook" / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))
import dl_prof as P  # noqa: E402
import dl_util  # noqa: E402
import dl_write as W  # noqa: E402
import r4_fixtures as F  # noqa: E402
from test_v2 import run  # noqa: E402

FX = HERE / "fixtures"


def look_at(path, *extra, tools=False):
    out = tempfile.mkdtemp(prefix="sdl-r4o-")
    r = run([str(path), "--out", out, "--fresh", *([] if tools else ["--no-tools"]), *extra])
    lj = json.loads((Path(out) / "look.json").read_text(encoding="utf-8"))
    return r, lj, "\n".join(c["text"] for c in lj["stream"]), Path(out)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="sdl-r4-"))

    def has(self, text, *needles):
        for n in needles:
            self.assertIn(n, text)


class NeverBareRead(Base):
    def test_small_text_families_get_counts_and_a_stored_stream_that_more_continues(self):
        for build in (F.small_json, F.yaml_file, F.toml_file, F.markdown_file, F.srt_file):
            p, _ = build(self.d)
            r, lj, text, out = look_at(p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(lj["facts"].get("direct_read"), p.name)
            self.assertTrue(lj["facts"].get("counts"), p.name)
            self.assertNotIn("Read this file directly", r.stdout)
            more = run([str(p), "--out", str(out), "--no-tools", "--more"])
            self.assertEqual(more.returncode, 0, more.stderr)
            self.assertTrue(more.stdout.strip(), p.name)

    def test_the_file_itself_ends_the_stream_once(self):
        p, _ = F.markdown_file(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(len(re.findall(r"^Some words here\. Some words here\. Some words here\. $", text, re.M)), 1)   # the file itself once, no head copy
        self.assertTrue(lj["stream"][-1]["text"].rstrip().endswith("The end is here."))


class Csv(Base):
    def test_every_count_matches_the_ground_truth(self):
        p, t = F.csv_file(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        self.assertEqual(c["data rows"], t["rows"])
        self.assertEqual(c["empty or null cells"], t["empty_qty"])
        self.assertEqual(c["complete rows (no empty cell)"], t["rows"] - t["empty_qty"])
        self.has(text, f"sum {P.fmt(t['sum_units'])}", f"max {P.fmt(t['max_units'])} (line {t['max_line']})", f"sku: text, {t['distinct_sku']} distinct")
        group = [l for l in text.splitlines() if l.startswith("Group by region")][0]
        for reg, n in t["per_region"].items():
            self.assertIn(f"{reg}: {P.fmt(n)},", group)
        self.has(text, f"qty: int, {t['empty_qty']} empty")


class Jsonl(Base):
    def test_fields_profiled_with_line_positions(self):
        p, t = F.jsonl_file(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(lj["facts"]["counts"]["records"], t["records"])
        self.has(text, f"sum {P.fmt(t['sum_ms'])}", f"max {t['max_ms']} (line", f"user: text, {t['users']} distinct", f"false ({t['false_ok']})")
        self.assertNotIn("INVALID-JSON", [f["kind"] for f in lj["flags"]])


class Json(Base):
    def test_records_inside_a_document_are_profiled(self):
        p, t = F.small_json(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(lj["facts"]["counts"]["array items"], t["servers"])
        self.has(text, f"sum {P.fmt(t['sum_port'])}", f"sum {t['sum_weight']}", "Records at servers")
        self.assertFalse([f for f in lj["flags"] if "JSON" in f["kind"]])


class Yaml(Base):
    def test_bare_tier_still_sums_key_numbers(self):
        p, t = F.yaml_file(self.d)
        _, lj, text, _ = look_at(p)
        self.has(text, f"replicas: 6x, min 1 (line 4), max 6 (line 24), sum {t['sum_replicas']}")

    @unittest.skipUnless(__import__("importlib").util.find_spec("yaml"), "PyYAML not installed")
    def test_with_pyyaml_the_map_of_services_is_a_record_set(self):
        p, t = F.yaml_file(self.d)
        _, lj, text, _ = look_at(p, tools=True)
        self.has(text, f"Records at services ({t['services']} items", f"sum {t['sum_replicas']}")


class Toml(Base):
    def test_toml_is_parsed_not_flagged_as_json(self):
        p, t = F.toml_file(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(lj["subtype"], "toml")
        self.has(text, f"Keys of dependencies ({t['deps']})", "dependencies.tokio = 1.37", "in 1 of 3 indexes")
        self.assertFalse([f for f in lj["flags"] if "JSON" in f["kind"]])


class Markdown(Base):
    def test_heading_counts_and_last_section(self):
        p, t = F.markdown_file(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        self.assertEqual((c["level-1 headings"], c["level-2 headings"], c["level-3 headings"]), (t["h1"], t["h2"], t["h3"]))
        self.assertTrue(str(c["task boxes"]).startswith(str(t["tasks"])))
        self.assertIn(f"last '{t['last']}'", lj["headline"] if "headline" in lj else text)


class Logs(Base):
    def test_level_counts_and_key_numbers(self):
        p, t = F.log_file(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        for lv, n in t["levels"].items():
            self.assertEqual(c[f"{lv} lines"], n, lv)
        self.has(text, f"latency_ms: {P.fmt(t['lat_n'])}x", f"max {P.fmt(t['lat_max'])} (line", f"sum {P.fmt(t['lat_sum'])}")

    def test_key_numbers_keep_true_line_numbers_and_split_adjacent_keys(self):
        lines = []
        for i in range(60):
            lines.append(f"2026-10-01 10:{i:02d}:00 {'ERROR' if i % 6 == 0 else 'INFO'} [api] GET /x status={500 if i % 6 == 0 else 200} ms={i * 3} req={i}")
            if i % 10 == 9:
                lines.append("")
        p = self.d / "api.log"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _, lj, text, _ = look_at(p)
        top = max(range(60), key=lambda i: i * 3)
        true_line = [n for n, l in enumerate(lines, 1) if l.endswith(f"req={top}")][0]
        self.has(text, f"ms: 60x, min 0 (line 1), max {top * 3} (line {true_line})", "status: 60x")
        per = [l for l in text.splitlines() if l.startswith("  ms: ") and "ERROR 10x" in l]
        self.assertTrue(per, "per-level line for ms")
        self.assertNotIn("status (ms)", text)

    def test_access_log_status_codes(self):
        p, t = F.access_log(self.d)
        _, lj, text, _ = look_at(p)
        line = [l for l in text.splitlines() if l.startswith("Access-log lines:")][0]
        for s, n in t["status"].items():
            self.assertIn(f"{s} {n}", line)


class Subtitles(Base):
    def test_cue_ranking_and_exact_stamps(self):
        p, t = F.srt_file(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(lj["facts"]["counts"]["cues"], t["cues"])
        rank = [l for l in text.splitlines() if l.startswith("Cues ranked by duration")][0]
        self.assertRegex(rank, rf": #{t['longest']} ")
        self.assertTrue(rank.rstrip().split("; ")[-1].startswith(f"#{t['shortest']} "))
        self.assertIn(f"last cue end 0:00:{t['last_end']:06.3f}", text)


class Office(Base):
    def test_docx_paragraphs_tables_props_and_revisions(self):
        p, t = F.docx_file(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        self.assertEqual(c["paragraphs (every w:p in the body)"], t["paragraphs"])
        self.assertEqual(c["empty paragraphs"], t["empty"])
        self.assertEqual(c["top-level body paragraphs"], t["body_paragraphs"])
        self.assertEqual((c["tables"], c["table cells"]), (t["tables"], t["cells"]))
        self.has(text, f"creator {t['author']}", f"{t['ins'] + t['dels']} tracked changes")

    def test_xlsx_sheets_hidden_aggregates_and_formulas(self):
        p, t = F.xlsx_file(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        self.assertEqual((c["sheets in workbook.xml"], c["hidden"], c["formulas"]), (t["sheets"], t["hidden"], t["formulas"]))
        self.has(text, f"numbers sum {t['sum']}, min {t['min']} at B7, max {t['max']} at B8", f"creator {t['author']}", "=SUM(Data!B2:B9)")

    def test_pptx_counts_and_slide_list_agree(self):
        p, t = F.pptx_file(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        self.assertEqual((c["slides"], c["hidden slides"], c["shapes"]), (t["slides"], t["hidden"], t["shapes"]))
        self.assertIn(f"Slides, {t['slides']} in all", text)


class Archives(Base):
    def test_jar_manifest_and_tree(self):
        p, t = F.jar_file(self.d)
        _, lj, text, _ = look_at(p)
        self.has(text, f"Implementation-Title: {t['title']}", f"version: {t['version']}", f".class {t['classes']} files", f"Biggest files (bytes): {t['biggest']}")

    def test_zip_project_manifest_inner_table_tests_and_env(self):
        p, t = F.zip_project(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        self.assertEqual((c["test functions"], c["environment variables"]), (t["tests"], len(t["env"])))
        self.has(text, f"name: {t['name']}", "react ^19.0.0", f"{t['rows']} data rows", f"sum {P.fmt(t['sum'])}", ", ".join(t["env"]),
                 f"Longest files (lines): {t['longest']}")

    def test_repo_directory(self):
        root, t = F.repo_dir(self.d)
        _, lj, text, _ = look_at(root)
        c = lj["facts"]["counts"]
        self.assertEqual((c["files"], c["test functions"]), (t["files"], t["tests"]))
        self.has(text, f"name: {t['name']}", f"Longest files (lines): {t['longest']}")
        self.assertTrue(lj["headline"].startswith("Code repository") if "headline" in lj else True)

    def test_single_gzip_member_is_profiled(self):
        p, t = F.gz_csv(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(lj["facts"]["counts"]["unpacked bytes"], t["unpacked"])
        self.has(text, f"{t['rows']} data rows", f"sum {P.fmt(t['sum_sq'])}")

    def test_tar_gz_tree(self):
        p, t = F.tar_gz(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(lj["facts"]["counts"]["files"], t["files"])
        self.has(text, f"Biggest files (bytes): {t['biggest']}", "Member dates:")


class Tables(Base):
    def test_sqlite_every_table_profiled_exactly(self):
        p, t = F.sqlite_db(self.d)
        _, lj, text, _ = look_at(p)
        self.assertEqual(lj["facts"]["counts"]["rows in all tables"], t["rows_all"])
        self.has(text, f"Table orders (rows numbered from 1, every row read): {P.fmt(t['orders'])} records", f"sum {P.fmt(t['sum_amount'])}",
                 f"max {t['max_amount']} (row")
        vals = [l for l in text.splitlines() if l.startswith("Table orders: Values of status")][0]
        for k, n in t["status"].items():
            self.assertIn(f"{k} {P.fmt(n)}", vals)

    @unittest.skipUnless(__import__("importlib").util.find_spec("pyarrow"), "pyarrow not installed")
    def test_parquet_rows_profiled_exactly(self):
        p, t = F.parquet_file(self.d)
        _, lj, text, _ = look_at(p, tools=True)
        self.assertEqual(lj["facts"]["counts"]["rows"], t["rows"])
        self.has(text, f"sum {P.fmt(t['sum'])}", f"red ({P.fmt(t['red'])})")


class Svg(Base):
    def test_elements_subpaths_colours_extremes(self):
        p, t = F.svg_file(self.d)
        _, lj, text, _ = look_at(p)
        c = lj["facts"]["counts"]
        self.assertEqual((c["elements"], c["paths"], c["subpaths (M/m commands)"]), (t["elements"], t["paths"], t["subpaths"]))
        self.has(text, f"x {t['x_min']} .. {t['x_max']}, y {t['y_min']} .. {t['y_max']}", f"#ff0000 {t['fill_red']}")

    def test_path_points_against_hand_worked_values(self):
        import dl_svg
        sub, cmds, pts = dl_svg.path_points("M10 10 l5 0 0 5 z m2 2 h3 V 40")
        self.assertEqual(sub, 2)
        self.assertEqual(pts, [(10, 10), (15, 10), (15, 15), (12, 12), (15, 12), (15, 40)])


class Pieces(unittest.TestCase):
    def test_long_facts_split_so_a_ladder_step_fills_its_budget(self):
        text = "Values: " + "; ".join(f"item{i} = {i * 7}" for i in range(600))
        parts = W.pieces(text)
        self.assertGreater(len(parts), 3)
        self.assertTrue(all(dl_util.est_tokens(x) <= W.PIECE_TOKENS + 40 for x in parts))
        joined = " ".join(parts)
        for i in (0, 299, 599):
            self.assertIn(f"item{i} = {i * 7}", joined)


@unittest.skipUnless(shutil.which("ffprobe"), "ffprobe not installed")
class Media(unittest.TestCase):
    def test_frames_duration_and_rate_match_ffprobe(self):
        r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames,r_frame_rate",
                            "-of", "json", str(FX / "clip.mp4")], capture_output=True, text=True)
        s = json.loads(r.stdout)["streams"][0]
        _, lj, text, _ = look_at(FX / "clip.mp4", "--quick", tools=True)
        c = lj["facts"]["counts"]
        self.assertEqual(c["video frames"], int(s["nb_read_frames"]))
        self.assertTrue(c["frame rate"].startswith(s["r_frame_rate"]))
        self.assertTrue(c["duration"].startswith("12.000 s"))


if __name__ == "__main__":
    unittest.main()
