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
import math
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
    return decode_legacy(raw)


# ---- single-byte code pages: pick the one whose letters look like real text (fix round H7)
LEGACY_LABELS = {"cp1252": "Windows-1252", "latin-1": "Latin-1", "cp1250": "Windows-1250 (Central European)", "cp1251": "Windows-1251 (Cyrillic)",
                 "koi8_r": "KOI8-R (Cyrillic)", "cp866": "CP866 (DOS Cyrillic)", "cp1253": "Windows-1253 (Greek)", "cp1254": "Windows-1254 (Turkish)"}
_COMMON_LATIN = {c: 1.0 for c in "éáíóúñüöäßàçêâîôåøÉÁÍÓÚÑÜÖÄ"}
_COMMON_LATIN.update({c: 0.7 for c in "èùëïûãõìòœÿýÈÀ"})
_COMMON_CE = {c: 1.0 for c in "éáíóúüöäýěščřžůťďňÉÁÍÓÚÜÖÄ"}   # Central-European letters the Western pages lack (the bulk of cp1250 text)
_COMMON_CE.update({c: 1.2 for c in "čćšžđČĆŠŽĐąęłśźżńĄĘŁŚŹŻŃőűŐŰ"})
_COMMON_CE.update({c: 0.8 for c in "ăâîșțşţĂÂÎȘȚŞŢĺľŕĹĽŔ"})
_COMMON_TR = {c: 1.2 for c in "ğışĞİŞ"}
_COMMON_TR.update(_COMMON_LATIN)
REPL = chr(0xFFFD)
WORDISH_RE = re.compile(r"[^\s\d.,;:|\"'()\[\]{}<>=+/\_-]+")   # a word for scoring: split on space, digits and the usual field and number marks
_CODEPAGES = ("cp1252", "cp1250", "cp1251", "koi8_r", "cp866", "cp1253", "cp1254")


def _latin_score(text, table):
    """Mean plausibility of the non-ASCII characters of a Latin-script reading: common letters score high, symbols and control codes low,
    and words made mostly of accented letters (a Cyrillic page read as Latin) are punished. A word is a run of letters and the bytes that
    decode to symbols (fix round 9): a delimited record ('4000;Èâàíîâ;Ìîñêâà') is three words, not one word mostly made of ASCII."""
    total = n = 0.0
    for m in WORDISH_RE.finditer(text):
        w = m.group()
        hi = [c for c in w if ord(c) > 127]
        if not hi:
            continue
        crowded = len(w) >= 3 and len(hi) / len(w) > 0.6
        for i, c in enumerate(w):
            if ord(c) < 128:
                continue
            n += 1
            if c == REPL or 0x80 <= ord(c) < 0xA0:
                total -= 6
            elif c.isalpha():
                v = table.get(c, 0.15)
                if c.isupper() and i and w[i - 1].islower():
                    v -= 1.0   # an upper-case letter inside a word
                total += v - (1.2 if crowded else 0)
            elif c in "‘’“”„–—…€•«»¿¡°":
                total += 0.8
            else:
                total -= 2.5   # a stray symbol (superscripts, fractions, math signs) is almost never what the author typed
    return total / n if n else 0.0


def _freq_table(spec):
    out = {}
    for item in spec.split():
        letters, _, f = item.partition("=")
        for c in letters:
            out[c] = float(f)
    return out


# approximate letter frequencies in percent (Russian and Serbian Cyrillic share most of them; Greek apart)
_FREQ_CYR = _freq_table("о=10 е=8.5 а=8 и=7.5 н=6.7 т=6.3 с=5.5 р=4.7 в=4.5 л=4.3 к=3.5 м=3.2 д=3 п=2.8 у=2.6 я=2 ы=1.9 ь=1.7 г=1.7 з=1.6 б=1.6 ч=1.4 й=1.2 х=.9 ж=.9 ш=.7 ю=.6 ц=.5 щ=.4 э=.3 ф=.3 ј=2.2 ђ=.5 ћ=.8 љ=.4 њ=.4 џ=.1 ё=.2 ъ=.1")
_FREQ_EL = _freq_table("α=11 ο=9.5 ε=8.5 ι=8 τ=8 ν=7 σ=6 ς=2 ρ=5.5 κ=4.8 π=4.5 μ=3.5 υ=3.4 λ=3.2 η=3 ω=2.5 δ=2 γ=1.6 θ=1.5 χ=1.2 φ=.9 β=.7 ξ=.5 ψ=.5 ζ=.4 ά=1.5 έ=1 ή=.8 ί=1 ό=1.5 ύ=.8 ώ=.6")


