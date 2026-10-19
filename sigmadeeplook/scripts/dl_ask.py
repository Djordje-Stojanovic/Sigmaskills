"""SigmaDeepLook --ask "<question>": one exact, targeted answer computed over the stored look (fix round 5). Stdlib only.

No model reads the question. It is cut into words, and three plain rules turn it into a computation:

1. the operation: how many / number of -> count; total / sum -> sum; average / mean -> mean; highest / largest / most -> max;
   lowest / smallest / least -> min; distinct / unique -> distinct values; "per X", "by X", "which X has the most Y" -> group by X;
   otherwise a lookup (the matching rows in full);
2. the fields: question words matched to column names (split on _ . - space and camelCase, plural s folded) of every table the
   look can re-read exactly: the delimited table (its normalised UTF-8 copy for cp1252, semicolon, decimal comma or .gz input),
   JSON Lines, every JSON record set at every depth (with its ancestors' plain fields, so "items in region North" works), sheets
   of xlsx/ods (total rows left out), SQLite tables, packets.csv, events.csv, INI keys;
3. the filters: question words or phrases equal to a value of a text column (Wien, North, server), comparisons ("over 100",
   "at least 5", "below 2"), and a year ("in 2025") on a date column.

The question may be English, German or Serbian/Croatian (dl_asklang.py: the words of each language are one table, the question is folded
to plain lowercase letters first). A table is held in memory up to a row and cell budget; past it the answer says PARTIAL with the
rows read and the rows in the file, and never presents a part as the whole.

The table that matches the most words wins. The answer prints with the computation, the filters and the rows used, so it can be
checked; it never guesses, and it says so when no table matches. Text questions (PDF, Word, transcripts, OCR) get the stated
counts of the look and the best-matching lines with their page, line or time.
"""
import codecs
import csv
import io
import json
import math
import os
import re
import sqlite3
from pathlib import Path

import dl_asklang as AL
import dl_core as core
import dl_prof as P
import dl_util as U

STOP = set(AL.LANGS["en"]["stop"].split())
YEAR_RE = re.compile(r"\b(19\d\d|20\d\d)\b")
DATE_VAL_RE = re.compile(r"^\s*\d{4}-\d\d(-\d\d)?")
MAX_ROWS = U.byte_cap("ASK_ROWS", 2_000_000)      # rows held per table
MAX_CELLS = U.byte_cap("ASK_CELLS", 40_000_000)   # cells held over all tables of one question (about 2-4 GB of Python strings at the cap)
JSON_DOC_CAP = U.byte_cap("ASK_JSON", 256 << 20)  # a JSON document is parsed whole: past this size it is named, not loaded
SNIFF_BYTES = 8 << 20


def stem(w):
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(s):
    """Column names and questions to comparable word stems: 'unitPrice_EUR' -> unit, price, eur."""
    s = AL.fold(re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s)))   # accents and Cyrillic folded: "Preis" = "preis", "Cena" = "цена"
    return [stem(w) for w in re.findall(r"[^\W_]+", s, re.U)]


def num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v == v else None
    return P.as_number(str(v), True)


class Table:
    def __init__(self, name, cols, rows, pos, where, unit="row", total=None):
        self.name, self.cols, self.rows, self.pos, self.where, self.unit = name, [str(c) for c in cols], rows, pos, where, unit
        self.total = total   # the rows the source holds when only part was read (None: every row is here)
        self.colw = [set(words(c)) for c in self.cols]
        self.ownw = [set(words(c.rsplit(".", 1)[-1])) for c in self.cols]   # the column's own name, without its ancestors' prefix
        self.namew = set(words(re.sub(r"\[\]", "", name).rsplit(".", 1)[-1]))   # a record set is named by its last path step
        self._num = {}

    def numeric(self, i):
        if i not in self._num:
            vals = [r[i] for r in self.rows[:5000] if i < len(r) and str(r[i]).strip() != ""]
            self._num[i] = bool(vals) and sum(1 for v in vals if num(v) is not None) >= 0.9 * len(vals)
        return self._num[i]

    def values(self, i):
        return [r[i] if i < len(r) else "" for r in self.rows]


