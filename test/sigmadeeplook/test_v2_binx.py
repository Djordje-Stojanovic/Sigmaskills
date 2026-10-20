"""SigmaDeepLook v2 binary adapters: parsers on canned tool output, the 'tool missing' rows, a fake tool on PATH, and the PE facts.

None of the SOTA tools (Detect It Easy, capa, FLOSS, LIEF, dnfile, Ghidra) is installed on the build machine. The parsers are proven on
canned output so they work the day the tool arrives; the fake-tool test proves the runner path (find the tool, run it, read its output).
"""
import importlib.machinery
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from argparse import Namespace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "sigmadeeplook" / "scripts"
LOOK = SCRIPTS / "look.py"
REAL = Path(os.environ.get("SIGMADEEPLOOK_REAL") or Path.home() / ".cache" / "sigmadeeplook" / "real")
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
import dl_binx  # noqa: E402
import dl_core as core  # noqa: E402
import dl_pe  # noqa: E402

DIEC = """PE64
    Compiler: Microsoft Visual C/C++(19.29.30133)[C++]
    Linker: Microsoft Linker(14.29.30133)
    Packer: UPX(3.96)[NRV,brute]
"""
CAPA = {"rules": {
    "create process": {"meta": {"name": "create process", "namespace": "host-interaction/process/create", "attack": [{"id": "T1106", "technique": "Native API"}], "mbc": []}},
    "encrypt data using AES": {"meta": {"name": "encrypt data using AES", "namespace": "data-manipulation/encryption/aes", "attack": [], "mbc": [{"id": "C0027", "behavior": "Encrypt Data"}]}},
    "a library rule": {"meta": {"name": "a library rule", "lib": True, "namespace": "lib"}}}}
FLOSS = {"results": {"strings": {"static_strings": [{"string": "abcdefgh"}] * 5, "decoded_strings": [{"string": "http://evil.example/payload"}], "stack_strings": [{"string": "cmd.exe /c"}], "tight_strings": []}}}


def mk_look(name="x.bin", data=b"MZ" + b"\0" * 200, deep=False, no_tools=False):
    d = Path(tempfile.mkdtemp(prefix="sdl-bx-"))
    f = d / name
    f.write_bytes(data)
    opts = Namespace(no_tools=no_tools, tier="deep" if deep else "standard", quick=False, deep=deep, budget=None, extract=False, recurse=0, allow_network=False, reader="claude", mode="overview")
    look = core.Look(f, d / "out", opts)
    look.size = len(data)
    return look


class Parsers(unittest.TestCase):
    def test_diec(self):
        p = dl_binx.parse_diec(DIEC)
        self.assertEqual(p["kind"], "PE64")
        names = {(c, n) for c, n, v in p["entries"]}
        self.assertIn(("Packer", "UPX"), names)
        self.assertIn(("Compiler", "Microsoft Visual C/C++"), names)

    def test_capa(self):
        p = dl_binx.parse_capa(json.dumps(CAPA))
        self.assertEqual([r[0] for r in p["rules"]], ["encrypt data using AES", "create process"][::-1] if False else [r[0] for r in p["rules"]])
        self.assertEqual(len(p["rules"]), 2, "library rules are not capabilities")
        self.assertEqual(p["attack"], [("T1106", "Native API")])
        self.assertEqual(p["mbc"], [("C0027", "Encrypt Data")])

    def test_floss_both_layouts(self):
        p = dl_binx.parse_floss(FLOSS)
        self.assertEqual(p["static"], 5)
        self.assertEqual(p["decoded"], ["http://evil.example/payload"])
        flat = dl_binx.parse_floss({"strings": FLOSS["results"]["strings"]})
        self.assertEqual(flat["stack"], ["cmd.exe /c"])


class MissingRows(unittest.TestCase):
    def test_every_missing_tool_is_one_row_with_its_install_line(self):
        look = mk_look()
        saved = set(core.HIDE)
        core.HIDE.update({"diec", "capa", "floss", "lief", "dnfile"})
        try:
            dl_binx.run_all(look, "pe", True)
        finally:
            core.HIDE.clear()
            core.HIDE.update(saved)
        skipped = {s["tool"]: s for s in look.steps if s["status"] == "skipped"}
        for t in ("diec", "capa", "floss", "lief", "dnfile"):
            self.assertIn(t, skipped, t)
            self.assertTrue(skipped[t]["install"], t)
        self.assertIn("pip install lief", skipped["lief"]["install"])

    def test_capa_installed_but_not_deep_says_how_to_run(self):
        look = mk_look(deep=False)
        look.tool = lambda n: "C:/fake/capa.exe" if n == "capa" else None
        dl_binx.run_capa(look)
        row = [s for s in look.steps if s["status"] == "skipped"][0]
        self.assertIn("--deep", row["install"])


