"""SigmaDeepLook SPSS .sav reader, standard library only (fix round 8, ticket 83 P0.14b.H8).

A .sav file keeps its dictionary up front: file header, one record per variable (name, label, type, width, formats, missing values),
value labels, documents and extension records (long names, very long strings). The cases follow, uncompressed or in SPSS bytecode
compression. This reader prints the header and the dictionary in full (every variable label and every value label), reads every case
and sends the rows through the shared exact profiler, so counts, distinct values, ranges and the last row are in the first print.
ZLIB-compressed files (compression 2) are named as not decoded.
"""
import struct
import time

import dl_prof as P

short = P.short


def _text(b):
    return b.decode("utf-8", "replace").rstrip("\0 ")


LOW, HIGH = -1.7976931348623157e308, 1.7976931348623157e308


def miss_spec(nmiss, miss):
    """The user-defined missing values of one variable -> {'codes': [...], 'range': (lo, hi) or None} or None. nmiss 1..3: that many codes; -2: a range;
    -3: a range and one more code (SPSS system file, variable record)."""
    if not nmiss or not miss:
        return None
    if nmiss > 0:
        return {"codes": list(miss), "range": None}
    if nmiss == -2 and len(miss) >= 2:
        return {"codes": [], "range": (miss[0], miss[1])}
    if nmiss == -3 and len(miss) >= 3:
        return {"codes": [miss[2]], "range": (miss[0], miss[1])}
    return None


def is_missing(spec, x):
    """True when the value is one the file declares missing (never for the system-missing None: that is missing already)."""
    if spec is None or x is None:
        return False
    if x in spec["codes"]:
        return True
    rg = spec["range"]
    return rg is not None and isinstance(x, (int, float)) and rg[0] <= x <= rg[1]


def _num(x):
    return str(int(x)) if x == int(x) and abs(x) < 1e15 else f"{x:g}"


def miss_text(spec):
    """'998, 999', '-9 to -1 and 99999', "'UNK'": the declared codes as a reader writes them."""
    parts = []
    if spec["range"] is not None:
        lo, hi = spec["range"]
        parts.append(f"{'lowest' if lo <= LOW else _num(lo)} to {'highest' if hi >= HIGH else _num(hi)}")
    for c in spec["codes"]:
        parts.append(_num(c) if isinstance(c, (int, float)) else repr(c))
    return (parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]) if spec["range"] is not None else ", ".join(parts)


