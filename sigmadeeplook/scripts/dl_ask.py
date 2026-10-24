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
import struct
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
STREAM_CELLS = U.byte_cap("ASK_STREAM", 1_000_000)   # a source with more cells than this is searched for the rows that hold a value of the question, not held whole
STREAM_KEEP = U.byte_cap("ASK_KEEP", 5000)           # rows kept by such a search; a search that fills the list says PARTIAL


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
    def __init__(self, name, cols, rows, pos, where, unit="row", total=None, ident=None):
        self.name, self.cols, self.rows, self.pos, self.where, self.unit = name, [str(c) for c in cols], rows, pos, where, unit
        self.total = total   # the rows the source holds when only part was read (None: every row is here)
        self.partial = None  # the PARTIAL sentence of a search that stopped early (its rows are only some of the matches)
        self.ident = ident   # the table's own name in the file (a database table): a question that writes it names this table
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


NOT_A_KEY = re.compile(r"\b\d+\s*(?:decimals?|decimal places?|places?|digits?|dp|significant|sig figs?|nachkommastellen?|dezimalstellen?|decimale|cifr\w*)\b"
                      r"|\b(?:round\w*|to)\s+\d+\b|\b(?:first|last|top|bottom|erste\w*|letzte\w*|prv\w+|poslednj\w+)\s+\d+\b")   # "to 1 decimal", "top 5": a precision or a count of rows, not a value


def wanted(pq):
    """For a pure lookup (no operation, group, comparison or year): the numbers and the key-like strings the question names, as a row test; else None."""
    if pq["ops"] or pq["group"] or pq["cmps"] or pq["years"]:
        return None
    blank = NOT_A_KEY.sub(" ", pq["blank"])
    nums = {float(x) for x in re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])", blank)}
    cands = key_candidates(blank)
    strs = {c.lower() for c in cands}
    keys = {loose(c) for c in cands if not re.fullmatch(r"\d+(?:\.\d+)?", c)}
    if not (nums or keys):
        return None

    def test(row):
        for v in row:
            if v.__class__ is str:
                s = v.strip()
                if s.lower() in strs or (keys and loose(s) in keys):
                    return True
            elif v is not None and v in nums:
                return True
        return False
    return test


def read_rows(name, cols, rows, total, where, unit, budget, hint):
    """A table from any row source: rows = iterator of (position, values), total = the rows the source holds (None: unknown). A source over
    STREAM_CELLS cells that is asked a pure lookup (`hint` = its row test) is read in one pass and only the rows that hold a value of the
    question are kept; otherwise it is held up to the row and cell budget, and the answer says PARTIAL when that cuts it."""
    if hint is not None and total is not None and total * max(1, len(cols)) > STREAM_CELLS:
        keep, pos, stopped = [], [], None
        for p, r in rows:
            if hint(r):
                keep.append(list(r))
                pos.append(p)
                if len(keep) >= STREAM_KEEP:
                    stopped = p
                    break
        t = Table(name, cols, keep, pos, where + "; one pass, only the rows that hold a value named in the question are kept", unit, total if stopped is not None else None)
        if stopped is not None:
            t.partial = f"PARTIAL: the scan stopped at {unit} {stopped:,} of {total:,} after {len(keep):,} {unit}s that hold a value named in the question; this answer covers those {unit}s only"
        return t
    out, pos, cut = [], [], None
    for p, r in rows:
        out.append(list(r))
        pos.append(p)
        if len(out) >= MAX_ROWS or budget.spent(max(1, len(cols))):
            cut = total if total is not None else len(out) + sum(1 for _ in rows)
            break
    return Table(name, cols, out, pos, where, unit, cut if cut and cut > len(out) else None)


