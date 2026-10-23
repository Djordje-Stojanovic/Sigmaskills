"""SigmaDeepLook generic profiles (fix round 4: generalisation). Stdlib only.

What any careful reader asks of any file, computed the same way for every format:
- `Profiler`: records (CSV rows, JSON objects, JSONL lines, YAML/TOML tables, sheet rows, SQL rows) -> one profile per field with exact
  counts: present, null, empty, distinct, min/max with the record where each first occurs, sum, mean, most frequent values with ties,
  every value with its count when there are few, group-by counts and sums, top and bottom records by each number.
- `text_profile`: headings outline with per-level counts and section sizes, lists, tables, code blocks, links, numbers in key lines.
- `kv_numbers`: `name=value` and `name: value` numbers in free text (logs, configs) with count, min, max, sum, mean.
- `tree_profile`: a file tree (archive or folder): counts and bytes per extension and language, line counts, biggest and longest files,
  test functions, SQL tables, environment variable names, constants.
- `counts`: one "Counts:" fact per look, so aggregate questions are answered with exact numbers, never with a rounded estimate.

Every number printed here is exact (thousands separators, no 1.2k): an estimate is said to be one.
"""
import math
import re
from collections import Counter

import dl_textx

DISTINCT_CAP = 50_000      # distinct values kept with their counts per field
HASH_CAP = 5_000_000       # past that, distinct values are counted by hash up to this many
ENUM_ALL = 40              # a field with at most this many distinct values gets every value with its count (in --more)
ENUM_TOP = 25              # otherwise the most frequent this many
GROUP_MAX_KEYS = 3         # categorical fields used for group-by
GROUP_MAX_NUM = 5          # numeric fields summed per group
GROUP_MAX_DISTINCT = 30    # a categorical field with at most this many values is a group-by key
TOPN = 5
KEY_MIN_ROWS = 11          # a table with fewer rows is printed in full: no "find one record" line
KEY_MAX_LEN = 60
NUM_RE = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
NUM_SEP_RE = re.compile(r"^[-+]?\d{1,3}(,\d{3})+(\.\d+)?$")
ID_RE = re.compile(r"(^|[_\s.-])(id|key|uuid|guid|sku|code|zip|phone)$|^id$", re.I)
NULL_WORDS = {"null", "none", "na", "n/a", "nan", "nil", "-", "#n/a"}


def fmt(x):
    """An exact number for people: 1234567 -> 1,234,567; 12.5 -> 12.5; 0.333333 -> 0.3333."""
    if x is None:
        return "?"
    if isinstance(x, bool):
        return str(x).lower()
    if isinstance(x, int):
        return f"{x:,}"
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if f != f or f in (math.inf, -math.inf):
        return str(f)
    if f.is_integer() and abs(f) < 1e15:
        return f"{int(f):,}"
    a = abs(f)
    if a >= 1000:
        return f"{f:,.2f}"
    if a >= 1:
        return f"{f:.4g}" if a < 100 else f"{f:.2f}"
    return f"{f:.4g}"


