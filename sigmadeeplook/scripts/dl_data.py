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
TAIL_ROWS = 20   # the last rows of a table, printed whole in step 2 (the file content shows its head)
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


def look_data(look):
    st = look.subtype
    fn = {"csv": data_csv, "tsv": data_csv, "json": data_json, "jsonl": data_jsonl, "sqlite": data_sqlite, "parquet": data_parquet,
          "arrow": data_arrow, "avro": lambda lk: __import__("dl_adapt").look_avro(lk), "xml": data_xml, "yaml": data_text_struct, "toml": data_toml,
          "ini": lambda lk: __import__("dl_conf").look_ini(lk), "reg": lambda lk: __import__("dl_reg").look_reg(lk), "pcap": lambda lk: __import__("dl_pcap").look_pcap(lk),
          "pcapng": lambda lk: __import__("dl_pcap").look_pcap(lk), "dbf": lambda lk: __import__("dl_dbf").look_dbf(lk)}.get(st) or getattr(__import__("dl_tab2"), "look_" + st, None) or getattr(__import__("dl_legacy"), "look_" + st, None) or getattr(__import__("dl_misc"), "look_" + st, data_text_struct)
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


CSV_READ_CAP = U.byte_cap("CSV", 256 << 20)   # the standard tier holds this many bytes of a table in memory; a bigger file is read as far as the cap, flagged PARTIAL, with the whole file's line count


def whole_file_stream(path, chunk=16 << 20):
    """(lines in the file, [line numbers where the header row appears again]) over the WHOLE file in bounded memory (chunks), from bytes alone."""
    done, first, pat, repeats, carry, eof, body = 0, None, None, [], b"", False, b""   # done = newlines before the current chunk
    with open(path, "rb") as f:
        while not eof:
            blk = f.read(chunk)
            eof = len(blk) < chunk
            buf = carry + blk
            cut = len(buf) if eof else buf.rfind(b"\n") + 1   # only whole lines are searched; the unfinished last line moves to the next chunk
            body, carry = buf[:cut], buf[cut:]
            if first is None and body:
                first = (body[:body.find(b"\n")] if b"\n" in body else body).rstrip(b"\r")
                if first.startswith(b"\xef\xbb\xbf"):
                    first = first[3:]   # the byte-order mark sits before the first header only
                pat = re.compile(b"^" + re.escape(first) + rb"\r?$", re.M) if first else None
            if pat is not None:
                for m in pat.finditer(body):
                    ln = done + body.count(b"\n", 0, m.start()) + 1
                    if ln > 1:
                        repeats.append(ln)
            done += body.count(b"\n")
    return done + (1 if body and not body.endswith(b"\n") else 0), repeats


