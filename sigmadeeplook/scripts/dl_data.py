"""SigmaDeepLook: data files (csv, tsv, json, jsonl, sqlite, parquet, arrow, xml, yaml, toml). Schema first, rows second.

Core is stdlib. SQLite opens read-only and immutable. XML with entity declarations is not parsed.
"""
import csv
import io
import json
import random
import re
import sqlite3
import struct
import time
from collections import Counter

import dl_core as core

SAMPLE_ROWS = 20000
TIME_CAP = 30.0
INT_RE = re.compile(r"^-?\d{1,18}$")
FLOAT_RE = re.compile(r"^-?\d*\.\d+([eE][-+]?\d+)?$|^-?\d+[eE][-+]?\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")
NULLS = {"", "null", "none", "na", "n/a", "nan", "-"}


def infer(vals):
    """A column type from sample strings: int, float, bool, date, text."""
    seen = {"int": 0, "float": 0, "bool": 0, "date": 0, "text": 0}
    n = 0
    for v in vals:
        if v.strip().lower() in NULLS:
            continue
        n += 1
        s = v.strip()
        if INT_RE.match(s):
            seen["int"] += 1
        elif FLOAT_RE.match(s):
            seen["float"] += 1
        elif s.lower() in ("true", "false"):
            seen["bool"] += 1
        elif DATE_RE.match(s):
            seen["date"] += 1
        else:
            seen["text"] += 1
    if not n:
        return "empty"
    for t in ("text", "date", "bool"):
        if seen[t] == n:
            return t
    if seen["text"] or seen["date"] or seen["bool"]:
        return "text"
    return "float" if seen["float"] else "int"


def decode_best(b):
    for enc in ("utf-8-sig", "utf-16"):
        try:
            if enc == "utf-16" and not b.startswith((b"\xff\xfe", b"\xfe\xff")):
                continue
            return b.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return b.decode("latin-1"), "latin-1"


def look_data(look):
    st = look.subtype
    fn = {"csv": data_csv, "tsv": data_csv, "json": data_json, "jsonl": data_jsonl, "sqlite": data_sqlite, "parquet": data_parquet,
          "arrow": data_arrow, "xml": data_xml, "yaml": data_text_struct, "toml": data_toml}.get(st, data_text_struct)
    fn(look)
    look.ask_human("What question should this data answer?", "Which columns or tables matter, and are any of them personal data?")


# ---------------------------------------------------------------- csv
def data_csv(look):
    raw = open(look.path, "rb").read(256 << 20)
    text, enc = decode_best(raw)
    if enc == "latin-1":
        look.flag("ENCODING", "file", "not valid UTF-8; read as Latin-1", "accents may be wrong if the real encoding is another one")
    if raw.startswith(b"\xef\xbb\xbf"):
        look.flag("BOM", "file", "UTF-8 byte-order mark", "some tools keep it in the first column name")
    sample = text[:100000]
    try:
        dia = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dia.delimiter
    except csv.Error:
        delim = "\t" if look.subtype == "tsv" else ","
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    t0 = time.time()
    header, rows, rejects, n, tail = None, [], [], 0, []
    for rec in rd:
        if header is None:
            header = rec
            continue
        n += 1
        if len(rec) != len(header):
            if len(rejects) < 100:
                rejects.append((rd.line_num, len(rec), rec))
            continue
        if len(rows) < SAMPLE_ROWS:
            rows.append(rec)
        tail.append(rec)
        if len(tail) > 5:
            tail.pop(0)
        if time.time() - t0 > TIME_CAP:
            look.flag("PARTIAL", "row count", f"stopped after {n} rows", "time cap reached; counts are lower bounds")
            break
    header = header or []
    nrej = len(rejects)
    look.fact("encoding", enc)
    look.fact("delimiter", delim)
    look.fact("rows", n)
    look.fact("columns", len(header))
    look.fact("column_names", header)
    look.fact("rejects", nrej)
    look.line(f"Delimited table: {n} data rows, {len(header)} columns, delimiter {delim!r}, encoding {enc}, {nrej} reject rows (wrong field count).")
    schema = []
    for i, name in enumerate(header):
        col = [r[i] for r in rows]
        nonnull = [v for v in col if v.strip().lower() not in NULLS]
        t = infer(col)
        nums = []
        if t in ("int", "float"):
            nums = [float(v) for v in nonnull if INT_RE.match(v.strip()) or FLOAT_RE.match(v.strip())]
        mn = min(nums) if nums else (min(nonnull) if nonnull else "")
        mx = max(nums) if nums else (max(nonnull) if nonnull else "")
        schema.append({"name": name, "type": t, "null_pct": round(100 * (len(col) - len(nonnull)) / max(1, len(col)), 1),
                       "distinct": len(set(nonnull)), "min": mn, "max": mx, "examples": list(dict.fromkeys(nonnull))[:5]})
    look.write_text("schema.json", json.dumps(schema, indent=1, default=str), "column types, null %, distinct, min/max, examples (from the first 20k rows)", "json")
    if header:
        look.line("Columns: " + ", ".join(f"{s['name']} ({s['type']})" for s in schema[:12]))
    rng = random.Random(7)
    rand = rng.sample(rows, min(10, len(rows)))

    def md(rs):
        return "\n".join("| " + " | ".join(c.replace("|", "\\|")[:60] for c in r) + " |" for r in rs)
    head = "| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n"
    look.write_text("sample.md", f"## head 5\n\n{head}{md(rows[:5])}\n\n## tail 5\n\n{head}{md(tail)}\n\n## 10 random rows (seed 7)\n\n{head}{md(rand)}\n",
                    "head 5, tail 5 and 10 random rows")
    if rejects:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["line", "fields_found", "fields_expected", "raw"])
        for ln, k, rec in rejects:
            w.writerow([ln, k, len(header), delim.join(rec)])
        look.write_text("rejects.csv", buf.getvalue(), f"{nrej} rows with the wrong number of fields")
        for ln, k, rec in rejects[:5]:
            look.flag("REJECT-ROW", f"line {ln}", f"{k} fields, expected {len(header)}", "short or long row: a missing or unquoted delimiter")
    if n > SAMPLE_ROWS:
        look.flag("SAMPLED", "schema", f"first {SAMPLE_ROWS} of {n} rows", "types after the sample may differ; raise the sample or force types")
    look.step("schema and rejects", "stdlib csv")


