"""Fix round 8, part 3: pixel and signal facts (category 4) and picture headers, on files built here.
Every expected figure is worked out from the data the test wrote, never read back from the look.
"""
import importlib.util
import math
import shutil
import struct
import sys
import unittest
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS  # noqa: E402
from test_v2_r8 import R8Base  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import dl_sig  # noqa: E402

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
BURSTS = [0.5, 1.7, 3.0, 4.4, 6.0]


def tone_samples(sr=8000, secs=7.0, bursts=BURSTS, length=0.2, freq=1000):
    a = [0] * int(secs * sr)
    for t in bursts:
        for k in range(int(length * sr)):
            a[int(t * sr) + k] = int(12000 * math.sin(2 * math.pi * freq * k / sr))
    return a


class Stub:
    """Just enough of a Look for dl_sig."""
    def __init__(self, numpy=False):
        self.lines, self.facts, self._np = [], {}, numpy

    def mod(self, name):
        if self._np and name == "numpy":
            import numpy
            return numpy
        return None

    def line(self, text, pri=50, tag=""):
        self.lines.append(text)

    def fact(self, k, v):
        self.facts[k] = v

    def skip(self, *a, **k):
        self.lines.append("SKIP " + " ".join(map(str, a)))


class Sound(R8Base):
    def test_au_bursts_counted_and_timed(self):
        a = tone_samples()
        p = self.tmp / "radio.au"
        p.write_bytes(b".snd" + struct.pack(">5I", 24, len(a) * 2, 3, 8000, 1) + b"".join(struct.pack(">h", v) for v in a))
        out, _, lj, _ = self.look(p)
        self.assertEqual(lj["type"], "audio")
        self.assertIn("Sun/NeXT .au header", out)
        self.assertIn("5 bursts", out)
        self.assertIn("the last ends at 0:06.20", out)
        self.assertIn("first starts at 0:00.50", out)
        self.assertIn("#5 6.00-6.20 s", out)
        self.assertIn("sound bursts 5", out)

    def test_wav_bursts_without_ffmpeg(self):
        p = self.tmp / "beeps.wav"
        w = wave.open(str(p), "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", v) for v in tone_samples()))
        w.close()
        out, _, _, _ = self.look(p)
        self.assertIn("5 bursts", out)
        self.assertIn("the last ends at 0:06.20", out)

    def test_speech_like_continuous_sound_is_one_burst(self):
        sr = 8000
        a = [int(9000 * math.sin(2 * math.pi * 220 * k / sr)) for k in range(3 * sr)]
        st = Stub()
        dl_sig.sound_events(st, a, sr)
        self.assertTrue(any("1 bursts" in x for x in st.lines), st.lines)

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_strongest_frequency_of_each_burst(self):
        import numpy as np
        x = np.array(tone_samples(freq=1000), dtype=np.float32) / 32768.0
        st = Stub(numpy=True)
        dl_sig.sound_events(st, x, 8000)
        text = " ".join(st.lines)
        self.assertIn("5 bursts", text)
        self.assertIn("1000 Hz x5", text)

    def test_silence_says_so(self):
        st = Stub()
        dl_sig.sound_events(st, [0] * 16000, 8000)
        self.assertTrue(any("digital silence" in x for x in st.lines), st.lines)