class Sav:
    def __init__(self, raw):
        self.raw = raw
        self.e = "<"
        self.vars, self.labels, self.docs, self.ext = [], {}, [], {}
        self.long_names, self.p = {}, 0
        self.mask = False   # True: a value the file declares missing is read as None (fix round 15)
        self.mcount = {}    # variable number -> cases that hold a declared missing value

    def i32(self, at=None):
        at = self.p if at is None else at
        return struct.unpack_from(self.e + "i", self.raw, at)[0]

    def parse(self):
        r = self.raw
        if r[:4] not in (b"$FL2", b"$FL3") or len(r) < 176:
            raise ValueError("not an SPSS system file")
        self.magic = r[:4].decode()
        self.product = _text(r[4:64])
        layout = struct.unpack_from("<i", r, 64)[0]
        if layout not in (2, 3):
            self.e = ">"
            layout = struct.unpack_from(">i", r, 64)[0]
        self.layout = layout
        self.case_size, self.compression, self.weight, self.ncases = struct.unpack_from(self.e + "4i", r, 68)
        self.bias = struct.unpack_from(self.e + "d", r, 84)[0]
        self.date, self.time, self.label = _text(r[92:101]), _text(r[101:109]), _text(r[109:173])
        self.p = 176
        slot = 0
        pending_labels = []
        while self.p + 4 <= len(r):
            t = self.i32()
            if t == 2:
                typ, has_label, nmiss, pf, wf = struct.unpack_from(self.e + "5i", r, self.p + 4)
                name = _text(r[self.p + 24:self.p + 32])
                self.p += 32
                label = ""
                if has_label:
                    n = self.i32()
                    label = _text(r[self.p + 4:self.p + 4 + n])
                    self.p += 4 + ((n + 3) // 4) * 4
                miss = []
                if nmiss:   # numeric: doubles; string: 8 bytes of text each
                    for k in range(abs(nmiss)):
                        raw8 = r[self.p + 8 * k:self.p + 8 * k + 8]
                        miss.append(struct.unpack(self.e + "d", raw8)[0] if typ == 0 else _text(raw8))
                self.p += 8 * abs(nmiss)
                if typ == -1:
                    slot += 1
                    continue
                self.vars.append({"name": name, "type": typ, "label": label, "print": pf, "write": wf, "missing": miss, "slot": slot, "nmiss": nmiss, "miss_spec": miss_spec(nmiss, miss)})
                slot += 1
            elif t == 3:
                n = self.i32(self.p + 4)
                self.p += 8
                pairs = []
                for _ in range(n):
                    v = r[self.p:self.p + 8]
                    ln = r[self.p + 8]
                    pairs.append((v, _text(r[self.p + 9:self.p + 9 + ln])))
                    self.p += 8 + (((1 + ln) + 7) // 8) * 8
                pending_labels.append(pairs)
            elif t == 4:
                n = self.i32(self.p + 4)
                idx = [struct.unpack_from(self.e + "i", r, self.p + 8 + 4 * k)[0] for k in range(n)]
                self.p += 8 + 4 * n
                pairs = pending_labels.pop() if pending_labels else []
                for i in idx:
                    self.labels.setdefault(i - 1, []).extend(pairs)
            elif t == 6:
                n = self.i32(self.p + 4)
                self.docs = [_text(r[self.p + 8 + 80 * k:self.p + 88 + 80 * k]) for k in range(n)]
                self.p += 8 + 80 * n
            elif t == 7:
                sub, size, count = struct.unpack_from(self.e + "3i", r, self.p + 4)
                data = r[self.p + 16:self.p + 16 + size * count]
                self.ext[sub] = data
                self.p += 16 + size * count
            elif t == 999:
                self.p += 8
                break
            else:
                raise ValueError(f"unknown record type {t} at {self.p}")
        ln = self.ext.get(13)
        if ln:
            for pair in ln.decode("utf-8", "replace").split("\t"):
                k, _, v = pair.partition("=")
                if v:
                    self.long_names[k.strip()] = v.strip()
        for v in self.vars:
            v["long"] = self.long_names.get(v["name"], v["name"])
        # width in slots of each variable
        for k, v in enumerate(self.vars):
            nxt = self.vars[k + 1]["slot"] if k + 1 < len(self.vars) else self.case_size
            v["slots"] = nxt - v["slot"]
        return self

    def decoded_labels(self, k):
        """Value labels of variable number k (its labels are filed by the dictionary index of its first record)."""
        v = self.vars[k]
        out = []
        for raw, lab in self.labels.get(v["slot"], []):
            if v["type"] == 0:
                x = struct.unpack(self.e + "d", raw)[0]
                out.append((int(x) if x == int(x) else x, lab))
            else:
                out.append((_text(raw), lab))
        return out

    def cases(self):
        """Yield one tuple of values per case (numbers as float, None for system-missing, strings stripped). With `mask` set, a value the file declares
        missing (user-defined) is None too; either way `mcount` counts the cases that hold one."""
        self._decl = self._declared()
        self.mcount = {}   # every pass over the cases counts afresh
        r, cs = self.raw, self.case_size
        if self.compression == 0:
            at = self.p
            while at + 8 * cs <= len(r):
                yield self._case([r[at + 8 * k:at + 8 * k + 8] for k in range(cs)])
                at += 8 * cs
            return
        if self.compression != 1:
            raise ValueError("compression 2 (ZLIB) is not decoded")
        at, slots = self.p, []
        sysmis = struct.unpack(self.e + "d", self.ext[4][:8])[0] if 4 in self.ext and len(self.ext[4]) >= 8 else -1.7976931348623157e308
        pack = struct.Struct(self.e + "d").pack
        while at + 8 <= len(r):
            cmds = r[at:at + 8]
            at += 8
            for c in cmds:
                if c == 0:
                    continue
                if c == 252:
                    return
                if c == 253:
                    slots.append(r[at:at + 8])
                    at += 8
                elif c == 254:
                    slots.append(b"        ")
                elif c == 255:
                    slots.append(pack(sysmis))
                else:
                    slots.append(pack(c - self.bias))
                while len(slots) >= cs:
                    yield self._case(slots[:cs])
                    del slots[:cs]

    def _declared(self):
        return [(k, v["miss_spec"]) for k, v in enumerate(self.vars) if v.get("miss_spec")]

    def _case(self, slots):
        out = []
        for v in self.vars:
            blk = slots[v["slot"]:v["slot"] + v["slots"]]
            if v["type"] == 0:
                x = struct.unpack(self.e + "d", blk[0])[0]
                out.append(None if x <= -1.7976931348623157e308 else (int(x) if x == int(x) and abs(x) < 1e15 else x))
            else:
                out.append(b"".join(blk)[:v["type"]].decode("utf-8", "replace").rstrip(" \0"))
        for k, spec in self._decl:
            if is_missing(spec, out[k]):
                self.mcount[k] = self.mcount.get(k, 0) + 1
                if self.mask:
                    out[k] = None
        return tuple(out)


def ask_source(path, keep_missing=False):
    """What --ask reads from a .sav file: -> (variable names, cases declared or None, iterator of (case number, values)), or None when the cases
    cannot be decoded (ZLIB). The same dictionary and case reader as the look; the iterator is lazy, so a lookup need not hold 700,000 cases."""
    size = path.stat().st_size
    raw = path.read_bytes() if size <= (512 << 20) else path.read_bytes()[:128 << 20]
    s = Sav(raw).parse()
    if s.compression == 2:
        return None
    seen = {}
    names = []
    for k, v in enumerate(s.vars):
        names.append(v["long"] if v["long"] not in seen else f"{v['long']}_{k}")
        seen[v["long"]] = 1
    s.mask = not keep_missing   # fix round 15: a declared missing value is not a value unless the question asks for the raw values
    miss = {}
    for k, v in enumerate(s.vars):
        if v.get("miss_spec"):
            miss[names[k]] = {"text": miss_text(v["miss_spec"]), "spec": v["miss_spec"], "k": k, "sav": s}
    return names, (s.ncases if s.ncases >= 0 else None), enumerate(s.cases(), 1), miss


def look_sav(look):
    raw = look.path.read_bytes() if look.size <= (512 << 20) else look.path.read_bytes()[:128 << 20]
    try:
        s = Sav(raw).parse()
    except (ValueError, struct.error) as e:
        look.flag("CORRUPT", "sav", f"{type(e).__name__}: {e}"[:120], "the SPSS dictionary could not be read")
        return
    nv = len(s.vars)
    kinds = {"numeric": sum(1 for v in s.vars if v["type"] == 0), "string": sum(1 for v in s.vars if v["type"] > 0)}
    labelled = sum(1 for v in s.vars if v["slot"] in s.labels)
    nlab = sum(len(s.labels.get(v["slot"], [])) for v in s.vars)
    ncomp = {0: "none", 1: "bytecode", 2: "ZLIB"}.get(s.compression, str(s.compression))
    look.headline = f"SPSS data file: {nv} variables" + (f", {s.ncases:,} cases" if s.ncases >= 0 else "")
    look.dims = f"{max(s.ncases, 0):,} rows"
    P.counts(look, [("cases", s.ncases if s.ncases >= 0 else None), ("variables", nv), ("numeric variables", kinds["numeric"]), ("string variables", kinds["string"]),
                    ("variables with value labels", labelled), ("value labels", nlab), ("document lines", len(s.docs) or None)], 96, "SPSS counts")
    look.line(f"SPSS system file {s.magic}: product '{s.product}', {'little' if s.e == '<' else 'big'}-endian, layout {s.layout}, {s.case_size} slots per case, compression {ncomp}, "
              f"weight variable {(s.vars[s.weight - 1]['long'] if 0 < s.weight <= nv else 'none')}, {s.ncases if s.ncases >= 0 else 'unknown number of'} cases, created {s.date} {s.time}"
              + (f", file label '{s.label}'" if s.label else "") + ".", 95, "structure")
    names = "; ".join(f"{v['long']} ({'numeric' if v['type'] == 0 else 'string ' + str(v['type'])}" + (f", label '{short(v['label'], 70)}'" if v["label"] else "") + (f", declared missing: {miss_text(v['miss_spec'])}" if v.get("miss_spec") else "") + ")" for v in s.vars)
    look.line("Variables (in file order): " + names, 93, "structure")
    if s.labels:
        parts = []
        for k, v in enumerate(s.vars):
            if v["slot"] in s.labels:
                parts.append(f"{v['long']}: " + "; ".join(f"{a} = {short(b, 60)}" for a, b in s.decoded_labels(k)))
        look.line(f"Value labels ({labelled} variables, {nlab} labels): " + " | ".join(parts), 92, "structure")
    import dl_varmeta   # fix round 15: print formats and value labels kept for --ask "format of variable X" / "value labels of X"
    dl_varmeta.attach(look, dl_varmeta.sav_meta(s), labels=False)
    if s.docs:
        look.line("Documents: " + " | ".join(short(d, 100) for d in s.docs[:10]), 60, "structure")
    declared = [(k, v) for k, v in enumerate(s.vars) if v.get("miss_spec")]

    def declared_line(counts):
        return ("Declared missing values (user-defined; --ask and the profile below leave them out, like system-missing values; --ask keeps them when the question asks for the raw values): "
                + "; ".join(f"{v['long']}: {miss_text(v['miss_spec'])}" + (f" ({counts.get(k, 0):,} cases)" if counts is not None else "") for k, v in declared) + ".")
    if look.quick:
        if declared:
            look.line(declared_line(None), 94, "structure")
        return
    if s.compression == 2:
        if declared:
            look.line(declared_line(None), 94, "structure")
        look.skip("the cases (ZLIB-compressed .sav)", "compression 2 is not decoded by the standard library", "pyreadstat")
        return
    names = [v["long"] if v["long"] not in {w["long"] for w in s.vars[:k]} else f"{v['long']}_{k}" for k, v in enumerate(s.vars)]
    import dl_data as D
    t0 = time.time()
    state = {"n": 0}
    s.mask = True   # a value the file declares missing is not a value: the profile leaves it out

    def rows():
        for i, c in enumerate(s.cases(), 1):
            state["n"] = i
            yield i, c
    try:
        D.table_profile(look, "Cases", names, rows, "case", s.ncases if s.ncases >= 0 else None, 84, 28)
    except ValueError as e:
        look.flag("CORRUPT", "sav", str(e)[:120], "the cases could not be decoded")
    n = state["n"]
    if declared:
        look.line(declared_line(s.mcount), 94, "structure")
    if s.ncases >= 0 and n != s.ncases:
        look.flag("COUNT-MISMATCH", "sav", f"header says {s.ncases:,} cases, {n:,} were decoded", "a damaged file, or a case layout this reader does not follow (very long strings)")
    look.fact("rows", n)
    look.step("SPSS dictionary and cases", "stdlib")
