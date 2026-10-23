"""Fix round 10, lane F1 (ticket 83, P0.14b.H9): the miss causes of held-out set 9 in text protocols, gettext .po, Java .properties,
OPML, YouTube .sbv, legacy Word .doc, PowerPoint .ppt and OpenDocument .odt, on fixtures built here (none from a held-out set).

Causes (from the miss table's diagnosis, never the questions): a semicolon table under a title block was read as a one-column CSV; a
feed URL in the last record was cut with an ellipsis; flag, key-prefix and subtree counts were missing; Word 97 files with garbage in
the high half of a stream size lost their WordDocument stream; .ppt properties were never read; .odt tables and footnotes never
reached the print; Latin-1 Spanish read as Windows-1250. Every expected figure is worked out here from the data this file wrote.
"""
import io
import json
import random
import shutil
import struct
import sys
import tempfile
import unittest
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
from test_v2 import SCRIPTS, run  # noqa: E402
from test_v2_r9 import sbv_stamp  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
FX = HERE / "fixtures"


class R10Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dl_r10f1_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def look(self, path, *extra, ok=(0,)):
        out = self.tmp / ("out_" + path.name)
        shutil.rmtree(out, ignore_errors=True)
        r = run([str(path), "--out", str(out), "--fresh", "--no-tools", *extra])
        self.assertIn(r.returncode, ok, r.stderr[-1500:] + r.stdout[-800:])
        lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
        return r.stdout, lj, out

    def kinds(self, lj):
        return {f["kind"] for f in lj.get("flags", [])}

    def no_crash(self, lj):
        self.assertNotIn("INTERNAL-ERROR", self.kinds(lj), lj.get("flags"))

    def fuzz(self, raw, name, rounds=5, hits=30, start=0):
        rnd = random.Random(10)
        for k in range(rounds):
            b = bytearray(raw)
            for _ in range(hits):
                b[rnd.randrange(start, len(b))] = rnd.randrange(256)
            p = self.tmp / f"fz{k}_{name}"
            p.write_bytes(bytes(b[:len(b) - rnd.randrange(0, len(b) // 3)]))
            _, lj, _ = self.look(p, ok=(0, 1, 2, 3))
            self.no_crash(lj)


# ------------------------------------------------------------------ a table inside a text: title block, table, totals
def protocol(n=300):
    rnd = random.Random(101)
    marks = ["", "", "", "брак", "недостача", "пересорт"]
    rows, total, counts = [], 0, Counter()
    for i in range(1, n + 1):
        qty = rnd.randint(1, 90)
        price = rnd.randint(10, 999)
        mark = rnd.choice(marks)
        counts[mark] += 1
        total += qty * price
        rows.append(f"{i};АРТ-{rnd.randint(1000, 9999)};Товар {i};{qty};{price};{qty * price};Склад {rnd.randint(1, 4)};{mark}")
    head = ["АКТ ПРИЁМКИ ТОВАРА", "Поставщик: ООО Ромашка (пример для теста)", "Дата: 12 марта 2026 г.", "Номер акта: 418", ""]
    tail = ["", f"ИТОГО строк: {n}", f"ИТОГО сумма (руб.): {total}", f"Брак: {counts['брак']}", "", "Подпись: ____________"]
    lines = head + ["№;Артикул;Наименование;Кол-во;Цена;Сумма;Склад;Отметка"] + rows + tail
    return "\r\n".join(lines) + "\r\n", rows, total, counts, len(head)


class TableInText(R10Base):
    def test_title_block_table_and_totals_are_read_apart(self):
        text, rows, total, counts, pre = protocol()
        p = self.tmp / "akt_priyomki.txt"
        p.write_bytes(text.encode("cp1251"))
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn(f"data rows {len(rows)};", out, "the table's rows, not the whole file's lines")
        self.assertIn("columns 8", out)
        self.assertIn(f"header row at line {pre + 1}", out)
        self.assertIn(f"ИТОГО сумма (руб.): {total}", out, "a stated total after the table is printed whole")
        self.assertIn(f"Брак: {counts['брак']}", out)
        self.assertIn("Номер акта: 418", out, "the title block is printed")
        self.assertIn(f"брак ({counts['брак']})", out, "the note column's top values with exact counts")
        self.assertIn(f"Сумма: int", out)
        self.assertRegex(out, rf"sum {total:,}\b", "the sum of the amount column over every row")
        last = rows[-1].split(";")
        self.assertIn(f"Last row (line {pre + 1 + len(rows)};", out)
        self.assertIn(f"Артикул={last[1]}", out)
        self.assertIn(rows[-15], out, "the last rows of the table are printed as the file has them")
        self.assertNotIn("REJECT-ROW", self.kinds(lj))
        self.no_crash(lj)

    def test_comma_table_under_a_title_line(self):
        rnd = random.Random(7)
        rows = [f"{i},{rnd.choice(['north', 'south'])},{rnd.randint(1, 500)}" for i in range(1, 61)]
        total = sum(int(r.split(",")[2]) for r in rows)
        p = self.tmp / "export.csv"
        p.write_text("Monthly export, plant 3\n\nid,region,units\n" + "\n".join(rows) + f"\n\nTotal units: {total}\n", encoding="utf-8")
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn("data rows 60;", out)
        self.assertIn(f"Total units: {total}", out)
        self.assertRegex(out, rf"units: int.*sum {total:,}\b")
        self.no_crash(lj)

    def test_plain_csv_is_unchanged(self):
        p = self.tmp / "plain.csv"
        p.write_text("a,b\n" + "\n".join(f"{i},{i * 2}" for i in range(1, 41)) + "\n", encoding="utf-8")
        out, _, _ = self.look(p)
        self.assertIn("data rows 40;", out)
        self.assertNotIn("Table inside the text", out)

    def test_damaged_protocols_do_not_crash(self):
        text, *_ = protocol(80)
        self.fuzz(text.encode("cp1251"), "akt.txt")
        for bad in ("\"open quote;a;b\n1;2;3\n", ";;;\n;;;\nx\n", "title\n\na;b\n"):
            p = self.tmp / "odd.txt"
            p.write_text(bad, encoding="utf-8")
            _, lj, _ = self.look(p, ok=(0, 1, 2, 3))
            self.no_crash(lj)


# ------------------------------------------------------------------ gettext flags
class PoFlags(R10Base):
    def test_flag_lines_counted_per_flag(self):
        rnd = random.Random(5)
        L = ['msgid ""', 'msgstr ""', '"Content-Type: text/plain; charset=UTF-8\\n"', ""]
        flags = Counter()
        lines_with_flag = 0
        for i in range(120):
            f = rnd.choice([[], ["python-format"], ["python-format"], ["c-format"], ["fuzzy"], ["fuzzy", "python-format"], ["python-brace-format"]])
            if f:
                L.append("#, " + ", ".join(f))
                flags.update(f)
                lines_with_flag += 1
            L += [f'msgid "Message %(n)s number {i}"', f'msgstr "Poruka %(n)s broj {i}"', ""]
        p = self.tmp / "app_sr.po"
        p.write_text("\n".join(L), encoding="utf-8")
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn(f"Flag lines ('#,'): {lines_with_flag}", out)
        for k, v in flags.items():
            self.assertRegex(out, rf"\b{k} {v}\b", k)
        self.assertIn(f"fuzzy {flags['fuzzy']}", out)
        self.no_crash(lj)


# ------------------------------------------------------------------ Java .properties in Latin-1
class JavaProperties(R10Base):
    def make(self):
        L = ["# Mensajes de prueba, ISO-8859-1", "! comentario", ""]
        pref = ["aviso", "error", "menu", "ayuda"]
        n = Counter()
        for i in range(1, 121):
            k = pref[i % 4] if i % 9 else "error"
            n[k] += 1
            if i % 10 == 0:
                L.append(f"{k}.saldo.{i:03d}=Saldo pendiente: {i * 3} \\u20ac, a\\u00f1o {2000 + i}")
            elif i % 13 == 0:
                L += [f"{k}.largo.{i:03d}=Primera parte del texto {i} \\", "        y la segunda parte del año"]
            else:
                L.append(f"{k}.texto.{i:03d}=¿Confirma el envío n.º {i}? Señor Muñoz, estado listo")
        p = self.tmp / "mensajes_es.properties"
        p.write_bytes(("\n".join(L) + "\n").encode("latin-1"))
        return p, n

    def test_prefix_counts_escapes_continuations_and_latin1(self):
        p, n = self.make()
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertIn("Keys by prefix", out)
        for k, v in n.items():
            self.assertRegex(out, rf"\b{k} {v}\b", k)
        self.assertIn("Saldo pendiente: 30 €, año 2010", out, "backslash-u escapes are decoded")
        self.assertIn("Primera parte del texto 13 y la segunda parte del año", out, "a trailing backslash joins the next line, blanks dropped")
        self.assertIn("¿Confirma el envío n.º 1? Señor Muñoz", out, "Latin-1, not Windows-1250")
        self.assertNotIn("żConfirma", out)
        self.no_crash(lj)

    def test_damaged_properties_do_not_crash(self):
        p, _ = self.make()
        self.fuzz(p.read_bytes(), "m.properties")
        q = self.tmp / "edge.properties"
        q.write_bytes(b"a=\\\nb=\\u12\nc=\\uZZZZ end\\\\\nd\\=x=1\n=novalue\n\\\n")
        _, lj, _ = self.look(q, ok=(0, 1, 2, 3))
        self.no_crash(lj)


# ------------------------------------------------------------------ OPML: a tree of feeds
class OpmlTree(R10Base):
    def make(self):
        rnd = random.Random(11)
        cats, out, total, last = {}, [], 0, None
        for c in ["Fruit", "Grain", "Dairy", "Spices"]:
            groups = {}
            body = []
            for g in range(rnd.randint(2, 4)):
                gname = f"{c} group {g + 1}"
                k = rnd.randint(3, 8)
                kinds = Counter()
                items = []
                for j in range(k):
                    typ = "link" if (c == "Grain" and g == 0 and j == 0) else "rss"
                    kinds[typ] += 1
                    last = f"https://feeds.example.org/{c.lower()}/{gname.replace(' ', '-').lower()}/very-long-feed-name-{j:04d}.xml"
                    attr = f'xmlUrl="{last}"' if typ == "rss" else f'url="{last}"'
                    items.append(f'<outline type="{typ}" text="{gname} feed {j}" {attr}/>')
                groups[gname] = kinds
                body.append(f'<outline text="{gname}">' + "".join(items) + "</outline>")
            cats[c] = groups
            out.append(f'<outline text="{c}" title="{c}">' + "".join(body) + "</outline>")
        xml = ('<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head><title>Market feeds</title></head><body>' + "".join(out) + "</body></opml>")
        p = self.tmp / "market.opml"
        p.write_text(xml, encoding="utf-8")
        return p, cats, last

    def test_items_per_category_and_last_url_in_full(self):
        p, cats, last = self.make()
        out, lj, _ = self.look(p, "--budget", "3000")
        for c, groups in cats.items():
            kinds = sum(groups.values(), Counter())
            n = sum(kinds.values())
            if len(kinds) > 1:
                self.assertIn(f"{c}: {n} items (rss {kinds['rss']}, link {kinds['link']}) in {len(groups)} groups", out)
            else:
                self.assertIn(f"{c}: {n} items (all rss) in {len(groups)} groups", out)
        g, kinds = next(iter(cats["Dairy"].items()))
        self.assertIn(f"{g} {sum(kinds.values())} items", out, "the items under each group")
        self.assertIn(last, out, "the last record's URL is printed whole, never cut")
        self.no_crash(lj)

    def test_damaged_opml_does_not_crash(self):
        p, _, _ = self.make()
        self.fuzz(p.read_bytes(), "m.opml", hits=8)


# ------------------------------------------------------------------ YouTube .sbv with repeated text
class SbvRepeats(R10Base):
    def test_distinct_lines_with_counts_and_the_single_line_cue(self):
        rnd = random.Random(21)
        say = ["Comets fly past the sun.", "Look to the north.", "The lens is clean.", "Venus is bright tonight.", "Keep the lights low.", "Mind the step."]
        t, cues = 1.0, []
        for i in range(1, 301):
            lines = [rnd.choice(say)] if i != 137 else ["Closing note: the dome shuts at ten."]
            if i % 5 == 0 and i != 137:
                lines.append(rnd.choice([s for s in say if s != lines[0]]))
            cues.append((t, t + 2.5, lines))
            t += 3.0
        txt = "\n".join(f"{sbv_stamp(a)},{sbv_stamp(b)}\n" + "\n".join(ls) + "\n" for a, b, ls in cues)
        p = self.tmp / "night.sbv"
        p.write_text(txt, encoding="utf-8")
        out, lj, _ = self.look(p, "--budget", "3000")
        held = Counter(x for _, _, ls in cues for x in set(ls))
        self.assertIn(f"Cue text lines: {len(held)} distinct lines in 300 cues", out)
        for s in say:
            self.assertIn(f"{held[s]} cues: {s}", out)
        self.assertIn("1 cue (#137): Closing note: the dome shuts at ten.", out)
        self.no_crash(lj)


# ------------------------------------------------------------------ OLE files: v3 stream sizes, property sets
NOSTREAM, END = 0xFFFFFFFF, 0xFFFFFFFE


def filetime(dt):
    return int((dt - datetime(1601, 1, 1, tzinfo=timezone.utc)).total_seconds() * 10_000_000)


def propset(fmtid, props):
    """An OLE property-set stream with one section: props = [(pid, vt, value)] (VT_I2, VT_I4, VT_LPSTR, VT_FILETIME)."""
    entries, blobs, off = [], [], 8 + 8 * len(props)
    for pid, vt, v in props:
        if vt == 30:
            raw = v.encode("cp1252") + b"\0"
            body = struct.pack("<HHI", 30, 0, len(raw)) + raw
        elif vt == 3:
            body = struct.pack("<HHi", 3, 0, v)
        elif vt == 2:
            body = struct.pack("<HHh", 2, 0, v) + b"\0\0"
        else:
            body = struct.pack("<HHQ", 64, 0, v)
        body += b"\0" * (-len(body) % 4)
        entries.append((pid, off))
        blobs.append(body)
        off += len(body)
    sec = struct.pack("<II", off, len(props)) + b"".join(struct.pack("<II", p, o) for p, o in entries) + b"".join(blobs)
    return struct.pack("<HHI", 0xFFFE, 0, 0x00020006) + b"\0" * 16 + struct.pack("<I", 1) + uuid.UUID(fmtid).bytes_le + struct.pack("<I", 48) + sec


def cfb(streams, garbage=True):
    """A version 3 OLE compound file (512-byte sectors) holding `streams` in the big FAT (each padded to 4 KB). `garbage` writes junk into
    the high 32 bits of every size, as Word 97 does; readers must ignore them."""
    names = list(streams)
    blobs = [streams[n] + b"\0" * (max(4096, len(streams[n])) - len(streams[n])) for n in names]
    nsec = [-(-len(b) // 512) for b in blobs]
    ndir = -(-(len(names) + 1) * 128 // 512)
    nfat = 1
    while nfat * 128 < nfat + ndir + sum(nsec):
        nfat += 1
    fat = [0xFFFFFFFD] * nfat + [nfat + i + 1 for i in range(ndir - 1)] + [END]
    cur, starts = nfat + ndir, []
    for k in nsec:
        starts.append(cur)
        fat += [cur + i + 1 for i in range(k - 1)] + [END]
        cur += k
    fat += [NOSTREAM] * (nfat * 128 - len(fat))
    high = 0xDEADBEEF if garbage else 0

    def entry(name, typ, right, child, start, size):
        nm = name.encode("utf-16-le") + b"\0\0"
        return (nm.ljust(64, b"\0") + struct.pack("<HBB", len(nm), typ, 1) + struct.pack("<III", NOSTREAM, right, child) + b"\0" * 36
                + struct.pack("<III", start, size, high))
    d = entry("Root Entry", 5, NOSTREAM, 1, END, 0)
    for i, (n, b) in enumerate(zip(names, blobs), 1):
        d += entry(n, 2, i + 1 if i < len(names) else NOSTREAM, NOSTREAM, starts[i - 1], len(b))
    d += (b"\0" * 64 + struct.pack("<HBB", 0, 0, 0) + struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM) + b"\0" * 48) * (ndir * 4 - len(names) - 1)
    h = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 16 + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\0" * 6
         + struct.pack("<IIIIIIIII", 0, nfat, nfat, 0, 4096, END, 0, END, 0) + struct.pack("<109I", *(list(range(nfat)) + [NOSTREAM] * (109 - nfat))))
    return h + struct.pack(f"<{len(fat)}I", *fat) + d + b"".join(blobs)


def garble_sizes(raw):
    """Junk in the high 32 bits of every directory entry's size of a version 3 file (what Word 97 leaves there)."""
    b = bytearray(raw)
    first_dir = struct.unpack_from("<I", b, 48)[0]
    fat = []
    for s in struct.unpack_from("<109I", b, 76):
        if s < 0xFFFFFFFA:
            fat += struct.unpack_from("<128I", b, 512 + s * 512)
    s, seen = first_dir, 0
    while s < 0xFFFFFFFA and seen < 1000:
        for i in range(4):
            o = 512 + s * 512 + 128 * i
            if b[o + 66] in (1, 2, 5):
                b[o + 124:o + 128] = b"\xef\xbe\xad\xde"
        s, seen = fat[s], seen + 1
    return bytes(b)


SI, DSI = "f29f85e0-4ff9-1068-ab91-08002b27b3d9", "d5cdd502-2e9c-101b-9397-08002b2cf9ae"


class OleFiles(R10Base):
    def ppt(self):
        si = propset(SI, [(1, 2, 1252), (2, 30, "Harvest results 2026"), (4, 30, "Mara Quell"), (8, 30, "Ivo Brandt"), (9, 30, "31"),
                          (18, 30, "Microsoft PowerPoint"), (12, 64, filetime(datetime(2019, 5, 6, 10, 20, tzinfo=timezone.utc))),
                          (13, 64, filetime(datetime(2020, 2, 3, 8, 5, tzinfo=timezone.utc))), (15, 3, 812)])
        dsi = propset(DSI, [(1, 2, 1252), (7, 3, 12), (8, 3, 2), (9, 3, 1), (15, 30, "Quell Farms")])
        return cfb({"\x05SummaryInformation": si, "\x05DocumentSummaryInformation": dsi, "PowerPoint Document": b"\x0f\x00" * 3000, "Current User": b"\0" * 64})

    def test_ppt_properties_are_printed_whole(self):
        p = self.tmp / "harvest.ppt"
        p.write_bytes(self.ppt())
        out, lj, _ = self.look(p, ok=(0, 1))
        for s in ("Revision: 31", "Application: Microsoft PowerPoint", "Title: Harvest results 2026", "Author: Mara Quell", "Last saved by: Ivo Brandt",
                  "Created: 2019-05-06 10:20 UTC", "Last saved: 2020-02-03 08:05 UTC", "Words: 812", "Slides: 12", "Hidden slides: 1", "Company: Quell Farms"):
            self.assertIn(s, out)
        self.no_crash(lj)

    def test_word97_size_garbage_is_ignored_and_tables_print_every_row(self):
        raw = (FX / "r9_report.doc").read_bytes()
        p = self.tmp / "garbled.doc"
        p.write_bytes(garble_sizes(raw))
        out, lj, _ = self.look(p, "--budget", "3000")
        self.assertNotIn("CORRUPT", self.kinds(lj), "WordDocument is found although the high half of its size is junk")
        self.assertRegex(out, r"Word binary header: nFib \d+")
        self.assertIn("Table 1 rows (6 rows, every row", out)
        for k in range(1, 6):
            self.assertIn(f"Item {k} | {2 * k} | {1.5 * k:.2f}", out)
        self.no_crash(lj)

    def test_damaged_ole_files_do_not_crash(self):
        self.fuzz(self.ppt(), "h.ppt", start=512)
        self.fuzz(garble_sizes((FX / "r9_report.doc").read_bytes()), "g.doc", start=512)


# ------------------------------------------------------------------ OpenDocument text: tables and footnotes
ODF_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:dc="http://purl.org/dc/elements/1.1/" '
          'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"')


class OdtTablesNotes(R10Base):
    def make(self):
        rows = [("Setting", "Default", "Limits")] + [(f"Valve {i} delay (s)", f"{i * 1.5:.1f}", f"0 to {i * 10}") for i in range(1, 14)]
        cell = "".join("<table:table-row>" + "".join(f"<table:table-cell><text:p>{c}</text:p></table:table-cell>" for c in r) + "</table:table-row>" for r in rows)
        body = ('<text:h text:outline-level="1">Setup</text:h><text:p>The pump starts first.<text:note text:id="n1" text:note-class="footnote">'
                '<text:note-citation>1</text:note-citation><text:note-body><text:p>Pump codes sit in annex B, which this sample leaves out.</text:p>'
                '</text:note-body></text:note></text:p>'
                f'<table:table table:name="Settings">{cell}</table:table>'
                '<text:p>Close the cover.<text:note text:id="n2" text:note-class="endnote"><text:note-citation>i</text:note-citation><text:note-body>'
                '<text:p>Torque 2 Nm.</text:p></text:note-body></text:note></text:p>')
        content = f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {ODF_NS}><office:body><office:text>{body}</office:text></office:body></office:document-content>'
        meta = f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta {ODF_NS}><office:meta><dc:title>Pump guide</dc:title></office:meta></office:document-meta>'
        p = self.tmp / "pump.odt"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text")
            z.writestr("content.xml", content)
            z.writestr("meta.xml", meta)
        return p, rows

    def test_every_table_row_and_note_text(self):
        p, rows = self.make()
        out, lj, d = self.look(p)
        self.assertIn(f"Table 1 'Settings' rows ({len(rows)} rows, every row", out)
        for r in rows:
            self.assertIn(" | ".join(r), out)
        self.assertIn("footnote 1: Pump codes sit in annex B, which this sample leaves out.", out)
        self.assertIn("endnote i: Torque 2 Nm.", out)
        md = (d / "text.md").read_text(encoding="utf-8")
        self.assertIn("| Valve 13 delay (s) | 19.5 | 0 to 130 |", md, "the table sits in text.md")
        self.assertIn("Pump codes sit in annex B", md, "the notes sit in text.md")
        self.assertIn("paragraphs (non-empty, outside tables) 2;", out, "counts are unchanged")
        self.no_crash(lj)

    def test_damaged_odt_does_not_crash(self):
        p, _ = self.make()
        z = zipfile.ZipFile(p)
        content = z.read("content.xml")
        for k, cut in enumerate((len(content) // 2, len(content) - 30)):
            q = self.tmp / f"cut{k}.odt"
            with zipfile.ZipFile(q, "w") as w:
                w.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text")
                w.writestr("content.xml", content[:cut])
            _, lj, _ = self.look(q, ok=(0, 1, 2, 3))
            self.no_crash(lj)


if __name__ == "__main__":
    unittest.main()
