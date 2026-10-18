"""SigmaDeepLook: VBA macro projects read with the standard library only (nothing is run, nothing is opened in Office).

An OLE compound file (a vbaProject.bin inside .xlsm/.docm/.pptm, or a legacy .doc/.xls/.ppt) keeps each module as a stream in the
MS-OVBA compressed container. This reads the compound file, finds every compressed module (the container always starts with 0x01 and
a first chunk whose first literal run spells `Attribut`), decompresses it, and reports the module source facts: procedure names,
auto-run routines, suspicious call keywords and quoted strings (URLs, paths, commands)."""
import math
import re
import struct

FREE, ENDCHAIN = 0xFFFFFFFF, 0xFFFFFFFE
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

AUTO_EXEC = ["AutoOpen", "Auto_Open", "AutoExec", "AutoClose", "Auto_Close", "AutoNew", "Document_Open", "Document_New", "Document_Close",
             "Workbook_Open", "Workbook_Activate", "Workbook_BeforeClose", "Presentation_Open", "Auto_Activate", "Worksheet_Change", "Worksheet_Activate"]
SUSPICIOUS = ["Shell", "CreateObject", "GetObject", "WScript", "Wscript.Shell", "PowerShell", "URLDownloadToFile", "URLDownloadToFileA", "XMLHTTP", "WinHttp",
              "ADODB.Stream", "Scripting.FileSystemObject", "Environ", "CallByName", "Declare Function", "Declare PtrSafe", "VirtualAlloc", "RtlMoveMemory",
              "cmd.exe", "cmd /c", "mshta", "regsvr32", "rundll32", "certutil", "bitsadmin", "SaveToFile", "Open For Binary", "Kill", "SendKeys", "Chr(", "StrReverse",
              "MacroOptions", "Application.Run", "ShellExecute", "Win32_Process", "ExecuteExcel4Macro", "VBProject", "SetWindowsHookEx"]


# ---------------------------------------------------------------- OLE compound file reader
def read_cfb(data):
    """-> {stream path: bytes} for every stream of an OLE compound file (storages are path prefixes). {} when it is not one."""
    if data[:8] != OLE_MAGIC or len(data) < 512:
        return {}
    shift, mshift = struct.unpack_from("<HH", data, 30)
    ssz, msz = 1 << shift, 1 << mshift
    n_fat, first_dir, _tx, cutoff, first_mfat, n_mfat, first_difat, n_difat = struct.unpack_from("<8I", data, 44)

    def sector(i):
        o = 512 + i * ssz
        return data[o:o + ssz]
    difat = list(struct.unpack_from("<109I", data, 76))
    s, seen = first_difat, 0
    while s < FREE - 1 and seen < n_difat + 1 and seen < 4096:
        blk = struct.unpack(f"<{ssz // 4}I", sector(s).ljust(ssz, b"\0"))
        difat += blk[:-1]
        s = blk[-1]
        seen += 1
    fat = []
    for sec in difat:
        if sec >= FREE - 1:
            continue
        fat += struct.unpack(f"<{ssz // 4}I", sector(sec).ljust(ssz, b"\0"))

    def chain(start, table, limit=1 << 20):
        out, s = [], start
        while s < FREE - 1 and s < len(table) and len(out) < limit:
            out.append(s)
            s = table[s]
        return out

    def read_chain(start, size=None):
        b = b"".join(sector(s) for s in chain(start, fat))
        return b if size is None else b[:size]
    d = read_chain(first_dir)
    ents = []
    for i in range(0, len(d) - 127, 128):
        nlen = struct.unpack_from("<H", d, i + 64)[0]
        typ = d[i + 66]
        left, right, child = struct.unpack_from("<III", d, i + 68)
        start, size = struct.unpack_from("<IQ", d, i + 116)
        name = d[i:i + max(0, nlen - 2)].decode("utf-16-le", "replace")
        ents.append((name, typ, left, right, child, start, size))
    if not ents:
        return {}
    root = ents[0]
    ministream = read_chain(root[5], root[6])
    mfat = []
    if first_mfat < FREE - 1:
        mfat = list(struct.unpack(f"<{len(read_chain(first_mfat)) // 4}I", read_chain(first_mfat)))

    def stream(e):
        _n, _t, _l, _r, _c, start, size = e
        if size < cutoff:
            b = b"".join(ministream[s * msz:(s + 1) * msz] for s in chain(start, mfat))
            return b[:size]
        return read_chain(start, size)
    out = {}

    def walk(i, prefix, depth=0):
        stack = [i]
        guard = set()
        while stack:
            k = stack.pop()
            if k >= len(ents) or k in guard or depth > 20:
                continue
            guard.add(k)
            e = ents[k]
            stack += [e[2], e[3]]
            path = prefix + e[0]
            if e[1] == 2 and e[6] < (64 << 20):
                try:
                    out[path] = stream(e)
                except Exception:
                    pass
            elif e[1] == 1 and e[4] < len(ents):
                walk(e[4], path + "/", depth + 1)
    if root[4] < len(ents):
        walk(root[4], "")
    return out


