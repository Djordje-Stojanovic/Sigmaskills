"""SigmaDeepLook: list-column stats. A column whose cells are lists or arrays (Parquet list types, JSON arrays in a table cell)
gets: how many cells are lists, length min / mean / max, empty lists, null cells and the element type. Any table reader can feed it."""
import json
from collections import Counter

NULL_WORDS = {"", "null", "none", "nan", "n/a", "na", "nil"}
SAMPLE_ELEMS = 20   # element types come from the first elements of each list; lengths are exact


def as_list(v):
    """-> a list for a list, tuple, array or JSON array text; None for anything else."""
    if isinstance(v, (list, tuple)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if len(s) >= 2 and s[0] == "[" and s[-1] == "]" and len(s) < 2_000_000:
            try:
                x = json.loads(s)
            except ValueError:
                return None
            return x if isinstance(x, list) else None
        return None
    if hasattr(v, "tolist") and not isinstance(v, (bytes, bytearray)):
        try:
            x = v.tolist()
        except Exception:
            return None
        return x if isinstance(x, list) else None
    return None


def elem_type(x):
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "string"
    if isinstance(x, (list, tuple)):
        return "list"
    if isinstance(x, dict):
        return "object"
    return type(x).__name__


def is_null(v):
    return v is None or (isinstance(v, str) and v.strip().lower() in NULL_WORDS) or (isinstance(v, float) and v != v)


class ListCols:
    def __init__(self, names):
        self.names = list(names)
        self.rows = 0
        self.st = {}   # column index -> [lists, len_sum, len_min, len_max, empty, types Counter]
        self.nulls = Counter()
        self.other = Counter()   # non-list, non-null cells per column

    def add_row(self, vals):
        self.rows += 1
        for i, v in enumerate(vals):
            if is_null(v):
                self.nulls[i] += 1
                continue
            lst = as_list(v)
            if lst is None:
                self.other[i] += 1
                continue
            s = self.st.get(i)
            if s is None:
                s = self.st[i] = [0, 0, None, 0, 0, Counter()]
            n = len(lst)
            s[0] += 1
            s[1] += n
            s[2] = n if s[2] is None else min(s[2], n)
            s[3] = max(s[3], n)
            s[4] += n == 0
            for x in lst[:SAMPLE_ELEMS]:
                s[5][elem_type(x)] += 1

    def lines(self):
        out = []
        for i, s in sorted(self.st.items()):
            if s[0] < 1 or s[0] < self.other[i]:   # mostly not lists: an ordinary column
                continue
            et = [t for t, _ in s[5].most_common() if t != "null"] or ["unknown"]
            name = self.names[i] if i < len(self.names) else f"column {i + 1}"
            out.append(f"{name}: list column, {s[0]:,} lists, length min {s[2]} / mean {s[1] / s[0]:.2f} / max {s[3]}, {self.nulls[i]:,} null cells, {s[4]:,} empty lists, element type {'/'.join(et[:3])}")
        return out

    def emit(self, look, pri=83):
        ls = self.lines()
        if ls:
            look.fact("list_columns", [l.split(":")[0] for l in ls])
            look.line("List columns (cells that hold lists or arrays; lengths are exact over every row read):\n" + "\n".join(ls[:30]), pri, "profile")
        return ls
