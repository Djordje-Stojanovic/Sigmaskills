"""SigmaDeepLook: the values inside an XML tree, by element path, over the whole document.

Counting element names says what the document is made of; the values (a title, a label, a price, a shape name in a Visio page) say what it
says. This walks every element once, keeps per path the distinct texts and attribute values (capped), and prints one compact row per path:
how many values, how many distinct, the numeric range or the most common samples. Used for an XML file and for XML members of a zip-based
office format (a Visio page, a docx part), including members written on a single line.
"""
import re
from collections import Counter

MAX_ELEMENTS = 2_000_000
DISTINCT_CAP = 300
WHOLE = 200   # a path with one value prints it whole up to this many characters
SKIP_MEMBERS = re.compile(r"(^|/)(\[content_types\]\.xml|theme\d*\.xml|fontTable\.xml|webSettings\.xml|settings\.xml|styles\.xml|numbering\.xml)$|\.rels$", re.I)
NUM_RE = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else str(tag)


def collect(root, max_depth=24):
    """-> (stats, n_elements): stats maps path -> [count, Counter of distinct values, overflowed flag] in order of first appearance."""
    stats, n = {}, 0

    def add(path, val):
        s = stats.get(path)
        if s is None:
            s = stats[path] = [0, Counter(), False, 0, 0.0, None, None]   # count, distinct values, overflow, numeric count, sum, min, max (exact over every value)
        s[0] += 1
        if val in s[1] or len(s[1]) < DISTINCT_CAP:
            s[1][val] += 1
        else:
            s[2] = True
        if NUM_RE.match(val):
            x = float(val)
            s[3] += 1
            s[4] += x
            s[5] = x if s[5] is None else min(s[5], x)
            s[6] = x if s[6] is None else max(s[6], x)
    stack = [(root, "/" + local(root.tag), 0)]
    while stack and n < MAX_ELEMENTS:
        el, path, d = stack.pop()
        n += 1
        text = (el.text or "").strip()
        if text and len(text) <= 400:
            add(path, text)
        for a, v in el.attrib.items():
            v = v.strip()
            if v:
                add(f"{path}@{local(a)}", v)
        if d < max_depth:
            kids = list(el)
            for c in reversed(kids):
                stack.append((c, f"{path}/{local(c.tag)}", d + 1))
    return stats, n


def row(path, s, width=44):
    count, vals, over, ncount, nsum, nmin, nmax = s
    if ncount == count and (len(vals) > 1 or over):
        body = f"numbers {nmin:,.12g} .. {nmax:,.12g}, sum {nsum:,.12g}"
    else:
        top = sorted(vals.items(), key=lambda kv: -kv[1])[:10 if len(vals) <= 60 else 6]
        # a path with one value names something of the file (a head title, an owner): it stays whole up to 200 characters; every cut says its length
        limit = WHOLE if count == 1 else width
        body = "; ".join((v if len(v) <= limit else v[:limit - 1] + f"…(cut, {len(v):,} chars)") + (f" (x{c})" if c > 1 else "") for v, c in top)
        if len(vals) > len(top):
            body += f"; +{len(vals) - len(top)} more"
    return f"{path} [{count:,} value{'s' if count != 1 else ''}, {len(vals)}{'+' if over else ''} distinct]: {body}"


def value_lines(root, max_rows=60):
    """Rows 'path [n values, k distinct]: samples' for the paths that carry text or attribute values; -> (rows, n_elements, n_paths_with_values)."""
    stats, n = collect(root)
    paths = [p for p, s in stats.items() if s[1]]
    order = {p: i for i, p in enumerate(stats)}
    ranked = sorted(paths, key=lambda p: (0 if any(ch.isalpha() for v in stats[p][1] for ch in v[:30]) else 1, order[p]))
    return [row(p, stats[p]) for p in ranked[:max_rows]], n, len(paths)


def emit(look, root, what="XML", pri=88, label=""):
    """Print the value rows in chunks of 12 rows: the first at `pri` (visible in the first print), the rest lower."""
    rows, n, total = value_lines(root)
    if not rows:
        return 0
    cut = any("(cut, " in r for r in rows)
    head = (f"{what} values by element path{label} (every element read, {n:,} elements; text and attribute values, samples by frequency"
            + ("; a cut value says its length, `--grep 'its first words'` prints it whole)" if cut else ")"))
    for k in range(0, len(rows), 12):
        look.line((head if k == 0 else head + " (continued)") + ":\n" + "\n".join(rows[k:k + 12]), pri if k == 0 else max(30, pri - 40), "values")
    if total > len(rows):
        look.line(f"+{total - len(rows)} more paths carry values (not listed).", 20, "values")
    return len(rows)


def member_lines(look, name, data, pri=62):
    """An XML member held in memory (a part of a zip-based format): parse it, even when it sits on one line, and print its values by path."""
    import xml.etree.ElementTree as ET
    import dl_data
    if SKIP_MEMBERS.search(name) or len(data) > 8 << 20:
        return 0
    if dl_data.xml_entity_danger(data):
        return 0
    try:
        root = ET.fromstring(data)
    except Exception:
        return 0
    return emit(look, root, f"XML member {name}", pri, "")