def short(v, n=40):
    s = " ".join(str(v).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def short_id(v, n=40, keep=200):
    """short(), but a value with no blank in it (a URL, path, e-mail, key, file name) stays whole up to `keep` characters: a cut
    identifier reads as another identifier (fix round 10: a feed URL cut with an ellipsis gave a confident wrong answer)."""
    s = " ".join(str(v).split())
    return s if len(s) <= n or (" " not in s and len(s) <= keep) else s[:n - 1] + "…"


def keyof(v):
    """The value as counted and grouped: stripped text, lower-case booleans, whole floats as ints."""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return int(v)
    if isinstance(v, (dict, list)):
        return short(v, 80)
    return v


def as_number(v, coerce):
    """-> float or None. Real numbers always count; strings count when `coerce` (CSV, sheets) and they look like a number."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v == v else None
    if coerce and isinstance(v, str):
        s = v.strip()
        if NUM_RE.match(s):
            try:
                return float(s)
            except ValueError:
                return None
        if NUM_SEP_RE.match(s):
            return float(s.replace(",", ""))
    return None


def kind_of(v, coerce):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return "empty"
        if coerce:
            if s.lower() in NULL_WORDS:
                return "null"
            if s.lower() in ("true", "false"):
                return "bool"
            if NUM_RE.match(s):
                return "int" if re.match(r"^[-+]?\d+$", s) else "float"
            if NUM_SEP_RE.match(s):
                return "number-with-commas"
            if re.match(r"^\d{4}-\d{2}-\d{2}", s):
                return "date"
        return "text"
    if isinstance(v, (list, tuple)):
        return "list"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


class Multi(list):
    """Several values of one field inside one record (the elements of a list)."""


LEN = "#items"   # suffix of the field that holds a list's length


def flatten(rec, prefix="", out=None, depth=0):
    """A nested record -> {dotted.path: scalar}. A list gives `path[]` (its elements, as a Multi), `path[].key` for lists of objects,
    and `path[]#items` = its length."""
    out = {} if out is None else out
    if isinstance(rec, dict) and depth < 6:
        if not rec and prefix:
            out[prefix] = None
        for k, v in rec.items():
            flatten(v, f"{prefix}.{k}" if prefix else str(k), out, depth + 1)
    elif isinstance(rec, list) and depth < 6:
        key = (prefix or "") + "[]"
        out[key + LEN] = len(rec)
        for x in rec:
            for k, v in flatten(x, key, {}, depth + 1).items():
                cur = out.get(k)
                if not isinstance(cur, Multi):
                    cur = out[k] = Multi()
                cur.extend(v if isinstance(v, Multi) else [v])
    else:
        out[prefix or "value"] = rec
    return out


def flat_of(rec):
    if isinstance(rec, dict) and not any(isinstance(v, (dict, list)) for v in rec.values()):
        return rec
    return flatten(rec)


class Field:
    """One field over every record."""
    def __init__(self, name, order):
        self.name, self.order = name, order
        self.present = self.nulls = self.empties = 0
        self.kinds = Counter()
        self.counts, self.first_at, self.overflow = Counter(), {}, False
        self.hashes = None   # past DISTINCT_CAP: hashes of every value, so the distinct count stays exact (up to HASH_CAP)
        self.n = 0
        self.sum = 0.0
        self.sq = 0.0
        self.lo = self.hi = None
        self.lo_at = self.hi_at = None
        self.lo_n = self.hi_n = 0     # how many records hold the minimum / the maximum
        self.len_lo = self.len_hi = None
        self.len_hi_at = None
        self.first_text = None

    def add(self, v, idx, coerce):
        self.present += 1
        x = None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                self.kinds["empty"] += 1
                self.empties += 1
                return
            key = s
            c = s[0]
            if coerce and (c.isdigit() or c in "-+.") and NUM_RE.match(s):
                x = float(s)
                k = "float" if ("." in s or "e" in s or "E" in s) else "int"
            elif coerce:
                k = kind_of(s, True)
                if k == "null":
                    self.kinds["null"] += 1
                    self.nulls += 1
                    return
                if k == "number-with-commas":
                    x = float(s.replace(",", ""))
            else:
                k = "text"
            ln = len(s)
            if self.len_lo is None or ln < self.len_lo:
                self.len_lo = ln
            if self.len_hi is None or ln > self.len_hi:
                self.len_hi, self.len_hi_at = ln, idx
        elif v is None:
            self.kinds["null"] += 1
            self.nulls += 1
            return
        elif isinstance(v, bool):
            k, key = "bool", str(v).lower()
        elif isinstance(v, int):
            k, key, x = "int", v, float(v)
        elif isinstance(v, float):
            if v != v:
                self.kinds["null"] += 1
                self.nulls += 1
                return
            k, x = "float", v
            key = int(v) if v.is_integer() and abs(v) < 1e15 else v
        else:
            k, key = kind_of(v, coerce), short(v, 80)
        self.kinds[k] += 1
        if x is not None:
            self.n += 1
            self.sum += x
            self.sq += x * x
            if self.lo is None or x < self.lo:
                self.lo, self.lo_at, self.lo_n = x, idx, 1
            elif x == self.lo:
                self.lo_n += 1
            if self.hi is None or x > self.hi:
                self.hi, self.hi_at, self.hi_n = x, idx, 1
            elif x == self.hi:
                self.hi_n += 1
        if not self.overflow:
            cnt = self.counts
            if key in cnt:
                cnt[key] += 1
            elif len(cnt) >= DISTINCT_CAP:
                self.overflow = True
                self.hashes = {hash(k) for k in cnt}
                self.hashes.add(hash(key))
            else:
                cnt[key] = 1
                self.first_at[key] = idx
        elif self.hashes is not None:
            self.hashes.add(hash(key))
            if len(self.hashes) > HASH_CAP:
                self.hashes = None

    # ---- derived
    def dominant(self):
        real = [(k, n) for k, n in self.kinds.items() if k not in ("null", "empty")]
        return max(real, key=lambda kv: kv[1])[0] if real else "empty"

    def numeric(self):
        return self.n > 0 and self.n >= 0.6 * max(1, self.present - self.nulls - self.empties)

    def distinct(self):
        if self.overflow and self.hashes is not None:
            return len(self.hashes)
        return len(self.counts)

    def distinct_exact(self):
        return not self.overflow or self.hashes is not None

    def top(self, k=5):
        """-> [(value, count)], plus the number of values tied with the last one shown."""
        mc = self.counts.most_common()
        if not mc:
            return [], 0
        shown = mc[:k]
        cut = shown[-1][1]
        ties = sum(1 for _, c in mc if c == cut) - sum(1 for _, c in shown if c == cut)
        return shown, ties

    def mean(self):
        return self.sum / self.n if self.n else None

    def std(self):
        if self.n < 2:
            return None
        m = self.sum / self.n
        return math.sqrt(max(0.0, self.sq / self.n - m * m))


class Profiler:
    """Feed records (dicts, flat or nested) one at a time; ask for lines afterwards. Index `idx` is what a reader calls the record:
    a 1-based row or line number, or an array index."""
    def __init__(self, coerce=False, label="record"):
        self.coerce, self.label = coerce, label
        self.fields, self.n = {}, 0
        self.keys_per_record = Counter()
        self.last = None   # (index, [(field, value)]) of the last record fed: the end of the file is a fact too
        self.marks = {}    # record number -> (index, pairs) at the fixed positions (1-5, 10, 20, 25 ...): "the 100th row" is a fact too

    def add(self, rec, idx=None):
        self.n += 1
        idx = self.n if idx is None else idx
        flat = flat_of(rec)
        self.last = (idx, flat)
        if dl_textx.is_landmark(self.n):
            self.marks[self.n] = (idx, list(flat.items()))
        self.keys_per_record[len(flat)] += 1
        for k, v in flat.items():
            f = self.fields.get(k)
            if f is None:
                f = self.fields[k] = Field(k, len(self.fields))
            if isinstance(v, Multi):
                for x in v:
                    f.add(x, idx, self.coerce)
            else:
                f.add(v, idx, self.coerce)

    def columns(self, names):
        """Fixed columns (a table): returns the Field list for add_row."""
        return [self.fields.setdefault(nm, Field(nm, len(self.fields))) for nm in names]

    def add_row(self, cols, values, idx):
        """Fast path for tables: values line up with cols (from columns())."""
        self.n += 1
        co = self.coerce
        self.last = (idx, cols, values)
        if dl_textx.is_landmark(self.n):
            self.marks[self.n] = (idx, [(f.name, v) for f, v in zip(cols, values)])
        for f, v in zip(cols, values):
            f.add(v, idx, co)

    def marks_facts(self, look, pri=74, width=36, fields=10):
        """The records at fixed positions (row 1-5, 10, 20, 25 ... 100 ...) as two facts, each with its file index."""
        noun = "row" if self.label in ("line", "row", "sheet row") else self.label

        def show(k):
            if k not in self.marks:
                return None
            idx, pairs = self.marks[k]
            body = "; ".join(f"{a}={short_id(v, width)}" for a, v in pairs[:fields]) + (f"; +{len(pairs) - fields} more" if len(pairs) > fields else "")
            return f"#{k} ({self.label} {idx}): {body}"
        if self.n > 3:
            dl_textx.marks_lines(look, self.n, show, noun, pri, keep=set(self.marks))

    def last_line(self, width=44, fields=16):
        """'Last row (line 801; 800 in all): id=800; name=n0 ...': the final record, so a question about the end of the file needs no later step."""
        if not self.last:
            return ""
        idx = self.last[0]
        if len(self.last) == 3:
            pairs = [(f.name, v) for f, v in zip(self.last[1], self.last[2])]
        else:
            pairs = list(self.last[1].items()) if isinstance(self.last[1], dict) else list(self.last[1])
        noun = "row" if self.label in ("line", "row", "sheet row") else self.label
        body = "; ".join(f"{k}={short_id(v, width)}" for k, v in pairs[:fields]) + (f"; +{len(pairs) - fields} more fields" if len(pairs) > fields else "")
        return f"Last {noun} ({self.label} {idx}; {fmt(self.n)} in all): {body}"

    def ordered(self):
        return sorted(self.fields.values(), key=lambda f: f.order)

    # ---- where one record lives (fix round 11)
    def _edge(self, which, name):
        """The value of field `name` in the first (marks[1]) or last record fed, or None."""
        rec = self.marks.get(1) if which == "first" else self.last
        if not rec:
            return None
        if which == "first":
            return dict(rec[1]).get(name)
        if len(rec) == 3:
            return next((v for f, v in zip(rec[1], rec[2]) if f.name == name), None)
        return dict(rec[1]).get(name) if not isinstance(rec[1], dict) else rec[1].get(name)

    def key_fields(self, limit=3, text_first=False):
        """Fields that name one record: present in every record and different in each (text up to 60 characters, or whole numbers)."""
        out = []
        for f in self.ordered():
            if self.n < KEY_MIN_ROWS or "[]" in f.name or f.name.endswith(LEN) or f.present != self.n or f.nulls or f.empties:
                continue
            if not f.distinct_exact() or f.distinct() != self.n or f.dominant() not in ("int", "text", "float"):
                continue
            if f.dominant() == "float" and not (f.n == self.n and f.lo is not None and f.hi is not None and float(f.lo).is_integer() and float(f.hi).is_integer() and f.hi - f.lo + 1 <= 4 * self.n):
                continue   # SAS and Excel hold whole numbers as floats: a float field is a key only when it is a dense run of whole numbers
            if f.dominant() == "text" and (f.len_hi or 0) > KEY_MAX_LEN:
                continue
            out.append(f)
        if text_first:   # a database line names one key per table: the text one (mark_code) before the row number (fid)
            out.sort(key=lambda f: f.dominant() != "text")
        return out[:limit]

    def key_range(self, f):
        """'first .. last' of a key field: numbers by value, text by sorted order when every value is held, else in file order."""
        if f.dominant() in ("int", "float") and f.lo is not None:
            return f"{fmt(f.lo)} .. {fmt(f.hi)}"
        if f.counts and not f.overflow:
            ks = [str(k) for k in f.counts]
            return f"{short(min(ks), 24)} .. {short(max(ks), 24)}"
        a, b = self._edge("first", f.name), self._edge("last", f.name)
        return f"{short(a, 24)} .. {short(b, 24)} (file order)" if a is not None and b is not None else ""

    def find_part(self, name=None, noun="rows", limit=3):
        """'table survey_marks, 5,200 rows, key column mark_code (unique, SM-00001 .. SM-05200)', or '' when no field names one record."""
        ASKABLE.append((name, self))   # the next find_line also says which counts can be asked of this table
        keys = self.key_fields(limit, text_first=limit == 1)
        if not keys:
            return ""
        return f"{name + ', ' if name else ''}{fmt(self.n)} {noun}, key column{'s' if len(keys) > 1 else ''} " + ", ".join(f"{f.name} (unique, {self.key_range(f)})" for f in keys)

    # ---- printing
    def field_line(self, f):
        bits = [f.dominant()]
        if f.present != self.n and "[]" not in f.name:
            bits.append(f"in {fmt(f.present)} of {fmt(self.n)} {plural(self.label)}")
        if f.nulls:
            bits.append(f"{fmt(f.nulls)} null")
        if f.empties:
            bits.append(f"{fmt(f.empties)} empty")
        bits.append(f"{'' if f.distinct_exact() else '>='}{fmt(f.distinct())} distinct")
        if f.numeric():
            bits.append(f"min {fmt(f.lo)} ({self.label} {f.lo_at}{', x' + fmt(f.lo_n) if f.lo_n > 1 else ''}), max {fmt(f.hi)} ({self.label} {f.hi_at}{', x' + fmt(f.hi_n) if f.hi_n > 1 else ''})")
            bits.append(f"sum {fmt(f.sum)}, mean {fmt(f.mean())}")
        top, ties = f.top(4)
        if top and not f.overflow and not (f.numeric() and f.distinct() > 12) and not (f.distinct() == f.present - f.nulls - f.empties and f.distinct() > 4):
            bits.append("top " + ", ".join(f"{short(v, 28)} ({fmt(c)})" for v, c in top) + (f" (+{ties} more tied at {top[-1][1]})" if ties else ""))
        elif not f.numeric() and f.len_hi is not None:
            bits.append(f"length {f.len_lo}..{f.len_hi}")
        return f"{f.name}: " + ", ".join(bits)

    def field_lines(self, limit=None):
        return [self.field_line(f) for f in self.ordered()[:limit]]

    def enum_lines(self):
        """Every value with its count for the low-cardinality fields; the most frequent ENUM_TOP for the others (for --more)."""
        out = []
        for f in self.ordered():
            if f.name.endswith(LEN) or not f.counts:
                continue
            d = f.distinct()
            if d <= 1 or (d > 4 and d >= f.present - f.nulls - f.empties):   # every value different: a list of them says nothing
                continue
            mc = f.counts.most_common()
            if d <= ENUM_ALL:
                body = ", ".join(f"{short(v, 40)} {fmt(c)}" for v, c in mc)
                out.append(f"Values of {f.name} (all {d}, with counts): {body}")
            elif not f.numeric() and mc[0][1] > 1:
                body = ", ".join(f"{short(v, 40)} {fmt(c)}" for v, c in mc[:ENUM_TOP])
                once = sum(1 for _, c in mc if c == 1)
                out.append(f"Values of {f.name} (top {ENUM_TOP} of {'' if f.distinct_exact() else '>='}{fmt(d)}{'' if not f.overflow else ', counts from the first ' + fmt(DISTINCT_CAP) + ' distinct'}; {fmt(once)} values occur once): {body}")
            if d <= ENUM_ALL or (mc[0][1] > 1 and not f.numeric()):
                firsts = sorted(((f.first_at.get(v), v) for v, _ in mc[:12]), key=lambda t: (t[0] is None, t[0] if isinstance(t[0], (int, float)) else 0))
                out.append(f"First {self.label} of each value of {f.name}: " + ", ".join(f"{short(v, 30)} @{a}" for a, v in firsts))
        return out

    def stats_lines(self):
        """Numeric fields in full: count, sum, mean, std, min/max with position and ties (for --more)."""
        out = []
        for f in self.ordered():
            if not f.numeric():
                continue
            out.append(f"Stats of {f.name}: {fmt(f.n)} numbers, sum {fmt(f.sum)}, mean {fmt(f.mean())}, std {fmt(f.std())}, "
                       f"min {fmt(f.lo)} first at {self.label} {f.lo_at} (held by {fmt(f.lo_n)}), max {fmt(f.hi)} first at {self.label} {f.hi_at} (held by {fmt(f.hi_n)})"
                       + (f", {fmt(f.nulls + f.empties)} missing" if f.nulls + f.empties else ""))
        return out

    def keys_and_numbers(self):
        cats = [f for f in self.ordered() if not f.name.endswith(LEN) and "[]" not in f.name and 2 <= f.distinct() <= GROUP_MAX_DISTINCT
                and not f.overflow and f.present >= 0.5 * self.n and not (f.numeric() and f.distinct() > 8)
                and f.distinct() < f.present - f.nulls - f.empties][:GROUP_MAX_KEYS]
        lab = self.label_field()
        nums = [f for f in self.ordered() if f.numeric() and "[]" not in f.name and not f.name.endswith(LEN) and f not in cats
                and f.name != lab and not ID_RE.search(f.name)][:GROUP_MAX_NUM]
        return cats, nums

    def label_field(self):
        """The field that names a record: the first text field whose values are (nearly) all different, else an id-named field."""
        cands = [f for f in self.ordered() if "[]" not in f.name and not f.name.endswith(LEN)]
        for f in cands:
            nonmiss = f.present - f.nulls - f.empties
            if nonmiss and f.distinct() >= 0.95 * nonmiss and f.distinct_exact() and not f.numeric():
                return f.name
        for f in cands:
            nonmiss = f.present - f.nulls - f.empties
            if nonmiss and f.distinct() >= 0.95 * nonmiss and f.distinct_exact() and ID_RE.search(f.name):
                return f.name
        return None


class SecondPass:
    """Group-by counts and sums, and the top / bottom records by each number. Needs the field choice of a finished Profiler."""
    def __init__(self, prof):
        self.p = prof
        self.cats, self.nums = prof.keys_and_numbers()
        self.label = prof.label_field()
        self.groups = {c.name: {} for c in self.cats}
        self.tops = {f.name: [] for f in prof.ordered() if f.numeric() and "[]" not in f.name and not f.name.endswith(LEN) and f.name != self.label}

    def add_row(self, names, values, idx):
        """Fast path for tables: only the fields this pass needs are looked up."""
        if not hasattr(self, "_need"):
            need = {c.name for c in self.cats} | {f.name for f in self.nums} | set(self.tops) | ({self.label} if self.label else set())
            self._need = [(i, n) for i, n in enumerate(names) if n in need]
        self.add({n: values[i] for i, n in self._need if i < len(values)}, idx)

    def add(self, rec, idx):
        flat = flat_of(rec)
        for c in self.cats:
            key = keyof(flat.get(c.name))
            g = self.groups[c.name].setdefault(key, [0] + [0.0] * len(self.nums) + [0] * len(self.nums))
            g[0] += 1
            for i, nf in enumerate(self.nums):
                x = as_number(flat.get(nf.name), self.p.coerce)
                if x is not None:
                    g[1 + i] += x
                    g[1 + len(self.nums) + i] += 1
        lab = flat.get(self.label) if self.label else None
        for name, lst in self.tops.items():
            x = as_number(flat.get(name), self.p.coerce)
            if x is not None:
                lst.append((x, idx, short(lab, 30) if lab is not None else ""))
                if len(lst) > 4 * TOPN + 40:
                    lst.sort(key=lambda t: t[0])
                    del lst[TOPN + 10:len(lst) - TOPN - 10]

    def lines(self):
        out = []
        for c in self.cats:
            g = self.groups[c.name]
            rows = sorted(g.items(), key=lambda kv: -kv[1][0])
            parts = []
            for k, v in rows:
                s = f"{short(k, 30) if k not in (None, '') else '(missing)'}: {fmt(v[0])}"
                for i, nf in enumerate(self.nums):
                    if v[1 + len(self.nums) + i]:
                        s += f", {nf.name} sum {fmt(v[1 + i])} mean {fmt(v[1 + i] / v[1 + len(self.nums) + i])}"
                parts.append(s)
            out.append(f"Group by {c.name} ({len(g)} groups; count of {self.p.label}s, then sums and means): " + "; ".join(parts))
        lab = self.label or "record"
        for name, lst in self.tops.items():
            if len(lst) < 2 or len({t[0] for t in lst}) <= 3:
                continue
            lst.sort(key=lambda t: (t[0], t[1]))
            lo = lst[:TOPN]
            hi = sorted(lst, key=lambda t: (-t[0], t[1]))[:TOPN]
            def row(t):
                return f"{fmt(t[0])} ({self.p.label} {t[1]}" + (f", {lab}={t[2]}" if t[2] and lab != name else "") + ")"
            out.append(f"Top {TOPN} by {name}: " + "; ".join(row(t) for t in hi) + f". Bottom {TOPN}: " + "; ".join(row(t) for t in lo))
        return out


def profile(records, coerce=False, label="record", second=True):
    """records: a list of (idx, record) or an iterable factory (callable) giving them; walked twice when `second`. -> (Profiler, lines2)."""
    it = records() if callable(records) else records
    p = Profiler(coerce, label)
    for idx, rec in it:
        p.add(rec, idx)
    extra = []
    if second and p.n:
        sp = SecondPass(p)
        for idx, rec in (records() if callable(records) else records):
            sp.add(rec, idx)
        extra = sp.lines()
    return p, extra


FIND_ASK = 'ask "<measure> of <key value>" with '
ASKABLE = []   # (table name or None, Profiler) of each find_part call; the next find_line turns them into one 'Ask a count' line


ASK_SKIP_RE = re.compile(r"date|time|stamp|year|(^|[_\s.-])(id|no|nr|code|key)$|^id$", re.I)   # not the best column to show in an example


def ask_forms(look, entries, pri):
    """'Ask a count: --ask "how many rows have <number column> over N" or ...; columns: ...' (fix round 12): the count forms `--ask` answers for a table,
    with the file's own column names, so an agent that reads step 1 knows it may ask. One line per look; several tables are named in it."""
    if not entries or getattr(look, "ask_forms_done", False):
        return
    tabs = []
    for name, p in entries[:4]:
        cols = [f for f in p.ordered() if p.n and "[]" not in f.name and not f.name.endswith(LEN)
                and not (f.dominant() == "text" and any(str(k).startswith("<") and "bytes>" in str(k) for k in list(f.counts)[:3]))]
        if not cols:
            continue
        numeric = [f for f in cols if f.numeric() and not ASK_SKIP_RE.search(f.name)] or [f for f in cols if f.numeric()]
        num = next((f for f in numeric if 1 < f.distinct() < p.n), None) or next(iter(numeric), None)
        txt = next((f for f in cols if not f.numeric() and not f.overflow and 2 <= f.distinct() <= 40 and f.distinct() < p.n), None)
        top = 10 if len(entries) == 1 else 6
        shown = ", ".join(short(f.name, 28) for f in cols[:top]) + (f", +{len(cols) - top} more" if len(cols) > top else "")
        tabs.append((name[6:] if name and name.startswith("table ") else name, plural(p.label), num, txt, shown))
    if not tabs:
        return
    look.ask_forms_done = True
    name, noun, num, txt, _ = next((t for t in tabs if t[2] or t[3]), tabs[0])
    what = name if len(tabs) > 1 and name else noun
    forms = ([f'"how many {what} have {num.name} over N"'] if num else []) + ([f"\"how many {what} have {txt.name} = '<value>'\"", f'"{what} per {txt.name}"'] if txt else [])
    cols = tabs[0][4] if len(tabs) == 1 else " | ".join(f"{t[0]}: {t[4]}" for t in tabs)
    look.line("Ask a count: --ask " + (" or ".join(forms) if forms else f'"how many {what} have <column> over N"') + ("; name the table in the question" if len(tabs) > 1 else "")
              + f". Columns: {cols}.", pri, "locate")


def ask_line(look, text, pri):
    """The 'Ask a count' line of a family that has no profiler (subtitle cues, gettext messages); one per look."""
    if not getattr(look, "ask_forms_done", False):
        look.ask_forms_done = True
        look.line("Ask a count: --ask " + text, pri, "locate")


def find_line(look, parts, route="--ask", pri=91, ask=None):
    """'Find one record: <table, rows, key column and range> | <next table ...>; ask "<measure> of <key value>" with --ask': where a single
    record lives, in step 1. parts: the find_part texts (empty ones are dropped). `ask`: the family's own wording of the last clause.
    The tables whose find_part ran since the last call also get one 'Ask a count' line."""
    entries = list(ASKABLE)
    ASKABLE.clear()
    parts = [x for x in parts if x]
    if parts:
        look.line("Find one record: " + " | ".join(parts) + "; " + (ask or FIND_ASK + route), pri, "locate")
    ask_forms(look, entries, pri)


def emit(look, p, extra, what, key_pri=88, more_pri=30, field_limit=24, write_name=None, prefix="", find=None, route="--ask"):
    """Put a profile into a look: one compact 'Fields' fact (step 1), then the full enumerations at a lower priority (--more).
    `find`: the table's name for its 'Find one record' line ("" for the only table; the line is left out when None)."""
    if find is not None:
        find_line(look, [p.find_part(find or None, plural(p.label))], route)
    fl = p.field_lines()
    ll = p.last_line()
    if ll:
        look.line(prefix + ll, key_pri - 2, "last")
        p.marks_facts(look, key_pri - 14)
    head = f"{what}: {fmt(p.n)} records, {fmt(len([f for f in p.fields if not f.endswith(LEN)]))} fields"
    look.line(head + ". Fields (type, missing, distinct, min/max with the " + p.label + " where it first occurs, sum, mean, top values):\n"
              + "\n".join("  " + x for x in fl[:field_limit]) + (f"\n  ... {len(fl) - field_limit} more fields below" if len(fl) > field_limit else ""), key_pri, "profile")
    if len(fl) > field_limit:
        look.line("More fields:\n" + "\n".join("  " + x for x in fl[field_limit:field_limit + 200]), more_pri + 6, "profile")
    for ln in p.stats_lines():
        look.line(prefix + ln, more_pri + 4, "aggregates")
    for ln in extra:
        look.line(prefix + ln, more_pri + 2, "aggregates")
    for ln in p.enum_lines():
        look.line(prefix + ln, more_pri, "values")
    if write_name:
        body = "\n".join(fl + [""] + p.stats_lines() + [""] + extra + [""] + p.enum_lines())
        look.write_text(write_name, body, f"full field profile of the {p.label}s: every count, sum, value list", value=3, inline=False)


# ---------------------------------------------------------------- the Counts block
def plural(w):
    """record -> records, index -> indexes, entry -> entries."""
    return w[:-1] + "ies" if w.endswith("y") and w[-2:-1] not in "aeiou" else w + "es" if w.endswith(("x", "s", "ch", "sh")) else w + "s"


TABLE_ROWS_MAX = 40   # a document table up to this many rows is printed row by row (fix round 10: a value in a middle row is a fact)


def table_rows(title, rows, limit=TABLE_ROWS_MAX, width=60):
    """A small table of a document, every row with its cells joined by ' | ' -> the fact text, or '' when it has more rows than `limit`."""
    if not rows or len(rows) > limit:
        return ""
    return f"{title} ({len(rows)} rows, every row; cells split by ' | '):\n" + "\n".join(
        f"row {k}: " + " | ".join(short(c, width) for c in r) for k, r in enumerate(rows, 1))


def counts(look, pairs, pri=94, title="Counts"):
    """One fact: 'Counts: rows 1,234; columns 9; ...' with exact numbers. pairs: [(name, value)] (None values dropped)."""
    items = [(k, v) for k, v in pairs if v is not None and v != ""]
    if not items:
        return
    look.line(f"{title}: " + "; ".join(f"{k} {fmt(v) if isinstance(v, (int, float)) else v}" for k, v in items), pri, "counts")
    for k, v in items:
        look.facts.setdefault("counts", {})[k] = v


# ---------------------------------------------------------------- text structure
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SETEXT_RE = re.compile(r"^(=+|-+)\s*$")
LIST_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+\S")
TASK_RE = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)[^)]*\)|https?://[^\s)>\]]+")
# `key=12`, `key = 12 ms`, `key: 12` (a colon needs a space or quote after it, so `File.java:88` is not a pair); a unit only when it
# is not the start of the next key (`status=200 ms=12` is status 200 and ms 12)
KV_NUM_RE = re.compile(r"(?<![\w.])([A-Za-z_][\w.\-]{1,40}?)\s*(?:=|:(?=[\s\"]))\s*\"?([-+]?\d+(?:[.,]\d+)?)(?:\s*(ms|s|sec|min|h|%|kb|mb|gb|b|bytes|px|x)(?![\w=:]))?(?!\w|\.\d)", re.I)
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
WORD_RE = re.compile(r"\w+", re.U)


