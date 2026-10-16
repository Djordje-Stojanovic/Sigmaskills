"""SigmaDeepLook: more of a Windows PE from the standard library alone (nothing is executed, nothing is loaded).

Header timestamp (and when not to believe it), debug directory (PDB path, reproducible-build marker), embedded Authenticode signature
(signer read from the PKCS#7 block when `cryptography` is present; the chain and the file hash are NOT verified here), overlay, .NET
header, import functions grouped by what they let a program do.
"""
import re
import struct
import time

import dl_core as core

DEBUG_TYPES = {1: "COFF", 2: "CodeView", 9: "Borland", 12: "CLSID", 13: "VC feature", 14: "POGO", 16: "reproducible build marker", 20: "extended DLL characteristics"}

API_GROUPS = {
    "process injection": ("VirtualAllocEx", "WriteProcessMemory", "CreateRemoteThread", "NtUnmapViewOfSection", "QueueUserAPC", "SetThreadContext", "NtWriteVirtualMemory", "RtlCreateUserThread"),
    "network": ("InternetOpen", "InternetConnect", "HttpSendRequest", "HttpOpenRequest", "WinHttpOpen", "WinHttpConnect", "WSAStartup", "URLDownloadToFile", "getaddrinfo", "gethostbyname", "InternetReadFile"),
    "registry or service persistence": ("RegSetValue", "RegCreateKey", "CreateService", "StartService", "ChangeServiceConfig", "SetWindowsHookEx"),
    "cryptography": ("CryptEncrypt", "CryptDecrypt", "CryptAcquireContext", "BCryptEncrypt", "BCryptDecrypt", "CryptGenKey", "CryptHashData"),
    "debugger checks": ("IsDebuggerPresent", "CheckRemoteDebuggerPresent", "NtQueryInformationProcess", "OutputDebugString"),
    "keyboard or screen capture": ("GetAsyncKeyState", "GetKeyboardState", "GetForegroundWindow", "BitBlt", "GetDC", "SetWindowsHookEx"),
    "process or file execution": ("CreateProcess", "ShellExecute", "WinExec", "CreateProcessAsUser"),
    "token or privilege change": ("AdjustTokenPrivileges", "OpenProcessToken", "ImpersonateLoggedOnUser", "DuplicateToken"),
}


def timestamp_text(ts, debug_entries=()):
    """-> (text, flag_or_None). The PE header timestamp is whatever the linker wrote; it is not a reliable build time."""
    if not ts:
        return "header timestamp 0 (none recorded)", None
    when = time.strftime("%Y-%m-%d", time.gmtime(ts))
    repro = any(e["type"] == 16 for e in debug_entries)
    if repro:
        return f"header timestamp {when} is a hash, not a time (reproducible build)", ("TIMESTAMP-UNRELIABLE", "reproducible-build marker in the debug directory")
    if ts > time.time() + 86400:
        return f"header timestamp {when} is in the future", ("TIMESTAMP-UNRELIABLE", "later than today: forged or garbage")
    if ts < 725846400:   # 1993-01-01: Windows NT 3.1 shipped in 1993; earlier values are placeholders
        return f"header timestamp {when} (before PE files existed: a placeholder, not a build date)", ("TIMESTAMP-UNRELIABLE", "predates the PE format")
    return f"header timestamp {when} (what the linker wrote; can be forged or zeroed)", None


def data_dirs(b):
    off = struct.unpack_from("<I", b, 0x3C)[0]
    opt = off + 24
    magic = struct.unpack_from("<H", b, opt)[0]
    ddir = opt + (112 if magic == 0x20B else 96)
    n = struct.unpack_from("<I", b, ddir - 4)[0]
    return [struct.unpack_from("<II", b, ddir + 8 * i) for i in range(min(n, 16))], magic == 0x20B


def rva_to_off(secs, rva):
    for s in secs:
        if s["va"] <= rva < s["va"] + max(s["vsize"], s["raw"]):
            return rva - s["va"] + s["rptr"]
    return None