def data_csv(look):
    with open(look.path, "rb") as fh:
        raw = fh.read(CSV_READ_CAP)
    read_cut = look.size > len(raw)   # the file is longer than what is held in memory
    quick_cut = look.quick and len(raw) > QUICK_BYTES
    whole_lines = whole_repeats = None
    if quick_cut or read_cut:
        whole_lines, whole_repeats = whole_file_stream(look.path)
        limit = QUICK_BYTES if quick_cut else len(raw)
        cut = raw.rfind(b"\n", 0, limit)
        raw = raw[:cut + 1] if cut > 0 else raw[:limit]
    prefix_cut = quick_cut or read_cut
    import dl_delim as D
    text, enc = D.sniff_encoding(raw)
    if enc not in ("utf-8", "utf-8-sig") and not enc.startswith(("utf-16", "utf-32")):
        look.flag("ENCODING", "file", f"not valid UTF-8; read as {D.LEGACY_LABELS.get(enc, enc)} (picked by how real the letters look)", "accents may be wrong if the real encoding is another one")
    elif enc == "utf-8" and chr(0xfffd) in text:
        look.flag("ENCODING", "file", f"UTF-8 with {text.count(chr(0xfffd))} undecodable byte(s), shown as U+FFFD", "the rest of the file is read as UTF-8")
    if raw.startswith(b"\xef\xbb\xbf"):
        look.flag("BOM", "file", "UTF-8 byte-order mark", "some tools keep it in the first column name")
    delim, mode_n, share = D.sniff_dialect(text, "\t" if look.subtype == "tsv" else ",")
    if look.subtype in ("csv", "tsv"):
        look.subtype = "tsv" if delim == "\t" else "csv"
    off = 0   # physical lines before the table (a title block above the header row); every line number below adds it
    region = None if prefix_cut else D.table_region(text, delim, mode_n)
    if region:
        text, off = region_facts(look, region, delim)
    first_rec = next(csv.reader(io.StringIO(text[:200000], newline=""), delimiter=delim), [])
    dec_cols = D.decimal_comma_columns(text, delim, len(first_rec))
    norm = D.normalizer(dec_cols)
    look.fact("decimal_comma_columns", [first_rec[i] for i in sorted(dec_cols) if i < len(first_rec)])
    look.line(D.describe(enc, delim, mode_n, share, dec_cols, first_rec), 93, "dialect")
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    t0 = time.time()
    header, rows, rejects, n, tail, prof, repeats = None, [], [], 0, [], [], []
    ncols, partial = 0, False
    import dl_prof as P
    gp, gcols = P.Profiler(True, "line"), None
    import dl_listcol
    lcols = None
    for rec in rd:
        if header is None:
            header = rec
            ncols = len(header)
            prof = [ColProfile(h, i == 0) for i, h in enumerate(header)]
            gcols = gp.columns([h.lstrip("﻿").strip() or f"column {i + 1}" for i, h in enumerate(header)])
            lcols = dl_listcol.ListCols(header)
            continue
        if len(rec) != ncols:
            n += 1
            if len(rejects) < 100:
                rejects.append((rd.line_num + off, len(rec), rec))
            continue
        if rec == header:
            repeats.append(rd.line_num + off)
            continue
        orig = rec
        if norm:
            rec = norm(rec)
        n += 1
        ln = rd.line_num + off
        for i in range(ncols):
            prof[i].add(rec[i], ln)
        gp.add_row(gcols, rec, ln)
        lcols.add_row(rec)
        if len(rows) < SAMPLE_ROWS:
            rows.append(rec)
        tail.append((ln, orig))
        if len(tail) > TAIL_ROWS:
            tail.pop(0)
        if time.time() - t0 > TIME_CAP:
            partial = True
            look.flag("PARTIAL", "row count", f"stopped after {n} rows", "time cap reached; counts are lower bounds")
            break
    header = header or []
    nrej = len(rejects)
    profiled = n
    if prefix_cut:   # rows and repeated headers come from the whole file's bytes; the column profile from its first rows
        repeats = list(whole_repeats)
        n = max(0, whole_lines - 1 - len(whole_repeats))
        tail = []
        if quick_cut:
            look.flag("QUICK-SAMPLE", "column profile", f"first {profiled} of about {n} rows", "quick tier: distinct counts, outliers and duplicate keys cover the first rows only; run --tier standard for the full pass")
        else:
            look.flag("PARTIAL", "file", f"read the first {len(raw):,} of {look.size:,} bytes ({100 * len(raw) / look.size:.0f} %): {profiled:,} of about {n:,} rows profiled",
                      "every sum, mean, min, max, distinct count, top value and outlier below covers those first rows only; the row count is the line count of the whole file")
    look.fact("encoding", enc)
    look.fact("delimiter", delim)
    look.fact("rows", n)
    look.fact("columns", len(header))
    look.fact("column_names", header)
    look.fact("rejects", nrej)
    look.headline = f"{look.subtype.upper()}, {'about ' if read_cut else ''}{n:,} rows x {len(header)} columns" + (f" (PARTIAL: first {profiled:,} rows profiled)" if read_cut else "")
    look.dims = f"{U.compact(n)} rows"
    if prefix_cut:
        look.line(f"Delimited table: about {n:,} data rows (line count over the whole file), {len(header)} columns, delimiter {delim!r}, encoding {enc}, {nrej} reject rows in the part profiled. "
                  + (f"Column profile: first {profiled:,} rows only." if quick_cut else f"PARTIAL: only the first {len(raw):,} of {look.size:,} bytes ({profiled:,} rows) were profiled; every figure below is for those rows, not for the whole file."))
    else:
        look.line(f"Delimited table: {n:,} data rows, {len(header)} columns, delimiter {delim!r}, encoding {enc}, {nrej} reject rows (wrong field count). "
                  + (f"PARTIAL: rows were read until the time cap ({n:,} rows); every figure below is a lower bound for the part read." if partial else "Every row was read; the profile below is a full pass, not a sample."), 38)
    total_ok = sum(prof[0].kinds.values()) if prof else 0
    notes = profile_findings(look, header, prof, total_ok, repeats)
    schema = [p.summary(total_ok) for p in prof]
    look.write_text("schema.json", json.dumps(schema, indent=1, default=str), ("per-column profile over the first rows only (PARTIAL read)" if read_cut else "per-column profile over every row") + ": type mix, empty %, distinct, range, median, top values", "json")
    notes = [n for n in notes if "empty" in n]   # every other finding is a flag and is listed once, under Watch out; the empty % sits in each column row
    if prof:   # one legend, then one compact row per column, exact counts over every row (positions are file line numbers)
        extra = csv_second_pass(look, text, delim, header, gp, norm=norm, line_off=off) if gp.n else []
        crow = gp.field_lines()
        legend = COLUMN_LEGEND if not (prefix_cut or partial) else COLUMN_LEGEND.replace("every count is exact over every row", f"every count is exact over the {profiled:,} rows profiled only (PARTIAL read)")
        if gp.last_line():
            look.line(gp.last_line(), 85, "last")
            if gp.n == n and not partial:   # row numbers at fixed positions only when every row was profiled
                gp.marks_facts(look, 74)
        look.line(legend + chr(10) + chr(10).join(crow[:40]) + (f"{chr(10)}... {len(crow) - 40} more columns below" if len(crow) > 40 else ""), 86, "profile")
        if len(crow) > 40:
            look.line("More columns:" + chr(10) + chr(10).join(crow[40:]), 36, "profile")
        miss = sum(f.nulls + f.empties for f in gp.fields.values())
        P.counts(look, [("data rows", n), ("columns", len(header)), ("rows profiled", gp.n if gp.n != n else None), ("reject rows", nrej), ("repeated header rows", len(repeats) or None),
                        ("empty or null cells", miss), ("complete rows (no empty cell)", complete_rows(text, delim, ncols) if not prefix_cut and n <= 2_000_000 else None)])
        lcols.emit(look)
        for ln_ in gp.stats_lines():
            look.line(ln_, 34, "aggregates")
        for ln_ in extra:
            look.line(ln_, 32, "aggregates")
        for ln_ in gp.enum_lines():
            look.line(ln_, 30, "values")
    if (enc not in ("utf-8", "utf-8-sig") or norm or delim not in (",", "\t") or look.facts.get("unpacked_from")) and not prefix_cut and len(text) <= 200 << 20:
        write_table_copy(look, text, delim, ncols, norm)
    import dl_sample
    if len(tail) > 1 and not prefix_cut:   # the content shows the head of the file; its end is shown here, as the file has it
        look.line(f"Last {len(tail)} rows (lines {tail[0][0]}-{tail[-1][0]} of {n:,} rows; as the file has them, after the header row):" + chr(10)
                  + chr(10).join(f"{ln_}: " + P.short(csv_line(r, delim), 240) for ln_, r in tail), 70, "tail")
    dl_sample.build_sample(look, text, delim, header, prof, n, repeats, [r for _, r in tail[-5:]], rows, partial or prefix_cut, line_off=off)
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