# ---------------------------------------------------------------- readers: every table the look can re-read exactly
class Budget:
    """Cells still allowed in memory for this question: a table read stops at the row cap or when the budget is spent."""
    def __init__(self, cells=None):
        self.cells = MAX_CELLS if cells is None else cells

    def spent(self, n):
        self.cells -= n
        return self.cells <= 0


def open_text(p):
    """-> (head text, encoding, text stream over the whole file or None). The encoding and dialect come from the first 8 MB; a bigger file is
    streamed in that encoding (bad bytes replaced), never read whole."""
    import dl_delim
    size = os.path.getsize(p)
    with open(p, "rb") as fh:
        head = fh.read(SNIFF_BYTES)
    text, enc = dl_delim.sniff_encoding(head)
    if len(head) >= size:
        return text, enc, None
    try:
        codecs.lookup(enc)
    except LookupError:
        enc = "latin-1"
    return text, enc, io.TextIOWrapper(open(p, "rb"), encoding=enc, errors="replace", newline="")


def read_delimited(p, delim=None, budget=None):
    """-> (columns, rows, line numbers, encoding, total rows when the read stopped early else None)."""
    import dl_delim
    budget = budget or Budget()
    text, enc, stream = open_text(p)
    d, ncols, _ = dl_delim.sniff_dialect(text, delim)
    norm = dl_delim.normalizer(dl_delim.decimal_comma_columns(text, d, ncols))
    rd = csv.reader(stream if stream is not None else io.StringIO(text, newline=""), delimiter=d)
    header = next(rd, None) or []
    rows, pos, total = [], [], None
    for rec in rd:
        if not any(c.strip() for c in rec):
            continue
        rows.append(norm(rec) if norm and len(rec) == ncols else rec)
        pos.append(rd.line_num)
        if len(rows) >= MAX_ROWS or budget.spent(max(1, len(rec))):
            total = len(rows) + sum(1 for r in rd if any(c.strip() for c in r))   # the rest is counted, not kept
            break
    if stream is not None:
        stream.close()
    return [h.lstrip("\ufeff").strip() or f"column {i + 1}" for i, h in enumerate(header)], rows, pos, enc, total


def flat(obj, prefix=""):
    out = {}
    for k, v in obj.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, key + "."))
        elif isinstance(v, list):
            if all(not isinstance(x, (dict, list)) for x in v):
                out[key] = ", ".join(str(x) for x in v)
            out[key + " (count)"] = len(v)
        else:
            out[key] = v
    return out


def json_sets(doc):
    """Every array of objects at every depth, merged by shape path, each record with its ancestors' plain fields."""
    sets = {}

    def walk(v, path, shape, ctx):
        if isinstance(v, dict):
            here = {k: x for k, x in v.items() if not isinstance(x, (dict, list))}
            name = shape.rsplit(".", 1)[-1].replace("[]", "") or "root"
            sub = dict(ctx)
            sub.update({f"{name}.{k}": x for k, x in here.items()})
            for k, x in v.items():
                if isinstance(x, (dict, list)):
                    walk(x, f"{path}.{k}" if path else k, f"{shape}.{k}" if shape else k, sub)
        elif isinstance(v, list):
            if v and all(isinstance(x, dict) for x in v):
                for i, x in enumerate(v):
                    rec = dict(ctx)
                    rec.update(flat(x))
                    s = sets.setdefault(shape + "[]", ([], []))
                    s[0].append(rec)
                    s[1].append(f"{path}[{i}]")
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]", shape + "[]", ctx)
    walk(doc, "", "", {})
    out = []
    for shape, (recs, pos) in sets.items():
        cols = []
        for r in recs:
            for k in r:
                if k not in cols:
                    cols.append(k)
        out.append(Table(f"JSON records {shape}", cols, [[r.get(c, "") for c in cols] for r in recs], pos, "the JSON file", "record"))
    return out


