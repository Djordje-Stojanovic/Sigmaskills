"""SigmaDeepLook MPEG transport streams read in pure Python (fix round 11): the stream table from the PAT and PMT, no ffprobe needed.

A transport stream is 188-byte packets (192 in .m2ts, 204 with error correction), each starting with the byte 0x47 and a 13-bit PID. PID 0 carries the
PAT (program number -> PMT PID); each PMT lists the programs' streams: stream type, elementary PID and descriptors (ISO 639 language 0x0A, AC-3 0x6A,
E-AC-3 0x7A, DTS 0x7B, teletext 0x56, DVB subtitles 0x59); PID 0x11 carries the SDT with the service name. Only the first few megabytes are read.
"""
import struct

SCAN_BYTES = 6 << 20
STREAM_TYPES = {0x01: ("video", "MPEG-1 video"), 0x02: ("video", "MPEG-2 video"), 0x03: ("audio", "MPEG-1 audio (mp1/mp2/mp3)"), 0x04: ("audio", "MPEG-2 audio"),
                0x06: ("data", "private PES"), 0x0F: ("audio", "AAC (ADTS)"), 0x10: ("video", "MPEG-4 video"), 0x11: ("audio", "AAC (LATM)"), 0x15: ("data", "timed metadata"),
                0x1B: ("video", "H.264 / AVC video"), 0x24: ("video", "H.265 / HEVC video"), 0x33: ("video", "VVC video"), 0x42: ("video", "AVS video"), 0x81: ("audio", "AC-3"),
                0x82: ("audio", "DTS"), 0x83: ("audio", "Dolby TrueHD"), 0x84: ("audio", "E-AC-3"), 0x85: ("audio", "DTS-HD"), 0x86: ("audio", "DTS-HD MA"), 0x87: ("audio", "E-AC-3"),
                0x90: ("subtitle", "PGS subtitles"), 0xEA: ("video", "VC-1 video")}
DESCRIPTOR_TYPES = {0x6A: ("audio", "AC-3"), 0x7A: ("audio", "E-AC-3"), 0x7B: ("audio", "DTS"), 0x7C: ("audio", "AAC"), 0x56: ("subtitle", "teletext"), 0x59: ("subtitle", "DVB subtitles")}


def packet_layout(raw):
    """-> (packet size, offset of the sync byte in a packet) for the first packet size whose sync bytes line up, or None."""
    for size in (188, 192, 204):
        for start in range(0, min(size, len(raw))):
            if raw[start] == 0x47 and all(raw[start + k * size:start + k * size + 1] == b"\x47" for k in range(1, 5)) and len(raw) >= start + 5 * size:
                return size, start
    return None


def _descriptors(blob):
    out, i = {}, 0
    while i + 2 <= len(blob):
        tag, n = blob[i], blob[i + 1]
        out.setdefault(tag, blob[i + 2:i + 2 + n])
        i += 2 + n
    return out


def read_table(path):
    """-> {"services": {id: (name, provider)}, "programs": [{"program", "pmt_pid", "pcr_pid", "streams": [{"pid", "type", "kind", "name", "lang"}]}]}, or None
    when the file is no transport stream or holds no PAT in its first megabytes."""
    with open(path, "rb") as fh:
        raw = fh.read(SCAN_BYTES)
    lay = packet_layout(raw)
    if not lay:
        return None
    size, start = lay
    bufs, pat, pmts, services = {}, {}, {}, {}
    for at in range(start, len(raw) - size + 1, size):
        if raw[at] != 0x47:
            continue
        b1, b2, b3 = raw[at + 1], raw[at + 2], raw[at + 3]
        pid, pusi, afc = ((b1 & 0x1F) << 8) | b2, bool(b1 & 0x40), (b3 >> 4) & 3
        if not (pid == 0 or pid == 0x11 or pid in pat.values()) or not afc & 1:
            continue
        pos = at + 4 + (1 + raw[at + 4] if afc & 2 else 0)
        payload = raw[pos:at + 188]
        if pusi:
            if not payload:
                continue
            bufs[pid] = bytearray(payload[1 + payload[0]:])
        elif pid in bufs:
            bufs[pid] += payload
        else:
            continue
        buf = bufs[pid]
        if len(buf) < 3:
            continue
        need = 3 + (((buf[1] & 0x0F) << 8) | buf[2])
        if len(buf) < need:
            continue
        sec = bytes(buf[:need])
        del bufs[pid]
        if sec[0] == 0 and pid == 0 and not pat:
            for i in range(8, len(sec) - 4, 4):
                num, p = struct.unpack(">HH", sec[i:i + 4])
                if num:
                    pat[num] = p & 0x1FFF
        elif sec[0] == 2 and len(sec) >= 16:
            num = struct.unpack(">H", sec[3:5])[0]
            if num in pat and pat[num] == pid and num not in pmts:
                pmts[num] = parse_pmt(sec, num, pid)
        elif sec[0] == 0x42 and pid == 0x11 and len(sec) > 15:
            parse_sdt(sec, services)
        if pat and len(pmts) == len(pat) and services:
            break
    if not pat:
        return None
    return {"services": services, "programs": [pmts[n] for n in sorted(pmts)] + [{"program": n, "pmt_pid": p, "pcr_pid": None, "streams": []} for n, p in sorted(pat.items()) if n not in pmts]}