def debug_entries(b, dirs, secs):
    rva, size = dirs[6] if len(dirs) > 6 else (0, 0)
    if not rva:
        return []
    o = rva_to_off(secs, rva)
    out = []
    if o is None:
        return out
    for i in range(min(size // 28, 16)):
        try:
            _ch, ts, _ma, _mi, typ, sz, _rva, ptr = struct.unpack_from("<IIHHIIII", b, o + 28 * i)
        except struct.error:
            break
        e = {"type": typ, "name": DEBUG_TYPES.get(typ, f"type {typ}"), "ts": ts}
        if typ == 2 and ptr and ptr + 24 <= len(b) and b[ptr:ptr + 4] == b"RSDS":
            end = b.find(b"\0", ptr + 24, ptr + 24 + 400)
            e["pdb"] = b[ptr + 24:end if end > 0 else ptr + 24].decode("utf-8", "replace")
        out.append(e)
    return out


def signature_block(b, dirs):
    off, size = dirs[4] if len(dirs) > 4 else (0, 0)
    if not off or not size or off + size > len(b) + 8:
        return None
    return b[off + 8:off + size]


def signer_info(block):
    """-> list of dicts for the certificates in an Authenticode PKCS#7 block, or None when cryptography is unavailable."""
    if not core.have_module("cryptography"):
        return None
    from cryptography.hazmat.primitives.serialization import pkcs7
    try:
        certs = pkcs7.load_der_pkcs7_certificates(bytes(block).rstrip(b"\0"))
    except Exception:
        return []
    out = []
    for c in certs:
        try:
            nb, na = c.not_valid_before_utc, c.not_valid_after_utc
        except AttributeError:
            nb, na = c.not_valid_before, c.not_valid_after
        cn = lambda n: next((a.value for a in n if a.oid._name == "commonName"), n.rfc4514_string()[:60])   # noqa: E731
        out.append({"subject": cn(c.subject), "issuer": cn(c.issuer), "not_before": nb.strftime("%Y-%m-%d"), "not_after": na.strftime("%Y-%m-%d"), "self": c.subject == c.issuer})
    return out


def overlay(b, secs, dirs, size):
    end = max((s["rptr"] + s["raw"] for s in secs), default=0)
    sig_off, sig_size = dirs[4] if len(dirs) > 4 else (0, 0)
    ov = size - end - (sig_size if sig_off and sig_off >= end else 0)
    return max(0, ov), end


def import_functions(b, dirs, secs, is64, cap_per_dll=300, cap_total=4000):
    rva, _ = dirs[1] if len(dirs) > 1 else (0, 0)
    out, total = {}, 0
    p = rva_to_off(secs, rva) if rva else None
    step = 8 if is64 else 4
    flag = 1 << (63 if is64 else 31)
    while p is not None and p + 20 <= len(b) and len(out) < 300:
        d = struct.unpack_from("<5I", b, p)
        if not any(d):
            break
        no = rva_to_off(secs, d[3])
        if no is None:
            p += 20
            continue
        dll = b[no:b.find(b"\0", no)].decode("latin-1")
        t = rva_to_off(secs, d[0] or d[4])
        names = []
        while t is not None and t + step <= len(b) and len(names) < cap_per_dll and total < cap_total:
            v = int.from_bytes(b[t:t + step], "little")
            if v == 0:
                break
            if not v & flag:
                no2 = rva_to_off(secs, v & 0x7FFFFFFF)
                if no2 is not None:
                    names.append(b[no2 + 2:b.find(b"\0", no2 + 2)].decode("latin-1"))
                    total += 1
            else:
                names.append(f"#{v & 0xFFFF}")
            t += step
        out[dll] = names
        p += 20
    return out


def api_groups(imports):
    """{group: [functions]} for the imported function names (matched by prefix, case-sensitive like the Windows names)."""
    hit = {}
    allnames = [n for names in imports.values() for n in names]
    for g, keys in API_GROUPS.items():
        found = sorted({n for n in allnames for k in keys if n == k or n == k + "A" or n == k + "W" or n == k + "ExA" or n == k + "ExW" or (k.endswith("_") and n.startswith(k))})
        if found:
            hit[g] = found
    return hit


def extras(look, b, info):
    """Add the stdlib PE facts to the Look. `info` is dl_bins.parse_pe's result (sections carry va/vsize/raw/rptr)."""
    try:
        dirs, is64 = data_dirs(b)
    except (struct.error, IndexError):
        return
    secs = info["sections"]
    dbg = debug_entries(b, dirs, secs)
    text, flag = timestamp_text(info["timestamp"], dbg)
    look.fact("pe_timestamp", info["timestamp"])
    if flag:
        look.flag(flag[0], "PE header", text, flag[1])
    pdb = next((e["pdb"] for e in dbg if e.get("pdb")), None)
    look.line(f"Build: {text}." + (f" Debug directory: {', '.join(e['name'] for e in dbg)}." if dbg else ""), 60)
    if pdb:
        look.line(f"PDB path baked into the file: {pdb[:160]} (reveals the builder's folders and sometimes a user name).", 66)
        look.fact("pdb_path", pdb)
    clr = dirs[14] if len(dirs) > 14 else (0, 0)
    if clr[0]:
        look.flag("DOTNET", "PE header", "managed (.NET) assembly", "the native sections are a stub; the code is in the .NET metadata, which needs a .NET reader")
        look.fact("dotnet", True)
    blk = signature_block(b, dirs)
    if blk:
        who = signer_info(blk)
        if who is None:
            look.line("Embedded Authenticode signature present; the signer name needs the cryptography package. The chain and file hash are not verified in any case.", 64)
            look.skip("signer name of the embedded signature", "python package cryptography not importable", "cryptography")
        elif who:
            leaf = next((c for c in who if not c["self"]), who[0])
            look.line(f"Embedded Authenticode signature: signer {leaf['subject']!r} (issuer {leaf['issuer']!r}, certificate valid {leaf['not_before']} to {leaf['not_after']}); {len(who)} certificate(s) in the block. "
                      "Chain and file hash are NOT verified here: 'signed' is a claim until Get-AuthenticodeSignature or signtool says Valid.", 66)
            look.fact("signer", leaf["subject"])
        else:
            look.line("Embedded signature block present but unreadable as PKCS#7.", 60)
            look.flag("SIGNATURE-UNREADABLE", "PE security directory", "PKCS#7 did not parse", "treat the file as unsigned")
    else:
        look.line("No embedded signature. Windows system files are usually signed through a catalog instead, which this look cannot see; unsigned here does not mean unsigned there.", 55)
    look.fact("signed_embedded", bool(blk))
    ov, end = overlay(b, secs, dirs, len(b))
    if ov > 1024:
        look.line(f"Overlay: {core.human(ov)} of data after the last section (installers, appended payloads and signatures live here); entropy {core.entropy(b[end:end + min(ov, 1 << 20)]):.2f}.", 58)
        look.fact("overlay_bytes", ov)
    imps = import_functions(b, dirs, secs, is64)
    if imps:
        nf = sum(len(v) for v in imps.values())
        look.fact("import_function_count", nf)
        top = sorted(imps.items(), key=lambda kv: -len(kv[1]))[:5]
        look.line(f"Imports: {nf} functions from {len(imps)} DLLs (most: " + ", ".join(f"{d} {len(v)}" for d, v in top) + ").", 56)
        groups = api_groups(imps)
        if groups:
            look.line("What the imports allow (by name, not proof of behaviour): " + "; ".join(f"{g}: {', '.join(v[:4])}" for g, v in list(groups.items())[:5]) + ".", 64)
            look.fact("api_groups", {g: v[:8] for g, v in groups.items()})
        low = {n for v in imps.values() for n in v}
        if nf < 12 and {"LoadLibraryA", "LoadLibraryW", "GetProcAddress"} & low:
            look.flag("FEW-IMPORTS", "import table", f"only {nf} imports, including LoadLibrary/GetProcAddress", "resolves its real APIs at run time: packed or obfuscated")
        look.write_text("imports.txt", "\n".join(f"{d}: " + ", ".join(v) for d, v in imps.items()), "every imported function by DLL", value=3, inline=False)
