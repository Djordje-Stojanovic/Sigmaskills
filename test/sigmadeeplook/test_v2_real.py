"""SigmaDeepLook v2 on the owner's real files (read-only copies in .scratch/deeplook/real; set SIGMADEEPLOOK_REAL to point elsewhere).

Skipped file by file when a copy is not on the machine. Checks per file: step 1 stays within the budget, the known traps are in the
first print, the whole stream can be walked with --more with no overlap and no gap, and every printed cost matches the real size
within 10 %.
"""
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
REAL = Path(os.environ.get("SIGMADEEPLOOK_REAL") or r"C:\AI\Design_Experiments\.scratch\deeplook\real")
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
import dl_util  # noqa: E402

FOOTER = re.compile(r"^-- chunks (\d+)-(\d+) of (\d+) \| printed ~([\d.]+k?) \| next: (.*?) \| remaining ~([\d.]+k?)\s*$", re.M)
STEP1_MAX = 1150

TRAPS = {
    "orders-export-2026.csv": ["REPEATED-HEADER", "DUPLICATE-KEYS", "MIXED-TYPES", "OUTLIER", "REJECT-ROW"],
    "shell32.dll": ["TIMESTAMP-UNRELIABLE"],
    "curl.exe": [],
    "long-document.pdf": ["AUTO-ACTION"],
    "mailbox-5200.mbox": ["AUTH-FAIL", "LINK-MISMATCH"],
}
MUST_SAY = {
    "shell32.dll": ["Authenticode", "Install: pip install lief"],
    "curl.exe": ["Authenticode", "PDB path"],
    "long-document.pdf": ["339 pages"],
    "orders-export-2026.csv": ["620000"],
    "mailbox-5200.mbox": ["5200 messages"],
}


def run(args):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(LOOK), *args], capture_output=True, text=True, encoding="utf-8", env=e, timeout=900)


def kilo(s):
    return float(s[:-1]) * 1000 if s.endswith("k") else float(s)


def parse_footer(text):
    m = FOOTER.findall(text)
    assert m, text[-300:]
    a, b, n, printed, nxt, rem = m[-1]
    return int(a), int(b), int(n), kilo(printed), nxt, kilo(rem)


class RealFiles(unittest.TestCase):
    pass


def make_test(name):
    path = REAL / name

    @unittest.skipUnless(path.exists(), f"{name} copy not on this machine")
    def test(self):
        out = tempfile.mkdtemp(prefix="sdl-real-")
        r = run([str(path), "--out", out, "--fresh"])
        self.assertEqual(r.returncode, 0, r.stderr)
        first = r.stdout
        self.assertLessEqual(dl_util.est_tokens(first), STEP1_MAX, "step 1 stays within the budget")
        for kind in TRAPS.get(name, []):
            self.assertIn(kind, first, f"{kind} must be in the first print of {name}")
        for phrase in MUST_SAY.get(name, []):
            self.assertIn(phrase, first)
        a, b, n, printed, _, _ = parse_footer(first)
        self.assertEqual(a, 0)
        seen = list(range(a, b + 1))
        total_actual = dl_util.est_tokens(first)
        self.assertLessEqual(abs(total_actual - printed) / printed, 0.10, ("step 1", total_actual, printed))
        guard = 0
        while b + 1 < n and guard < 120:
            guard += 1
            r = run([str(path), "--out", out, "--more"])
            self.assertEqual(r.returncode, 0, r.stderr)
            a, b, n, printed, _, _ = parse_footer(r.stdout)
            self.assertEqual(a, seen[-1] + 1, "the next window starts where the last one ended (no gap, no overlap)")
            seen += list(range(a, b + 1))
            actual = dl_util.est_tokens(r.stdout)
            if printed >= 300:
                self.assertLessEqual(abs(actual - printed) / printed, 0.10, (guard, actual, printed))
        self.assertEqual(seen, list(range(n)))
        end = run([str(path), "--out", out, "--more"])
        self.assertIn("nothing more", end.stdout.lower())
    return test


for _name in TRAPS:
    setattr(RealFiles, "test_" + re.sub(r"\W", "_", _name), make_test(_name))


class RealDirectFiles(unittest.TestCase):
    @unittest.skipUnless((REAL / "DESIGN.md").exists(), "copy not on this machine")
    def test_small_text_is_read_directly_and_nothing_is_written(self):
        for name in ("DESIGN.md", "package-check.json", "timing_par.csv"):
            if not (REAL / name).exists():
                continue
            g = run(["gate", str(REAL / name)])
            self.assertTrue(g.stdout.startswith("READ "), g.stdout)
            r = run([str(REAL / name)])
            self.assertTrue(r.stdout.startswith("Read this file directly"), r.stdout[:200])
            self.assertLessEqual(dl_util.est_tokens(r.stdout), 120)


if __name__ == "__main__":
    unittest.main()