def parse_pmt(sec, num, pmt_pid):
    pcr = ((sec[8] & 0x1F) << 8) | sec[9]
    i = 12 + (((sec[10] & 0x0F) << 8) | sec[11])
    streams = []
    while i + 5 <= len(sec) - 4:
        st, pid, n = sec[i], ((sec[i + 1] & 0x1F) << 8) | sec[i + 2], ((sec[i + 3] & 0x0F) << 8) | sec[i + 4]
        d = _descriptors(sec[i + 5:i + 5 + n])
        kind, name = STREAM_TYPES.get(st, ("data", f"stream type 0x{st:02x}"))
        if st == 0x06 or st not in STREAM_TYPES:
            for tag, (k, nm) in DESCRIPTOR_TYPES.items():
                if tag in d:
                    kind, name = k, nm
                    break
        lang = d.get(0x0A, b"")[:3].decode("latin-1", "replace") if len(d.get(0x0A, b"")) >= 3 else ""
        streams.append({"pid": pid, "type": st, "kind": kind, "name": name, "lang": lang})
        i += 5 + n
    return {"program": num, "pmt_pid": pmt_pid, "pcr_pid": pcr, "streams": streams}


def parse_sdt(sec, out):
    i = 11
    while i + 5 <= len(sec) - 4:
        sid, n = struct.unpack(">H", sec[i:i + 2])[0], ((sec[i + 3] & 0x0F) << 8) | sec[i + 4]
        d = _descriptors(sec[i + 5:i + 5 + n]).get(0x48)
        if d and len(d) >= 3:
            pl = d[1]
            prov = d[2:2 + pl].decode("latin-1", "replace")
            nl = d[2 + pl] if len(d) > 2 + pl else 0
            out[sid] = (d[3 + pl:3 + pl + nl].decode("latin-1", "replace").strip("\x05\x15"), prov.strip("\x05\x15"))
        i += 5 + n


def table_line(t):
    """The one print line for a stream table from `read_table`."""
    rows = []
    for p in t["programs"]:
        svc = t["services"].get(p["program"])
        head = f"program {p['program']}" + (f" '{svc[0]}'" + (f" by '{svc[1]}'" if svc[1] else "") if svc and svc[0] else "") + f" (PMT PID {p['pmt_pid']}" + (f", PCR PID {p['pcr_pid']}" if p["pcr_pid"] is not None else "") + ")"
        rows.append(head + ": " + (" | ".join(f"PID {s['pid']} (0x{s['pid']:x}) {s['kind']} {s['name']}" + (f" {s['lang']}" if s["lang"] else "") for s in p["streams"]) or "no PMT in the part read"))
    return "MPEG-TS stream table (PAT and PMT read from the file; PID decimal, then hex): " + " || ".join(rows) + "."


def stream_table_line(look, pri=94):
    """Adds the stream table of a transport stream to the look (no tool needed). Returns True when a table was found."""
    try:
        t = read_table(look.path)
    except (OSError, ValueError, IndexError, struct.error):
        return False
    if not t:
        return False
    look.line(table_line(t), pri, "container")
    look.fact("ts_pids", [s["pid"] for p in t["programs"] for s in p["streams"]])
    return True
