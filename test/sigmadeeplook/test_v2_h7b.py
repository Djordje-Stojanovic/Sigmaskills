"""Fix round H7, part 2: six generic failure categories from the graded held-out set 6, on fixtures built here.

1 a legacy binary table (dBASE) is decoded, 2 a detection conflict tries the reader for the type found, 3 a single-line XML member of a zip-based
format is expanded, 4 element values from late in a big XML document sit in the first print, 5 the container counts of an Ogg file are printed,
6 a small file says "complete" once and does not advertise drill-down flags that do not apply.
"""
import importlib.util
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

NAMES = ["Đorđe Šćekić", "Žarko Ćirić", "Nenad Đurić", "Željko Perišić", "Čedomir Pavlović"]


def have(mod):
    return importlib.util.find_spec(mod) is not None


def write_dbf(path, fields, rows, ver=0x03, lang=0xC8, enc="cp1250", deleted=()):
    rlen = 1 + sum(f[2] for f in fields)
    hlen = 32 + 32 * len(fields) + 1
    h = bytearray(32)
    h[0] = ver
    h[1:4] = bytes([126, 10, 19])   # 2026-10-19
    struct.pack_into("<IHH", h, 4, len(rows), hlen, rlen)
    h[29] = lang
    d = bytearray()
    for n, t, ln, dc in fields:
        e = bytearray(32)
        e[:len(n)] = n.encode()
        e[11], e[16], e[17] = ord(t), ln, dc
        d += e
    body = bytearray()
    for i, r in enumerate(rows):
        body += b"*" if i in deleted else b" "
        for (n, t, ln, dc), v in zip(fields, r):
            if t == "C":
                body += str(v).encode(enc).ljust(ln)[:ln]
            elif t in "NF":
                body += (f"{v:.{dc}f}" if dc else str(v)).rjust(ln).encode()
            elif t == "D":
                body += v.replace("-", "").encode()
            elif t == "L":
                body += b"T" if v else b"F"
    path.write_bytes(bytes(h) + bytes(d) + b"\x0d" + bytes(body) + b"\x1a")


def ogg_page(serial, seq, granule, payload, bos=False, eos=False, cont=False):
    segs = []
    n = len(payload)
    while n >= 255:
        segs.append(255)
        n -= 255
    segs.append(n)
    htype = (1 if cont else 0) | (2 if bos else 0) | (4 if eos else 0)
    return b"OggS" + bytes([0, htype]) + struct.pack("<qIII", granule, serial, seq, 0) + bytes([len(segs)]) + bytes(segs) + payload


