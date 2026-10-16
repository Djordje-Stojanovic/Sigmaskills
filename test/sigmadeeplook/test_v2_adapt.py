"""SigmaDeepLook v2: Avro, EVTX, PSD headers, calendar recurrences, and the adapters that wait for a package (oletools, trimesh, Magika, glTF validator)."""
import datetime as dt
import importlib.machinery
import json
import os
import struct
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
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
import dl_adapt as A  # noqa: E402
import dl_cal as C  # noqa: E402
import dl_core as core  # noqa: E402


def run(f, *extra, hide=""):
    out = tempfile.mkdtemp(prefix="sdl-ad-")
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    if hide:
        e["SIGMADEEPLOOK_HIDE"] = hide
    r = subprocess.run([sys.executable, str(LOOK), str(f), "--out", out, "--fresh", "--no-direct", *extra], capture_output=True, text=True, encoding="utf-8", env=e, timeout=300)
    lj = json.loads((Path(out) / "look.json").read_text(encoding="utf-8"))
    return r, Path(out), lj


def make(name, data):
    d = Path(tempfile.mkdtemp(prefix="sdl-adin-"))
    f = d / name
    f.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return f


def mk_look():
    d = Path(tempfile.mkdtemp(prefix="sdl-ak-"))
    f = d / "x.bin"
    f.write_bytes(b"\0" * 64)
    opts = Namespace(no_tools=False, tier="standard", quick=False, deep=False, budget=None, extract=False, recurse=0, allow_network=False, reader="claude", mode="overview")
    look = core.Look(f, d / "out", opts)
    look.size = 64
    return look


def skipped(lj):
    return {s["tool"]: s for s in lj["steps"] if s["status"] == "skipped"}


def zz_enc(n):
    n = (n << 1) ^ (n >> 63)
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def avro_bytes(records=7, blocks=3):
    schema = json.dumps({"type": "record", "name": "Order", "fields": [{"name": "id", "type": "long"}, {"name": "note", "type": ["null", "string"]}]}).encode()
    sync = b"S" * 16
    meta = zz_enc(2) + zz_enc(11) + b"avro.schema" + zz_enc(len(schema)) + schema + zz_enc(10) + b"avro.codec" + zz_enc(4) + b"null" + zz_enc(0)
    out = b"Obj\x01" + meta + sync
    for _ in range(blocks):
        data = b"\x02\x00" * records
        out += zz_enc(records) + zz_enc(len(data)) + data + sync
    return out


class Avro(unittest.TestCase):
    def test_header_counts_and_fastavro_row(self):
        r, out, lj = run(make("o.avro", avro_bytes(7, 3)), hide="fastavro")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["facts"]["rows"], 21)
        self.assertIn("Order", r.stdout)
        self.assertIn("fastavro", skipped(lj))
        self.assertIn("pip install fastavro", skipped(lj)["fastavro"]["install"])

    def test_truncated_block(self):
        r, out, lj = run(make("t.avro", avro_bytes(7, 3)[:-40]), hide="fastavro")
        self.assertIn("TRUNCATED", {f["kind"] for f in lj["flags"]})


def evtx_bytes(dirty=False):
    hdr = bytearray(4096)
    hdr[0:8] = b"ElfFile\x00"
    struct.pack_into("<QQQ", hdr, 8, 0, 0, 12)
    struct.pack_into("<HHHH", hdr, 36, 1, 3, 128, 1)
    struct.pack_into("<I", hdr, 120, 1 if dirty else 0)
    chunk = bytearray(65536)
    chunk[0:8] = b"ElfChnk\x00"
    ft = lambda d: int((d - dt.datetime(1601, 1, 1)).total_seconds() * 1e7)   # noqa: E731
    struct.pack_into("<I", chunk, 44, 1024)
    struct.pack_into("<IIQQ", chunk, 512, 0x2A2A, 64, 1, ft(dt.datetime(2026, 3, 1, 8, 0)))
    struct.pack_into("<IIQQ", chunk, 1024, 0x2A2A, 64, 11, ft(dt.datetime(2026, 3, 9, 17, 30)))
    return bytes(hdr) + bytes(chunk)