def text_profile(look, text, pri=90, kind="Text"):
    """Line, word and character counts; for markdown-like text the heading outline with per-level counts and the size of each section,
    the first and last section, list items, tasks, tables, code blocks, links, dates, and numbers on key lines."""
    lines = text.splitlines()
    n = len(lines)
    blank = sum(1 for x in lines if not x.strip())
    words = len(WORD_RE.findall(text))
    rst = dl_textx.rst_headings(lines)   # reST-style underlines of any character: the titles come from there, not from the markdown rules
    heads, in_code, fences, code_lines = (list(rst) if rst else []), False, 0, 0
    lists = tasks = done_tasks = table_rows = tables = quotes = 0
    prev_table = False
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if rst:
            if LIST_RE.match(ln):
                lists += 1
            continue
        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            fences += 1 if in_code else 0
            continue
        if in_code:
            code_lines += 1
            continue
        m = HEAD_RE.match(ln)
        if m and m.group(2):
            heads.append([len(m.group(1)), m.group(2).strip(), i])
        elif i > 1 and SETEXT_RE.match(ln) and lines[i - 2].strip() and not HEAD_RE.match(lines[i - 2]) and not LIST_RE.match(lines[i - 2]) and len(s) >= 3:
            heads.append([1 if s[0] == "=" else 2, lines[i - 2].strip(), i - 1])
        if LIST_RE.match(ln):
            lists += 1
        t = TASK_RE.match(ln)
        if t:
            tasks += 1
            done_tasks += t.group(1).lower() == "x"
        is_table = s.startswith("|") and s.count("|") >= 2
        if is_table:
            if not re.match(r"^\|?\s*:?-{2,}", s):
                table_rows += 1
            if not prev_table:
                tables += 1
        prev_table = is_table
        if s.startswith(">"):
            quotes += 1
    links = LINK_RE.findall(text)
    dates = sorted(set(DATE_RE.findall(text)))
    per_level = Counter(h[0] for h in heads)
    pairs = [("lines", n), ("non-blank lines", n - blank), ("words", words), ("characters", len(text))]
    paragraphs = dl_textx.facts(look, lines, short, pri - 6)
    is_rst = bool(rst) or str(getattr(look, "path", "")).lower().endswith((".rst", ".rest")) or len(dl_textx.directives(lines)) >= 2
    if is_rst:   # Sphinx files often use only = and - underlines (read as markdown titles above): the reST parts are counted all the same
        tables, fences = dl_textx.rst_facts(look, lines, heads, short, pri - 2)
    if paragraphs > 1:
        pairs.append(("paragraphs", paragraphs))
    if heads:
        pairs.append(("headings", len(heads)))
        pairs += [(f"level-{k} headings", per_level[k]) for k in sorted(per_level)]
    pairs += [("list items", lists or None), ("task boxes", f"{tasks} ({done_tasks} checked)" if tasks else None), ("tables", tables or None),
              ("table rows (incl. header)", table_rows or None), ("code blocks", fences or None), ("links", len(links) or None), ("quote lines", quotes or None)]
    counts(look, pairs, pri + 4, f"{kind} counts")
    if heads:
        for j, h in enumerate(heads):   # section size: lines up to the next heading of the same or a higher level
            end = next((k[2] for k in heads[j + 1:] if k[0] <= h[0]), n + 1)
            h.append(end - h[2])
        first, last = heads[0], heads[-1]
        top_level = min(per_level)
        tops = [h for h in heads if h[0] == top_level]
        look.line(f"Sections: {len(heads)} headings; first '{short(first[1], 60)}' (line {first[2]}), last '{short(last[1], 60)}' (line {last[2]}, level {last[0]}); "
                  f"{len(tops)} at the top level (#{'#' * (top_level - 1)}), last top-level '{short(tops[-1][1], 60)}' (line {tops[-1][2]}).", pri)
        body = [f"{'  ' * (h[0] - 1)}{'#' * h[0]} {short(h[1], 70)}  (line {h[2]}, {h[3]} lines)" for h in heads]
        look.line(f"Outline ({len(heads)} headings, line number and section size):\n" + "\n".join(body[:30]) + (f"\n... {len(body) - 30} more in the outline below" if len(body) > 30 else ""), pri - 22, "outline")
        if len(body) > 30:
            for k in range(30, len(body), 60):
                look.line("Outline, continued:\n" + "\n".join(body[k:k + 60]), 28, "outline")
    if dates:
        look.line(f"Dates in the text: {len(dates)} distinct, earliest {dates[0]}, latest {dates[-1]}" + (f"; all: {', '.join(dates)}" if len(dates) <= 30 else ""), pri - 30)
    kv_numbers(look, lines, pri - 28)
    return heads


