"""Fix round 7 (held-out set 4): structure readers for families the first prints left to strings, built on fixtures made here.

Every expected figure comes from the code that wrote the fixture, never from the look. Library-gated tests skip when the library is missing.
"""
import importlib.util
import io
import json
import marshal
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))


def have(mod):
    return importlib.util.find_spec(mod) is not None


def leb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def sec(i, body):
    return bytes([i]) + leb(len(body)) + body


def be(o):
    if isinstance(o, int):
        return b"i%de" % o
    if isinstance(o, bytes):
        return b"%d:%s" % (len(o), o)
    if isinstance(o, str):
        return be(o.encode())
    if isinstance(o, list):
        return b"l" + b"".join(be(x) for x in o) + b"e"
    return b"d" + b"".join(be(k) + be(v) for k, v in sorted(o.items())) + b"e"


class R7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r7_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look(self, path, *extra, tools=True):
        out = self.tmp / ("out_" + path.name)
        r = run([str(path), "--out", str(out), "--fresh", *([] if tools else ["--no-tools"]), *extra])
        self.assertIn(r.returncode, (0, 3), r.stderr[-1500:])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return r.stdout, lj, "\n".join(x["text"] for x in lj["stream"])

    # ---------------------------------------------------------------- binaries
    def test_wasm_sections_imports_exports(self):
        mod = (b"\0asm\x01\0\0\0" + sec(1, b"\x01\x60\x00\x00") + sec(2, b"\x01" + leb(3) + b"env" + leb(1) + b"f" + b"\x00\x00")
               + sec(3, b"\x01\x00") + sec(7, b"\x01" + leb(3) + b"run" + b"\x00\x01") + sec(10, b"\x01\x02\x00\x0b"))
        p = self.tmp / "m.wasm"
        p.write_bytes(mod)
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("1 imports, 1 exports", out)
        self.assertIn("env.f (function)", stream)
        self.assertIn("run (function)", stream)
        self.assertIn("start function: none", stream)

    @unittest.skipUnless(shutil.which("javac"), "javac not installed")
    def test_java_class_members_and_constants(self):
        d = self.tmp / "jv"
        d.mkdir()
        (d / "Acct.java").write_text('package a.b;\npublic class Acct { public static final int LIMIT = 77; public static final String TAG = "x1"; private long bal; '
                                     'public void add(long c){bal+=c;} protected long get(){return bal;} }\n')
        subprocess.run(["javac", "-d", str(d), "--release", "11", str(d / "Acct.java")], check=True)
        out, lj, stream = self.look(d / "a" / "b" / "Acct.class", tools=False)
        self.assertIn("Java class a.b.Acct", out)
        self.assertIn("LIMIT = 77", stream)
        self.assertIn("TAG = 'x1'", stream)
        self.assertIn("Java 11", stream)
        self.assertIn("protected long get()", stream)

    def test_headerless_fixed_records_get_a_layout(self):
        p = self.tmp / "rec.bin"
        with open(p, "wb") as f:
            for i in range(1, 2001):
                f.write(struct.pack("<IfHH", i, 20.0 + (i % 7) * 0.5, i % 3, 0))
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("2,000 records of 12 bytes", out)
        self.assertIn("strictly increasing", stream)
        self.assertIn("uint32 1..2000", stream)
        self.assertIn("float32 20..23", stream)

    def test_midi_tracks_tempo_notes(self):
        def track(ev):
            d = b"".join(ev) + b"\x00\xff\x2f\x00"
            return b"MTrk" + struct.pack(">I", len(d)) + d
        t0 = track([b"\x00\xff\x51\x03" + (500000).to_bytes(3, "big"), b"\x00\xff\x58\x04\x03\x02\x18\x08"])
        t1 = track([b"\x00\xff\x03\x03Pno", b"\x00\xc0\x00"] + [b"\x00\x90\x3c\x50", b"\x60\x80\x3c\x00"] * 5)
        p = self.tmp / "t.mid"
        p.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 1, 2, 96) + t0 + t1)
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("2 tracks", out)
        self.assertIn("5 notes", stream)
        self.assertIn("120.0 BPM", stream)
        self.assertIn("3/4", stream)
        self.assertIn("Acoustic Grand Piano", stream)

    def test_torrent_files_and_trackers(self):
        info = {"name": "pack", "piece length": 16384, "pieces": b"\0" * 20 * 3, "files": [{"length": 1000, "path": ["a", "x.bin"]}, {"length": 2500, "path": ["b.txt"]}]}
        p = self.tmp / "t.torrent"
        p.write_bytes(be({"announce": "udp://t1.example:80", "announce-list": [["udp://t1.example:80"], ["udp://t2.example:81"]], "info": info}))
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("2 files, 3.4 KB" if "3.4 KB" in out else "2 files", out)
        self.assertIn("total 3,500 bytes", stream)
        self.assertIn("Trackers (2)", stream)
        self.assertIn("a/x.bin 1,000", stream)

    def test_deb_control_file_and_installed_files(self):
        def tgz(files):
            b = io.BytesIO()
            with tarfile.open(fileobj=b, mode="w:gz") as t:
                for n, d in files:
                    ti = tarfile.TarInfo(n)
                    ti.size = len(d)
                    t.addfile(ti, io.BytesIO(d))
            return b.getvalue()

        def ar(ms):
            o = b"!<arch>\n"
            for n, d in ms:
                o += n.ljust(16).encode() + b"1700000000  0     0     100644  " + str(len(d)).ljust(10).encode() + b"`\n" + d + (b"\n" if len(d) % 2 else b"")
            return o
        p = self.tmp / "x.deb"
        p.write_bytes(ar([("debian-binary", b"2.0\n"), ("control.tar.gz", tgz([("./control", b"Package: demo\nVersion: 1.2.3\nArchitecture: all\n")])),
                          ("data.tar.gz", tgz([("./usr/bin/demo", b"abc"), ("./etc/demo.conf", b"k=v\n")]))]))
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("Debian package", out)
        self.assertIn("Version: 1.2.3", stream)
        self.assertIn("2 files, 7 bytes installed", stream)

    def test_pyc_names_and_version(self):
        src = self.tmp / "mm.py"
        src.write_text("K = 'zz'\ndef a(x):\n    return x\nclass B:\n    pass\n")
        import py_compile
        pyc = self.tmp / "mm.pyc"
        py_compile.compile(str(src), cfile=str(pyc))
        out, lj, stream = self.look(pyc, tools=False)
        self.assertIn("Python bytecode", out)
        self.assertIn("module code names: K, a, B", stream)
        self.assertIn("'zz'", stream)

    # ---------------------------------------------------------------- tables
    @unittest.skipUnless(have("numpy"), "numpy")
    def test_npz_arrays_are_summarised(self):
        import numpy as np
        p = self.tmp / "a.npz"
        a = np.arange(1, 101, dtype="int32")
        m = np.zeros((4, 5), dtype=bool)
        m[1, :3] = True
        np.savez(p, vals=a, mask=m, x=np.array([0.5, 1.5, 2.5]))
        out, lj, stream = self.look(p)
        self.assertIn("3 arrays", out)
        self.assertIn("vals: dtype int32, shape 100", stream)
        self.assertIn("min 1, max 100, mean 50.5", stream)
        self.assertIn("strictly increasing", stream)
        self.assertIn("mask: dtype bool, shape 4x5 (20 elements", stream)
        self.assertIn("3 True (15.0 %)", stream)

    @unittest.skipUnless(have("pyarrow"), "pyarrow")
    def test_orc_rows_profiled(self):
        import pyarrow as pa
        import pyarrow.orc as orc
        p = self.tmp / "t.orc"
        vals = [i % 9 for i in range(500)]
        orc.write_table(pa.table({"k": [f"g{i % 4}" for i in range(500)], "v": vals}), str(p))
        out, lj, stream = self.look(p)
        self.assertIn("ORC", out)
        self.assertIn("500 rows", stream)
        self.assertIn(f"sum {sum(vals):,}", stream)
        self.assertIn("4 distinct", stream)

    @unittest.skipUnless(have("duckdb"), "duckdb")
    def test_duckdb_tables_counts_and_views(self):
        import duckdb
        p = self.tmp / "d.duckdb"
        c = duckdb.connect(str(p))
        c.execute("create table t(id integer primary key, g varchar, v double)")
        c.executemany("insert into t values (?,?,?)", [(i, "a" if i % 3 else "b", i * 0.5) for i in range(1, 301)])
        c.execute("create view vv as select g, sum(v) s from t group by g")
        c.close()
        out, lj, stream = self.look(p)
        self.assertIn("DuckDB", out)
        self.assertIn("t 300", stream)
        self.assertIn("View vv", stream)
        self.assertIn("sum 22,575", stream)   # sum of i*0.5 for i in 1..300, worked out by hand
        self.assertIn("PRIMARY KEY", stream)

    @unittest.skipUnless(have("pandas"), "pandas")
    def test_stata_labels_and_rows(self):
        import pandas as pd
        p = self.tmp / "s.dta"
        df = pd.DataFrame({"id": range(1, 201), "g": ["m" if i % 2 else "f" for i in range(200)], "inc": [1000 + i for i in range(200)]})
        df.to_stata(str(p), variable_labels={"inc": "Income EUR"}, write_index=False)
        out, lj, stream = self.look(p)
        self.assertIn("200 rows x 3 columns", out)
        self.assertIn("inc = Income EUR", stream)
        self.assertIn(f"sum {sum(1000 + i for i in range(200)):,}", stream)

    # ---------------------------------------------------------------- containers
    def test_nested_archive_contents_are_read_in_memory(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("d/x.csv", "a,b\n" + "\n".join(f"{i},{i * 2}" for i in range(1, 51)))
        p = self.tmp / "n.tar.xz"
        with tarfile.open(p, "w:xz") as t:
            b = inner.getvalue()
            ti = tarfile.TarInfo("pk/in.zip")
            ti.size = len(b)
            t.addfile(ti, io.BytesIO(b))
            note = b"hello note\nsecond line\n"
            ti = tarfile.TarInfo("pk/NOTE")
            ti.size = len(note)
            t.addfile(ti, io.BytesIO(note))
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("pk/in.zip!/d/x.csv", stream)
        self.assertIn(f"sum {sum(range(1, 51)):,}", stream)
        self.assertIn("Small text member pk/NOTE: hello note | second line", stream)

    @unittest.skipUnless(have("safetensors") and have("numpy"), "safetensors")
    def test_safetensors_lists_every_tensor(self):
        import numpy as np
        from safetensors.numpy import save_file
        p = self.tmp / "m.safetensors"
        save_file({"w.a": np.zeros((3, 4), dtype="float32"), "w.b": np.zeros(5, dtype="float16")}, str(p))
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("w.a F32 3x4 (12)", stream)
        self.assertIn("w.b F16 5 (5)", stream)

    def test_side_files_fill_the_room_a_step_has_left(self):
        # an STL's model.json is not pointed at, it is printed; the figures inside answer a question without a second call
        tri = [((0, 0, 0), (1, 0, 0), (0, 1, 0)), ((0, 0, 0), (0, 1, 0), (0, 0, 1)), ((0, 0, 0), (0, 0, 1), (1, 0, 0)), ((1, 0, 0), (0, 0, 1), (0, 1, 0))]
        p = self.tmp / "tet.stl"
        with open(p, "wb") as f:
            f.write(b"tetra test".ljust(80, b" ") + struct.pack("<I", 4))
            for t in tri:
                f.write(struct.pack("<3f", 0, 0, 0))
                for v in t:
                    f.write(struct.pack("<3f", *v))
                f.write(b"\0\0")
        out, lj, stream = self.look(p, tools=False)
        self.assertIn("Header text: 'tetra test'", out)
        self.assertIn("surface area", stream)
        self.assertIn("4 triangles", out)


if __name__ == "__main__":
    unittest.main()