def load_tables(path, out, lj, notes=None):
    """Every table the look can re-read exactly. Anything that could not be read whole or at all is added to `notes` (printed with the answer)."""
    notes = notes if notes is not None else []
    budget = Budget()
    facts = lj.get("facts") or {}
    st, tp = lj.get("subtype"), lj.get("type")
    src = Path(facts.get("unpacked") or path)
    inner = (facts.get("inner_type") or f"{tp}/{st}").split("/")[-1]
    tables = []
    try:
        if facts.get("table_copy") and Path(facts["table_copy"]).exists():
            cols, rows, pos, _, tot = read_delimited(facts["table_copy"], ",", budget)
            tables.append(Table("the table", cols, rows, pos, "the table (normalised UTF-8 copy: decimal comma converted)", "line", tot))
        elif inner in ("csv", "tsv", "psv", "delimited", "semicolon", "pipe") or (tp == "data" and inner in ("txt",)):
            cols, rows, pos, enc, tot = read_delimited(src, facts.get("delimiter"), budget)
            tables.append(Table("the table", cols, rows, pos, f"the file ({enc})", "line", tot))
        elif inner in ("jsonl", "ndjson"):
            tables.append(read_jsonl(src, budget))
        elif inner in ("json", "geojson"):
            if src.stat().st_size > JSON_DOC_CAP:
                notes.append(f"The JSON document is {core.human(src.stat().st_size)}, over the {core.human(JSON_DOC_CAP)} that is parsed whole for --ask: no table was built from it (--grep and --lines still read it).")
            else:
                text, _ = __import__("dl_delim").sniff_encoding(src.read_bytes())
                tables += json_sets(json.loads(text))
        elif inner == "sqlite":
            con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
            for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()[:50]:
                cur = con.execute(f'SELECT rowid, * FROM "{name}"')
                cols = [d[0] for d in cur.description][1:]
                rows, total = [], None
                while True:
                    chunk = cur.fetchmany(min(10000, MAX_ROWS))
                    if not chunk:
                        break
                    rows += chunk
                    if len(rows) >= MAX_ROWS or budget.spent(len(chunk) * max(1, len(cols))):
                        total = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                        break
                tables.append(Table(f"SQLite table {name}", cols, [list(r[1:]) for r in rows], [r[0] for r in rows], "the database", "rowid", total if total and total > len(rows) else None))
            con.close()
        elif inner == "ini":
            tables.append(ini_table(src))
        elif inner == "parquet" and core.have_module("pyarrow"):
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(str(src))
            cols = list(pf.schema_arrow.names)
            rows, total = [], None
            for batch in pf.iter_batches(batch_size=max(1, min(50000, MAX_ROWS))):
                dct = batch.to_pydict()
                rows += [list(r) for r in zip(*[dct[c] for c in cols])]
                if len(rows) >= MAX_ROWS or budget.spent(batch.num_rows * max(1, len(cols))):
                    total = pf.metadata.num_rows
                    break
            tables.append(Table("the Parquet table", cols, rows, list(range(1, len(rows) + 1)), "the file", "row", total if total and total > len(rows) else None))
    except (OSError, ValueError, sqlite3.Error, csv.Error, MemoryError) as e:
        notes.append(f"A table of this file could not be read for --ask ({type(e).__name__}: {str(e)[:150]}).")
    arts = lj.get("artifacts", [])
    curated = any(Path(a.get("path", "")).name.startswith("asktable-") for a in arts)
    for a in arts:   # tables the look wrote: sheets (header found, total rows out), packets, events
        p = Path(a.get("path", ""))
        if not p.is_file() or a.get("private") or (curated and p.suffix == ".csv" and p.parent.name == "sheets"):
            continue
        try:
            if p.name.startswith("asktable-") and p.suffix == ".json":
                t = json.loads(p.read_text(encoding="utf-8"))
                tables.append(Table(t["name"], t["cols"], [r[1] for r in t["rows"]], [r[0] for r in t["rows"]], t.get("where", "the file"), t.get("unit", "row")))
            elif p.suffix == ".csv" and p.name != "table.utf8.csv":
                cols, rows, pos, _, tot = read_delimited(p, ",", budget)
                tables.append(Table(p.stem, cols, rows, [k - 1 for k in pos], f"{p.name} (written by the look)", f"{p.stem[:-1] if p.stem.endswith('s') else p.stem} row", tot))
        except (OSError, ValueError, KeyError, csv.Error):
            continue
    return [t for t in tables if isinstance(t, Table) and t.rows]


