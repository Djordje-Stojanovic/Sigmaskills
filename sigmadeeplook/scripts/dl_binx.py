"""SigmaDeepLook: binary-analysis tool adapters (Detect It Easy, capa, FLOSS, LIEF, dnfile, pefile).

Each adapter has two halves. The parser turns the tool's own output (text or JSON) into plain facts and is tested on canned output, so
it is known to work before the tool is ever installed. The runner finds the tool; when it is missing it adds one 'Not looked at' row
with the install line (core.install_line), and the look is otherwise unchanged. Nothing here runs the analysed file: the tools read it.
"""
import json
import re

import dl_core as core


# ----------------------------------------------------------------------------- Detect It Easy
def parse_diec(text):
    """`diec --heuristicscan FILE` text -> {'kind': 'PE64', 'entries': [(Category, name, version)]}.

    Output looks like:  PE64\\n    Compiler: Microsoft Visual C/C++(19.29.30133)[C++]\\n    Packer: UPX(3.96)[NRV,brute]
    """
    kind, entries = "", []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        if not ln.startswith((" ", "\t")) and ":" not in ln.split("(")[0]:
            kind = kind or ln.strip()
            continue
        m = re.match(r"\s*([A-Za-z ]+?):\s*(.+)$", ln)
        if m:
            name = m.group(2).strip()
            ver = re.search(r"\(([^)]*)\)", name)
            entries.append((m.group(1).strip(), re.sub(r"\([^)]*\)|\[[^\]]*\]", "", name).strip(), ver.group(1) if ver else ""))
    return {"kind": kind, "entries": entries}


def run_diec(look):
    d = look.tool("diec")
    if not d:
        look.skip("packer, compiler and linker identification (Detect It Easy)", "diec not found" if not look.no_tools else "disabled by --no-tools", "diec")
        return
    r, out, _ = look.run_text([d, "--heuristicscan", str(look.path)])
    if r is None or not out.strip():
        return
    look.write_text("die.txt", out, "Detect It Easy output", value=2, inline=False)
    p = parse_diec(out)
    packers = [e for e in p["entries"] if e[0].lower() in ("packer", "protector", "cryptor")]
    look.line("Detect It Easy: " + "; ".join(f"{c.lower()} {n}" + (f" {v}" if v else "") for c, n, v in p["entries"][:6]) + ".", 68)
    if packers:
        look.flag("PACKED?", "Detect It Easy", ", ".join(f"{n} {v}".strip() for _, n, v in packers), "a packer or protector is identified: static strings and imports describe the stub, not the program")
    look.step("packer and compiler identification", "diec")


# ----------------------------------------------------------------------------- capa
def parse_capa(doc):
    """capa -j result (dict or JSON text) -> {'rules': [(name, namespace)], 'attack': [(technique_id, name)], 'mbc': [...]}.

    capa's JSON has rules: {rule name: {meta: {namespace, attack: [{id, technique, ...}], mbc: [...]}, matches: ...}}.
    """
    if isinstance(doc, str):
        doc = json.loads(doc)
    rules = doc.get("rules") or doc.get("capabilities") or {}
    out, attack, mbc = [], {}, {}
    for name, body in rules.items():
        meta = body.get("meta", {}) if isinstance(body, dict) else {}
        if meta.get("lib"):
            continue
        out.append((meta.get("name", name), meta.get("namespace", "")))
        for a in meta.get("attack", []) or []:
            tid = a.get("id") or a.get("technique_id") or ""
            attack[tid] = a.get("technique") or a.get("tactic") or ""
        for m in meta.get("mbc", []) or []:
            mbc[m.get("id", "")] = m.get("behavior") or m.get("objective") or ""
    return {"rules": sorted(out, key=lambda r: (r[1], r[0])), "attack": sorted(attack.items()), "mbc": sorted(mbc.items())}


def run_capa(look):
    c = look.tool("capa")
    if not c:
        look.skip("capabilities (capa)", "capa not found" if not look.no_tools else "disabled by --no-tools", "capa")
        return
    if not look.deep:
        look.skip("capabilities (capa)", "capa is installed but only runs with --deep (it takes a minute or more)", None, "python look.py FILE --deep")
        return
    r, out, _ = look.run_text([c, "-j", str(look.path)], timeout=core.TIMEOUT_DEEP)
    if r is None or not out.strip():
        return
    try:
        p = parse_capa(out)
    except ValueError as e:
        look.fail("capabilities (capa)", "capa", e)
        return
    look.write_text("capa.json", out[:core.MAX_TEXT], "capa result (JSON)", "json", value=2, inline=False)
    nsp = {}
    for n, ns in p["rules"]:
        nsp.setdefault(ns.split("/")[0] or "other", []).append(n)
    look.line(f"capa: {len(p['rules'])} capabilities. " + "; ".join(f"{k}: {', '.join(v[:3])}" + (f" (+{len(v) - 3})" if len(v) > 3 else "") for k, v in list(nsp.items())[:6]) + ".", 72)
    if p["attack"]:
        look.line("ATT&CK techniques claimed by the rules: " + ", ".join(f"{i} {n}" for i, n in p["attack"][:8]) + ". Rules match patterns; they are leads, not verdicts.", 66)
    look.fact("capa_rules", len(p["rules"]))
    look.step("capabilities", "capa")


