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
SECTIONS = ["Key facts", "Watch out", "Map", "Read next", "Not looked at"]


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
        r, out = look("bad.csv")
        self.assertEqual(r.returncode, 0, r.stderr)
        heads = re.findall(r"^## (.+?)\s*$", re.sub(r"```.*?```", "", r.stdout, flags=re.S), re.M)
        heads = [h for h in heads if not h.startswith("Content: ")]
        self.assertEqual([h for h in SECTIONS if h in heads], heads)
        self.assertIn("Key facts", heads)
        self.assertEqual((out / "LOOK.md").read_text(encoding="utf-8").strip(), r.stdout.strip())
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        self.assertEqual(lj["schema"], 1)
        self.assertEqual(lj["type"], "data")
        self.assertTrue((out / "view.html").exists())

    def test_same_file_same_folder(self):
        a = run([str(FX / "plain.txt"), "--json", "--no-tools", "--fresh"])
        b = run([str(FX / "plain.txt"), "--json", "--no-tools"])
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(json.loads(a.stdout)["sha256"], json.loads(b.stdout)["sha256"])


def look_bytes(name, data, *extra):
    d = Path(tempfile.mkdtemp(prefix="sdl-in-"))
    f = d / name
    f.write_bytes(data)
    out = tempfile.mkdtemp(prefix="sdl-out-")
    r = run([str(f), "--out", out, "--fresh", "--no-tools", "--json", *extra])
    return r, Path(out), (json.loads(r.stdout) if r.stdout.strip().startswith("{") else None)


def threshold():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(LOOK.parent))
    import dl_core
    return dl_core.DIRECT_MAX_BYTES


def csv_of_size(n):
    """Exactly n bytes of well-formed, valid UTF-8 CSV (the last line is padded)."""
    lines, size, i = ["id,name,note"], 13, 0
    while size < n - 60:
        line = f"{i},name{i},some plain note text"
        lines.append(line)
        size += len(line) + 1
        i += 1
    lines.append("end,pad," + "x" * (n - size - len("end,pad,") - 1))
    data = ("\n".join(lines) + "\n").encode()
    assert len(data) == n, (len(data), n)
    return data


class DirectTier(unittest.TestCase):
    """Fix round 4: a small text file is never 'read directly' with no summary. It gets a full look with exact counts, stored so
    --more works, plus one note that reading it whole is also fine."""
    def test_threshold_boundary(self):
        n = threshold()
        under, out_u, lj_u = look_bytes("under.csv", csv_of_size(n))
        over, out_o, lj_o = look_bytes("over.csv", csv_of_size(n + 1))
        self.assertEqual(under.returncode, 0, under.stderr)
        self.assertEqual(lj_u["size"], n)
        self.assertTrue(lj_u["facts"].get("direct_read"))
        self.assertEqual(lj_o["size"], n + 1)
        self.assertFalse(lj_o["facts"].get("direct_read"))
        md_u = (out_u / "LOOK.md").read_text(encoding="utf-8")
        md_o = (out_o / "LOOK.md").read_text(encoding="utf-8")
        self.assertIn("Small text file: the whole file is ~", md_u)
        self.assertNotIn("Small text file", md_o)
        for md in (md_u, md_o):
            self.assertIn("Counts:", md)
            self.assertNotIn("Read this file directly", md)

    def test_small_file_gets_a_full_look_and_keeps_real_flags(self):
        r, out, lj = look_bytes("rows.csv", b"id,name,note\n1,a,x\n2,b\n3,c,z\n")
        self.assertNotEqual(lj["tier"], "direct")
        self.assertTrue(lj["stream"], "the look is stored as a stream")
        self.assertIn("REJECT-ROW", (out / "LOOK.md").read_text(encoding="utf-8"))
        self.assertEqual(lj["facts"]["rejects"], 1)
        self.assertEqual(lj["facts"]["counts"]["data rows"], 3)

    def test_invalid_utf8_small_file_is_not_direct_and_is_flagged(self):
        r, out, lj = look_bytes("latin.csv", b"id,name\n1,Caf\xe9\n2,Zo\xeb\n3,x\n")
        self.assertNotEqual(lj["tier"], "direct")
        self.assertIn("ENCODING", [f["kind"] for f in lj["flags"]])

    def test_binary_and_media_are_never_direct(self):
        for name in ("app.sqlite", "clip.mp4", "hello.exe", "chart.png", "logo.svg", "mixed.pdf"):
            r, out = look(name)
            self.assertNotEqual(json.loads((out / "look.json").read_text(encoding="utf-8"))["tier"], "direct", name)
        r, out, lj = look_bytes("nul.txt", b"hello\x00world\n" * 4)
        self.assertNotEqual(lj["tier"], "direct")

    def test_no_direct_switch(self):
        r, out, lj = look_bytes("small.csv", b"a,b\n1,2\n3,4\n", "--no-direct")
        self.assertNotEqual(lj["tier"], "direct")

    def test_small_text_kinds_get_a_summary_not_a_bare_read_line(self):
        for name in ("plain.txt", "tool.py", "events.jsonl", "box.mbox", "cal.ics", "nb.ipynb"):
            r, out = look(name)
            lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
            md = (out / "LOOK.md").read_text(encoding="utf-8")
            self.assertFalse(md.startswith("Read this file directly"), name)
            self.assertTrue(md.startswith("# "), name)
            self.assertGreater(len(lj["stream"]), 2, name)
        r, out = look("tool.py")
        self.assertIn("U+200B", r.stdout)  # hidden Unicode is a real flag and survives


