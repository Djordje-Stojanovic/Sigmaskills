"""Fix round 4 fixtures: small synthesised files per family, each with its ground truth worked out here, independently of the tool.

Every builder returns (path, truth). Seeded random, so a failure reproduces. Nothing is downloaded or executed.
"""
import gzip
import io
import json
import random
import tarfile
import zipfile
from pathlib import Path

REGIONS = ["north", "south", "east", "west"]


def csv_file(d, n=3000, seed=4):
    rnd = random.Random(seed)
    rows, truth = [], {"rows": n, "sum_units": 0, "empty_qty": 0, "per_region": {}, "max_units": None, "max_line": None, "distinct_sku": set()}
    for i in range(n):
        reg = rnd.choice(REGIONS)
        units = rnd.randint(1, 900)
        if i == 2222:
            units = 12_345   # the one maximum, on file line 2224 (header is line 1)
        qty = "" if i % 37 == 0 else str(rnd.randint(1, 9))
        sku = f"S{rnd.randint(1, 250)}"
        rows.append(f"{1000 + i},{reg},{sku},{units},{qty}")
        truth["sum_units"] += units
        truth["empty_qty"] += qty == ""
        truth["per_region"][reg] = truth["per_region"].get(reg, 0) + 1
        truth["distinct_sku"].add(sku)
        if truth["max_units"] is None or units > truth["max_units"]:
            truth["max_units"], truth["max_line"] = units, i + 2
    truth["distinct_sku"] = len(truth["distinct_sku"])
    p = Path(d) / "sales.csv"
    p.write_text("order_id,region,sku,units,qty\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p, truth


def jsonl_file(d, n=800, seed=5):
    rnd = random.Random(seed)
    recs = [{"id": i, "user": f"u{rnd.randint(1, 40)}", "ms": rnd.randint(5, 500), "ok": rnd.random() > 0.2} for i in range(n)]
    p = Path(d) / "calls.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    return p, {"records": n, "sum_ms": sum(r["ms"] for r in recs), "max_ms": max(r["ms"] for r in recs), "users": len({r["user"] for r in recs}),
               "false_ok": sum(1 for r in recs if not r["ok"])}


def small_json(d):
    doc = {"name": "demo", "version": "1.2.3", "servers": [{"host": f"h{i}", "port": 8000 + i, "weight": i * 2} for i in range(7)], "debug": False}
    p = Path(d) / "conf.json"
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p, {"servers": 7, "sum_port": sum(8000 + i for i in range(7)), "sum_weight": sum(i * 2 for i in range(7))}


def yaml_file(d):
    lines = ["services:"]
    for i in range(6):
        lines += [f"  svc{i}:", f"    image: app{i}:latest", f"    replicas: {i + 1}", f"    port: {9000 + i}"]
    p = Path(d) / "stack.yaml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p, {"services": 6, "sum_replicas": sum(range(1, 7))}


def toml_file(d):
    body = '[package]\nname = "widget"\nversion = "0.4.1"\n\n[dependencies]\nserde = "1.0"\ntokio = "1.37"\nrand = "0.8"\n\n[profile.release]\nlto = true\nopt-level = 3\n'
    p = Path(d) / "Cargo.toml"
    p.write_text(body, encoding="utf-8")
    return p, {"deps": 3}


def markdown_file(d):
    parts, h2, h3 = ["# Handbook", "", "Intro text."], 0, 0
    for i in range(9):
        parts += ["", f"## Chapter {i + 1}", "", "Some words here. " * (i + 1)]
        h2 += 1
        if i % 3 == 0:
            parts += ["", f"### Detail {i + 1}", "", "- item a", "- item b", "- [ ] todo one", "- [x] done one"]
            h3 += 1
    parts += ["", "## Last words", "", "The end is here."]
    h2 += 1
    p = Path(d) / "handbook.md"
    p.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return p, {"h1": 1, "h2": h2, "h3": h3, "last": "Last words", "tasks": 2 * h3}


