"""Fix round 10, lane F2 (ticket 83, P0.14b.H9): the miss categories of held-out set 9 for SAS, xlsb, netCDF, BMP/PCX, Sun .au,
MPEG-TS and archives, on fixtures built here (none from a held-out set).

Categories: (1) a header field (the SAS dataset name); (2) the end of every table (the last row of each worksheet, hidden ones too, and of
a CSV inside a nested archive); (3) packed and text arrays (netCDF values unpacked with scale_factor and add_offset, char variables in full);
(4) pixel facts (every palette entry, where the frequent colours sit, a colour gradient); (5) signal events (tones: count, frequency, start
times; video key frames). Every fact must be in the first two prints (step 1 and the first --more). Every expected figure is worked out
here from the data this file wrote, never read back from the look.
"""
import array
import importlib.util
import io
import json
import math
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r8b import xlsb_bytes  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class R10Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r10f2_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look2(self, path, *extra, tools=False, ok=(0,)):
        """Step 1 and the first --more (tier b): -> (both prints, look.json)."""
        out = self.tmp / ("out_" + path.name)
        shutil.rmtree(out, ignore_errors=True)
        base = [str(path), "--out", str(out)] + ([] if tools else ["--no-tools"])
        a = run(base + ["--fresh", *extra])
        self.assertIn(a.returncode, ok, a.stderr[-1500:] + a.stdout[-800:])
        b = run(base + ["--more"])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return a.stdout + "\n" + b.stdout, lj

    def no_crash(self, lj):
        kinds = {f["kind"] for f in lj.get("flags", [])}
        self.assertNotIn("INTERNAL-ERROR", kinds, lj.get("flags"))
        return kinds


def mutants(data, n, seed):
    """n damaged copies of `data`: cut short, bytes flipped, a block zeroed."""
    rnd = random.Random(seed)
    out = []
    for k in range(n):
        b = bytearray(data)
        kind = k % 3
        if kind == 0:
            b = b[:rnd.randrange(8, max(9, len(b)))]
        elif kind == 1:
            for _ in range(rnd.randrange(1, 40)):
                b[rnd.randrange(len(b))] = rnd.randrange(256)
        else:
            at = rnd.randrange(len(b))
            b[at:at + rnd.randrange(4, 512)] = bytes(min(len(b) - at, 512))
        out.append(bytes(b))
    return out


# ------------------------------------------------------------------ SAS: the file header
def sas_header(name, ftype=b"DATA", release=b"9.0401M7", host=b"W32_7PRO", created=1_900_000_000.0, page=4096, pages=0):
    """A sas7bdat header (32-bit layout, little-endian) and no data pages: what a cut-off download looks like."""
    h = bytearray(page)
    h[12:32] = bytes.fromhex("c2ea8160b31411cfbd92080009c7318c181f1011")
    h[32], h[35], h[37], h[39] = 0x22, 0x33, 0x01, ord("2")
    h[70] = 20                                        # utf-8
    h[84:92] = b"SAS FILE"
    h[92:156] = name.ljust(64)
    h[156:164] = ftype.ljust(8)
    struct.pack_into("<dd", h, 168, created, created + 3600)
    struct.pack_into("<iii", h, 200, page, page, pages)
    h[220:228] = release.ljust(8)
    h[228:244] = host.ljust(16, b"\0")
    return bytes(h)


class SasHeader(R10Base):
    def test_dataset_name_and_header_fields_even_without_rows(self):
        p = self.tmp / "cut.sas7bdat"
        p.write_bytes(sas_header(b"HARBOUR_TOLLS_R10"))
        out, lj = self.look2(p, ok=(0, 1))
        self.no_crash(lj)
        self.assertIn("dataset name 'HARBOUR_TOLLS_R10'", out)
        self.assertIn("type DATA", out)
        self.assertIn("SAS release 9.0401M7", out)
        self.assertIn("host W32_7PRO", out)
        self.assertIn("created 2020-03-16 17:46:40", out, "1.9e9 seconds after 1960-01-01")

    def test_damaged_headers_never_crash(self):
        for k, b in enumerate(mutants(sas_header(b"FUZZ_ME"), 9, 10)):
            p = self.tmp / f"fz{k}.sas7bdat"
            p.write_bytes(b)
            _, lj = self.look2(p, ok=(0, 1))
            self.no_crash(lj)