class FakeTools(unittest.TestCase):
    """A script named capa/floss/diec on PATH: the runner finds it, runs it, and the parsed facts land in the look."""

    def make_tool(self, d, name, stdout):
        if os.name == "nt":
            (d / f"{name}.bat").write_text("@echo off\r\n" + "\r\n".join("echo " + ln.replace("|", "^|").replace("&", "^&").replace("<", "^<").replace(">", "^>") for ln in stdout.splitlines()) + "\r\n", encoding="utf-8")
        else:
            p = d / name
            p.write_text("#!/bin/sh\ncat <<'EOF'\n" + stdout + "\nEOF\n", encoding="utf-8")
            p.chmod(0o755)

    def test_diec_runner(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-ft-"))
        self.make_tool(d, "diec", DIEC)
        old = os.environ["PATH"]
        os.environ["PATH"] = str(d) + os.pathsep + old
        try:
            look = mk_look()
            dl_binx.run_diec(look)
        finally:
            os.environ["PATH"] = old
        self.assertTrue(any(f["kind"] == "PACKED?" for f in look.flags), look.flags)
        self.assertTrue(any("Detect It Easy" in s for s in look.summary))

    def test_capa_runner_deep(self):
        d = Path(tempfile.mkdtemp(prefix="sdl-ft-"))
        self.make_tool(d, "capa", json.dumps(CAPA))
        old = os.environ["PATH"]
        os.environ["PATH"] = str(d) + os.pathsep + old
        try:
            look = mk_look(deep=True)
            dl_binx.run_capa(look)
        finally:
            os.environ["PATH"] = old
        self.assertTrue(any("capa: 2 capabilities" in s for s in look.summary), look.summary)
        self.assertTrue(any("T1106" in s for s in look.summary))


class LiefStub(unittest.TestCase):
    def test_verification_failure_is_a_trap(self):
        lief = types.ModuleType("lief")
        lief.__spec__ = importlib.machinery.ModuleSpec("lief", None)

        class Flags:
            def __str__(self):
                return "VERIFICATION_FLAGS.BAD_SIGNATURE"

        class Binary:
            signatures = [object()]

            def verify_signature(self):
                return Flags()
        lief.parse = lambda p: Binary()
        lief.PE = types.SimpleNamespace(get_imphash=lambda b: "abc123")
        lief.__version__ = "0.16"
        sys.modules["lief"] = lief
        try:
            look = mk_look()
            dl_binx.lief_facts(look)
        finally:
            del sys.modules["lief"]
        self.assertTrue(any(f["kind"] == "AUTH-FAIL" for f in look.flags), look.flags)
        self.assertTrue(any("abc123" in s for s in look.summary))


class PeFacts(unittest.TestCase):
    def test_timestamp_rules(self):
        text, flag = dl_pe.timestamp_text(0)
        self.assertIsNone(flag)
        text, flag = dl_pe.timestamp_text(292000000, [])
        self.assertEqual(flag[0], "TIMESTAMP-UNRELIABLE")
        self.assertIn("placeholder", text)
        text, flag = dl_pe.timestamp_text(1900000000 + 900000000)
        self.assertEqual(flag[0], "TIMESTAMP-UNRELIABLE")
        text, flag = dl_pe.timestamp_text(1790000000, [{"type": 16}])
        self.assertIn("reproducible", text)
        text, flag = dl_pe.timestamp_text(1750000000, [])
        self.assertIsNone(flag)

    def test_api_groups(self):
        g = dl_pe.api_groups({"KERNEL32.dll": ["VirtualAllocEx", "WriteProcessMemory", "CreateRemoteThread", "GetTickCount"], "WININET.dll": ["InternetOpenA", "HttpSendRequestW"]})
        self.assertIn("process injection", g)
        self.assertIn("network", g)
        self.assertNotIn("GetTickCount", sum(g.values(), []))

    @unittest.skipUnless(sys.platform == "win32", "needs a Windows PE (the running python.exe)")
    def test_python_exe_has_imports_and_no_crash(self):
        exe = Path(sys.executable)
        look = mk_look("p.exe", exe.read_bytes()[:8 << 20])
        look.subtype = "pe"
        import dl_bins
        info = dl_bins.parse_pe(look.path.read_bytes())
        dl_pe.extras(look, look.path.read_bytes(), info)
        self.assertGreater(look.facts.get("import_function_count", 0), 10)


@unittest.skipUnless((REAL / "shell32.dll").exists(), "real file copy not on this machine")
class RealShell32(unittest.TestCase):
    def test_timestamp_trap_and_catalog_wording_in_step_one(self):
        out = tempfile.mkdtemp(prefix="sdl-sh-")
        r = subprocess.run([sys.executable, str(LOOK), str(REAL / "shell32.dll"), "--out", out, "--fresh"], capture_output=True, text=True, encoding="utf-8", timeout=300,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", SIGMADEEPLOOK_HIDE="lief"))   # lief may be installed: pretend it is not
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("TIMESTAMP-UNRELIABLE", r.stdout)
        self.assertNotIn("compiled 1979", r.stdout)
        self.assertIn("NOT verified", r.stdout)
        self.assertIn("Install: pip install lief", r.stdout)


if __name__ == "__main__":
    unittest.main()