def log_file(d, n=1500, seed=6):
    rnd = random.Random(seed)
    lv = {"INFO": 0, "WARN": 0, "ERROR": 0}
    lat = []
    lines = []
    for i in range(n):
        level = rnd.choices(["INFO", "WARN", "ERROR"], [80, 15, 5])[0]
        lv[level] += 1
        ms = rnd.randint(1, 2000)
        lat.append(ms)
        lines.append(f"2026-10-0{1 + i // 500} {10 + (i // 60) % 10:02d}:{i % 60:02d}:00 {level} req done latency_ms={ms} worker={i % 4}")
    p = Path(d) / "app.log"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p, {"lines": n, "levels": lv, "lat_max": max(lat), "lat_sum": sum(lat), "lat_n": n}


def access_log(d, n=900, seed=7):
    rnd = random.Random(seed)
    st = {}
    lines = []
    for i in range(n):
        s = rnd.choice([200, 200, 200, 301, 404, 500])
        st[s] = st.get(s, 0) + 1
        lines.append(f'10.0.0.{i % 50} - - [01/Oct/2026:12:{i % 60:02d}:00 +0000] "GET /p/{i % 30} HTTP/1.1" {s} {100 + i}')
    p = Path(d) / "access.log"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p, {"status": st, "lines": n}


def srt_file(d):
    cues, t = [], 0.0
    lens = [1.2, 4.75, 2.0, 0.5, 3.333, 6.1, 2.2]
    for i, ln in enumerate(lens):
        a, b = t, t + ln
        cues.append((a, b, f"Cue number {i + 1} words"))
        t = b + 0.25

    def s(x):
        ms = round(x * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    body = "\n".join(f"{i + 1}\n{s(a)} --> {s(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(cues))
    p = Path(d) / "talk.srt"
    p.write_text(body, encoding="utf-8")
    longest = max(range(len(lens)), key=lambda i: lens[i])
    return p, {"cues": len(cues), "longest": longest + 1, "shortest": min(range(len(lens)), key=lambda i: lens[i]) + 1, "last_end": cues[-1][1]}


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
CT = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>{}</Types>'


def core_xml(author):
    return ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>Round four</dc:title><dc:creator>{author}</dc:creator><cp:lastModifiedBy>Editor Two</cp:lastModifiedBy>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-02T03:04:05Z</dcterms:created></cp:coreProperties>')


def docx_file(d):
    body, n_p, empty, in_tbl = [], 0, 0, 0
    for i in range(23):
        if i % 5 == 4:
            body.append("<w:p/>")
            empty += 1
        elif i % 4 == 0:
            body.append(f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Heading {i}</w:t></w:r></w:p>')
        else:
            body.append(f"<w:p><w:r><w:t>Paragraph {i} has some words.</w:t></w:r></w:p>")
        n_p += 1
    rows = []
    for r in range(3):
        cells = "".join(f"<w:tc><w:p><w:r><w:t>r{r}c{c}</w:t></w:r></w:p></w:tc>" for c in range(4))
        rows.append(f"<w:tr>{cells}</w:tr>")
        in_tbl += 4
    body.append("<w:tbl>" + "".join(rows) + "</w:tbl>")
    body.append('<w:p><w:ins w:id="1" w:author="Ann"><w:r><w:t>inserted</w:t></w:r></w:ins><w:del w:id="2" w:author="Bob"><w:r><w:delText>gone</w:delText></w:r></w:del></w:p>')
    n_p += 1
    doc = f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body>' + "".join(body) + "<w:sectPr/></w:body></w:document>"
    p = Path(d) / "report.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", CT.format('<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'))
        z.writestr("word/document.xml", doc)
        z.writestr("docProps/core.xml", core_xml("Mara Quill"))
    return p, {"paragraphs": n_p + in_tbl, "body_paragraphs": n_p, "empty": empty, "tables": 1, "cells": 12, "author": "Mara Quill", "ins": 1, "dels": 1}


def xlsx_file(d):
    S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    sheets = [("Data", "visible"), ("Hidden", "hidden"), ("Calc", "visible")]
    wb = (f'<?xml version="1.0" encoding="UTF-8"?><workbook {S} {R}><sheets>'
          + "".join(f'<sheet name="{n}" sheetId="{i + 1}" r:id="rId{i + 1}"' + (f' state="{st}"' if st != "visible" else "") + "/>" for i, (n, st) in enumerate(sheets))
          + "</sheets></workbook>")
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(3))
            + "</Relationships>")
    vals = [7, 13, 21, 4, 55, 3, 89, 34]

    def sheet(rows):
        return f'<?xml version="1.0" encoding="UTF-8"?><worksheet {S}><sheetData>' + "".join(rows) + "</sheetData></worksheet>"
    data_rows = ['<row r="1"><c r="A1" t="inlineStr"><is><t>item</t></is></c><c r="B1" t="inlineStr"><is><t>amount</t></is></c></row>']
    for i, v in enumerate(vals):
        data_rows.append(f'<row r="{i + 2}"><c r="A{i + 2}" t="inlineStr"><is><t>it{i}</t></is></c><c r="B{i + 2}"><v>{v}</v></c></row>')
    hidden_rows = ['<row r="1"><c r="A1"><v>1000</v></c></row>']
    calc_rows = [f'<row r="1"><c r="A1"><f>SUM(Data!B2:B9)</f><v>{sum(vals)}</v></c><c r="B1"><f>MAX(Data!B2:B9)</f><v>{max(vals)}</v></c></row>']
    p = Path(d) / "book4.xlsx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", CT.format('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'))
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet(data_rows))
        z.writestr("xl/worksheets/sheet2.xml", sheet(hidden_rows))
        z.writestr("xl/worksheets/sheet3.xml", sheet(calc_rows))
        z.writestr("docProps/core.xml", core_xml("Ivo Ledger"))
    return p, {"sheets": 3, "hidden": 1, "sum": sum(vals), "max": max(vals), "min": min(vals), "formulas": 2, "author": "Ivo Ledger"}