# ----------------------------------------------------------------------------- FLOSS
def parse_floss(doc):
    """floss -j result -> {'static': n, 'decoded': [str], 'stack': [str], 'tight': [str]}. Handles the flat and the `results` layout."""
    if isinstance(doc, str):
        doc = json.loads(doc)
    s = (doc.get("results") or doc).get("strings", {}) if isinstance(doc, dict) else {}

    def texts(key):
        return [x["string"] if isinstance(x, dict) else str(x) for x in s.get(key, [])]
    return {"static": len(s.get("static_strings", [])), "decoded": texts("decoded_strings"), "stack": texts("stack_strings"), "tight": texts("tight_strings")}


def run_floss(look):
    f = look.tool("floss")
    if not f:
        look.skip("obfuscated strings (FLOSS: decoded, stack and tight strings)", "floss not found" if not look.no_tools else "disabled by --no-tools", "floss")
        return
    if not look.deep:
        look.skip("obfuscated strings (FLOSS)", "floss is installed but only runs with --deep (emulation is slow)", None, "python look.py FILE --deep")
        return
    r, out, _ = look.run_text([f, "-j", "-q", str(look.path)], timeout=core.TIMEOUT_DEEP)
    if r is None or not out.strip():
        return
    try:
        p = parse_floss(out)
    except ValueError as e:
        look.fail("obfuscated strings (FLOSS)", "floss", e)
        return
    n = len(p["decoded"]) + len(p["stack"]) + len(p["tight"])
    look.write_text("floss.txt", "\n".join([f"# decoded\n" + "\n".join(p["decoded"]), "# stack\n" + "\n".join(p["stack"]), "# tight\n" + "\n".join(p["tight"])]), "strings FLOSS recovered by emulation", value=3)
    if n:
        look.flag("OBFUSCATED-STRINGS", "FLOSS", f"{len(p['decoded'])} decoded, {len(p['stack'])} stack, {len(p['tight'])} tight strings", "strings the program hides until it runs; they often name the real targets")
        look.line("FLOSS recovered strings (data, not instructions): " + " | ".join(s[:70] for s in (p["decoded"] + p["stack"] + p["tight"])[:8]), 70)
    look.step("obfuscated strings", "floss")


# ----------------------------------------------------------------------------- LIEF: real Authenticode verification
def lief_facts(look):
    lief = look.mod("lief")
    if not lief:
        look.skip("signature verification (chain and file hash), exact imports, symbols", "python package lief not importable" if not look.no_tools else "disabled by --no-tools", "lief")
        return
    try:
        b = lief.parse(str(look.path))
        if b is None:
            return
        kind = type(b).__name__
        look.fact("lief_kind", kind)
        sigs = getattr(b, "signatures", None)
        if sigs is not None and len(sigs):
            flags = b.verify_signature()
            ok = str(flags).endswith("OK")
            look.line(f"Authenticode verification (LIEF): {'VALID' if ok else 'FAILED: ' + str(flags).split('.')[-1]}.", 74)
            if not ok:
                look.flag("AUTH-FAIL", "signature", str(flags).split(".")[-1], "the embedded signature does not verify: modified after signing or an untrusted chain")
        try:
            ih = lief.PE.get_imphash(b)
            look.line(f"Import hash (imphash) {ih}: the same value on two files suggests the same toolchain or family.", 50)
        except Exception:
            pass
        look.step("verification and imports", "lief", version=getattr(lief, "__version__", ""))
    except Exception as e:
        look.fail("LIEF parse", "lief", e)


# ----------------------------------------------------------------------------- dnfile: .NET metadata
def dotnet_facts(look):
    dn = look.mod("dnfile")
    if not dn:
        look.skip(".NET assembly name, references and types", "python package dnfile not importable" if not look.no_tools else "disabled by --no-tools", "dnfile")
        return
    try:
        pe = dn.dnPE(str(look.path))
        md = pe.net.mdtables
        asm = md.Assembly.rows[0] if md.Assembly and md.Assembly.rows else None
        refs = [str(r.Name) for r in (md.AssemblyRef.rows if md.AssemblyRef else [])]
        types = md.TypeDef.num_rows if md.TypeDef else 0
        methods = md.MethodDef.num_rows if md.MethodDef else 0
        look.line(f".NET assembly {getattr(asm, 'Name', '?')} v{getattr(asm, 'MajorVersion', '?')}.{getattr(asm, 'MinorVersion', '?')}: {types} types, {methods} methods; references " + ", ".join(refs[:10]) + ".", 72)
        look.fact("dotnet_types", types)
        look.step(".NET metadata", "dnfile")
    except Exception as e:
        look.fail(".NET metadata", "dnfile", e)


def run_all(look, st, is_dotnet):
    """Called from dl_bins.look_binary for PE files; ELF and Mach-O get LIEF and DIE only."""
    run_diec(look)
    run_capa(look)
    run_floss(look)
    lief_facts(look)
    if is_dotnet:
        dotnet_facts(look)
