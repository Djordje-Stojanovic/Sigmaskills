"""SigmaDeepLook v2 tests: the gate, the ranked stream and its cursor, drill-down flags, and the 'tool missing' paths.

Standard library only. Fixtures are generated into temp folders; the real-size checks use the owner's read-only copies in
.scratch/deeplook/real (set SIGMADEEPLOOK_REAL to point elsewhere) and are skipped when those files are not on the machine.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "sigmadeeplook" / "scripts"
LOOK = SCRIPTS / "look.py"
FX = HERE / "fixtures"
REAL = Path(os.environ.get("SIGMADEEPLOOK_REAL") or r"C:\AI\Design_Experiments\.scratch\deeplook\real")
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
import dl_util  # noqa: E402

FOOTER = re.compile(r"^-- chunks (\d+)-(\d+) of (\d+) \| printed ~([\d.]+k?) \| next: (.*?) \| remaining ~([\d.]+k?)\s*$", re.M)


def run(args, env=None, cwd=None):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    e.update(env or {})
    return subprocess.run([sys.executable, str(LOOK), *args], capture_output=True, text=True, encoding="utf-8", env=e, timeout=600, cwd=cwd)


def kilo(s):
    return float(s[:-1]) * 1000 if s.endswith("k") else float(s)


def footer_of(text):
    m = FOOTER.findall(text)
    assert m, text[-300:]
    a, b, n, printed, nxt, rem = m[-1]
    return int(a), int(b), int(n), kilo(printed), nxt, kilo(rem)


def big_csv(rows=9000):
    extra = ",".join(f"c{k}" for k in range(1, 21))
    lines = [f"id,name,amount,status,day,{extra}"]
    for i in range(1, rows + 1):
        vals = ",".join(str((i * k) % (7 + k)) for k in range(1, 21))
        row = f"{i if i != 77 else 76},name{i},{10 + i % 90}.5,{'shipped' if i % 5 else 'Shipped'},2026-01-{1 + i % 28:02d},{vals}"
        if i % 75 == 0:
            row = row.rsplit(",", 3)[0]     # a short row: a reject
        lines.append(row)
    return ("\n".join(lines) + "\n").encode()


class Gate(unittest.TestCase):
    def gate(self, path, *extra):
        r = run(["gate", str(path), *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_small_text_is_read(self):
        for name in ("tool.py", "plain.txt", "events.jsonl", "nb.ipynb", "cal.ics"):
            out = self.gate(FX / name)
            self.assertRegex(out, r"^READ .+ \(~\d+ tokens\)$", name)

    def test_binary_and_media_are_looked_at(self):
        for name in ("clip.mp4", "speech.wav", "chart.png", "mixed.pdf", "hello.exe", "app.sqlite", "t.parquet", "ok.tar.gz", "Tiny.ttf", "cube.glb"):
            out = self.gate(FX / name)
            self.assertRegex(out, r"^LOOK (quick|standard|deep) ", name)

    def test_big_text_is_looked_at_and_budget_moves_the_line(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-g-"))
        f = d / "big.csv"
        f.write_bytes(big_csv(9000))
        self.assertRegex(self.gate(f), r"^LOOK ", "over 25k tokens")
        small = d / "small.csv"
        small.write_bytes(big_csv(300))
        self.assertRegex(self.gate(small), r"^READ ")
        self.assertRegex(self.gate(small, "--budget", "100"), r"^LOOK ", "a small budget turns READ into LOOK")

    def test_gate_is_one_short_line(self):
        out = self.gate(FX / "clip.mp4")
        self.assertEqual(len(out.splitlines()), 1)
        self.assertLess(dl_util.est_tokens(out), 60)

    def test_missing_file(self):
        r = run(["gate", str(FX / "nope.bin")])
        self.assertEqual(r.returncode, 1)


class DirectWritesNothing(unittest.TestCase):
    def test_small_text_prints_one_line_and_writes_no_cache(self):
        cache = tempfile.mkdtemp(prefix="sdl-cache-")
        env = {"LOCALAPPDATA": cache, "XDG_CACHE_HOME": cache, "HOME": cache}
        r = run([str(FX / "plain.txt"), "--no-tools"], env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.splitlines()[0], r"^Read this file directly: .+ \(~\d+ tokens\)$")
        self.assertEqual(list(Path(cache).rglob("*")), [], "nothing is written for a direct read")

    def test_force_analyses_small_text(self):
        r = run([str(FX / "plain.txt"), "--no-tools", "--force", "--out", tempfile.mkdtemp(prefix="sdl-f-")])
        self.assertTrue(r.stdout.startswith("# plain.txt"), r.stdout[:80])


class Stream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(prefix="sdl-s-"))
        cls.f = d / "orders.csv"
        cls.f.write_bytes(big_csv(9000))
        cls.out = Path(tempfile.mkdtemp(prefix="sdl-so-"))
        cls.r1 = run([str(cls.f), "--out", str(cls.out), "--no-tools", "--fresh"])

    def test_step_one_is_about_a_thousand_tokens_and_ends_with_the_footer(self):
        self.assertEqual(self.r1.returncode, 0, self.r1.stderr)
        n = dl_util.est_tokens(self.r1.stdout)
        self.assertLessEqual(n, 1150)
        a, b, total, printed, nxt, rem = footer_of(self.r1.stdout)
        self.assertEqual(a, 0)
        self.assertGreater(total, b)
        self.assertIn("--more", nxt)

    def test_no_ask_the_human_and_no_full_sha(self):
        self.assertNotIn("Ask the human", self.r1.stdout)
        self.assertNotRegex(self.r1.stdout, r"[0-9a-f]{64}")

    def test_cursor_continuity_no_gap_no_overlap(self):
        out = Path(tempfile.mkdtemp(prefix="sdl-sc-"))
        r = run([str(self.f), "--out", str(out), "--no-tools", "--fresh"])
        a, b, total, _, _, _ = footer_of(r.stdout)
        seen = list(range(a, b + 1))
        guard = 0
        while b + 1 < total and guard < 80:
            guard += 1
            r = run([str(self.f), "--out", str(out), "--no-tools", "--more", "400"])
            self.assertEqual(r.returncode, 0, r.stderr)
            a, b, total, _, _, _ = footer_of(r.stdout)
            self.assertEqual(a, seen[-1] + 1, "the next window starts where the last one ended")
            seen += list(range(a, b + 1))
        self.assertEqual(seen, list(range(total)), "every chunk exactly once")
        end = run([str(self.f), "--out", str(out), "--no-tools", "--more"])
        self.assertIn("nothing more", end.stdout.lower())

    def test_printed_cost_matches_actual_within_ten_percent(self):
        out = Path(tempfile.mkdtemp(prefix="sdl-sk-"))
        r = run([str(self.f), "--out", str(out), "--no-tools", "--fresh"])
        checks = [r.stdout]
        for n in ("800", "1500", "3000"):
            checks.append(run([str(self.f), "--out", str(out), "--no-tools", "--more", n]).stdout)
        for text in checks:
            if "-- chunks" not in text:
                continue
            _, _, _, printed, _, _ = footer_of(text)
            actual = dl_util.est_tokens(text)
            if printed < 300:
                continue
            self.assertLessEqual(abs(actual - printed) / printed, 0.10, (actual, printed))

    def test_default_ladder_reaches_three_k_then_ten_k(self):
        out = Path(tempfile.mkdtemp(prefix="sdl-sl-"))
        r = run([str(self.f), "--out", str(out), "--no-tools", "--fresh"])
        _, _, _, p1, nxt, _ = footer_of(r.stdout)
        r2 = run([str(self.f), "--out", str(out), "--no-tools", "--more"])
        _, _, _, p2, _, _ = footer_of(r2.stdout)
        self.assertGreater(p2, 1000)
        self.assertLessEqual(p1 + p2, 3400)
        self.assertGreater(p1 + p2, 2200)

    def test_from_rereads_and_remaining_moves_nothing(self):
        out = Path(tempfile.mkdtemp(prefix="sdl-sf-"))
        run([str(self.f), "--out", str(out), "--no-tools", "--fresh"])
        c0 = json.loads((out / "cursor.json").read_text())["pos"]
        r = run([str(self.f), "--out", str(out), "--no-tools", "--from", "0", "--more", "300"])
        a, b, _, _, _, _ = footer_of(r.stdout)
        self.assertEqual(a, 0)
        rem = run([str(self.f), "--out", str(out), "--no-tools", "--remaining"])
        self.assertRegex(rem.stdout, r"remaining ~[\d.]+k? tokens in \d+ chunks")
        self.assertEqual(json.loads((out / "cursor.json").read_text())["pos"], max(c0, b + 1) if b + 1 > c0 else c0)

    def test_stream_in_look_json_is_ranked_with_costs(self):
        lj = json.loads((self.out / "look.json").read_text(encoding="utf-8"))
        st = lj["stream"]
        self.assertEqual(st[0]["sec"], "head")
        pris = [c["pri"] for c in st[1:]]
        self.assertEqual(pris, sorted(pris, reverse=True), "most valuable first")
        self.assertTrue(all(c["tok"] > 0 for c in st))
        self.assertEqual([c["id"] for c in st], list(range(len(st))))


class Drill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp(prefix="sdl-d-"))
        cls.f = d / "orders.csv"
        cls.f.write_bytes(big_csv(9000))
        cls.out = Path(tempfile.mkdtemp(prefix="sdl-do-"))
        run([str(cls.f), "--out", str(cls.out), "--no-tools", "--fresh"])

    def test_grep_finds_lines_with_numbers_and_prints_cost(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--grep", "name8999"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"hit\(s\)")
        self.assertRegex(r.stdout.strip().splitlines()[-1], r"^-- ~\d+ tokens$")

    def test_grep_caps_at_fifty_hits(self):
        r = run([str(self.f), "--out", str(self.out), "--no-tools", "--grep", "name"])
        hits = [x for x in r.stdout.splitlines() if re.match(r"^\S+:\d+: ", x)]
        self.assertLessEqual(len(hits), 50)

    def test_sql_is_read_only(self):
        for bad in ("DROP TABLE t", "SELECT 1; DELETE FROM t", "COPY t TO 'x.csv'", "SELECT * FROM read_csv('x.csv')", "ATTACH 'x.db'", "PRAGMA table_info(t)"):
            r = run([str(self.f), "--out", str(self.out), "--no-tools", "--sql", bad])
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn("--sql", r.stdout, bad)

    def test_drill_not_available_says_so(self):
        r = run([str(FX / "clip.mp4"), "--out", tempfile.mkdtemp(prefix="sdl-n-"), "--no-tools", "--func", "main"])
        self.assertNotEqual(r.returncode, 0)


class Regressions(unittest.TestCase):
    """Found by the independent QA run (ticket 83 P0.14)."""

    def test_pdf_subset_font_name_is_not_an_auto_action(self):
        sys.path.insert(0, str(HERE))
        import make_fixtures as mf
        objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
                4: mf.stream(b"", b"BT /F1 12 Tf 20 100 Td (Hello) Tj ET"), 5: b"<< /Type /Font /Subtype /Type1 /BaseFont /AAAAAA+Helvetica >>"}
        d = Path(tempfile.mkdtemp(prefix="sdl-aa-"))
        (d / "subset.pdf").write_bytes(mf.build_pdf(objs))
        r = run([str(d / "subset.pdf"), "--out", str(d / "out"), "--fresh"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("AUTO-ACTION", r.stdout)

    def test_headline_keeps_the_rest_of_the_first_line(self):
        import sqlite3
        d = Path(tempfile.mkdtemp(prefix="sdl-hl-"))
        c = sqlite3.connect(str(d / "a.sqlite"))
        c.execute("create table people(id int, name text)")
        c.executemany("insert into people values (?,?)", [(i, "x") for i in range(5)])
        c.commit()
        c.close()
        r = run([str(d / "a.sqlite"), "--out", str(d / "out"), "--fresh"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("people 5", r.stdout)   # rows per table, biggest first


if __name__ == "__main__":
    unittest.main()
