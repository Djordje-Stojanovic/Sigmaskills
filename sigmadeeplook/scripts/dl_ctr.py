"""SigmaDeepLook: container-level counts of audio files, read from the bytes with the standard library (no ffprobe needed).

A single-stream audio container has no table of contents for ffprobe to summarise, but its framing can be counted exactly: Ogg pages and
packets (with the codec from the first page and the duration from the last granule position), WAV chunks, FLAC metadata blocks and the
total sample count, MP3 frames. These counts are facts about the container, printed at the first budget with the stream facts.
"""
import struct

OGG_CODECS = ((b"\x01vorbis", "vorbis"), (b"OpusHead", "opus"), (b"\x7fFLAC", "flac"), (b"Speex   ", "speex"), (b"\x80theora", "theora"), (b"fishead\0", "skeleton"), (b"BBCD", "dirac"))


def ogg_counts(path, limit_s=20.0):
    """-> dict with pages, packets, streams {serial: {codec, rate, channels, pages, last_granule, bos, eos}}, bytes min/max/mean per page, complete."""
    import time
    t0 = time.time()
    pages, packets, sizes, streams, bad = 0, 0, [], {}, 0
    with open(path, "rb") as f:
        size = f.seek(0, 2)
        f.seek(0)
        while True:
            pos = f.tell()
            h = f.read(27)
            if len(h) < 27:
                break
            if h[:4] != b"OggS":   # lost sync: look for the next capture pattern in the next 64 KB
                bad += 1
                f.seek(pos + 1)
                chunk = f.read(65536)
                k = chunk.find(b"OggS")
                if k < 0:
                    if len(chunk) < 65536:
                        break
                    f.seek(pos + 65536)
                    continue
                f.seek(pos + 1 + k)
                continue
            htype, granule, serial = h[5], struct.unpack_from("<q", h, 6)[0], struct.unpack_from("<I", h, 14)[0]
            nseg = h[26]
            table = f.read(nseg)
            body = sum(table)
            first = f.read(min(body, 64)) if htype & 2 else b""
            f.seek(pos + 27 + nseg + body)
            pages += 1
            packets += sum(1 for s in table if s < 255)
            sizes.append(27 + nseg + body)
            st = streams.setdefault(serial, {"codec": None, "rate": None, "channels": None, "pages": 0, "last_granule": None, "bos": False, "eos": False, "pre_skip": 0})
            st["pages"] += 1
            if htype & 2:
                st["bos"] = True
                for magic, name in OGG_CODECS:
                    if first.startswith(magic):
                        st["codec"] = name
                        if name == "vorbis" and len(first) >= 16:
                            st["channels"], st["rate"] = first[11], struct.unpack_from("<I", first, 12)[0]
                        elif name == "opus" and len(first) >= 16:
                            st["channels"], st["pre_skip"], st["rate"] = first[9], struct.unpack_from("<H", first, 10)[0], 48000
                        elif name == "flac" and len(first) >= 30:
                            st["rate"] = (int.from_bytes(first[27:30], "big") >> 4)
                            st["channels"] = ((first[29] >> 1) & 7) + 1
                        break
            if granule >= 0:
                st["last_granule"] = granule
            if htype & 4:
                st["eos"] = True
            if pages % 5000 == 0 and time.time() - t0 > limit_s:
                return {"pages": pages, "packets": packets, "streams": streams, "bytes": sizes, "bad": bad, "complete": False, "file_size": size, "read_to": f.tell()}
    return {"pages": pages, "packets": packets, "streams": streams, "bytes": sizes, "bad": bad, "complete": True, "file_size": size, "read_to": size}


