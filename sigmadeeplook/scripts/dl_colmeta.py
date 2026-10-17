"""SigmaDeepLook: file-level key/value metadata of columnar and container formats (fix round 5). Stdlib only.

Parquet keeps a list of key/value pairs in its footer (custom keys, `pandas`, `ARROW:schema`, Spark and Delta keys) next to
`created_by`; Arrow IPC and Feather keep them on the schema and on each field; Avro keeps them in the file header. People ask
for those values (who produced the file, which pipeline version, what the source system was), so every pair is printed: plain
values in full, JSON values as their keys, base64 blobs by kind and size.

The Parquet footer is read here with a small Thrift compact-protocol decoder, so the row count, the schema, the row groups
and the metadata are known even without pyarrow or duckdb.
"""
import json
import re
import struct


# ---------------------------------------------------------------- Thrift compact protocol (read only, generic)
class Compact:
    def __init__(self, b, i=0):
        self.b, self.i = b, i

    def byte(self):
        v = self.b[self.i]
        self.i += 1
        return v

    def varint(self):
        shift = out = 0
        while True:
            x = self.byte()
            out |= (x & 0x7F) << shift
            if not x & 0x80:
                return out
            shift += 7

    def zigzag(self):
        n = self.varint()
        return (n >> 1) ^ -(n & 1)

    def binary(self):
        n = self.varint()
        v = self.b[self.i:self.i + n]
        self.i += n
        return v

    def value(self, t):
        if t in (1, 2):
            return t == 1
        if t == 3:
            v = self.byte()
            return v - 256 if v > 127 else v
        if t in (4, 5, 6):
            return self.zigzag()
        if t == 7:
            v = struct.unpack("<d", self.b[self.i:self.i + 8])[0]
            self.i += 8
            return v
        if t == 8:
            return self.binary()
        if t in (9, 10):
            return self.list()
        if t == 11:
            n = self.varint()
            if not n:
                return {}
            kv = self.byte()
            return {self.value(kv >> 4): self.value(kv & 0x0F) for _ in range(n)}
        if t == 12:
            return self.struct()
        raise ValueError(f"thrift type {t}")

    def list(self):
        h = self.byte()
        n, et = h >> 4, h & 0x0F
        if n == 15:
            n = self.varint()
        if et in (1, 2):   # booleans in a list are one byte each
            return [self.byte() == 1 for _ in range(n)]
        return [self.value(et) for _ in range(n)]

    def struct(self):
        out, last = {}, 0
        while True:
            h = self.byte()
            if h == 0:
                return out
            delta, t = h >> 4, h & 0x0F
            fid = last + delta if delta else self.zigzag()
            last = fid
            out[fid] = self.value(t)


PHYS = {0: "BOOLEAN", 1: "INT32", 2: "INT64", 3: "INT96", 4: "FLOAT", 5: "DOUBLE", 6: "BYTE_ARRAY", 7: "FIXED_LEN_BYTE_ARRAY"}
CONV = {0: "UTF8", 1: "MAP", 3: "LIST", 4: "ENUM", 5: "DECIMAL", 6: "DATE", 7: "TIME_MILLIS", 9: "TIMESTAMP_MILLIS", 10: "TIMESTAMP_MICROS", 19: "JSON"}
CODEC = {0: "uncompressed", 1: "snappy", 2: "gzip", 3: "lzo", 4: "brotli", 5: "lz4", 6: "zstd", 7: "lz4_raw"}


def _s(b):
    return b.decode("utf-8", "replace") if isinstance(b, (bytes, bytearray)) else str(b)


def parquet_footer(path):
    """-> dict(version, rows, created_by, kv {key: value}, schema [(name, type, repetition)], row_groups [(rows, bytes)], codecs) or None."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size < 12:
            return None
        f.seek(size - 8)
        tail = f.read(8)
        if tail[4:] != b"PAR1":
            return None
        n = struct.unpack("<I", tail[:4])[0]
        if n > size - 8 or n > 256 << 20:
            return None
        f.seek(size - 8 - n)
        b = f.read(n)
    md = Compact(b).struct()
    schema = []
    for el in md.get(2, [])[1:]:   # the first element is the root
        t = PHYS.get(el.get(1)) if 1 in el else "group"
        if 6 in el and el[6] in CONV:
            t += f"/{CONV[el[6]]}"
        schema.append((_s(el.get(4, b"?")), t, {0: "required", 1: "optional", 2: "repeated"}.get(el.get(3), "")))
    rgs, codecs = [], set()
    for rg in md.get(4, []):
        rgs.append((rg.get(3, 0), rg.get(2, 0)))
        for cc in rg.get(1, []):
            m = cc.get(3) or {}
            if 4 in m:
                codecs.add(CODEC.get(m[4], str(m[4])))
    kv = {}
    for item in md.get(5, []) or []:
        kv[_s(item.get(1, b""))] = _s(item.get(2, b""))
    return {"version": md.get(1), "rows": md.get(3), "created_by": _s(md.get(6, b"")) or None, "kv": kv, "schema": schema, "row_groups": rgs, "codecs": sorted(codecs)}


def describe_value(k, v, full=200):
    """A metadata value for people: plain text in full (up to `full` chars), JSON by its keys, base64 by kind and size."""
    v = v if isinstance(v, str) else _s(v)
    s = v.strip()
    if s[:1] in "{[":
        try:
            j = json.loads(s)
            if isinstance(j, dict):
                bits = []
                for kk, vv in list(j.items())[:12]:
                    bits.append(f"{kk}: {vv if not isinstance(vv, (dict, list)) else ('object' if isinstance(vv, dict) else f'list of {len(vv)}')}"[:80])
                return f"JSON object ({len(s):,} chars) with " + ", ".join(bits)
            return f"JSON list of {len(j)} ({len(s):,} chars)"
        except ValueError:
            pass
    if len(s) > 120 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", s):
        return f"base64 data ({len(s):,} chars)" + (", the serialised Arrow schema" if k == "ARROW:schema" else "")
    return s if len(s) <= full else s[:full - 1] + "…"


def kv_line(kv, what):
    if not kv:
        return f"{what}: none (no custom key/value pairs)."
    return f"{what} ({len(kv)} keys): " + "; ".join(f"{k} = {describe_value(k, v)}" for k, v in kv.items())
