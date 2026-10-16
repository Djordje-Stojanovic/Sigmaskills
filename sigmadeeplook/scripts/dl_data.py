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
NUM_SEP_RE = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
DMY_RE = re.compile(r"^\d{1,2}[/.]\d{1,2}[/.]\d{4}")
ID_NAME_RE = re.compile(r"(^|[_\s-])(id|key|uuid|guid|sku)$|^id$", re.I)
DISTINCT_CAP = 100_000
DISTINCT_CAP_ID = 2_000_000
TOP_CAP = 60


def num(x):
    """1e+07 reads badly; show 9999999.99 and 5, not 1e+07 and 5.0."""
    return f"{x:.0f}" if float(x).is_integer() else f"{x:.2f}"


def cell_kind(s):
    """One cell -> int, float, num-sep, date-iso, date-dmy, null-token, empty or text. Cheap first-character tests keep a full pass fast."""
    if not s:
        return "empty"
    c = s[0]
    if c.isdigit() or c in "-+.":
        if INT_RE.match(s):
            return "int"
        if FLOAT_RE.match(s):
            return "float"
        if NUM_SEP_RE.match(s):
            return "num-sep"
        if DATE_RE.match(s):
            return "date-iso"
        if DMY_RE.match(s):
            return "date-dmy"
    if s.lower() in NULLS:
        return "null-token"
    return "text"


class ColProfile:
    """Streaming profile of one column over every row: kinds, distinct values, top values, range, spread, first line of each oddity."""
    def __init__(self, name, first):
        self.name = name
        self.kinds, self.first_line = Counter(), {}
        self.cap = DISTINCT_CAP_ID if (first or ID_NAME_RE.search(name or "")) else DISTINCT_CAP
        self.distinct, self.overflow = set(), False
        self.top = Counter()
        self.lo = self.hi = None
        self.lo_line = self.hi_line = None
        self.neg, self.neg_line, self.nnum, self.res, self.stride = 0, None, 0, [], 1
        self.dup, self.dup_line = 0, None

    def add(self, raw, line):
        s = raw.strip()
        k = cell_kind(s)
        self.kinds[k] += 1
        if k not in self.first_line:
            self.first_line[k] = line
        if k in ("empty", "null-token"):
            return
        if k in ("int", "float"):
            x = float(s)
            self.nnum += 1
            if self.lo is None or x < self.lo:
                self.lo, self.lo_line = x, line
            if self.hi is None or x > self.hi:
                self.hi, self.hi_line = x, line
            if x < 0:
                self.neg += 1
                if self.neg_line is None:
                    self.neg_line = line
            if self.nnum % self.stride == 0:  # even systematic sample: halve it and double the stride when full
                self.res.append(x)
                if len(self.res) > 10000:
                    self.res = self.res[::2]
                    self.stride *= 2
        if not self.overflow:
            if s in self.distinct:
                self.dup += 1
                if self.dup_line is None:
                    self.dup_line = line
            elif len(self.distinct) >= self.cap:
                self.overflow = True
            else:
                self.distinct.add(s)
        if self.top is not None:
            self.top[s] += 1
            if len(self.top) > TOP_CAP:
                self.top = None

    def pct(self, q):
        if not self.res:
            return None
        r = sorted(self.res)
        return r[min(len(r) - 1, int(q * len(r)))]

    def dominant(self):
        real = [(k, n) for k, n in self.kinds.items() if k not in ("empty", "null-token")]
        return max(real, key=lambda kv: kv[1])[0] if real else "empty"

    def summary(self, total):
        nonempty = sum(n for k, n in self.kinds.items() if k not in ("empty", "null-token"))
        d = {"name": self.name, "type": self.dominant(), "kinds": dict(self.kinds),
             "null_pct": round(100 * (total - nonempty) / max(1, total), 2),
             "distinct": (f">={len(self.distinct)}" if self.overflow else len(self.distinct))}
        if self.lo is not None:
            d.update(min=self.lo, max=self.hi, p50=self.pct(0.5), p99=self.pct(0.99))
        elif self.distinct:
            vals = [v for v in self.distinct if DATE_RE.match(v)] if self.dominant() == "date-iso" else self.distinct
            d.update(min=min(vals or self.distinct), max=max(vals or self.distinct))
        if self.top is not None and self.top:
            d["top_values"] = self.top.most_common(8)
        elif self.distinct:
            d["examples"] = sorted(self.distinct)[:5]
        return d


