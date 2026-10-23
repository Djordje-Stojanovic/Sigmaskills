"""SigmaDeepLook: INI-style and other simple key/value config files (fix round 5). Stdlib only.

Every section with its line and key count, and every key with its value, in file order; values of keys that look like secrets
(password, token, secret, api key...) are named by kind and length only. Handles `[section]` headers, `key = value`, `key: value`
and `key value` lines, `;` / `#` / `!` comments, indented continuation lines, keys before the first section, repeated sections
(merged, flagged) and repeated keys (the last one wins, as in most readers; flagged).
"""
import re
from collections import Counter, OrderedDict

import dl_prof as P

SECTION_RE = re.compile(r"^\s*\[\s*([^\]\n]*?)\s*\]\s*(?:[;#].*)?$")
KV_RE = re.compile(r"^\s*([^=:\s][^=:\n]*?)\s*([=:])\s?(.*)$")
SPACE_RE = re.compile(r"^\s*([A-Za-z_][\w.\-]*)\s+(\S.*)$")
SECRET_RE = re.compile(r"(?i)(pass(word|wd)?|pwd|secret|token|api[_.-]?key|private[_.-]?key|credential|auth[_.-]?key|access[_.-]?key|client[_.-]?secret|\bsalt\b)")
NOSEC = "(no section)"
LIST_CHARS = 9000   # the key listing in step 1; past this it continues at a lower priority


ESC_RE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)")
ESC_CHARS = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


def java_unescape(s):
    """A .properties key or value as Java reads it: a backslash-u escape with four hex digits is that character, a backslash with t, n, r
    or f is the control character, any other backslash pair is its second character."""
    if "\\" not in s:
        return s
    out = ESC_RE.sub(lambda m: chr(int(m.group(1)[1:], 16)) if len(m.group(1)) == 5 else ESC_CHARS.get(m.group(1), m.group(1)), s)
    return out.encode("utf-16", "surrogatepass").decode("utf-16", "replace")   # an escaped pair (an emoji) joins; a lone half becomes U+FFFD


def java_split(line):
    """A logical .properties line -> (key, value or None): the key ends at the first '=', ':' or blank that no backslash escapes."""
    s = line.lstrip(" \t\f")
    i = 0
    while i < len(s) and s[i] not in "=: \t\f":
        i += 2 if s[i] == "\\" else 1
    key, rest = s[:i], s[i:].lstrip(" \t\f")
    if rest[:1] in ("=", ":"):
        rest = rest[1:].lstrip(" \t\f")
    elif not rest and i >= len(s):
        return java_unescape(key), None
    return java_unescape(key), java_unescape(rest)


def java_lines(text, st):
    """Physical lines -> [(first line number, logical line)]: a line that ends in an odd number of backslashes goes on with the next
    line, whose leading blanks are dropped (the .properties rule; a comment line never goes on)."""
    out, buf, start = [], None, 0
    for ln, raw in enumerate(text.splitlines(), 1):
        if buf is not None:
            st["continuation lines"] += 1
            raw = raw.lstrip(" \t\f")
        elif raw.strip().startswith(("#", "!")):
            out.append((ln, raw))
            continue
        else:
            start, buf = ln, ""
        if (len(raw) - len(raw.rstrip("\\"))) % 2:
            buf += raw[:-1]
            continue
        out.append((start, buf + raw))
        buf = None
    if buf is not None:
        out.append((start, buf))
    return out


def parse(text, java=False):
    """-> (sections: OrderedDict name -> {'line', 'keys': OrderedDict key -> (value, line)}, stats Counter, dup_keys, dup_sections).
    `java`: a .properties file (backslash line continuation and escapes, no sections, no indented continuation)."""
    secs = OrderedDict()
    st = Counter()
    dup_keys, dup_secs = [], []
    cur = NOSEC
    last = None
    for ln, raw in (java_lines(text, st) if java else enumerate(text.splitlines(), 1)):
        s = raw.strip()
        if not s:
            st["blank lines"] += 1
            last = None
            continue
        if s.startswith((";", "#", "!", "//")):
            st["comment lines"] += 1
            continue
        m = None if java else SECTION_RE.match(raw)
        if m:
            cur = m.group(1) or "(empty name)"
            if cur in secs:
                dup_secs.append((cur, ln))
            else:
                secs[cur] = {"line": ln, "keys": OrderedDict()}
            last = None
            continue
        if last is not None and raw[:1] in (" ", "\t") and not java:   # continuation of the last value
            k = last
            v, kl = secs[cur]["keys"][k]
            secs[cur]["keys"][k] = ((v + "\n" + s) if v else s, kl)
            st["continuation lines"] += 1
            continue
        m = None if java else KV_RE.match(raw)
        if java:
            k, v = java_split(raw)
            if v is None:
                st["keys without a value"] += 1
        elif m:
            k, v = m.group(1).strip(), m.group(3).strip()
        else:
            m = SPACE_RE.match(raw)
            if m:
                k, v = m.group(1), m.group(2).strip()
            else:
                k, v = s, None   # a bare key (allowed by some readers)
                st["keys without a value"] += 1
        sec = secs.setdefault(cur, {"line": ln, "keys": OrderedDict()})
        if k in sec["keys"]:
            dup_keys.append((cur, k, ln))
        sec["keys"][k] = (v, ln)
        last = k
    return secs, st, dup_keys, dup_secs