def read_jsonl(src, budget):
    recs, pos, total = [], [], None
    text, _enc, stream = open_text(src)
    lines = stream if stream is not None else io.StringIO(text, newline="")
    for n, ln in enumerate(lines, 1):
        try:
            v = json.loads(ln)
        except ValueError:
            continue
        if isinstance(v, dict):
            f = flat(v)
            recs.append(f)
            pos.append(n)
            if len(recs) >= MAX_ROWS or budget.spent(max(1, len(f))):
                total = len(recs) + sum(1 for x in lines if x.strip())   # the rest of the lines is counted, not kept
                break
    if stream is not None:
        stream.close()
    cols = {}
    for r in recs:
        for k in r:
            cols.setdefault(k, None)
    cols = list(cols)
    return Table("JSON Lines records", cols, [[r.get(c, "") for c in cols] for r in recs], pos, "the file", "line", total)


def ini_table(p):
    import dl_delim
    text, _ = dl_delim.sniff_encoding(Path(p).read_bytes())
    sec, rows, pos = "", [], []
    for n, ln in enumerate(text.splitlines(), 1):
        s = ln.strip()
        if not s or s[0] in "#;":
            continue
        m = re.match(r"^\[([^\]]+)\]", s)
        if m:
            sec = m.group(1).strip()
            continue
        m = re.match(r"^([^=:]+?)\s*[=:]\s*(.*)$", s)
        if m:
            rows.append([sec, m.group(1).strip(), m.group(2).strip()])
            pos.append(n)
    return Table("the settings", ["section", "key", "value"], rows, pos, "the file", "line")


def store_table(look, name, cols, rows, where="the file", unit="row"):
    """Analysis side: keep one table for --ask (internal artifact, never printed). rows: [(position, [values])]."""
    k = len([a for a in look.artifacts if Path(a["path"]).name.startswith("asktable-")]) if hasattr(look, "artifacts") else 0
    p = look.path_for(f"asktable-{k + 1}.json")
    p.write_text(json.dumps({"name": name, "cols": cols, "rows": rows, "where": where, "unit": unit}, default=str), encoding="utf-8")
    look.add(p, "internal", f"{name} as rows for --ask")


# ---------------------------------------------------------------- the question
def parse(q):
    fq = AL.fold(q)
    lang = AL.detect(fq)
    L = AL.compiled(lang)
    cmps, blank = [], fq
    for m in L["cmp"].finditer(fq):
        word, val = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        op = L["cmpwords"].get(word) or {"=": "="}.get(word) or word
        cmps.append((op, float(val.replace(",", "")), m.start()))
        blank = blank[:m.start()] + " " * (m.end() - m.start()) + blank[m.end():]   # "at most 5" is a comparison, not a request for the maximum
    ops = [name for name, rx in L["ops"] if rx.search(blank)]
    grp = L["group"].findall(blank)
    which = L["which"].match(blank)
    order = "first" if L["first"].search(blank) else "last" if L["last"].search(blank) else None
    ordn = re.search(r"\b(?:first|last|erste\w*|letzte\w*|prv\w+|poslednj\w+)\s+(\d+)\b", blank)
    onext = re.search(r"\b(?:first|last|erste\w*|letzte\w*|prv\w+|poslednj\w+)\s+([a-z]+)", blank)
    stop = STOP | L["stop"]
    return {"ops": ops, "group": [stem(g) for g in grp], "which": stem(which.group(1)) if which else None, "cmps": cmps, "lang": lang, "fq": fq,
            "order": order, "order_n": int(ordn.group(1)) if ordn else 1, "order_next": stem(onext.group(1)) if onext else None,
            "years": YEAR_RE.findall(q), "words": [w for w in words(q) if w not in stop and not w.isdigit()]}