def _letter_value(c, table):
    f = table.get(c.lower(), 0.0)
    return (math.log10(f + 0.2) + 0.7) / 1.5


def _script_score(text, table, lo, hi):
    """Mean plausibility of the letters of one script: how common each letter is in real text; a word that mixes ASCII letters with this
    script, or flips from lower to upper case inside the word, is almost surely the wrong code page."""
    total = n = 0.0
    for m in WORDISH_RE.finditer(text):
        w = m.group()
        if not any(ord(c) > 127 for c in w):
            continue
        mixed = any(c.isascii() and c.isalpha() for c in w)
        for i, c in enumerate(w):
            if ord(c) < 128:
                continue
            n += 1
            if lo <= c <= hi:
                v = _letter_value(c, table)
                if mixed:
                    v -= 1.5
                if c.isupper() and i and w[i - 1].islower():
                    v -= 1.0
                total += v
            elif c in "‘’“”„–—…€•«»№°":
                total += 0.8
            else:
                total -= 3.0
    return total / n if n else 0.0


def _score_codepage(sample, enc):
    text = sample.decode(enc, "replace")
    if enc == "cp1252":
        return _latin_score(text, _COMMON_LATIN)
    if enc == "cp1250":
        return _latin_score(text, _COMMON_CE)
    if enc == "cp1254":
        return _latin_score(text, _COMMON_TR) - 0.1
    if enc == "cp1253":
        return _script_score(text, _FREQ_EL, "Ͱ", "Ͽ")
    return _script_score(text, _FREQ_CYR, "Ѐ", "ӿ") - (0.05 if enc != "cp1251" else 0)


def _sample(raw, size=300_000):
    if len(raw) <= size:
        return raw
    k = size // 3
    mid = len(raw) // 2
    return raw[:k] + b"\n" + raw[mid:mid + k] + b"\n" + raw[-k:]


def guess_codepage(raw):
    """-> the single-byte code page whose reading of the bytes looks most like real text (default cp1252). A multi-byte East-Asian code page
    comes from charset-normalizer when that package is installed."""
    smp = _sample(raw)
    try:
        import charset_normalizer   # optional: only to recognise the multi-byte East-Asian code pages
        best = charset_normalizer.from_bytes(smp).best()
        if best is not None and best.encoding in ("shift_jis", "cp932", "euc_jp", "gb2312", "gbk", "gb18030", "big5", "euc_kr", "cp949", "johab"):
            return best.encoding
    except Exception:
        pass
    scores = {}
    for enc in _CODEPAGES:
        scores[enc] = _score_codepage(smp, enc) + (0.25 if enc == "cp1252" else 0.0)   # the usual "ANSI" export wins a close call
    return max(scores, key=scores.get)


def decode_legacy(raw):
    """Bytes that are not valid UTF-8 -> (text, encoding). A big UTF-8 file with a few stray bad bytes stays UTF-8 (the bad ones become U+FFFD);
    anything else is read with the code page that scores best. Never raises."""
    lossy = raw.decode("utf-8", "replace")
    bad = lossy.count(REPL)
    good = sum(1 for c in lossy if ord(c) > 127 and c != REPL)
    if bad and good >= 20 * bad and good >= 20:
        return lossy, "utf-8"
    enc = guess_codepage(raw)
    try:
        return raw.decode(enc), enc
    except UnicodeDecodeError:
        if enc == "cp1252":
            return raw.decode("latin-1"), "latin-1"
        return raw.decode(enc, "replace"), enc


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
