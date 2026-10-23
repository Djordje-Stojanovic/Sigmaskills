"""SigmaDeepLook: the header facts of container files, read from the file's own bytes with the standard library (fix round 11).

A container's header declares counts that a listing tool may not show, or that a run without 7-Zip cannot get: a cabinet's folders
(compression groups), files and data blocks; a zip's end record (entries, central directory, comment); the 7z start header; the RAR
version and flags; the ISO 9660 volume; the OLE sector layout. One fact line each (the cabinet gets a second line per folder). A damaged
or cut header is named, never guessed.
"""
import struct
import zlib

import dl_core as core

CAB_FLAGS = {1: "previous cabinet", 2: "next cabinet", 4: "reserve area"}
CAB_COMPRESSION = {0: "stored", 1: "MSZIP", 2: "Quantum", 3: "LZX"}
RAR4_FLAGS = {0x1: "volume", 0x2: "comment", 0x4: "locked", 0x8: "solid", 0x10: "new volume naming", 0x20: "authenticity", 0x40: "recovery record",
              0x80: "encrypted headers", 0x100: "first volume"}
RAR5_FLAGS = {0x1: "volume", 0x2: "volume number", 0x4: "solid", 0x8: "recovery record", 0x10: "locked"}
HEAD_READ = 8 << 20   # a cabinet's folder and file tables sit in the first bytes; the data blocks after them are never read


def header_facts(look):
    """Dispatch on the first bytes. Only archives, disk images and OLE files get a line."""
    p = look.path
    if p.is_dir() or look.size < 16:
        return
    with open(p, "rb") as f:
        first = f.read(4)
        f.seek(0)
        head = f.read(HEAD_READ if first == b"MSCF" else 512)   # only a cabinet needs more than the first sector
    if head[:4] == b"MSCF":
        cab_facts(look, head)
    elif head[:6] == b"7z\xbc\xaf\x27\x1c":
        sevenz_facts(look, head)
    elif head[:4] == b"Rar!":
        rar_facts(look, head)
    elif head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        ole_facts(look, head)
    elif head[:4] in (b"PK\x03\x04", b"PK\x05\x06") and look.type == "archive":
        zip_facts(look)
    elif look.subtype == "iso" and look.size > 0x8800:
        iso_facts(look)


def cstr(b, at):
    """The NUL-ended string at `at` -> (text, offset after it)."""
    end = b.find(b"\0", at)
    if end < 0:
        end = len(b)
    return b[at:end].decode("latin-1", "replace"), end + 1


def cab_facts(look, b):
    if len(b) < 36:
        look.flag("CORRUPT", "cabinet header", f"{len(b)} bytes; a cabinet header needs 36", "the folders and files are not known")
        return
    cb, coff_files = struct.unpack_from("<I4xI", b, 8)
    vmin, vmaj, nfold, nfiles, flags, set_id, icab = struct.unpack_from("<BBHHHHH", b, 24)
    pos = 36
    cb_folder = 0
    extra = []
    if flags & 4:
        if len(b) < 40:
            look.flag("CORRUPT", "cabinet header", "the reserve sizes are cut off", "")
            return
        cb_header, cb_folder, _cb_data = struct.unpack_from("<HBB", b, 36)
        pos = 40 + cb_header
    if flags & 1:
        name, pos = cstr(b, pos)
        disk, pos = cstr(b, pos)
        extra.append(f"continues from cabinet '{name}' (disk '{disk}')")
    if flags & 2:
        name, pos = cstr(b, pos)
        disk, pos = cstr(b, pos)
        extra.append(f"continues in cabinet '{name}' (disk '{disk}')")
    names = [n for bit, n in CAB_FLAGS.items() if flags & bit]
    problems = []
    if cb != look.size:
        problems.append(f"the header says {cb:,} bytes, the file has {look.size:,}")
    look.fact("cab_folders", nfold)
    look.fact("cab_files", nfiles)
    look.line(f"Cabinet header (CFHEADER, read from the file's own bytes): cabinet size {cb:,} bytes; version {vmaj}.{vmin}; folders (compression groups) {nfold}; "
              f"files {nfiles}; flags 0x{flags:04x} ({', '.join(names) or 'none'}); set id {set_id}; cabinet index {icab}; file entries start at byte {coff_files:,}"
              + ("; " + "; ".join(extra) if extra else "") + (f". Check: {'; '.join(problems)}" if problems else "") + ".", 96, "structure")
    folders = []
    for i in range(nfold):
        at = pos + i * (8 + cb_folder)
        if at + 8 > len(b):
            look.flag("CORRUPT", "cabinet folders", f"folder {i} of {nfold} lies past the bytes read", "the rest of the folder table is not known")
            break
        folders.append(struct.unpack_from("<IHH", b, at))
    members = [[] for _ in folders]
    at = coff_files
    for _ in range(nfiles):
        if at + 16 > len(b):
            look.flag("CORRUPT", "cabinet files", "the file table is cut off", "the files after it are not listed")
            break
        size, _uoff, ifold = struct.unpack_from("<IIH", b, at)
        name, at = cstr(b, at + 16)
        if ifold >= 0xFFFD:   # continued from the previous cabinet (0xFFFD), into the next one (0xFFFE), or both (0xFFFF)
            ifold = len(folders) - 1 if ifold == 0xFFFE else 0
        if 0 <= ifold < len(members):
            members[ifold].append((name, size))
    rows = []
    for i, (_start, blocks, ctype) in enumerate(folders[:16]):
        low = ctype & 0xF
        label = CAB_COMPRESSION.get(low, f"type {ctype:#x}")
        if low == 3:
            label += f" (window 2^{(ctype >> 8) & 0x1F})"
        elif low == 2:
            label += f" (level {(ctype >> 4) & 0xF}, memory 2^{(ctype >> 8) & 0x1F})"
        files = members[i]
        shown = ", ".join(n for n, _ in files[:4]) + (f", +{len(files) - 4} more" if len(files) > 4 else "")
        rows.append(f"folder {i}: {label}, {blocks:,} data blocks, {len(files):,} files ({shown}), {sum(s for _, s in files):,} bytes uncompressed")
    if rows:
        look.line("Cabinet folders: " + "; ".join(rows) + (f"; +{len(folders) - 16} more folders" if len(folders) > 16 else "") + ".", 95, "structure")


