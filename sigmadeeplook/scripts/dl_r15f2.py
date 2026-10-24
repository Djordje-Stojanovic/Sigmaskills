"""SigmaDeepLook --ask: never answer a count silently when the question holds a qualifier the engine did not apply (fix round 15).

A question often carries a clause that changes the answer: "values declared missing do not count", "whole word, any capitalisation", "greater than 22,50",
"between 2020 and 2022", "except Berlin". The engine counts what it has a filter for. When a clause is left over, the number is still given, but a line
`Not applied: <the clause>` follows the answer, so the reader knows the figure ignores it.

The rule is conservative. A clause counts as applied when the answer's own lines (the Answer, Filters and Table lines and the notes) show it: the same
number in a comparison, the same word in an exclusion, "whole word" or "ignoring case" in a word filter. Only these clause shapes are watched; an aside
in brackets that matches none of them is never flagged.
"""
import re

SENT = r"[^.?!;\n]*"
MISSING_WORD = r"(?:missing|null|blank|empty|n/?a|nan|unknown)"
MISSING_A = re.compile(SENT + r"\b" + MISSING_WORD + r"\b" + SENT + r"\b(?:do(?:es)?\s*n[o']t\s+count|not\s+count(?:ed)?|excluded?|ignored|left\s+out|skipped|omitted|removed|disregarded|do\s+not\s+apply)\b" + SENT, re.I)
MISSING_B = re.compile(r"\b(?:exclud\w+|ignor\w+|skip\w*|omit\w*|disregard\w*|not\s+counting|without|leav\w+\s+out)\s+" + SENT + r"\b" + MISSING_WORD + r"\b" + SENT, re.I)
MISSING_OK = re.compile(r"(?:\b(?:non-?|not\s+|without\s+|excluding\s+|excluded\s+|ignoring\s+|skipping\s+)(?:\w+\s+)?" + MISSING_WORD + r"\b|\b" + MISSING_WORD
                        + r"\w*\s+(?:values?\s+|cells?\s+|codes?\s+)?(?:are\s+|were\s+)?(?:excluded|ignored|skipped|not\s+counted|left\s+out)|user-?missing|declared\s+missing)", re.I)
SPECIAL_MISSING = re.compile(r"\b(?:declared|user|defined|code[sd]?|sentinel|special|reserved|flag(?:ged)?)\b", re.I)
WORD_Q = re.compile(r"\bwhole[- ]words?\b", re.I)
WORD_OK = re.compile(r"\bwhole[- ]words?\b|\bword\s+boundar|\bas\s+a\s+(?:whole\s+)?word\b", re.I)
CASE_Q = re.compile(r"\b(?:any\s+capitali[sz]ation|either\s+case|(?:upper|lower)\s*(?:or|and)\s*(?:lower|upper)\s*case|case[- ]?insensitive|(?:ignor\w+|regardless\s+of|irrespective\s+of)\s+(?:the\s+)?(?:case|capitali[sz]ation|upper|lower))\b", re.I)
CASE_OK = re.compile(r"ignor\w+\s+(?:the\s+)?(?:case|capital)|case[- ]insensitiv|any\s+(?:case|capital)|regardless of case|casefold|lower-?cas|upper-?cas|case-folded|in any capital", re.I)
ONCE_Q = re.compile(r"\b(?:counts?|counted)\s+once\b|\bonce\s+however\s+often\b|\bonly\s+once\b", re.I)
ONCE_OK = re.compile(r"\bonce\b|\bdistinct\b|\bunique\b|\bper\s+(?:cue|row|record|slide|paragraph|line|message|page)\b|\b(?:cues|rows|records|slides|paragraphs|lines|messages|pages|cases)\s+match", re.I)
DISTINCT_Q = re.compile(r"\b(?:unique|distinct)\s+\w+|\bdifferent\s+\w+s\b", re.I)   # "different cities", not "a different city than Paris"
DISTINCT_OK = re.compile(r"\bdistinct\b|\bunique\b|\bdifferent\b", re.I)
BETWEEN_Q = re.compile(r"\bbetween\s+([\w.,:/-]+)\s+and\s+([\w.,:/-]+)", re.I)
BEFORE_Q = re.compile(r"\b(?:before|after|since|until|prior\s+to|earlier\s+than|later\s+than)\s+(\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{2,4}|(?:19|20)\d{2})\b", re.I)
EXCEPT_Q = re.compile(r"\b(?:except(?:ing)?|excluding|other\s+than|apart\s+from|but\s+not|not\s+including)\s+(?:the\s+|those\s+|rows?\s+|records?\s+|cases?\s+|lines?\s+|from\s+|of\s+)*(?:where\s+|with\s+|in\s+)?(['\"‘“]?)([\w.-]{2,40})\1", re.I)
COMPARE_Q = re.compile(r"\b(?:greater|more|larger|bigger|higher|over|above|exceed\w*|less|fewer|smaller|lower|under|below|at\s+least|at\s+most|no\s+more|no\s+less)\s+(?:than\s+)?(-?\d[\d.,]*\d|-?\d)\b", re.I)
NUM = re.compile(r"-?\d[\d.,]*\d|-?\d")
GENERIC_EXCEPT = {"the", "this", "that", "these", "those", "any", "all", "one", "it", "them", "there", "here", "other", "others", "rows", "row", "records", "cases"}