def load_tables(path, out, lj, notes=None, hint=None):
    """Every table the look can re-read exactly. Anything that could not be read whole or at all is added to `notes` (printed with the answer).
    `hint`: the row test of a pure lookup (see `wanted`), which lets a very big source be searched instead of held."""
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
            tl = facts.get("table_lines")
            if tl and tl[0] > 1:   # a table inside a text: the copy starts at the header row, so a copy line + (header line - 1) is the line of the original file
                pos = [k + tl[0] - 1 for k in pos]
            tables.append(Table("the table", cols, rows, pos, "the table (normalised UTF-8 copy: decimal comma converted; line = line of the original file)" if tl else "the table (normalised UTF-8 copy: decimal comma converted)", "line", tot))
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
        elif inner == "sav":
            import dl_sav
            got = dl_sav.ask_source(src)
            if got:
                names, n, it = got
                tables.append(read_rows("SPSS cases", names, it, n, "the file", "case", budget, hint))
            else:
                notes.append("The cases of this .sav file are ZLIB-compressed and not decoded: no table was built (the dictionary is in the look).")
        elif inner in ("sas7bdat", "sasxpt", "stata"):
            import dl_tab2
            try:
                df = dl_tab2.ask_frame(src, inner)
            except Exception as e:   # pandas reads many formats and raises many errors: a damaged file is named, never a crash
                df = None
                notes.append(f"A table of this file could not be read for --ask ({type(e).__name__}: {str(e)[:150]}).")
            if df is not None:
                tables.append(read_rows(f"{inner} table", [str(c) for c in df.columns], enumerate(df.itertuples(index=False, name=None), 1), len(df), "the file", "row", budget, hint))
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
                tables.append(Table(f"SQLite table {name}", cols, [[__import__("dl_data").plain(x) for x in r[1:]] for r in rows], [r[0] for r in rows], "the database", "rowid", total if total and total > len(rows) else None, ident=name))
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
    except (OSError, ValueError, sqlite3.Error, csv.Error, MemoryError, struct.error, IndexError) as e:
        notes.append(f"A table of this file could not be read for --ask ({type(e).__name__}: {str(e)[:150]}).")
    arts = lj.get("artifacts", [])
    curated = any(Path(a.get("path", "")).name.startswith("asktable-") for a in arts)
    for a in arts:   # tables the look wrote: sheets (header found, total rows out), packets, events
        p = Path(a.get("path", ""))
        if not p.is_file() or a.get("private") or (curated and p.suffix == ".csv" and (p.parent.name == "sheets" or p.name == "cues.csv")):
            continue
        try:
            if p.name.startswith("asktable-") and p.suffix == ".json":
                t = json.loads(p.read_text(encoding="utf-8"))
                tables.append(Table(t["name"], t["cols"], [r[1] for r in t["rows"]], [r[0] for r in t["rows"]], t.get("where", "the file"), t.get("unit", "row"), t.get("total")))
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
    import dl_conf
    import dl_delim
    text, _ = dl_delim.sniff_encoding(Path(p).read_bytes())   # the look's own parser: a .properties value has its continuation lines joined and its \uXXXX escapes decoded
    secs = dl_conf.parse(text, java=Path(p).suffix.lower() == ".properties")[0]
    rows, pos = [], []
    for sec, d in secs.items():
        for k, (v, ln) in d["keys"].items():
            v = "" if v is None else v
            rows.append(["" if sec == dl_conf.NOSEC else sec, k, f"(secret-like value, {len(v)} chars; not printed)" if v.strip() and dl_conf.SECRET_RE.search(k) else v])
            pos.append(ln)
    return Table("the settings", ["section", "key", "value"], rows, pos, "the file (line = where the key starts)", "line")


def store_table(look, name, cols, rows, where="the file", unit="row", total=None):
    """Analysis side: keep one table for --ask (internal artifact, never printed). rows: [(position, [values])]. `total`: the rows the file
    holds when only the first `rows` were kept (the answer then says PARTIAL)."""
    k = len([a for a in look.artifacts if Path(a["path"]).name.startswith("asktable-")]) if hasattr(look, "artifacts") else 0
    p = look.path_for(f"asktable-{k + 1}.json")
    p.write_text(json.dumps({"name": name, "cols": cols, "rows": rows, "where": where, "unit": unit, "total": total}, default=str), encoding="utf-8")
    look.add(p, "internal", f"{name} as rows for --ask")


