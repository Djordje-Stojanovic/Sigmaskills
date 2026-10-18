"""SigmaDeepLook: Windows Registry Editor files (.reg, REGEDIT4 and Version 5.00; stdlib only, nothing is imported into a registry).

First print: the keys, the value counts by type, the keys and values the file deletes, and the notable values."""
import re
from collections import Counter

import dl_core as core

REG_HEADER = re.compile(r"(?i)^(windows registry editor version \d+\.\d+|regedit4)\s*$")
NOTABLE_KEYS = re.compile(r"(?i)\\(run|runonce|runservices|runonceex|services|winlogon|image file execution options|policies|appinit_dlls|"
                          r"shell folders|startup|browser helper objects|shellexecutehooks|command|firewallpolicy|terminal server|"
                          r"safeboot|lsa|credential providers)(\\|$)")
NOTABLE_VAL = re.compile(r"(?i)(\.(exe|dll|bat|cmd|ps1|vbs|js|scr|sys|lnk)\b|https?://|\\\\[\w.$-]+\\|powershell|cmd\.exe|rundll32|mshta|wscript|cscript)")
NOTABLE_NAME = re.compile(r"(?i)(disable|enable|^start$|debugger|autorun|autoadminlogon|defaultpassword|proxy|allowremote|fdenytsconnections|enablelua|consentprompt)")
REG_TYPES = {"1": "sz", "2": "expand_sz", "3": "binary", "4": "dword", "7": "multi_sz", "b": "qword", "0": "none", "8": "resource_list"}


def decode_value(spec):
    """The text after `=` of a value line -> (type, value). A `-` deletes the value."""
    spec = spec.strip()
    if spec == "-":
        return "delete", None
    if spec.startswith('"'):
        end = spec.rfind('"')
        return "sz", re.sub(r"\\(.)", r"\1", spec[1:end] if end > 0 else spec[1:])
    m = re.match(r"(?i)dword:([0-9a-f]{1,8})", spec)
    if m:
        return "dword", int(m.group(1), 16)
    m = re.match(r"(?i)hex(?:\(([0-9a-f]+)\))?:(.*)$", spec, re.S)
    if m:
        kind = (m.group(1) or "3").lower()
        raw = bytes(int(x, 16) for x in re.findall(r"[0-9a-fA-F]{1,2}", m.group(2)))
        name = REG_TYPES.get(kind, "hex(" + kind + ")")
        if name in ("expand_sz", "sz", "multi_sz"):
            txt = raw.decode("utf-16-le", "replace").rstrip("\x00")
            return name, txt.replace("\x00", " | ") if name == "multi_sz" else txt
        if name in ("qword", "dword"):
            return name, int.from_bytes(raw[:8 if name == "qword" else 4], "little")
        return name, raw
    return "other", spec[:80]


def parse_reg(text):
    """-> {'version', 'keys': [(path, deleted, [(name, type, value)])], 'deleted_values': [(path, name)]}. Lines that end in a backslash continue."""
    lines, buf = [], None
    for raw in text.replace("\r\n", "\n").split("\n"):
        l = raw.rstrip()
        if buf is not None:
            buf += l.strip()
        else:
            buf = l
        if buf.endswith("\\") and re.match(r'^\s*("(?:[^"\\]|\\.)*"|@)\s*=\s*hex', buf):
            buf = buf[:-1]
            continue
        lines.append(buf)
        buf = None
    if buf is not None:
        lines.append(buf)
    version, keys, dvals, cur = "", [], [], None
    for t in (x.strip() for x in lines):
        if not t or t.startswith(";"):
            continue
        if not version and REG_HEADER.match(t):
            version = t
            continue
        m = re.match(r"^\[(-?)(.*)\]$", t)
        if m:
            cur = (m.group(2), bool(m.group(1)), [])
            keys.append(cur)
            continue
        m = re.match(r'^(@|"((?:[^"\\]|\\.)*)")\s*=\s*(.*)$', t)
        if m and cur is not None:
            name = "(Default)" if m.group(1) == "@" else re.sub(r"\\(.)", r"\1", m.group(2))
            typ, val = decode_value(m.group(3))
            if typ == "delete":
                dvals.append((cur[0], name))
            else:
                cur[2].append((name, typ, val))
    return {"version": version, "keys": keys, "deleted_values": dvals}


def show(v):
    return v.hex() if isinstance(v, bytes) else str(v)


def look_reg(look):
    text, enc = core.decode_text(look.path.read_bytes()[: 64 << 20])
    r = parse_reg(text or "")
    keys, dvals = r["keys"], r["deleted_values"]
    nvals = sum(len(k[2]) for k in keys)
    dkeys = [k[0] for k in keys if k[1]]
    types = Counter(v[1] for k in keys for v in k[2])
    hives = Counter(k[0].split("\\")[0] for k in keys)
    look.headline = f"Windows registry export ({r['version'] or 'no header'}): {len(keys)} keys, {nvals} values" + (f", {len(dkeys)} deleted keys" if dkeys else "")
    look.fact("keys", len(keys))
    look.fact("values", nvals)
    look.line(f"Windows registry file ({r['version'] or 'header missing'}, {enc}): {len(keys)} keys ({len(dkeys)} marked for deletion), {nvals} values set, "
              f"{len(dvals)} values marked for deletion; value types {dict(types.most_common())}; hives {dict(hives.most_common(6))}.", 97)
    if dkeys or dvals:
        look.flag("REG-DELETES", "registry file", f"{len(dkeys)} key(s) and {len(dvals)} value(s) deleted when this file is imported", "importing it removes data")
        parts = [f"delete key {k}" for k in dkeys[:15]] + [f"delete value {n} in {k}" for k, n in dvals[:15]]
        more = (f"; +{len(dkeys) - 15} more keys" if len(dkeys) > 15 else "") + (f"; +{len(dvals) - 15} more values" if len(dvals) > 15 else "")
        look.line("Deletions on import: " + "; ".join(parts) + more + ".", 96)
    nota = []
    for path, deleted, vals in keys:
        if deleted:
            continue
        keyhit = bool(NOTABLE_KEYS.search(path))
        for n, t, v in vals:
            if (keyhit or NOTABLE_NAME.search(n) or (isinstance(v, str) and NOTABLE_VAL.search(v))) and len(nota) < 400:
                nota.append(f"{path.split(chr(92), 1)[-1][-70:]} | {n} = {t}:{show(v)[:90]}")
    if nota:
        look.line(f"Notable values ({len(nota)}; startup, service, policy and security keys, program paths, URLs, enable/disable switches): " + "; ".join(nota[:12])
                  + (f"; +{len(nota) - 12} more in keys.txt" if len(nota) > 12 else "") + ".", 94)
    body = []
    for p, d, vs in keys:
        body.append(("-" if d else "") + p)
        body += [f"    {n} = {t}:{show(v)[:200]}" for n, t, v in vs]
    look.write_text("keys.txt", "\n".join(body), "every key with its values")
    look.step("registry keys, values, deletions", "stdlib")
