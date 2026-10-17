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
import dl_util as U

SAMPLE_ROWS = 20000
TIME_CAP = 180.0   # a full pass: every count exact (accuracy over speed); the quick tier profiles the first 4 MB
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
          "arrow": data_arrow, "avro": lambda lk: __import__("dl_adapt").look_avro(lk), "xml": data_xml, "yaml": data_text_struct, "toml": data_toml}.get(st, data_text_struct)
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


COLUMN_LEGEND = ("Columns (name: type, null and empty counts, distinct values, min and max with the file line where each first occurs "
                 "(xN = N rows hold it), sum, mean, top values (count)); every count is exact over every row:")


def profile_line(p, total):
    s = p.summary(total)
    bits = [f"{s['type']}"]
    if s["null_pct"]:
        bits.append(f"{s['null_pct']:g} % empty")
    d = s["distinct"]
    bits.append(f"{U.compact(d) if isinstance(d, int) and d >= 10000 else d} distinct")
    if "p50" in s and s.get("p50") is not None:
        bits.append(f"range {num(s['min'])} to {num(s['max'])}, median {num(s['p50'])}")
    elif "top_values" in s:
        bits.append("top: " + ", ".join(f"{v} ({n})" for v, n in s["top_values"][:5]))
    elif "min" in s:
        bits.append(f"{str(s['min'])[:24]} .. {str(s['max'])[:24]}")
    return f"{p.name}: " + ", ".join(bits)


QUICK_BYTES = 4 << 20   # the quick tier profiles the first 4 MB of a big table; the line count and the repeated-header search cover the whole file


def whole_file_scan(raw):
    """Quick tier: (lines in the file, [line numbers where the header row appears again]) from the bytes alone, no CSV parsing."""
    nl = raw.count(b"\n")
    lines = nl + (0 if raw.endswith(b"\n") or not raw else 1)
    first = raw[:raw.find(b"\n")].rstrip(b"\r") if b"\n" in raw else raw
    if first.startswith(b"\xef\xbb\xbf"):
        first = first[3:]   # the byte-order mark sits before the first header only
    repeats = []
    if first:
        for m in re.finditer(b"\n" + re.escape(first) + rb"\r?(?=\n|$)", raw):
            repeats.append(raw.count(b"\n", 0, m.start()) + 2)
    return lines, repeats


def data_csv(look):
    raw = open(look.path, "rb").read(256 << 20)
    quick_cut = look.quick and len(raw) > QUICK_BYTES
    whole_lines = whole_repeats = None
    if quick_cut:
        whole_lines, whole_repeats = whole_file_scan(raw)
        cut = raw.rfind(b"\n", 0, QUICK_BYTES)
        raw = raw[:cut + 1 if cut > 0 else QUICK_BYTES]
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
    import dl_prof as P
    gp, gcols = P.Profiler(True, "line"), None
    for rec in rd:
        if header is None:
            header = rec
            ncols = len(header)
            prof = [ColProfile(h, i == 0) for i, h in enumerate(header)]
            gcols = gp.columns([h.lstrip("﻿").strip() or f"column {i + 1}" for i, h in enumerate(header)])
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
        gp.add_row(gcols, rec, ln)
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
    profiled = n
    if quick_cut:   # rows and repeated headers come from the whole file's bytes; the column profile from its first rows
        repeats = list(whole_repeats)
        n = max(0, whole_lines - 1 - len(whole_repeats))
        tail = []
        look.flag("QUICK-SAMPLE", "column profile", f"first {profiled} of about {n} rows", "quick tier: distinct counts, outliers and duplicate keys cover the first rows only; run --tier standard for the full pass")
    look.fact("encoding", enc)
    look.fact("delimiter", delim)
    look.fact("rows", n)
    look.fact("columns", len(header))
    look.fact("column_names", header)
    look.fact("rejects", nrej)
    look.headline = f"{look.subtype.upper()}, {n:,} rows x {len(header)} columns"
    look.dims = f"{U.compact(n)} rows"
    if quick_cut:
        look.line(f"Delimited table: {n:,} data rows (counted over the whole file), {len(header)} columns, delimiter {delim!r}, encoding {enc}, {nrej} reject rows in the part profiled. Column profile: first {profiled:,} rows only.")
    else:
        look.line(f"Delimited table: {n:,} data rows, {len(header)} columns, delimiter {delim!r}, encoding {enc}, {nrej} reject rows (wrong field count). Every row was read" + (" until the time cap." if partial else "; the profile below is a full pass, not a sample."))
    total_ok = sum(prof[0].kinds.values()) if prof else 0
    notes = profile_findings(look, header, prof, total_ok, repeats)
    schema = [p.summary(total_ok) for p in prof]
    look.write_text("schema.json", json.dumps(schema, indent=1, default=str), "per-column profile over every row: type mix, empty %, distinct, range, median, top values", "json")
    notes = [n for n in notes if "empty" in n]   # every other finding is a flag and is listed once, under Watch out; the empty % sits in each column row
    if prof:   # one legend, then one compact row per column, exact counts over every row (positions are file line numbers)
        extra = csv_second_pass(look, text, delim, header, gp) if gp.n else []
        crow = gp.field_lines()
        look.line(COLUMN_LEGEND + chr(10) + chr(10).join(crow[:40]) + (f"{chr(10)}... {len(crow) - 40} more columns below" if len(crow) > 40 else ""), 86, "profile")
        if len(crow) > 40:
            look.line("More columns:" + chr(10) + chr(10).join(crow[40:]), 36, "profile")
        miss = sum(f.nulls + f.empties for f in gp.fields.values())
        P.counts(look, [("data rows", n), ("columns", len(header)), ("rows profiled", gp.n if gp.n != n else None), ("reject rows", nrej), ("repeated header rows", len(repeats) or None),
                        ("empty or null cells", miss), ("complete rows (no empty cell)", complete_rows(text, delim, ncols) if not quick_cut and n <= 2_000_000 else None)])
        for ln_ in gp.stats_lines():
            look.line(ln_, 34, "aggregates")
        for ln_ in extra:
            look.line(ln_, 32, "aggregates")
        for ln_ in gp.enum_lines():
            look.line(ln_, 30, "values")
    import dl_sample
    dl_sample.build_sample(look, text, delim, header, prof, n, repeats, tail, rows, partial or quick_cut)
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


