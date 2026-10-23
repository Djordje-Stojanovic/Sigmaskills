"""Fix round 11, lane F2 (ticket 83, P0.14b.H5): the pixel and signal probes of held-out set 10, on fixtures built here (none from a held-out set).

Families: (1) one pixel of a still picture by `--ask "pixel x,y"` (BMP, PCX, PNG, GIF, TGA, TIFF, WebP; bottom-up rows, palettes, RLE, 24-bit
planes) and the print line that says where to ask; (2) tone events per channel of a stereo or multi-channel recording, short pips included;
(3) the stream table of a container with several streams (PID or track id, type, codec, language, bit rate) and a tone summary for every audio
stream, from ffprobe when present and from the PAT/PMT tables of a transport stream read in pure Python when not.
Every expected figure is worked out here from the data this file wrote, never read back from the look.
"""
import array
import importlib.util
import json
import math
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r10_f2 import R10Base, mutants  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
HAVE_PIL = importlib.util.find_spec("PIL") is not None
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class Base(R10Base):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r11f2_"))

    def ask(self, path, question, *, tools=False, ok=(0,)):
        out = self.tmp / ("out_" + path.name + ("_t" if tools else ""))
        args = [str(path), "--out", str(out), "--ask", question] + ([] if tools else ["--no-tools"])
        r = run(args)
        self.assertIn(r.returncode, ok, r.stderr[-1500:] + r.stdout[-800:])
        self.assertNotIn("Traceback", r.stderr)
        return r.stdout


# ------------------------------------------------------------------ pictures
W, H = 60, 40


def rgb_at(x, y):
    return ((x * 7 + y * 3) % 256, (x * 13 + y * 11 + 5) % 256, (x * x + y * 5) % 256)


def palette(n=200, seed=4):
    rnd = random.Random(seed)
    return [(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(n)]


PAL = palette()


def idx_at(x, y):
    return (x * 5 + y * 3) % len(PAL)


def bmp24_bottom_up():
    pad = (-3 * W) % 4
    rows = [b"".join(bytes(rgb_at(x, y)[::-1]) for x in range(W)) + bytes(pad) for y in range(H - 1, -1, -1)]
    body = b"".join(rows)
    return b"BM" + struct.pack("<IHHI", 54 + len(body), 0, 0, 54) + struct.pack("<IiiHHIIiiII", 40, W, H, 1, 24, 0, len(body), 3780, 3780, 0, 0) + body


def bmp8(top_down, rle=False):
    table = b"".join(bytes((b, g, r, 0)) for r, g, b in PAL)
    order = range(H) if top_down else range(H - 1, -1, -1)
    if rle:
        out = bytearray()
        for y in order:
            x = 0
            while x < W:
                n = 1
                while x + n < W and idx_at(x + n, y) == idx_at(x, y) and n < 255:
                    n += 1
                out += bytes((n, idx_at(x, y)))
                x += n
            out += b"\0\0"
        body = bytes(out) + b"\0\1"
        comp = 1
    else:
        stride = (W + 3) // 4 * 4
        body = b"".join(bytes(idx_at(x, y) for x in range(W)) + bytes(stride - W) for y in order)
        comp = 0
    off = 54 + len(table)
    return (b"BM" + struct.pack("<IHHI", off + len(body), 0, 0, off) + struct.pack("<IiiHHIIiiII", 40, W, -H if top_down else H, 1, 8, comp, len(body), 3780, 3780, len(PAL), 0)
            + table + body)


def _rle(row):
    out, i = bytearray(), 0
    while i < len(row):
        c, n = row[i], 1
        while i + n < len(row) and row[i + n] == c and n < 63:
            n += 1
        out += bytes([0xC0 | n, c]) if n > 1 or c >= 0xC0 else bytes([c])
        i += n
    return bytes(out)


def pcx(planes24):
    bpl = W + (W & 1)
    head = struct.pack("<BBBBHHHHHH", 10, 5, 1, 8, 0, 0, W - 1, H - 1, 96, 96) + bytes(48) + bytes([0, 3 if planes24 else 1]) + struct.pack("<HHHH", bpl, 1, 0, 0) + bytes(54)
    body = bytearray()
    for y in range(H):
        if planes24:
            for c in range(3):
                body += _rle(bytes(rgb_at(x, y)[c] for x in range(W)) + bytes(bpl - W))
        else:
            body += _rle(bytes(idx_at(x, y) for x in range(W)) + bytes(bpl - W))
    tail = b"" if planes24 else b"\x0c" + bytes(v for rgb in PAL + [(0, 0, 0)] * (256 - len(PAL)) for v in rgb)
    return head + bytes(body) + tail


QUESTIONS = ["RGB colour at pixel x={x}, y={y}, counted from the top-left corner of the picture as displayed",
             "What is the colour at x={x} y={y}?", "pixel ({x}, {y})", "Give the RGB value of the pixel at {x},{y}", "colour of the pixel at column {x}, row {y}"]
SPOTS = [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1), (17, 23), (41, 5)]


