"""SigmaDeepLook: dBASE / FoxPro tables (.dbf), a legacy binary table format with a header that names every field.

The 32-byte header holds the record count, the header length and the record length; 32-byte field descriptors follow (name, type, length,
decimals) up to a 0x0D byte; fixed-size records follow, each starting with a deletion flag. Detection is by structure, not by extension:
the descriptors must end in 0x0D and their lengths must add up to the record length. The rows then go through the same exact profiler as
a CSV (type mix, distinct values, ranges, sums, group-by, top rows). Memo text (.dbt/.fpt) is not read: a memo field shows its block number.
"""
import csv
import datetime as dt
import struct

import dl_util as U

VERSIONS = {0x02: "FoxBase", 0x03: "dBASE III", 0x04: "dBASE IV", 0x05: "dBASE 5", 0x30: "Visual FoxPro", 0x31: "Visual FoxPro (autoincrement)",
            0x32: "Visual FoxPro (varchar)", 0x43: "dBASE IV SQL table", 0x63: "dBASE IV SQL system", 0x83: "dBASE III with memo", 0x8B: "dBASE IV with memo",
            0x8E: "dBASE IV SQL with memo", 0xCB: "dBASE IV SQL table with memo", 0xF5: "FoxPro 2 with memo", 0xFB: "FoxBase"}
FIELD_TYPES = {"C": "text", "N": "number", "F": "float", "D": "date", "L": "logical", "M": "memo", "G": "general", "P": "picture", "I": "int32", "B": "double", "Y": "currency",
               "T": "datetime", "O": "double", "+": "autoincrement", "@": "timestamp", "V": "varchar", "Q": "varbinary", "W": "blob", "0": "null flags"}
LANGUAGE = {0x01: "cp437", 0x02: "cp850", 0x03: "cp1252", 0x08: "cp865", 0x09: "cp437", 0x0A: "cp850", 0x0B: "cp437", 0x0D: "cp437", 0x0E: "cp850", 0x0F: "cp437", 0x10: "cp850",
            0x11: "cp437", 0x12: "cp850", 0x13: "cp932", 0x14: "cp850", 0x15: "cp437", 0x16: "cp850", 0x17: "cp865", 0x18: "cp437", 0x19: "cp437", 0x1A: "cp850", 0x1B: "cp437",
            0x1C: "cp863", 0x1D: "cp850", 0x1F: "cp852", 0x22: "cp852", 0x23: "cp852", 0x24: "cp860", 0x25: "cp850", 0x26: "cp866", 0x37: "cp850", 0x40: "cp852", 0x4D: "cp936",
            0x4E: "cp949", 0x4F: "cp950", 0x50: "cp874", 0x57: "cp1252", 0x58: "cp1252", 0x59: "cp1252", 0x64: "cp852", 0x65: "cp866", 0x66: "cp865", 0x67: "cp861", 0x6A: "cp737",
            0x6B: "cp857", 0x78: "cp950", 0x79: "cp949", 0x7A: "cp936", 0x7B: "cp932", 0x7C: "cp874", 0x86: "cp737", 0x87: "cp852", 0x88: "cp857", 0xC8: "cp1250", 0xC9: "cp1251",
            0xCA: "cp1254", 0xCB: "cp1253", 0xCC: "cp1257"}
MAX_ROWS_COPY = 5_000_000


def parse_header(h, size=None):
    """-> dict(version, nrec, header_len, rec_len, fields[(name, type, length, dec)], updated, lang, flags) or None when the bytes are not a dBASE header."""
    if len(h) < 66 or h[0] not in VERSIONS:
        return None
    nrec, hlen, rlen = struct.unpack_from("<IHH", h, 4)
    if hlen < 65 or rlen < 2 or hlen > len(h) + 65535:
        return None
    fields, pos, offset = [], 32, 1
    while True:
        if pos >= min(len(h), hlen):
            return None
        if h[pos] == 0x0D:
            break
        if pos + 32 > len(h):
            return None
        raw = h[pos:pos + 32]
        name = raw[:11].split(b"\0")[0]
        typ = chr(raw[11])
        length, dec = raw[16], raw[17]
        if not name or not all(32 < c < 127 for c in name) or typ not in FIELD_TYPES:
            return None
        fields.append((name.decode("ascii"), typ, length, dec, offset))
        offset += length
        pos += 32
    if h[pos:pos + 1] != b"\x0d" or not fields or offset != rlen:
        return None
    yy, mm, dd = h[1], h[2], h[3]
    updated = None
    if 1 <= mm <= 12 and 1 <= dd <= 31:
        updated = f"{1900 + yy if (yy >= 80 or yy >= 100) else 2000 + yy}-{mm:02d}-{dd:02d}"
    return {"version": h[0], "nrec": nrec, "header_len": hlen, "rec_len": rlen, "fields": fields, "updated": updated, "lang": h[29], "flags": h[28]}