def match_values(t, q):
    """(column, value) pairs whose value appears in the question as a whole word or phrase (text columns, 1..300 distinct values)."""
    ql = " " + re.sub(r"[^\w.@-]+", " ", q.lower()) + " "
    out = []
    for i in range(len(t.cols)):
        if t.numeric(i):
            continue
        vals = {str(v).strip() for v in t.values(i) if str(v).strip()}
        if not vals or len(vals) > max(300, len(t.rows) // 2 + 1):
            continue
        for v in sorted(vals, key=len, reverse=True):
            vl = " " + re.sub(r"[^\w.@-]+", " ", v.lower()).strip() + " "
            if len(vl.strip()) >= 2 and vl in ql and v.lower() not in STOP:
                out.append((i, v))
    best = {}
    for i, v in out:   # one value may sit in several columns: keep the column whose name is also in the question, else all
        best.setdefault(v.lower(), []).append(i)
    res = []
    qw = set(words(q))
    for v, cols in best.items():
        named = [i for i in cols if t.colw[i] & qw]
        for i in (named or cols):
            res.append((i, next(x for c, x in out if c == i and x.lower() == v)))
    return res


def score(t, pq, q):
    fw = sum(1 for w in set(pq["words"]) if col_for(t, w) is not None)
    vals = match_values(t, q)
    named = sum(3 for w in set(pq["words"]) if w in t.namew)
    return fw * 2 + len(vals) * 2 + named, vals


def col_for(t, w, numeric=None):
    """The column a question word names: its own name first, then a name with its ancestors' prefix, then a name the word
    starts (pop -> population, 3+ letters)."""
    ok = [i for i in range(len(t.cols)) if numeric is None or t.numeric(i) == numeric]
    for test in (lambda i: w in t.ownw[i], lambda i: w in t.colw[i], lambda i: len(w) >= 3 and any(x.startswith(w) for x in t.ownw[i])):
        cands = [i for i in ok if test(i)]
        if cands:
            return min(cands, key=lambda i: (len(t.colw[i]), i))
    return None


def pick_measure(t, pq, exclude=()):
    best = None
    for w in pq["words"]:
        i = col_for(t, w, True)
        if i is not None and i not in exclude:
            sc = len(t.colw[i] & set(pq["words"])) / len(t.colw[i])
            if best is None or sc > best[0]:
                best = (sc, i)
    return best[1] if best else None


def answer(t, pq, q, vals):
    lines = []
    keep = list(range(len(t.rows)))
    filt = []
    by_col = {}
    for i, v in vals:
        by_col.setdefault(i, set()).add(v.lower())
    group = None
    for g in pq["group"] + ([pq["which"]] if pq["which"] else []):
        gi = col_for(t, g, False) if g else None
        if gi is None and g:
            gi = col_for(t, g)
        if gi is not None:
            group = gi
            break
    for i, vs in by_col.items():
        if i == group and len(vs) < 1:
            continue
        keep = [k for k in keep if str(t.rows[k][i] if i < len(t.rows[k]) else "").strip().lower() in vs]
        filt.append(f"{t.cols[i]} = " + " or ".join(repr(v) for v in sorted(vs)))
    measure = pick_measure(t, pq, exclude={group})
    for op, val, at in pq["cmps"]:
        before = re.findall(r"[^\W_]+", pq["fq"][:at])
        ci = None
        for w in reversed(before[-4:]):
            ci = col_for(t, stem(w), True)
            if ci is not None:
                break
        ci = ci if ci is not None else measure
        if ci is None:
            continue
        f = {">": lambda a: a > val, ">=": lambda a: a >= val, "<": lambda a: a < val, "<=": lambda a: a <= val, "=": lambda a: a == val}[op]
        keep = [k for k in keep if (lambda x: x is not None and f(x))(num(t.rows[k][ci] if ci < len(t.rows[k]) else None))]
        filt.append(f"{t.cols[ci]} {op} {P.fmt(val)}")
    for y in pq["years"]:
        dc = [i for i in range(len(t.cols)) if not t.numeric(i) and sum(1 for v in t.values(i)[:200] if DATE_VAL_RE.match(str(v))) >= 0.8 * min(200, len(t.rows))]
        if dc:
            keep = [k for k in keep if str(t.rows[k][dc[0]]).strip().startswith(y)]
            filt.append(f"{t.cols[dc[0]]} in {y}")
    ops = list(pq["ops"])
    if "count" in ops and "sum" in ops and measure is None:   # "how many orders in total": no column named, so the total is a count
        ops.remove("sum")
    head = f"Table: {t.name} ({len(t.rows):,} {t.unit}s, read from {t.where})"
    lines.append(head)
    lines.append("Filters: " + ("; ".join(filt) if filt else "none") + f" -> {len(keep):,} {t.unit}s")

    def pos_list(ks, n=20):
        if not ks:
            return "(none)"
        if ks and len(str(t.pos[ks[0]])) > 12:
            n = min(n, 5)
        return ", ".join(str(t.pos[k]) for k in ks[:n]) + (f" (+{len(ks) - n} more)" if len(ks) > n else "")

    def agg(ks, op, i):
        xs = [x for x in (num(t.rows[k][i] if i < len(t.rows[k]) else None) for k in ks) if x is not None]
        if op == "sum":
            return math.fsum(xs), len(xs)
        if op == "mean":
            return (math.fsum(xs) / len(xs) if xs else None), len(xs)
        if op == "max":
            return (max(xs) if xs else None), len(xs)
        if op == "min":
            return (min(xs) if xs else None), len(xs)
        return len(ks), len(ks)

    main_op = next((o for o in ("mean", "sum", "max", "min", "distinct", "count") if o in ops), None)
    hm = AL.compiled(pq["lang"])["howmany"].search(pq["fq"])
    if main_op == "count" and hm and stem(hm.group(1)) not in t.namew and col_for(t, stem(hm.group(1)), True) is not None:   # "how many units": the Units column, summed
        measure, main_op = col_for(t, stem(hm.group(1)), True), "sum"
    if main_op == "count" and measure is not None and "sum" in ops:
        main_op = "sum"
    if group is not None and main_op in (None, "count", "sum", "mean", "max", "min"):
        uniq = len({str(t.rows[k][group]) for k in keep}) == len(keep)
        if uniq and measure is not None and main_op in ("max", "min", None):   # which <id> has the highest <measure>: a row-level answer
            main_op = main_op or "max"
            xs = [(num(t.rows[k][measure]), k) for k in keep if num(t.rows[k][measure]) is not None]
            if xs:
                v, k = (max if main_op == "max" else min)(xs, key=lambda x: x[0])
                ties = [kk for x, kk in xs if x == v]
                lines.insert(0, f"Answer: {', '.join(str(t.rows[kk][group]) for kk in ties)} ({t.cols[measure]} {P.fmt(v)}; {main_op} over {len(xs):,} {t.unit}s; at {t.unit} {pos_list(ties)})")
                return lines
        if measure is None or ("count" in ops and "sum" not in ops and "mean" not in ops):
            inner = "count"
        elif "mean" in ops:
            inner = "mean"
        elif "sum" in ops:
            inner = "sum"
        elif "min" in ops and "max" not in ops:
            inner = "min"
        elif "max" in ops:
            inner = "max"
        else:
            inner = "sum"
        groups = {}
        for k in keep:
            groups.setdefault(str(t.rows[k][group]).strip(), []).append(k)
        res = []
        for g, ks in groups.items():
            v, _ = agg(ks, inner, measure) if inner != "count" else (len(ks), len(ks))
            res.append((g, v, ks))
        res = [r for r in res if r[1] is not None]
        res.sort(key=lambda r: -r[1])
        what = f"{inner} of {t.cols[measure]}" if inner != "count" else f"number of {t.unit}s"
        if res and (main_op in ("max", "min") or pq["which"] or "max" in ops or "min" in ops):
            low = "min" in ops and "max" not in ops
            pick = res[-1] if low else res[0]
            ties = [r for r in res if r[1] == pick[1]]
            lines.insert(0, f"Answer: {', '.join(r[0] for r in ties)} ({what} {P.fmt(pick[1])}, the {'lowest' if low else 'highest'} of {len(res)} groups of {t.cols[group]})")
        else:
            lines.insert(0, f"Answer: {what} per {t.cols[group]} ({len(res)} groups)")
        lines.append(f"Per {t.cols[group]} ({what}, largest first): " + "; ".join(f"{g} {P.fmt(v)}" for g, v, _ in res[:30]) + (f"; +{len(res) - 30} more" if len(res) > 30 else ""))
        return lines
    if main_op == "distinct":
        ci = None
        for w in pq["words"]:
            ci = col_for(t, w)
            if ci is not None:
                break
        if ci is not None:
            vs = sorted({str(t.rows[k][ci]).strip() for k in keep if str(t.rows[k][ci]).strip()})
            lines.insert(0, f"Answer: {len(vs):,} distinct {t.cols[ci]} values")
            lines.append("Values: " + "; ".join(vs[:60]) + (f"; +{len(vs) - 60} more" if len(vs) > 60 else ""))
            return lines
    if main_op in ("sum", "mean", "max", "min") and measure is not None:
        v, n = agg(keep, main_op, measure)
        exact = repr(round(v, 10)) if isinstance(v, float) and not float(v).is_integer() else ""
        s = f"Answer: {main_op} of {t.cols[measure]} = {P.fmt(v)}" + (f" (exact {exact})" if exact and exact != P.fmt(v) else "") + f" over {n:,} numbers"
        if main_op in ("max", "min") and v is not None:
            at = [k for k in keep if num(t.rows[k][measure]) == v]
            s += f"; at {t.unit} {pos_list(at, 5)}"
            lines.append(f"{t.unit.capitalize()} {t.pos[at[0]]}: " + "; ".join(f"{c} = {P.short(x, 40)}" for c, x in zip(t.cols, t.rows[at[0]]) if str(x).strip()))
        lines.insert(0, s)
        lines.append(f"{t.unit.capitalize()}s used: {pos_list(keep)}")
        return lines
    if main_op == "count" or (main_op in ("max", "min") and measure is None):
        lines.insert(0, f"Answer: {len(keep):,} {t.unit}s match" + (" (no filter matched the question, so this is every row)" if not filt else ""))
        lines.append(f"{t.unit.capitalize()}s: {pos_list(keep)}")
        return lines
    if pq["order"] and keep and main_op is None and not (pq["order_next"] and col_for(t, pq["order_next"]) is not None):   # "the first order", "the last 3 rows": by position in the file, said so
        n = max(1, min(pq["order_n"], 10))
        pick = keep[:n] if pq["order"] == "first" else keep[-n:]
        lines.insert(0, f"Answer: the {pq['order']} {n if n > 1 else ''}{' ' if n > 1 else ''}{t.unit}(s) in file order ({len(keep):,} after the filters), shown in full")
        for k in pick:
            lines.append(f"  {t.unit} {t.pos[k]}: " + "; ".join(f"{c} = {P.short(x, 60)}" for c, x in zip(t.cols, t.rows[k]) if str(x).strip() != ""))
        return lines
    # a lookup: the matching rows in full
    if not filt:
        return None
    lines.insert(0, f"Answer: {len(keep):,} matching {t.unit}(s)" + (", shown in full" if len(keep) <= 10 else ", the first 10 in full"))
    for k in keep[:10]:
        lines.append(f"  {t.unit} {t.pos[k]}: " + "; ".join(f"{c} = {P.short(x, 60)}" for c, x in zip(t.cols, t.rows[k]) if str(x).strip() != ""))
    return lines


# ---------------------------------------------------------------- text questions
PAGE_RE = re.compile(r"<!--\s*page\s+(\d+)\s*-->|^-{2,}\s*page\s+(\d+)", re.I)


def text_hits(srcs, pq, n=8):
    ws = [w for w in dict.fromkeys(pq["words"]) if len(w) >= 2]
    if not ws:
        return []
    hits = []
    for p in srcs:
        if isinstance(p, tuple):   # (name, text) already in memory: the look's own lines
            name, text = p
        else:
            name = Path(p).name
            try:
                text = Path(p).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        page = None
        for ln_no, ln in enumerate(text.splitlines(), 1):
            m = PAGE_RE.search(ln)
            if m:
                page = int(m.group(1) or m.group(2))
                continue
            lw = set(words(ln))
            got = sum(1 for w in ws if w in lw or any(x.startswith(w) for x in lw if len(w) >= 4))
            if got:
                hits.append((got, name, page, ln_no, " ".join(ln.split())))
    need = max(1, math.ceil(len(ws) / 2))
    hits = [h for h in hits if h[0] >= need]
    hits.sort(key=lambda h: -h[0])
    return [(g, nm, pg, no, clip(t, ws)) for g, nm, pg, no, t in hits[:n]]


def clip(line, ws, n=220):
    """The part of a long line around its first question word."""
    if len(line) <= n:
        return line
    low = line.lower()
    at = min([i for i in (low.find(w) for w in ws) if i >= 0] or [0])
    a = max(0, min(at - n // 3, len(line) - n))
    return ("…" if a else "") + line[a:a + n] + ("…" if a + n < len(line) else "")


def run(o, path, out, lj):
    import dl_drill
    q = o.ask.strip()
    if not q:
        return dl_drill.refuse("--ask needs a question.")
    pq = parse(q)
    lines = [f"--ask {q!r}", f"Read as: operation {', '.join(pq['ops']) or 'lookup'}; words {', '.join(pq['words']) or '(none)'}"
             + (f"; group by {', '.join(pq['group'])}" if pq["group"] else "") + (f"; comparisons {', '.join(f'{a} {P.fmt(b)}' for a, b, _ in pq['cmps'])}" if pq["cmps"] else "") + f"; language {pq['lang']}"]
    notes = []
    tables = load_tables(path, out, lj, notes)
    ranked = sorted(((score(t, pq, q), t) for t in tables), key=lambda x: (-x[0][0], -len(x[1].rows)))
    got = None
    if ranked and ranked[0][0][0] > 0:
        (_, vals), t = ranked[0]
        got = answer(t, pq, q, vals)
        if got and t.total:   # only part of the table is in memory: no figure may read as a total
            note = f"PARTIAL: {len(t.rows):,} of {t.total:,} {t.unit}s were read (row and memory budget); this answer covers those {t.unit}s only"
            got = [x.replace("Answer:", f"Answer ({note}):", 1) if x.startswith("Answer:") else x for x in got]
            got.insert(1, note + ".")
        if got:
            lines += got
            others = [f"{x.name} (score {s[0]})" for s, x in ranked[1:4] if s[0] > 0]
            if others:
                lines.append("Other tables that match some words: " + "; ".join(others))
    lines += notes
    counts = (lj.get("facts") or {}).get("counts") or {}
    cw = set(pq["words"])
    stated = [(k, v) for k, v in counts.items() if set(words(k)) and set(words(k)) <= cw | {"non", "empty"} and set(words(k)) & cw]
    exact = [(k, v) for k, v in stated if set(words(k)) == cw]
    if exact and "count" in pq["ops"]:   # the look's own count names exactly what was asked: it is the answer, the table count is context
        k, v = exact[0]
        lines = [x.replace("Answer:", "Table count:", 1) if x.startswith("Answer:") else x for x in lines]
        lines.insert(2, f"Answer: {k} {P.fmt(v) if isinstance(v, (int, float)) else v} (the look's own exact count of exactly these words)")
        got = got or ["stated"]
    elif stated:
        lines.append("Counts stated in the look: " + "; ".join(f"{k} {P.fmt(v) if isinstance(v, (int, float)) else v}" for k, v in stated))
    if not got:
        lines.append("No table answers this exactly" + (" (no table matched the question words)" if tables else " (this file has no table the look can re-read)") + "; the lines below match the question words.")
    srcs = dl_drill.text_sources(out, lj, path)
    figs = [s for s in ((lj.get("facts") or {}).get("stated_figures") or []) if sum(1 for w in pq["words"] if w in set(words(s))) >= max(1, len(pq["words"]) // 2)]
    if figs:
        lines.append("Figures stated in the text that match: " + " | ".join(figs[:8]))
    look_lines = "\n".join(" ".join(str(x.get("text", "")).split()) for x in (lj.get("stream") or []) if x.get("sec") != "head")
    hits = text_hits([("LOOK", look_lines)] + srcs, pq, 8) if not got else []
    if hits:
        lines.append("Best-matching lines (source, page, line; LOOK = a fact line of this look):")
        for h in hits:
            lines.append(f"  {h[1]}{f' p{h[2]}' if h[2] else ''}:{h[3]}: {h[4]}")
    return dl_drill.done("\n".join(lines))