class PixelAsk(Base):
    def check_rgb(self, path, fn, tools, *, index=None, spots=SPOTS):
        for x, y in spots:
            q = QUESTIONS[(x + y) % len(QUESTIONS)].format(x=x, y=y)
            out = self.ask(path, q, tools=tools)
            r, g, b = fn(x, y)
            self.assertIn(f"Answer: {r},{g},{b}", out, f"{path.name} {q}\n{out}")
            self.assertIn(f"#{r:02x}{g:02x}{b:02x}", out)
            if index:
                self.assertIn(f"palette index {index(x, y)}", out, out)

    def tool_modes(self):
        return (False, True) if HAVE_PIL else (False,)

    def test_bmp24_bottom_up_rows(self):
        p = self.tmp / "bu24.bmp"
        p.write_bytes(bmp24_bottom_up())
        for tools in self.tool_modes():
            self.check_rgb(p, rgb_at, tools)

    def test_bmp8_palette_bottom_up_and_top_down(self):
        for top_down in (False, True):
            p = self.tmp / f"pal8_{int(top_down)}.bmp"
            p.write_bytes(bmp8(top_down))
            for tools in self.tool_modes():
                self.check_rgb(p, lambda x, y: PAL[idx_at(x, y)], tools, index=idx_at)

    @unittest.skipUnless(HAVE_PIL, "Pillow")
    def test_bmp_rle8_through_pillow(self):
        p = self.tmp / "rle8.bmp"
        p.write_bytes(bmp8(False, rle=True))
        self.check_rgb(p, lambda x, y: PAL[idx_at(x, y)], True, index=idx_at)

    def test_pcx_palette_and_24_bit_planes(self):
        p = self.tmp / "pal.pcx"
        p.write_bytes(pcx(False))
        q = self.tmp / "true.pcx"
        q.write_bytes(pcx(True))
        for tools in self.tool_modes():
            self.check_rgb(p, lambda x, y: PAL[idx_at(x, y)], tools, index=idx_at)
            self.check_rgb(q, rgb_at, tools)

    @unittest.skipUnless(HAVE_PIL, "Pillow")
    def test_other_formats_through_pillow(self):
        from PIL import Image
        im = Image.new("RGB", (W, H))
        im.putdata([rgb_at(x, y) for y in range(H) for x in range(W)])
        for ext in ("png", "gif", "tga", "tiff", "webp"):
            p = self.tmp / f"pic.{ext}"
            if ext == "gif":
                pal = Image.new("P", (W, H))
                pal.putpalette([v for c in PAL for v in c])
                pal.putdata([idx_at(x, y) for y in range(H) for x in range(W)])
                pal.save(p)
                self.check_rgb(p, lambda x, y: PAL[idx_at(x, y)], True, index=idx_at)
                continue
            im.save(p, **({"lossless": True} if ext == "webp" else {}))
            self.check_rgb(p, rgb_at, True, spots=SPOTS[:3] + [(17, 23)])

    @unittest.skipUnless(HAVE_PIL, "Pillow")
    def test_alpha_and_exif_orientation(self):
        from PIL import Image
        im = Image.new("RGBA", (W, H), (1, 2, 3, 255))
        im.putpixel((5, 6), (10, 20, 30, 128))
        p = self.tmp / "alpha.png"
        im.save(p)
        out = self.ask(p, "colour at x=5 y=6", tools=True)
        self.assertIn("Answer: 10,20,30", out)
        self.assertIn("alpha 128", out)
        base = Image.new("RGB", (W, H), (0, 0, 0))
        base.putpixel((W - 1, 0), (200, 100, 50))        # top-right as stored
        ex = Image.Exif()
        ex[274] = 6                                      # displayed rotated 90 clockwise: stored top-right lands at bottom-right, size H x W
        j = self.tmp / "turned.jpg"
        base.save(j, quality=100, subsampling=0, exif=ex)
        out = self.ask(j, f"pixel x={H - 1} y={W - 1}", tools=True)
        self.assertRegex(out, r"Answer: (19\d|20\d),(9\d|10\d),(4\d|5\d|6\d)")
        self.assertIn(f"{H} x {W}", out)

    def test_out_of_range_answers_with_the_size(self):
        p = self.tmp / "small.bmp"
        p.write_bytes(bmp24_bottom_up())
        for tools in self.tool_modes():
            out = self.ask(p, "RGB colour at pixel x=900, y=5", tools=tools)
            self.assertNotRegex(out, r"Answer: \d+,\d+,\d+")
            self.assertIn(f"{W} x {H}", out)
            self.assertIn("outside", out)

    def test_print_says_where_to_ask(self):
        for name, data in (("w.bmp", bmp24_bottom_up()), ("w.pcx", pcx(False))):
            p = self.tmp / name
            p.write_bytes(data)
            for tools in self.tool_modes():
                out = self.tmp / ("print_" + name + str(tools))
                r = run([str(p), "--out", str(out), "--fresh"] + ([] if tools else ["--no-tools"]))
                self.assertEqual(r.returncode, 0, r.stderr[-800:])
                self.assertIn('Ask a pixel: --ask "pixel X,Y"', r.stdout)
                self.assertIn(f"image is {W} x {H}", r.stdout)

    def test_damaged_pictures_never_crash_the_ask(self):
        for k, b in enumerate(mutants(pcx(True), 6, 21) + mutants(bmp8(False), 6, 22) + mutants(bmp24_bottom_up(), 6, 23)):
            p = self.tmp / (f"fz{k}.pcx" if k < 6 else f"fz{k}.bmp")
            p.write_bytes(b)
            for tools in self.tool_modes():
                out = self.tmp / f"o_fz{k}{tools}"
                r = run([str(p), "--out", str(out), "--ask", "pixel x=3, y=4"] + ([] if tools else ["--no-tools"]))
                self.assertIn(r.returncode, (0, 1), r.stderr[-800:])
                self.assertNotIn("Traceback", r.stderr)
                if (out / "look.json").exists():
                    kinds = {f["kind"] for f in json.loads((out / "look.json").read_text(encoding="utf-8")).get("flags", [])}
                    self.assertNotIn("INTERNAL-ERROR", kinds)