def looks_dbf(h, size):
    """True when the head parses as a dBASE header whose record count and sizes fit the file (a truncated file still counts)."""
    d = parse_header(h, size)
    if not d:
        return False
    return size >= d["header_len"]


def guess_encoding(d, sample):
    enc = LANGUAGE.get(d["lang"])
    hi = [c for c in sample if c > 127]
    if enc is None or (enc == "cp1252" and hi):
        try:
            sample.decode("utf-8")
            if hi:
                return "utf-8"
        except UnicodeDecodeError:
            pass
    if enc:
        return enc
    if not hi:
        return "ascii"
    import dl_delim
    return dl_delim.guess_codepage(sample)


def julian(day, ms=0):
    try:
        return (dt.datetime(1, 1, 1) + dt.timedelta(days=day - 1721426, milliseconds=ms)).strftime("%Y-%m-%d %H:%M:%S" if ms else "%Y-%m-%d")
    except (OverflowError, ValueError):
        return None


def decode_field(raw, typ, dec, enc):
    if typ in "CVQ":
        return raw.rstrip(b" \x00").decode(enc, "replace").strip()
    if typ in "NF":
        s = raw.strip(b" \x00").decode("ascii", "replace")
        if not s or set(s) <= {"*", "?"}:
            return None
        try:
            return int(s) if dec == 0 and "." not in s and "e" not in s.lower() else float(s)
        except ValueError:
            return s
    if typ == "D":
        s = raw.decode("ascii", "replace").strip()
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() and s != "00000000" else None
    if typ == "L":
        c = raw[:1].upper()
        return True if c in (b"T", b"Y") else False if c in (b"F", b"N") else None
    if typ in "MGP":
        s = raw.strip(b" \x00")
        if len(raw) == 4 and len(s) <= 4 and not s.isdigit():
            n = struct.unpack("<I", raw)[0]
            return n or None
        return int(s) if s.isdigit() else None
    if typ in "I+" and len(raw) == 4:
        return struct.unpack("<i", raw)[0]
    if typ in "BO" and len(raw) == 8:
        return struct.unpack("<d", raw)[0]
    if typ == "Y" and len(raw) == 8:
        return struct.unpack("<q", raw)[0] / 10000
    if typ in "T@" and len(raw) == 8:
        day, ms = struct.unpack("<ii", raw)
        return julian(day, ms) if day else None
    return raw.hex()


def read_rows(path, d, enc, flagged=None):
    """Yield (record number from 1, [values]) for every record that is not deleted; flagged (a dict) counts deleted records and what ended the data."""
    names = [f for f in d["fields"] if f[1] != "0"]
    with open(path, "rb") as f:
        f.seek(d["header_len"])
        rlen = d["rec_len"]
        for k in range(1, d["nrec"] + 1):
            rec = f.read(rlen)
            if len(rec) < rlen or rec[:1] == b"\x1a":
                if flagged is not None:
                    flagged["ended"] = k - 1
                return
            if rec[:1] == b"*":
                if flagged is not None:
                    flagged["deleted"] = flagged.get("deleted", 0) + 1
                continue
            yield k, [decode_field(rec[off:off + ln], typ, dec, enc) for (_n, typ, ln, dec, off) in names]