# ---------------------------------------------------------------- "contain the word X": a text filter (fix round 12)
_Q = "\"'`‘’‚‛“”„‟«»‹›"
_VERB = r"(?:contain\w*|includ\w*|mention\w*|enth[aä]lt\w*|enthaelt\w*|sadr[zž]\w*|spominj\w*)"
_VERB_WITH = r"(?:with|having|has|have|hat|haben|ima|imaju)"
_NOUN = r"(?:words?|terms?|phrases?|texts?|strings?|wort|wörter|begriff\w*|re[cč]i?|izraz\w*|tekst\w*)"
_ART = r"(?:the\s+|das\s+|die\s+|den\s+|ove\s+|tu\s+)?"
CONTAINS_QUOTED = re.compile(rf"\b(?:{_VERB}\s+{_ART}(?:{_NOUN}\s+)?|{_VERB_WITH}\s+{_ART}{_NOUN}\s+)([{_Q}])(.+?)[{_Q}](?!\w)", re.I)
APPEARS_QUOTED = re.compile(rf"\b(?:(?:does|do|did|is|are)\s+)?{_ART}(?:{_NOUN}\s+)?([{_Q}])(.+?)[{_Q}](?!\w)\s*(?:appears?|occurs?|shows?\s+up|comes?\s+up|exists?|is\s+(?:used|found|present|written|mentioned))\b", re.I)   # "does the word 'X' appear" (fix round 13)
HOW_MANY = re.compile(r"\bhow\s+many\b|\bnumber\s+of\b|\bcount\b", re.I)
COUNT_OF_TIMES = re.compile(r"\bhow\s+(?:many|often)\s+(?:times|occurrences|instances|mentions|appearances)\b|\bhow\s+often\b|\bnumber\s+of\s+(?:times|occurrences|instances|mentions|appearances)\b", re.I)
CONTAINS_BARE = re.compile(rf"\b{_VERB}\s+{_ART}{_NOUN}\s+([^\s{_Q}?!,;:()]+)", re.I)
IGNORE_CASE = re.compile(r"\b(?:ignor\w*\s+(?:the\s+)?case|case[- ]?insensitiv\w*|any\s+case|regardless\s+of\s+(?:the\s+)?case|in\s+any\s+capitali[sz]ation|(?:upper|lower)\s*(?:case)?\s+or\s+(?:upper|lower)\s*case)\b", re.I)
CASE_NOTE = re.compile(r"\(?\b(?:in\s+)?(?:lower|upper)\s*case\b\)?|\bcase[- ]?sensitiv\w*|\bas\s+written\b|\bexact(?:ly)?\s+as\s+(?:written|spelled)\b", re.I)


def contains_filter(q):
    """'How many cues contain the word 'riego' (lower case)?' -> dict(needle, nocase, rest) where `rest` is the question without the clause, or None.
    The word is matched whole and as written (case counts) unless the question says to ignore case."""
    m = CONTAINS_QUOTED.search(q)
    needle = m.group(2).strip() if m else None
    if not m and HOW_MANY.search(q) and not COUNT_OF_TIMES.search(q):   # "how many times does the word 'X' appear" counts occurrences, not rows
        m = APPEARS_QUOTED.search(q)
        needle = m.group(2).strip() if m else None
    if not m:
        m = CONTAINS_BARE.search(q)
        needle = m.group(1).strip(".") if m else None
    if not m or not needle:
        return None
    nocase = bool(IGNORE_CASE.search(q))
    rest = q[:m.start()] + " " + q[m.end():]
    rest = CASE_NOTE.sub(" ", IGNORE_CASE.sub(" ", rest))
    return {"needle": needle, "nocase": nocase, "rest": rest}


def needle_regex(needle, nocase):
    """The needle as a whole word or phrase (spaces match any run of white space), case as written unless `nocase`."""
    body = r"\s+".join(re.escape(x) for x in needle.split())
    lead = r"(?<!\w)" if re.match(r"\w", needle) else ""
    tail = r"(?!\w)" if re.search(r"\w$", needle) else ""
    return re.compile(lead + body + tail, re.I if nocase else 0)


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
    return {"blank": blank, "allw": set(words(blank)), "ops": ops, "group": [stem(g) for g in grp], "which": stem(which.group(1)) if which else None, "cmps": cmps, "lang": lang, "fq": fq,
            "order": order, "order_n": int(ordn.group(1)) if ordn else 1, "order_next": stem(onext.group(1)) if onext else None,
            "years": YEAR_RE.findall(q), "words": [w for w in words(q) if w not in stop and not w.isdigit()]}


QUOTED_RE = re.compile(r"(?<!\w)(['\"‘“«„])(.+?)(['\"’”»“])(?!\w)")
PUNCT = "'\"‘’“”«»„.,;:?!()[]{}"


