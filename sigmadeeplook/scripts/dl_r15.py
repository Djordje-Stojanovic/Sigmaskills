"""SigmaDeepLook fix round 15 (ticket 83, P0.14b.H5): the exact routes that held-out set 14's wrong answers showed. Stdlib only.

1. `IGNORE_CASE`: the wordings that make a whole-word match ignore case ("any capitalisation", "regardless of case", ...), shared by the table
   route (`dl_ask`) and the document route (`dl_wordcount`).
2. `drop_asideq`: a quoted word inside a bracketed aside is an example, never a filter.
3. `number_value`: a number written with a comma in a question is a decimal or a thousands separator; the table's own convention decides the
   ambiguous case ("2,250").
4. `miss_*`: the codes an SPSS file declares missing (discrete values, ranges, strings) and the line that says what an answer left out.
"""
import re

IGNORE_CASE = re.compile(
    r"\b(?:ignor\w*\s+(?:the\s+)?(?:letter\s+)?case"
    r"|case[- ]?insensitiv\w*"
    r"|(?:in\s+)?any\s+(?:letter\s+)?(?:case|capitali[sz]ation|capitals?)"
    r"|(?:regardless|irrespective)\s+of\s+(?:the\s+)?(?:letter\s+)?(?:case|capitali[sz]ation|capitals)"
    r"|(?:whatever|no\s+matter)\s+(?:the\s+)?(?:letter\s+)?(?:case|capitali[sz]ation)"
    r"|without\s+regard\s+to\s+(?:the\s+)?(?:letter\s+)?(?:case|capitali[sz]ation)"
    r"|(?:upper|lower)\s*(?:case)?\s+or\s+(?:upper|lower)\s*case"
    r"|(?:capitali[sz]ation|case)\s+(?:does\s*n[o'’]t|doesn[’']t|is\s+not|isn[’']t)\s+matter"
    r"|capital\s+or\s+small\s+letters)\b", re.I)

_PAREN = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
_QUOTED = re.compile(r"(?<!\w)(['\"`‘“«„])(.+?)(['\"`’”»“])(?!\w)")


def drop_asideq(text):
    """The text without the quoted words inside its bracketed asides: "(forms such as 'latarni' do not count)" asks for no filter."""
    return _PAREN.sub(lambda m: _QUOTED.sub(" ", m.group(0)), text)


def number_value(text):
    """A number as a question writes it -> (value, other reading or None). A comma followed by one, two or four or more digits, or after a lone 0, is a
    decimal comma; several groups of three digits are thousands; one comma and exactly three digits is ambiguous (thousands first, the decimal
    reading second); a comma and a point together: the later one is the decimal mark."""
    s = text.strip().rstrip(",")
    sign = -1.0 if s.startswith("-") else 1.0
    s = s.lstrip("+-")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):   # 1.234,5
            return sign * float(s.replace(".", "").replace(",", ".")), None
        return sign * float(s.replace(",", "")), None   # 2,250.5
    if "," not in s:
        return sign * float(s), None
    parts = s.split(",")
    if len(parts) > 2:   # 1,234,567
        return sign * float("".join(parts)), None
    whole, frac = parts
    if len(frac) != 3 or whole == "0" or len(whole) > 3:
        return sign * float(whole + "." + frac), None
    return sign * float(whole + frac), sign * float(whole + "." + frac)


# ---------------------------------------------------------------- declared missing values (SPSS)
_RAW_A = re.compile(r"(?i)\b(?:includ\w*|incl\.?|counting|count|keeping|keep|using|use)\s+(?:also\s+)?(?:the\s+|all\s+|any\s+)?(?:user[- ]defined\s+|declared\s+)?missing\b"
                    r"|\braw\s+(?:values?|codes?|data|numbers|figures)\b|\bas\s+(?:they\s+are\s+)?coded\b|\bunmasked\b|\bmissing\s+(?:codes?|values?)\s+(?:too|as\s+well|included|count|do\s+count)\b"
                    r"|\bnot\s+(?:excluding|ignoring|dropping|removing)\b[^.?;]{0,40}missing\b|\bdo(?:es)?\s*n[o'’]t\s+(?:exclude|ignore|drop|remove)\b[^.?;]{0,40}missing\b")
_NOT_BEFORE = re.compile(r"(?i)\b(?:not|never|without|n[o'’]t|except|excluding|ignoring|ignore|exclude)\s*$")


def wants_raw_missing(q):
    """True when the question asks to keep the values a file declares missing ("including the missing codes", "the raw values")."""
    for m in _RAW_A.finditer(q):
        if m.group(0).lower().startswith(("not", "do")) or not _NOT_BEFORE.search(q[max(0, m.start() - 14):m.start()]):
            return True
    return False


def missing_line(table, cols):
    """The line that says what an answer did about the values its columns declare missing, or None when none of them holds one."""
    miss = getattr(table, "miss", None) or {}
    parts, total = [], 0
    for ci in sorted(cols):
        m = miss.get(ci)
        n = m["sav"].mcount.get(m["k"], 0) if m else 0
        if n:
            total += n
            parts.append(f"{table.cols[ci]}: codes {m['text']}")
    if not parts:
        return None
    if getattr(table, "raw_missing", False):
        return f"User-defined missing values included, as the question asks for the raw values: {total:,} cases ({'; '.join(parts)})."
    return f"User-defined missing values excluded: {total:,} cases ({'; '.join(parts)}); system-missing values are not counted either."