def csv_line(rec, delim):
    """A record written back as one delimited line, quoted where the file had to quote it."""
    buf = io.StringIO()
    csv.writer(buf, delimiter=delim, lineterminator="").writerow(rec)
    return buf.getvalue()


def region_facts(look, region, delim, cap=60):
    """A table inside a text (fix round 10): print where it sits and every line around it (the title block above, the totals and notes
    below: a stated total is a fact the rows cannot give), then -> (the table's own text, physical lines before it)."""
    lines, head, end = region
    body = "".join(lines[head:end])
    pre = [(i + 1, ln.strip()) for i, ln in enumerate(lines[:head]) if ln.strip()]
    post = [(i + 1, ln.strip()) for i, ln in enumerate(lines[end:], end) if ln.strip()]
    look.line(f"Table inside the text: header row at line {head + 1}, table lines {head + 2}-{end}; {head} line(s) before it (title block), "
              f"{len(lines) - end} line(s) after it (totals and notes). Rows, columns and counts below are the table's; the lines around it are printed whole.", 95, "structure")
    look.fact("table_lines", [head + 1, end])

    import dl_prof as P
    nl = chr(10)

    def show(items):
        return nl.join(f"{i}: {P.short(t, 240)}" for i, t in items[:cap]) + (f"{nl}... {len(items) - cap} more lines" if len(items) > cap else "")
    if post:
        look.line(f"Lines after the table ({len(post)} non-blank; totals and notes as the file states them):{nl}" + show(post), 94, "tail")
    if pre:
        look.line(f"Lines before the table ({len(pre)} non-blank; title block):{nl}" + show(pre), 92, "structure")
    return body, head