def loose(s):
    """A key compared without case, accents, script (Cyrillic or Latin letters) and separators: 'MZ-0388' = 'мз 0388' = 'mz0388'."""
    return re.sub(r"[\W_]+", "", AL.fold(s))


def key_candidates(q):
    """The strings of a question that may name one record: quoted text, and bare words that hold a digit (МЗ-0388, 5650000, SM-05200)."""
    out = [m.group(2).strip() for m in QUOTED_RE.finditer(q)]
    for tok in q.split():
        tok = tok.strip(PUNCT)
        if any(c.isdigit() for c in tok) and len(tok) >= 2:
            out.append(tok)
    return list(dict.fromkeys(x for x in out if x))


def match_values(t, q, blank=None):
    """(column, value) pairs whose value appears in the question as a whole word or phrase (text columns, 1..300 distinct values), and
    (column, value) pairs for the key-like strings of the question (quoted text, words with a digit; `blank` = the question with its
    comparisons cut out) that equal a cell of a text column: a record id, a code, a name, written with or without hyphens and in either script."""
    ql = " " + re.sub(r"[^\w.@-]+", " ", q.lower()) + " "
    out, keys, plain = [], None, None
    for i in range(len(t.cols)):
        if t.numeric(i):
            continue
        vals = {str(v).strip() for v in t.values(i) if str(v).strip()}
        if not vals:
            continue
        if keys is None:
            cands = key_candidates(q if blank is None else blank)
            plain = {c for c in cands if re.fullmatch(r"\d+(?:\.\d+)?", c)}   # a bare number must equal the cell exactly ('5.0' is not '50')
            keys = {loose(c): c for c in cands if c not in plain and loose(c)}
        if keys or plain:
            hit = []
            for v in vals:
                if v in plain or (keys and loose(v) in keys and not re.fullmatch(r"\d+(?:\.\d+)?", v)):
                    hit.append(v)
            out += [(i, v) for v in hit]
        if len(vals) > max(300, len(t.rows) // 2 + 1):   # a high-cardinality column: only a quoted or digit-bearing string of the question names its value
            continue
        for v in sorted(vals, key=len, reverse=True):
            vl = " " + re.sub(r"[^\w.@-]+", " ", v.lower()).strip() + " "
            if len(vl.strip()) >= 2 and vl in ql and v.lower() not in STOP and (i, v) not in out:
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
    if not fw:   # an operation or filler word can be a column's whole name ("total of 8031" for a column called total)
        fw = sum(1 for w in pq["allw"] if any(t.ownw[i] == {w} for i in range(len(t.cols))))
    vals = match_values(t, q, pq["blank"])
    named = sum(3 for w in set(pq["words"]) if w in t.namew)
    if t.ident and re.search(r"(?<!\w)" + re.escape(t.ident) + r"(?!\w)", q, re.I):   # the question writes the table's own name (gpkg_contents): that table, not a look-alike
        named += 100
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


def col_phrase(t, ws, numeric=True):
    """The column whose whole name (all its words) is among the last four words `ws`; the longest name wins, a tie goes to the first column."""
    sw = {stem(w) for w in ws[-4:]}
    cands = [i for i in range(len(t.cols)) if t.colw[i] and t.colw[i] <= sw and t.numeric(i) == numeric]
    return max(cands, key=lambda i: (len(t.colw[i]), -i)) if cands else None


def named_words(t, pq):
    """The question words that name a numeric column, except the words that name the group ('per region', 'which tool')."""
    skip = set(pq["group"]) | ({pq["which"]} if pq["which"] else set())
    return [w for w in dict.fromkeys(pq["words"]) if w not in skip and col_for(t, w, True) is not None]


def measure_ok(t, pq, i):
    """A column may answer when the question names all of its words, or when the question names only one numeric word.
    'How many tool errors' names two: hookErrors and shape.tools each name only one of them, so neither answers it."""
    return len(named_words(t, pq)) < 2 or (t.colw[i] - {"count"}) <= set(pq["words"])


def pick_measure(t, pq, exclude=()):
    best = None
    for w in pq["words"]:
        i = col_for(t, w, True)
        if i is not None and i not in exclude:
            sc = len(t.colw[i] & set(pq["words"])) / len(t.colw[i])
            if best is None or sc > best[0]:
                best = (sc, i)
    if best is None:   # a column named like an operation word (total, count, average): "which ticket_no has the largest total"
        for w in words(pq["blank"]):
            i = next((k for k in range(len(t.cols)) if t.colw[k] == {w} and t.numeric(k) and k not in exclude), None)
            if i is not None:
                return i   # the question writes the column's whole name: nothing else in it can name another measure
    return best[1] if best and measure_ok(t, pq, best[1]) else None


EQ_SKIP = {"number", "no", "nr", "num", "nummer", "broj", "index", "idx", "is", "are", "equals", "equal", "at", "of", "has", "was", "ist", "je", "number:"}


EQ_ORDINAL = {"first", "last", "top", "bottom", "next", "previous", "erste", "letzte", "prvi", "poslednji", "zadnji"}
EQ_TAIL = {"id", "no", "nr", "num", "number", "code", "key"}
EQ_OF = {"of", "for", "von", "fuer", "für", "za", "od"}


def eq_filters(t, pq):
    """(column, number text) pairs: a bare number that the question puts right after the name of a column ('visit_id 5650000',
    'cue number 840', 'station index 17'). The name is the nearest word before the number, leaving out 'number', 'index', 'is'."""
    toks = pq["blank"].split()
    out = []
    for k, raw in enumerate(toks):
        s = raw.strip(PUNCT)
        if not re.fullmatch(r"\d+(?:\.\d+)?", s):
            continue
        ws, of = [], False
        for j in range(k - 1, max(-1, k - 4), -1):
            ws = [w for w in words(toks[j].strip(PUNCT)) if w not in EQ_SKIP]
            of = of or toks[j].strip(PUNCT).lower() in EQ_OF
            if ws:
                break
        sw = set(ws)
        if not ws or sw & EQ_ORDINAL:   # 'the last 2 rows', 'top 5': a count of records, not a key
            continue
        whole = [i for i in range(len(t.cols)) if t.colw[i] and t.colw[i] <= sw]
        if whole:
            ci = max(whole, key=lambda i: (len(t.colw[i]), -i))
        else:   # 'invoice 1234' names the column invoice_no: a column name without its id-like tail words
            part = [i for i in range(len(t.cols)) if t.colw[i] - EQ_TAIL and t.colw[i] - EQ_TAIL <= sw]
            if len(part) != 1:
                continue
            ci = part[0]
        if of and not t.colw[ci] & EQ_TAIL:   # 'cost_eur of 7512345': the column is what is asked for, the number names the record
            continue
        out.append((ci, s))
    return out


BARE_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")


def bare_key(t, pq, keys):
    """(column, number text) for a pure lookup whose one bare number names a record by its key, without the key column's name ('cost_eur of 7512345', fix round 13):
    the number lies in the range of a unique key column the look advertised for this table (`keys`: facts.find_keys), or, when the look
    kept none, it is the value of exactly one numeric column the question does not name. A column the question names is the measure, not the key.
    The table's own rows decide between two keys that both fit: the one that holds the number. -> [(column index, number text)] or []."""
    if set(pq["ops"]) - {"sum", "mean", "max", "min"} or pq["group"] or (pq["which"] and col_for(t, pq["which"]) is not None) or pq["cmps"] or pq["years"] or not t.rows:   # "total of 8031": the sum of one record is its value
        return []
    lits = list(dict.fromkeys(BARE_NUM.findall(NOT_A_KEY.sub(" ", pq["blank"]))))
    if len(lits) != 1:
        return []
    lit = lits[0]
    want = float(lit)
    if lit in {x for _, x in eq_filters(t, pq)}:   # "PETALLEN 22" puts the number right after a column: a value of that column, not a key
        return []
    named = {i for i in range(len(t.cols)) if t.colw[i] and t.colw[i] <= pq["allw"]}
    if not named:   # a key lookup asks for something of the record: a column of the table is named
        return []
    whole = t.total is None and "one pass" not in t.where   # every row is held: a column can be tested for being unique

    def holds(i):
        return any(num(r[i] if i < len(r) else None) == want for r in t.rows)

    adv = []
    for k in keys or []:
        try:
            lo, hi = float(k["lo"]), float(k["hi"])
        except (KeyError, TypeError, ValueError):
            continue
        ident = k.get("table") or ""
        for i, c in enumerate(t.cols):
            if c == k.get("column") and i not in named and lo <= want <= hi and t.numeric(i) and (not ident or not t.ident or ident == t.ident or ident == t.name or t.name.endswith(ident)):
                adv.append(i)
    if adv:
        return [(next((i for i in adv if holds(i)), adv[0]), lit)]
    if keys:   # the look named the key columns and the number is in none of their ranges: it is no key
        return []
    found = [i for i in range(len(t.cols)) if i not in named and t.numeric(i) and holds(i)
             and (not whole or len({str(r[i]).strip() for r in t.rows}) == len(t.rows))]
    return [(found[0], lit)] if len(found) == 1 else []


def point_cols(t, pq, skip):
    """The columns a lookup question asks for: those whose name words the question holds best (not the key columns it filtered on)."""
    qw = pq["allw"]   # every word, the filler and operation words too: 'total', 'value' and 'first' name columns of a record
    scored = [(len(t.colw[i] & qw) / len(t.colw[i]), i) for i in range(len(t.cols)) if i not in skip and t.colw[i] and t.colw[i] & qw]
    if not scored:
        return []
    top = max(sc for sc, _ in scored)
    return [i for sc, i in scored if sc == top][:3]


def point_answer(t, pq, keep, fcols, lines):
    """One record (or a few) asked for by its key: 'Answer: <column> = <value> (where <key column> = <key>; <unit> <position>)', then the record in full."""
    pc = point_cols(t, pq, fcols)
    if not pc:
        return None
    said = "; ".join(f"{t.cols[c]} = {P.short(t.rows[k][c], 400)}" for k in keep for c in pc)
    where = ", ".join(f"{t.cols[f]} = {P.short(t.rows[keep[0]][f], 40)}" for f in sorted(fcols))
    lines.insert(0, f"Answer: {said} (where {where}; {t.unit} {', '.join(str(t.pos[k]) for k in keep)})")
    lines.append(f"The {t.unit}(s) in full:")
    for k in keep:
        lines.append(f"  {t.unit} {t.pos[k]}: " + "; ".join(f"{c} = {P.short(x, 400)}" for c, x in zip(t.cols, t.rows[k]) if str(x).strip() != ""))
    return lines


FILLER = {"contain", "include", "hold", "list", "listed", "stored", "recorded", "present", "available", "exist", "dataset", "spreadsheet", "workbook", "database",
          "collection", "sheet", "worksheet", "entry", "item", "line", "case", "observation", "element", "cue", "message", "packet", "event", "record", "row"}   # words that name the rows or the file, not a condition


def leftover_words(t, pq):
    """The content words of a count question that name no column, no part of the table's name, no row noun and no value: a condition this table could not apply."""
    unit = set(words(t.unit))
    return [w for w in dict.fromkeys(pq["words"]) if w not in FILLER and w not in t.namew and w not in unit and col_for(t, w) is None]


def text_columns(t, pq):
    """The columns a word filter reads: the text columns the question names, else every text column."""
    text = [i for i in range(len(t.cols)) if not t.numeric(i)]
    named = [i for i in text if t.colw[i] and t.colw[i] <= pq["allw"]]
    return named or text


def refusal(t, head, left):
    """A count that matched no filter: say so, list what `--ask` can do on this table, and give no figure."""
    cols = ", ".join(t.cols[:12]) + (f", ... ({len(t.cols)} columns)" if len(t.cols) > 12 else "")
    return [head,
            "Answer: not answered: no filter matched the question" + (f" ({'; '.join(left[:4])})" if left else "") + f", so no count was made. The table has {len(t.rows):,} {t.unit}s in all.",
            f"It can count {t.unit}s where a column compares with a number (\"<column> over N\"), where a column equals a value as the data writes it (\"<column> = '<value>'\"), "
            f"where a text column contains a whole word (\"contain the word 'X'\"), or per column (\"{t.unit}s per <column>\"). Columns: {cols}."]


def answer(t, pq, q, vals, keys=None):
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
        if gi is None and g and len(words(g)) > 1:   # "which parcel_no ...": a column written with a separator is one name of several words
            gi = col_phrase(t, words(g), False)
            gi = col_phrase(t, words(g), True) if gi is None else gi
        if gi is not None:
            group = gi
            break
    for i, vs in by_col.items():
        if i == group and len(vs) < 1:
            continue
        keep = [k for k in keep if str(t.rows[k][i] if i < len(t.rows[k]) else "").strip().lower() in vs]
        filt.append(f"{t.cols[i]} = " + " or ".join(repr(v) for v in sorted(vs)))
    fcols = set(by_col)
    for ci, lit in eq_filters(t, pq):
        want = float(lit)
        hit = [k for k in keep if (lambda c: (num(c) == want) if num(c) is not None else str(c).strip() == lit)(t.rows[k][ci] if ci < len(t.rows[k]) else "")]
        if not hit and not (t.colw[ci] & EQ_TAIL):   # 'sales 2021' names a year, not a sales figure: a measure column that holds no such number is not a key
            continue
        keep = hit
        filt.append(f"{t.cols[ci]} = {lit}")
        fcols.add(ci)
    if not fcols:   # "cost_eur of 7512345": a bare number that is a key of this table names the record
        for ci, lit in bare_key(t, pq, keys):
            want = float(lit)
            keep = [k for k in keep if num(t.rows[k][ci] if ci < len(t.rows[k]) else None) == want]
            filt.append(f"{t.cols[ci]} = {lit} (the key column the look names)")
            fcols.add(ci)
    unmatched = []   # parts of the question that asked for a filter this table could not apply
    tf = pq.get("contains")
    if tf:
        cols = text_columns(t, pq)
        if cols:
            rx = needle_regex(tf["needle"], tf["nocase"])
            keep = [k for k in keep if any(rx.search(str(t.rows[k][i])) for i in cols if i < len(t.rows[k]))]
            filt.append(f"text contains the whole {'phrase' if len(tf['needle'].split()) > 1 else 'word'} {tf['needle']!r} ({'any case' if tf['nocase'] else 'case as written'}) in "
                        + (f"column {t.cols[cols[0]]}" if len(cols) == 1 else f"any of the {len(cols)} text columns"))
        else:
            unmatched.append(f"the word {tf['needle']!r} (this table has no text column)")
    measure = pick_measure(t, pq, exclude={group})
    for op, val, at in pq["cmps"]:
        before = re.findall(r"[^\W_]+", pq["fq"][:at])
        ci = col_phrase(t, before)   # 'Petal_Length greater than 5': the column whose whole name stands before the comparison, not any column with 'length' in it
        for w in reversed(before[-4:]):
            if ci is not None:
                break
            ci = col_for(t, stem(w), True)
        ci = ci if ci is not None else measure
        if ci is None:
            unmatched.append(f"the comparison {op} {P.fmt(val)} (no column named)")
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
    if unmatched:   # the question asked for a filter this table cannot apply: no figure over the unfiltered rows may stand as the answer
        return refusal(t, head, unmatched)

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
    hw = col_for(t, stem(hm.group(1)), True) if main_op == "count" and hm and stem(hm.group(1)) not in t.namew else None
    if hw is not None and measure_ok(t, pq, hw) and not (t.colw[hw] & EQ_TAIL):   # "how many units": the Units column, summed (an id or code column is never summed)
        measure, main_op = hw, "sum"
    if main_op == "count" and measure is not None and "sum" in ops:
        main_op = "sum"
    if group is None and fcols and len(keep) == 1 and main_op in (None, "sum", "mean", "max", "min"):   # a key names one record: its column, not an aggregate of one
        got = point_answer(t, pq, keep, fcols, lines)
        if got:
            return got
    if measure is None and main_op in ("count", "sum", "mean", "max", "min") and len(named_words(t, pq)) >= 2:
        return None   # the question names two numeric columns and no column names both: no table answers it exactly
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
        if not filt:   # nothing the question asked for was applied: the row count of the whole table is not its answer
            left = unmatched + [f"the word {w!r}" for w in leftover_words(t, pq)]
            if left or main_op != "count":
                return refusal(t, head, left)
        lines.insert(0, f"Answer: {len(keep):,} {t.unit}s match" + (" (the question names no condition, so this is every row)" if not filt else ""))
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
    if fcols and 0 < len(keep) <= 5:
        got = point_answer(t, pq, keep, fcols, lines)
        if got:
            return got
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
    import dl_colour   # fix round 14: "how many pixels have the colour RGB (r, g, b)" is a colour count over the whole picture, not a pixel position
    got_px = dl_colour.try_ask(q, path, lj, getattr(o, "no_tools", False))
    if got_px:
        return dl_drill.done(got_px)
    import dl_pixel   # a pixel of a still picture ("pixel x,y"): its own exact answer
    got_px = dl_pixel.try_ask(q, path, lj, getattr(o, "no_tools", False))
    if got_px:
        return dl_drill.done(got_px)
    import dl_r14f2   # fix round 14: a declared code page, the spatial reference system of a GeoPackage, a line of a small text member of an archive
    for route in (lambda: dl_r14f2.try_ask_encoding(q, lj), lambda: dl_r14f2.try_ask_srs(q, path, lj), lambda: dl_r14f2.archive_ask(q, path, lj)):
        got_r14 = route()
        if got_r14:
            return dl_drill.done(got_r14)
    tf = contains_filter(q)
    qe = tf["rest"] if tf else q   # a "contain the word X" clause is a filter of its own: its words are not table or column words
    pq = parse(qe)
    pq["contains"] = tf
    lines = [f"--ask {q!r}", f"Read as: operation {', '.join(pq['ops']) or 'lookup'}; words {', '.join(pq['words']) or '(none)'}"
             + (f"; group by {', '.join(pq['group'])}" if pq["group"] else "") + (f"; comparisons {', '.join(f'{a} {P.fmt(b)}' for a, b, _ in pq['cmps'])}" if pq["cmps"] else "") + f"; language {pq['lang']}"]
    import dl_wordcount   # fix round 11: "how many times does the word X appear" is counted over the whole text, not over a table
    wc = dl_wordcount.answer(q, lj)
    if wc:
        return dl_drill.done("\n".join(lines[:1] + wc))
    notes = []
    cell = None
    if (lj.get("subtype") or "") == "netcdf" or str((lj.get("facts") or {}).get("inner_type", "")).endswith("netcdf"):   # a grid: one cell by index or coordinate value
        import dl_netcdf
        src_ = Path((lj.get("facts") or {}).get("unpacked") or path)
        try:
            cell = dl_netcdf.ask(src_, q)
        except (OSError, ValueError, struct.error, IndexError, KeyError) as e:   # a cut or damaged file: named, never a crash
            notes.append(f"The netCDF grid could not be read for --ask ({type(e).__name__}: {str(e)[:150]}).")
    tables = [] if cell else load_tables(path, out, lj, notes, wanted(pq))
    ranked = sorted(((score(t, pq, qe), t) for t in tables), key=lambda x: (-x[0][0], -len(x[1].rows)))
    got = cell or None
    lines += cell or []
    if ranked and ranked[0][0][0] > 0:
        (_, vals), t = ranked[0]
        got = answer(t, pq, qe, vals, (lj.get("facts") or {}).get("find_keys"))
        if got and t.total:   # only part of the table is in memory: no figure may read as a total
            note = t.partial or f"PARTIAL: {len(t.rows):,} of {t.total:,} {t.unit}s were read (row and memory budget); this answer covers those {t.unit}s only"
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
    filtered = bool(tf) or any(x.startswith("Answer: not answered") for x in lines)   # a word filter or a refusal: the look's whole-file count is not the answer
    if exact and "count" in pq["ops"] and not filtered:   # the look's own count names exactly what was asked: it is the answer, the table count is context
        k, v = exact[0]
        lines = [x.replace("Answer:", "Table count:", 1) if x.startswith("Answer:") else x for x in lines]
        lines.insert(2, f"Answer: {k} {P.fmt(v) if isinstance(v, (int, float)) else v} (the look's own exact count of exactly these words)")
        got = got or ["stated"]
    elif stated:
        lines.append("Counts stated in the look: " + "; ".join(f"{k} {P.fmt(v) if isinstance(v, (int, float)) else v}" for k, v in stated))
    if not got:
        why = " (no column names every question word)" if ranked and ranked[0][0][0] > 0 else " (no table matched the question words)" if tables else " (this file has no table the look can re-read)"
        lines.append("No table answers this exactly" + why + "; the lines below match the question words.")
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