# ------------------------------------------------------------------ xlsb: the last row of every worksheet, hidden ones too
class SheetEnds(R10Base):
    def test_last_row_of_each_sheet_is_in_the_first_two_prints(self):
        sales = [["region", "units", "price"]] + [[["north", "south", "east"][i % 3], i * 3, round(10 + i * 0.37, 2)] for i in range(1, 121)]
        stage = [["batch", "delta"]] + [[f"B-{900 + i}", (i * 7) % 23 - 11] for i in range(1, 46)]
        strings = sorted({v for rows in (sales, stage) for r in rows for v in r if isinstance(v, str)})
        p = self.tmp / "ends.xlsb"
        rk = [[[v & 0x3FFFFFFF if isinstance(v, int) and v < 0 else v for v in r] for r in rows] for rows in (sales, stage)]   # a negative RK integer
        p.write_bytes(xlsb_bytes([("Sales", 0, rk[0]), ("Stage", 1, rk[1])], strings))
        out, lj = self.look2(p)
        self.no_crash(lj)
        last = sales[-1]
        self.assertIn(f"Sales: Last row (row {len(sales)}; {len(sales) - 1} in all): region={last[0]}; units={last[1]}; price={last[2]}", out)
        last = stage[-1]
        self.assertIn(f"Stage: Last row (row {len(stage)}; {len(stage) - 1} in all): batch={last[0]}; delta={last[1]}", out)


# ------------------------------------------------------------------ netCDF: packed values unpacked, char variables in full
NC = {2: ("c", 1), 3: (">h", 2), 4: (">i", 4), 5: (">f", 4), 6: (">d", 8)}


def _p4(b):
    return b + b"\0" * (-len(b) % 4)


def _name(s):
    return struct.pack(">I", len(s)) + _p4(s.encode())


def _attrs(atts):
    """atts: [(name, value)]; str -> char, float -> double, (code, [values]) -> that type."""
    if not atts:
        return struct.pack(">II", 0, 0)
    out = struct.pack(">II", 12, len(atts))
    for k, v in atts:
        if isinstance(v, str):
            out += _name(k) + struct.pack(">II", 2, len(v)) + _p4(v.encode())
        elif isinstance(v, float):
            out += _name(k) + struct.pack(">IId", 6, 1, v)
        else:
            code, vals = v
            out += _name(k) + struct.pack(">II", code, len(vals)) + _p4(b"".join(struct.pack(NC[code][0], x) for x in vals))
    return out


