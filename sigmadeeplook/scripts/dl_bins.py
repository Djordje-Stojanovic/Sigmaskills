"""SigmaDeepLook: binaries, archives, fonts, code (file and directory) and unknown files.

The input is never executed, never imported and never extracted unless --extract is given and the screen passes.
"""
import ast
import bz2
import csv
import fnmatch
import gzip
import io
import json
import lzma
import os
import re
import shutil
import struct
import tarfile
import time
import zipfile
import zlib
from collections import Counter
from pathlib import Path, PurePosixPath

import dl_core as core

STRINGS_CAP = 20000
READ_CAP = 64 << 20


def read_bytes(look, cap=READ_CAP):
    with open(look.path, "rb") as f:
        return f.read(cap)


# ================================================================= unknown
def look_unknown(look):
    look.exit_code = 3
    b = read_bytes(look, 8 << 20)
    look.fact("size", look.size)
    look.fact("entropy", round(core.entropy(b), 3))
    wins = [core.entropy(b[i:i + 4096]) for i in range(0, len(b), 4096)] or [0.0]
    look.line(f"Unknown or empty file: {core.human(look.size)}, entropy {look.facts['entropy']} bits/byte (4 KiB windows: min {min(wins):.2f}, max {max(wins):.2f}).")
    if look.size == 0:
        look.line("The file has 0 bytes.")
        look.flag("EMPTY", "file", "0 bytes", "nothing to look at")
    elif look.facts["entropy"] > 7.5:
        look.flag("HIGH-ENTROPY", "file", look.facts["entropy"], "looks compressed, encrypted or random; the format is not identified")
    fb = look.tool("file")
    if fb:
        r, out, _ = look.run_text([fb, "-b", str(look.path)])
        if r is not None and r.returncode == 0:
            look.fact("file_b", out.strip())
            look.line(f"`file -b` says: {out.strip()[:200]}")
    else:
        look.skip("file -b type guess", "`file` not found" if not look.no_tools else "disabled by --no-tools", "file", "install the `file` utility (Git for Windows ships it)")
    if b:
        look.write_text("hexdump.txt", core.hexdump(b[:512]), "first 512 bytes as hex", "internal")
    st = core.strings_of(b, 8, 2000)
    if st:
        look.write_text("strings.txt", "\n".join(f"{o:08x} {s[:200]}" for o, k, s in st), "printable strings (min 8)")
    look.ask_human("What is this file meant to be, and where did it come from?")


# ================================================================= code
LANGS = {".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript",
         ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cc": "C++", ".cs": "C#", ".java": "Java", ".go": "Go", ".rs": "Rust",
         ".rb": "Ruby", ".php": "PHP", ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell", ".bat": "Batch", ".lua": "Lua",
         ".kt": "Kotlin", ".swift": "Swift", ".sql": "SQL", ".css": "CSS", ".html": "HTML", ".md": "Markdown", ".json": "JSON",
         ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".txt": "Text", ".vue": "Vue", ".r": "R"}
DEF_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|func|fn|interface|struct|enum|trait|impl|type)\s+([A-Za-z_][\w$]*)", re.M)
SECRET_PATTERNS = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("API key assignment", re.compile(r"(?i)\b(api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{16,}['\"]")),
]
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", "dist", "build", ".next", "target", ".idea"}
LOCK_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "Gemfile.lock", "composer.lock", "go.sum", "uv.lock"}
MANIFESTS = ["package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "go.mod", "Cargo.toml", "Gemfile", "pom.xml",
             "build.gradle", "Makefile", "Dockerfile", "docker-compose.yml", "composer.json", "CMakeLists.txt"]
ENTRY_NAMES = {"main.py", "__main__.py", "app.py", "manage.py", "index.js", "main.js", "server.js", "app.js", "main.go", "main.rs", "lib.rs", "index.ts", "main.ts", "Program.cs"}
INSTRUCTION_FILES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".github/copilot-instructions.md"]


def outline_of(text, ext):
    """Definitions with line numbers. Python uses ast (parse only, never import); other languages use a regex."""
    out = []
    if ext == ".py":
        try:
            tree = ast.parse(text)
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    out.append({"line": n.lineno, "kind": "class" if isinstance(n, ast.ClassDef) else "def", "name": n.name})
            out.sort(key=lambda d: d["line"])
            return out[:500], "ast"
        except (SyntaxError, ValueError, RecursionError):
            pass
    for m in DEF_RE.finditer(text):
        out.append({"line": text.count("\n", 0, m.start()) + 1, "kind": "def", "name": m.group(1)})
        if len(out) >= 500:
            break
    return out, "regex"


def scan_secrets(look, text, where):
    n = 0
    for i, line in enumerate(text.splitlines(), 1):
        for name, rx in SECRET_PATTERNS:
            if rx.search(line):
                look.flag("SECRET?", f"{where}:{i}", name, "a key-like string; its value is not written to any output; ask before quoting it")
                n += 1
                break
        if n >= 10:
            break
    return n


def look_code(look):
    if look.path.is_dir():
        return look_repo(look)
    b = read_bytes(look, 8 << 20)
    text, enc = core.decode_text(b)
    ext = look.path.suffix.lower()
    if text is None:
        look.type = "unknown"
        return look_unknown(look)
    lines = text.splitlines()
    crlf, lf = text.count("\r\n"), text.count("\n") - text.count("\r\n")
    ends = "CRLF" if crlf and not lf else "LF" if lf and not crlf else "mixed" if crlf and lf else "none"
    lang = LANGS.get(ext) or ("Shell" if text.startswith("#!") and "sh" in lines[0] else "Python" if text.startswith("#!") and "python" in lines[0] else "Text")
    look.fact("language", lang)
    look.fact("lines", len(lines))
    look.fact("encoding", enc)
    look.fact("line_endings", ends)
    avg = (len(text) / max(1, len(lines)))
    minified = avg > 300 and len(text) > 2000
    look.line(f"{lang} source: {len(lines)} lines, {core.human(len(b))}, encoding {enc}, line endings {ends}.")
    if minified:
        look.flag("MINIFIED", "file", f"average line {avg:.0f} chars", "minified or generated; read the outline, not the code")
    n_inj = core.scan_injection(look, text, look.path.name, hidden_only=(ext not in (".md", ".txt", "")))
    look.fact("injection_flags", n_inj)
    scan_secrets(look, text, look.path.name)
    ol, how = outline_of(text, ext)
    import dl_skel
    rows, _how = dl_skel.skeleton(text, ext) if len(lines) > 80 and not minified else ([], "")
    if ol:
        if not rows:   # the skeleton below carries the same names with their signatures
            look.write_text("outline.json", json.dumps(ol, indent=1), f"definitions with line numbers ({how})", "json")
        if not rows:
            look.line(f"{len(ol)} definitions found ({how}): " + ", ".join(d["name"] for d in ol[:8]) + (" ..." if len(ol) > 8 else ""))
        look.fact("definitions", len(ol))
    look.excerpt("First lines", "\n".join(lines[:15]))
    if rows:   # headers and signatures instead of bodies: as good for finding the place (Agentless), a fraction of the tokens
        look.write_text("skeleton.md", dl_skel.render(rows, len(lines)), f"signature skeleton: {len(rows)} definitions with line numbers and a doc remark", value=8)
        look.line(f"Skeleton: {len(rows)} definitions with their signatures in skeleton.md; the body of one is one call away.", 40)
        look.cmd("--func NAME", "the body of one function or class (--func list names them all)", None)
    else:
        look.write_text("head.txt", "\n".join(lines[:200]), "first 200 lines")
    ctags = look.tool("ctags")
    if ctags and ext != ".py":
        r, out, _ = look.run_text([ctags, "--output-format=json", "-f", "-", str(look.path)])
        if r is not None and out.strip():
            look.write_text("ctags.jsonl", out, "ctags symbol list")
    look.ask_human("Which part of this file matters (a function, a bug, the whole)?",
                   "Is it OK to treat any hidden-Unicode or key-like findings in Flags as real problems?" if look.flags else "Do you need it run? This skill never runs code; say what to run and where.")


