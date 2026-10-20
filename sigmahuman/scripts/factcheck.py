#!/usr/bin/env python3
"""SigmaHuman fact check: compare a text before and after a rewrite.

  python factcheck.py BEFORE AFTER [--json]

Lists numbers, quotes, inline code and links that the rewrite lost or added, names that
appear less or more often, and the sentence-length band of both texts (average words per
sentence and spread), so a script for the ear keeps its rhythm.

Numbers are compared by value: "4,500", "4.5 thousand" and "four and a half thousand" are
one number; "40%" and "40 percent" are one number. Standard library only, Python 3.8+.

Exit 0: no number, quote, code span or link lost or added. Exit 1: the list shows what to
fix (a lost claim the patterns cut on purpose is fine; say so in the report). Exit 2: bad
arguments or an unreadable file.
"""
import collections
import json
import re
import statistics
import sys

SMALL = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
SCALE = {"hundred": 100, "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
SHORT = {"k": 1e3, "m": 1e6, "mn": 1e6, "bn": 1e9, "b": 1e9, "tn": 1e12}
PERCENT = {"%", "percent", "per cent"}
WORDNUM = re.compile(
    r"\b(?:(?:%s|a|half|and)[\s-]+)*(?:%s)\b" % (
        "|".join(list(SMALL) + list(SCALE)), "|".join(list(SMALL) + list(SCALE))),
    re.I)
NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*"
    r"(%|percent\b|per cent\b|thousand\b|million\b|billion\b|trillion\b|k\b|mn?\b|bn\b|tn\b)?",
    re.I)
QUOTE = re.compile(r"[\"“]([^\"“”\n]{3,})[\"”]")
CODE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"https?://[^\s)>\]\"']+")
MONTHS = ("January February March April May June July August September October November "
          "December").split()
STOP = set("""A An And As At But By For From He Her His How I If In It Its My No Not Of On Or Our
So She That The Their Then There These They This To We What When Where Which Who Why With You
Your Yes Here Now Just Also Still Even Dear Hey Oh Well Look Let Today Tomorrow""".split())


def words_to_number(phrase):
    """'four and a half thousand' -> 4500.0; None when the phrase holds no number word."""
    total, current, seen, half = 0.0, 0.0, False, False
    for w in re.split(r"[\s-]+", phrase.lower()):
        if w in SMALL:
            current += SMALL[w]
            seen = True
        elif w == "half":
            half, seen = True, True
        elif w == "hundred":
            current = (current or 1) * 100
        elif w in SCALE:
            current = ((current or 1) + (0.5 if half else 0)) * SCALE[w]
            total, current, half = total + current, 0.0, False
    if not seen and total == 0 and current == 0:
        return None
    return total + current + (0.5 if half else 0)


def numbers(text):
    found = collections.Counter()
    for m in WORDNUM.finditer(text):
        phrase = m.group(0).strip()
        if phrase.lower() in {"a", "and", "one"}:
            continue  # "a" and a lone "one" are words, not claims
        value = words_to_number(phrase)
        if value is not None:
            found[(round(value, 6), "")] += 1
    for m in NUMBER.finditer(text):
        value = float(m.group(1).replace(",", "") + (m.group(2) or ""))
        unit = (m.group(3) or "").lower()
        if unit in PERCENT:
            found[(round(value, 6), "%")] += 1
            continue
        value *= SCALE.get(unit, SHORT.get(unit, 1))
        found[(round(value, 6), "")] += 1
    return found


def names(text):
    found = collections.Counter()
    for sentence in re.split(r"(?<=[.!?:])\s+|\n+", text):
        tokens = re.findall(r"[A-ZÀ-ɏ][\w'À-ɏ-]*|\S+", sentence)
        for tok in tokens[1:]:
            tok = re.sub(r"'s$", "", tok)
            if tok[:1].isupper() and tok not in STOP and not tok.isupper():
                found[tok] += 1
    for month in MONTHS:
        n = len(re.findall(r"\b%s\b" % month, text))
        if n:
            found[month] = n
    return found


def band(text):
    prose = CODE.sub(" ", LINK.sub(" ", text))
    lengths = [len(s.split()) for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", prose) if s.split()]
    if not lengths:
        return {"sentences": 0, "avg_words": 0, "spread": 0}
    spread = statistics.pstdev(lengths) if len(lengths) > 1 else 0
    return {"sentences": len(lengths), "avg_words": round(statistics.mean(lengths), 1),
            "spread": round(spread, 1)}


def fmt(key):
    value, unit = key
    return ("%g" % value) + unit


def compare(before, after):
    report = {"lost": [], "added": [], "names_fewer": [], "names_more": []}
    nb, na = numbers(before), numbers(after)
    report["lost"] += ["number %s" % fmt(k) for k in sorted((nb - na).elements())]
    report["added"] += ["number %s" % fmt(k) for k in sorted((na - nb).elements())]
    for label, pattern in (("quote", QUOTE), ("code", CODE), ("link", LINK)):
        cb = collections.Counter(m.group(1) if pattern.groups else m.group(0) for m in pattern.finditer(before))
        ca = collections.Counter(m.group(1) if pattern.groups else m.group(0) for m in pattern.finditer(after))
        report["lost"] += ["%s %r" % (label, k) for k in sorted((cb - ca).elements())]
        report["added"] += ["%s %r" % (label, k) for k in sorted((ca - cb).elements())]
    mb, ma = names(before), names(after)
    report["names_fewer"] = ["%s (%d -> %d)" % (k, mb[k], ma.get(k, 0)) for k in sorted(mb) if ma.get(k, 0) < mb[k]]
    report["names_more"] = ["%s (%d -> %d)" % (k, mb.get(k, 0), ma[k]) for k in sorted(ma) if mb.get(k, 0) < ma[k]]
    report["band_before"], report["band_after"] = band(before), band(after)
    report["ok"] = not report["lost"] and not report["added"]
    return report


def main(argv):
    args = [a for a in argv if a != "--json"]
    if len(args) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    try:
        before, after = (open(p, encoding="utf-8").read() for p in args)
    except OSError as err:
        print("cannot read %s" % err.filename, file=sys.stderr)
        return 2
    report = compare(before, after)
    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    print("Facts: %s" % ("nothing lost or added" if report["ok"] else "CHECK the lines below"))
    for line in report["lost"]:
        print("  LOST   " + line)
    for line in report["added"]:
        print("  ADDED  " + line)
    for line in report["names_fewer"]:
        print("  NAME FEWER  " + line)
    for line in report["names_more"]:
        print("  NAME MORE   " + line)
    b, a = report["band_before"], report["band_after"]
    print("Sentences: before %d, avg %.1f words, spread %.1f | after %d, avg %.1f words, spread %.1f"
          % (b["sentences"], b["avg_words"], b["spread"], a["sentences"], a["avg_words"], a["spread"]))
    if b["avg_words"] and abs(a["avg_words"] - b["avg_words"]) > 0.25 * b["avg_words"]:
        print("  BAND  the average sentence length moved more than 25 %; for a script for the ear, keep the band")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