def nc_file(dims, gatts, variables, numrecs):
    """A CDF-1 file. dims [(name, size)], size 0 = unlimited (first dim of a record variable); variables [(name, dimids, code, atts, payload bytes)].
    A record variable's payload is all its records one after the other (each record a multiple of 4 bytes)."""
    rec = next((i for i, (_, s) in enumerate(dims) if s == 0), None)

    def header(begins):
        h = b"CDF\x01" + struct.pack(">I", numrecs)
        h += struct.pack(">II", 10, len(dims)) + b"".join(_name(n) + struct.pack(">I", s) for n, s in dims)
        h += _attrs(gatts) + struct.pack(">II", 11, len(variables))
        for (name, ids, code, atts, _), (vsize, begin) in zip(variables, begins):
            h += _name(name) + struct.pack(">I", len(ids)) + b"".join(struct.pack(">I", d) for d in ids) + _attrs(atts) + struct.pack(">III", code, vsize, begin)
        return h
    hl = len(header([(0, 0)] * len(variables)))
    begins, data = [None] * len(variables), b""
    for i, (name, ids, code, atts, payload) in enumerate(variables):
        if not (ids and ids[0] == rec):
            blob = _p4(payload)
            begins[i] = (len(blob), hl + len(data))
            data += blob
    recs = [i for i, v in enumerate(variables) if v[1] and v[1][0] == rec]
    sizes = {i: len(variables[i][4]) // max(numrecs, 1) for i in recs}
    first, off = hl + len(data), 0
    for i in recs:
        begins[i] = (sizes[i], first + off)
        off += sizes[i]
    for r in range(numrecs):
        for i in recs:
            data += variables[i][4][r * sizes[i]:(r + 1) * sizes[i]]
    return header(begins) + data


STATIONS = ["Alpha Point", "Bravo Bay", "Charlie Cove", "Delta Dunes", "Echo Spit"]


def raw_hs(t, i, j):
    return -32767 if (i, j) == (0, 0) else (t * 37 + i * 11 + j * 7) % 500 - 250


def wave_nc():
    nt, ny, nx, ns, nl = 6, 12, 20, len(STATIONS), 12
    hs = b"".join(struct.pack(">h", raw_hs(t, i, j)) for t in range(nt) for i in range(ny) for j in range(nx))
    names = b"".join(s.encode().ljust(nl) for s in STATIONS)
    return nc_file([("time", 0), ("lat", ny), ("lon", nx), ("station", ns), ("namelen", nl)], [("title", "r10 packed grid")],
                   [("time", [0], 4, [("units", "hours since 2025-01-01")], b"".join(struct.pack(">i", 6 * t) for t in range(nt))),
                    ("lat", [1], 6, [("units", "degrees_north")], b"".join(struct.pack(">d", 40 + 0.5 * i) for i in range(ny))),
                    ("lon", [2], 6, [("units", "degrees_east")], b"".join(struct.pack(">d", -5 + 0.25 * j) for j in range(nx))),
                    ("station_name", [3, 4], 2, [("long_name", "station name")], names),
                    ("hs", [0, 1, 2], 3, [("units", "m"), ("scale_factor", 0.01), ("add_offset", 2.5), ("_FillValue", (3, [-32767]))], hs)], nt)


class NetcdfArrays(R10Base):
    def test_char_variable_entries_in_full(self):
        p = self.tmp / "waves.nc"
        p.write_bytes(wave_nc())
        out, lj = self.look2(p)
        self.no_crash(lj)
        for k, s in enumerate(STATIONS, 1):
            self.assertIn(f"{k} '{s}'", out)

    def test_packed_variable_unpacked_and_the_last_slice_on_a_grid(self):
        p = self.tmp / "waves.nc"
        p.write_bytes(wave_nc())
        out, lj = self.look2(p)
        vals = [raw_hs(t, i, j) for t in range(6) for i in range(12) for j in range(20) if (i, j) != (0, 0)]
        self.assertIn("unpacked (value x scale_factor + add_offset)", out)
        self.assertIn(f"min {min(vals) * 0.01 + 2.5:.4g}", out)
        self.assertIn(f"max {max(vals) * 0.01 + 2.5:.4g}", out)
        self.assertIn("hs at time index 5 (the last)", out)
        row = next((ln for ln in out.splitlines() if ln.startswith("lat[10] ")), None)
        self.assertIsNotNone(row, "a grid row for lat index 10")
        cells = row.split(": ", 1)[1].split()
        cols = list(range(0, 20, 2)) + [19]
        self.assertEqual(len(cells), len(cols))
        self.assertEqual(float(cells[cols.index(14)]), round(raw_hs(5, 10, 14) * 0.01 + 2.5, 4))
        row0 = next(ln for ln in out.splitlines() if ln.startswith("lat[0] "))
        self.assertEqual(row0.split(": ", 1)[1].split()[0], "fill", "a fill value is named, never unpacked")

    def test_damaged_files_never_crash(self):
        for k, b in enumerate(mutants(wave_nc(), 9, 11)):
            p = self.tmp / f"fz{k}.nc"
            p.write_bytes(b)
            _, lj = self.look2(p, ok=(0, 1))
            self.no_crash(lj)


# ------------------------------------------------------------------ pictures: palette, where colours sit, gradients
def pcx_file(w, h, pix, pal):
    def rle(row):
        out, i = bytearray(), 0
        while i < len(row):
            c, n = row[i], 1
            while i + n < len(row) and row[i + n] == c and n < 63:
                n += 1
            out += bytes([0xC0 | n, c]) if n > 1 or c >= 0xC0 else bytes([c])
            i += n
        return bytes(out)
    head = struct.pack("<BBBBHHHHHH", 10, 5, 1, 8, 0, 0, w - 1, h - 1, 96, 96) + bytes(48) + bytes([0, 1]) + struct.pack("<HHHH", w + (w & 1), 1, 0, 0) + bytes(54)
    rows = [bytes(pix[y * w:(y + 1) * w]) + (b"\0" if w & 1 else b"") for y in range(h)]
    return head + b"".join(rle(r) for r in rows) + b"\x0c" + bytes(v for rgb in pal for v in rgb)


def stamp():
    w, h = 160, 120
    pal = [((i * 53) % 256, (i * 101 + 7) % 256, (i * 29 + 200) % 256) for i in range(256)]
    pix = [(x // 8 + y // 8) % 40 + 10 for y in range(h) for x in range(w)]       # a small checker of 40 colours
    for y in range(20, 61):
        for x in range(30, 91):
            pix[y * w + x] = 211                                                   # one solid block
    return w, h, pix, pal


def bmp24(w, h, px):
    pad = (-3 * w) % 4
    body = b"".join(b"".join(bytes([b, g, r]) for r, g, b in px[y * w:(y + 1) * w]) + bytes(pad) for y in range(h - 1, -1, -1))
    head = b"BM" + struct.pack("<IHHI", 54 + len(body), 0, 0, 54) + struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(body), 3780, 3780, 0, 0)
    return head + body


def gradient(w=300, h=200):
    px = []
    for y in range(h):
        for x in range(w):
            if 40 <= x < 120 and 50 <= y < 100:
                px.append((200, 30, 30))
            else:
                px.append((x * 255 // (w - 1), y * 255 // (h - 1), 77))
    return px


@unittest.skipUnless(HAVE_NUMPY and HAVE_PIL, "numpy and Pillow")
class PicturesR10(R10Base):
    def test_every_palette_entry_and_the_solid_block(self):
        w, h, pix, pal = stamp()
        p = self.tmp / "stamp.pcx"
        p.write_bytes(pcx_file(w, h, pix, pal))
        out, lj = self.look2(p)
        self.no_crash(lj)
        for i in (0, 100, 211, 255):
            r, g, b = pal[i]
            self.assertIn(f"{i}={r:02x}{g:02x}{b:02x}", out, f"palette entry {i}")
        r, g, b = pal[211]
        self.assertIn(f"#{r:02x}{g:02x}{b:02x} x 30-90, y 20-60 (100 %)", out, "the block of the most frequent colour")

    def test_a_gradient_is_named_with_its_formula(self):
        p = self.tmp / "grad.bmp"
        p.write_bytes(bmp24(300, 200, gradient()))
        out, lj = self.look2(p)
        self.no_crash(lj)
        line = next((ln for ln in out.splitlines() if "gradient" in ln.lower()), "")
        self.assertIn("R = 255·x/299", line)
        self.assertIn("G = 255·y/199", line)
        self.assertIn("B = 77", line)
        self.assertIn("rounded down", line)
        self.assertIn("#c81e1e x 40-119, y 50-99 (100 %)", out)

    def test_noise_has_no_gradient(self):
        rnd = random.Random(5)
        p = self.tmp / "noise.bmp"
        p.write_bytes(bmp24(120, 90, [(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(120 * 90)]))
        out, lj = self.look2(p)
        self.no_crash(lj)
        self.assertNotIn("gradient", out.lower())

    def test_damaged_pictures_never_crash(self):
        w, h, pix, pal = stamp()
        for k, b in enumerate(mutants(pcx_file(w, h, pix, pal), 6, 12) + mutants(bmp24(60, 40, gradient(60, 40)), 6, 13)):
            p = self.tmp / (f"fz{k}.pcx" if k < 6 else f"fz{k}.bmp")
            p.write_bytes(b)
            _, lj = self.look2(p, ok=(0, 1))
            self.no_crash(lj)


# ------------------------------------------------------------------ sound: tone events over a noisy floor with a steady hum
ALARMS = [2.0, 7.35, 13.1, 20.45, 27.8]
CALIB = [5.0, 17.0]


def tone_au(path, sr=16000, secs=30.0):
    rnd = random.Random(3)
    n = int(secs * sr)
    x = [0.05 * (rnd.random() * 2 - 1) + 0.05 * math.sin(2 * math.pi * 50 * k / sr) for k in range(n)]
    for t0, f, ln in [(t, 1500, 0.3) for t in ALARMS] + [(t, 600, 1.0) for t in CALIB]:
        a = int(round(t0 * sr))
        for k in range(int(ln * sr)):
            x[a + k] += 0.4 * math.sin(2 * math.pi * f * k / sr)
    a = array.array("h", (max(-32767, min(32767, int(v * 32767))) for v in x))
    if sys.byteorder == "little":
        a.byteswap()
    path.write_bytes(struct.pack(">4sIIIII", b".snd", 24, len(a) * 2, 3, sr, 1) + a.tobytes())


@unittest.skipUnless(HAVE_NUMPY, "numpy")
class Tones(R10Base):
    def test_tone_events_counted_timed_and_grouped_by_frequency(self):
        """numpy is off under --no-tools, so the .au samples go through the reader and the burst pass directly (as the look does with tools)."""
        import numpy as np
        import dl_ctr
        import dl_sig
        from test_v2_r8c import Stub
        p = self.tmp / "hall.au"
        tone_au(p)
        c = dl_ctr.au_counts(p)
        chans, _ = dl_ctr.au_channels(p, c, np=np)
        st = Stub(numpy=True)
        dl_sig.sound_events(st, chans[0].astype(np.float32) / 32768.0, c["rate"])
        out = "\n".join(st.lines)
        self.assertIn(f"1500 Hz: {len(ALARMS)} tones", out)
        self.assertIn(f"600 Hz: {len(CALIB)} tones", out)
        self.assertIn("starts " + ", ".join(f"{t:.2f}" for t in ALARMS) + " s", out)
        self.assertIn(f"the last at {ALARMS[-1]:.2f} s", out)
        self.assertIn("each 1.00 s", out)

    def test_speech_like_and_silent_files_name_no_tones(self):
        import numpy as np
        import dl_sig
        from test_v2_r8c import Stub
        rnd = np.random.default_rng(4)
        sr = 8000
        st = Stub(numpy=True)
        dl_sig.tone_events(st, (rnd.standard_normal(sr * 10) * 0.1).astype(np.float32), sr)
        dl_sig.tone_events(st, np.zeros(sr * 5, dtype=np.float32), sr)
        t = np.arange(sr * 6) / sr                                         # a gliding pitch: no single frequency holds
        dl_sig.tone_events(st, (0.3 * np.sin(2 * np.pi * (200 + 300 * t) * t)).astype(np.float32), sr)
        self.assertFalse([x for x in st.lines if "Tones" in x], st.lines)


# ------------------------------------------------------------------ video: key frames
@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
class KeyFrames(R10Base):
    def test_key_frame_count_and_last_time(self):
        p = self.tmp / "gop.ts"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=64x48:r=25:d=4", "-c:v", "mpeg2video", "-g", "25", "-bf", "0",
                        "-sc_threshold", "1000000000", "-f", "mpegts", str(p)], check=True, timeout=60)
        out, lj = self.look2(p, "--quick", tools=True)
        self.no_crash(lj)
        self.assertIn("4 key frames", out)
        self.assertIn("3.000 s after the stream start", out, "the last key frame, frames 0, 25, 50, 75 at 25 fps")
        self.assertIn("one every 1.000 s", out)


# ------------------------------------------------------------------ archives: the first and last row of a CSV in a nested archive
class NestedTable(R10Base):
    def test_first_and_last_row_of_a_nested_csv(self):
        rows = [("g%02d" % (i % 9), f"2025-08-{1 + i % 28:02d}", (i * 13) % 301 - 150) for i in range(1, 401)]
        csv_text = "gauge,day,level\n" + "".join(f"{a},{b},{c}\n" for a, b, c in rows)
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("levels.csv", csv_text)
            z.writestr("note.txt", "r10 nested\n")
        p = self.tmp / "bundle.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("readme.txt", "bundle\n")
            z.writestr("q3.zip", inner.getvalue())
        out, lj = self.look2(p)
        self.no_crash(lj)
        a, b, c = rows[-1]
        self.assertIn(f"Last row (line {len(rows) + 1}; {len(rows)} in all): gauge={a}; day={b}; level={c}", out)
        a, b, c = rows[0]
        self.assertIn(f"First row (line 2): gauge={a}; day={b}; level={c}", out)


# ------------------------------------------------------------------ review findings (code-review pass of this lane)
class ReviewFixesR10(R10Base):
    @unittest.skipUnless(HAVE_NUMPY, "numpy")
    def test_close_tones_stay_apart_and_one_tone_is_singular(self):
        import numpy as np
        import dl_sig
        from test_v2_r8c import Stub
        sr = 8000
        x = (np.random.default_rng(1).standard_normal(sr * 8) * 0.01).astype(np.float32)
        t = np.arange(int(0.4 * sr)) / sr
        for t0, f in ((1.0, 1000), (4.0, 1015)):
            x[int(t0 * sr):int(t0 * sr) + len(t)] += (0.5 * np.sin(2 * np.pi * f * t)).astype(np.float32)
        st = Stub(numpy=True)
        dl_sig.tone_events(st, x, sr)
        text = "\n".join(st.lines)
        self.assertIn("1000 Hz: 1 tone,", text)
        self.assertIn("1015 Hz: 1 tone,", text)
        self.assertIn("2 tones at 2 frequencies", text)

    def test_lone_record_variable_is_read_without_padding(self):
        """Three records of three shorts: the file stores 6 bytes per record, though the header's vsize says 8."""
        data = bytearray(nc_file([("time", 0), ("x", 3)], [], [("v", [0, 1], 3, [], b"".join(struct.pack(">h", k) for k in range(1, 10)))], 3))
        at = data.index(b"\0\0\0\x03\0\0\0\x06")         # the type (short) and vsize of v
        data[at + 4:at + 8] = struct.pack(">I", 8)
        p = self.tmp / "lone.nc"
        p.write_bytes(bytes(data))
        out, lj = self.look2(p)
        self.no_crash(lj)
        self.assertIn("time[1]: 4 5 6", out)
        self.assertIn("time[2]: 7 8 9", out)

    def test_streaming_record_count_and_long_text_do_not_hang_or_lie(self):
        body = nc_file([("rec", 0), ("w", 8)], [], [("tag", [0, 1], 2, [], b"abcdefgh" * 4)], 4)
        data = bytearray(body)
        data[4:8] = b"\xff\xff\xff\xff"                     # numrecs: streaming
        p = self.tmp / "stream.nc"
        p.write_bytes(bytes(data))
        _, lj = self.look2(p, ok=(0, 1))
        self.no_crash(lj)
        p = self.tmp / "note.nc"
        p.write_bytes(nc_file([("n", 1600)], [], [("note", [0], 2, [], b"abc " * 400)], 0))
        out, lj = self.look2(p)
        self.assertIn(f"{len(('abc ' * 400).rstrip()):,} characters of text, in the next fact", out)
        self.assertIn("text: abc abc", out)
        self.assertNotIn("text: ,", out)


if __name__ == "__main__":
    unittest.main()