def read_gitignore(root):
    pats = []
    p = Path(root) / ".gitignore"
    if p.exists():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and not ln.startswith("!"):
                pats.append(ln.rstrip("/"))
    return pats


def ignored(rel, pats):
    parts = PurePosixPath(rel).parts
    for pat in pats:
        pat = pat.lstrip("/")
        if any(fnmatch.fnmatch(part, pat) for part in parts) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def look_repo(look):
    """A directory as a code repository: counts, largest files, entry points, instruction-file scan, a short map. Never runs anything."""
    root = look.path
    pats = read_gitignore(root)
    files, skipped = [], 0
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in EXCLUDE_DIRS)
        for n in sorted(fns):
            full = Path(dp) / n
            rel = full.relative_to(root).as_posix()
            if ignored(rel, pats):
                skipped += 1
                continue
            try:
                if full.is_symlink():
                    look.flag("SYMLINK", rel, "symlink", "not followed")
                    continue
                files.append((rel, full.stat().st_size))
            except OSError:
                pass
        if len(files) > 200000:
            look.flag("TRUNCATED", "walk", "200000 files", "repository larger than the walk limit")
            break
    by_lang, by_dir = {}, {}
    for rel, sz in files:
        ext = Path(rel).suffix.lower()
        lang = LANGS.get(ext, ext or "(none)")
        by_lang.setdefault(lang, [0, 0])
        by_lang[lang][0] += 1
        by_lang[lang][1] += sz
        top = rel.split("/")[0] if "/" in rel else "."
        by_dir[top] = by_dir.get(top, 0) + sz
    look.fact("files", len(files))
    look.fact("languages", {k: v[0] for k, v in sorted(by_lang.items(), key=lambda kv: -kv[1][1])[:12]})
    look.fact("total_bytes", sum(s for _, s in files))
    look.line(f"Code repository: {len(files)} files, {core.human(sum(s for _, s in files))} ({skipped} paths ignored by .gitignore; .git, node_modules and caches skipped).")
    top = sorted(by_lang.items(), key=lambda kv: -kv[1][1])[:8]
    look.line("Languages by size: " + ", ".join(f"{k} {v[0]} files" for k, v in top))
    largest = sorted(files, key=lambda x: -x[1])[:25]
    kinds = []
    for rel, sz in largest:
        nm = Path(rel).name
        k = "lockfile" if nm in LOCK_NAMES else "vendored" if re.search(r"(^|/)(vendor|third_party|node_modules)/", rel) else "generated?" if re.search(r"\.(min\.js|map|lock)$|(^|/)(dist|build|gen|generated)/", rel) else ""
        kinds.append((rel, sz, k))
    look.write_text("largest.txt", "\n".join(f"{sz:>12}  {rel}  {k}" for rel, sz, k in kinds), "25 largest files, lock/vendor/generated marked")
    names = {Path(r).name: r for r, _ in files}
    man = [m for m in MANIFESTS if m in names or any(Path(r).name == m for r, _ in files if r.count("/") <= 1)]
    entry = sorted({r for r, _ in files if Path(r).name in ENTRY_NAMES and r.count("/") <= 2})
    look.fact("manifests", man)
    look.fact("entry_points", entry)
    if man:
        look.line("Manifests: " + ", ".join(man))
    if entry:
        look.line("Entry points: " + ", ".join(entry[:10]))
    # instruction files and hooks: scan, never run
    for rel in INSTRUCTION_FILES:
        p = root / rel
        if p.is_file():
            t = p.read_text(encoding="utf-8", errors="replace")[:200000]
            core.scan_injection(look, t, rel)
    for dp, dns, fns in os.walk(root / ".cursor") if (root / ".cursor").is_dir() else []:
        for n in fns:
            p = Path(dp) / n
            core.scan_injection(look, p.read_text(encoding="utf-8", errors="replace")[:200000], p.relative_to(root).as_posix())
    for rel in (".claude/settings.json", ".claude/settings.local.json", ".mcp.json", ".vscode/tasks.json", ".devcontainer/devcontainer.json"):
        p = root / rel
        if p.is_file():
            t = p.read_text(encoding="utf-8", errors="replace")[:200000]
            try:
                j = json.loads(t)
            except ValueError:
                j = {}
            if rel.startswith(".claude") and ("hooks" in j or "mcpServers" in j or "env" in j):
                look.flag("HOOK-OR-MCP", rel, ", ".join(k for k in ("hooks", "mcpServers", "env") if k in j),
                          "this repo configures agent hooks or MCP servers that run commands; do not open an agent with auto-trust inside it")
            elif rel == ".mcp.json" and j:
                look.flag("HOOK-OR-MCP", rel, "MCP servers configured", "runs commands when an agent opens the repo")
            elif rel in (".vscode/tasks.json", ".devcontainer/devcontainer.json"):
                look.flag("AUTO-RUN?", rel, "task or container config", "check for auto-run tasks before opening in an editor")
            core.scan_injection(look, t, rel, hidden_only=True)
    n_sec = 0
    for rel, sz in files:
        if sz < 300000 and Path(rel).suffix.lower() in LANGS or Path(rel).name in (".env", ".env.local"):
            try:
                t = (root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if Path(rel).suffix.lower() in (".py", ".js", ".sh") and core.HIDDEN_RE.search(t):
                core.scan_injection(look, t, rel, hidden_only=True)
            n_sec += scan_secrets(look, t, rel)
            if n_sec >= 20:
                break
    # the map: top-level tree and outlines of the most important files, <= ~5k tokens
    L = [f"# Map of {root.name}", "", "## Top level", ""]
    for d, sz in sorted(by_dir.items(), key=lambda kv: -kv[1])[:30]:
        cnt = sum(1 for r, _ in files if (r.split("/")[0] if "/" in r else ".") == d)
        L.append(f"- `{d}` - {cnt} files, {core.human(sz)}")
    L += ["", "## Outlines (first definitions of the main source files)", ""]
    budget = 14000
    cands = sorted([(r, s) for r, s in files if Path(r).suffix.lower() in (".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb", ".php")
                    and Path(r).name not in LOCK_NAMES and s < 400000], key=lambda x: (x[0].count("/"), -x[1]))[:40]
    for rel, _ in cands:
        try:
            t = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ol, _how = outline_of(t, Path(rel).suffix.lower())
        if not ol:
            continue
        chunk = f"### `{rel}`\n" + "\n".join(f"- {d['kind']} `{d['name']}` (line {d['line']})" for d in ol[:15]) + "\n"
        if len(chunk) > budget:
            break
        budget -= len(chunk)
        L.append(chunk)
    look.write_text("map.md", "\n".join(L), "repository map: top level plus outlines (about 5k tokens)")
    look.write_text("repo.json", json.dumps({"files": len(files), "by_language": by_lang, "manifests": man, "entry_points": entry}, indent=1), "repo facts", "json")
    look.step("repo map", "stdlib")
    look.line("The repository was only read, never built, tested or imported.")
    look.ask_human("Which subsystem is in scope?", "Does generated or vendored code count?", "May any command run project code? Default: no.")


# ================================================================= binary
SEC_FLAGS = {0x20000000: "x", 0x40000000: "r", 0x80000000: "w"}
PE_MACHINES = {0x14c: "x86", 0x8664: "x86-64 (AMD64)", 0x1c0: "ARM", 0xaa64: "ARM64", 0x200: "IA-64"}
SUBSYS = {1: "native", 2: "Windows GUI", 3: "Windows console", 5: "OS/2", 7: "POSIX", 9: "Windows CE", 10: "EFI application"}
ELF_MACHINES = {3: "x86", 8: "MIPS", 40: "ARM", 62: "x86-64", 183: "AArch64", 243: "RISC-V", 20: "PowerPC", 21: "PowerPC64"}
MACHO_CPU = {7: "x86", 0x01000007: "x86-64", 12: "ARM", 0x0100000c: "ARM64"}


VERSION_KEYS = ("CompanyName", "FileDescription", "FileVersion", "ProductName", "OriginalFilename", "InternalName", "LegalCopyright", "ProductVersion", "Comments")


def parse_pe(b):
    off = struct.unpack_from("<I", b, 0x3C)[0]
    if b[off:off + 4] != b"PE\0\0":
        raise ValueError("no PE signature")
    machine, nsec, ts, _, _, optsz, chars = struct.unpack_from("<HHIIIHH", b, off + 4)
    opt = off + 24
    magic = struct.unpack_from("<H", b, opt)[0]
    entry = struct.unpack_from("<I", b, opt + 16)[0]
    subsystem = struct.unpack_from("<H", b, opt + 68)[0]
    ddir = opt + (112 if magic == 0x20B else 96)
    imp_rva, _imp_sz = struct.unpack_from("<II", b, ddir + 8)
    secs = []
    so = opt + optsz
    for i in range(nsec):
        n, vsz, va, rsz, rptr, _, _, _, _, ch = struct.unpack_from("<8sIIIIIIHHI", b, so + 40 * i)
        data = b[rptr:rptr + rsz]
        secs.append({"name": n.rstrip(b"\0").decode("latin-1"), "va": va, "vsize": vsz, "raw": rsz, "rptr": rptr,
                     "entropy": round(core.entropy(data), 2), "perms": "".join(v for k, v in SEC_FLAGS.items() if ch & k)})
    imports = []

    def r2o(rva):
        for s in secs:
            if s["va"] <= rva < s["va"] + max(s["vsize"], s["raw"]):
                return rva - s["va"] + s["rptr"]
        return None
    exports, export_count = [], 0
    exp_rva, _exp_sz = struct.unpack_from("<II", b, ddir)
    eo = r2o(exp_rva) if exp_rva else None
    if eo is not None and eo + 40 <= len(b):
        nnames, an = struct.unpack_from("<II", b, eo + 24)[0], struct.unpack_from("<I", b, eo + 32)[0]
        export_count = struct.unpack_from("<I", b, eo + 20)[0]
        ao = r2o(an)
        for i in range(min(nnames, 400)):
            if ao is None or ao + 4 * i + 4 > len(b):
                break
            no = r2o(struct.unpack_from("<I", b, ao + 4 * i)[0])
            if no is not None:
                exports.append(b[no:b.find(b"\0", no)].decode("latin-1"))
    sec_off, sec_sz = struct.unpack_from("<II", b, ddir + 32)
    version = {}
    for key in VERSION_KEYS[:5]:
        for m in re.finditer(key.encode("utf-16-le") + b"\0\0(?:\0\0)*((?:[^\0]\0)+)", b):
            val = m.group(1).decode("utf-16-le", "replace").strip()
            if val and val not in VERSION_KEYS:
                version[key] = val[:80]
                break
    if imp_rva:
        p = r2o(imp_rva)
        while p is not None and p + 20 <= len(b) and len(imports) < 100:
            d = struct.unpack_from("<5I", b, p)
            if not any(d):
                break
            no = r2o(d[3])
            if no is not None:
                end = b.find(b"\0", no)
                imports.append(b[no:end].decode("latin-1"))
            p += 20
    return {"machine": PE_MACHINES.get(machine, hex(machine)), "timestamp": ts, "subsystem": SUBSYS.get(subsystem, str(subsystem)),
            "pe32plus": magic == 0x20B, "sections": secs, "imports": imports, "dll": bool(chars & 0x2000), "entry_rva": entry,
            "exports": exports, "export_count": export_count, "signed": bool(sec_off and sec_sz), "version": version}


def parse_elf(b):
    cls = {1: "ELF32", 2: "ELF64"}.get(b[4], "?")
    end = "<" if b[5] == 1 else ">"
    etype, machine = struct.unpack_from(end + "HH", b, 16)
    secs = []
    if b[4] == 2:
        shoff = struct.unpack_from(end + "Q", b, 40)[0]
        shentsize, shnum, shstrndx = struct.unpack_from(end + "HHH", b, 58)
        hdr = "IIQQQQIIQQ"
    else:
        shoff = struct.unpack_from(end + "I", b, 32)[0]
        shentsize, shnum, shstrndx = struct.unpack_from(end + "HHH", b, 46)
        hdr = "IIIIIIIIII"
    ents = []
    if shoff and shnum and shoff + shentsize * shnum <= len(b):
        for i in range(shnum):
            ents.append(struct.unpack_from(end + hdr, b, shoff + i * shentsize))
        stroff, strsz = (ents[shstrndx][4], ents[shstrndx][5]) if shstrndx < len(ents) else (0, 0)
        table = b[stroff:stroff + strsz]
        for e in ents:
            name = table[e[0]:table.find(b"\0", e[0])].decode("latin-1") if e[0] < len(table) else ""
            off, size = e[4], e[5]
            if name:
                secs.append({"name": name, "size": size, "entropy": round(core.entropy(b[off:off + min(size, 1 << 20)]), 2) if e[1] != 8 else 0.0})
    return {"class": cls, "machine": ELF_MACHINES.get(machine, str(machine)), "type": {1: "relocatable", 2: "executable", 3: "shared/PIE", 4: "core"}.get(etype, str(etype)), "sections": secs}


def look_binary(look):
    b = read_bytes(look)
    st = look.subtype
    info = {}
    try:
        if st == "pe":
            info = parse_pe(b)
            kind = "DLL" if info["dll"] else "executable"
            look.headline = f"Windows {kind} ({info['machine']})" + (f", {info['version']['FileDescription']}" if info["version"].get("FileDescription") else "") + (f", {info['export_count']} exports" if info["export_count"] else "")
            look.dims = f"{info['machine']}"
            look.line(f"Windows PE ({kind}): machine {info['machine']}, subsystem {info['subsystem']}." + (f" Exports {info['export_count']} functions, e.g. " + ", ".join(info["exports"][:5]) + "." if info["export_count"] else " No exports."), 80)
            if info["version"]:
                look.line("Version info: " + "; ".join(f"{k} {v}" for k, v in info["version"].items()), 78)
            import dl_pe
            dl_pe.extras(look, b, info)
            hi = max(info["sections"], key=lambda s: s["entropy"], default=None)
            look.line("Sections: " + ", ".join(s["name"] for s in info["sections"]) + (f"; highest entropy {hi['entropy']} ({hi['name']}), writable and executable: " + (", ".join(s["name"] for s in info["sections"] if "x" in s["perms"] and "w" in s["perms"]) or "none") if hi else ""), 48)
            look.fact("arch", info["machine"])
            look.fact("sections", [s["name"] for s in info["sections"]])
            look.fact("imports", info["imports"])
            if any(s["entropy"] > 7.2 for s in info["sections"]):
                look.flag("PACKED?", "sections", "entropy above 7.2", "high-entropy section: possibly packed or encrypted; static results may mislead")
            pf = look.mod("pefile")
            if not pf:
                look.skip("resources, Rich header and header checksum (pefile)", "pefile not importable" if not look.no_tools else "disabled by --no-tools", "pefile")
        elif st == "elf":
            info = parse_elf(b)
            look.line(f"ELF: {info['class']}, {info['machine']}, {info['type']}. Sections: " + ", ".join(s["name"] for s in info["sections"][:16]))
            look.fact("arch", info["machine"])
            look.fact("sections", [s["name"] for s in info["sections"]])
            if any(s["entropy"] > 7.2 and s["size"] > 1024 for s in info["sections"]):
                look.flag("PACKED?", "sections", "entropy above 7.2", "possibly packed")
        elif st in ("macho", "macho-fat"):
            if st == "macho-fat":
                n = struct.unpack(">I", b[4:8])[0]
                archs = [MACHO_CPU.get(struct.unpack(">I", b[8 + 20 * i:12 + 20 * i])[0], "?") for i in range(min(n, 8))]
                look.line("Mach-O universal binary with architectures: " + ", ".join(archs))
                look.fact("arch", archs)
            else:
                big = b[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf")
                cpu = struct.unpack(">I" if big else "<I", b[4:8])[0]
                look.line(f"Mach-O: cpu {MACHO_CPU.get(cpu, hex(cpu))}.")
                look.fact("arch", MACHO_CPU.get(cpu, hex(cpu)))
        elif st == "wasm":
            look.line(f"WebAssembly module, version {struct.unpack('<I', b[4:8])[0]}.")
        elif st == "java-class":
            look.line(f"Java class file, major version {struct.unpack('>H', b[6:8])[0]}.")
        elif st == "dex":
            look.line("Android Dalvik executable (dex).")
        else:
            look.line(f"Binary of kind {st}.")
    except (struct.error, ValueError, IndexError) as e:
        look.flag("PARSE-ERROR", "header", str(e)[:100], "the header is truncated or malformed; strings and entropy still ran")
    look.fact("entropy", round(core.entropy(b[:4 << 20]), 3))
    st_list = core.strings_of(b, 8, STRINGS_CAP)
    lines = [f"{o:08x} {k} {s[:300]}" for o, k, s in st_list]
    if lines:
        look.write_text("strings.txt", "\n".join(lines), f"ASCII and UTF-16LE strings (min 8, {len(lines)} shown, capped at {STRINGS_CAP})", inline=False)
    noise = re.compile(r"schemas\.microsoft\.com|w3\.org|/pki|/crl|\.crt|\.crl|xmlns")  # manifest and certificate-chain URLs say nothing about behaviour
    urls = sorted({s.strip() for _, _, s in st_list if re.search(r"https?://|\\\\[\w.]+\\|HKEY_|\.onion", s) and not noise.search(s)})[:10]
    if urls:
        look.line("Notable strings: " + "; ".join(u[:60] for u in urls[:5]), 45)
    look.fact("strings", len(st_list))
    if info:
        look.write_text("header.json", json.dumps(info, indent=1, default=str), "parsed header, sections, imports", "json")
    look.write_text("hexdump.txt", core.hexdump(b[:512]), "first 512 bytes as hex", inline=False)
    look.step("header, sections, entropy, strings", "stdlib")
    import dl_binx
    dl_binx.run_all(look, st, bool(look.facts.get("dotnet")))
    if st not in ("pe", "elf", "macho", "macho-fat"):
        look.skip("decompilation and function-level reading (Ghidra)", "only for PE, ELF and Mach-O files", None, "")
    elif not look.tool("ghidra"):
        look.skip("decompilation and function-level reading (Ghidra)", "Ghidra not found" if not look.no_tools else "disabled by --no-tools", "ghidra")
    look.flag("NOT-EXECUTED", "file", "static look only", "the binary was never run; do not run it outside a VM you chose")
    look.ask_human("May the strings or the file be uploaded anywhere? Default: no.", "Which function or behaviour do you need explained?")


# ================================================================= archives
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_MEMBERS = 10000
MAX_TOTAL = 2 << 30
MAX_RATIO = 200
MAX_DEPTH = 2


def bad_name(name):
    """-> a reason string when a member name is unsafe, else None."""
    n = name.replace("\\", "/")
    if n.startswith("/") or re.match(r"^[A-Za-z]:", n):
        return "absolute path or drive letter"
    parts = [p for p in n.split("/") if p not in ("", ".")]
    if ".." in parts:
        return "path traversal (..)"
    for p in parts:
        stem = p.split(".")[0].upper()
        if stem in RESERVED:
            return f"Windows reserved name ({p})"
        if p.endswith((".", " ")):
            return f"trailing dot or space ({p!r})"
        if ":" in p:
            return f"colon in name (NTFS stream) ({p})"
    return None


def zip_depth(data, depth=0):
    """How many levels of zip-inside-zip below this one (bounded, in memory)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError):
        return depth
    best = depth
    for i in z.infolist()[:50]:
        if i.filename.lower().endswith((".zip", ".jar")) and i.file_size < 64 << 20 and not i.flag_bits & 1:
            try:
                best = max(best, zip_depth(z.read(i), depth + 1))
            except Exception:
                pass
            if best > MAX_DEPTH:
                break
    return best


def list_archive(look):
    """-> (members, extra). Each member: name, size, packed, kind (file|dir|symlink|hardlink|device), enc(bool), offset."""
    p = look.path
    members, extra = [], {}
    st = look.subtype
    if st in ("zip", "jar", "apk", "epub") or (look.type == "archive" and zipfile.is_zipfile(p) and st not in ("tar",)):
        with zipfile.ZipFile(p) as z:
            for i in z.infolist():
                mode = (i.external_attr >> 16) & 0xFFFF
                kind = "dir" if i.is_dir() else "symlink" if (mode & 0o170000) == 0o120000 else "file"
                members.append(dict(name=i.filename, size=i.file_size, packed=i.compress_size, kind=kind, enc=bool(i.flag_bits & 1), offset=i.header_offset))
        extra["format"] = "zip"
    elif tarfile.is_tarfile(p):
        with tarfile.open(p, "r:*") as t:
            for m in t:
                kind = "dir" if m.isdir() else "symlink" if m.issym() else "hardlink" if m.islnk() else "device" if (m.isdev() or m.isfifo()) else "file"
                members.append(dict(name=m.name, size=m.size, packed=0, kind=kind, enc=False, offset=m.offset_data, target=m.linkname))
                if len(members) > MAX_MEMBERS + 1:
                    break
        extra["format"] = "tar"
    return members, extra


def screen_members(look, members, depth):
    """-> list of (rule, member, detail) refusals. The safety screen from the plan, run on the listing only."""
    refusals = []
    if len(members) > MAX_MEMBERS:
        refusals.append(("too-many-members", "archive", f"{len(members)} members (limit {MAX_MEMBERS})"))
    total = sum(m["size"] for m in members)
    free = shutil.disk_usage(look.out).free
    if total > MAX_TOTAL or total > free * 0.5:
        refusals.append(("too-large", "archive", f"{core.human(total)} uncompressed (limit 2 GiB or half the free disk)"))
    seen, ranges = set(), []
    for m in members[: MAX_MEMBERS + 1]:
        r = bad_name(m["name"])
        if r:
            refusals.append(("unsafe-name", m["name"], r))
        if m["kind"] in ("symlink", "hardlink", "device"):
            refusals.append(("link-or-device", m["name"], f"{m['kind']}" + (f" -> {m.get('target')}" if m.get("target") else "")))
        key = m["name"].replace("\\", "/").rstrip("/").lower()
        if key in seen and m["kind"] != "dir":
            refusals.append(("duplicate-name", m["name"], "same name twice"))
        seen.add(key)
        if m["packed"] and m["size"] / max(1, m["packed"]) > MAX_RATIO:
            refusals.append(("ratio", m["name"], f"ratio {m['size'] // max(1, m['packed'])}:1 (limit {MAX_RATIO}:1)"))
        if m["packed"]:
            ranges.append((m["offset"], m["offset"] + m["packed"], m["name"]))
    ranges.sort()
    for a, b in zip(ranges, ranges[1:]):
        if b[0] < a[1]:
            refusals.append(("overlap", b[2], f"shares bytes with {a[2]}"))
            break
    if depth > MAX_DEPTH:
        refusals.append(("nesting", "archive", f"zip inside zip {depth} levels deep (limit {MAX_DEPTH})"))
    return refusals


def safe_extract(look, members, which, dest):
    """Extract the named members one at a time into dest with a byte and time counter. -> list of written paths."""
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    written, total, t0 = [], 0, time.time()
    p = look.path

    def target(name):
        real = Path(os.path.realpath(dest / name))
        if os.path.commonpath([str(dest), str(real)]) != str(dest):
            raise ValueError(f"member escapes the folder: {name}")
        return real

    if zipfile.is_zipfile(p) and look.subtype != "tar":
        with zipfile.ZipFile(p) as z:
            for name in which:
                info = z.getinfo(name)
                if info.is_dir() or info.flag_bits & 1:
                    continue
                out = target(name)
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    while True:
                        chunk = src.read(1 << 16)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_TOTAL or time.time() - t0 > core.TIMEOUT:
                            raise ValueError("extraction limit hit (bytes or time)")
                        dst.write(chunk)
                written.append(out)
    else:
        with tarfile.open(p, "r:*") as t:
            for name in which:
                m = t.getmember(name)
                if not m.isfile():
                    continue
                out = target(name)
                out.parent.mkdir(parents=True, exist_ok=True)
                src = t.extractfile(m)
                with open(out, "wb") as dst:
                    while True:
                        chunk = src.read(1 << 16)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_TOTAL or time.time() - t0 > core.TIMEOUT:
                            raise ValueError("extraction limit hit (bytes or time)")
                        dst.write(chunk)
                written.append(out)
    return written


NESTED_EXT = (".zip", ".tgz", ".tar.gz", ".tar", ".7z", ".rar", ".gz", ".bz2", ".xz", ".jar", ".whl", ".nupkg")
RISKY_EXT = (".exe", ".dll", ".msi", ".bat", ".cmd", ".ps1", ".sh", ".vbs", ".js", ".scr", ".lnk")


def archive_overview(members):
    """Summary lines for a big archive: where the bytes are, what kinds of files, the biggest members, nested archives, runnable files."""
    files = [m for m in members if m["kind"] == "file"]
    if not files:
        return []
    out = []
    top = {}
    for m in files:
        parts = m["name"].replace("\\", "/").strip("/").split("/")
        key = parts[0] + "/" if len(parts) > 1 else "(top level)"
        a = top.setdefault(key, [0, 0])
        a[0] += 1
        a[1] += m["size"]
    out.append("Folders (files, uncompressed): " + "; ".join(f"{k} {n} files {core.human(b)}" for k, (n, b) in sorted(top.items(), key=lambda kv: -kv[1][1])[:8])
               + (f"; +{len(top) - 8} more" if len(top) > 8 else ""))
    depth = max(m["name"].replace("\\", "/").strip("/").count("/") for m in files)
    ext = Counter(os.path.splitext(m["name"])[1].lower() or "(none)" for m in files)
    out.append(f"File types: " + ", ".join(f"{e} {n}" for e, n in ext.most_common(8)) + f"; deepest folder nesting {depth}.")
    big = sorted(files, key=lambda m: -m["size"])[:5]
    out.append("Largest: " + "; ".join(f"{m['name']} ({core.human(m['size'])})" for m in big))
    nested = [m["name"] for m in files if m["name"].lower().endswith(NESTED_EXT)]
    if nested:
        out.append(f"{len(nested)} members are archives themselves (not opened), e.g. {', '.join(nested[:2])}.")
    risky = [m["name"] for m in files if m["name"].lower().endswith(RISKY_EXT)]
    if risky:
        out.append(f"{len(risky)} runnable-looking members (never run), e.g. {', '.join(risky[:3])}.")
    notable = [m["name"] for m in files if os.path.basename(m["name"]).lower() in ("readme", "readme.md", "package.json", "setup.py", "pyproject.toml", "manifest.json", "install.ps1", "install.sh", "license")]
    if notable:
        out.append("Notable files: " + ", ".join(notable[:4]))
    return out


def parse_7z_slt(text):
    """`7z l -slt` output -> (members, extra). Members use the same keys as list_archive; offsets are unknown (0)."""
    members, extra, cur, in_files = [], {}, {}, False
    for ln in text.splitlines():
        if ln.startswith("----------"):
            in_files = True
            continue
        if not ln.strip():
            if in_files and cur.get("Path"):
                attr = cur.get("Attributes", "")
                kind = "dir" if cur.get("Folder") == "+" or attr.startswith("D") else "symlink" if cur.get("Symbolic Link") or attr.startswith("l") or attr.startswith("_l") else "file"
                members.append(dict(name=cur["Path"], size=int(cur.get("Size") or 0), packed=int(cur.get("Packed Size") or 0), kind=kind, enc=cur.get("Encrypted") == "+", offset=0))
            cur = {}
            continue
        if "=" in ln:
            k, v = ln.split("=", 1)
            (cur if in_files else extra).__setitem__(k.strip(), v.strip())
    if in_files and cur.get("Path"):
        members.append(dict(name=cur["Path"], size=int(cur.get("Size") or 0), packed=int(cur.get("Packed Size") or 0), kind="file", enc=cur.get("Encrypted") == "+", offset=0))
    extra = {"method": extra.get("Method", ""), "solid": extra.get("Solid", ""), "type": extra.get("Type", "")}
    return members, extra


def look_archive(look):
    p = look.path
    st = look.subtype
    if st == "gitbundle":
        import dl_extra
        dl_extra.look_gitbundle(look)
        return
    members, extra = [], {}
    single = st in ("gzip", "bzip2", "xz")
    try:
        if not single and st not in ("7z", "rar", "iso", "cab", "zstd"):
            members, extra = list_archive(look)
        if single and not members and tarfile.is_tarfile(p):
            members, extra = list_archive(look)
    except (zipfile.BadZipFile, tarfile.TarError, OSError, EOFError, NotImplementedError) as e:
        look.flag("CORRUPT", "archive", str(e)[:120], "the archive could not be listed")
    if not members and not extra and st in ("7z", "rar", "iso", "cab", "zstd"):
        sz = look.tool("7z")
        if sz:
            r, out, _ = look.run_text([sz, "l", "-slt", str(p)])
            if r is not None and out:
                members, extra = parse_7z_slt(out)
                extra["format"] = st
                tot = sum(m["size"] for m in members)
                if tot > MAX_RATIO * 5 * max(1, look.size):
                    look.exit_code = 2
                    look.flag("DECOMPRESSION-BOMB?", "archive", f"{core.human(tot)} uncompressed from {core.human(look.size)} ({tot // max(1, look.size)}:1)", "possible compression bomb: do not extract")
                look.write_text("listing-7z.txt", out[:core.MAX_TEXT], "7-Zip technical listing", value=2, inline=False)
        else:
            look.skip(f"member listing of a {st} archive", "7-Zip not found" if not look.no_tools else "disabled by --no-tools", "7z")
            look.line(f"Archive of kind {st}; only the type and size are known.")
        if st == "iso":
            b = read_bytes(look, 0x9000)
            label = b[0x8028:0x8048].decode("latin-1", "replace").strip() if len(b) >= 0x8048 else ""
            look.line(f"ISO 9660 volume label: {label!r}")
        if not members:
            return
    if single and not members:
        opener = {"gzip": gzip.open, "bzip2": bz2.open, "xz": lzma.open}[st]
        n = 0
        try:
            with opener(p, "rb") as f:
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    n += len(chunk)
                    if n > 256 << 20:
                        break
        except (OSError, EOFError, lzma.LZMAError) as e:
            look.flag("CORRUPT", "stream", str(e)[:100], "")
        ratio = n / max(1, look.size)
        look.line(f"Single {st} stream: {core.human(look.size)} packed, at least {core.human(n)} unpacked (ratio {ratio:.0f}:1).")
        look.fact("unpacked_bytes_at_least", n)
        if n > 256 << 20 or ratio > MAX_RATIO * 5:
            look.exit_code = 2
            look.flag("REFUSED", "stream", f"ratio {ratio:.0f}:1", "possible compression bomb; not unpacked")
        return
    depth = 0
    if extra.get("format") == "zip":
        depth = zip_depth(read_bytes(look, 64 << 20)) if look.size < 64 << 20 else 0
    refusals = screen_members(look, members, depth)
    nfile = sum(1 for m in members if m["kind"] == "file")
    total = sum(m["size"] for m in members)
    ratios = [m["size"] / max(1, m["packed"]) for m in members if m["packed"]]
    look.fact("members", len(members))
    look.fact("files", nfile)
    look.fact("uncompressed_bytes", total)
    look.fact("max_ratio", round(max(ratios), 1) if ratios else 0)
    look.fact("nesting_depth", depth)
    look.line(f"Archive ({extra.get('format', st)}): {len(members)} members, {nfile} files, {core.human(total)} uncompressed ({core.human(look.size)} packed), largest ratio {max(ratios) if ratios else 0:.0f}:1" + (f", nesting depth {depth}" if depth else "") + ".")
    for ln in archive_overview(members):
        look.line(ln)
    rows = [(m["name"], m["size"], m["packed"], f"{m['size'] / max(1, m['packed']):.1f}" if m["packed"] else "", m["kind"], "encrypted" if m["enc"] else "") for m in members[:2000]]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "size", "packed", "ratio", "type", "flags"])
    w.writerows(rows)
    look.write_text("listing.csv", buf.getvalue(), f"member list ({len(members)} members)", inline=False if len(members) > 40 else None)
    for m in members:
        if m["enc"]:
            look.flag("ENCRYPTED", m["name"], "encrypted member", "listed only; not readable without the password")
    # docker image: layers and whiteouts
    names = [m["name"] for m in members]
    if extra.get("format") == "tar" and "manifest.json" in names:
        docker_layers(look, names)
    if refusals:
        look.exit_code = 2
        verdict = {"extract": False, "reasons": [dict(rule=r, member=m, detail=d) for r, m, d in refusals]}
        for r, m, d in refusals[:12]:
            look.flag("REFUSED", m, f"{r}: {d}", "the safety screen refuses extraction")
        look.line("Safety screen: REFUSED. " + "; ".join(f"{r} ({m})" for r, m, d in refusals[:4]))
    else:
        verdict = {"extract": True, "reasons": []}
        look.line("Safety screen: passed (names, links, ratios, overlaps).")
    look.write_text("screen.json", json.dumps(verdict, indent=1), "extraction screen verdict", "json")
    want_n = look.recurse
    if (look.extract or want_n) and extra.get("format") not in ("zip", "tar"):
        look.skip("extraction of members", f"{extra.get('format', st)} archives are listed and screened only; extraction is built for zip and tar", None, f'7z x "{p}" -o<empty folder>  (after the screen above passed)')
        look.step("list and screen", "7-Zip")
        return
    if (look.extract or want_n) and not refusals:
        pick = [m["name"] for m in members if m["kind"] == "file" and not m["enc"]]
        pick = pick if look.extract else pick[:want_n]
        try:
            done = safe_extract(look, members, pick, look.out / "extract")
            look.line(f"Extracted {len(done)} files to `{look.out / 'extract'}`.")
            look.fact("extracted", len(done))
            for d in done[:want_n]:
                core.recurse_into(look, d, str(d.relative_to(look.out / "extract")))
        except (ValueError, OSError, KeyError, tarfile.TarError, zipfile.BadZipFile) as e:
            look.flag("EXTRACT-STOPPED", "extract", str(e)[:150], "")
    elif look.extract and refusals:
        look.line("--extract was given but the screen refused: nothing was written.")
    elif not look.extract and st != "epub":
        look.skip("member contents", "listed only; pass --extract (or --recurse N) after the screen passes", None, "python look.py FILE --extract")
    if st == "epub" and not refusals:
        import dl_extra
        dl_extra.epub_extras(look)
    look.step("list and screen", "stdlib")
    look.ask_human("Do you trust where this archive came from?", "Should the members be extracted and looked at (--extract / --recurse N)?")


def docker_layers(look, names):
    try:
        with tarfile.open(look.path, "r:*") as t:
            man = json.load(t.extractfile("manifest.json"))
            rows, whiteouts = [], []
            for img in man:
                for layer in img.get("Layers", []):
                    try:
                        lt = tarfile.open(fileobj=t.extractfile(layer), mode="r:*")
                    except (KeyError, tarfile.TarError):
                        continue
                    ms = lt.getmembers()
                    wo = [m.name for m in ms if os.path.basename(m.name).startswith(".wh.")]
                    whiteouts += wo
                    rows.append([layer, sum(m.size for m in ms), len(ms), len(wo)])
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["layer", "bytes", "members", "whiteouts"])
            w.writerows(rows)
            look.write_text("layers.csv", buf.getvalue(), "Docker image layers")
            look.fact("docker_layers", len(rows))
            look.fact("whiteouts", whiteouts)
            look.line(f"Docker image: {len(rows)} layers; whiteout (delete) entries: {', '.join(whiteouts[:6]) or 'none'}.")
    except (KeyError, ValueError, tarfile.TarError, OSError) as e:
        look.flag("DOCKER-UNREADABLE", "manifest.json", str(e)[:100], "")


# ================================================================= fonts
BLOCKS = [("Basic Latin", 0x20, 0x7E), ("Latin-1 Supplement", 0xA0, 0xFF), ("Latin Extended-A", 0x100, 0x17F), ("Greek", 0x370, 0x3FF),
          ("Cyrillic", 0x400, 0x4FF), ("Hebrew", 0x590, 0x5FF), ("Arabic", 0x600, 0x6FF), ("Devanagari", 0x900, 0x97F), ("Thai", 0xE00, 0xE7F),
          ("Hiragana", 0x3040, 0x309F), ("Katakana", 0x30A0, 0x30FF), ("CJK Unified", 0x4E00, 0x9FFF), ("Hangul", 0xAC00, 0xD7AF)]
LATIN = [chr(c) for c in list(range(65, 91)) + list(range(97, 123)) + list(range(48, 58))]
NAME_IDS = {1: "family", 2: "subfamily", 4: "full name", 5: "version", 6: "postscript", 0: "copyright", 13: "license", 14: "license url"}


def sfnt_tables(b):
    n = struct.unpack_from(">H", b, 4)[0]
    tabs = {}
    for i in range(n):
        tag, _cs, off, ln = struct.unpack_from(">4sIII", b, 12 + 16 * i)
        tabs[tag.decode("latin-1")] = (off, ln)
    return tabs


def sfnt_names(b, tabs):
    if "name" not in tabs:
        return {}
    off, ln = tabs["name"]
    _f, cnt, so = struct.unpack_from(">HHH", b, off)
    out = {}
    for i in range(cnt):
        pid, eid, lid, nid, ln2, o2 = struct.unpack_from(">HHHHHH", b, off + 6 + 12 * i)
        raw = b[off + so + o2: off + so + o2 + ln2]
        try:
            s = raw.decode("utf-16-be" if pid in (0, 3) else "mac_roman")
        except UnicodeDecodeError:
            continue
        out.setdefault(nid, s)
    return out


def woff_unwrap(b):
    """WOFF 1 -> (tables dict of raw bytes, flavor) using zlib. None for other input."""
    if b[:4] != b"wOFF":
        return None
    flavor, _len, n = struct.unpack_from(">4sIH", b, 4)
    tabs = {}
    for i in range(n):
        tag, off, comp, orig, _cs = struct.unpack_from(">4sIIII", b, 44 + 20 * i)
        raw = b[off:off + comp]
        tabs[tag.decode("latin-1")] = zlib.decompress(raw) if comp != orig else raw
    return tabs, flavor


def look_font(look):
    b = read_bytes(look, 32 << 20)
    st = look.subtype
    ft = look.mod("fontTools")
    font = None
    facts = {}
    if ft:
        from fontTools.ttLib import TTFont
        try:
            if st == "woff2" and not look.mod("brotli"):
                raise ImportError("brotli missing")
            font = TTFont(io.BytesIO(b), lazy=True, fontNumber=0)
        except Exception as e:
            look.skip("full font tables" + (" (WOFF2)" if st == "woff2" else ""), f"{type(e).__name__}: {e}"[:100], "brotli" if st == "woff2" else "fontTools")
    else:
        look.skip("cmap coverage, variable axes and specimen", "fontTools not importable" if not look.no_tools else "disabled by --no-tools", "fontTools")
    if font is not None:
        names = {}
        for rec in font["name"].names:
            if rec.nameID in NAME_IDS and rec.nameID not in names:
                try:
                    names[rec.nameID] = rec.toUnicode()
                except Exception:
                    pass
        facts["family"] = names.get(1, "")
        facts["subfamily"] = names.get(2, "")
        facts["full_name"] = names.get(4, "")
        facts["glyphs"] = font["maxp"].numGlyphs
        facts["tables"] = sorted(font.keys())
        facts["variable"] = "fvar" in font
        cmap = font.getBestCmap() or {}
        facts["cmap_codepoints"] = len(cmap)
        cov = {}
        for nm, lo, hi in BLOCKS:
            c = sum(1 for cp in cmap if lo <= cp <= hi)
            if c:
                cov[nm] = f"{c}/{hi - lo + 1}"
        facts["coverage"] = cov
        facts["missing_latin"] = "".join(ch for ch in LATIN if ord(ch) not in cmap)
        if "fvar" in font:
            facts["axes"] = [{"tag": a.axisTag, "min": a.minValue, "default": a.defaultValue, "max": a.maxValue} for a in font["fvar"].axes]
        if "OS/2" in font:
            facts["weight_class"] = font["OS/2"].usWeightClass
        facts["license"] = names.get(13, "")[:200]
    else:
        raw = woff_unwrap(b) if st == "woff" else None
        if raw:
            tabs, flavor = raw
            fake = b"\0\1\0\0" + struct.pack(">H", len(tabs)) + b"\0" * 6
            blob, offs, pos = b"", {}, 12 + 16 * len(tabs)
            for tag, data in tabs.items():
                offs[tag] = (pos + len(blob), len(data))
                blob += data
            head = fake
            for tag, (o, l) in offs.items():
                head += struct.pack(">4sIII", tag.encode("latin-1"), 0, o, l)
            sf = head + blob
            tb = sfnt_tables(sf)
            names = sfnt_names(sf, tb)
            facts["tables"] = sorted(tb)
            if "maxp" in tb:
                facts["glyphs"] = struct.unpack_from(">H", sf, tb["maxp"][0] + 4)[0]
            facts["variable"] = "fvar" in tb
        elif st in ("ttf", "otf", "ttc"):
            tb = sfnt_tables(b)
            names = sfnt_names(b, tb)
            facts["tables"] = sorted(tb)
            if "maxp" in tb:
                facts["glyphs"] = struct.unpack_from(">H", b, tb["maxp"][0] + 4)[0]
            facts["variable"] = "fvar" in tb
        else:
            names = {}
            if st == "woff2":
                flavor, _l, ntab = struct.unpack_from(">4sIH", b, 4)
                facts["tables_count"] = ntab
        facts["family"] = names.get(1, "")
        facts["subfamily"] = names.get(2, "")
        facts["full_name"] = names.get(4, "")
    for k, v in facts.items():
        look.fact(k, v)
    if facts.get("family") or facts.get("glyphs"):
        look.line(f"Font {facts.get('full_name') or facts.get('family')!r} ({st}): {facts.get('glyphs', '?')} glyphs, {'variable' if facts.get('variable') else 'static'}; "
                  f"{len(facts.get('tables', []))} tables.")
    else:
        look.line(f"Font file ({st}); names and glyph count need more than the header.")
    if facts.get("coverage"):
        look.line("Unicode coverage: " + ", ".join(f"{k} {v}" for k, v in facts["coverage"].items()))
    if facts.get("missing_latin"):
        look.line(f"Missing Basic Latin letters and digits: {facts['missing_latin']}")
        look.flag("MISSING-LATIN", "cmap", facts["missing_latin"][:60], "text in these characters falls back to another font")
    if facts.get("axes"):
        look.line("Variable axes: " + ", ".join(f"{a['tag']} {a['min']}..{a['max']}" for a in facts["axes"]))
    if facts.get("license"):
        look.line(f"Licence string in the font: {facts['license']}")
    look.write_text("font.json", json.dumps(facts, indent=1, default=str), "font facts (tables, names, coverage)", "json")
    if font is not None:
        pil = look.mod("PIL")
        if pil:
            specimen(look, font, facts)
        else:
            look.skip("specimen picture", "Pillow not importable" if not look.no_tools else "disabled by --no-tools", "PIL")
    look.skip("sanitizer check (OTS) and quality checks (Font Bakery)", "not installed; run `pip install fontbakery` if you need a validity gate" if not look.no_tools else "disabled by --no-tools", None, "see references/font.md")
    look.ask_human("Which scripts or languages must this font cover?", "Is the licence in the file the one you expect?")


def specimen(look, font, facts):
    from PIL import Image, ImageDraw, ImageFont
    buf = io.BytesIO()
    try:
        font.flavor = None
        font.save(buf)
    except Exception as e:
        look.skip("specimen picture", f"could not re-save the font: {type(e).__name__}", None, "")
        return
    buf.seek(0)
    cmap = font.getBestCmap() or {}
    W = 1400
    im = Image.new("RGB", (W, 640), "white")
    d = ImageDraw.Draw(im)
    y = 10
    try:
        for size, text in ((72, "Hamburgefonstiv 0123456789"), (40, "The quick brown fox jumps over the lazy dog"), (22, "Sphinx of black quartz, judge my vow")):
            buf.seek(0)
            f = ImageFont.truetype(buf, size)
            shown = "".join(ch if ord(ch) in cmap else " " for ch in text)
            d.text((10, y), shown, font=f, fill="black")
            y += size + 24
        # glyph grid: first 144 mapped characters
        buf.seek(0)
        gf = ImageFont.truetype(buf, 34)
        cps = sorted(cmap)[:144]
        for i, cp in enumerate(cps):
            x, yy = 10 + (i % 24) * 56, y + 10 + (i // 24) * 56
            d.rectangle([x, yy, x + 52, yy + 52], outline="#cccccc")
            d.text((x + 8, yy + 4), chr(cp), font=gf, fill="black")
        im = im.crop((0, 0, W, min(640, y + 10 + 56 * ((len(cps) + 23) // 24) + 10)))
        p = look.path_for("specimen.png")
        im.save(p)
        look.add(p, "image", "specimen: three sizes plus the first 144 glyphs")
    except Exception as e:
        look.skip("specimen picture", f"{type(e).__name__}: {e}"[:100], None, "")