def pptx_file(d):
    P_ = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    p = Path(d) / "deck4.pptx"
    n = 5
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", CT.format('<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'))
        z.writestr("ppt/presentation.xml", f'<?xml version="1.0" encoding="UTF-8"?><p:presentation {P_}/>')
        for i in range(n):
            shapes = "".join(f'<p:sp><p:txBody><a:p><a:r><a:t>Slide {i + 1} box {k}</a:t></a:r></a:p></p:txBody></p:sp>' for k in range(i + 1))
            hid = ' show="0"' if i == 3 else ""
            z.writestr(f"ppt/slides/slide{i + 1}.xml", f'<?xml version="1.0" encoding="UTF-8"?><p:sld {P_}{hid}><p:cSld><p:spTree>{shapes}</p:spTree></p:cSld></p:sld>')
        z.writestr("docProps/core.xml", core_xml("Deck Author"))
    return p, {"slides": n, "hidden": 1, "shapes": sum(range(1, n + 1))}


def jar_file(d):
    p = Path(d) / "lib.jar"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nImplementation-Title: widgetlib\nImplementation-Version: 3.2.1\nMain-Class: com.ex.Main\n")
        z.writestr("META-INF/maven/com.ex/widgetlib/pom.properties", "groupId=com.ex\nartifactId=widgetlib\nversion=3.2.1\n")
        for i in range(12):
            z.writestr(f"com/ex/C{i}.class", b"\xca\xfe\xba\xbe" + bytes(40 + i * 10))
        z.writestr("com/ex/big.properties", "x=" + "y" * 5000)
    return p, {"title": "widgetlib", "version": "3.2.1", "classes": 12, "biggest": "com/ex/big.properties"}


def zip_project(d):
    rnd = random.Random(8)
    pkg = {"name": "shopfront", "version": "2.0.0", "dependencies": {"react": "^19.0.0", "zod": "^3.23.0"}, "devDependencies": {"vitest": "^2.0.0"}}
    amounts = [rnd.randint(1, 500) for _ in range(40)]
    tests = "\n".join(f"def test_case_{i}():\n    assert True\n" for i in range(9))
    p = Path(d) / "project.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("shop/package.json", json.dumps(pkg, indent=2))
        z.writestr("shop/data/prices.csv", "sku,amount\n" + "\n".join(f"s{i},{a}" for i, a in enumerate(amounts)) + "\n")
        z.writestr("shop/tests/test_shop.py", tests)
        z.writestr("shop/src/app.py", 'import os\nKEY = os.environ.get("SHOP_API_KEY")\nDB = os.getenv("SHOP_DB_URL")\n' + "x = 1\n" * 300)
        z.writestr("shop/README.md", "# Shopfront\n\n## Setup\n\nRun it.\n")
    return p, {"name": "shopfront", "sum": sum(amounts), "rows": 40, "tests": 9, "env": ["SHOP_API_KEY", "SHOP_DB_URL"], "longest": "shop/src/app.py"}