def write_table_copy(look, text, delim, ncols, norm):
    """The table as plain UTF-8 comma CSV with dot decimals (internal: --sql and --ask read it; never printed)."""
    p = look.path_for("table.utf8.csv")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
        for k, rec in enumerate(rd):
            w.writerow(norm(rec) if norm and k and len(rec) == ncols else rec)
    look.add(p, "internal", "the table as UTF-8 comma CSV with dot decimals")
    look.fact("table_copy", str(p))


def complete_rows(text, delim, ncols):
    """Rows with no empty cell (and the right field count)."""
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    next(rd, None)
    return sum(1 for r in rd if len(r) == ncols and all(c.strip() for c in r))


def csv_second_pass(look, text, delim, header, gp, cap_s=40.0, norm=None, line_off=0):
    """Group-by counts and sums and the top / bottom rows by each number (one more pass over the rows, time-capped).
    `line_off`: physical lines of the file before `text` (a title block above the table)."""
    import dl_prof as P
    sp = P.SecondPass(gp)
    names = [h.lstrip("﻿").strip() or f"column {i + 1}" for i, h in enumerate(header)]
    rd = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    next(rd, None)
    t0 = time.time()
    for k, rec in enumerate(rd):
        if len(rec) != len(header) or rec == header:
            continue
        sp.add_row(names, norm(rec) if norm else rec, rd.line_num + line_off)
        if k % 5000 == 0 and time.time() - t0 > cap_s:
            look.flag("PARTIAL", "group-by and top rows", f"stopped at line {rd.line_num + line_off}", "time cap: the group sums cover the rows up to that line only")
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


JSON_READ_CAP = U.byte_cap("JSON", 64 << 20)   # a document is parsed whole up to this size; a bigger one is read as far as the cap and flagged PARTIAL
_CUT = object()


def salvage_json(text, max_depth=64):
    """The complete elements of a JSON document that was cut off at an arbitrary byte (or is broken part-way): arrays and objects keep every
    element that parsed, the last unfinished one is kept as far as it goes. Returns None when not even the first value starts."""
    dec = json.JSONDecoder()
    n = len(text)

    def skip(i):
        while i < n and text[i] in " \t\r\n":
            i += 1
        return i

    def value(i, depth):
        i = skip(i)
        if i >= n:
            return _CUT, n
        if text[i] in "[{" and depth < max_depth:
            return container(i, depth)
        try:
            return dec.raw_decode(text, i)
        except ValueError:
            return _CUT, n

    def container(i, depth):
        is_list = text[i] == "["
        out = [] if is_list else {}
        i += 1
        while True:
            i = skip(i)
            if i >= n:
                return out, n
            c = text[i]
            if c == ",":
                i += 1
                continue
            if c in "]}":
                return out, i + 1
            if is_list:
                v, i = value(i, depth + 1)
                if v is _CUT:
                    return out, n
                out.append(v)
            else:
                try:
                    k, i = dec.raw_decode(text, i)
                except ValueError:
                    return out, n
                i = skip(i)
                if i >= n or text[i] != ":" or not isinstance(k, str):
                    return out, n
                v, i = value(i + 1, depth + 1)
                if v is _CUT:
                    return out, n
                out[k] = v
    v, _ = value(0, 0)
    return None if v is _CUT else v


def looks_jsonl(text):
    """True when the text is one JSON value per line (two lines or more, 80 % of the first 50 parse)."""
    lines = [x for x in text.splitlines() if x.strip()]
    ok = 0
    for x in lines[:50]:
        try:
            json.loads(x)
            ok += 1
        except ValueError:
            pass
    return len(lines) >= 2 and ok >= 0.8 * min(50, len(lines))