def ogg_lines(look, c):
    import dl_prof as P
    if not c["pages"]:
        return
    sizes = c["bytes"]
    st = c["streams"]
    parts = []
    longest = 0.0
    for serial, s in sorted(st.items()):
        dur = None
        if s["last_granule"] is not None and s["rate"]:
            dur = max(0.0, (s["last_granule"] - s["pre_skip"]) / s["rate"])
            longest = max(longest, dur)
        parts.append(f"stream 0x{serial:08x}: {s['codec'] or 'unidentified codec'}" + (f", {s['rate']} Hz" if s["rate"] else "") + (f", {s['channels']} ch" if s["channels"] else "")
                     + f", {s['pages']:,} pages" + (f", {dur:.2f} s from the last granule position" if dur is not None else "") + (", ends with an EOS page" if s["eos"] else ", NO EOS page (cut off or still being written)"))
    look.fact("ogg_pages", c["pages"])
    look.fact("ogg_packets", c["packets"])
    look.fact("ogg_streams", len(st))
    look.line(f"Ogg container: {c['pages']:,} pages ({min(sizes)} to {max(sizes):,} bytes, mean {sum(sizes) // len(sizes):,}), {c['packets']:,} packets, {len(st)} logical stream(s). " + " | ".join(parts) + ".", 94, "container")
    P.counts(look, [("ogg pages", c["pages"]), ("ogg packets", c["packets"]), ("logical streams", len(st)), ("page sync losses", c["bad"] or None)], 95)
    if c["bad"]:
        look.flag("OGG-SYNC", "container", f"{c['bad']} place(s) with no OggS capture pattern where a page should start", "damaged or cut file: pages after the break were found by searching")
    if not c["complete"]:
        look.flag("PARTIAL", "container", f"page walk stopped at byte {c['read_to']:,} of {c['file_size']:,}", "time cap: the counts are lower bounds")
    if st and not all(s["eos"] for s in st.values()):
        look.flag("NO-EOS", "container", "a logical stream has no end-of-stream page", "the file is truncated, or it was a live capture that was never closed")


def wav_counts(path):
    with open(path, "rb") as f:
        h = f.read(12)
        if h[:4] not in (b"RIFF", b"RF64") or h[8:12] != b"WAVE":
            return None
        size = f.seek(0, 2)
        f.seek(12)
        chunks, fmt = [], None
        while f.tell() + 8 <= size and len(chunks) < 200:
            tag, ln = struct.unpack("<4sI", f.read(8))
            at = f.tell()
            if tag == b"fmt " and ln >= 16:
                tag_, ch, rate, _br, align, bits = struct.unpack("<HHIIHH", f.read(16))
                fmt = {"format": tag_, "channels": ch, "rate": rate, "align": align, "bits": bits}
            chunks.append((tag.decode("latin-1"), ln))
            f.seek(at + ln + (ln & 1))
    return {"chunks": chunks, "fmt": fmt, "file_size": size}


def wav_lines(look, c):
    d = next((ln for t, ln in c["chunks"] if t == "data"), None)
    fm = c["fmt"] or {}
    frames = d // fm["align"] if d and fm.get("align") else None
    look.line(f"WAV container: {len(c['chunks'])} chunks (" + ", ".join(f"{t.strip()} {ln:,}" for t, ln in c["chunks"][:12]) + (" ..." if len(c["chunks"]) > 12 else "") + ")"
              + (f"; data {d:,} bytes = {frames:,} sample frames" + (f" = {frames / fm['rate']:.2f} s" if fm.get("rate") else "") if frames else "")
              + (f"; format tag {fm['format']}, {fm['channels']} ch, {fm['rate']} Hz, {fm['bits']} bit" if fm else "") + ".", 94, "container")
    look.fact("wav_chunks", len(c["chunks"]))


def flac_counts(path):
    with open(path, "rb") as f:
        if f.read(4) != b"fLaC":
            return None
        blocks, info = [], None
        while True:
            h = f.read(4)
            if len(h) < 4:
                break
            last, typ, ln = h[0] >> 7, h[0] & 0x7F, int.from_bytes(h[1:], "big")
            body = f.read(ln) if typ == 0 else None
            if body is None:
                f.seek(ln, 1)
            else:
                v = int.from_bytes(body[10:18], "big")
                info = {"rate": v >> 44, "channels": ((v >> 41) & 7) + 1, "bits": ((v >> 36) & 31) + 1, "samples": v & ((1 << 36) - 1), "min_block": struct.unpack(">H", body[0:2])[0],
                        "max_block": struct.unpack(">H", body[2:4])[0]}
            blocks.append((typ, ln))
            if last:
                break
        audio_at = f.tell()
        size = f.seek(0, 2)
    return {"blocks": blocks, "info": info, "audio_bytes": size - audio_at}