def zip_facts(look):
    """The zip end record: how many entries it declares, where the central directory sits, the archive comment."""
    with open(look.path, "rb") as f:
        f.seek(max(0, look.size - 65557))
        tail = f.read()
    at = tail.rfind(b"PK\x05\x06")
    if at < 0 or at + 22 > len(tail):
        return
    _d, _cd, n_disk, total, cd_size, cd_off, clen = struct.unpack_from("<HHHHIIH", tail, at + 4)
    z64 = ""
    if (total == 0xFFFF or cd_off == 0xFFFFFFFF) and at >= 20 and tail[at - 20:at - 16] == b"PK\x06\x07":
        loc = struct.unpack_from("<Q", tail, at - 12)[0]
        with open(look.path, "rb") as f:
            f.seek(loc)
            r = f.read(56)
        if r[:4] == b"PK\x06\x06" and len(r) >= 56:
            total, cd_size, cd_off = struct.unpack_from("<QQQ", r, 32)
            z64 = " (zip64)"
    com = tail[at + 22:at + 22 + clen]
    cm = (f"comment {clen} bytes: '{com[:120].decode('utf-8', 'replace')}'" + ("..." if clen > 120 else "")) if clen else "no comment"
    look.fact("zip_entries_declared", total)
    look.line(f"Zip end record{z64}: {total:,} entries declared (central directory {cd_size:,} bytes at byte {cd_off:,}), {cm}.", 62, "structure")


def sevenz_facts(look, b):
    if len(b) < 32:
        look.flag("CORRUPT", "7z start header", f"{len(b)} bytes; the start header needs 32", "")
        return
    vmaj, vmin = b[6], b[7]
    crc, off, size, ncrc = struct.unpack_from("<IQQI", b, 8)
    ok = zlib.crc32(b[12:32]) & 0xFFFFFFFF == crc
    end = 32 + off + size
    look.line(f"7z start header: format version {vmaj}.{vmin}; next header ({size:,} bytes) at byte {32 + off:,}"
              + (f", which ends at byte {end:,} of a {look.size:,}-byte file" if end != look.size else "")
              + ("" if ok else "; the start header's own check value does not match")
              + (" (the file looks cut short or has extra bytes)" if end > look.size else "") + ".", 90, "structure")


def vint(b, at):
    """A RAR 5 variable-length integer -> (value, next offset)."""
    v = shift = 0
    while at < len(b) and shift < 64:
        c = b[at]
        v |= (c & 0x7F) << shift
        at += 1
        if not c & 0x80:
            return v, at
        shift += 7
    return None, at


def rar_facts(look, b):
    if b[:7] == b"Rar!\x1a\x07\x00" and len(b) >= 20:
        _crc, typ, flags, size = struct.unpack_from("<HBHH", b, 7)
        names = [n for bit, n in RAR4_FLAGS.items() if flags & bit]
        look.line(f"RAR 4.x archive: main header {'found' if typ == 0x73 else 'not found where expected'}, flags 0x{flags:04x} ({', '.join(names) or 'none'})"
                  + ("; the file names are encrypted" if flags & 0x80 else "") + ".", 90, "structure")
    elif b[:8] == b"Rar!\x1a\x07\x01\x00" and len(b) >= 20:
        _size, at = vint(b, 12)
        typ, at = vint(b, at)
        hflags, at = vint(b, at)
        if hflags is not None and hflags & 1:
            _extra, at = vint(b, at)
        if hflags is not None and hflags & 2:
            _data, at = vint(b, at)
        aflags, at = vint(b, at) if typ == 1 else (None, at)
        names = [n for bit, n in RAR5_FLAGS.items() if aflags and aflags & bit]
        look.line(f"RAR 5.x archive: main header {'found' if typ == 1 else 'not found where expected'}"
                  + (f", archive flags 0x{aflags:x} ({', '.join(names) or 'none'})" if aflags is not None else "") + ".", 90, "structure")