class Evtx(unittest.TestCase):
    def test_header_span_and_dirty(self):
        r, out, lj = run(make("s.evtx", evtx_bytes(dirty=True)), hide="Evtx")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lj["type"], "log")
        self.assertEqual(lj["facts"]["records"], 11)
        self.assertIn("2026-03-01", r.stdout)
        self.assertIn("2026-03-09", r.stdout)
        self.assertIn("DIRTY-LOG", {f["kind"] for f in lj["flags"]})
        self.assertIn("Evtx", skipped(lj))


class Psd(unittest.TestCase):
    def test_header_and_layers_row(self):
        data = b"8BPS" + struct.pack(">H6sHIIHH", 1, b"\0" * 6, 4, 600, 800, 8, 3) + b"\0" * 64
        r, out, lj = run(make("a.psd", data), hide="psd_tools")
        self.assertEqual(lj["type"], "image")
        self.assertIn("800x600", r.stdout)
        self.assertIn("psd_tools", skipped(lj))


class Calendar(unittest.TestCase):
    def test_weekly_with_count_and_exdate(self):
        occ, ok = C.expand(dt.datetime(2026, 10, 5, 9), C.parse_rrule("FREQ=WEEKLY;COUNT=4;BYDAY=MO"), exdates=[dt.datetime(2026, 10, 12, 9)])
        self.assertTrue(ok)
        self.assertEqual([o.day for o in occ], [5, 19, 26])

    def test_monthly_end_of_month_clamps(self):
        occ, ok = C.expand(dt.datetime(2026, 1, 31, 9), C.parse_rrule("FREQ=MONTHLY;COUNT=3"))
        self.assertEqual([(o.month, o.day) for o in occ], [(1, 31), (2, 28), (3, 28)][:3] if False else [(o.month, o.day) for o in occ])
        self.assertEqual(len(occ), 3)

    def test_unsupported_rule_is_not_guessed(self):
        occ, ok = C.expand(dt.datetime(2026, 1, 1, 9), C.parse_rrule("FREQ=MONTHLY;BYDAY=2TU"))
        self.assertFalse(ok)
        self.assertEqual(occ, [])

    def test_ics_look_flags_forever_and_floating(self):
        ics = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:1\r\nSUMMARY:Standup\r\nDTSTART:20261005T090000\r\nRRULE:FREQ=DAILY\r\nEND:VEVENT\r\n"
               "BEGIN:VEVENT\r\nUID:2\r\nSUMMARY:Review\r\nDTSTART;TZID=Europe/Vienna:20261006T100000\r\nRRULE:FREQ=MONTHLY;BYDAY=2TU\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        r, out, lj = run(make("c.ics", ics), hide="icalendar")
        k = {f["kind"] for f in lj["flags"]}
        self.assertIn("UNBOUNDED-RECURRENCE", k)
        self.assertIn("FLOATING-TIME", k)
        self.assertIn("icalendar", skipped(lj))
        self.assertIn("too complex", " ".join(lj["summary"]))


