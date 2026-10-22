"""Dead code and the copy loop in the sigmadeeplook scripts (ticket 83, S12 note, S18).

Seven functions had no caller. safe_extract repeated one 64 KB copy loop for zip and for tar. The behaviour stays: the tests below pin it
for zip and tar, the byte limit and the path-escape check, and name the seven dead functions so they do not come back.
"""
import io
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import dl_bins  # noqa: E402
import dl_core  # noqa: E402
import dl_data  # noqa: E402
import dl_docs  # noqa: E402
import dl_media  # noqa: E402

DEAD = {
    dl_data: ["decode_best", "profile_line"],
    dl_core: ["collapse_direct", "md_table"],
    dl_docs: ["mail_ics"],
    dl_media: ["scenes_list"],
}


class DeadCode(unittest.TestCase):
    def test_dead_functions_stay_gone(self):
        back = [f"{m.__name__}.{n}" for m, names in DEAD.items() for n in names if hasattr(m, n)]
        self.assertEqual(back, [])

    def test_need_tool_stays_gone(self):
        import inspect
        for _name, cls in inspect.getmembers(dl_core, inspect.isclass):
            self.assertFalse(hasattr(cls, "need_tool"), cls.__name__)


class SafeExtract(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dl_s18_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def make(self, kind):
        p = self.tmp / ("a." + kind)
        if kind == "zip":
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("one.txt", b"hello")
                z.writestr("sub/two.bin", b"x" * 200000)
                z.writestr("../evil.txt", b"no")
        else:
            with tarfile.open(p, "w") as t:
                for name, data in (("one.txt", b"hello"), ("sub/two.bin", b"x" * 200000), ("../evil.txt", b"no")):
                    ti = tarfile.TarInfo(name)
                    ti.size = len(data)
                    t.addfile(ti, io.BytesIO(data))
        return SimpleNamespace(path=str(p), subtype=kind)

    def test_zip_and_tar_write_the_members(self):
        for kind in ("zip", "tar"):
            look = self.make(kind)
            dest = self.tmp / ("out_" + kind)
            got = dl_bins.safe_extract(look, ["one.txt", "sub/two.bin"], ["one.txt", "sub/two.bin"], dest)
            self.assertEqual([p.name for p in got], ["one.txt", "two.bin"], kind)
            self.assertEqual((dest / "one.txt").read_bytes(), b"hello", kind)
            self.assertEqual(len((dest / "sub" / "two.bin").read_bytes()), 200000, kind)

    def test_member_that_escapes_is_refused(self):
        for kind in ("zip", "tar"):
            look = self.make(kind)
            with self.assertRaises(ValueError, msg=kind):
                dl_bins.safe_extract(look, ["../evil.txt"], ["../evil.txt"], self.tmp / ("esc_" + kind))
            self.assertFalse((self.tmp / "evil.txt").exists(), kind)

    def test_byte_limit_stops_the_copy(self):
        old = dl_bins.MAX_TOTAL
        dl_bins.MAX_TOTAL = 1000
        try:
            for kind in ("zip", "tar"):
                look = self.make(kind)
                with self.assertRaises(ValueError, msg=kind):
                    dl_bins.safe_extract(look, ["sub/two.bin"], ["sub/two.bin"], self.tmp / ("lim_" + kind))
        finally:
            dl_bins.MAX_TOTAL = old


if __name__ == "__main__":
    unittest.main()
