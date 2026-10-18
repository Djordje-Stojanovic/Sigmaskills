"""SigmaDeepLook: small structured binaries that carry their facts in a header or a tag tree (stdlib only, nothing is run).

BitTorrent metainfo (bencode), property lists, Standard MIDI files, Python bytecode (.pyc), ar archives including .deb packages.
Each reader prints what a person would ask first: what is in it, how big, who made it, and the numbers that describe it.
"""
import datetime
import io
import marshal
import plistlib
import struct
import tarfile
import time

import dl_core as core


# ------------------------------------------------------------------------------------------------ bencode / torrent
def bdecode(b, i=0, depth=0):
    if depth > 40:
        raise ValueError("nested too deep")
    c = b[i:i + 1]
    if c == b"i":
        j = b.index(b"e", i)
        return int(b[i + 1:j]), j + 1
    if c == b"l":
        i += 1
        out = []
        while b[i:i + 1] != b"e":
            v, i = bdecode(b, i, depth + 1)
            out.append(v)
        return out, i + 1
    if c == b"d":
        i += 1
        out = {}
        while b[i:i + 1] != b"e":
            k, i = bdecode(b, i, depth + 1)
            v, i = bdecode(b, i, depth + 1)
            out[k] = v
        return out, i + 1
    if c.isdigit():
        j = b.index(b":", i)
        n = int(b[i:j])
        return b[j + 1:j + 1 + n], j + 1 + n
    raise ValueError(f"bad bencode byte at {i}")


def _s(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


def look_torrent(look):
    b = look.path.read_bytes()
    d, _ = bdecode(b)
    info = d.get(b"info", {})
    files = info.get(b"files")
    if files:
        items = [("/".join(_s(x) for x in f.get(b"path", [])), f.get(b"length", 0)) for f in files]
    else:
        items = [(_s(info.get(b"name", b"")), info.get(b"length", 0))]
    total = sum(n for _, n in items)
    pl = info.get(b"piece length", 0)
    pieces = len(info.get(b"pieces", b"")) // 20 if info.get(b"pieces") else len(info.get(b"pieces root", b"")) // 32
    trackers = [_s(d[b"announce"])] if b"announce" in d else []
    for tier in d.get(b"announce-list", []):
        for t in tier:
            if _s(t) not in trackers:
                trackers.append(_s(t))
    cd = d.get(b"creation date")
    look.headline = f"BitTorrent metainfo {_s(info.get(b'name', ''))!r}: {len(items)} files, {core.human(total)}"
    look.fact("files", len(items))
    look.line(f"BitTorrent metainfo for {_s(info.get(b'name', '?'))!r}: {'multi-file' if files else 'single-file'}, {len(items)} files, total {total:,} bytes ({core.human(total)}), "
              f"piece length {pl:,} B, {pieces:,} pieces, {'private' if info.get(b'private') else 'public'} torrent"
              + (f", created {datetime.datetime.fromtimestamp(cd, datetime.timezone.utc):%Y-%m-%d %H:%M} UTC" if isinstance(cd, int) else "")
              + (f", created by {_s(d[b'created by'])}" if b"created by" in d else "") + (f", comment {_s(d[b'comment'])!r}" if b"comment" in d else "") + ".", 96)
    look.line(f"Trackers ({len(trackers)}): " + "; ".join(trackers[:12]) + ".", 90)
    look.line("Files (path, bytes): " + "; ".join(f"{p} {n:,}" for p, n in items[:60]) + (f"; +{len(items) - 60} more" if len(items) > 60 else "") + ".", 88)
    if len(items) > 1:
        big = max(items, key=lambda x: x[1])
        look.line(f"Largest file {big[0]} ({big[1]:,} B); smallest {min(items, key=lambda x: x[1])[0]} ({min(n for _, n in items):,} B); mean {total // len(items):,} B.", 80)
    keys = sorted(_s(k) for k in d) + ["info." + _s(k) for k in info]
    look.line("Top-level and info keys: " + ", ".join(keys) + ".", 50)
    look.step("bencode metainfo", "stdlib")


# ------------------------------------------------------------------------------------------------ property list
def _plist_walk(v, depth=0, st=None):
    st = st if st is not None else {"dict": 0, "array": 0, "string": 0, "int": 0, "real": 0, "bool": 0, "date": 0, "data": 0, "keys": []}
    if isinstance(v, dict):
        st["dict"] += 1
        for k, x in v.items():
            if depth < 2:
                st["keys"].append(k)
            _plist_walk(x, depth + 1, st)
    elif isinstance(v, list):
        st["array"] += 1
        for x in v:
            _plist_walk(x, depth + 1, st)
    else:
        key = "bool" if isinstance(v, bool) else "int" if isinstance(v, int) else "real" if isinstance(v, float) else "string" if isinstance(v, str) else \
            "date" if isinstance(v, datetime.datetime) else "data" if isinstance(v, (bytes, bytearray)) else "string"
        st[key] += 1
    return st


def _short(v, n=60):
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)} bytes>"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_short(x, 30)}" for k, x in list(v.items())[:4]) + (", ..." if len(v) > 4 else "") + "}"
    if isinstance(v, list):
        return f"[{len(v)} items]"
    return str(v)[:n]