def complete_rows(text, delim, ncols):
    """Rows with no empty cell (and the right field count)."""
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    next(rd, None)
    return sum(1 for r in rd if len(r) == ncols and all(c.strip() for c in r))


def csv_second_pass(look, text, delim, header, gp, cap_s=40.0):
    """Group-by counts and sums and the top / bottom rows by each number (one more pass over the rows, time-capped)."""
    import dl_prof as P
    sp = P.SecondPass(gp)
    names = [h.lstrip("﻿").strip() or f"column {i + 1}" for i, h in enumerate(header)]
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    next(rd, None)
    t0 = time.time()
    for k, rec in enumerate(rd):
        if len(rec) != len(header) or rec == header:
            continue
        sp.add_row(names, rec, rd.line_num)
        if k % 5000 == 0 and time.time() - t0 > cap_s:
            look.flag("PARTIAL", "group-by and top rows", f"stopped at line {rd.line_num}", "time cap: the group sums cover the rows up to that line only")
            break
    return sp.lines()


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
        lines = [x for x in text.splitlines() if x.strip()]
        ok = 0
        for x in lines[:50]:
            try:
                json.loads(x)
                ok += 1
            except ValueError:
                pass
        if len(lines) >= 2 and ok >= 0.8 * min(50, len(lines)):   # one JSON value per line: JSON Lines with a .json name
            look.subtype = "jsonl"
            look.flag("JSON-LINES", "file", "one JSON value per line, not one document", "parsed as JSON Lines")
            return data_jsonl(look)
        look.flag("INVALID-JSON", "file", str(e)[:120], "")
        look.line("Invalid JSON; first lines below.")
        look.excerpt("First lines", text, 10)
        import dl_prof as P
        P.text_profile(look, text, 70, "Text")
        return
    sk = skeleton(v)
    look.fact("json_top", type(v).__name__)
    look.write_text("skeleton.json", json.dumps(sk, indent=1), "keys and types tree, array lengths", "json")
    look.line(f"JSON {type(v).__name__}" + (f" with {len(v)} items" if hasattr(v, "__len__") else "") + f", encoding {enc}.")
    look.excerpt("Skeleton", json.dumps(sk, indent=1), 25, 1800, 40)
    import dl_prof as P
    P.doc_profile(look, v, "JSON")


def data_jsonl(look):
    import dl_prof as P
    n, bad, keys, first = 0, 0, Counter(), []
    recs = []
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
                if len(recs) < 2_000_000:
                    recs.append((ln, o))
            except ValueError:
                bad += 1
                if bad <= 3:
                    look.flag("INVALID-LINE", f"line {ln}", "not valid JSON", "")
    look.fact("rows", n)
    look.fact("bad_lines", bad)
    look.fact("keys", dict(keys))
    look.headline = f"JSON Lines, {n:,} records"
    look.line(f"JSON Lines: {n:,} records, {bad} invalid lines; keys (records holding each): " + ", ".join(f"{k} ({c:,})" for k, c in keys.most_common(30)), 88)
    p, extra = P.profile(recs, False, "line")
    full = sum(1 for _, o in recs if isinstance(o, dict) and len(o.keys() & keys.keys()) == len(keys)) if keys else None
    P.counts(look, [("records", n), ("invalid lines", bad), ("distinct keys", len(keys)), ("records with every key", full)])
    P.emit(look, p, extra, "Records (positions are file line numbers)", 86, 30, 30)
    if n <= 3000:
        rows = []
        for ln, o in recs:
            fl = P.flat_of(o) if isinstance(o, (dict, list)) else {"value": o}
            rows.append(f"line {ln}: " + "; ".join(f"{k}={P.short(x if not isinstance(x, P.Multi) else ', '.join(map(str, x)), 60)}" for k, x in fl.items() if not k.endswith(P.LEN)))
        for k in range(0, len(rows), 20):
            look.line("Records:\n" + "\n".join(rows[k:k + 20]), 18, "records")
    look.write_text("sample.md", "```json\n" + "\n".join(json.dumps(o) for o in first)[:6000] + "\n```\n", "first 5 records")