def look_dbf(look):
    import dl_data as D
    import dl_prof as P
    with open(look.path, "rb") as f:
        h = f.read(65536)
    d = parse_header(h, look.size)
    if not d:
        look.flag("DBF-HEADER", "file", "not a readable dBASE header", "treated as unknown binary")
        look.exit_code = 3
        return
    fields = [f for f in d["fields"] if f[1] != "0"]
    names = [f[0] for f in fields]
    with open(look.path, "rb") as f:
        f.seek(d["header_len"])
        body = f.read(min(1 << 20, max(0, d["nrec"]) * d["rec_len"]))
    cols = [(off, ln) for (_n, typ, ln, _d, off) in fields if typ in "CVM"]
    sample = b"".join(body[i + off:i + off + ln] for i in range(0, len(body) - d["rec_len"] + 1, d["rec_len"]) for off, ln in cols)[:300000]
    enc = guess_encoding(d, sample)
    expect = d["header_len"] + d["nrec"] * d["rec_len"]
    ver = VERSIONS[d["version"]]
    look.fact("dbf_version", ver)
    look.fact("rows", d["nrec"])
    look.fact("columns", len(names))
    look.fact("column_names", names)
    look.fact("encoding", enc)
    look.headline = f"{ver} table (.dbf), {d['nrec']:,} records x {len(names)} fields"
    look.dims = f"{U.compact(d['nrec'])} rows"
    look.line(f"{ver} table: {d['nrec']:,} records of {d['rec_len']} bytes, {len(names)} fields, header {d['header_len']} bytes, last updated {d['updated'] or 'unknown'}, "
              f"text encoding {enc}" + (f" (language driver 0x{d['lang']:02x})" if d["lang"] else " (no language driver in the header)") + ".", 93)
    look.line("Fields (name type length[,decimals]): " + "; ".join(f"{n} {t}{ln}" + (f",{dc}" if dc else "") + f" ({FIELD_TYPES[t]})" for n, t, ln, dc, _o in fields[:200])
              + (f"; {len(fields) - 200} more" if len(fields) > 200 else "") + ".", 92)
    P.counts(look, [("records (header)", d["nrec"]), ("fields", len(names)), ("record length (bytes)", d["rec_len"]), ("memo fields", sum(1 for f in fields if f[1] in "MGP") or None)], 96)
    if size_gap := look.size - expect:
        if size_gap < 0:
            look.flag("TRUNCATED", "file", f"{look.size:,} bytes, the header promises {expect:,}", f"about {(-size_gap) // max(1, d['rec_len']):,} records are missing at the end")
        elif size_gap > 1:
            look.flag("TRAILING-BYTES", "file", f"{size_gap:,} bytes after the last record", "the record count in the header may be stale, or extra data follows")
    if any(f[1] in "MGP" for f in fields):
        look.flag("MEMO-FIELDS", "file", ", ".join(f[0] for f in fields if f[1] in "MGP")[:80], "a memo field holds a block number; its text is in the .dbt / .fpt file next to this one, which is not read")
    if look.quick:
        look.skip("record values (profile, sums, rows)", "skipped at the quick tier: run again with --tier standard", None, "")
        look.step("dbf header", "stdlib struct")
        return
    state = {}

    def rows():
        state.clear()
        return read_rows(look.path, d, enc, state)
    D.table_profile(look, "Records", names, rows, "record", d["nrec"], 84, 28)
    if state.get("deleted"):
        look.flag("DELETED-RECORDS", "file", f"{state['deleted']:,} records are marked deleted", "they are left out of every count and sum below (a dBASE PACK removes them)")
    if state.get("ended") is not None and state["ended"] < d["nrec"]:
        look.flag("RECORD-COUNT", "header", f"{d['nrec']:,} promised, {state['ended']:,} found", "the data ends before the header says")
    if d["nrec"] <= MAX_ROWS_COPY and names:
        p = look.path_for("table.utf8.csv")
        with open(p, "w", encoding="utf-8", newline="") as out:
            w = csv.writer(out)
            w.writerow(names)
            for _i, vals in read_rows(look.path, d, enc):
                w.writerow(["" if v is None else v for v in vals])
        look.add(p, "internal", "the table as UTF-8 comma CSV")
        look.fact("table_copy", str(p))
    look.step("dbf records", "stdlib struct")
