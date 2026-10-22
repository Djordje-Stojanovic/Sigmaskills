"""SigmaDeepLook netCDF classic reader (CDF-1, CDF-2 and CDF-5), standard library only (fix round 8, ticket 83 P0.14b.H8).

A classic netCDF file keeps its dictionary up front: dimensions, global attributes and, per variable, its type, shape, attributes and
the offset of its data. This reader prints all of that and reads every value of every variable (up to a cap per variable) for exact
minimum, maximum, mean, sum, fill-value and NaN counts, plus the first and last values: a question about a dimension length, a unit,
a range or the last time step is answered from the first print. netCDF-4 (HDF5) files are not read here.
"""
import array
import math
import struct
import sys

import dl_prof as P

TYPES = {1: ("byte", "b", 1), 2: ("char", None, 1), 3: ("short", "h", 2), 4: ("int", "i", 4), 5: ("float", "f", 4), 6: ("double", "d", 8),
         7: ("ubyte", "B", 1), 8: ("ushort", "H", 2), 9: ("uint", "I", 4), 10: ("int64", "q", 8), 11: ("uint64", "Q", 8)}
FILL = {1: -127, 3: -32767, 4: -2147483647, 5: 9.969209968386869e36, 6: 9.969209968386869e36}
VALUE_CAP = 5_000_000


class Reader:
    def __init__(self, raw):
        self.b, self.p = raw, 0
        self.ver = raw[3]
        self.big = self.ver == 5

    def u32(self):
        v = struct.unpack_from(">I", self.b, self.p)[0]
        self.p += 4
        return v

    def u64(self):
        v = struct.unpack_from(">Q", self.b, self.p)[0]
        self.p += 8
        return v

    def count(self):
        return self.u64() if self.big else self.u32()

    def name(self):
        n = self.count()
        s = self.b[self.p:self.p + n].decode("utf-8", "replace")
        self.p += (n + 3) & ~3
        return s

    def attrs(self):
        tag, n = self.u32(), self.count()
        out = []
        if tag not in (0, 12):
            raise ValueError("bad attribute list")
        for _ in range(n):
            nm = self.name()
            t = self.u32()
            k = self.count()
            tn, code, size = TYPES.get(t, ("?", None, 1))
            raw = self.b[self.p:self.p + k * size]
            self.p += (k * size + 3) & ~3
            if t == 2:
                val = raw.decode("utf-8", "replace").rstrip("\0")
            elif code:
                a = array.array(code)
                a.frombytes(raw)
                if sys.byteorder == "little":
                    a.byteswap()
                val = a.tolist()
                val = val[0] if len(val) == 1 else val
            else:
                val = raw
            out.append((nm, tn, val))
        return out


def parse(raw):
    """-> dict(version, numrecs, dims [(name, size, unlimited)], attrs, vars [dict]) for a classic netCDF file, or None."""
    if raw[:3] != b"CDF" or raw[3] not in (1, 2, 5):
        return None
    r = Reader(raw)
    r.p = 4
    numrecs = r.count()
    tag, n = r.u32(), r.count()
    dims = []
    for _ in range(n):
        nm = r.name()
        sz = r.count()
        dims.append((nm, sz))
    gat = r.attrs()
    tag, n = r.u32(), r.count()
    vs = []
    for _ in range(n):
        nm = r.name()
        nd = r.count()
        ids = [r.count() for _ in range(nd)]
        at = r.attrs()
        t = r.u32()
        vsize = r.count()
        begin = r.u64() if r.ver >= 2 else r.u32()
        vs.append({"name": nm, "dimids": ids, "attrs": at, "type": t, "vsize": vsize, "begin": begin})
    return {"version": r.ver, "numrecs": numrecs, "dims": dims, "attrs": gat, "vars": vs, "header_end": r.p}


def _stats(vals, fill, nan_ok):
    lo = hi = None
    s, n, nans, fills = 0.0, 0, 0, 0
    for v in vals:
        if v != v:
            nans += 1
            continue
        if fill is not None and v == fill:
            fills += 1
            continue
        if lo is None or v < lo:
            lo = v
        if hi is None or v > hi:
            hi = v
        s += v
        n += 1
    return {"n": n, "lo": lo, "hi": hi, "sum": s, "nan": nans, "fill": fills}