# ------------------------------------------------------------------ sound: tone events per channel
SR = 16000
LEFT_PIPS = [(2.0, 0.2), (5.5, 0.2), (9.25, 0.2), (14.0, 0.2), (18.5, 0.04)]     # 1 kHz; the last is a 40 ms pip
RIGHT_BURSTS = [(4.0, 0.5), (11.0, 0.5), (16.0, 0.5)]                             # 3 kHz


def stereo(secs=22.0, left=LEFT_PIPS, right=RIGHT_BURSTS, fl=1000, fr=3000):
    import numpy as np
    rnd = np.random.default_rng(8)
    n = int(secs * SR)
    t = np.arange(n) / SR
    chans = [0.03 * np.sin(2 * np.pi * 50 * t) + rnd.normal(0, 0.02, n), 0.03 * np.sin(2 * np.pi * 60 * t) + rnd.normal(0, 0.02, n)]
    for ch, spec, f, amp in ((0, left, fl, 0.5), (1, right, fr, 0.55)):
        for t0, ln in spec:
            a, b = int(round(t0 * SR)), int(round((t0 + ln) * SR))
            chans[ch][a:b] += amp * np.sin(2 * np.pi * f * t[a:b])
    return chans


def au_bytes(chans, sr=SR):
    import numpy as np
    inter = np.empty(len(chans[0]) * len(chans), dtype=">i2")
    for k, c in enumerate(chans):
        inter[k::len(chans)] = np.round(np.clip(c, -1, 1) * 32767).astype(">i2")
    return b".snd" + struct.pack(">5I", 24, inter.nbytes, 3, sr, len(chans)) + inter.tobytes()