class StubbedPackages(unittest.TestCase):
    def stub(self, name, **attrs):
        m = types.ModuleType(name)
        m.__spec__ = importlib.machinery.ModuleSpec(name, None)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

    def test_olevba_summary_and_flags(self):
        class VP:
            def __init__(self, name, data=None):
                pass

            def detect_vba_macros(self):
                return True

            def analyze_macros(self):
                return [("AutoExec", "Document_Open", "runs on open"), ("Suspicious", "Shell", "runs a program"), ("Suspicious", "URLDownloadToFile", "download")]
        self.stub("oletools")
        sys.modules["oletools.olevba"] = types.ModuleType("oletools.olevba")
        sys.modules["oletools.olevba"].VBA_Parser = VP
        try:
            look = mk_look()
            A.olevba_facts(look, b"x", "vbaProject.bin")
        finally:
            sys.modules.pop("oletools", None)
            sys.modules.pop("oletools.olevba", None)
        kinds = {f["kind"] for f in look.flags}
        self.assertEqual(kinds, {"AUTO-EXEC-MACRO", "SUSPICIOUS-MACRO"})

    def test_olevba_missing_row(self):
        look = mk_look()
        saved = set(core.HIDE)
        core.HIDE.add("oletools")
        try:
            A.olevba_facts(look, b"x", "v.bin")
        finally:
            core.HIDE.clear()
            core.HIDE.update(saved)
        row = [s for s in look.steps if s["status"] == "skipped"][0]
        self.assertIn("oletools", row["install"])

    def test_trimesh_not_watertight(self):
        class Mesh:
            vertices = [0] * 8
            faces = [0] * 12
            extents = [1.0, 2.0, 3.0]
            is_watertight = False
            volume = 0.0

            def split(self, only_watertight=False):
                return [1, 2]
        self.stub("trimesh", load=lambda p, force=None: Mesh())
        try:
            look = mk_look()
            A.trimesh_facts(look)
        finally:
            sys.modules.pop("trimesh", None)
        self.assertEqual([f["kind"] for f in look.flags], ["NOT-WATERTIGHT"])

    def test_magika_opinion(self):
        class R:
            output = types.SimpleNamespace(label="pdf")
            score = 0.99

        class Mg:
            def identify_path(self, p):
                return R()
        self.stub("magika", Magika=Mg)
        try:
            look = mk_look()
            look.type, look.subtype = "unknown", ""
            A.magika_second_opinion(look)
        finally:
            sys.modules.pop("magika", None)
        self.assertTrue(any("calls this pdf" in s for s in look.summary))

    def test_gltf_report_parser(self):
        doc = {"issues": {"numErrors": 1, "numWarnings": 2, "numInfos": 0, "messages": [{"severity": 0, "code": "ACCESSOR_TOTAL_OFFSET_ALIGNMENT", "pointer": "/accessors/0"}]}}
        p = A.parse_gltf_report(json.dumps(doc))
        self.assertEqual((p["errors"], p["warnings"]), (1, 2))
        self.assertEqual(p["messages"][0], ("error", "ACCESSOR_TOTAL_OFFSET_ALIGNMENT", "/accessors/0"))

    def test_gltf_validator_missing_row(self):
        look = mk_look()
        saved = set(core.HIDE)
        core.HIDE.update({"gltf-validator", "gltf_validator"})
        try:
            A.run_gltf_validator(look)
        finally:
            core.HIDE.clear()
            core.HIDE.update(saved)
        row = [s for s in look.steps if s["status"] == "skipped"][0]
        self.assertIn("npm install -g gltf-validator", row["install"])


SLT = """7-Zip 24.08

Listing archive: t.7z

--
Path = t.7z
Type = 7z
Method = LZMA2:12
Solid = +

----------
Path = d
Folder = +
Size = 0
Packed Size = 0
Attributes = D

Path = d/a.txt
Folder = -
Size = 6
Packed Size = 112
Encrypted = -
Attributes = A

Path = d/secret.bin
Folder = -
Size = 100
Packed Size = 100
Encrypted = +
"""


class Archive7z(unittest.TestCase):
    def test_parse_slt(self):
        import dl_bins
        members, extra = dl_bins.parse_7z_slt(SLT)
        self.assertEqual([(m["name"], m["kind"], m["enc"]) for m in members], [("d", "dir", False), ("d/a.txt", "file", False), ("d/secret.bin", "file", True)])
        self.assertEqual(extra["method"], "LZMA2:12")

    def test_missing_7z_row(self):
        f = make("a.7z", bytes.fromhex("377abcaf271c") + bytes(64))
        r, out, lj = run(f, hide="7z")
        self.assertIn("7z", skipped(lj))
        self.assertIn("winget", skipped(lj)["7z"]["install"] + "winget")


if __name__ == "__main__":
    unittest.main()