def look_plist(look):
    raw = look.path.read_bytes()
    v = plistlib.loads(raw)
    st = _plist_walk(v)
    fmt = "binary" if raw[:8] == b"bplist00" else "XML"
    look.headline = f"Property list ({fmt}): {st['dict']} dictionaries, {st['array']} arrays"
    look.line(f"Property list ({fmt}): root is a {type(v).__name__} with {len(v)} entries; in all {st['dict']} dictionaries, {st['array']} arrays, {st['string']} strings, {st['int']} integers, "
              f"{st['real']} reals, {st['bool']} booleans, {st['date']} dates, {st['data']} data blobs.", 96)
    if isinstance(v, dict):
        look.line("Top-level entries: " + "; ".join(f"{k} = {_short(x)}" for k, x in list(v.items())[:60]) + ".", 92)
    look.step("property list tree", "plistlib")


# ------------------------------------------------------------------------------------------------ MIDI
GM = ["Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet", "Celesta", "Glockenspiel",
      "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica",
      "Tango Accordion", "Nylon Guitar", "Steel Guitar", "Jazz Guitar", "Clean Guitar", "Muted Guitar", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics", "Acoustic Bass", "Fingered Bass",
      "Picked Bass", "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp",
      "Timpani", "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2", "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone", "Tuba",
      "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2", "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet",
      "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina"]


def _vlq(b, i):
    v = 0
    while True:
        c = b[i]
        i += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, i