@unittest.skipUnless(HAVE_NUMPY, "numpy")
class ChannelTones(Base):
    def segments(self, text):
        a = text.index("LEFT (channel 1)")
        b = text.index("RIGHT (channel 2)")
        return text[a:b], text[b:]

    def test_each_channel_has_its_own_tone_events(self):
        import numpy as np
        import dl_sig
        from test_v2_r8c import Stub
        chans = [c.astype(np.float32) for c in stereo()]
        st = Stub(numpy=True)
        dl_sig.tone_events_channels(st, chans, SR)
        text = "\n".join(st.lines)
        left, right = self.segments(text)
        self.assertIn(f"1000 Hz: {len(LEFT_PIPS)} tones", left)
        self.assertNotIn("3000 Hz", left)
        self.assertIn("starts " + ", ".join(f"{t:.2f}" for t, _ in LEFT_PIPS) + " s", left)
        self.assertIn(f"the last at {LEFT_PIPS[-1][0]:.2f} s", left)
        self.assertIn(f"3000 Hz: {len(RIGHT_BURSTS)} tones", right)
        self.assertNotIn("1000 Hz", right)
        self.assertIn("starts " + ", ".join(f"{t:.2f}" for t, _ in RIGHT_BURSTS) + " s", right)
        self.assertIn("each 0.50 s", right)
        self.assertRegex(left, r"background -\d+(\.\d)? dBFS")
        self.assertRegex(right, r"background -\d+(\.\d)? dBFS")

    def test_a_silent_or_noise_only_channel_says_so(self):
        import numpy as np
        import dl_sig
        from test_v2_r8c import Stub
        a, b = stereo(right=[])
        st = Stub(numpy=True)
        dl_sig.tone_events_channels(st, [a.astype(np.float32), b.astype(np.float32)], SR)
        left, right = self.segments("\n".join(st.lines))
        self.assertIn("1000 Hz: 5 tones", left)
        self.assertIn("no tone", right)

    def test_voiced_speech_like_sound_and_a_glide_name_no_tones(self):
        """Short frames must not turn vowels (harmonics 100+ Hz apart, syllables 3.5 per second) or a gliding pitch into tones."""
        import numpy as np
        import dl_sig
        from test_v2_r8c import Stub
        n = SR * 20
        t = np.arange(n) / SR
        f0 = 120 + 30 * np.sin(2 * np.pi * 0.3 * t)
        ph = 2 * np.pi * np.cumsum(f0) / SR
        x = np.zeros(n)
        for h in range(1, 30):
            fh = h * f0
            x += (np.exp(-((fh - 700) / 300) ** 2) + 0.6 * np.exp(-((fh - 1200) / 300) ** 2) + 0.2 * np.exp(-((fh - 2500) / 500) ** 2)) / h ** 0.3 * np.sin(h * ph)
        x = x * (np.sin(2 * np.pi * 3.5 * t) > 0) * 0.1 + np.random.default_rng(1).normal(0, 0.003, n)
        glide = 0.3 * np.sin(2 * np.pi * (200 + 300 * t[:SR * 12]) * t[:SR * 12])
        glide = np.concatenate([glide, np.zeros(n - len(glide))])   # up to 7.4 kHz: below half the sample rate
        st = Stub(numpy=True)
        dl_sig.tone_events_channels(st, [x.astype(np.float32), glide.astype(np.float32)], SR)
        self.assertEqual([ln for ln in st.lines if "Tones" in ln], [])

    def test_mono_keeps_the_single_line(self):
        import numpy as np
        import dl_sig
        from test_v2_r8c import Stub
        a = stereo()[0].astype(np.float32)
        st = Stub(numpy=True)
        dl_sig.tone_events_channels(st, [a], SR)
        text = "\n".join(st.lines)
        self.assertIn(f"1000 Hz: {len(LEFT_PIPS)} tones", text)
        self.assertNotIn("channel 1", text)

    def test_au_look_prints_both_channels(self):
        p = self.tmp / "pump.au"
        p.write_bytes(au_bytes(stereo()))
        out, lj = self.look2(p, "--quick", tools=True)
        self.no_crash(lj)
        a = out.index("LEFT (channel 1)")
        left, right = out[a:out.index("RIGHT (channel 2)")], out[out.index("RIGHT (channel 2)"):]
        self.assertIn(f"1000 Hz: {len(LEFT_PIPS)} tones", left)
        self.assertIn(f"3000 Hz: {len(RIGHT_BURSTS)} tones", right)
        self.assertIn(f"the last at {RIGHT_BURSTS[-1][0]:.2f} s", right)

    def wav3(self):
        import wave
        chans = stereo()
        raw = array.array("h")
        for frame in zip(chans[0], chans[1], chans[0] * 0):
            raw.extend(int(max(-1, min(1, v)) * 32767) for v in frame)
        if sys.byteorder == "big":
            raw.byteswap()
        wav = self.tmp / "three.wav"
        w = wave.open(str(wav), "wb")
        w.setnchannels(3)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(raw.tobytes())
        w.close()
        return wav

    def check3(self, out):
        self.assertIn(f"1000 Hz: {len(LEFT_PIPS)} tones", out[out.index("LEFT (channel 1)"):out.index("RIGHT (channel 2)")])
        self.assertIn(f"3000 Hz: {len(RIGHT_BURSTS)} tones", out[out.index("RIGHT (channel 2)"):])
        self.assertRegex(out, r"channel 3[^.;]*no tone")

    def test_three_channel_wav_without_ffmpeg(self):
        wav = self.wav3()
        outd = self.tmp / "o_wav3"
        r = run([str(wav), "--out", str(outd), "--fresh"], env={"SIGMADEEPLOOK_HIDE": "ffmpeg"})
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.check3(r.stdout + run([str(wav), "--out", str(outd), "--more"]).stdout)

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
    def test_three_channel_wav_with_ffmpeg(self):
        wav = self.wav3()
        out, lj = self.look2(wav, tools=True, ok=(0, 1))
        self.no_crash(lj)
        self.check3(out)

    def test_damaged_stereo_files_never_crash(self):
        data = au_bytes(stereo(secs=8.0, left=[(1.0, 0.2)], right=[(3.0, 0.5)]))
        for k, b in enumerate(mutants(data, 6, 31)):
            p = self.tmp / f"fz{k}.au"
            p.write_bytes(b)
            _, lj = self.look2(p, "--quick", tools=True, ok=(0, 1))
            self.no_crash(lj)