def kind(v):
    if v is None:
        return "no value"
    s = v.strip().strip('"\'')
    if not s:
        return "empty"
    if s.lower() in ("true", "false", "yes", "no", "on", "off"):
        return "boolean"
    if re.match(r"^[-+]?\d+$", s):
        return "integer"
    if re.match(r"^[-+]?\d*\.\d+$", s):
        return "decimal"
    if re.match(r"^[a-z][\w+.-]*://", s, re.I):
        return "URL"
    if re.match(r"^([A-Za-z]:)?[\\/~.]", s):
        return "path"
    return "text"


def shown(k, v):
    if v is None:
        return k
    if SECRET_RE.search(k) and v.strip():
        return f"{k} = (secret-like value, {len(v)} chars; not printed)"
    return f"{k} = {P.short(v, 120)}"


def look_ini(look):
    raw = open(look.path, "rb").read(16 << 20)
    import dl_delim
    text, enc = dl_delim.sniff_encoding(raw)
    secs, st, dup_keys, dup_secs = parse(text, java=look.path.suffix.lower() == ".properties")
    n_keys = sum(len(s["keys"]) for s in secs.values())
    named = [s for s in secs if s != NOSEC]
    kinds = Counter(kind(v) for s in secs.values() for v, _ in s["keys"].values())
    look.fact("sections", named)
    look.fact("keys", n_keys)
    look.fact("keys_per_section", {k: len(s["keys"]) for k, s in secs.items()})
    look.headline = f"key/value config, {len(named)} sections, {n_keys} keys"
    look.dims = f"{n_keys} keys"
    P.counts(look, [("sections", len(named)), ("keys", n_keys), ("keys before the first section", len(secs[NOSEC]["keys"]) if NOSEC in secs else None),
                    ("comment lines", st["comment lines"]), ("blank lines", st["blank lines"]), ("continuation lines", st["continuation lines"] or None),
                    ("repeated keys", len(dup_keys) or None), ("repeated section headers", len(dup_secs) or None), ("lines", len(text.splitlines()))], 96)
    look.line("Keys per section (in file order, with the line of the header): " + "; ".join(f"[{k}] {len(s['keys'])} (line {s['line']})" if k != NOSEC else f"{k} {len(s['keys'])}" for k, s in secs.items())
              + ". Value kinds: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()), 95, "counts")
    prefix = Counter(k.split(".", 1)[0] for sec in secs.values() for k in sec["keys"] if "." in k.strip("."))
    if prefix and max(prefix.values()) > 1:   # message catalogues and Java configs group keys by namespace: 'error.*', 'menu.*'
        look.line(f"Keys by prefix (the part before the first '.'; {len(prefix)} prefixes, keys per prefix): "
                  + "; ".join(f"{k} {v:,}" for k, v in prefix.most_common(30)) + (f"; +{len(prefix) - 30} more" if len(prefix) > 30 else ""), 94, "counts")
    last_sec = next((n for n in reversed(list(secs)) if secs[n]["keys"]), None)
    if last_sec is not None:
        ks = list(secs[last_sec]["keys"].items())
        look.line(f"Last keys of the file (section {last_sec if last_sec != NOSEC else '(no section)'}; {n_keys:,} keys in all): "
                  + "; ".join(f"{shown(k, v)} (line {ln})" for k, (v, ln) in ks[-3:]) + ".", 93, "tail")
    rows, size = [], 0
    for name, s in secs.items():
        body = "; ".join(shown(k, v) + (f" (line {ln})" if len(s["keys"]) > 12 else "") for k, (v, ln) in s["keys"].items())
        rows.append((f"[{name}]" if name != NOSEC else NOSEC) + f" {len(s['keys'])} keys: " + (body or "(none)"))
    first, rest = [], []
    for r in rows:
        (first if size + len(r) <= LIST_CHARS or not first else rest).append(r)
        size += len(r)
    look.line("Every section with every key = value, in file order:\n" + "\n".join(first), 92, "listing")
    for k in range(0, len(rest), 20):
        look.line("Sections (continued):\n" + "\n".join(rest[k:k + 20]), 40, "listing")
    for sec, k, ln in dup_keys[:8]:
        look.flag("DUPLICATE-KEYS", f"[{sec}] line {ln}", f"key {k!r} set again", "most readers keep the last value; some keep the first")
    for sec, ln in dup_secs[:5]:
        look.flag("DUPLICATE-KEYS", f"line {ln}", f"section [{sec}] opened again", "its keys were merged into the first one")
    secrets = [(s, k) for s, d in secs.items() for k, (v, _) in d["keys"].items() if v and SECRET_RE.search(k)]
    if secrets:
        look.flag("SECRET?", ", ".join(f"[{s}] {k}" for s, k in secrets[:5]), f"{len(secrets)} secret-like value(s), not printed", "ask the human before quoting them")
    P.kv_numbers(look, text.splitlines(), 60)
    look.step("config parse", "stdlib")
