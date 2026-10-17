"""SigmaDeepLook: delimited-text sniffing (fix round 5). Stdlib only.

Three questions a CSV reader must answer before it can count anything, each answered from the bytes, never from the extension alone:

- encoding: byte-order marks (UTF-8, UTF-16, UTF-32), UTF-16 without a mark (NUL bytes on every second position), strict UTF-8,
  then Windows-1252 (the usual "ANSI" export) and Latin-1 as the last resort;
- dialect: the delimiter whose field count is the same on the most lines (comma, semicolon, tab, pipe, colon), quotes honoured;
  ties go to the delimiter that gives more fields;
- decimal mark: a column whose numbers are written `1.234,56` or `3,5` (and the delimiter is not a comma) is read with a decimal
  comma; its cells are converted (`1.234,56` -> `1234.56`) before any sum, mean, minimum or maximum.
"""
import codecs
import csv
import io
import re

DELIMS = (",", ";", "\t", "|", ":")
DEC_COMMA_RE = re.compile(r"^[-+]?(\d{1,3}(\.\d{3})+|\d+),\d+$")      # 1.234,56  3,5  -0,25
THOUSANDS_DOT_RE = re.compile(r"^[-+]?\d{1,3}(\.\d{3})+$")          # 1.234 (a whole number in a decimal-comma column)
PLAIN_INT_RE = re.compile(r"^[-+]?\d+$")
DOT_DEC_RE = re.compile(r"^[-+]?\d*\.\d+$")
SAMPLE_LINES = 400


def sniff_encoding(raw):
    """bytes -> (text, encoding name). Never raises; Latin-1 decodes anything."""
    for bom, enc in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"), (codecs.BOM_UTF8, "utf-8-sig"),
                     (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16")):
        if raw.startswith(bom):
            try:
                return raw.decode(enc), enc
            except UnicodeDecodeError:
                break
    head = raw[:4096]
    if len(head) >= 4:
        even0 = sum(1 for b in head[0::2] if b == 0) / max(1, len(head[0::2]))
        odd0 = sum(1 for b in head[1::2] if b == 0) / max(1, len(head[1::2]))
        if odd0 > 0.3 and even0 < 0.05:
            enc = "utf-16-le"
        elif even0 > 0.3 and odd0 < 0.05:
            enc = "utf-16-be"
        else:
            enc = None
        if enc:
            try:
                return raw[:len(raw) - len(raw) % 2].decode(enc), enc
            except UnicodeDecodeError:
                pass
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as e:
        if e.start >= len(raw) - 3:   # a cut multi-byte character at the very end (a capped read)
            try:
                return raw[:e.start].decode("utf-8"), "utf-8"
            except UnicodeDecodeError:
                pass
    try:
        return raw.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1"


def is_text_bytes(raw):
    """True when the bytes decode as text by sniff_encoding's rules (UTF-16 without a mark included) and hold few control bytes."""
    text, enc = sniff_encoding(raw[:65536])
    if enc.startswith(("utf-16", "utf-32")):
        body = text[:20000]
        return bool(body) and sum(1 for c in body if ord(c) < 9 or 13 < ord(c) < 32) / len(body) < 0.02
    return b"\0" not in raw[:65536]


def _lines(text, n=SAMPLE_LINES):
    out = []
    for ln in io.StringIO(text[:400_000], newline=""):
        if ln.strip():
            out.append(ln)
            if len(out) >= n:
                break
    return out


def sniff_dialect(text, hint=None):
    """-> (delimiter, field count, share of lines with that count). The delimiter with the most consistent field count > 1 wins;
    ties go to more fields, then to the hint (the extension's delimiter)."""
    lines = _lines(text)
    if not lines:
        return hint or ",", 1, 0.0
    sample = "".join(lines)
    best = None
    for d in DELIMS:
        if d not in sample:
            continue
        try:
            counts = [len(r) for r in csv.reader(io.StringIO(sample, newline=""), delimiter=d)]
        except csv.Error:
            continue
        if not counts:
            continue
        mode = max(set(counts), key=counts.count)
        if mode < 2:
            continue
        share = counts.count(mode) / len(counts)
        header_ok = counts[0] == mode
        score = (round(share, 2) + (0.05 if header_ok else 0), mode, d == hint, -DELIMS.index(d))
        if best is None or score > best[0]:
            best = (score, d, mode, share)
    if best is None:
        return hint or ",", 1, 0.0
    return best[1], best[2], best[3]


def decimal_comma_columns(text, delim, ncols, max_rows=2000):
    """Column indexes written with a decimal comma: most non-empty cells match `1.234,56` / `3,5` (whole numbers may join them)
    and at least one cell has the comma. Never for comma-delimited text."""
    if delim == "," or ncols < 1:
        return set()
    hits = [0] * ncols
    ints = [0] * ncols
    dots = [0] * ncols
    filled = [0] * ncols
    rd = csv.reader(io.StringIO(text[:2_000_000], newline=""), delimiter=delim)
    next(rd, None)
    for k, rec in enumerate(rd):
        if k >= max_rows:
            break
        if len(rec) != ncols:
            continue
        for i, c in enumerate(rec):
            s = c.strip()
            if not s:
                continue
            filled[i] += 1
            if DEC_COMMA_RE.match(s):
                hits[i] += 1
            elif PLAIN_INT_RE.match(s) or THOUSANDS_DOT_RE.match(s):
                ints[i] += 1
            elif DOT_DEC_RE.match(s):
                dots[i] += 1
    return {i for i in range(ncols) if hits[i] and not dots[i] and hits[i] + ints[i] >= 0.9 * filled[i]}


def to_dot(s):
    """'1.234,56' -> '1234.56'; '3,5' -> '3.5'; '1.234' -> '1234'; anything else unchanged."""
    t = s.strip()
    if DEC_COMMA_RE.match(t):
        return t.replace(".", "").replace(",", ".")
    if THOUSANDS_DOT_RE.match(t):
        return t.replace(".", "")
    return s


def normalizer(cols):
    """-> f(record) that rewrites the decimal-comma columns, or None when there are none."""
    if not cols:
        return None
    cols = sorted(cols)

    def norm(rec):
        rec = list(rec)
        for i in cols:
            if i < len(rec):
                rec[i] = to_dot(rec[i])
        return rec
    return norm


def describe(enc, delim, ncols, share, dec_cols, header):
    names = [header[i] if i < len(header) else f"column {i + 1}" for i in sorted(dec_cols)]
    d = {"\t": "tab", ",": "comma", ";": "semicolon", "|": "pipe", ":": "colon"}.get(delim, repr(delim))
    s = f"Read as: encoding {enc}, delimiter {d}, {ncols} fields on {share:.0%} of the first lines"
    if names:
        s += f", decimal comma in {', '.join(names[:12])} (converted to numbers before every sum and range)"
    return s + "."