# ------------------------------------------------------------------ containers with several streams
def _crc(b):
    crc = 0xFFFFFFFF
    for byte in b:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return struct.pack(">I", crc)


def _ts_packet(pid, payload, cc=0):
    head = bytes((0x47, 0x40 | (pid >> 8), pid & 0xFF, 0x10 | (cc & 15)))
    return head + (b"\0" + payload).ljust(184, b"\xff")


def _section(table_id, ident, body):
    sec = struct.pack(">BHHBBB", table_id, 0xB000 | (len(body) + 9), ident, 0xC1, 0, 0) + body
    return sec + _crc(sec)


def hand_ts(streams, pmt_pid=4096, pcr=512, program=1, extra=200):
    """A transport stream with a PAT, a PMT and null packets. streams: [(stream_type, pid, descriptor bytes)]."""
    pat = _section(0, 7, struct.pack(">HH", program, 0xE000 | pmt_pid))
    es = b"".join(struct.pack(">BHH", t, 0xE000 | pid, 0xF000 | len(d)) + d for t, pid, d in streams)
    pmt = _section(2, program, struct.pack(">HH", 0xE000 | pcr, 0xF000) + es)
    pk = [_ts_packet(0, pat), _ts_packet(pmt_pid, pmt)]
    pk += [bytes((0x47, 0x1F, 0xFF, 0x10)) + bytes(184) for _ in range(extra)]
    pk += [_ts_packet(0, pat, 1), _ts_packet(pmt_pid, pmt, 1)]
    return b"".join(pk)


def lang(code, kind=0):
    return bytes((0x0A, 4)) + code.encode() + bytes((kind,))


STREAMS = [(0x02, 512, b""), (0x03, 600, lang("ita")), (0x81, 601, lang("eng")), (0x1B, 700, b"")]