def data_json(look):
    with open(look.path, "rb") as fh:
        raw = fh.read(JSON_READ_CAP)
    cut = look.size > len(raw)
    text, enc = __import__("dl_delim").sniff_encoding(raw)
    try:
        if cut:
            v = None if looks_jsonl(text) else salvage_json(text)
            if v is None:
                raise ValueError("the first value does not start inside the part read")
            look.flag("PARTIAL", "file", f"read the first {len(raw):,} of {look.size:,} bytes ({100 * len(raw) / look.size:.0f} %)",
                      "keys, types, array lengths and every count below cover the complete elements inside that part only; lengths are lower bounds")
        else:
            v = json.loads(text)
    except ValueError as e:
        if looks_jsonl(text):   # one JSON value per line: JSON Lines with a .json name
            look.subtype = "jsonl"
            look.flag("JSON-LINES", "file", "one JSON value per line, not one document", "parsed as JSON Lines")
            return data_jsonl(look)
        if cut:   # the part read could not be parsed, but the file itself was not shown to be invalid
            look.flag("PARTIAL", "file", f"read the first {len(raw):,} of {look.size:,} bytes ({100 * len(raw) / look.size:.0f} %) and could not parse them: {str(e)[:100]}", "the document is larger than the read limit, so no verdict on its validity")
            look.line("JSON larger than the read limit; the part read did not parse. First lines below.")
        else:
            look.flag("INVALID-JSON", "file", str(e)[:120], "")
            look.line("Invalid JSON; first lines below.")
        look.excerpt("First lines", text, 10)
        import dl_prof as P
        P.text_profile(look, text, 70, "Text")
        return
    import dl_geo
    if dl_geo.is_geojson(v):   # GeoJSON: features, geometry types, bounding box, lengths and areas lead
        try:
            dl_geo.geojson_facts(look, v)
        except Exception as e:
            look.fail("GeoJSON totals", "stdlib", e)
    sk = skeleton(v)
    look.fact("json_top", type(v).__name__)
    look.write_text("skeleton.json", json.dumps(sk, indent=1), "keys and types tree, array lengths", "json")
    look.line(f"JSON {type(v).__name__}" + (f" with {'at least ' if cut else ''}{len(v)} items" if hasattr(v, "__len__") else "") + f", encoding {enc}" + (" (PARTIAL: the part read)." if cut else "."))
    look.excerpt("Skeleton", json.dumps(sk, indent=1), 25, 1800, 40)
    import dl_prof as P
    P.doc_profile(look, v, "JSON", 55 if dl_geo.is_geojson(v) else 92)


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
    import dl_colmeta as CM
    try:
        ft = CM.parquet_footer(look.path)
    except Exception as e:   # a damaged footer: pyarrow below says more
        ft = None
        look.fail("Parquet footer (stdlib Thrift reader)", "stdlib", e)
    if ft:
        look.fact("file_metadata", ft["kv"])
        look.fact("created_by", ft["created_by"])
        look.line(CM.kv_line(ft["kv"], f"File key/value metadata (footer; created_by {ft['created_by'] or 'not set'}, format version {ft['version']})"), 94, "props")
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
    if ft:   # the footer alone: rows, schema, row groups, codecs
        import dl_prof as P
        look.fact("rows", ft["rows"])
        look.fact("columns", [s[0] for s in ft["schema"]])
        look.headline = f"Parquet, {rows_fmt(ft['rows'] or 0)} rows x {len(ft['schema'])} columns"
        look.dims = f"{rows_fmt(ft['rows'] or 0)} rows"
        P.counts(look, [("rows", ft["rows"]), ("columns (leaf and group)", len(ft["schema"])), ("row groups", len(ft["row_groups"]))], 96)
        look.line("Schema (name type repetition): " + "; ".join(" ".join(x for x in s if x) for s in ft["schema"][:80]) + f". Codecs: {', '.join(ft['codecs']) or '?'}; rows per row group: "
                  + ", ".join(f"{r:,}" for r, _ in ft["row_groups"][:20]), 92)
    look.skip("parquet column values (profile, sums, rows)", "pyarrow and duckdb not importable" if not look.no_tools else "disabled by --no-tools", "pyarrow")


