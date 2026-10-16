"""Offline tests for sigmadeeplook. Standard library only; they run on the committed fixtures.

The bare tier (--no-tools) is what CI proves on every OS. The full tier needs ffmpeg, LibreOffice and
friends, so it is run by hand: `python sigmadeeplook/scripts/look.py selftest --tier full`.
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
LOOK = ROOT / "sigmadeeplook" / "scripts" / "look.py"
FX = HERE / "fixtures"
SECTIONS = ["Identity", "Summary", "Read next", "Flags", "Not looked at", "Ask the human"]


def run(args, **kw):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(LOOK), *args], capture_output=True, text=True, encoding="utf-8", env=env, timeout=300, **kw)


def look(name, *extra):
    out = tempfile.mkdtemp(prefix="sdl-test-")
    r = run([str(FX / name), "--out", out, "--fresh", "--no-tools", *extra])
    return r, Path(out)


class Fixtures(unittest.TestCase):
    def test_fixtures_exist(self):
        truth = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
        names = [n for n in truth if not n.startswith("_")]
        self.assertGreaterEqual(len(names), 40)
        for n in names:
            self.assertTrue((FX / n).exists(), n)


class Contract(unittest.TestCase):
    def test_sections_in_order_and_files_written(self):
        r, out = look("tool.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        heads = re.findall(r"^## (.+?)\s*$", re.sub(r"```.*?```", "", r.stdout, flags=re.S), re.M)
        self.assertEqual(heads, SECTIONS)
        self.assertEqual((out / "LOOK.md").read_text(encoding="utf-8").strip(), r.stdout.strip())
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        self.assertEqual(lj["schema"], 1)
        self.assertEqual(lj["type"], "code")
        self.assertTrue((out / "view.html").exists())

    def test_same_file_same_folder(self):
        a = run([str(FX / "plain.txt"), "--json", "--no-tools", "--fresh"])
        b = run([str(FX / "plain.txt"), "--json", "--no-tools"])
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(json.loads(a.stdout)["sha256"], json.loads(b.stdout)["sha256"])


class Refusals(unittest.TestCase):
    def test_unsafe_archives_exit_2_and_write_nothing(self):
        for name in ("slip.zip", "ratio.zip", "nested.zip", "links.tar"):
            r, out = look(name, "--extract")
            self.assertEqual(r.returncode, 2, name)
            self.assertIn("REFUSED", r.stdout, name)
            self.assertFalse((out / "extract").exists(), name)

    def test_unknown_and_empty_exit_3(self):
        for name in ("empty.bin", "noise.bin"):
            r, _ = look(name)
            self.assertEqual(r.returncode, 3, name)
            self.assertIn("## Identity", r.stdout)

    def test_url_needs_the_network_flag(self):
        r = run(["https://example.invalid/page.html", "--no-tools"])
        self.assertEqual(r.returncode, 2)

    def test_canary_never_runs(self):
        r, out = look("repo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(list((FX / "repo").rglob("CANARY*")))
        self.assertFalse(list(out.rglob("CANARY*")))
        self.assertIn("HOOK-OR-MCP", r.stdout)


class Privacy(unittest.TestCase):
    def test_gps_stays_out_of_look_md(self):
        r, out = look("photo.jpg")
        self.assertNotRegex(r.stdout, r"48\.0|16\.0|22\.0")


class Selftest(unittest.TestCase):
    def test_bare_tier_all_ten_checks(self):
        r = run(["selftest", "--tier", "bare"])
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr)
        self.assertIn("RESULT bare: PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