class StreamTable(Base):
    def test_pat_pmt_read_without_any_tool(self):
        p = self.tmp / "hand.ts"
        p.write_bytes(hand_ts(STREAMS))
        out, lj = self.look2(p)
        self.no_crash(lj)
        self.assertRegex(out, r"PID 512 \(0x200\)[^;|\n]*video[^;|\n]*MPEG-2")
        self.assertRegex(out, r"PID 600 \(0x258\)[^;|\n]*audio[^;|\n]*ita")
        self.assertRegex(out, r"PID 601 \(0x259\)[^;|\n]*audio[^;|\n]*AC-3[^;|\n]*eng|PID 601 \(0x259\)[^;|\n]*audio[^;|\n]*eng")
        self.assertRegex(out, r"PID 700 \(0x2bc\)[^;|\n]*video[^;|\n]*(H\.264|AVC)")
        self.assertIn("PMT PID 4096", out)
        self.assertIn("PCR PID 512", out)

    def test_two_programs_and_damaged_files(self):
        data = hand_ts(STREAMS)
        for k, b in enumerate(mutants(data, 9, 41)):
            p = self.tmp / f"fz{k}.ts"
            p.write_bytes(b)
            _, lj = self.look2(p, ok=(0, 1))
            self.no_crash(lj)

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
    def test_ffprobe_stream_table_and_a_tone_summary_for_every_audio_stream(self):
        p = self.tmp / "two_audio.ts"
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=64x48:r=25:d=6", "-f", "lavfi", "-i", "sine=f=600:sample_rate=48000:duration=6",
               "-f", "lavfi", "-i", "sine=f=1200:sample_rate=48000:duration=6", "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "mpeg2video", "-c:a:0", "mp2",
               "-c:a:1", "ac3", "-b:a:0", "128k", "-b:a:1", "192k", "-ac", "2", "-metadata:s:a:0", "language=ita", "-metadata:s:a:1", "language=eng",
               "-streamid", "0:512", "-streamid", "1:600", "-streamid", "2:601", "-f", "mpegts", str(p)]
        subprocess.run(cmd, check=True, timeout=60)
        out, lj = self.look2(p, "--quick", tools=True)
        self.no_crash(lj)
        self.assertRegex(out, r"PID 512 \(0x200\)[^|\n]*video[^|\n]*mpeg2video")
        self.assertRegex(out, r"PID 600 \(0x258\)[^|\n]*audio[^|\n]*mp2[^|\n]*ita[^|\n]*128,000")
        self.assertRegex(out, r"PID 601 \(0x259\)[^|\n]*audio[^|\n]*ac3[^|\n]*eng[^|\n]*192,000")
        line = next(ln for ln in out.splitlines() if "Tone per audio stream" in ln)
        items = line.split(" | ")
        first = next(i for i in items if "PID 600" in i)
        second = next(i for i in items if "PID 601" in i)
        self.assertRegex(first, r"\b60\d(\.\d)? Hz")
        self.assertNotIn("1200", first)
        self.assertRegex(second, r"\b1(19|20)\d(\.\d)? Hz")


@unittest.skipUnless(HAVE_NUMPY, "numpy")
class StreamTones(Base):
    def test_summary_of_a_steady_tone_bursts_and_speech_like_noise(self):
        import numpy as np
        import dl_sig
        from test_v2_r8c import Stub
        sr = 16000
        t = np.arange(sr * 12) / sr
        steady = (0.3 * np.sin(2 * np.pi * 1200 * t)).astype(np.float32)
        s = dl_sig.tone_summary(Stub(numpy=True), steady, sr)
        self.assertAlmostEqual(s["freq"], 1200, delta=1)
        self.assertGreater(s["share"], 0.9)
        rnd = np.random.default_rng(2)
        noise = (rnd.normal(0, 0.1, len(t))).astype(np.float32)
        bursts = noise.copy()
        for t0 in (2.0, 5.0, 8.0):
            a = int(t0 * sr)
            bursts[a:a + sr // 2] += (0.5 * np.sin(2 * np.pi * 800 * t[:sr // 2])).astype(np.float32)
        s = dl_sig.tone_summary(Stub(numpy=True), bursts, sr)
        self.assertEqual(s["tones"], 3)
        self.assertAlmostEqual(s["tone_freq"], 800, delta=2)
        s = dl_sig.tone_summary(Stub(numpy=True), noise, sr)
        self.assertLess(s["share"], 0.2)
        self.assertEqual(s["tones"], 0)

    def test_pure_python_summary_of_a_steady_tone(self):
        import dl_sig
        from test_v2_r8c import Stub
        sr = 8000
        x = array.array("f", (0.3 * math.sin(2 * math.pi * 1200 * k / sr) for k in range(sr * 6)))
        s = dl_sig.tone_summary(Stub(numpy=False), x, sr)
        self.assertAlmostEqual(s["freq"], 1200, delta=3)
        self.assertGreater(s["share"], 0.8)


if __name__ == "__main__":
    unittest.main()