# ---------------------------------------------------------------- sqlite
TIME_COL_RE = re.compile(r"(^|_)(ts|time|date|datetime|timestamp|created|updated|modified|seen|at|published)(_|$)|(_at|_ts|_time|_date)$", re.I)
SQLITE_BUDGET_S = 12.0


def cell_text(v, n=36):
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray)):
        return f"<blob {len(v)} B>"
    s = " ".join(str(v).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def when(v):
    """A time-like number as a date: seconds or milliseconds since 1970 become ISO dates; anything else is shown as written."""
    import datetime
    try:
        x = float(v)
        if 9e8 < x < 4.2e9:
            return datetime.datetime.fromtimestamp(x, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
        if 9e11 < x < 4.2e12:
            return datetime.datetime.fromtimestamp(x / 1000, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    return str(v)[:19]


def implicit_relations(info):
    """Columns named <thing>_id / <thing>id that match another table, when no foreign key says so -> ['child.col~parent']."""
    low = {t.lower(): t for t in info}
    out = []
    for t, i in info.items():
        for c in i["columns"]:
            m = re.match(r"(?i)^(.+?)_?id$", c[0])
            if not m or c[0].lower() == "id":
                continue
            stem = m.group(1).lower()
            for cand in (stem, stem + "s", stem + "es", stem[:-1] + "ies" if stem.endswith("y") else None):
                if cand and cand in low and low[cand] != t:
                    out.append(f"{t}.{c[0]}~{low[cand]}")
                    break
    return out


def rows_fmt(n):
    """Row counts for people: 1052870 -> 1.05M, 856601 -> 857k, 9671 -> 9671."""
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1e6:.2f}M".replace("0M", "M") if n < 10_000_000 else U.compact(n)
    return U.compact(n)


def qident(name):
    return '"' + name.replace('"', '""') + '"'


def data_sqlite(look):
    uri = "file:" + str(look.path).replace("\\", "/").replace("?", "%3f") + "?mode=ro&immutable=1"
    if not uri.startswith("file:/") and not uri.startswith("file:///"):
        uri = "file:///" + uri[5:]
    t0 = time.time()
    try:
        con = sqlite3.connect(uri, uri=True)
        con.execute("PRAGMA query_only=1")
        deadline = [t0 + SQLITE_BUDGET_S]
        con.set_progress_handler(lambda: 1 if time.time() > deadline[0] else 0, 20000)
        tabs = [r[0] for r in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
        info = {}
        unknown = []
        for t in tabs:
            q = qident(t)
            cols = [(r[1], r[2], r[5]) for r in con.execute(f"pragma table_info({q})")]
            try:
                cnt = con.execute(f"select count(*) from {q}").fetchone()[0]
            except sqlite3.OperationalError:
                cnt = None
                unknown.append(t)
                deadline[0] = time.time() + 1.0
            try:
                sample = [[cell_text(v) for v in r] for r in con.execute(f"select * from {q} limit 3")]
            except sqlite3.OperationalError:
                sample = []
            idx = []
            try:
                for r in con.execute(f"pragma index_list({q})"):
                    idx.append((r[1], [x[2] for x in con.execute(f"pragma index_info({qident(r[1])})")]))
            except sqlite3.Error:
                pass
            fks = [(r[3], r[2], r[4]) for r in con.execute(f"pragma foreign_key_list({q})")]
            info[t] = {"rows": cnt, "columns": cols, "sample": sample, "indexes": idx, "fks": fks}
        objs = Counter(r[0] for r in con.execute("select type from sqlite_master"))
        ver = con.execute("pragma user_version").fetchone()[0]
        pages = con.execute("pragma page_count").fetchone()[0] * con.execute("pragma page_size").fetchone()[0]
        jm = con.execute("pragma journal_mode").fetchone()[0]
        # declared foreign keys: do the children point at parents that exist?
        declared = [(t, f) for t, i in info.items() for f in i["fks"]]
        orphans = []
        if declared:
            deadline[0] = time.time() + 6.0
            try:
                cnt = Counter()
                for r in con.execute("pragma foreign_key_check"):
                    cnt[(r[0], r[2])] += 1
                    if sum(cnt.values()) >= 100000:
                        break
                orphans = [(c, p, n) for (c, p), n in cnt.most_common(6)]
            except sqlite3.Error:
                orphans = None
        # freshness: the oldest and newest value of a time-like column in the biggest tables
        fresh = []
        deadline[0] = time.time() + 4.0
        for t, i in sorted(info.items(), key=lambda kv: -(kv[1]["rows"] or 0))[:4]:
            tcols = [c for c in i["columns"] if TIME_COL_RE.search(c[0]) and (c[1] or "").upper() != "BLOB"][:2]
            for c in tcols:
                cq = qident(c[0])
                try:
                    lo, hi = con.execute(f"select min({cq}), max({cq}) from {qident(t)}").fetchone()
                except sqlite3.Error:
                    continue
                if hi is not None:
                    fresh.append(f"{t}.{c[0]} {when(lo)} .. {when(hi)}")
        con.close()
    except sqlite3.Error as e:
        look.flag("SQLITE-ERROR", "file", str(e)[:120], "")
        return
    look.fact("tables", tabs)
    look.fact("row_counts", {t: i["rows"] for t, i in info.items()})
    look.fact("foreign_keys_declared", len(declared))
    ntab = len(tabs)
    look.headline = f"SQLite, {ntab} tables, {core.human(pages)}"
    look.line(f"SQLite: {ntab} tables, {objs.get('index', 0)} indexes, {objs.get('view', 0)} views, {objs.get('trigger', 0)} triggers, user_version {ver}, read-only.", 90)
    ranked = sorted(info.items(), key=lambda kv: -(kv[1]["rows"] or 0))
    top = ranked[:8]
    look.line("Rows per table, biggest first: " + "; ".join(f"{t} {rows_fmt(i['rows'])}" for t, i in ranked[:14]) + (f"; +{ntab - 14} smaller" if ntab > 14 else "") + ".", 88)
    look.line("Columns of the biggest: " + " | ".join(f"{t}: " + ", ".join(f"{c[0]} {c[1] or '?'}" + (" PK" if c[2] else "") for c in i["columns"][:6]) + (f" +{len(i['columns']) - 6}" if len(i["columns"]) > 6 else "") for t, i in top[:3]), 80)
    blobs = [f"{t}.{c[0]}" for t, i in info.items() for c in i["columns"] if (c[1] or "").upper() == "BLOB"]
    if blobs:
        look.line("BLOB columns (vectors, images, files): " + ", ".join(blobs[:8]) + ".", 70)
    # foreign keys: the trap is the missing ones
    if declared:
        look.line(f"Foreign keys: {len(declared)} declared (" + ", ".join(f"{t}.{f[0]}->{f[1]}" for t, f in declared[:6]) + (f", +{len(declared) - 6}" if len(declared) > 6 else "") + ").", 86)
        if orphans:
            look.flag("ORPHAN-ROWS", ", ".join(f"{c}->{p}" for c, p, _ in orphans[:3]), f"{sum(n for *_, n in orphans)} child rows point at a parent that does not exist", "foreign_key_check failed: data was deleted or imported with keys off")
        elif orphans is not None:
            look.line("Foreign-key check: every declared key resolves (no orphan rows).", 60)
    else:
        rel = implicit_relations(info)
        look.line(f"Foreign keys: none declared in {ntab} tables" + (f"; links exist only by naming ({', '.join(rel[:6])}{', +' + str(len(rel) - 6) if len(rel) > 6 else ''}), so nothing stops orphan rows." if rel else "."), 86)
        if rel and ntab >= 3:
            look.flag("NO-FOREIGN-KEYS", f"{ntab} tables", f"0 declared; {len(rel)} implicit id links", "relationships are by naming only: verify with a join before trusting them")
    if fresh:
        look.line("Time range (min .. max): " + "; ".join(fresh[:5]) + ".", 78)
    empty = [t for t, i in info.items() if i["rows"] == 0]
    if empty:
        look.line(f"Empty tables: {', '.join(empty[:12])}.", 40)
    if unknown:
        look.flag("PARTIAL", "row counts", f"{len(unknown)} table(s) not counted in time: {', '.join(unknown[:4])}", "time cap reached")
    if jm.lower() == "wal":
        look.flag("WAL-PRESENT", "journal", "WAL mode", "recent writes may sit in the -wal file next to the database")
    md = []
    for t, i in ranked:
        has_idx = [(n, cs) for n, cs in i["indexes"] if not n.startswith("sqlite_autoindex")]
        md.append(f"{t}: {i['rows'] if i['rows'] is not None else '?'} rows. " + ", ".join(f"{c[0]} {c[1] or '?'}{' PK' if c[2] else ''}" for c in i["columns"][:16])
                  + (f" +{len(i['columns']) - 16} more" if len(i["columns"]) > 16 else "")
                  + (". idx " + ", ".join(f"{n}({','.join(map(str, cs))})" for n, cs in has_idx[:4]) if has_idx else "")
                  + (". fk " + ", ".join(f"{a}->{b}.{c}" for a, b, c in i["fks"]) if i["fks"] else "")
                  + (f". e.g. {' | '.join(', '.join(r[:6]) for r in i['sample'][:2])}" if i["sample"] else ""))
    # every row of every table through the field profiler (biggest first; one shared time budget), so counts, sums, distinct values
    # and group-bys are exact and `--more` has the full enumerations
    import dl_prof as P
    P.counts(look, [("tables", ntab), ("rows in all tables", sum(i["rows"] or 0 for i in info.values())), ("columns in all tables", sum(len(i["columns"]) for i in info.values())),
                    ("indexes", objs.get("index", 0)), ("views", objs.get("view", 0)), ("triggers", objs.get("trigger", 0)), ("empty tables", len(empty) or None)])
    t_all = time.time()
    budget = TABLE_PROFILE_S * (3 if look.deep else 1.5)
    if not look.quick:
        try:
            con = sqlite3.connect(uri, uri=True)
            con.execute("PRAGMA query_only=1")
            for t, i in ranked:
                left = budget - (time.time() - t_all)
                if not i["rows"]:
                    continue
                if left <= 1:
                    look.skip(f"profile of table {t}", "time budget for table profiles used up", None, f"--table {t}")
                    continue
                q, names = qident(t), [c[0] for c in i["columns"]]

                def rows(q=q):
                    return enumerate(con.execute(f"select * from {q}"), 1)
                try:
                    table_profile(look, f"Table {t}", names, rows, "row", i["rows"], 82 if t == ranked[0][0] else 60, 26, cap_s=max(1.0, left / 2))
                except sqlite3.Error as e:
                    look.fail(f"profile of table {t}", "sqlite3", e)
            con.close()
        except sqlite3.Error as e:
            look.fail("table profiles", "sqlite3", e)
    look.write_text("tables.md", "\n".join(md), "every table: rows, columns, indexes, foreign keys, 2 example rows", value=5, slice_cmd="--table NAME", inline=False if ntab > 6 else None)
    look.write_text("schema.json", json.dumps(info, indent=1, default=str), "tables, columns, row counts, example rows (json)", "json", inline=False)
    look.cmd("--table NAME", "profile of one table: nulls, distinct, min, max per column, indexes, foreign keys, 5 rows")


# ---------------------------------------------------------------- parquet / arrow
NUMERIC_TYPES = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT", "FLOAT", "DOUBLE", "DECIMAL")
PROFILE_TIMEOUT_S = 25.0


def fnum(x):
    if x is None:
        return "?"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)[:19]
    if v != v:
        return "nan"
    return num(v) if abs(v) >= 100 or v == int(v) else f"{v:.3g}"


def duck_profile(look, d, path, ncols, timeout=PROFILE_TIMEOUT_S):
    """DuckDB SUMMARIZE (one scan) plus one scan for outliers beyond q75 + 10 IQR. -> list of column dicts, or None when it failed."""
    import threading
    con = d.connect()
    p = str(path).replace("'", "''")
    timer = threading.Timer(timeout, con.interrupt)
    timer.start()
    try:
        rows = con.execute(f"summarize select * from read_parquet('{p}')").fetchall()
        cols = []
        for r in rows:
            name, typ, mn, mx, uniq, avg, std, q25, q50, q75, cnt, nullp = r[:12]
            cols.append(dict(name=name, type=typ, min=mn, max=mx, distinct=uniq, p25=q25, p50=q50, p75=q75, count=cnt, null_pct=float(nullp) if nullp is not None else 0.0, outliers=None))
        num_cols = [c for c in cols if c["type"].split("(")[0] in NUMERIC_TYPES and c["p25"] is not None and c["p75"] is not None]
        conds = []
        for c in num_cols:
            try:
                q1, q3 = float(c["p25"]), float(c["p75"])
            except (TypeError, ValueError):
                continue
            iqr = q3 - q1
            if iqr <= 0:
                continue
            col = '"' + c["name"].replace('"', '""') + '"'
            conds.append((c, f'count(*) filter (where {col} > {q3 + 10 * iqr!r} or {col} < {q1 - 10 * iqr!r})'))
        if conds:
            got = con.execute("select " + ", ".join(e for _, e in conds) + f" from read_parquet('{p}')").fetchone()
            for (c, _), n in zip(conds, got):
                c["outliers"] = int(n)
        return cols
    except Exception as e:
        look.fail("column profile (DuckDB)", "duckdb", e)
        return None
    finally:
        timer.cancel()
        con.close()


def pa_profile(look, pq, path, md):
    """pyarrow-only fallback: null count, min and max per column, read one column at a time (skipped above 30 M rows)."""
    import pyarrow.compute as pc
    if md.num_rows > 30_000_000:
        return None
    f = pq.ParquetFile(str(path))
    cols = []
    for fld in f.schema_arrow:
        try:
            arr = f.read(columns=[fld.name]).column(0)
            mm = pc.min_max(arr).as_py() if str(fld.type) not in ("binary", "large_binary") else {"min": None, "max": None}
            cols.append(dict(name=fld.name, type=str(fld.type), min=mm["min"], max=mm["max"], distinct=None, p25=None, p50=None, p75=None,
                             count=len(arr), null_pct=100.0 * arr.null_count / max(1, len(arr)), outliers=None))
        except Exception:
            continue
    return cols


def parquet_report(look, cols, nrows):
    lines = []
    for c in cols:
        bits = [c["type"].lower()]
        if c["null_pct"] >= 0.05:
            bits.append(f"{c['null_pct']:.0f}% null" if c["null_pct"] >= 1 else f"{c['null_pct']:.1f}% null")
        if c["min"] is not None and c["max"] is not None:
            if c["p50"] is not None and c["type"].split("(")[0] in NUMERIC_TYPES:
                bits.append(f"{fnum(c['min'])}..{fnum(c['max'])} (median {fnum(c['p50'])})")
            else:
                bits.append(f"{str(c['min'])[:19]}..{str(c['max'])[:19]}")
        if c.get("distinct") is not None and c["type"].split("(")[0] not in NUMERIC_TYPES:
            bits.append(f"~{U.compact(c['distinct'])} distinct")
        lines.append(f"{c['name']} " + ", ".join(bits))
        if c["null_pct"] >= 30:
            look.flag("NULL-HEAVY", c["name"], f"{c['null_pct']:.0f}% null", "a third or more of the values are missing")
        if c["outliers"]:
            look.flag("OUTLIER", c["name"], f"{c['outliers']} value(s) far outside the rest: max {fnum(c['max'])}, upper quartile {fnum(c['p75'])}", "a typo, a sentinel or a placeholder such as 999")
    return lines


def data_parquet(look):
    pa = look.mod("pyarrow")
    d = look.mod("duckdb")
    if pa:
        import pyarrow.parquet as pq
        f = pq.ParquetFile(str(look.path))
        md = f.metadata
        look.fact("rows", md.num_rows)
        look.fact("row_groups", md.num_row_groups)
        look.fact("columns", [fld.name for fld in f.schema_arrow])
        look.headline = f"Parquet, {rows_fmt(md.num_rows)} rows x {md.num_columns} columns"
        look.dims = f"{rows_fmt(md.num_rows)} rows"
        # min/max statistics: without them a reader cannot skip row groups and every filter scans the whole file
        have = total = 0
        codecs = set()
        for rg in range(min(md.num_row_groups, 64)):
            for c in range(md.num_columns):
                col = md.row_group(rg).column(c)
                total += 1
                codecs.add(str(col.compression).lower())
                if col.is_stats_set and col.statistics is not None and col.statistics.has_min_max:
                    have += 1
        per_rg = md.num_rows // max(1, md.num_row_groups)
        look.line(f"Parquet: {md.num_rows:,} rows, {md.num_columns} columns, {md.num_row_groups} row group(s) of about {rows_fmt(per_rg)} rows, "
                  f"{'/'.join(sorted(codecs))}, written by {md.created_by or 'unknown'}.", 90)
        if total and have < total:
            look.flag("NO-STATISTICS", "row groups", f"min/max statistics missing in {total - have} of {total} column chunks", "readers cannot skip row groups: every filter scans the whole file")
        elif total:
            look.line("Row-group statistics (min/max) are present: filters can skip row groups.", 40)
        cols = None
        if d:
            cols = duck_profile(look, d, look.path, md.num_columns, 8.0 if look.quick else PROFILE_TIMEOUT_S)
        if cols is None and not look.quick:
            cols = pa_profile(look, pq, look.path, md)
        if cols is None and have == total and total:   # quick: the statistics already in the footer
            cols = []
            for c in range(md.num_columns):
                nn = mn = mx = None
                nulls = 0
                for rg in range(md.num_row_groups):
                    st = md.row_group(rg).column(c).statistics
                    if st is not None and st.has_min_max:
                        mn = st.min if mn is None else min(mn, st.min)
                        mx = st.max if mx is None else max(mx, st.max)
                        nulls += st.null_count or 0
                fld = f.schema_arrow.field(c)
                cols.append(dict(name=fld.name, type=str(fld.type), min=mn, max=mx, distinct=None, p25=None, p50=None, p75=None, count=md.num_rows,
                                 null_pct=100.0 * nulls / max(1, md.num_rows), outliers=None))
        if cols:
            rep = parquet_report(look, cols, md.num_rows)
            look.line("Columns (name type, null %, min..max (median), ~distinct): " + "; ".join(rep[:30]) + (f"; +{len(rep) - 30} more in profile.json" if len(rep) > 30 else "") + ".", 86)
            look.write_text("profile.json", json.dumps(cols, indent=1, default=str), "per-column null %, min, max, quartiles, outlier count", "json", inline=False)
            look.fact("column_profile", True)
        else:
            look.line("Columns: " + ", ".join(f"{fld.name} {fld.type}" for fld in f.schema_arrow) + ".", 86)
            if look.quick:
                look.skip("column profile (null %, range, outliers)", "skipped at the quick tier: run again with --tier standard", None, "")
        import dl_prof as P
        P.counts(look, [("rows", md.num_rows), ("columns", md.num_columns), ("row groups", md.num_row_groups)])
        if not look.quick:
            names = [fld.name for fld in f.schema_arrow]

            def rows():
                k = 0
                for b in pq.ParquetFile(str(look.path)).iter_batches(batch_size=65536):
                    for r in zip(*[c.to_pylist() for c in b.columns]):
                        k += 1
                        yield k, r
            try:
                table_profile(look, "Rows", names, rows, "row", md.num_rows, 84, 28, cap_s=TABLE_PROFILE_S * (3 if look.deep else 1))
            except Exception as e:
                look.fail("exact row profile", "pyarrow", e)
        t = f.read_row_group(0).slice(0, 5).to_pylist() if md.num_row_groups else []
        look.write_text("schema.json", json.dumps({"schema": [[fld.name, str(fld.type)] for fld in f.schema_arrow], "rows": md.num_rows, "head": t}, indent=1, default=str), "schema and 5 rows", "json", inline=False)
        look.cmd('--sql "SELECT ..."', "any question on the rows: counts, filters, group-bys (the table is `t`)")
        return
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
    import dl_prof as P
    try:
        root = ET.fromstring(raw)
    except Exception as e:
        look.flag("INVALID-XML", "file", f"{type(e).__name__}: {e}"[:120], "")
        P.text_profile(look, raw.decode("utf-8", "replace"), 70, "Text")
        return

    def local(t):
        return t.rsplit("}", 1)[-1] if isinstance(t, str) else str(t)
    counts, attrs, depth, texts = Counter(), Counter(), 0, 0
    parent_of = Counter()
    stack = [(root, 0, "")]
    while stack:
        el, d, par = stack.pop()
        depth = max(depth, d)
        t = local(el.tag)
        counts[t] += 1
        parent_of[(par, t)] += 1
        attrs.update(f"{t}@{local(a)}" for a in el.attrib)
        if (el.text or "").strip():
            texts += 1
        for c in el:
            stack.append((c, d + 1, t))
    root_tag = local(root.tag)
    look.fact("root", root_tag)
    look.fact("element_counts", dict(counts.most_common(40)))
    look.line(f"XML: root <{root_tag}>, {sum(counts.values()):,} elements of {len(counts)} kinds, depth {depth}. Elements: " + ", ".join(f"{k} ({v:,})" for k, v in counts.most_common(30)), 90)
    P.counts(look, [("elements", sum(counts.values())), ("element kinds", len(counts)), ("attributes", sum(attrs.values())), ("elements with text", texts),
                    ("max depth", depth), ("root children", len(list(root)))], 94, "XML counts")
    if attrs:
        look.line("Attributes (element@name, count): " + ", ".join(f"{k} ({v:,})" for k, v in attrs.most_common(40)), 60)
    # records: the most repeated element that has attributes or children, each as {@attr, child: text}
    best = None
    for (par, t), n in sorted(parent_of.items(), key=lambda kv: -kv[1]):
        if n < 2:
            break
        els = [e for e in root.iter() if local(e.tag) == t]
        if els and (els[0].attrib or len(els[0])):
            best = (t, els)
            break
    if not best:
        return

    def rec_of(e):
        r = {"@" + local(a): v for a, v in e.attrib.items()}
        for c in e:
            k = local(c.tag)
            if len(c) and not (c.text or "").strip():
                r[k] = rec_of(c)
                continue
            val = (c.text or "").strip()
            if k in r:
                r[k] = (r[k] if isinstance(r[k], list) else [r[k]]) + [val]
            else:
                r[k] = val
            for a, v in c.attrib.items():
                r[f"{k}@{local(a)}"] = v
        if (e.text or "").strip() and not len(e):
            r["#text"] = e.text.strip()
        return r
    t, els = best
    recs = [(i, rec_of(e)) for i, e in enumerate(els)]
    p, extra = P.profile(recs, True, "element")
    P.emit(look, p, extra, f"<{t}> records ({len(els):,} elements, numbered from 0 in document order)", 86, 30)
    if len(recs) <= 3000:
        rows = [f"[{i}] " + "; ".join(f"{k}={P.short(x if not isinstance(x, P.Multi) else ', '.join(map(str, x)), 60)}" for k, x in P.flat_of(r).items() if not k.endswith(P.LEN)) for i, r in recs]
        for k in range(0, len(rows), 20):
            look.line(f"<{t}> records:\n" + "\n".join(rows[k:k + 20]), 18, "records")


def data_toml(look):
    import dl_prof as P
    text = open(look.path, "rb").read().decode("utf-8", "replace")
    try:
        import tomllib
    except ImportError:
        return data_text_struct(look)
    try:
        v = tomllib.loads(text)
    except Exception as e:
        look.flag("INVALID-TOML", "file", str(e)[:120], "")
        P.text_profile(look, text, 70, "Text")
        return
    look.write_text("skeleton.json", json.dumps(skeleton(v), indent=1), "keys and types tree", "json")
    tables = re.findall(r"(?m)^\s*\[([^\[\]]+)\]\s*(?:#.*)?$", text)
    arrays = re.findall(r"(?m)^\s*\[\[([^\[\]]+)\]\]\s*(?:#.*)?$", text)
    look.line(f"TOML: {len(v)} top-level keys ({', '.join(v)}); {len(tables)} [tables], {len(arrays)} [[array-of-tables]] entries"
              + (f" ({', '.join(f'{k} x{c}' for k, c in Counter(arrays).most_common(8))})" if arrays else "") + f"; {len(text.splitlines())} lines.", 90)
    look.fact("keys", list(v))
    P.doc_profile(look, v, "TOML")


def data_text_struct(look):
    """YAML (and any key: value text): parsed with PyYAML when present (every document), else a line-based outline."""
    import dl_prof as P
    text = open(look.path, "rb").read(32 << 20).decode("utf-8", "replace")
    yaml = look.mod("yaml")
    docs = None
    if yaml is not None:
        try:
            docs = list(yaml.safe_load_all(text))
        except Exception as e:
            look.flag("INVALID-YAML", "file", f"{type(e).__name__}: {e}"[:140], "")
    keys = re.findall(r"(?m)^([A-Za-z_][\w-]*):", text)
    nl = len(text.splitlines())
    look.line((f"{look.subtype.upper()} text file, {nl:,} lines" + (f", {len(docs)} document(s)" if docs is not None else "") + "; top-level keys: " + ", ".join(dict.fromkeys(keys)))
              if keys else f"{look.subtype} text file, {nl:,} lines.", 90)
    look.fact("keys", list(dict.fromkeys(keys)))
    if docs:
        v = docs[0] if len(docs) == 1 else docs
        P.doc_profile(look, v, "YAML" if look.subtype == "yaml" else "Document")
        return
    if yaml is None:
        look.skip("YAML parse (types, nested keys, lists)", "python package yaml not importable" if not look.no_tools else "disabled by --no-tools", "yaml")
    look.excerpt("First lines", text, 12)
    P.text_profile(look, text, 70, "Text")
    ind = Counter(len(x) - len(x.lstrip(" ")) for x in text.splitlines() if x.strip() and not x.lstrip().startswith("#"))
    items = sum(1 for x in text.splitlines() if x.lstrip().startswith("- "))
    P.counts(look, [("list items (- )", items), ("indent levels", len(ind)), ("comment lines", sum(1 for x in text.splitlines() if x.lstrip().startswith("#")))], 80, "Structure counts")


# ---------------------------------------------------------------- exact table profile (sqlite tables, parquet): fix round 4
TABLE_PROFILE_S = 60.0
TABLE_LISTING_ROWS = 400


def plain(v):
    """A database or Arrow value as the profiler counts it: numbers stay numbers, Decimal becomes float, times and bytes become text."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    try:
        import decimal
        if isinstance(v, decimal.Decimal):
            return float(v)
    except ImportError:
        pass
    if isinstance(v, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(v))} bytes>"
    return str(v)


def table_profile(look, what, names, rows, label="row", total=None, key_pri=84, more_pri=28, cap_s=TABLE_PROFILE_S, listing=True):
    """Every row of one table through the field profiler and the group-by pass. rows: a callable giving (index, values) each time it
    is called (walked twice). Exact over every row unless the time cap stops it, which is flagged with the row it stopped at."""
    import dl_prof as P
    p = P.Profiler(False, label)
    cols = p.columns(list(names))
    t0, stopped, first = time.time(), None, []
    for k, (idx, vals) in enumerate(rows()):
        vals = [plain(v) for v in vals]
        p.add_row(cols, vals, idx)
        if listing and len(first) < TABLE_LISTING_ROWS:
            first.append((idx, vals))
        if k % 2000 == 0 and time.time() - t0 > cap_s:
            stopped = idx
            break
    if not p.n:
        return None
    sp = P.SecondPass(p)
    for k, (idx, vals) in enumerate(rows()):
        sp.add_row(list(names), [plain(v) for v in vals], idx)
        if stopped is not None and idx >= stopped:
            break
        if k % 2000 == 0 and time.time() - t0 > 2 * cap_s:
            break
    if stopped is not None:
        look.flag("PARTIAL", what, f"profile stopped at {label} {stopped:,} of {total:,}" if total else f"profile stopped at {label} {stopped:,}",
                  "time cap: the counts below cover the rows up to there only")
    P.emit(look, p, sp.lines(), f"{what} ({label}s numbered from 1" + (", every row read" if stopped is None else ", PARTIAL") + ")", key_pri, more_pri, 24,
           prefix=f"{what}: " if what.startswith("Table ") else "")
    if listing and first and (total or p.n) <= TABLE_LISTING_ROWS:
        rws = [f"{label} {i}: " + "; ".join(f"{n}={P.short(v, 60)}" for n, v in zip(names, vals)) for i, vals in first]
        for k in range(0, len(rws), 20):
            look.line(f"{what}, {label}s:\n" + "\n".join(rws[k:k + 20]), 16, "records")
    return p