FLAC_BLOCKS = {0: "STREAMINFO", 1: "PADDING", 2: "APPLICATION", 3: "SEEKTABLE", 4: "VORBIS_COMMENT", 5: "CUESHEET", 6: "PICTURE"}


def flac_lines(look, c):
    i = c["info"] or {}
    look.line(f"FLAC container: {len(c['blocks'])} metadata blocks (" + ", ".join(f"{FLAC_BLOCKS.get(t, t)} {ln:,}" for t, ln in c["blocks"]) + ")"
              + (f"; {i['samples']:,} samples per channel = {i['samples'] / i['rate']:.2f} s at {i['rate']} Hz, {i['channels']} ch, {i['bits']} bit, block size {i['min_block']} to {i['max_block']}" if i and i.get("rate") else "")
              + f"; {c['audio_bytes']:,} bytes of audio frames.", 94, "container")
    look.fact("flac_blocks", len(c["blocks"]))


BR_MPEG1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]   # Layer III, kbit/s
BR_LSF = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_counts(path, limit_frames=2_000_000):
    """Walk MPEG-1 Layer III frame headers: -> (frames, seconds) or None. An ID3v2 tag is skipped; a lost sync is searched for."""
    with open(path, "rb") as f:
        data = f.read(1 << 28)
    pos = 0
    if data[:3] == b"ID3" and len(data) > 10:
        pos = 10 + ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14 | (data[8] & 0x7F) << 7 | (data[9] & 0x7F))
    frames, secs, lost = 0, 0.0, 0
    while pos + 4 <= len(data) and frames < limit_frames:
        b = data[pos:pos + 4]
        if b[0] == 0xFF and (b[1] & 0xE0) == 0xE0:
            ver, layer, br_i, sr_i, pad = (b[1] >> 3) & 3, (b[1] >> 1) & 3, b[2] >> 4, (b[2] >> 2) & 3, (b[2] >> 1) & 1
            if ver != 1 and layer == 1 and 0 < br_i < 15 and sr_i < 3:
                rate = RATES[ver][sr_i]
                lay3 = ver == 3
                kbps = (BR_MPEG1 if lay3 else BR_LSF)[br_i]
                flen = (144 if lay3 else 72) * kbps * 1000 // rate + pad
                spf = 1152 if lay3 else 576
                if flen > 4:
                    frames += 1
                    secs += spf / rate
                    pos += flen
                    continue
        lost += 1
        nxt = data.find(b"\xff", pos + 1)
        if nxt < 0:
            break
        pos = nxt
    return (frames, secs, lost) if frames else None


def mp3_lines(look, c):
    frames, secs, lost = c
    look.line(f"MP3 container: {frames:,} MPEG Layer III frames = {secs:.2f} s" + (f"; {lost:,} place(s) where the frame chain broke and was searched again" if lost else "; frames chain without a break") + ".", 94, "container")
    look.fact("mp3_frames", frames)


def container_counts(look):
    """Dispatch on the file's subtype; never raises (a failure is a Not-looked-at row)."""
    st = look.subtype
    try:
        if st in ("ogg", "ogv", "opus", "oga"):
            ogg_lines(look, ogg_counts(look.path))
        elif st == "wav":
            c = wav_counts(look.path)
            if c:
                wav_lines(look, c)
        elif st == "flac":
            c = flac_counts(look.path)
            if c:
                flac_lines(look, c)
        elif st == "mp3" and look.size <= 1 << 28:
            c = mp3_counts(look.path)
            if c:
                mp3_lines(look, c)
    except Exception as e:
        look.fail("container counts", "stdlib", e)