def ole_entry_kinds(path, shift, first_dir, first_difat, ndifat, cap=20000):
    """-> ({entry type: count}, complete) over the directory chain of an OLE file (type 1 storage, 2 stream, 5 root). The FAT is read one
    entry at a time, through the header's 109 FAT sector numbers and the DIFAT chain; {} when the chain cannot be followed."""
    ssz = 1 << shift
    per = ssz // 4
    out, complete = {}, True
    try:
        with open(path, "rb") as f:
            hdr = f.read(512)
            fats = [s for s in struct.unpack_from("<109I", hdr, 76) if s < 0xFFFFFFFA]
            d, n = first_difat, 0
            while d < 0xFFFFFFFA and n < min(ndifat, 4096):   # the DIFAT sectors list the FAT sectors past the first 109
                f.seek((d + 1) * ssz)
                blk = f.read(ssz)
                if len(blk) < ssz:
                    break
                ids = struct.unpack(f"<{per}I", blk)
                fats += [s for s in ids[:-1] if s < 0xFFFFFFFA]
                d, n = ids[-1], n + 1

            def following(sec):
                k, i = divmod(sec, per)
                if k >= len(fats):
                    return None
                f.seek((fats[k] + 1) * ssz + 4 * i)
                v = f.read(4)
                return struct.unpack("<I", v)[0] if len(v) == 4 else None
            sec, seen = first_dir, 0
            while sec is not None and sec < 0xFFFFFFFA:
                if seen >= cap // (ssz // 128):
                    complete = False
                    break
                f.seek((sec + 1) * ssz)   # sector 0 follows the header sector (512 bytes for version 3, 4096 for version 4)
                blk = f.read(ssz)
                for i in range(0, len(blk) - 127, 128):
                    if blk[i + 66] in (1, 2, 5) and struct.unpack_from("<H", blk, i + 64)[0] >= 2:
                        out[blk[i + 66]] = out.get(blk[i + 66], 0) + 1
                sec, seen = following(sec), seen + 1
    except (OSError, struct.error):
        return {}, False
    return out, complete


def ole_facts(look, b):
    if len(b) < 76:
        look.flag("CORRUPT", "OLE header", f"{len(b)} bytes; an OLE header needs 76", "")
        return
    minor, major, order, shift, mshift = struct.unpack_from("<HHHHH", b, 24)
    ndir, nfat, first_dir, _tx, cutoff, first_mfat, nmfat, first_difat, ndifat = struct.unpack_from("<9I", b, 40)
    if major not in (3, 4) or not 7 <= shift <= 16:
        look.flag("CORRUPT", "OLE header", f"version {major}.{minor}, sector shift {shift}", "not a valid compound file header")
        return
    kinds, complete = ole_entry_kinds(look.path, shift, first_dir, first_difat, ndifat)
    look.line(f"OLE compound file header: version {major}.{minor}; sector size {1 << shift} bytes (mini sector {1 << mshift}); {nfat} FAT sectors; "
              + (f"{ndir} directory sectors; " if major == 4 else "") + f"first directory sector {first_dir}; mini stream cutoff {cutoff}; {nmfat} mini FAT sectors; "
              f"{ndifat} DIFAT sectors" + (f"; directory: {kinds.get(2, 0)} streams, {kinds.get(1, 0)} storages" + ("" if complete else " (the first entries only)") if kinds else "") + ".", 55, "structure")


def iso_facts(look):
    with open(look.path, "rb") as f:
        f.seek(0x8000)
        b = f.read(0x1000)
    if len(b) < 0x800 or b[1:6] != b"CD001":
        return
    types = []
    for k in range(0, len(b), 0x800):
        if b[k + 1:k + 6] != b"CD001":
            break
        types.append(b[k])
        if b[k] == 255:
            break
    pvd = b[:0x800] if b[0] == 1 else None
    if pvd is None:
        return

    def txt(a, z):
        return pvd[a:z].decode("latin-1", "replace").strip(" \x00")
    blocks = struct.unpack_from("<I", pvd, 80)[0]
    bs = struct.unpack_from("<H", pvd, 128)[0]
    made = txt(813, 830)
    bits = [f"volume id '{txt(40, 72)}'", f"system id '{txt(8, 40)}'", f"{blocks:,} blocks of {bs:,} bytes ({core.human(blocks * bs)})"]
    if len(made) >= 14 and made[:14].isdigit():
        bits.append(f"created {made[:4]}-{made[4:6]}-{made[6:8]} {made[8:10]}:{made[10:12]}:{made[12:14]}")
    for label, a, z in (("publisher", 318, 446), ("preparer", 446, 574), ("application", 574, 702)):
        if txt(a, z):
            bits.append(f"{label} '{txt(a, z)[:60]}'")
    kinds = {0: "boot record (El Torito)", 2: "Joliet or enhanced volume descriptor"}
    extra = [kinds[t] for t in dict.fromkeys(types) if t in kinds]
    look.line("ISO 9660 primary volume descriptor: " + "; ".join(bits) + (f"; also has a {' and a '.join(extra)}" if extra else "") + ".", 88, "structure")