def data_arrow(look):
    if not look.need_mod("pyarrow", "arrow schema and rows"):
        look.line("Arrow IPC file; schema needs pyarrow.")
        return
    import pyarrow as pa
    with pa.memory_map(str(look.path)) as src:
        r = pa.ipc.open_file(src)
        look.fact("columns", [f.name for f in r.schema])
        look.line(f"Arrow IPC: {r.num_record_batches} batches. Columns: " + ", ".join(f"{f.name} ({f.type})" for f in r.schema))
        import dl_colmeta as CM
        kv = {k.decode("utf-8", "replace"): v.decode("utf-8", "replace") for k, v in (r.schema.metadata or {}).items()}
        look.fact("file_metadata", kv)
        look.line(CM.kv_line(kv, "Schema key/value metadata"), 94, "props")
        fm = [(f.name, {k.decode("utf-8", "replace"): v.decode("utf-8", "replace") for k, v in f.metadata.items()}) for f in r.schema if f.metadata]
        if fm:
            look.line("Field metadata: " + " | ".join(CM.kv_line(m, n) for n, m in fm[:20]), 80, "props")


# ---------------------------------------------------------------- xml, yaml, toml
XML_READ_CAP = U.byte_cap("XML", 20 << 20)   # elements are read as far as this many bytes; a bigger file is flagged PARTIAL
ENTITY_DECL = re.compile(rb"""<!ENTITY\s+(?:%\s+)?([^\s"']+)\s+(?:SYSTEM|PUBLIC|"([^"]*)"|'([^']*)')""", re.I)
ENTITY_REF = re.compile(r"[&%]([A-Za-z_][\w.:-]*);")


def xml_entity_danger(raw):
    """None, or the reason an XML must not be expanded: an entity that refers to itself, expands past 1 million characters, or would put more
    than 50 million characters into the document. A harmless declaration (a copyright sign, a company name) is no reason to refuse the file."""
    values = {}
    for m in ENTITY_DECL.finditer(raw):
        v = m.group(2) if m.group(2) is not None else m.group(3)
        if v is not None:
            values[m.group(1).decode("latin-1")] = v.decode("utf-8", "replace")
    if not values:
        return None
    memo, inf = {}, float("inf")

    def size(name, stack):
        if name in memo:
            return memo[name]
        if name in stack:
            return inf
        if name not in values:
            return 1   # a built-in or external reference: one unit
        v = values[name]
        memo[name] = len(ENTITY_REF.sub("", v)) + sum(size(r, stack | {name}) for r in ENTITY_REF.findall(v))
        return memo[name]
    total = 0
    for name in values:
        sz = size(name, frozenset())
        if sz == inf:
            return f"entity {name!r} refers to itself"
        if sz > 1_000_000:
            return f"entity {name!r} expands to {sz:,} characters"
        total += sz * raw.count(b"&" + name.encode("latin-1") + b";")
    if total > 50_000_000:
        return f"the entities would add {total:,} characters to the document"
    return None