def kv_numbers(look, lines, pri=60, max_keys=40, title="Numbers on key lines"):
    """`key=number` / `key: number` pairs over all lines -> per key: count, min, max, sum, mean, the line of the first one.
    lines: strings (numbered from 1), or (line number, text) or (line number, text, group) tuples; with groups (a log level, say)
    each key also gets its count, min, max and mean per group."""
    acc, grp = {}, {}
    for i, ln in enumerate(lines, 1):
        g = None
        if isinstance(ln, tuple):
            i, ln, g = (ln + (None,))[:3]
        if len(ln) > 2000:
            ln = ln[:2000]
        for m in KV_NUM_RE.finditer(ln):
            k = m.group(1).lower().strip(".-")
            if len(k) < 2 or k.isdigit():
                continue
            try:
                x = float(m.group(2).replace(",", "."))
            except ValueError:
                continue
            unit = (m.group(3) or "").lower()
            a = acc.get((k, unit))
            if a is None:
                if len(acc) > 2000:
                    continue
                a = acc[(k, unit)] = [0, 0.0, x, x, i, i, i]
            a[0] += 1
            a[1] += x
            if x < a[2]:
                a[2], a[5] = x, i
            if x > a[3]:
                a[3], a[6] = x, i
            if g is not None:
                b = grp.setdefault((k, unit), {}).get(g)
                if b is None:
                    b = grp[(k, unit)][g] = [0, 0.0, x, x, i, i]
                b[0] += 1
                b[1] += x
                if x < b[2]:
                    b[2], b[4] = x, i
                if x > b[3]:
                    b[3], b[5] = x, i
    good = sorted(((k, u, a) for (k, u), a in acc.items() if a[0] >= 1), key=lambda t: (-t[2][0], t[0]))[:max_keys]
    if not good:
        return {}
    rows = [f"{k}{(' (' + u + ')') if u else ''}: {fmt(a[0])}x, min {fmt(a[2])} (line {a[5]}), max {fmt(a[3])} (line {a[6]}), sum {fmt(a[1])}, mean {fmt(a[1] / a[0])}, first line {a[4]}" for k, u, a in good]
    look.line(f"{title} (key = number, over every line):\n" + "\n".join("  " + r for r in rows[:12]), pri, "aggregates")
    if len(rows) > 12:
        look.line(f"{title}, continued:\n" + "\n".join("  " + r for r in rows[12:]), 27, "aggregates")
    by = []
    for k, u, a in good[:20]:
        gs = grp.get((k, u)) or {}
        if len(gs) > 1:
            by.append(f"{k}{(' (' + u + ')') if u else ''}: " + "; ".join(
                f"{g} {fmt(b[0])}x, min {fmt(b[2])} (line {b[4]}), max {fmt(b[3])} (line {b[5]}), mean {fmt(b[1] / b[0])}"
                for g, b in sorted(gs.items(), key=lambda kv: -kv[1][0])))
    if by:
        look.line(f"{title}, per level (count, min, max, mean):\n" + "\n".join("  " + r for r in by), pri - 30, "aggregates")
    return acc


