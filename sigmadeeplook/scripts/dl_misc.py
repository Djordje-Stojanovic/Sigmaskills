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
import dl_util as U


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


WHOLE_CAP = U.byte_cap("WHOLE", 256 << 20)   # these readers parse one whole structure in memory: a file past this size is named, not loaded


def _whole(look, what):
    """The file's bytes for a reader that needs the whole structure, or None (and a Not-looked-at row) when the file is past WHOLE_CAP."""
    if look.size > WHOLE_CAP:
        look.skip(what, f"{core.human(look.size)} is over the {core.human(WHOLE_CAP)} this reader holds in memory", None,
                  "raise SIGMADEEPLOOK_WHOLE_CAP, or query the file with its own tools")
        return None
    return look.path.read_bytes()


def _s(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


def look_torrent(look):
    b = _whole(look, "torrent metainfo")
    if b is None:
        return
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
    raw = _whole(look, "property list")
    if raw is None:
        return
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


def midi_seconds(tick, div, tempos):
    """Tick -> seconds through the tempo map (None for SMPTE time division)."""
    if div & 0x8000:
        return None
    secs, last_t, last_us = 0.0, 0, 500000
    for t, us in sorted(tempos):
        if t >= tick:
            break
        secs += (t - last_t) / div * last_us / 1e6
        last_t, last_us = t, us
    return secs + (tick - last_t) / div * last_us / 1e6


def midi_event_lines(m, cap=40):
    """Every set_tempo and key_signature meta event with its tick and time, plus the count. -> lines."""
    out, div = [], m["division"]

    def when(t):
        s = midi_seconds(t, div, m["tempos"])
        return f"tick {t} ({s:.2f} s)" if s is not None else f"tick {t}"
    if m["tempos"]:
        ev = [f"{when(t)}: {60_000_000 / us:.2f} BPM" for t, us in m["tempos"][:cap]]
        out.append(f"All {len(m['tempos'])} set_tempo events: " + "; ".join(ev) + (f"; +{len(m['tempos']) - cap} more" if len(m["tempos"]) > cap else "") + ".")
    if m["keys"]:
        def kname(k, mi):
            return f"{abs(k)} {'sharps' if k > 0 else 'flats' if k < 0 else 'sharps or flats (C major / A minor)'} {'minor' if mi else 'major'}"
        ev = [f"{when(t)}: {kname(k, mi)}" for t, k, mi in m["keys"][:cap]]
        out.append(f"All {len(m['keys'])} key_signature events: " + "; ".join(ev) + (f"; +{len(m['keys']) - cap} more" if len(m["keys"]) > cap else "") + ".")
    return out


def look_midi(look):
    raw = _whole(look, "MIDI tracks")
    if raw is None:
        return
    m = parse_midi(raw)
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
    for line in midi_event_lines(m):
        look.line(line, 95)
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
    b = _whole(look, "Python bytecode")
    if b is None:
        return
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
def parse_ar(b, data_cap=None):
    """-> [(name, size, mtime, data)]. b may be a memory map: a member bigger than data_cap gets data None and is never copied."""
    i, out = 8, []
    while i + 60 <= len(b):
        h = b[i:i + 60]
        name = h[:16].decode("latin-1").strip().rstrip("/")
        size = int(h[48:58].decode().strip() or 0)
        mtime = int(h[16:28].decode().strip() or 0)
        out.append((name, size, mtime, None if data_cap is not None and size > data_cap else b[i + 60:i + 60 + size]))
        i += 60 + size + (size % 2)
    return out


def open_tar(data):
    """A tar member in any compression: plain, gzip, bzip2, xz (tarfile), zstd (stdlib 3.14, zstandard, or the zstd tool). -> TarFile or raises."""
    try:
        return tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
    except tarfile.TarError:
        if data[:4] != b"\x28\xb5\x2f\xfd":
            raise
    raw = None
    try:
        from compression import zstd   # Python 3.14+
        raw = zstd.decompress(data)
    except Exception:
        try:
            import zstandard
            raw = zstandard.ZstdDecompressor().decompressobj().decompress(data)
        except Exception:
            import shutil
            import subprocess
            exe = shutil.which("zstd")
            if exe:
                raw = subprocess.run([exe, "-d", "-c"], input=data, capture_output=True, timeout=60).stdout
    if not raw:
        raise ValueError("zstd member and no zstd decoder found")
    return tarfile.open(fileobj=io.BytesIO(raw), mode="r:")


def control_fields(text):
    """Debian control text -> {field: value}; continuation lines are joined with a newline."""
    out, cur = {}, None
    for l in text.splitlines():
        if l[:1] in (" ", "\t") and cur:
            out[cur] += "\n" + l.strip()
        elif ":" in l and not l.startswith("#"):
            cur, v = l.split(":", 1)
            cur = cur.strip()
            out[cur] = v.strip()
    return out


CONTROL_KEYS = ["Package", "Version", "Architecture", "Maintainer", "Depends", "Installed-Size", "Section"]


AR_MEMBER_CAP = U.byte_cap("AR_MEMBER", 256 << 20)   # one ar member (data.tar.xz of a .deb) is opened in memory up to this size


def look_ar(look):
    import mmap
    with open(look.path, "rb") as fh:   # mapped, not read: a multi-GB .deb costs only the members that are opened
        with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as b:
            mem = parse_ar(b, AR_MEMBER_CAP)
    _look_ar_members(look, mem)


def _look_ar_members(look, mem):
    is_deb = bool(mem) and mem[0][0] == "debian-binary"
    look.headline = f"{'Debian package' if is_deb else 'ar archive'}: {len(mem)} members"
    look.line(f"{'Debian package (ar container)' if is_deb else 'ar archive'} with {len(mem)} members: " + "; ".join(f"{n} {s:,} B" for n, s, _m, _d in mem) + ".", 96)
    for n, s, m, data in mem:
        if data is None and (n.startswith("control.tar") or n.startswith("data.tar")):
            look.line(f"{n}: {s:,} bytes, over the {core.human(AR_MEMBER_CAP)} opened in memory, so its file list is not read (PARTIAL).", 60)
            look.flag("PARTIAL", n, f"{core.human(s)} member not opened", "raise SIGMADEEPLOOK_AR_MEMBER_CAP to list it")
        elif n.startswith("control.tar") or n.startswith("data.tar"):
            try:
                t = open_tar(data)
                ms = t.getmembers()
                if n.startswith("control.tar"):
                    for x in ms:
                        if x.isfile() and x.name.lstrip("./") == "control":
                            f = control_fields(t.extractfile(x).read().decode("utf-8", "replace"))
                            desc = f.get("Description", "").split("\n")[0]
                            look.fact("deb_control", {k: f[k] for k in CONTROL_KEYS if k in f})
                            if f.get("Package"):
                                look.headline = f"Debian package {f['Package']} {f.get('Version', '')}".strip()
                            look.line("Package control fields: " + "; ".join(f"{k}: {f[k][:300]}" for k in CONTROL_KEYS if k in f) + f"; Description (first line): {desc[:200]}.", 97)
                            other = [k for k in f if k not in CONTROL_KEYS and k != "Description"]
                            if other:
                                look.line("Other control fields: " + ", ".join(other[:20]) + ".", 60)
                    look.line(f"{n} holds: " + ", ".join(x.name for x in ms[:20]) + ".", 70)
                else:
                    files = [x for x in ms if x.isfile()]
                    look.line(f"{n}: {len(files)} files, {sum(x.size for x in files):,} bytes installed: " + "; ".join(f"{x.name} {x.size:,}" for x in files[:40]) + (f"; +{len(files) - 40} more" if len(files) > 40 else "") + ".", 88)
                    if len(files) > 40:
                        look.write_text("data_files.txt", "\n".join(f"{x.size}\t{x.name}" for x in files), f"every file in {n}")
            except Exception as e:
                look.line(f"{n}: not readable here ({type(e).__name__}: {str(e)[:80]}).", 40)
    look.step("ar members, control file and file list", "stdlib")


# ------------------------------------------------------------------------------------------------ headerless fixed-size records
TS_LO, TS_HI = 631152000, 4102444800   # epoch seconds for 1990-01-01 .. 2100-01-01: a column wholly inside is read as a timestamp


def _iso(sec):
    return datetime.datetime.fromtimestamp(sec, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _text_runs(m, np):
    """Runs of byte columns that hold fixed-width text: printable ASCII (letters, digits, space, punctuation) with NUL padding, seen in at least
    two columns, at least 80 % word characters. -> [(start, end)]."""
    s = m.shape[1]
    pr = [(m[:, c] >= 32) & (m[:, c] < 127) for c in range(s)]
    loose = [bool((pr[c] | (m[:, c] == 0)).mean() >= 0.97) for c in range(s)]
    core_ = [loose[c] and bool(pr[c].mean() >= 0.3) for c in range(s)]
    runs, c = [], 0
    while c < s:
        if not core_[c]:
            c += 1
            continue
        e = c
        while e < s and loose[e]:
            e += 1
        cols = [x for x in range(c, e) if core_[x]]
        if len(cols) >= 2:
            chars = np.concatenate([m[:, x][pr[x]] for x in cols])
            word = ((chars >= 48) & (chars <= 57)) | ((chars >= 65) & (chars <= 90)) | ((chars >= 97) & (chars <= 122)) | (chars == 32) | (chars == 46) | (chars == 95) | (chars == 45)
            if word.mean() >= 0.8:
                runs.append((c, e))
        c = e
    return runs


def _describe_int(col, width, prefix):
    vals = np_unique_small(col)
    d = col.astype("int64") if width < 8 else col
    inc = ""
    if len(d) > 1:
        dd = d[1:] - d[:-1]
        inc = " strictly increasing (a counter or id)" if (dd > 0).all() else " non-decreasing" if (dd >= 0).all() else ""
    return (f"{prefix}{width * 8} {int(col.min())}..{int(col.max())}, {len(vals[0]) if vals[1] else 'many'} distinct{inc}"
            + (f", values {vals[0][:8]}" if vals[1] and len(vals[0]) <= 8 else ""))


def np_unique_small(col):
    u = sorted(set(col[:200000].tolist()))
    return u, len(col) <= 200000 or len(u) > 8


def type_fields(m, s, np):
    """Type every byte of a record matrix (records x s bytes) from the bytes alone -> ([(offset, width, description)], byte order).
    Per offset: fixed-width text, then 8-byte timestamp / float64 / integer, 4-byte timestamp / float32 / integer, 2-byte, 1-byte;
    all-zero columns are padding. The byte order is whichever makes the high bytes of the 4-byte columns the quieter ones."""
    recs = m.shape[0]
    runs = _text_runs(m, np)
    le_quiet = be_quiet = 0
    for o in range(0, s - 3, 4):
        lo, hi = len(np.unique(m[:, o])), len(np.unique(m[:, o + 3]))
        le_quiet += hi < lo
        be_quiet += lo < hi
    big = be_quiet > le_quiet
    e = ">" if big else "<"
    loose = [bool((((m[:, c] >= 32) & (m[:, c] < 127)) | (m[:, c] == 0)).mean() >= 0.97) for c in range(s)]
    fields, o = [], 0
    while o < s:
        run = next((b for a, b in runs if a <= o < b), None)
        # a timestamp or float whose bytes are not all printable (a text column would read as a number by accident) is tried first
        if o + 8 <= s and not all(loose[o:o + 8]):
            blk = np.ascontiguousarray(m[:, o:o + 8])
            u8 = blk.view(e + "u8").ravel()
            f8 = blk.view(e + "f8").ravel()
            if (u8 == 0).all():
                fields.append((o, 8, "zero padding"))
                o += 8
                continue
            if ((u8 > TS_LO * 1000) & (u8 < TS_HI * 1000)).all() and len(np.unique(u8)) > 1:
                fields.append((o, 8, f"timestamp (uint64 epoch milliseconds) {_iso(int(u8.min()) // 1000)} .. {_iso(int(u8.max()) // 1000)}"))
                o += 8
                continue
            if np.isfinite(f8).all() and (((np.abs(f8) > 1e-9) & (np.abs(f8) < 1e12)) | (f8 == 0)).all() and u8.max() > 2 ** 40 and len(np.unique(u8)) > 1 and ((u8 & 0xFFFFFFFF if e == '<' else u8 >> 32).max() > 2 ** 24 or ((u8 & 0xFFFFFFFF if e == '<' else u8 >> 32) == 0).all()):
                if ((f8 > TS_LO) & (f8 < TS_HI)).all():
                    fields.append((o, 8, f"timestamp (float64 epoch seconds) {_iso(float(f8.min()))} .. {_iso(float(f8.max()))}"))
                else:
                    fields.append((o, 8, f"float64 {f8.min():.6g}..{f8.max():.6g}, mean {f8.mean():.6g}"))
                o += 8
                continue
        if o + 4 <= s and not all(loose[o:o + 4]):
            raw = np.ascontiguousarray(m[:, o:o + 4])
            col = raw.view(e + "u4").ravel()
            f32 = raw.view(e + "f4").ravel()
            sane = bool((np.isfinite(f32) & (((np.abs(f32) >= 1e-3) & (np.abs(f32) < 1e7)) | (f32 == 0))).all())   # measurement-sized floats win over a 2000-2011 epoch reading
            if sane and col.max() > 2 ** 24 and len(np.unique(col)) > 1:
                fields.append((o, 4, f"float32 {f32.min():.4g}..{f32.max():.4g}, mean {f32.mean():.4g}"))
                o += 4
                continue
            if ((col >= TS_LO) & (col < TS_HI)).all() and len(np.unique(col)) > 1:
                fields.append((o, 4, f"timestamp (uint32 epoch seconds) {_iso(int(col.min()))} .. {_iso(int(col.max()))}"))
                o += 4
                continue
            if (np.isfinite(f32) & (((np.abs(f32) > 1e-6) & (np.abs(f32) < 1e9)) | (f32 == 0))).all() and col.max() > 2 ** 24 and len(np.unique(col)) > 1:
                fields.append((o, 4, f"float32 {f32.min():.4g}..{f32.max():.4g}, mean {f32.mean():.4g}"))
                o += 4
                continue
        if run is not None:
            blk = m[:, o:run]
            strs = [bytes(r).rstrip(b"\0").decode("latin-1") for r in blk[:2000]]
            ln = [len(x) for x in strs]
            ex = list(dict.fromkeys(x for x in strs if x))[:4]
            fields.append((o, run - o, f"fixed text, {run - o} bytes (NUL-trimmed length {min(ln)}..{max(ln)}), e.g. {ex}"))
            o = run
            continue
        nxt = min([a for a, _b in runs if a > o] + [s])   # an integer never reaches into the next text run
        if o % 4 == 0 and o + 4 <= nxt:
            raw = np.ascontiguousarray(m[:, o:o + 4])
            col = raw.view(e + "u4").ravel()
            if (col == 0).all():
                fields.append((o, 4, "zero padding"))
            else:
                i4 = raw.view(e + "i4").ravel()
                neg = bool((i4 < 0).any() and (np.abs(i4.astype("int64")) < 2 ** 24).all())   # small values with a negative sign: signed
                fields.append((o, 4, _describe_int(i4 if neg else col, 4, "int" if neg else "uint")))
            o += 4
        elif o % 2 == 0 and o + 2 <= nxt:
            col = np.ascontiguousarray(m[:, o:o + 2]).view(e + "u2").ravel()
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
    return fields, ("big" if big else "little")


def refine_size(arr, n, s, np):
    """A record size that is a multiple of the true one (two records per window) repeats its own layout: the smallest divisor d of s whose
    byte columns c and c + d look alike (same low-entropy flag, similar min and max) is the real record size."""
    recs = min(n // s, 20000)
    m = arr[:recs * s].reshape(recs, s)
    fp = []
    for c in range(s):
        cnt = np.bincount(m[:, c], minlength=256)
        p = cnt[cnt > 0] / recs
        fp.append((-(p * np.log2(p)).sum() < 1.2, int(m[:, c].min()), int(m[:, c].max())))
    for d in range(4, s // 2 + 1):
        if s % d:
            continue
        ok = sum(1 for c in range(s - d) if fp[c][0] == fp[c + d][0] and abs(fp[c][1] - fp[c + d][1]) <= 16 and abs(fp[c][2] - fp[c + d][2]) <= 48)
        if ok >= 0.9 * (s - d):
            return d
    return s


HEADER_SIZES = tuple(range(1, 65)) + (128, 256, 512, 1024, 2048, 4096)   # tried only when no layout fits the bytes from offset 0
MIN_RECORDS = 40
HEADERLESS_OK = 0.4   # a layout from offset 0 with at least this share of low-entropy columns is taken as headerless


def _layout_score(arr, n, s, h, np):
    """Share of byte columns with low entropy over the records that start at offset h, or None when fewer than MIN_RECORDS fit."""
    recs = min((n - h) // s, 20000)
    if recs < MIN_RECORDS:
        return None
    m = arr[h:h + recs * s].reshape(recs, s)
    low = 0
    for c in range(s):
        cnt = np.bincount(m[:, c], minlength=256)
        p = cnt[cnt > 0] / recs
        if -(p * np.log2(p)).sum() < 1.2:
            low += 1
    return low / s


def _trim_header(arr, n, s, h, np):
    """The records may start one or more whole records later than the best offset: while the first record disagrees with the records after it in
    the columns that never change (its bytes are not among the values those columns take), it belongs to the header and the offset moves up."""
    for _ in range(8):
        if h + s * (MIN_RECORDS + 1) > n:
            break
        rest = arr[h + s:h + s + s * min(300, (n - h) // s - 1)].reshape(-1, s)
        stable = [c for c in range(s) if len(np.unique(rest[:, c])) <= 2]
        if len(stable) < 2:
            break
        first = arr[h:h + s]
        bad = sum(1 for c in stable if first[c] not in rest[:, c])
        if bad >= 1 and bad >= 0.3 * len(stable):
            h += s
        else:
            break
    return h


def record_layout(b, total):
    """Guess the record size of a headerless binary table and type its fields -> (lines) or [] when nothing structured is found.
    Record sizes that divide the file are tried at offset 0 first, then after a header of 1..64 bytes (or 128..4096); a header layout has to beat
    the headerless ones clearly. The runner-up layouts are named, so a wrong first guess can be told from the bytes."""
    try:
        import numpy as np
    except ImportError:
        return []
    n = len(b)
    if n < 512 or total < 512:
        return []
    arr = np.frombuffer(b, dtype=np.uint8)
    cands = []   # (score, size, header)
    best = None   # (score, size, header)
    seen = set()   # (size, offset within a record): a header that is whole records longer is the same alignment, found by _trim_header
    for h in (0,) + HEADER_SIZES:
        if h and best and best[0] >= HEADERLESS_OK:
            break   # a clearly structured layout from offset 0 stands; a header is only looked for when none fits
        for s in range(2, 257):
            if (total - h) % s or (s, h % s) in seen:
                continue
            seen.add((s, h % s))
            if (n - h) // s < MIN_RECORDS:
                break
            score = _layout_score(arr, n, s, h, np)
            if score is None:
                break
            if score >= (0.25 if h == 0 else 0.4):
                cands.append((score, s, h))
                # a multiple of the true size scores the same; the smallest size with a clearly structured layout wins
                if best is None or score > best[0] + 0.12 or (h and best[2] == 0 and score >= 0.4 > best[0]):
                    best = (score, s, h)
    if not best:
        return []
    h = _trim_header(arr, n, best[1], best[2], np)
    best = best[:2]
    s = refine_size(arr[h:], n - h, best[1], np)
    recs = (n - h) // s
    m = arr[h:h + recs * s].reshape(recs, s)
    fields, order = type_fields(m, s, np)
    first = (f"Looks like a table of fixed-size binary records after a {h}-byte header: {(total - h) // s:,} records of {s} bytes ({total} = {h} + {(total - h) // s} x {s})"
             if h else f"Looks like a headerless table of fixed-size binary records: {total // s:,} records of {s} bytes ({total} = {total // s} x {s})")
    out = [first + f"; a guess from the bytes, confirm it against the format's documentation; field layout (typed from the bytes, {order}-endian guess): "
           + "; ".join(f"bytes {h + a}-{h + a + k - 1} {desc}" for a, k, desc in fields) + "."]
    alt = []
    for sc, s2, h2 in sorted(cands, key=lambda c: (-c[0], c[1], c[2])):
        if (h2 - h) % s == 0 and (s2 % s == 0 or s % s2 == 0) or len(alt) >= 2:   # the same layout seen as a multiple, a divisor or a shifted copy
            continue
        alt.append(f"{s2} bytes" + (f" after a {h2}-byte header" if h2 else "") + f" (structure score {sc:.2f})")
    if alt:
        out.append(f"Other record layouts that also divide the file and look structured (weaker): {'; '.join(alt)}; chosen: {s} bytes (score {best[0]:.2f}).")
    return out