def parse_midi(b):
    fmt, ntrk, div = struct.unpack(">HHH", b[8:14])
    i = 8 + struct.unpack(">I", b[4:8])[0]
    tracks, tempos, sigs, keys, ends = [], [], [], [], []
    for _ in range(ntrk):
        if b[i:i + 4] != b"MTrk":
            break
        ln = struct.unpack(">I", b[i + 4:i + 8])[0]
        d, j, t, run = b[i + 8:i + 8 + ln], 0, 0, 0
        tr = {"name": "", "events": 0, "notes": 0, "channels": set(), "programs": [], "end": 0, "lo": 128, "hi": -1, "texts": []}
        while j < len(d):
            dt, j = _vlq(d, j)
            t += dt
            st = d[j]
            if st == 0xFF:
                typ, j = d[j + 1], j + 2
                n, j = _vlq(d, j)
                data = d[j:j + n]
                j += n
                if typ == 0x03:
                    tr["name"] = data.decode("latin-1")
                elif typ in (0x01, 0x05, 0x06):
                    tr["texts"].append(data.decode("latin-1")[:40])
                elif typ == 0x51 and n == 3:
                    tempos.append((t, int.from_bytes(data, "big")))
                elif typ == 0x58 and n >= 2:
                    sigs.append((t, data[0], 2 ** data[1]))
                elif typ == 0x59 and n == 2:
                    keys.append((t, struct.unpack("b", data[:1])[0], data[1]))
                continue
            if st in (0xF0, 0xF7):
                n, j = _vlq(d, j + 1)
                j += n
                continue
            if st & 0x80:
                run = st
                j += 1
            else:
                st = run
            k = st & 0xF0
            ch = st & 0x0F
            n = 1 if k in (0xC0, 0xD0) else 2
            a = d[j:j + n]
            j += n
            tr["events"] += 1
            tr["channels"].add(ch)
            if k == 0x90 and len(a) == 2 and a[1] > 0:
                tr["notes"] += 1
                tr["lo"], tr["hi"] = min(tr["lo"], a[0]), max(tr["hi"], a[0])
            elif k == 0xC0:
                tr["programs"].append((ch, a[0]))
        tr["end"] = t
        tracks.append(tr)
        ends.append(t)
        i += 8 + ln
    return {"format": fmt, "ntrk": ntrk, "division": div, "tracks": tracks, "tempos": tempos, "sigs": sigs, "keys": keys, "ticks": max(ends or [0])}