def read_values(raw, nc, v, rec_vars, recsize):
    """All values of variable `v` as an array('x') in native order, up to VALUE_CAP, or None for char data."""
    tn, code, size = TYPES.get(v["type"], ("?", None, 1))
    if code is None:
        return None
    shape = v["shape"]
    nrec = nc["numrecs"]
    per = 1
    for s in (shape[1:] if v["record"] else shape):
        per *= s
    out = array.array(code)
    if v["record"]:
        take = min(nrec, max(1, VALUE_CAP // max(per, 1)))
        chunk = per * size
        for i in range(take):
            at = v["begin"] + i * recsize
            out.frombytes(raw[at:at + chunk])
    else:
        n = min(per, VALUE_CAP)
        out.frombytes(raw[v["begin"]:v["begin"] + n * size])
    if sys.byteorder == "little" and size > 1:
        out.byteswap()
    return out


def look_netcdf(look):
    raw = look.path.read_bytes() if look.size <= (512 << 20) else look.path.read_bytes()[:64 << 20]
    nc = parse(raw)
    if not nc:
        look.line("netCDF classic header could not be read.")
        return
    dims = nc["dims"]
    unlimited = next((i for i, (_, s) in enumerate(dims) if s == 0), None)
    vs = nc["vars"]
    for v in vs:
        v["shape"] = [nc["numrecs"] if d == unlimited else dims[d][1] for d in v["dimids"]]
        v["record"] = bool(v["dimids"]) and v["dimids"][0] == unlimited
    rec_vars = [v for v in vs if v["record"]]
    recsize = sum(v["vsize"] for v in rec_vars)
    if len(rec_vars) == 1 and rec_vars[0]["vsize"] and recsize == rec_vars[0]["vsize"]:
        pass
    ver = {1: "CDF-1 (classic)", 2: "CDF-2 (64-bit offset)", 5: "CDF-5 (64-bit data)"}[nc["version"]]
    look.headline = f"netCDF {ver}: {len(dims)} dimensions, {len(vs)} variables"
    look.dims = " x ".join(f"{n}={s or nc['numrecs']}" for n, s in dims[:4])
    P.counts(look, [("dimensions", len(dims)), ("variables", len(vs)), ("global attributes", len(nc["attrs"])), ("records", nc["numrecs"] if unlimited is not None else None),
                    ("values in all variables", sum(_prod(v["shape"]) for v in vs))], 96, "netCDF counts")
    look.line(f"netCDF {ver}: dimensions " + ", ".join(f"{n} = {nc['numrecs'] if s == 0 else s}" + (" (unlimited)" if s == 0 else "") for n, s in dims) + ".", 95, "structure")
    if nc["attrs"]:
        look.line("Global attributes: " + "; ".join(f"{n} ({t}) = {P.short(v, 80)}" for n, t, v in nc["attrs"][:30]), 94, "structure")
    for k, v in enumerate(vs[:60]):
        tn, code, size = TYPES.get(v["type"], ("?", None, 1))
        shp = " x ".join(f"{dims[d][0]} {n}" for d, n in zip(v["dimids"], v["shape"])) or "scalar"
        total = _prod(v["shape"])
        at = {n: val for n, _t, val in v["attrs"]}
        head = f"Variable {v['name']} ({tn}, {shp}, {total:,} values)"
        if v["attrs"]:
            head += ": " + "; ".join(f"{n} = {P.short(val, 50)}" for n, _t, val in v["attrs"][:10])
        body = ""
        if not look.quick and code and total:
            try:
                vals = read_values(raw, nc, v, rec_vars, recsize)
                fill = at.get("_FillValue", at.get("missing_value", FILL.get(v["type"] if tn in ("byte", "short", "int", "float", "double") else 0)))
                if isinstance(fill, list):
                    fill = fill[0] if fill else None
                if vals is not None and len(vals):
                    st = _stats(vals, fill, tn in ("float", "double"))
                    cut = len(vals) < total
                    body = (f"; read {len(vals):,} of {total:,} values" + (" (PARTIAL: first values only)" if cut else "") + (f"; min {P.fmt(st['lo'])}, max {P.fmt(st['hi'])}, mean {P.fmt(st['sum'] / st['n'])}, sum {P.fmt(st['sum'])}" if st["n"] else "")
                            + (f"; {st['nan']:,} NaN" if st["nan"] else "") + (f"; {st['fill']:,} equal to the fill value {P.fmt(fill)}" if st["fill"] else "")
                            + f"; first {', '.join(P.fmt(x) for x in vals[:4])}; last {P.fmt(vals[-1])}")
                    if v["record"] or len(v["shape"]) == 1:
                        pass
            except Exception as e:
                body = f"; values not read ({type(e).__name__})"
        elif tn == "char" and total and not look.quick:
            at0 = v["begin"]
            body = f"; text starts '{raw[at0:at0 + min(total, 60)].decode('utf-8', 'replace').rstrip(chr(0))}'"
        look.line(head + body + ".", 92 - min(k, 40) // 4, "structure")
    if len(vs) > 60:
        look.line(f"{len(vs) - 60} more variables: " + ", ".join(v["name"] for v in vs[60:200]), 40, "structure")
    look.fact("netcdf_variables", [v["name"] for v in vs][:200])
    look.step("netCDF header and values", "stdlib")


def _prod(shape):
    n = 1
    for s in shape:
        n *= s
    return n
