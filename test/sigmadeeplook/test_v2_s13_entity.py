"""S13 review 10-23: the XML entity guards looked only at the start of the file, and zip parts were read without a size limit.

dl_docs.parse_xml refused a DTD entity only when "<!ENTITY" sat in the first 200,000 bytes, and dl_data.xml_entity_danger scanned only the first
1,000,000 bytes. A comment of that size before the DOCTYPE hid the declaration: the parser then expanded it (10 MB of text from a 250 KB part in
the case below), which is the memory blow-up both guards exist to stop.
"""
import os
import sys
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import dl_core  # noqa: E402
import dl_data  # noqa: E402
import dl_docs  # noqa: E402
import dl_offx  # noqa: E402


class Look:
    def __init__(self):
        self.flags = []

    def flag(self, *a):
        self.flags.append(a)

    def mod(self, name):
        return None                     # no defusedxml: the standard parser is what the guard protects


def bomb():
    """Ten levels of ten references: b0 -> 10 x a, b1 -> 10 x b0 ... b5 expands to 10 million characters."""
    decls = b'<!ENTITY a "aaaaaaaaaa">' + b"".join(
        b'<!ENTITY b%d "%s">' % (i, (b"&b%d;" % (i - 1) if i else b"&a;") * 10) for i in range(6))
    return b"<!DOCTYPE r [" + decls + b"]>"


def doc(pad):
    return b'<?xml version="1.0"?><!--' + b"x" * pad + b"-->" + bomb() + b"<r>&b5;</r>"


class EntityGuardSeesTheWholeFile(unittest.TestCase):
    def test_parse_xml_refuses_a_declaration_after_a_long_comment(self):
        for pad in (0, 250_000):
            look = Look()
            self.assertIsNone(dl_docs.parse_xml(look, doc(pad)), f"pad {pad}")
            self.assertEqual([f[0] for f in look.flags], ["ENTITY-DECLARATION"], f"pad {pad}")

    def test_xml_entity_danger_sees_a_declaration_after_a_long_comment(self):
        for pad in (0, 1_200_000):
            self.assertIn("expands to", dl_data.xml_entity_danger(doc(pad)) or "", f"pad {pad}")

    def test_a_harmless_entity_after_a_long_comment_is_still_allowed(self):
        small = b'<?xml version="1.0"?><!--' + b"x" * 1_200_000 + b'--><!DOCTYPE r [<!ENTITY c "copyright">]><r>&c;</r>'
        self.assertIsNone(dl_data.xml_entity_danger(small))


CORE = (b'<?xml version="1.0"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        b'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>%s</dc:title></cp:coreProperties>')


class ZipPartBomb(unittest.TestCase):
    """A 600 KB docx with a 600 MB docProps/core.xml took 7.1 GB of memory (measured 10-23): the properties reader read every part whole."""

    def docx(self, title_bytes):
        tmp = Path(tempfile.mkdtemp(prefix="dl_s13_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        p = tmp / "bomb.docx"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                       '<Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" '
                       'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            z.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                       'Target="word/document.xml"/></Relationships>')
            z.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       '<w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body></w:document>')
            z.writestr("docProps/core.xml", CORE % (b"A" * title_bytes))
        return p

    def test_a_bomb_part_reads_as_empty_and_is_flagged(self):
        p = self.docx(24 << 20)                                     # 24 MB inflated from about 24 KB
        look = Look()
        with dl_core.CappedZip(p, look=look) as z:
            self.assertEqual(z.read("docProps/core.xml"), b"")
            self.assertIsNone(dl_offx._xml(z, "docProps/core.xml"))
        kinds = [f[0] for f in look.flags]
        self.assertIn("TRUNCATED", kinds)
        self.assertNotIn("A" * 100, " ".join(str(f) for f in look.flags))

    def test_a_normal_part_reads_whole(self):
        p = self.docx(1000)
        with dl_core.CappedZip(p, look=Look()) as z:
            self.assertIn(b"A" * 1000, z.read("docProps/core.xml"))
            self.assertIn(b"A" * 1000, z.read(z.getinfo("docProps/core.xml")))      # a ZipInfo works too

    def test_office_look_flags_the_bomb_end_to_end(self):
        import json
        from test_v2 import run
        p = self.docx(24 << 20)
        out = p.parent / "out"
        r = run([str(p), "--out", str(out), "--fresh"])
        self.assertEqual(r.returncode, 0, r.stderr)
        facts = json.loads((out / "look.json").read_text(encoding="utf-8"))
        self.assertIn("TRUNCATED", json.dumps(facts))


CHILD = """import os, subprocess, sys, time
g = subprocess.Popen([sys.executable, "-c", "import os, sys, time; open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(40)", sys.argv[1]])
time.sleep(40)
"""


class ToolTimeout(unittest.TestCase):
    """A tool behind a .cmd or .sh shim: the timeout killed the shim, the real tool kept the output pipe, and the look waited for it for ever
    (measured 10-23 on Windows: diec on a truncated .exe ran at 100 % CPU for 10+ minutes after the 120 s limit)."""

    def shim(self):
        tmp = Path(tempfile.mkdtemp(prefix="dl_s13t_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        (tmp / "child.py").write_text(CHILD, encoding="utf-8")
        pidfile = tmp / "grandchild.pid"
        call = '"%s" "%s" "%s"' % (sys.executable, tmp / "child.py", pidfile)
        if sys.platform.startswith("win"):
            s = tmp / "tool.cmd"
            s.write_bytes(("@echo off\r\n" + call + "\r\n").encode())
        else:
            s = tmp / "tool.sh"
            s.write_bytes(("#!/bin/sh\n" + call + "\n").encode())
            s.chmod(0o755)
        return tmp, s, pidfile

    def alive(self, pid):
        if sys.platform.startswith("win"):
            import subprocess
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
            return str(pid) in out
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def test_a_timeout_kills_the_tool_behind_a_shim_and_returns_in_time(self):
        tmp, shim, pidfile = self.shim()
        opts = types.SimpleNamespace(tier=None, quick=False, deep=False, no_tools=False, allow_network=False, reader="claude", budget=1000)
        look = dl_core.Look(tmp / "child.py", tmp / "out", opts)
        t0 = time.time()
        got = look.run([str(shim)], timeout=3)
        took = time.time() - t0
        self.addCleanup(lambda: pidfile.exists() and self.alive(int(pidfile.read_text())) and __import__("os").kill(int(pidfile.read_text()), 9))
        self.assertIsNone(got)
        self.assertLess(took, 20, "the look waited for the tool behind the shim")
        self.assertEqual([f["kind"] for f in look.flags], ["TIMEOUT"])
        time.sleep(1)
        self.assertTrue(pidfile.exists(), "the grandchild never started")
        self.assertFalse(self.alive(int(pidfile.read_text())), "the tool behind the shim is still running")

    def test_run_tree_returns_output_and_the_exit_code(self):
        r = dl_core.run_tree([sys.executable, "-c", "import sys; sys.stdout.write('ok'); sys.stderr.write('e'); sys.exit(3)"], 20)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (3, b"ok", b"e"))
        r = dl_core.run_tree([sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read().upper())"], 20, input=b"abc", stdin=-1)
        self.assertEqual(r.stdout, b"ABC")


if __name__ == "__main__":
    unittest.main()