def number(tok):
    """A number as written in a question or a filter -> float, or None. '22,50' is 22.5 (a decimal comma), '1,234' is 1234, '1.234,5' is 1234.5."""
    t = tok.strip().rstrip(".,")
    try:
        if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", t):
            return float(t.replace(",", ""))
        if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+,\d+", t):
            return float(t.replace(".", "").replace(",", "."))
        if re.fullmatch(r"-?\d+,\d+", t):
            return float(t.replace(",", "."))
        return float(t)
    except ValueError:
        return None


def evidence(text):
    """The lines that show what the engine applied: everything of the answer except the echoed question, the `Read as` line (it lists the question's
    own words), the other-tables line and the best-matching lines that follow."""
    out = []
    for i, ln in enumerate(text.split("\n")):
        if i == 0 and ln.startswith("--ask"):
            continue
        if ln.startswith(("Read as:", "Other tables that match", "Best-matching lines")):
            if ln.startswith("Best-matching lines"):
                break
            continue
        out.append(ln)
    return "\n".join(out)


def filters_of(ev):
    return " ".join(ln for ln in ev.split("\n") if ln.startswith("Filters:"))


def check(q, text):
    """-> the list of question clauses the answer text does not show as applied (each at most 140 characters)."""
    ev = evidence(text)
    flt = filters_of(ev)
    left = []

    def add(clause):
        c = " ".join(clause.split()).strip(" ,;:()")
        if c and c not in left:
            left.append(c[:140])
    m = MISSING_A.search(q) or MISSING_B.search(q)
    if m and not MISSING_OK.search(ev):
        has_condition = bool(flt) and not re.match(r"Filters: none\b", flt)
        if not (has_condition and not SPECIAL_MISSING.search(m.group(0))):   # a comparison or an equality never matches an empty cell: "missing values do not count" is then honoured
            add(m.group(0))
    if WORD_Q.search(q) and not WORD_OK.search(ev):
        add(WORD_Q.search(q).group(0))
    if CASE_Q.search(q) and not CASE_OK.search(ev):
        add(CASE_Q.search(q).group(0))
    if ONCE_Q.search(q) and not ONCE_OK.search(ev):
        add(ONCE_Q.search(q).group(0))
    ops = next((ln for ln in text.split(chr(10)) if ln.startswith("Read as:")), "").split(";")[0]   # "Read as: operation distinct"
    if DISTINCT_Q.search(q) and not DISTINCT_OK.search(ev + " " + ops):
        add(DISTINCT_Q.search(q).group(0))
    if flt:   # the clauses below compare against the filters the engine applied
        low = flt.lower()
        shown = {number(t) for t in NUM.findall(flt) if number(t) is not None}
        for m in BETWEEN_Q.finditer(q):
            a, b = m.group(1), m.group(2)
            va, vb = number(a), number(b)
            ok = (va in shown and vb in shown) if va is not None and vb is not None else (a.lower() in low and b.lower() in low)
            if not ok:
                add(m.group(0))
        for m in BEFORE_Q.finditer(q):
            tok = m.group(1)
            if tok.lower() not in low and tok.replace("/", ".") not in low and (number(tok) not in shown or number(tok) is None):
                add(m.group(0))
        for m in EXCEPT_Q.finditer(q):
            w = m.group(2).lower()
            if w in GENERIC_EXCEPT or w in {"missing", "null", "blank", "empty"}:
                continue
            if not re.search(r"(?:\bnot\b|!=|<>|\bexcept\w*|\bexclud\w*|\bother\s+than|\bwithout|\bminus)\W+(?:\w+\W+){0,3}" + re.escape(w) + r"\b", ev.lower()):   # the word must be filtered out, not in
                add(m.group(0))
        for m in COMPARE_Q.finditer(q):
            v = number(m.group(1))
            if v is not None and v not in shown:
                add(m.group(0))
    return left


def guard(q, text):
    """-> the answer text with a `Not applied:` line after its Answer line when the question holds a clause the engine did not apply."""
    if "\nAnswer:" not in "\n" + text or re.search(r"(?m)^Answer: (?:not answered|none)\b", text):
        return text
    if not re.search(r"(?m)^(?:Read as:|Filters:)", text):   # only the table engine's answers: other routes (code page, colours, archives) state their own scope
        return text
    left = check(q, text)
    if not left:
        return text
    lines = text.split("\n")
    at = next(i for i, ln in enumerate(lines) if ln.startswith("Answer:"))
    lines.insert(at + 1, "Not applied: " + "; ".join(f'"{c}"' for c in left) + " (the engine has no filter for it, so the figure above does not account for it)")
    return "\n".join(lines)