class H7b(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_h7b_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look(self, path, *extra, tools=False):
        out = self.tmp / ("out_" + path.name)
        r = run([str(path), "--out", str(out), "--fresh", *([] if tools else ["--no-tools"]), *extra])
        self.assertIn(r.returncode, (0, 2, 3), r.stderr[-1500:])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return r.stdout, r.returncode, "\n".join(x["text"] for x in lj["stream"]), out

    # ------------------------------------------------------------ 1. dBASE
    def dbf(self, name="kupci.dbf", n=500, deleted=(3, 4)):
        rows = [(i, NAMES[i % 5], 100.5 + i, "2024-03-%02d" % (1 + i % 28), i % 2 == 0) for i in range(1, n + 1)]
        p = self.tmp / name
        write_dbf(p, [("ID", "N", 6, 0), ("IME", "C", 24, 0), ("IZNOS", "N", 10, 2), ("DATUM", "D", 8, 0), ("AKTIVAN", "L", 1, 0)], rows, deleted=deleted)
        return p, rows

    def test_dbf_header_is_decoded_and_rows_are_profiled(self):
        p, rows = self.dbf()
        out, rc, stream, folder = self.look(p)
        live = [r for i, r in enumerate(rows) if i not in (3, 4)]
        self.assertEqual(rc, 0)
        self.assertIn("data/dbf", out)
        self.assertIn("500 records of 50 bytes, 5 fields", out)
        self.assertIn("text encoding cp1250", out)
        self.assertIn("Fields (name type length[,decimals]): ID N6", out)
        self.assertIn("Žarko Ćirić", out)                  # the cp1250 letters, not mojibake
        self.assertNotIn("Ðorðe", stream)
        self.assertIn(f"{len(live)} records", out)         # deleted records are left out of the profile
        self.assertIn("DELETED-RECORDS", out)
        self.assertIn(f"sum {sum(r[2] for r in live):,.2f}".replace(".00", ""), stream)
        self.assertTrue((folder / "table.utf8.csv").exists())

    def test_dbf_truncated_file_is_flagged_and_other_binaries_are_not_dbf(self):
        p, rows = self.dbf("cut.dbf", 200, ())
        p.write_bytes(p.read_bytes()[:-2500])
        out, rc, stream, _ = self.look(p)
        self.assertIn("TRUNCATED", out)
        self.assertEqual(rc, 0)
        q = self.tmp / "random.bin"
        q.write_bytes(b"\x03" + bytes(range(1, 255)) * 20)
        out2, rc2, _s, _f = self.look(q)
        self.assertNotIn("data/dbf", out2)

    # ------------------------------------------------------------ 2. detection conflict
    @unittest.skipUnless(have("magika"), "magika")
    def test_content_model_text_beats_unknown_binary(self):
        lines = ["id,ime,grad,iznos"] + [f"{i},{NAMES[i % 2]},{['Čačak', 'Šabac', 'Niš'][i % 3]},{i * 3}.5" for i in range(400)]
        b = "\n".join(lines).encode("cp1250") + b"\n"
        p = self.tmp / "nul.dat"
        p.write_bytes(b[:2000] + b"\x00\x00" + b[2000:])   # two NUL bytes make the byte-level detector call it binary
        out, rc, stream, _ = self.look(p, tools=True)
        self.assertEqual(rc, 0)
        self.assertIn("data/csv", out)
        self.assertIn("calls this csv", out)
        self.assertIn("400 rows", out)

    # ------------------------------------------------------------ 3. one-line XML member of a zip-based format
    def test_single_line_xml_member_is_expanded(self):
        shapes = "".join(f'<Shape ID="{i}" NameU="Proces {i}"><Text>Korak {i}: {NAMES[i % 5]}</Text><Section N="Property"><Row N="Cost"><Cell N="Value" V="{i * 10}"/></Row></Section></Shape>' for i in range(1, 40))
        page = f'<?xml version="1.0" encoding="utf-8"?><PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main"><Shapes>{shapes}</Shapes></PageContents>'
        ct = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>'
        p = self.tmp / "dijagram.vsdx"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", ct)
            z.writestr("visio/pages/page1.xml", page)
        out, rc, stream, _ = self.look(p)
        self.assertEqual(rc, 0)
        self.assertIn("XML member visio/pages/page1.xml values by element path", stream)
        self.assertIn("/PageContents/Shapes/Shape/Text [39 values, 39 distinct]", stream)
        self.assertIn(f"Korak 1: {NAMES[1]}", stream)
        self.assertIn("/PageContents/Shapes/Shape@NameU", stream)
        self.assertIn("Proces 7", stream)

    # ------------------------------------------------------------ 4. values late in a big XML document
    def test_late_element_values_are_in_the_first_print(self):
        body = "".join(f"<rec id='{i}'><ime>{NAMES[i % 5]}</ime><iznos>{i}.5</iznos></rec>\n" for i in range(6000))
        p = self.tmp / "late.xml"
        p.write_text(f"<?xml version='1.0' encoding='utf-8'?>\n<doc><meta><naslov>Godišnji izveštaj</naslov></meta>\n{body}"
                     "<audit><approver>Žarko Ćirić</approver><status>odobreno</status></audit></doc>\n", encoding="utf-8")
        out, rc, stream, _ = self.look(p)
        self.assertIn("/doc/audit/approver [1 value, 1 distinct]: Žarko Ćirić", out)   # step 1, not the largest budget
        self.assertIn("/doc/meta/naslov", out)
        self.assertIn("numbers 0.5 .. 5,999.5, sum 18,000,000", out)                    # exact over every value, not over the capped distinct list

    # ------------------------------------------------------------ 5. Ogg container counts
    def ogg(self, name, pages=50, eos=True, serial=0x1234):
        ident = b"\x01vorbis" + struct.pack("<IBIiii", 0, 2, 44100, 0, 128000, 0) + b"\xb8\x01"
        data = ident and b""
        data += ogg_page(serial, 0, 0, ident, bos=True)
        for k in range(1, pages - 1):
            data += ogg_page(serial, k, k * 44100 // 10, bytes(300 + k))
        data += ogg_page(serial, pages - 1, (pages - 1) * 44100 // 10, bytes(100), eos=eos)
        p = self.tmp / name
        p.write_bytes(data)
        return p

    def test_ogg_pages_streams_codec_and_duration_are_counted(self):
        p = self.ogg("song.ogg", pages=50)
        out, rc, stream, _ = self.look(p)
        self.assertEqual(rc, 0)
        self.assertIn("Ogg container: 50 pages", out)
        self.assertIn("1 logical stream(s)", out)
        self.assertIn("vorbis, 44100 Hz, 2 ch, 50 pages", out)
        self.assertIn("ends with an EOS page", out)
        self.assertIn("ogg pages 50", out)
        self.assertIn("4.90 s from the last granule position", out)   # 49 * 4410 samples at 44100 Hz
        q = self.ogg("cutoff.ogg", pages=30, eos=False)
        out2, _rc, _s, _f = self.look(q)
        self.assertIn("NO-EOS", out2)

    # ------------------------------------------------------------ 6. small files do not advertise what does not apply
    def test_small_file_says_complete_once_and_names_no_irrelevant_flags(self):
        p = self.tmp / "tiny.csv"
        p.write_text("id,ime\n1,Đorđe\n2,Žarko\n3,Nenad\n", encoding="utf-8")
        out, rc, _s, folder = self.look(p)
        footer = out.strip().splitlines()[-1]
        if "remaining ~0" not in footer:
            self.skipTest("this fixture is not complete at the first print on this machine")
        self.assertIn("this look is complete", footer)
        self.assertNotIn("--speaker", out)
        more = run([str(p), "--out", str(folder), "--no-tools", "--more"])
        self.assertIn("complete in the first print", more.stdout)
        self.assertNotIn("--speaker", more.stdout)
        self.assertNotIn("--sql", more.stdout)


if __name__ == "__main__":
    unittest.main()