# ---------------------------------------------------------------- trees (archives, folders)
CODE_LANG = {".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
             ".jsx": "JavaScript", ".java": "Java", ".kt": "Kotlin", ".scala": "Scala", ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C/C++ header",
             ".cpp": "C++", ".cc": "C++", ".hpp": "C++", ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".sh": "Shell", ".bash": "Shell",
             ".ps1": "PowerShell", ".bat": "Batch", ".cmd": "Batch", ".lua": "Lua", ".r": "R", ".sql": "SQL", ".html": "HTML", ".htm": "HTML",
             ".css": "CSS", ".scss": "SCSS", ".vue": "Vue", ".svelte": "Svelte", ".md": "Markdown", ".rst": "reST", ".txt": "Text", ".json": "JSON",
             ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".xml": "XML", ".ini": "INI", ".cfg": "INI", ".properties": "Properties",
             ".gradle": "Gradle", ".csv": "CSV", ".tsv": "TSV", ".ipynb": "Notebook", ".dart": "Dart", ".pl": "Perl", ".m": "Objective-C/Matlab"}
TEXT_EXT = set(CODE_LANG) | {".env", ".lock", ".mf", ".gitignore", ".dockerfile", ".tf", ".hcl", ".graphql", ".proto", ".svg", ".log"}
TEXT_NAMES = {"makefile", "dockerfile", "license", "licence", "readme", "changelog", "notice", "authors", "copying", "procfile", "gemfile", "rakefile", "jenkinsfile"}
TEST_FN_RE = re.compile(r"(?m)^\s*(?:async\s+)?def\s+(test\w*)\s*\(|^\s*(?:it|test)\s*\(\s*['\"`]|^\s*@Test\b|^\s*func\s+(Test\w+)\s*\(|^\s*#\[test\]")
ENV_RE = re.compile(r"os\.environ(?:\.get)?\s*[\[(]\s*['\"]([A-Z][A-Z0-9_]{1,60})['\"]|os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]{1,60})['\"]|process\.env\.([A-Z][A-Z0-9_]{1,60})|process\.env\[['\"]([A-Z][A-Z0-9_]{1,60})['\"]\]|System\.getenv\(\s*\"([A-Z][A-Z0-9_]{1,60})\"|Getenv\(\s*\"([A-Z][A-Z0-9_]{1,60})\"|env::var\(\s*\"([A-Z][A-Z0-9_]{1,60})\"|\$\{([A-Z][A-Z0-9_]{1,60})(?::-[^}]*)?\}|ENV\[['\"]([A-Z][A-Z0-9_]{1,60})['\"]\]")
DOTENV_RE = re.compile(r"(?m)^\s*(?:export\s+)?([A-Z][A-Z0-9_]{1,60})\s*=")
CONST_RE = re.compile(r"(?m)^\s*(?:(?:public|private|protected|static|final|export|const|let|var|pub)\s+)*(?:[\w<>\[\]]+\s+)?([A-Z][A-Z0-9_]{2,60})\s*(?::\s*[\w\[\], ]+)?=\s*([^=\n].{0,80})")
SQL_TABLE_RE = re.compile(r"(?i)\bcreate\s+(?:temp(?:orary)?\s+)?table\s+(?:if\s+not\s+exists\s+)?[`\"\[]?([\w.]+)")
DEF_COUNT_RE = re.compile(r"(?m)^\s*(?:export\s+)?(?:async\s+)?(?:def|function|func|fn)\s+\w|^\s*(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+\w+\s*\([^;]*\)\s*\{")
CLASS_RE = re.compile(r"(?m)^\s*(?:export\s+)?(?:public\s+|abstract\s+|final\s+)*(?:class|interface|struct|enum|trait)\s+\w")