def repo_dir(d):
    root = Path(d) / "minirepo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "minirepo"\nversion = "0.9.0"\ndependencies = ["requests>=2", "rich"]\n', encoding="utf-8")
    (root / "src" / "core.py").write_text("\n".join(f"def f{i}():\n    return {i}\n" for i in range(50)), encoding="utf-8")
    (root / "src" / "util.js").write_text("export const A = 1;\n" * 20, encoding="utf-8")
    (root / "tests" / "test_core.py").write_text("\n".join(f"def test_{i}():\n    pass\n" for i in range(6)), encoding="utf-8")
    files = [p for p in root.rglob("*") if p.is_file()]
    return root, {"files": len(files), "name": "minirepo", "tests": 6, "longest": "src/core.py"}


def gz_csv(d):
    vals = list(range(1, 501))
    raw = ("n,sq\n" + "\n".join(f"{v},{v * v}" for v in vals) + "\n").encode()
    p = Path(d) / "squares.csv.gz"
    p.write_bytes(gzip.compress(raw))
    return p, {"rows": 500, "sum_sq": sum(v * v for v in vals), "unpacked": len(raw)}


def tar_gz(d):
    p = Path(d) / "bundle.tar.gz"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for i in range(7):
            data = (f"line {i}\n" * (i + 1) * 10).encode()
            ti = tarfile.TarInfo(f"bundle/f{i}.txt")
            ti.size = len(data)
            ti.mtime = 1_780_000_000 + i * 86400
            t.addfile(ti, io.BytesIO(data))
    p.write_bytes(buf.getvalue())
    return p, {"files": 7, "biggest": "bundle/f6.txt"}


def svg_file(d):
    body = ['<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">']
    body.append('<path id="p1" d="M10 10 L50 10 L50 50 Z M60 60 l10 0 l0 10 z" fill="#f00" stroke="#000"/>')
    body.append('<path id="p2" d="M100 100 h50 v-40 m5 5 c1 1 2 2 3 3" fill="#00ff00"/>')
    body.append('<rect x="300" y="200" width="90" height="95" fill="#F00"/>')
    body.append('<circle cx="20" cy="250" r="15" style="fill: #0000ff; stroke: #000"/>')
    body.append('<g><text x="5" y="290">Hello SVG</text></g></svg>')
    p = Path(d) / "pic.svg"
    p.write_text("".join(body), encoding="utf-8")
    # paths: 2; subpaths: p1 has 2 (M, M), p2 has 2 (M, m) -> 4; x extremes: 5 (text) .. 390 (rect), y: 10 .. 295
    return p, {"paths": 2, "subpaths": 4, "elements": 7, "x_min": 5, "x_max": 390, "y_min": 10, "y_max": 295, "fill_red": 2}


def sqlite_db(d, seed=9):
    import sqlite3
    rnd = random.Random(seed)
    p = Path(d) / "shop.db"
    con = sqlite3.connect(p)
    con.execute("create table customers (id integer primary key, country text)")
    con.execute("create table orders (id integer primary key, customer_id integer, amount integer, status text)")
    cust = [(i, rnd.choice(["AT", "DE", "RS", "US"])) for i in range(1, 51)]
    con.executemany("insert into customers values (?, ?)", cust)
    orders = [(i, rnd.randint(1, 50), rnd.randint(5, 999), rnd.choice(["paid", "paid", "refunded", "open"])) for i in range(1, 1201)]
    con.executemany("insert into orders values (?, ?, ?, ?)", orders)
    con.commit()
    con.close()
    st = {}
    for o in orders:
        st[o[3]] = st.get(o[3], 0) + 1
    return p, {"orders": 1200, "customers": 50, "sum_amount": sum(o[2] for o in orders), "max_amount": max(o[2] for o in orders),
               "status": st, "rows_all": 1250}


def parquet_file(d, seed=10):
    import pyarrow as pa
    import pyarrow.parquet as pq
    rnd = random.Random(seed)
    n = 5000
    vals = [rnd.randint(0, 10_000) for _ in range(n)]
    cat = [rnd.choice(["red", "green", "blue"]) for _ in range(n)]
    p = Path(d) / "readings.parquet"
    pq.write_table(pa.table({"v": vals, "c": cat}), p, row_group_size=2000)
    return p, {"rows": n, "sum": sum(vals), "red": cat.count("red")}