def profile_findings(look, header, prof, total, repeats):
    """Turn the full-pass profiles into flags (leads, not verdicts). -> lines for the Summary."""
    notes = []
    if repeats:
        look.flag("REPEATED-HEADER", f"line {repeats[0]}", f"the header row appears again {len(repeats)} time(s)", "two exports pasted together; the repeats were left out of every count")
        notes.append(f"the header row repeats at line {repeats[0]}" + (f" (+{len(repeats) - 1} more)" if len(repeats) > 1 else ""))
    for p in prof:
        nonempty = sum(n for k, n in p.kinds.items() if k not in ("empty", "null-token"))
        if not nonempty:
            if total > 0:
                notes.append(f"{p.name}: always empty")
            continue
        dom = p.dominant()
        numeric_col = dom in ("int", "float")
        if ID_NAME_RE.search(p.name or "") or (p is prof[0]):
            if not p.overflow and p.dup and p.dup / nonempty < 0.5 and len(p.distinct) / nonempty > 0.5:
                look.flag("DUPLICATE-KEYS", f"{p.name}, first repeat at line {p.dup_line}", f"{p.dup} repeated values among {nonempty}", "looks like an identifier but is not unique")
                notes.append(f"{p.name}: {p.dup} duplicate values")
        for kind, n in p.kinds.items():
            if kind in ("empty", "null-token") or kind == dom:
                continue
            if numeric_col and kind in ("text", "num-sep", "date-iso", "date-dmy"):
                look.flag("MIXED-TYPES", f"{p.name}, first at line {p.first_line[kind]}", f"{n} cells are {kind}, the rest are {dom}", "a number column with text or formatted numbers in it")
                notes.append(f"{p.name}: {n} cells {kind} in a {dom} column")
            elif kind.startswith("date") and dom.startswith("date") and n >= 2:
                look.flag("MIXED-DATE-FORMATS", f"{p.name}, first at line {p.first_line[kind]}", f"{p.kinds[dom]} {dom}, {n} {kind}", "two date formats in one column")
                notes.append(f"{p.name}: dates in two formats")
        nt = p.kinds.get("null-token", 0)
        if nt:
            look.flag("NULL-TOKENS", f"{p.name}, first at line {p.first_line['null-token']}", f"{nt} cells hold a null word such as N/A", "counted as missing, not as values")
        if numeric_col and p.hi is not None:
            p99 = p.pct(0.99)
            if p99 and p.hi > 20 * abs(p99) and p.hi > 100:
                look.flag("OUTLIER", f"{p.name}, line {p.hi_line}", f"max {num(p.hi)} vs 99th percentile {num(p99)}", "one value dwarfs the rest: a typo or a placeholder")
                notes.append(f"{p.name}: max {num(p.hi)} against p99 {num(p99)}")
            if p.neg and p.neg / max(1, p.nnum) < 0.01:
                look.flag("NEGATIVE-VALUES", f"{p.name}, first at line {p.neg_line}", f"{p.neg} negative of {p.nnum}", "negative numbers in a column that is otherwise positive")
                notes.append(f"{p.name}: {p.neg} negative values")
        if p.top:
            groups = {}
            for v in p.top:
                groups.setdefault(v.lower().replace(" ", ""), []).append(v)
            variants = [g for g in groups.values() if len(g) > 1]
            if variants:
                look.flag("CASE-VARIANTS", p.name, "; ".join(" / ".join(f"{v} ({p.top[v]})" for v in g) for g in variants[:3]), "the same value spelled in more than one way")
                notes.append(f"{p.name}: same value spelled several ways ({' / '.join(variants[0])})")
        if total and p.kinds.get("empty", 0) / total >= 0.9 and nonempty:
            notes.append(f"{p.name}: {100 * p.kinds['empty'] / total:.0f} % empty")
    return notes


