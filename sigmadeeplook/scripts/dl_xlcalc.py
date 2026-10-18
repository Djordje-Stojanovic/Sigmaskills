"""SigmaDeepLook: a small spreadsheet evaluator for formulas that carry no stored result, and the targets of named ranges.

A workbook written by a library (openpyxl, a report generator) has formulas but no cached values; Excel fills them on open. Without
LibreOffice there is no other way to learn what they say, so the common grammar is evaluated here: arithmetic, comparison, cell and range
references (also across sheets and through named ranges), and SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, ROUND, ABS, IF, AND, OR, NOT, SQRT,
POWER, MOD, INT, LEN, SUMPRODUCT, SUMIF, COUNTIF, VLOOKUP (exact match), IFERROR. Anything else gives no result (never a guessed one).
"""
import math
import re

TOKEN = re.compile(r"""
    (?P<str>"(?:[^"]|"")*")
  | (?P<ref>(?:(?:'[^']+'|[A-Za-z_][A-Za-z0-9_.]*)!)?\$?[A-Z]{1,3}\$?\d{1,7}(?::\$?[A-Z]{1,3}\$?\d{1,7})?)(?![A-Za-z0-9_(])
  | (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
  | (?P<func>[A-Za-z_][A-Za-z0-9_.]*)\(
  | (?P<name>[A-Za-z_][A-Za-z0-9_.]*)
  | (?P<op><>|<=|>=|[-+*/^&=<>(),%])
  | (?P<ws>\s+)
""", re.X)