def data_xml(look):
    with open(look.path, "rb") as fh:
        raw = fh.read(XML_READ_CAP)
    cut = look.size > len(raw)
    danger = xml_entity_danger(raw)
    if danger:
        look.flag("ENTITY-DECLARATION", "file", f"DTD entity expansion: {danger}", "not parsed: that expansion can blow up memory (a billion-laughs file); read it as text")
        look.exit_code = 2
        look.excerpt("First lines", raw[:1500].decode("utf-8", "replace"), 12)
        return
    import dl_prof as P
    import xml.etree.ElementTree as ET
    it = None
    if look.mod("defusedxml"):
        from defusedxml import ElementTree as DET
        try:   # the entity check above already ran, so the declaration itself is allowed; external references stay unresolved
            it = DET.iterparse(io.BytesIO(raw), events=("start",), forbid_dtd=False, forbid_entities=False, forbid_external=False)
        except Exception:
            it = None
    if it is None:
        it = ET.iterparse(io.BytesIO(raw), events=("start",))
    root, err = None, None
    try:
        for _ev, el in it:
            if root is None:
                root = el
    except Exception as e:   # iterparse keeps the tree built so far: for a part-read file that is the answer
        err = e
    if err is not None and (root is None or not cut):
        if cut and root is None:
            look.flag("PARTIAL", "file", f"read the first {len(raw):,} of {look.size:,} bytes and could not parse them: {type(err).__name__}: {err}"[:200], "the file is larger than the read limit, so no verdict on its validity")
        else:
            look.flag("INVALID-XML", "file", f"{type(err).__name__}: {err}"[:120], "")
        P.text_profile(look, raw.decode("utf-8", "replace"), 70, "Text")
        return
    if cut:
        look.flag("PARTIAL", "file", f"read the first {len(raw):,} of {look.size:,} bytes ({100 * len(raw) / look.size:.0f} %)",
                  "element counts, attributes and records cover that part only; every count is a lower bound")

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
    base = 0
    if root_tag in ("gpx", "kml"):   # a track or map file: its totals lead; the generic XML profile follows in --more
        import dl_geo
        try:
            (dl_geo.look_gpx if root_tag == "gpx" else dl_geo.look_kml)(look, root)
            base = -50
        except Exception as e:
            look.fail(f"{root_tag} totals", "stdlib", e)
    look.line(f"XML: root <{root_tag}>, {'at least ' if cut else ''}{sum(counts.values()):,} elements of {len(counts)} kinds, depth {depth}. Elements: " + ", ".join(f"{k} ({v:,})" for k, v in counts.most_common(30)), 90 + base)
    P.counts(look, [("elements", sum(counts.values())), ("element kinds", len(counts)), ("attributes", sum(attrs.values())), ("elements with text", texts),
                    ("max depth", depth), ("root children", len(list(root)))], 94 + base, "XML counts")
    import dl_xmlvals
    dl_xmlvals.emit(look, root, "XML", 88 + base)   # the values, by element path, over the whole document: a late element's text is in the first print too
    if attrs:
        look.line("Attributes (element@name, count): " + ", ".join(f"{k} ({v:,})" for k, v in attrs.most_common(40)), 60)
    for t in sorted({c for (par, c) in parent_of if par == c}, key=lambda c: -counts[c])[:2]:
        nested_tree(look, root, t, 87 + base)
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
    P.emit(look, p, extra, f"<{t}> records ({len(els):,} elements, numbered from 0 in document order)", 86 + base, 30)
    if len(recs) <= 3000:
        rows = [f"[{i}] " + "; ".join(f"{k}={P.short(x if not isinstance(x, P.Multi) else ', '.join(map(str, x)), 60)}" for k, x in P.flat_of(r).items() if not k.endswith(P.LEN)) for i, r in recs]
        for k in range(0, len(rows), 20):
            look.line(f"<{t}> records:\n" + "\n".join(rows[k:k + 20]), 18, "records")


def nested_tree(look, root, tag, pri):
    """An element that nests in itself (OPML <outline>, a folder tree, a menu): per top-level node and per group under it, how many
    items (nodes with no child of the same tag) sit anywhere below. 'How many feeds are under Endgames' is a count over a subtree."""
    def local(t):
        return t.rsplit("}", 1)[-1] if isinstance(t, str) else str(t)

    def kids(e):
        return [c for c in e if local(c.tag) == tag]

    def label(e):
        for a in ("text", "title", "name", "label", "id"):
            if e.get(a):
                return e.get(a)
        return (e.text or "").strip() or f"<{tag}>"

    def leaves(e, depth=0):
        ks = kids(e)
        if not ks:
            return [e]
        return [x for c in ks for x in leaves(c, depth + 1)] if depth < 60 else []

    def items(e):
        lv = leaves(e)
        kinds = Counter(x.get("type") for x in lv if x.get("type"))
        typed = (" (" + ", ".join(f"{k} {v:,}" for k, v in kinds.most_common(4)) + ")" if len(kinds) > 1 or sum(kinds.values()) < len(lv)
                 else f" (all {next(iter(kinds))})" if kinds else "")
        return f"{len(lv):,} items{typed}"
    tops, stack = [], [iter([root])]
    while stack:   # the outermost nodes of the tag, in document order
        e = next(stack[-1], None)
        if e is None:
            stack.pop()
        elif e is not root and local(e.tag) == tag:
            tops.append(e)
        elif len(stack) < 60:
            stack.append(iter(list(e)))
    groups = [e for e in tops if kids(e)]
    if not groups:
        return
    short = __import__("dl_prof").short

    def under(e):
        g = sum(1 for c in kids(e) if kids(c))
        return f"{short(label(e), 40)}: {items(e)}" + (f" in {g} groups" if g else "")
    loose = len(tops) - len(groups)
    look.line(f"Nested <{tag}> tree: {len(tops):,} top-level nodes ({len(groups):,} with nodes inside, {loose:,} without), {sum(len(leaves(e)) for e in tops):,} items in all "
              f"(an item is a <{tag}> with no <{tag}> inside it; its type attribute in parentheses); items anywhere under each top-level node that holds any: "
              + "; ".join(under(e) for e in groups[:60]) + (f"; ... {len(groups) - 60} more" if len(groups) > 60 else ""), pri, "structure")
    rows = [f"{short(label(e), 40)} > " + "; ".join(f"{short(label(c), 40)} {items(c)}" for c in kids(e)[:40]) for e in groups[:60]]
    look.line(f"Nested <{tag}> tree, items under each group of each top-level node:\n" + "\n".join(rows), max(30, pri - 25), "structure")