# ---------------------------------------------------------------- json
def skeleton(v, depth=0, maxdepth=5):
    if depth >= maxdepth:
        return "..."
    if isinstance(v, dict):
        return {k: skeleton(x, depth + 1, maxdepth) for k, x in list(v.items())[:40]}
    if isinstance(v, list):
        if not v:
            return "[] (empty)"
        kinds = Counter(type(x).__name__ for x in v)
        return {"__array__": f"{len(v)} items", "types": dict(kinds), "first": skeleton(v[0], depth + 1, maxdepth)}
    return type(v).__name__


def data_json(look):
    raw = open(look.path, "rb").read(64 << 20)
    if look.size > 64 << 20:
        look.flag("PARTIAL", "file", "first 64 MB only", "")
    text, enc = decode_best(raw)
    try:
        v = json.loads(text)
    except ValueError as e:
        look.flag("INVALID-JSON", "file", str(e)[:120], "")
        look.line("Invalid JSON; first lines below.")
        look.excerpt("First lines", text, 10)
        return
    sk = skeleton(v)
    look.fact("json_top", type(v).__name__)
    look.write_text("skeleton.json", json.dumps(sk, indent=1), "keys and types tree, array lengths", "json")
    look.line(f"JSON {type(v).__name__}" + (f" with {len(v)} items" if hasattr(v, "__len__") else "") + f", encoding {enc}.")
    look.excerpt("Skeleton", json.dumps(sk, indent=1), 25, 1800)
    look.write_text("sample.md", "```json\n" + json.dumps(v if look.size < 20000 else (v[:5] if isinstance(v, list) else {k: v[k] for k in list(v)[:8]} if isinstance(v, dict) else v), indent=1, default=str)[:20000] + "\n```\n",
                    "a small slice of the values")


def data_jsonl(look):
    n, bad, keys, first = 0, 0, Counter(), []
    with open(look.path, "rb") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            n += 1
            try:
                o = json.loads(line)
                if isinstance(o, dict):
                    keys.update(o.keys())
                if len(first) < 5:
                    first.append(o)
            except ValueError:
                bad += 1
                if bad <= 3:
                    look.flag("INVALID-LINE", f"line {ln}", "not valid JSON", "")
    look.fact("rows", n)
    look.fact("bad_lines", bad)
    look.fact("keys", dict(keys))
    look.line(f"JSON Lines: {n} records, {bad} invalid lines; keys: " + ", ".join(f"{k} ({c})" for k, c in keys.most_common(12)))
    look.write_text("sample.md", "```json\n" + "\n".join(json.dumps(o) for o in first)[:6000] + "\n```\n", "first 5 records")


# ---------------------------------------------------------------- sqlite
def data_sqlite(look):
    uri = "file:" + str(look.path).replace("\\", "/").replace("?", "%3f") + "?mode=ro&immutable=1"
    if not uri.startswith("file:/") and not uri.startswith("file:///"):
        uri = "file:///" + uri[5:]
    try:
        con = sqlite3.connect(uri, uri=True)
        con.execute("PRAGMA query_only=1")
        tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
        info = {}
        for t in tabs:
            q = '"' + t.replace('"', '""') + '"'
            cols = [(r[1], r[2]) for r in con.execute(f"pragma table_info({q})")]
            cnt = con.execute(f"select count(*) from {q}").fetchone()[0]
            sample = [list(map(str, r)) for r in con.execute(f"select * from {q} limit 5")]
            info[t] = {"rows": cnt, "columns": cols, "sample": sample}
        con.close()
    except sqlite3.Error as e:
        look.flag("SQLITE-ERROR", "file", str(e)[:120], "")
        return
    look.fact("tables", tabs)
    look.fact("row_counts", {t: i["rows"] for t, i in info.items()})
    look.line(f"SQLite database: {len(tabs)} tables, opened read-only. " + "; ".join(f"{t} ({i['rows']} rows)" for t, i in info.items()))
    look.write_text("schema.json", json.dumps(info, indent=1, default=str), "tables, columns, row counts, 5 sample rows each", "json")