# ---------------------------------------------------------------- MS-OVBA decompression
def decompress(data):
    """The MS-OVBA compressed container (starts with 0x01) -> bytes. Raises ValueError when it is not one."""
    if not data or data[0] != 1:
        raise ValueError("no 0x01 signature")
    out, i = bytearray(), 1
    while i + 2 <= len(data):
        hdr = struct.unpack_from("<H", data, i)[0]
        if (hdr >> 12) & 7 != 3:
            break
        size = (hdr & 0x0FFF) + 3
        chunk = data[i + 2:i + size]
        i += size
        if not hdr & 0x8000:
            out += chunk[:4096]
            continue
        start, j = len(out), 0
        while j < len(chunk):
            flags = chunk[j]
            j += 1
            for bit in range(8):
                if j >= len(chunk):
                    break
                if not (flags >> bit) & 1:
                    out.append(chunk[j])
                    j += 1
                else:
                    tok = struct.unpack_from("<H", chunk, j)[0] if j + 2 <= len(chunk) else 0
                    j += 2
                    done = len(out) - start
                    bits = max((done - 1).bit_length(), 4) if done > 0 else 4
                    length = (tok & (0xFFFF >> bits)) + 3
                    off = (tok >> (16 - bits)) + 1
                    if off > len(out) - start:
                        raise ValueError("bad copy token")
                    for _ in range(length):
                        out.append(out[-off])
    return bytes(out)


def modules(streams):
    """-> [(stream path, source text)] for every stream that holds a compressed VBA module."""
    found = []
    for path, b in streams.items():
        k = b.find(b"\x00Attribut")
        while k >= 3 and b[k - 3] == 1:
            try:
                src = decompress(b[k - 3:]).decode("latin-1")
            except ValueError:
                break
            if "Attribute" in src[:200] or "Sub " in src or "Function " in src:
                found.append((path, src))
            break
    return found


# ---------------------------------------------------------------- facts from source
PROC_RE = re.compile(r"(?im)^\s*(?:(?:public|private|friend|static)\s+)?(sub|function|property\s+(?:get|let|set))\s+([A-Za-z_]\w*)")
STR_RE = re.compile(r'"((?:[^"\r\n]|"")*)"')
INTERESTING_STR = re.compile(r"(?i)(https?://|ftp://|\\\\|[a-z]:\\|%\w+%|\.(exe|dll|bat|cmd|ps1|vbs|js|hta|scr)\b|powershell|cmd\b|wscript|regsvr|-enc|\.run|/c\s)")


def analyse(streams):
    """-> dict(modules, procs, auto, suspicious, strings, urls) from a stream map."""
    mods = modules(streams)
    procs, auto, sus, strs = [], set(), {}, []
    for path, src in mods:
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("'", "Attribute ")))
        procs += [(path.split("/")[-1], m.group(2)) for m in PROC_RE.finditer(code)]
        for a in AUTO_EXEC:
            if re.search(r"(?im)^\s*(?:(?:public|private)\s+)?(?:sub|function)\s+" + re.escape(a) + r"\b", code):
                auto.add(a)
        for k in SUSPICIOUS:
            n = len(re.findall((r"(?<!\w)" if k[0].isalnum() else "") + re.escape(k) + (r"\b" if k[-1].isalnum() else ""), code, re.I))
            if n:
                sus[k] = sus.get(k, 0) + n
        for m in STR_RE.finditer(code):
            s = m.group(1).replace('""', '"')
            if len(s) >= 5:
                strs.append(s)
    seen, uniq = set(), []
    for s in strs:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return {"modules": mods, "procs": procs, "auto": sorted(auto), "suspicious": sus, "strings": uniq,
            "interesting": [s for s in uniq if INTERESTING_STR.search(s)]}


def vba_facts(look, data, name):
    """Print the macro facts of an OLE file's bytes (stdlib). Returns True when a VBA module was found."""
    try:
        streams = read_cfb(data)
        r = analyse(streams)
    except Exception as e:
        look.fail("macro source (stdlib reader)", "stdlib", e)
        return False
    if not r["modules"]:
        look.line(f"Macro project present in {name} but no readable VBA module source (the project may be password-locked, p-code only or stomped).", 70)
        return False
    mods = r["modules"]
    look.fact("vba_modules", [p for p, _ in mods])
    look.line(f"VBA macro project in {name}: {len(mods)} module(s) " + ", ".join(f"{p.split('/')[-1]} ({len(s.splitlines())} lines)" for p, s in mods[:12])
              + f"; procedures: {', '.join(f'{m}.{p}' for m, p in r['procs'][:25]) or 'none'}" + (f" (+{len(r['procs']) - 25} more)" if len(r["procs"]) > 25 else "") + ".", 90)
    if r["auto"]:
        look.flag("AUTO-EXEC-MACRO", name, ", ".join(r["auto"][:6]), "runs by itself when the file is opened (macro security permitting); never open it to see")
    if r["suspicious"]:
        look.flag("SUSPICIOUS-MACRO", name, ", ".join(sorted(r["suspicious"])[:8]), "calls that download, run or write files")
    look.line(f"Macro keywords: auto-run {r['auto'] or 'none'}; suspicious calls {dict(sorted(r['suspicious'].items(), key=lambda kv: -kv[1])[:12]) or 'none'}.", 89)
    if r["interesting"]:
        look.line("Macro strings that look like URLs, paths or commands: " + " | ".join(s[:100] for s in r["interesting"][:12]) + (f" (+{len(r['interesting']) - 12} more)" if len(r["interesting"]) > 12 else "") + ".", 88)
    look.write_text("vba_source.txt", "\n\n".join(f"' ===== module {p} =====\n{s}" for p, s in mods), "decompressed VBA module source (read only, never run)")
    if r["strings"]:
        look.write_text("vba_strings.txt", "\n".join(r["strings"]), "every quoted string of 5+ characters in the macro source")
    look.step("VBA modules (MS-OVBA decompression)", "stdlib")
    return True
