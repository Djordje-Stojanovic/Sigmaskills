"""SigmaDeepLook: a small spreadsheet evaluator for formulas that carry no stored result, and the targets of named ranges.

A workbook written by a library (openpyxl, a report generator) has formulas but no cached values; Excel fills them on open. Without
LibreOffice there is no other way to learn what they say, so the common grammar is evaluated here with Excel's own rules: a real
precedence parser (negation, then %, then ^ left to right, then * /, then + -, then & text join, then the comparisons), text compared
without regard to case, numbers joined as text the way Excel shows them. Cell and range references (also across sheets and through named
ranges), and SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, ROUND, ABS, IF, AND, OR, NOT, SQRT, POWER, MOD, INT, LEN, SUMPRODUCT, SUMIF, COUNTIF,
VLOOKUP (exact match, or approximate on a sorted first column), IFERROR. Anything else, and anything the evaluator is not sure of (a text
that would need converting to a number, a wildcard, an overflow), gives no result: it is never guessed.
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
NUM_RE = re.compile(r"^\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*$")
MAX_FORMULA = 8192


def col_num(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


class Unsupported(Exception):
    pass


class ExcelError(Exception):
    """A real spreadsheet error value (#N/A, #NUM!): IFERROR catches it; Unsupported (this evaluator's limit) is never caught."""


class Text(str):
    """A cell the file stores as text (a shared or inline string): it stays text, "12" is not the number 12."""


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


# ---------------------------------------------------------------- Excel value semantics
def num(x):
    """A value as Excel's arithmetic reads it: blank is 0, TRUE is 1, a number-like text is its number; anything else is not ours to guess."""
    if x is None:
        return 0.0
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str) and NUM_RE.match(x):
        return float(x)
    raise Unsupported("not a number")


def to_text(x):
    """A value as Excel joins it into text: 12 not 12.0, TRUE/FALSE, blank is empty."""
    if x is None:
        return ""
    if isinstance(x, bool):
        return "TRUE" if x else "FALSE"
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e15:
            return str(int(x))
        return format(x, ".15g").replace("e", "E")
    if isinstance(x, list):
        raise Unsupported("range as text")
    return str(x)


def power(a, b):
    """Excel's ^ on plain numbers; a result that is complex, infinite or past the float range is not a number Excel would show."""
    a, b = num(a), num(b)
    try:
        r = a ** b
    except OverflowError:
        raise Unsupported("overflow")
    if isinstance(r, complex) or math.isinf(r) or math.isnan(r):
        raise Unsupported("power")
    return r


def _rank(x):
    return 2 if isinstance(x, bool) else 1 if isinstance(x, str) else 0