class BigText(unittest.TestCase):
    """Above the direct-read line the look must find faults that sit anywhere in the file, not only in a sample."""

    def test_csv_full_pass_finds_planted_faults(self):
        head = "id,amount,status,day,qty"
        rows = [head]
        for i in range(1, 6001):
            amount = "N/A" if i == 5500 else '"1,299.50"' if i == 5600 else "9999999.99" if i == 5900 else f"{10 + i % 90}.00"
            rows.append(f"{i if i != 5001 else 5000},{amount},{'shipped' if i % 7 else 'Shipped'},2026-01-{1 + i % 28:02d},{-2 if i == 5950 else 1 + i % 5}")
            if i == 3000:
                rows.append(head)
        data = ("\n".join(rows) + "\n").encode()
        self.assertGreater(len(data), threshold())
        r, out, lj = look_bytes("orders.csv", data)
        kinds = {f["kind"] for f in lj["flags"]}
        for k in ("REPEATED-HEADER", "DUPLICATE-KEYS", "MIXED-TYPES", "NULL-TOKENS", "OUTLIER", "CASE-VARIANTS", "NEGATIVE-VALUES"):
            self.assertIn(k, kinds, k)
        self.assertEqual(lj["facts"]["rows"], 6000)

    def test_mbox_profile_flags_auth_failures_and_link_mismatch(self):
        msgs = []
        for i in range(400):
            auth = "Authentication-Results: mx; spf=fail\n" if i % 100 == 7 else ""
            body = ('Content-Type: text/html\n\n<a href="https://evil.example.net/x">https://bank.example.org</a>\n' if i == 250
                    else "Content-Type: text/plain\n\nhello number " + "x" * 120 + "\n")
            msgs.append(f"From a{i % 3}@example.org Mon Sep  1 00:00:00 2026\nFrom: a{i % 3}@example.org\nSubject: Report {i}\nDate: Mon, 01 Sep 2026 10:00:00 +0000\n{auth}{body}\n")
        data = "".join(msgs).encode()
        self.assertGreater(len(data), threshold())
        r, out, lj = look_bytes("box.mbox", data)
        kinds = [f["kind"] for f in lj["flags"]]
        self.assertIn("AUTH-FAIL", kinds)
        self.assertIn("LINK-MISMATCH", kinds)
        self.assertEqual(lj["facts"]["messages"], 400)
        self.assertEqual(lj["facts"]["auth_failures"], 4)


class Refusals(unittest.TestCase):
    def test_unsafe_archives_exit_2_and_write_nothing(self):
        for name in ("slip.zip", "nested.zip", "links.tar"):
            r, out = look(name, "--extract")
            self.assertEqual(r.returncode, 2, name)
            self.assertIn("REFUSED", r.stdout, name)
            self.assertFalse((out / "extract").exists(), name)

    def test_a_ratio_bomb_member_is_left_out_not_the_archive(self):
        r, out = look("ratio.zip", "--extract")
        self.assertEqual(r.returncode, 0)
        self.assertIn("REFUSED", r.stdout)
        self.assertFalse((out / "extract" / "zeros.bin").exists())

    def test_unknown_and_empty_exit_3(self):
        for name in ("empty.bin", "noise.bin"):
            r, _ = look(name)
            self.assertEqual(r.returncode, 3, name)
            self.assertNotIn("sha ", r.stdout, "concise default: no id on the identity line")
            self.assertIn("folder:", r.stdout)

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