class Pictures(R8Base):
    def bmp(self, w=64, h=48):
        pal = [(i, 255 - i, (i * 7) % 256) for i in range(256)]
        rows = [bytes(((x + y) % 90) for x in range(w)) for y in range(h)]
        pix = b"".join(rows[::-1])    # bottom-up
        hdr = b"BM" + struct.pack("<IHHI", 14 + 40 + 1024 + len(pix), 0, 0, 14 + 40 + 1024)
        hdr += struct.pack("<IiiHHIIiiII", 40, w, h, 1, 8, 0, len(pix), 2835, 2835, 256, 256)
        p = self.tmp / "scan.bmp"
        p.write_bytes(hdr + b"".join(bytes([b, g, r, 0]) for r, g, b in pal) + pix)
        distinct = len({(x + y) % 90 for y in range(h) for x in range(w)})
        return p, pal, rows, distinct

    def test_bmp_header_and_exact_pixels(self):
        p, pal, rows, distinct = self.bmp()
        out, _, _, _ = self.look(p)
        self.assertIn(f"{distinct} distinct colours", out)
        self.assertIn("8 bits per pixel", out)
        self.assertIn("256 colours in the palette", out)
        r, g, b = pal[rows[0][0]]
        self.assertIn(f"(0,0) #{r:02x}{g:02x}{b:02x}", out, "the top-left pixel of a bottom-up bitmap")
        y = 47
        r, g, b = pal[rows[y][63]]
        self.assertIn(f"(63,47) #{r:02x}{g:02x}{b:02x}", out)

    def pcx(self, w=40, h=30):
        def rle(row):
            out, i = bytearray(), 0
            while i < len(row):
                c, n = row[i], 1
                while i + n < len(row) and row[i + n] == c and n < 63:
                    n += 1
                if n > 1 or c >= 0xC0:
                    out += bytes([0xC0 | n, c])
                else:
                    out.append(c)
                i += n
            return bytes(out)
        rows = [bytes(((x // 4 + y // 3) % 25) for x in range(w)) for y in range(h)]
        pal = [(i, 255 - i, i // 2) for i in range(256)]
        head = struct.pack("<BBBBHHHHHH", 10, 5, 1, 8, 0, 0, w - 1, h - 1, 72, 72) + bytes(48) + bytes([0, 1]) + struct.pack("<HHHH", w + (w & 1), 1, 0, 0) + bytes(54)
        p = self.tmp / "gate.pcx"
        p.write_bytes(head + b"".join(rle(r) for r in rows) + b"\x0c" + bytes(sum(([r, g, b] for r, g, b in pal), [])))
        return p, pal, rows

    def test_pcx_is_recognised_and_decoded(self):
        p, pal, rows = self.pcx()
        out, _, lj, _ = self.look(p)
        self.assertEqual(lj["type"], "image")
        self.assertIn("PCX", out)
        self.assertIn("40x30", out)
        self.assertIn("1 colour plane", out)
        self.assertIn("8 bits per pixel", out)
        self.assertIn("256-colour palette", out)
        distinct = len({v for r in rows for v in r})
        self.assertIn(f"{distinct} distinct colours", out)
        r, g, b = pal[rows[29][39]]
        self.assertIn(f"(39,29) #{r:02x}{g:02x}{b:02x}", out)

    def test_pixel_facts_of_a_tiny_picture_list_every_pixel(self):
        st = Stub()
        rgb = bytes([10, 20, 30] * 3 + [255, 255, 255])
        dl_sig.pixel_facts(st, 2, 2, rgb)
        text = "\n".join(st.lines)
        self.assertIn("2 distinct colours", text)
        self.assertIn("0a141e 0a141e", text)
        self.assertIn("(1,1) #ffffff", text)


class TextAsBytes(R8Base):
    """A reader that leaves text as bytes (SAS without an encoding) must not turn every value into '<8 bytes>' (a wrong distinct count)."""

    def test_bytes_that_are_text_are_counted_as_text(self):
        import dl_data
        self.assertEqual(dl_data.plain(b"MEMBER_17  "), "MEMBER_17  ")
        self.assertEqual(dl_data.plain(bytes([0, 255, 1])), "<3 bytes>")

    @unittest.skipUnless(importlib.util.find_spec("pandas") is not None, "pandas not installed")
    def test_sas_reader_asks_for_the_encoding_and_counts_distinct_text(self):
        import pandas as pd
        import dl_tab2
        calls = []
        names = [f"T{i}".encode() for i in range(40)]

        def fake(path, **kw):
            calls.append(kw)
            return pd.DataFrame({"memname": [n if "encoding" not in kw else n.decode() for n in names * 3], "n": list(range(120))})
        orig = pd.read_sas
        pd.read_sas = fake
        st = Stub()
        st.need_mod = lambda *a, **k: True
        st.quick = False
        st.flag = lambda *a, **k: None
        st.fail = lambda *a, **k: None
        st.step = lambda *a, **k: None
        st.path = Path("x.sas7bdat")
        try:
            dl_tab2.look_sas7bdat(st)
        finally:
            pd.read_sas = orig
        self.assertEqual(calls[0].get("encoding"), "infer")
        self.assertTrue(any("40 distinct" in x for x in st.lines), st.lines[:6])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
class TransportStreamPrograms(R8Base):
    def test_service_name_in_programs_line(self):
        import subprocess
        p = self.tmp / "svc.ts"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x48:d=1", "-f", "lavfi", "-i", "sine=d=1",
                        "-shortest", "-c:v", "mpeg2video", "-c:a", "mp2", "-metadata", "service_name=Harbour Cam 3",
                        "-metadata", "service_provider=Port Authority", "-f", "mpegts", str(p)], check=True, timeout=60)
        out, _, _, _ = self.look(p, "--quick", tools=True)
        self.assertIn("Programs in the stream", out)
        self.assertIn("Harbour Cam 3", out)
        self.assertIn("Port Authority", out)
