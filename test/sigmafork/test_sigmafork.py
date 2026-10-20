"""Offline tests for sigmafork/scripts/sigmafork.py (standard library, temp folders only)."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sigmafork" / "scripts"))
import sigmafork as sf  # noqa: E402


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()):
        return fn(*args)


class Spellings(unittest.TestCase):
    def test_windows_root_has_every_spelling(self):
        got = dict(sf.spellings(r"C:\AI\Repo"))
        self.assertEqual(got["back"], r"C:\AI\Repo")
        self.assertEqual(got["fwd"], "C:/AI/Repo")
        self.assertEqual(got["escaped"], "C:" + "\\\\" + "AI" + "\\\\" + "Repo")
        self.assertEqual(got["gitbash"], "/c/AI/Repo")
        self.assertEqual(got["wsl"], "/mnt/c/AI/Repo")
        self.assertEqual(got["file"], "file:///C:/AI/Repo")

    def test_rewrite_keeps_the_style_and_stops_at_a_name_boundary(self):
        rx, styles = sf.pattern(r"C:\AI\Repo")
        text = rb"a C:\AI\Repo\x b c:/ai/repo/y c C:\AI\Repo_old d C:\AI\Repo.bak e /c/AI/Repo."
        out = rx.sub(lambda m: sf.render(r"D:\T\Copy", styles[m.group(0).decode().lower()]).encode(), text)
        self.assertEqual(out, rb"a D:\T\Copy\x b D:/T/Copy/y c C:\AI\Repo_old d C:\AI\Repo.bak e /d/T/Copy.")

    def test_posix_destination(self):
        self.assertEqual(sf.render("/home/me/copy", "back"), "/home/me/copy")
        self.assertEqual(sf.render("/home/me/copy", "file"), "file:///home/me/copy")


class EndToEnd(unittest.TestCase):
    def test_selftest_passes(self):
        self.assertEqual(quiet(sf.cmd_selftest), 0)

    def test_git_remote_into_the_source_blocks_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp, "Src"), Path(tmp, "Dest")
            (src / ".git").mkdir(parents=True)
            (src / ".git" / "config").write_text(f'[remote "origin"]\n\turl = {src}\n', encoding="utf-8")
            (src / "a.txt").write_text("plain", encoding="utf-8")
            self.assertEqual(quiet(sf.cmd_copy, src, dest, [], False, False), 0)
            self.assertEqual(quiet(sf.cmd_fix, dest, str(src), []), 0)
            self.assertEqual(quiet(sf.cmd_verify, dest, str(src)), 1, "a remote into the source must block")
            (dest / ".git" / "config").write_text('[remote "origin"]\n\turl = https://example.invalid/x.git\n', encoding="utf-8")
            self.assertEqual(quiet(sf.cmd_verify, dest, str(src)), 0)

    def test_map_rewrites_an_outside_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp, "Src"), Path(tmp, "Dest")
            src.mkdir()
            esc = "\\\\"  # two backslashes, as JSON writes one
            (src / "cfg.json").write_text('{"out": "Z:' + esc + 'renders' + esc + 'Src' + esc + 'final"}', encoding="utf-8")
            quiet(sf.cmd_copy, src, dest, [], False, False)
            report = sf.scan(dest, str(src), [])
            self.assertTrue(any(k.startswith("Z:\\renders\\Src") for k in report["outside_paths"]), report)
            quiet(sf.cmd_fix, dest, str(src), [("Z:\\renders\\Src", "Z:\\renders\\Copy")])
            self.assertIn("Z:" + esc + "renders" + esc + "Copy" + esc + "final", (dest / "cfg.json").read_text(encoding="utf-8"))
            self.assertIn("Src", (src / "cfg.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