def _note(n):
    return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][n % 12] + str(n // 12 - 1)


def look_midi(look):
    m = parse_midi(look.path.read_bytes())
    div = m["division"]
    tempo = m["tempos"][0][1] if m["tempos"] else 500000
    secs = None
    if not div & 0x8000:
        secs, last_t, last_us, tempos = 0.0, 0, 500000, sorted(m["tempos"])
        for t, us in tempos:
            secs += (t - last_t) / div * last_us / 1e6
            last_t, last_us = t, us
        secs += (m["ticks"] - last_t) / div * last_us / 1e6
    notes = sum(t["notes"] for t in m["tracks"])
    look.headline = f"Standard MIDI file: format {m['format']}, {len(m['tracks'])} tracks, {notes} notes" + (f", {secs:.1f} s" if secs is not None else "")
    look.fact("tracks", len(m["tracks"]))
    look.line(f"Standard MIDI file format {m['format']}: {len(m['tracks'])} tracks, {div} ticks per quarter note, {notes} note-on events in total, length {m['ticks']:,} ticks"
              + (f" = {secs:.2f} s at the file's tempo map" if secs is not None else "") + f", first tempo {tempo} us per beat = {60_000_000 / tempo:.1f} BPM"
              + (f" ({len(m['tempos'])} tempo changes)" if len(m["tempos"]) > 1 else "") + (", time signature " + ", ".join(f"{a}/{b} at tick {t}" for t, a, b in m["sigs"][:4]) if m["sigs"] else ", no time signature (4/4 assumed)")
              + (", key signature " + ", ".join(f"{abs(k)} {'sharps' if k > 0 else 'flats'} {'minor' if mi else 'major'}" for _t, k, mi in m["keys"][:2]) if m["keys"] else "") + ".", 96)
    for k, t in enumerate(m["tracks"][:32]):
        prog = ", ".join(f"channel {c + 1}: {GM[p] if p < len(GM) else 'program ' + str(p)}" for c, p in t["programs"][:4])
        look.line(f"Track {k}: name {t['name']!r}, {t['events']} channel events, {t['notes']} notes"
                  + (f", pitch range {_note(t['lo'])}..{_note(t['hi'])}" if t["notes"] else "") + (f", channels {sorted(c + 1 for c in t['channels'])}" if t["channels"] else "")
                  + (f", instruments {prog}" if prog else "") + f", ends at tick {t['end']:,}.", 90 - min(k, 20))
    look.step("MIDI header, tracks and events", "stdlib")


# ------------------------------------------------------------------------------------------------ Python bytecode
PYC_RANGES = ((3379, "3.6"), (3399, "3.7"), (3413, "3.8"), (3429, "3.9"), (3449, "3.10"), (3499, "3.11"), (3549, "3.12"), (3599, "3.13"))   # highest magic number of each release


def pyc_version(magic):
    for top, v in PYC_RANGES:
        if magic <= top:
            return v if magic > 3300 else "3.5 or older"
    return "3.14 or newer"


def look_pyc(look):
    b = look.path.read_bytes()
    magic = struct.unpack("<H", b[:2])[0]
    flags = struct.unpack("<I", b[4:8])[0]
    ver = pyc_version(magic)
    if flags & 1:
        src = f"hash-based ({'checked' if flags & 2 else 'unchecked'}), source hash {b[8:16].hex()}"
    else:
        ts, sz = struct.unpack("<II", b[8:16])
        src = f"timestamp-based: source modified {datetime.datetime.fromtimestamp(ts, datetime.timezone.utc):%Y-%m-%d %H:%M:%S} UTC, source size {sz:,} B"
    look.headline = f"Python bytecode (magic {magic}, CPython {ver})"
    look.line(f"Compiled Python file: magic number {magic} = CPython {ver}; {src}; code object {len(b) - 16:,} bytes.", 96)
    try:
        code = marshal.loads(b[16:])   # decoding a code object never runs it
        def walk(c, depth=0, out=None):
            out = out if out is not None else []
            out.append((depth, c))
            for k in c.co_consts:
                if hasattr(k, "co_code"):
                    walk(k, depth + 1, out)
            return out
        cs = walk(code)
        look.line(f"Source file name recorded: {code.co_filename}; module code names: {', '.join(code.co_names[:30])}; {len(cs) - 1} nested code objects (functions, classes, lambdas): "
                  + ", ".join(f"{c.co_qualname if hasattr(c, 'co_qualname') else c.co_name}({c.co_argcount} args, line {c.co_firstlineno})" for _d, c in cs[1:30]) + ".", 92)
        consts = [repr(k)[:50] for c in (x for _d, x in cs) for k in c.co_consts if isinstance(k, (str, int, float, bytes)) and k not in (None, 0, 1)][:30]
        look.line("Constants: " + ", ".join(consts) + ".", 80)
    except Exception as e:
        look.line(f"The code object could not be decoded here ({type(e).__name__}: {str(e)[:80]}); it was made by a different Python version than {__import__('sys').version.split()[0]}.", 70)
    look.step("pyc header and code objects", "marshal")


# ------------------------------------------------------------------------------------------------ ar / deb
def parse_ar(b):
    i, out = 8, []
    while i + 60 <= len(b):
        h = b[i:i + 60]
        name = h[:16].decode("latin-1").strip().rstrip("/")
        size = int(h[48:58].decode().strip() or 0)
        mtime = int(h[16:28].decode().strip() or 0)
        out.append((name, size, mtime, b[i + 60:i + 60 + size]))
        i += 60 + size + (size % 2)
    return out


def look_ar(look):
    b = look.path.read_bytes()
    mem = parse_ar(b)
    is_deb = bool(mem) and mem[0][0] == "debian-binary"
    look.headline = f"{'Debian package' if is_deb else 'ar archive'}: {len(mem)} members"
    look.line(f"{'Debian package (ar container)' if is_deb else 'ar archive'} with {len(mem)} members: " + "; ".join(f"{n} {s:,} B" for n, s, _m, _d in mem) + ".", 96)
    for n, s, m, data in mem:
        if n.startswith("control.tar") or n.startswith("data.tar"):
            try:
                t = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
                ms = t.getmembers()
                if n.startswith("control.tar"):
                    for x in ms:
                        if x.isfile() and x.name.lstrip("./") == "control":
                            look.line("Package control file: " + " | ".join(l.strip() for l in t.extractfile(x).read().decode("utf-8", "replace").splitlines() if l.strip())[:900], 94)
                    look.line(f"{n} holds: " + ", ".join(x.name for x in ms[:20]) + ".", 70)
                else:
                    files = [x for x in ms if x.isfile()]
                    look.line(f"{n}: {len(files)} files, {sum(x.size for x in files):,} bytes installed: " + "; ".join(f"{x.name} {x.size:,}" for x in files[:40]) + (f"; +{len(files) - 40} more" if len(files) > 40 else "") + ".", 88)
            except Exception as e:
                look.line(f"{n}: not readable here ({type(e).__name__}).", 40)
    look.step("ar members, control file and file list", "stdlib")


# ------------------------------------------------------------------------------------------------ headerless fixed-size records
def record_layout(b, total):
    """Guess the record size of a headerless binary table and type its fields -> (lines) or [] when nothing structured is found."""
    try:
        import numpy as np
    except ImportError:
        return []
    n = len(b)
    if n < 512 or total < 512:
        return []
    arr = np.frombuffer(b, dtype=np.uint8)
    best = None
    for s in range(2, 257):
        if total % s:
            continue
        recs = min(n // s, 20000)
        if recs < 40:
            break
        m = arr[:recs * s].reshape(recs, s)
        low = 0
        for c in range(s):
            cnt = np.bincount(m[:, c], minlength=256)
            p = cnt[cnt > 0] / recs
            if -(p * np.log2(p)).sum() < 1.2:
                low += 1
        score = low / s
        # a multiple of the true size scores the same; the smallest size with a clearly structured layout wins
        if score >= 0.25 and (best is None or score > best[0] + 0.12):
            best = (score, s)
    if not best:
        return []
    s = best[1]
    recs = n // s
    m = arr[:recs * s].reshape(recs, s)
    fields, o = [], 0
    while o < s:
        if o % 4 == 0 and o + 4 <= s:
            col = np.ascontiguousarray(m[:, o:o + 4]).view("<u4").ravel()
            f32 = col.view("<f4")
            if (col == 0).all():
                fields.append((o, 4, "zero padding"))
                o += 4
                continue
            fin = np.isfinite(f32) & (((np.abs(f32) > 1e-6) & (np.abs(f32) < 1e9)) | (f32 == 0))
            if fin.all() and col.max() > 2 ** 24:
                fields.append((o, 4, f"float32 {f32.min():.4g}..{f32.max():.4g}, mean {f32.mean():.4g}"))
            else:
                d = np.diff(col.astype("int64"))
                inc = " strictly increasing (a counter or id)" if len(d) and (d > 0).all() else " non-decreasing" if len(d) and (d >= 0).all() else ""
                nd = len(np.unique(col))
                fields.append((o, 4, f"uint32 {int(col.min())}..{int(col.max())}, {nd} distinct{inc}" + (f", values {sorted(np.unique(col).tolist())[:8]}" if nd <= 8 else "")))
            o += 4
        elif o % 2 == 0 and o + 2 <= s:
            col = np.ascontiguousarray(m[:, o:o + 2]).view("<u2").ravel()
            nd = len(np.unique(col))
            if (col == 0).all():
                fields.append((o, 2, "zero padding"))
            else:
                vc = np.bincount(col.astype("int64"))[: 1 << 16] if col.max() < 1 << 16 else None
                top = ", ".join(f"{k}:{int(vc[k])}" for k in np.argsort(-vc)[:6] if vc[k]) if (nd <= 12 and vc is not None) else ""
                fields.append((o, 2, f"uint16 {int(col.min())}..{int(col.max())}, {nd} distinct" + (f" (value:count {top})" if top else "")))
            o += 2
        else:
            col = m[:, o]
            fields.append((o, 1, f"byte {int(col.min())}..{int(col.max())}, {len(np.unique(col))} distinct"))
            o += 1
    return [f"Looks like a headerless table of fixed-size binary records: {total // s:,} records of {s} bytes ({total} = {total // s} x {s}); a guess from the bytes, confirm it against the format's documentation; field layout (little-endian guess): "
            + "; ".join(f"bytes {a}-{a + n - 1} {desc}" for a, n, desc in fields) + "."]