def data_toml(look):
    import dl_prof as P
    if look.size > (64 << 20):
        look.skip("TOML structure", f"{core.human(look.size)} is over the 64.0 MB a TOML document is parsed whole at", None, "read it as text with --grep / --lines")
        return
    text = open(look.path, "rb").read().decode("utf-8", "replace")
    try:
        import tomllib
    except ImportError:
        return data_text_struct(look)
    try:
        v = tomllib.loads(text)
    except Exception as e:
        if re.search(r"(?m)^\s*\[[^\]\n]+\]\s*$", text) or look.path.suffix.lower() != ".toml":   # INI-style text that is not valid TOML
            look.subtype = "ini"
            return __import__("dl_conf").look_ini(look)
        look.flag("INVALID-TOML", "file", str(e)[:120], "")
        P.text_profile(look, text, 70, "Text")
        return
    look.write_text("skeleton.json", json.dumps(skeleton(v), indent=1), "keys and types tree", "json")
    tables = re.findall(r"(?m)^\s*\[([^\[\]]+)\]\s*(?:#.*)?$", text)
    arrays = re.findall(r"(?m)^\s*\[\[([^\[\]]+)\]\]\s*(?:#.*)?$", text)
    look.line(f"TOML: {len(v)} top-level keys ({', '.join(v)}); {len(tables)} [tables], {len(arrays)} [[array-of-tables]] entries"
              + (f" ({', '.join(f'{k} x{c}' for k, c in Counter(arrays).most_common(8))})" if arrays else "") + f"; {len(text.splitlines())} lines.", 90)
    look.fact("keys", list(v))
    __import__("dl_conf").comment_block(look, text, ("#",))
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
    __import__("dl_conf").comment_block(look, text, ("#",))
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
        b = bytes(v)
        if len(b) <= 4096:   # text that a reader left as bytes (SAS, some databases) is counted as the text it is, never as "<8 bytes>" for every value
            try:
                t = b.decode("utf-8")
                if t.isprintable():
                    return t
            except UnicodeDecodeError:
                pass
        return f"<{len(b)} bytes>"
    return str(v)


def table_profile(look, what, names, rows, label="row", total=None, key_pri=84, more_pri=28, cap_s=TABLE_PROFILE_S, listing=True):
    """Every row of one table through the field profiler and the group-by pass. rows: a callable giving (index, values) each time it
    is called (walked twice). Exact over every row unless the time cap stops it, which is flagged with the row it stopped at."""
    import dl_prof as P
    p = P.Profiler(False, label)
    cols = p.columns(list(names))
    import dl_listcol
    lc = dl_listcol.ListCols(names)
    t0, stopped, first = time.time(), None, []
    for k, (idx, vals) in enumerate(rows()):
        lc.add_row(vals)
        vals = [plain(v) for v in vals]
        p.add_row(cols, vals, idx)
        if listing and len(first) < TABLE_LISTING_ROWS:
            first.append((idx, vals))
        if k % 2000 == 0 and time.time() - t0 > cap_s:
            stopped = idx
            break
    if not p.n:
        return None
    lc.emit(look)
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