def col_num(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


class Unsupported(Exception):
    pass


def split_ref(ref, cur):
    sheet = cur
    if "!" in ref:
        sh, ref = ref.rsplit("!", 1)
        sheet = sh.strip("'")
    a, _, b = ref.replace("$", "").partition(":")
    return sheet, a, b or None


def addr(a):
    m = re.match(r"([A-Z]+)(\d+)$", a)
    return int(m.group(2)) - 1, col_num(m.group(1)) - 1


class Book:
    def __init__(self, cells, formulas, names):
        self.cells = cells            # sheet -> {(r, c): raw value string}
        self.formulas = formulas      # sheet -> {(r, c): formula text}
        self.names = names            # name -> target text
        self.memo = {}
        self.busy = set()

    def value(self, sheet, r, c):
        key = (sheet, r, c)
        if key in self.memo:
            return self.memo[key]
        raw = self.cells.get(sheet, {}).get((r, c), "")
        f = self.formulas.get(sheet, {}).get((r, c))
        if raw not in ("", None) and f is None:
            v = num_or_text(raw)
        elif f is not None and f != "(shared)":
            if key in self.busy:
                raise Unsupported("circular")
            self.busy.add(key)
            try:
                v = num_or_text(raw) if raw not in ("", None) else self.evaluate(f, sheet)
            finally:
                self.busy.discard(key)
        else:
            v = num_or_text(raw) if raw not in ("", None) else None
        self.memo[key] = v
        return v

    def rng(self, sheet, a, b):
        r1, c1 = addr(a)
        r2, c2 = addr(b)
        return [[self.value(sheet, r, c) for c in range(min(c1, c2), max(c1, c2) + 1)] for r in range(min(r1, r2), max(r1, r2) + 1)]

    def evaluate(self, f, sheet, depth=0):
        if depth > 8:
            raise Unsupported("deep")
        py = self.translate(f, sheet, depth)
        env = {"__builtins__": {}, "B": self, "S": sheet, "FN": FUNCS, "C": self.cell, "RG": self.rng_flat, "TX": text_join}
        try:
            return eval(py, env)   # only names produced by translate() exist here: no builtins, no attribute access from the formula text
        except (ZeroDivisionError, TypeError, ValueError, KeyError, IndexError, Unsupported, OverflowError):
            raise Unsupported("eval")

    def cell(self, sheet, a):
        r, c = addr(a)
        return self.value(sheet, r, c)

    def rng_flat(self, sheet, a, b):
        return self.rng(sheet, a, b)

    def translate(self, f, sheet, depth):
        out, pos, f = [], 0, f.strip()
        if f.startswith("="):
            f = f[1:]
        while pos < len(f):
            m = TOKEN.match(f, pos)
            if not m:
                raise Unsupported("token")
            pos = m.end()
            k = m.lastgroup
            t = m.group(k)
            if k == "ws":
                continue
            if k == "str":
                out.append(repr(t[1:-1].replace('""', '"')))
            elif k == "num":
                out.append(t)
            elif k == "ref":
                sh, a, b = split_ref(t, sheet)
                out.append(f"RG({sh!r},{a!r},{b!r})" if b else f"C({sh!r},{a!r})")
            elif k == "func":
                name = t.upper()
                if name not in FUNCS:
                    raise Unsupported(name)
                out.append(f"FN[{name!r}](")
            elif k == "name":
                u = t.upper()
                if u in ("TRUE", "FALSE"):
                    out.append("True" if u == "TRUE" else "False")
                elif t in self.names:
                    target = self.names[t]
                    out.append("(" + self.translate(target, sheet, depth + 1) + ")")
                else:
                    raise Unsupported("name " + t)
            else:
                out.append({"^": "**", "=": "==", "<>": "!=", "&": "+", "%": "/100"}.get(t, t))
        return "".join(out)


def num_or_text(raw):
    try:
        return float(raw) if not isinstance(raw, (int, float)) else raw
    except (TypeError, ValueError):
        return str(raw)


def flat(args):
    for a in args:
        if isinstance(a, list):
            for x in flat(a):
                yield x
        else:
            yield a


def nums(args):
    return [x for x in flat(args) if isinstance(x, (int, float)) and not isinstance(x, bool)]


def text_join(*a):
    return "".join(str(x) for x in a)


def f_if(c, a=True, b=False):
    return a if c else b


def vlookup(key, table, idx, exact=True):
    for row in table:
        if row and row[0] == key or (row and isinstance(row[0], float) and isinstance(key, float) and row[0] == key):
            return row[int(idx) - 1]
    raise Unsupported("vlookup miss")


def crit(c):
    if isinstance(c, str):
        m = re.match(r"(<=|>=|<>|<|>|=)?(.*)$", c)
        op, val = m.group(1) or "=", m.group(2)
        try:
            val = float(val)
        except ValueError:
            pass
        return op, val
    return "=", c


def match(x, op, val):
    try:
        return {"=": x == val, "<>": x != val, "<": x < val, ">": x > val, "<=": x <= val, ">=": x >= val}[op]
    except TypeError:
        return False


FUNCS = {
    "SUM": lambda *a: sum(nums(a)), "AVERAGE": lambda *a: sum(nums(a)) / len(nums(a)), "MIN": lambda *a: min(nums(a)), "MAX": lambda *a: max(nums(a)),
    "COUNT": lambda *a: len(nums(a)), "COUNTA": lambda *a: sum(1 for x in flat(a) if x not in (None, "")), "ROUND": lambda x, n=0: round(x + 1e-12 * (1 if x >= 0 else -1), int(n)),
    "ABS": abs, "IF": f_if, "AND": lambda *a: all(flat(a)), "OR": lambda *a: any(flat(a)), "NOT": lambda x: not x, "SQRT": math.sqrt, "POWER": lambda a, b: a ** b,
    "MOD": lambda a, b: a % b, "INT": lambda x: math.floor(x), "LEN": lambda x: len(str(x)), "VLOOKUP": vlookup,
    "SUMPRODUCT": lambda *a: sum(math.prod(t) for t in zip(*[list(flat([x])) for x in a])),
    "SUMIF": lambda rg, c, sr=None: sum(s for x, s in zip(flat([rg]), flat([sr if sr is not None else rg])) if isinstance(s, (int, float)) and match(x, *crit(c))),
    "COUNTIF": lambda rg, c: sum(1 for x in flat([rg]) if match(x, *crit(c))),
}


def iferror_wrap(f):
    """IFERROR(a, b) needs lazy evaluation: handled by evaluating the first argument inside try in translate-free form."""
    return f


def fmt(v):
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return f"{v:,.6g}" if abs(v) < 1e15 else f"{v:.6g}"
    return str(v)


def report(look, store, defined, uncached_by_sheet):
    """store: sheet -> (cells {(r, c): raw}, formulas [(ref, text)]); defined: name -> target; -> lines for the look."""
    cells = {s: c for s, (c, _f) in store.items()}
    forms = {}
    for s, (_c, fl) in store.items():
        d = {}
        for ref, text in fl:
            m = re.match(r"([A-Z]+)(\d+)", ref)
            d[(int(m.group(2)) - 1, col_num(m.group(1)) - 1)] = text
        forms[s] = d
    book = Book(cells, forms, {k: v for k, v in defined.items() if "#REF!" not in v})
    if defined:
        items = []
        for n, tgt in list(defined.items())[:40]:
            val = ""
            if "#REF!" in tgt:
                items.append(f"{n} -> {tgt} (broken)")
                continue
            try:
                m = re.match(r"^(?:'[^']+'|[A-Za-z_][\w.]*)!\$?[A-Z]{1,3}\$?\d+$", tgt)
                if m:
                    sh, a, _b = split_ref(tgt, "")
                    val = " = " + fmt(book.value(sh, *addr(a)))
            except Unsupported:
                pass
            items.append(f"{n} -> {tgt}{val}")
        look.line("Named ranges (name -> target, value of a single cell): " + "; ".join(items) + ".", 62)
    lines, done = [], 0
    for sheet, refs in uncached_by_sheet.items():
        # one-off formulas first (a total, a rate), then a few of the repeated pattern
        pats = {}
        for ref in refs:
            m = re.match(r"([A-Z]+)(\d+)", ref)
            key = (int(m.group(2)) - 1, col_num(m.group(1)) - 1)
            pats.setdefault(re.sub(r"\d+", "#", forms[sheet].get(key, "")), []).append(ref)
        order = sorted(pats.values(), key=len)
        for group in order:
            for ref in group[:3 if len(group) > 3 else 3]:
                m = re.match(r"([A-Z]+)(\d+)", ref)
                key = (int(m.group(2)) - 1, col_num(m.group(1)) - 1)
                f = forms[sheet].get(key)
                if f in (None, "(shared)"):
                    continue
                try:
                    v = book.evaluate(f, sheet)
                except Unsupported:
                    continue
                if v is None:
                    continue
                lines.append(f"{sheet}!{ref} = {fmt(v)} (={f[:60]})")
                done += 1
                if done >= 30:
                    break
            if done >= 30:
                break
    if lines:
        look.line("Computed here from the formulas (the file stores no result for them; every figure is evaluated from the cells, not guessed): " + "; ".join(lines) + ".", 66)
        look.fact("computed_formulas", len(lines))