def is_text_name(name):
    base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    ext = ("." + base.rsplit(".", 1)[-1]) if "." in base else ""
    return ext in TEXT_EXT or base in TEXT_NAMES or base.split(".")[0] in TEXT_NAMES


def lang_of(name):
    base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    ext = ("." + base.rsplit(".", 1)[-1]) if "." in base else ""
    if base == "dockerfile":
        return "Dockerfile"
    if base == "makefile":
        return "Makefile"
    return CODE_LANG.get(ext, ext or "(no extension)")


class Tree:
    """Accumulates a file tree: add(name, size, text_or_None)."""
    def __init__(self):
        self.files = []          # (name, size, lines or None)
        self.lang = {}           # lang -> [files, bytes, lines]
        self.tests, self.test_files = 0, set()
        self.env, self.consts, self.sql_tables = Counter(), {}, Counter()
        self.defs = self.classes = 0
        self.longest_line = (0, "")

    def add(self, name, size, text=None):
        lines = None
        if text is not None:
            lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        self.files.append((name, size, lines))
        lg = lang_of(name)
        a = self.lang.setdefault(lg, [0, 0, 0])
        a[0] += 1
        a[1] += size
        a[2] += lines or 0
        if text is None:
            return
        low = name.lower()
        nt = len(TEST_FN_RE.findall(text))
        if nt:
            self.tests += nt
            self.test_files.add(name)
        for m in ENV_RE.finditer(text):
            v = next(g for g in m.groups() if g)
            self.env[v] += 1
        if low.rsplit("/", 1)[-1].startswith(".env") or low.endswith((".env", ".env.example")):
            for v in DOTENV_RE.findall(text):
                self.env[v] += 1
        if lg in ("Python", "JavaScript", "TypeScript", "Java", "Kotlin", "Go", "Rust", "C#", "C", "C++", "Ruby", "PHP", "Swift", "Scala", "Dart"):
            for m in CONST_RE.finditer(text):
                if len(self.consts) < 400 and m.group(1) not in self.consts:
                    self.consts[m.group(1)] = (name, short(m.group(2).rstrip(";,"), 50))
            self.defs += len(DEF_COUNT_RE.findall(text))
            self.classes += len(CLASS_RE.findall(text))
        for t in SQL_TABLE_RE.findall(text):
            self.sql_tables[t] += 1

    def emit(self, look, what="Files", pri=88, extra_pairs=()):
        files = self.files
        if not files:
            return
        total = sum(s for _, s, _ in files)
        with_lines = [f for f in files if f[2] is not None]
        total_lines = sum(f[2] for f in with_lines)
        code = [f for f in with_lines if lang_of(f[0]) not in ("Markdown", "Text", "JSON", "YAML", "TOML", "XML", "CSV", "TSV", "INI", "reST", "Properties")]
        counts(look, [("files", len(files)), ("bytes", total), ("text files", len(with_lines)), ("text lines", total_lines),
                      ("source files", len(code)), ("source lines", sum(f[2] for f in code)), ("functions/methods (regex)", self.defs or None),
                      ("classes/types", self.classes or None), ("test functions", self.tests or None), ("test files", len(self.test_files) or None),
                      ("SQL tables created", len(self.sql_tables) or None), ("environment variables", len(self.env) or None), *extra_pairs], pri + 6, f"{what} counts")
        langs = sorted(self.lang.items(), key=lambda kv: (-kv[1][0], kv[0]))
        look.line("Per language or extension (files, bytes, lines): " + "; ".join(f"{k} {v[0]} files, {fmt(v[1])} B" + (f", {fmt(v[2])} lines" if v[2] else "") for k, v in langs[:14])
                  + (f"; +{len(langs) - 14} more kinds" if len(langs) > 14 else ""), pri)
        if len(langs) > 14:
            look.line("Per language, continued: " + "; ".join(f"{k} {v[0]} files, {fmt(v[1])} B" + (f", {fmt(v[2])} lines" if v[2] else "") for k, v in langs[14:]), 34)
        big = sorted(files, key=lambda f: -f[1])[:8]
        look.line("Biggest files (bytes): " + "; ".join(f"{n} {fmt(s)}" for n, s, _ in big), pri - 6)
        if with_lines:
            lng = sorted(with_lines, key=lambda f: -f[2])[:8]
            look.line("Longest files (lines): " + "; ".join(f"{n} {fmt(l)}" for n, _, l in lng), pri - 7)
        if self.env:
            look.line(f"Environment variables read or set ({len(self.env)}): " + ", ".join(sorted(self.env)), pri - 10)
        if self.sql_tables:
            look.line(f"SQL tables created ({len(self.sql_tables)}): " + ", ".join(sorted(self.sql_tables)), pri - 10)
        if self.tests:
            look.line(f"Tests: {fmt(self.tests)} test functions in {len(self.test_files)} files: " + ", ".join(sorted(self.test_files)[:12]) + (" ..." if len(self.test_files) > 12 else ""), pri - 12)
        if self.consts:
            items = list(self.consts.items())
            look.line(f"Constants (UPPER_CASE assignments, {len(items)}): " + "; ".join(f"{k} = {v[1]} ({v[0].rsplit('/', 1)[-1]})" for k, v in items[:20]), 40, "constants")
            if len(items) > 20:
                look.line("Constants, continued: " + "; ".join(f"{k} = {v[1]} ({v[0].rsplit('/', 1)[-1]})" for k, v in items[20:200]), 26, "constants")
        dirs = Counter()
        for n, s, _ in files:
            parts = n.replace("\\", "/").strip("/").split("/")
            for d in range(1, len(parts)):
                dirs["/".join(parts[:d]) + "/"] += 1
        if dirs:
            look.line(f"Folders ({len(dirs)}), files below each: " + "; ".join(f"{d} {c}" for d, c in sorted(dirs.items())[:80]) + (f"; +{len(dirs) - 80} more" if len(dirs) > 80 else ""), 30, "tree")
        rows = [f"{n}\t{s}\t{'' if l is None else l}" for n, s, l in sorted(files)]
        for k in range(0, min(len(rows), 3000), 150):
            look.line(f"File list (name, bytes, lines) {k + 1}-{min(len(rows), k + 150)} of {len(rows)}:\n" + "\n".join(rows[k:k + 150]), 22 - min(10, k // 150), "tree")


# ---------------------------------------------------------------- parsed documents (JSON, YAML, TOML, XML as records)
def walk_stats(v):
    """-> dict of exact structure counts of a parsed document and [(path, list_of_dicts)] record arrays."""
    st = Counter()
    arrays = []
    leaves = []
    stack = [(v, "", 0)]
    maxd = 0
    while stack:
        x, path, d = stack.pop()
        maxd = max(maxd, d)
        if isinstance(x, dict):
            st["objects"] += 1
            st["keys"] += len(x)
            if len(x) >= 3 and sum(isinstance(y, dict) for y in x.values()) >= 0.8 * len(x):   # a map of records: name -> fields
                arrays.append((path or "(top level)", [dict({"@key": k}, **y) if isinstance(y, dict) else {"@key": k, "value": y} for k, y in x.items()], "map"))
            for k, y in reversed(list(x.items())):
                stack.append((y, f"{path}.{k}" if path else str(k), d + 1))
        elif isinstance(x, list):
            st["arrays"] += 1
            st["array items"] += len(x)
            if x and sum(isinstance(y, dict) for y in x) >= 0.8 * len(x):   # one-element arrays too: they join their siblings' set
                arrays.append((path or "(top level)", x))
            for i in range(len(x) - 1, -1, -1):
                stack.append((x[i], f"{path}[{i}]", d + 1))
        else:
            st["null" if x is None else "booleans" if isinstance(x, bool) else "numbers" if isinstance(x, (int, float)) else "strings" if isinstance(x, str) else "other values"] += 1
            if len(leaves) < 20000:
                leaves.append((path or "(value)", x))
    st["max depth"] = maxd
    return st, arrays, leaves


def record_sets(arrays):
    """Every array of records at the same path shape merged into one set, whatever branch it sits in: `orders[3].items` and
    `orders[7].items` are both `orders[].items[]`. -> [(shape, [(concrete path of the record, record)], parents)] largest first."""
    groups = {}
    for path, arr, *kind in arrays:
        is_map = bool(kind)
        shape = re.sub(r"\[\d+\]", "[]", path) + (".*" if is_map else "" if path == "(top level)" else "[]")
        g = groups.setdefault(shape, ([], []))
        g[1].append(len(arr))
        top = path == "(top level)"
        for i, rec in enumerate(arr):
            if is_map:
                g[0].append(((rec["@key"] if top else f"{path}.{rec['@key']}"), rec))
            else:
                g[0].append(((f"[{i}]" if top else f"{path}[{i}]"), rec))
    out = [(shape, recs, sizes) for shape, (recs, sizes) in groups.items() if len(recs) >= 2]
    out.sort(key=lambda t: (-len(t[1]), t[0].count("[]"), t[0]))
    return out


def record_row(path, rec):
    """One record as `path: key=value; ...` with its scalar fields only (nested record lists are listed in their own set)."""
    if not isinstance(rec, dict):
        return f"{path}: {short(rec, 80)}"
    bits = []
    for k, x in flatten(rec).items():
        if isinstance(x, Multi) or "[]" in k and not k.endswith(LEN):
            continue
        bits.append(f"{k}={short(x, 60)}")
    return f"{path}: " + "; ".join(bits)


def doc_profile(look, v, what, pri=92):
    """Exact structure counts, every set of records (all branches, every depth) profiled field by field with the path of each
    extreme, and every scalar leaf `path = value` (for --more)."""
    st, arrays, leaves = walk_stats(v)
    top = type(v).__name__
    pairs = [("top level", f"{'object' if top == 'dict' else 'array' if top == 'list' else top}" + (f" of {len(v)} {'keys' if isinstance(v, dict) else 'items'}" if isinstance(v, (dict, list)) else "")),
             ("objects", st["objects"]), ("arrays", st["arrays"]), ("array items", st["array items"]), ("keys", st["keys"]),
             ("strings", st["strings"]), ("numbers", st["numbers"]), ("booleans", st["booleans"]), ("nulls", st["null"]), ("max depth", st["max depth"])]
    counts(look, pairs, pri + 2, f"{what} counts")
    if isinstance(v, dict):
        scal = [(k, x) for k, x in v.items() if not isinstance(x, (dict, list))]
        nest = [(k, x) for k, x in v.items() if isinstance(x, (dict, list))]
        bits = [f"{k} = {short(x, 50)}" for k, x in scal[:30]] + [f"{k}: {'object of ' + str(len(x)) + ' keys' if isinstance(x, dict) else 'array of ' + str(len(x))}" for k, x in nest[:30]]
        look.line(f"Top-level keys ({len(v)}): " + "; ".join(bits) + (" ..." if len(v) > 60 else ""), pri - 2)
        for k, x in nest[:20]:
            if isinstance(x, dict) and x:
                look.line(f"Keys of {k} ({len(x)}): " + "; ".join(f"{kk} = {short(xx, 40)}" if not isinstance(xx, (dict, list)) else f"{kk}: {'object' if isinstance(xx, dict) else 'array'} of {len(xx)}" for kk, xx in list(x.items())[:40]), pri - 20)
    sets = record_sets(arrays)
    if sets:
        look.fact("record_sets", {shape: len(recs) for shape, recs, _ in sets[:40]})
        look.line("Record sets (every array of objects at every depth, all branches merged; `[]` = every element): "
                  + "; ".join(f"{shape} {len(recs):,} records" + (f" in {len(sizes):,} arrays ({min(sizes)}..{max(sizes)} each)" if len(sizes) > 1 else "") for shape, recs, sizes in sets[:30]), pri + 1, "counts")
    covered = []
    shapes = {s for s, _, _ in sets}
    for k, (shape, recs, sizes) in enumerate(sets[:30]):
        base = "" if shape == "(top level)" else shape[:-2] if shape.endswith("[]") else shape[:-2] if shape.endswith(".*") else shape
        own = []   # a nested list of records that is a set of its own is profiled there; here it is only counted
        for path, rec in recs:
            if isinstance(rec, dict) and any(isinstance(x, list) and (f"{base}[].{kk}[]" if base else f"[].{kk}[]") in shapes for kk, x in rec.items()):
                rec = {(kk + "[]" + LEN if isinstance(x, list) and (f"{base}[].{kk}[]" if base else f"[].{kk}[]") in shapes else kk): (len(x) if isinstance(x, list) and (f"{base}[].{kk}[]" if base else f"[].{kk}[]") in shapes else x)
                       for kk, x in rec.items()}
            own.append((path, rec))
        p, extra = profile(own, False, "record")
        emit(look, p, extra, f"Records of {shape} ({len(recs):,}; positions are record paths)", (pri - 6 - 2 * k) if k < 4 else pri - 34, 28, 24)
        if len(recs) <= 3000:
            covered.append(shape)
            rows = [record_row(path, rec) for path, rec in recs]
            for j in range(0, len(rows), 20):
                look.line(f"Records of {shape} {j + 1}-{min(len(rows), j + 20)} of {len(rows)}:\n" + "\n".join(rows[j:j + 20]), 18, "records")

    def inside(path):
        n = re.sub(r"\[\d+\]", "[]", path)
        return any(n.startswith(c + ".") or n == c or (c == "(top level)" and n.startswith("[]")) or (c.endswith(".*") and n.startswith(c[:-1])) for c in covered)
    rest = [(p, x) for p, x in leaves if not inside(p)]
    rows = [f"{p} = {short(x, 80)}" for p, x in rest]
    for k in range(0, min(len(rows), 20000), 40):
        look.line(f"Values {k + 1}-{min(len(rows), k + 40)} of {len(rows)} (path = value, outside the record lists):\n" + "\n".join(rows[k:k + 40]), 17, "values")
    return st


# ---------------------------------------------------------------- manifests and package metadata (archives, jars, wheels, repos)
LICENSES = [("MIT", r"Permission is hereby granted, free of charge"), ("Apache-2.0", r"Apache License,?\s+Version 2\.0"), ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
            ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"), ("LGPL", r"GNU LESSER GENERAL PUBLIC LICENSE"), ("BSD-3-Clause", r"Neither the name of"),
            ("BSD-2-Clause", r"Redistributions in binary form must reproduce"), ("MPL-2.0", r"Mozilla Public License,?\s+v(ersion)?\.? ?2\.0"),
            ("ISC", r"Permission to use, copy, modify, and/or distribute"), ("Unlicense", r"This is free and unencumbered software"),
            ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE")]
MANIFEST_NAMES = {"manifest.mf", "package.json", "pyproject.toml", "setup.cfg", "setup.py", "requirements.txt", "cargo.toml", "go.mod", "pom.xml", "pom.properties",
                  "metadata", "pkg-info", "composer.json", "gemfile", "build.gradle", "build.gradle.kts", "manifest.json", "plugin.xml", "plugin.yml",
                  "pubspec.yaml", "environment.yml", "dockerfile", "docker-compose.yml", "docker-compose.yaml", "chart.yaml", "mix.exs", "deno.json", "app.json",
                  "wheel", "entry_points.txt", "top_level.txt", "record"}
QUOTED_RE = re.compile(r"['\"]([^'\"]+)['\"]")


def is_manifest(name):
    base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return (base in MANIFEST_NAMES or base.endswith((".nuspec", ".gemspec", ".csproj", ".podspec"))
            or base.startswith(("readme", "license", "licence", "copying", "changelog", "changes", "history", "notice")))


def _headers(text, stop_at_blank):
    hdr = []
    for ln in text.splitlines():
        if not ln.strip():
            if stop_at_blank and hdr:
                break
            continue
        if ln.startswith(" ") and hdr:
            hdr[-1] = (hdr[-1][0], hdr[-1][1] + ln[1:])
            continue
        if ln.lstrip().startswith("#"):
            continue
        m = re.match(r"([^:=]+)[:=](.*)", ln)
        if m:
            hdr.append((m.group(1).strip(), m.group(2).strip()))
    return hdr


def manifest_lines(name, text):
    """-> [str] facts from one manifest, README, licence or changelog."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    out = []
    try:
        if base in ("manifest.mf", "metadata", "pkg-info", "wheel", "pom.properties"):
            hdr = _headers(text, base in ("metadata", "pkg-info"))
            reqs = [v for k, v in hdr if k.lower() == "requires-dist"]
            main = [(k, v) for k, v in hdr if k.lower() not in ("requires-dist", "classifier")]
            out.append(f"{name}: " + "; ".join(f"{k}: {short(v, 90)}" for k, v in main[:40]) + (f" (+{len(main) - 40} more headers)" if len(main) > 40 else ""))
            if reqs:
                out.append(f"{name} Requires-Dist ({len(reqs)}): " + "; ".join(short(r, 60) for r in reqs[:60]))
        elif base in ("package.json", "composer.json", "manifest.json", "deno.json", "app.json"):
            import json
            j = json.loads(text)
            keys = ("name", "version", "description", "license", "author", "main", "module", "type", "private", "homepage", "manifest_version", "engines")
            out.append(f"{name}: " + "; ".join(f"{k}: {short(j[k], 80)}" for k in keys if k in j))
            for dk in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies", "require", "require-dev", "permissions"):
                if isinstance(j.get(dk), dict) and j[dk]:
                    out.append(f"{name} {dk} ({len(j[dk])}): " + ", ".join(f"{k} {v}" for k, v in j[dk].items()))
                elif isinstance(j.get(dk), list) and j[dk]:
                    out.append(f"{name} {dk} ({len(j[dk])}): " + ", ".join(map(str, j[dk])))
            if isinstance(j.get("scripts"), dict) and j["scripts"]:
                out.append(f"{name} scripts ({len(j['scripts'])}): " + "; ".join(f"{k}: {short(v, 50)}" for k, v in j["scripts"].items()))
        elif base in ("pyproject.toml", "cargo.toml"):
            import tomllib
            j = tomllib.loads(text)
            proj = j.get("project") or j.get("package") or j.get("tool", {}).get("poetry") or {}
            out.append(f"{name}: " + "; ".join(f"{k}: {short(proj[k], 80)}" for k in ("name", "version", "description", "requires-python", "edition", "license", "authors") if k in proj))
            deps = proj.get("dependencies") or j.get("dependencies") or {}
            if deps:
                body = ", ".join(f"{k} {short(v, 30)}" for k, v in deps.items()) if isinstance(deps, dict) else ", ".join(map(str, deps))
                out.append(f"{name} dependencies ({len(deps)}): " + body)
            for grp, d in (proj.get("optional-dependencies") or {}).items():
                out.append(f"{name} optional [{grp}] ({len(d)}): " + ", ".join(map(str, d)))
            dev = j.get("dev-dependencies") or {}
            if dev:
                out.append(f"{name} dev-dependencies ({len(dev)}): " + ", ".join(dev))
            scripts = proj.get("scripts") or {}
            if scripts:
                out.append(f"{name} scripts ({len(scripts)}): " + "; ".join(f"{k} = {v}" for k, v in scripts.items()))
        elif base == "requirements.txt":
            reqs = [x.strip() for x in text.splitlines() if x.strip() and not x.strip().startswith(("#", "-"))]
            out.append(f"{name} ({len(reqs)} requirements): " + ", ".join(reqs[:120]))
        elif base == "go.mod":
            mod = re.search(r"(?m)^module\s+(\S+)", text)
            gov = re.search(r"(?m)^go\s+(\S+)", text)
            reqs = re.findall(r"(?m)^\s*([\w./-]+\.[\w./-]+)\s+(v[\w.+-]+)", text)
            out.append(f"{name}: module {mod.group(1) if mod else '?'}; go {gov.group(1) if gov else '?'}; {len(reqs)} requirements: " + ", ".join(f"{a} {b}" for a, b in reqs[:80]))
        elif base == "pom.xml" or base.endswith((".nuspec", ".csproj")):
            def g(tag):
                m = re.search(rf"<{tag}>\s*([^<]+?)\s*</{tag}>", text)
                return m.group(1) if m else None
            deps = re.findall(r"<dependency>.*?<artifactId>\s*([^<]+?)\s*</artifactId>(?:.*?<version>\s*([^<]+?)\s*</version>)?.*?</dependency>", text, re.S)
            pk = re.findall(r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"', text)
            out.append(f"{name}: " + "; ".join(f"{t}: {g(t)}" for t in ("groupId", "artifactId", "version", "packaging", "name", "id", "authors", "TargetFramework") if g(t)))
            if deps or pk:
                out.append(f"{name} dependencies ({len(deps) + len(pk)}): " + ", ".join(f"{a} {b}".strip() for a, b in (deps + pk)[:80]))
        elif base == "setup.cfg":
            out.append(f"{name}: " + "; ".join(f"{k.strip()}: {short(v, 60)}" for k, v in re.findall(r"(?m)^(name|version|description|license|python_requires|author)\s*=\s*(.+)$", text)))
        elif base == "setup.py":
            kv = re.findall(r"\b(name|version|description|license|python_requires|author)\s*=\s*['\"]([^'\"]+)['\"]", text)
            reqs = re.search(r"install_requires\s*=\s*\[([^\]]*)\]", text, re.S)
            out.append(f"{name}: " + "; ".join(f"{k}: {v}" for k, v in kv) + (f"; install_requires: {', '.join(QUOTED_RE.findall(reqs.group(1)))}" if reqs else ""))
        elif base.startswith(("license", "licence", "copying")):
            kind = next((k for k, rx in LICENSES if re.search(rx, text, re.I)), "unrecognised text")
            cp = re.search(r"(?im)^\s*copyright\s+(?:\(c\)|©)?\s*(.+)$", text)
            out.append(f"{name}: licence {kind}, {len(text.splitlines())} lines" + (f"; {short(cp.group(0).strip(), 90)}" if cp else ""))
        elif base.startswith(("changelog", "changes", "history")):
            vers = re.findall(r"(?m)^#+\s*\[?v?(\d+\.\d+(?:\.\d+)?[\w.-]*)\]?(?:\s*[-–(]\s*(\d{4}-\d{2}-\d{2}))?", text)
            if not vers:
                vers = re.findall(r"(?m)^\s*v?(\d+\.\d+(?:\.\d+)?)\s*[-–(]?\s*(\d{4}-\d{2}-\d{2})?", text)
            dates = sorted(set(DATE_RE.findall(text)))
            line = f"{name}: {len(vers)} version entries"
            if vers:
                line += f"; first listed: {vers[0][0]}" + (f" ({vers[0][1]})" if vers[0][1] else "") + "; entries: " + ", ".join(f"{v} {d}".strip() for v, d in vers[:40])
            if dates:
                line += f"; dates {dates[0]} .. {dates[-1]} ({len(dates)} distinct)"
            out.append(line)
        elif base.startswith(("readme", "notice")):
            heads = [m.group(2).strip() for m in (HEAD_RE.match(x) for x in text.splitlines()) if m]
            first = next((x.strip() for x in text.splitlines() if x.strip() and not x.startswith(("#", "!", "[", "<", "="))), "")
            out.append(f"{name}: {len(text.splitlines())} lines, {len(heads)} headings" + (f" ({'; '.join(short(h, 40) for h in heads[:15])})" if heads else "")
                       + (f"; first text: {short(first, 160)}" if first else ""))
        elif base == "dockerfile":
            frm = re.findall(r"(?im)^FROM\s+(\S+)", text)
            exp = re.findall(r"(?im)^EXPOSE\s+(.+)$", text)
            env = re.findall(r"(?im)^ENV\s+(\w+)", text)
            runs = len(re.findall(r"(?im)^RUN ", text))
            out.append(f"{name}: FROM {', '.join(frm)}; EXPOSE {', '.join(exp) or '-'}; ENV {', '.join(env) or '-'}; {runs} RUN steps")
        else:
            ls = [x for x in text.splitlines() if x.strip() and not x.strip().startswith("#")]
            out.append(f"{name} ({len(ls)} lines): " + "; ".join(short(x, 70) for x in ls[:25]))
    except Exception as e:  # a broken manifest is a fact too
        out.append(f"{name}: could not be parsed ({type(e).__name__}: {short(e, 80)})")
    return [x for x in out if not x.rstrip().endswith(":")]