def compare(op, a, b):
    """Excel's comparison: numbers < text < logicals; text equal without regard to case; a blank equals 0 and ''."""
    if isinstance(a, list) or isinstance(b, list):
        raise Unsupported("range compare")
    if a is None:
        a = "" if isinstance(b, str) else False if isinstance(b, bool) else 0.0
    if b is None:
        b = "" if isinstance(a, str) else False if isinstance(a, bool) else 0.0
    ra, rb = _rank(a), _rank(b)
    if ra != rb:
        c = (ra > rb) - (ra < rb)
    elif ra == 1:
        if op not in ("=", "<>") and not (a.isascii() and b.isascii()):
            raise Unsupported("text order")   # the order of accented letters depends on the locale
        x, y = a.lower(), b.lower()
        c = (x > y) - (x < y)
    else:
        c = (a > b) - (a < b)
    return {"=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0}[op]


def num_or_text(raw):
    if isinstance(raw, Text):
        return str(raw)
    if isinstance(raw, (int, float)):
        return raw
    return float(raw) if NUM_RE.match(str(raw)) else str(raw)


# ---------------------------------------------------------------- parser: Excel precedence, no eval()
class Parser:
    def __init__(self, f, names):
        self.toks, self.i, self.names = [], 0, names
        f = f.strip()
        if f.startswith("="):
            f = f[1:]
        if len(f) > MAX_FORMULA:
            raise Unsupported("long")
        pos = 0
        while pos < len(f):
            m = TOKEN.match(f, pos)
            if not m:
                raise Unsupported("token")
            pos = m.end()
            if m.lastgroup != "ws":
                self.toks.append((m.lastgroup, m.group(m.lastgroup)))

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def op(self, *ops):
        k, t = self.peek()
        if k == "op" and t in ops:
            self.i += 1
            return t
        return None

    def parse(self):
        n = self.cmp()
        if self.i != len(self.toks):
            raise Unsupported("syntax")
        return n

    def cmp(self):
        n = self.concat()
        while (o := self.op("=", "<>", "<=", ">=", "<", ">")):
            n = ("cmp", o, n, self.concat())
        return n

    def concat(self):
        n = self.add()
        while self.op("&"):
            n = ("cat", n, self.add())
        return n

    def add(self):
        n = self.mul()
        while (o := self.op("+", "-")):
            n = ("bin", o, n, self.mul())
        return n

    def mul(self):
        n = self.pow()
        while (o := self.op("*", "/")):
            n = ("bin", o, n, self.pow())
        return n

    def pow(self):   # ^ is left to right: 2^3^2 is (2^3)^2 = 64
        n = self.pct()
        while self.op("^"):
            n = ("pow", n, self.pct())
        return n

    def pct(self):
        n = self.unary()
        while self.op("%"):
            n = ("bin", "/", n, ("num", 100.0))
        return n

    def unary(self):   # negation binds tighter than ^: -2^2 is 4
        if self.op("-"):
            return ("neg", self.unary())
        if self.op("+"):
            return self.unary()
        return self.primary()

    def primary(self):
        k, t = self.take()
        if k == "num":
            return ("num", float(t))
        if k == "str":
            return ("str", t[1:-1].replace('""', '"'))
        if k == "ref":
            return ("ref", t)
        if k == "func":
            name = t.upper()
            if name not in FUNCS and name not in LAZY:
                raise Unsupported(name)
            args = []
            if not self.op(")"):
                while True:
                    args.append(self.cmp())
                    if self.op(")"):
                        break
                    if not self.op(","):
                        raise Unsupported("syntax")
            return ("call", name, args)
        if k == "name":
            u = t.upper()
            if u in ("TRUE", "FALSE"):
                return ("bool", u == "TRUE")
            if t.lower() in self.names:
                return ("name", self.names[t.lower()])
            raise Unsupported("name " + t)
        if k == "op" and t == "(":
            n = self.cmp()
            if not self.op(")"):
                raise Unsupported("syntax")
            return n
        raise Unsupported("syntax")


class Book:
    def __init__(self, cells, formulas, names):
        self.cells = cells            # sheet -> {(r, c): raw value string}
        self.formulas = formulas      # sheet -> {(r, c): formula text}
        self.names = names            # name -> target text
        self.lnames = {k.lower(): v for k, v in names.items()}
        self.memo = {}
        self.busy = set()
        self.parsed = {}

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
        if (abs(r2 - r1) + 1) * (abs(c2 - c1) + 1) > 1_000_000:
            raise Unsupported("range too large")
        return [[self.value(sheet, r, c) for c in range(min(c1, c2), max(c1, c2) + 1)] for r in range(min(r1, r2), max(r1, r2) + 1)]

    def evaluate(self, f, sheet, depth=0):
        """The formula's value, or Unsupported when it is outside what this evaluator does exactly."""
        if depth > 8:
            raise Unsupported("deep")
        try:
            tree = self.parsed.get(f)
            if tree is None:
                tree = self.parsed[f] = Parser(f, self.lnames).parse()
            v = self.ev(tree, sheet, depth)
        except (ZeroDivisionError, TypeError, ValueError, KeyError, IndexError, OverflowError, RecursionError, ExcelError):
            raise Unsupported("eval")
        if isinstance(v, list):
            raise Unsupported("range result")
        return v

    def ev(self, n, sheet, depth):
        k = n[0]
        if k == "num" or k == "str" or k == "bool":
            return n[1]
        if k == "ref":
            sh, a, b = split_ref(n[1], sheet)
            return self.rng(sh, a, b) if b else self.value(sh, *addr(a))
        if k == "name":
            return self.evaluate(n[1], sheet, depth + 1)
        if k == "neg":
            return -num(self.ev(n[1], sheet, depth))
        if k == "pow":
            return power(self.ev(n[1], sheet, depth), self.ev(n[2], sheet, depth))
        if k == "bin":
            a, b = num(self.ev(n[2], sheet, depth)), num(self.ev(n[3], sheet, depth))
            r = a + b if n[1] == "+" else a - b if n[1] == "-" else a * b if n[1] == "*" else a / b
            if not math.isfinite(r):
                raise Unsupported("overflow")
            return r
        if k == "cat":
            return to_text(self.ev(n[1], sheet, depth)) + to_text(self.ev(n[2], sheet, depth))
        if k == "cmp":
            return compare(n[1], self.ev(n[2], sheet, depth), self.ev(n[3], sheet, depth))
        if k == "call":
            name, args = n[1], n[2]
            if name == "IF":   # lazy: only the branch taken is evaluated, so IF(A1=0,0,1/A1) is fine
                if not 2 <= len(args) <= 3:
                    raise Unsupported("IF args")
                cond = self.ev(args[0], sheet, depth)
                if isinstance(cond, (list, str)):
                    raise Unsupported("IF condition")
                if cond:
                    return self.ev(args[1], sheet, depth)
                return self.ev(args[2], sheet, depth) if len(args) == 3 else False
            if name == "IFERROR":
                if len(args) != 2:
                    raise Unsupported("IFERROR args")
                try:
                    return self.ev(args[0], sheet, depth)
                except (ZeroDivisionError, ValueError, ExcelError):
                    return self.ev(args[1], sheet, depth)
            return FUNCS[name](*[self.ev(a, sheet, depth) for a in args])
        raise Unsupported(k)


def flat(args):
    for a in args:
        if isinstance(a, list):
            for x in flat(a):
                yield x
        else:
            yield a


def nums(args):
    if any(isinstance(a, str) for a in args):
        raise Unsupported("text argument")   # SUM("3") is 3 in Excel: not ours to guess
    return [x for x in flat(args) if isinstance(x, (int, float)) and not isinstance(x, bool)]


def vlookup(key, table, idx, approx=True):
    if not isinstance(table, list) or int(num(idx)) < 1:
        raise Unsupported("vlookup")
    col = int(num(idx)) - 1
    exact = approx is False or (not isinstance(approx, (list, bool)) and num(approx) == 0)
    if exact:
        for row in table:
            if row and row[0] is not None and compare("=", row[0], key):
                return row[col]
        raise ExcelError("#N/A")
    keys = [row[0] for row in table if row]   # approximate match: the last row whose key is not above the wanted one, on a sorted first column
    if not all(isinstance(k, (int, float)) and not isinstance(k, bool) for k in keys) or keys != sorted(keys) or not isinstance(key, (int, float)):
        raise Unsupported("approximate lookup needs sorted numbers")
    hit = [i for i, k in enumerate(keys) if k <= key]
    if not hit:
        raise ExcelError("#N/A")
    return table[hit[-1]][col]


def crit(c):
    if isinstance(c, str):
        if "*" in c or "?" in c or "~" in c or c == "":
            raise Unsupported("wildcard criterion")
        m = re.match(r"(<=|>=|<>|<|>|=)?(.*)$", c)
        op, val = m.group(1) or "=", m.group(2)
        try:
            val = float(val)
        except ValueError:
            pass
        return op, val
    return "=", c


def match(x, op, val):
    """One COUNTIF/SUMIF test: text equals without regard to case; a number-vs-text pair never matches (Excel skips it)."""
    if x is None or isinstance(x, bool) or isinstance(x, (int, float)) != isinstance(val, (int, float)):
        return False
    try:
        return compare(op, x, val)
    except Unsupported:
        return False


def f_round(x, n=0):
    x, n = num(x), int(num(n))
    return round(x + 1e-12 * (1 if x >= 0 else -1) * min(1.0, abs(x)), n) if abs(x) < 1e15 else x


FUNCS = {
    "SUM": lambda *a: sum(nums(a)), "AVERAGE": lambda *a: sum(nums(a)) / len(nums(a)), "MIN": lambda *a: min(nums(a)), "MAX": lambda *a: max(nums(a)),
    "COUNT": lambda *a: float(len(nums(a))), "COUNTA": lambda *a: float(sum(1 for x in flat(a) if x not in (None, ""))), "ROUND": f_round,
    "ABS": lambda x: abs(num(x)), "AND": lambda *a: all(flat(a)), "OR": lambda *a: any(flat(a)), "NOT": lambda x: not x,
    "SQRT": lambda x: math.sqrt(num(x)), "POWER": power, "MOD": lambda a, b: num(a) % num(b), "INT": lambda x: float(math.floor(num(x))),
    "LEN": lambda x: float(len(to_text(x))), "VLOOKUP": vlookup,
    "SUMPRODUCT": lambda *a: sum(math.prod(t) for t in zip(*[list(flat([x])) for x in a])),
    "SUMIF": lambda rg, c, sr=None: sum(s for x, s in zip(flat([rg]), flat([sr if sr is not None else rg])) if isinstance(s, (int, float)) and not isinstance(s, bool) and match(x, *crit(c))),
    "COUNTIF": lambda rg, c: float(sum(1 for x in flat([rg]) if match(x, *crit(c)))),
}
LAZY = {"IF", "IFERROR"}   # evaluated in Book.ev, one branch at a time


def fmt(v):
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return f"{v:,.12g}" if abs(v) < 1e15 else f"{v:.12g}"
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
    lines, done, skipped = [], 0, []
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
                    skipped.append(f"{sheet}!{ref}")   # no stored result and not exactly computable here: no value is given, none is guessed
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
        look.line("Computed here from the formulas (the file stores no result for them; each figure is this tool's own evaluation of the cells with Excel's rules, so confirm a key one in Excel): "
                  + "; ".join(lines) + ".", 66)
        look.fact("computed_formulas", len(lines))
    if skipped:
        look.line(f"Not computed: {len(skipped)} formula(s) without a stored result use something this evaluator does not do exactly (a function it lacks, text-to-number conversion, an overflow, a wildcard); no value is given for them: "
                  + ", ".join(skipped[:12]) + (" ..." if len(skipped) > 12 else "") + ".", 65)
        look.fact("uncomputed_formulas", len(skipped))