def profile_line(p, total):
    s = p.summary(total)
    bits = [f"{s['type']}"]
    if s["null_pct"]:
        bits.append(f"{s['null_pct']:g} % empty")
    bits.append(f"{s['distinct']} distinct")
    if "p50" in s and s.get("p50") is not None:
        bits.append(f"range {num(s['min'])} to {num(s['max'])}, median {num(s['p50'])}")
    elif "top_values" in s:
        bits.append("top: " + ", ".join(f"{v} ({n})" for v, n in s["top_values"][:5]))
    elif "min" in s:
        bits.append(f"{str(s['min'])[:24]} .. {str(s['max'])[:24]}")
    return f"- {p.name}: " + ", ".join(bits)


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
    header, rows, rejects, n, tail, prof, repeats = None, [], [], 0, [], [], []
    ncols, partial = 0, False
    for rec in rd:
        if header is None:
            header = rec
            ncols = len(header)
            prof = [ColProfile(h, i == 0) for i, h in enumerate(header)]
            continue
        if len(rec) != ncols:
            n += 1
            if len(rejects) < 100:
                rejects.append((rd.line_num, len(rec), rec))
            continue
        if rec == header:
            repeats.append(rd.line_num)
            continue
        n += 1
        ln = rd.line_num
        for i in range(ncols):
            prof[i].add(rec[i], ln)
        if len(rows) < SAMPLE_ROWS:
            rows.append(rec)
        tail.append(rec)
        if len(tail) > 5:
            tail.pop(0)
        if time.time() - t0 > TIME_CAP:
            partial = True
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
    look.line(f"Delimited table: {n} data rows, {len(header)} columns, delimiter {delim!r}, encoding {enc}, {nrej} reject rows (wrong field count). Every row was read" + (" until the time cap." if partial else "; the profile below is a full pass, not a sample."))
    total_ok = sum(prof[0].kinds.values()) if prof else 0
    notes = profile_findings(look, header, prof, total_ok, repeats)
    schema = [p.summary(total_ok) for p in prof]
    look.write_text("schema.json", json.dumps(schema, indent=1, default=str), "per-column profile over every row: type mix, empty %, distinct, range, median, top values", "json")
    if notes:
        look.line("Findings: " + "; ".join(notes[:10]) + (f"; +{len(notes) - 10} more in Flags" if len(notes) > 10 else "") + ".")
    for p in prof[:16]:
        look.line(profile_line(p, total_ok))
    if len(prof) > 16:
        look.line(f"- ... {len(prof) - 16} more columns in schema.json")
    rng = random.Random(7)
    rand = rng.sample(rows, min(10, len(rows)))

    def md(rs):
        return "\n".join("| " + " | ".join(c.replace("|", "\\|")[:60] for c in r) + " |" for r in rs)
    head = "| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n"
    look.write_text("sample.md", f"## head 5\n\n{head}{md(rows[:5])}\n\n## tail 5\n\n{head}{md(tail)}\n\n## 10 random rows from the first {len(rows)} (seed 7)\n\n{head}{md(rand)}\n",
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
        objs = Counter(r[0] for r in con.execute("select type from sqlite_master"))
        ver = con.execute("pragma user_version").fetchone()[0]
        pages = con.execute("pragma page_count").fetchone()[0] * con.execute("pragma page_size").fetchone()[0]
        con.close()
    except sqlite3.Error as e:
        look.flag("SQLITE-ERROR", "file", str(e)[:120], "")
        return
    look.fact("tables", tabs)
    look.fact("row_counts", {t: i["rows"] for t, i in info.items()})
    look.line(f"SQLite database: {len(tabs)} tables, {objs.get('index', 0)} indexes, {objs.get('view', 0)} views, {objs.get('trigger', 0)} triggers, user_version {ver}, {core.human(pages)} of pages; opened read-only. "
              + "; ".join(f"{t} ({i['rows']} rows)" for t, i in info.items()))
    big = sorted(info.items(), key=lambda kv: -kv[1]["rows"])[:6]
    look.line("Biggest tables and their columns: " + " | ".join(f"{t}: " + ", ".join(f"{c[0]} {c[1] or '?'}" for c in i["columns"][:10]) + (" ..." if len(i["columns"]) > 10 else "") for t, i in big))
    empty = [t for t, i in info.items() if not i["rows"]]
    if empty:
        look.line(f"Empty tables: {', '.join(empty)}.")
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