# ---------------------------------------------------------------- parquet / arrow
def data_parquet(look):
    pa = look.mod("pyarrow")
    if pa:
        import pyarrow.parquet as pq
        f = pq.ParquetFile(str(look.path))
        md = f.metadata
        look.fact("rows", md.num_rows)
        look.fact("row_groups", md.num_row_groups)
        look.fact("columns", [fld.name for fld in f.schema_arrow])
        look.line(f"Parquet: {md.num_rows} rows, {md.num_columns} columns, {md.num_row_groups} row groups. Columns: " +
                  ", ".join(f"{fld.name} ({fld.type})" for fld in f.schema_arrow))
        t = f.read_row_group(0).slice(0, 5).to_pylist() if md.num_row_groups else []
        look.write_text("schema.json", json.dumps({"schema": [[fld.name, str(fld.type)] for fld in f.schema_arrow], "rows": md.num_rows, "head": t}, indent=1, default=str), "schema and 5 rows", "json")
        return
    d = look.mod("duckdb")
    if d:
        con = d.connect()
        p = str(look.path).replace("'", "''")
        desc = con.execute(f"describe select * from read_parquet('{p}')").fetchall()
        n = con.execute(f"select count(*) from read_parquet('{p}')").fetchone()[0]
        look.fact("rows", n)
        look.fact("columns", [r[0] for r in desc])
        look.line(f"Parquet: {n} rows. Columns: " + ", ".join(f"{r[0]} ({r[1]})" for r in desc))
        return
    b = open(look.path, "rb").read()
    flen = struct.unpack("<I", b[-8:-4])[0] if b[-4:] == b"PAR1" else 0
    look.line(f"Parquet file, footer {flen} bytes. Schema and rows need pyarrow or duckdb.")
    look.skip("parquet schema and rows", "pyarrow and duckdb not importable" if not look.no_tools else "disabled by --no-tools", "pyarrow")


def data_arrow(look):
    if not look.need_mod("pyarrow", "arrow schema and rows"):
        look.line("Arrow IPC file; schema needs pyarrow.")
        return
    import pyarrow as pa
    with pa.memory_map(str(look.path)) as src:
        r = pa.ipc.open_file(src)
        look.fact("columns", [f.name for f in r.schema])
        look.line(f"Arrow IPC: {r.num_record_batches} batches. Columns: " + ", ".join(f"{f.name} ({f.type})" for f in r.schema))


# ---------------------------------------------------------------- xml, yaml, toml
def data_xml(look):
    raw = open(look.path, "rb").read(20 << 20)
    if b"<!ENTITY" in raw[:200000]:
        look.flag("ENTITY-DECLARATION", "file", "DTD entity declared", "not parsed: entity expansion can blow up memory; read it as text")
        look.exit_code = 2
        look.excerpt("First lines", raw[:1500].decode("utf-8", "replace"), 12)
        return
    dx = look.mod("defusedxml")
    if dx:
        from defusedxml import ElementTree as ET
    else:
        import xml.etree.ElementTree as ET
    try:
        counts, root_tag, depth = Counter(), None, 0
        for ev, el in ET.iterparse(io.BytesIO(raw), events=("start",)):
            if root_tag is None:
                root_tag = el.tag
            counts[el.tag] += 1
    except Exception as e:
        look.flag("INVALID-XML", "file", f"{type(e).__name__}: {e}"[:120], "")
        return
    look.fact("root", root_tag)
    look.fact("element_counts", dict(counts.most_common(20)))
    look.line(f"XML: root <{root_tag}>, {sum(counts.values())} elements. Most common: " + ", ".join(f"{k} ({v})" for k, v in counts.most_common(8)))


def data_toml(look):
    try:
        import tomllib
        v = tomllib.loads(open(look.path, "rb").read().decode("utf-8", "replace"))
    except Exception as e:
        look.flag("INVALID-TOML", "file", str(e)[:120], "")
        return
    look.write_text("skeleton.json", json.dumps(skeleton(v), indent=1), "keys and types tree", "json")
    look.line("TOML with top-level keys: " + ", ".join(v))
    look.fact("keys", list(v))


def data_text_struct(look):
    text = open(look.path, "rb").read(2 << 20).decode("utf-8", "replace")
    keys = re.findall(r"(?m)^([A-Za-z_][\w-]*):", text)
    look.line(f"{look.subtype.upper()} text file, {len(text.splitlines())} lines; top-level keys: " + ", ".join(dict.fromkeys(keys)) if keys else f"{look.subtype} text file.")
    look.excerpt("First lines", text, 12)
    look.fact("keys", list(dict.fromkeys(keys)))
