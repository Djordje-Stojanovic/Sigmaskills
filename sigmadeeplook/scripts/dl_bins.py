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
import dl_util as U

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
    if b and look.size == len(b) or (b and look.size <= (64 << 20)):
        import dl_misc
        for t in dl_misc.record_layout(read_bytes(look, 64 << 20), look.size):
            look.headline = "Headerless binary file that looks like a table of fixed-size records (a guess from the bytes)"
            look.exit_code = 0   # a reader found a layout (labelled a guess): the run is not an unknown-type failure
            look.line(t, 93)
    if b:
        look.line("First 32 bytes: " + b[:32].hex(" ") + " | " + "".join(chr(c) if 32 <= c < 127 else "." for c in b[:32]), 52)
    st = [x for x in core.strings_of(b, 6, 4000) if wordy(x[2])]
    if st:
        look.write_text("strings.txt", "\n".join(f"{o:08x} {s[:200]}" for o, k, s in st), "printable strings that read as words, paths or names (min 6)")
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


COMMENT_RE = re.compile(r"^\s*(#|//|--|;|/\*|\*|<!--|')")
IMPORT_RE = re.compile(r"^\s*(import\s|from\s+\S+\s+import\s|#include\s|using\s+[\w.]+;|require\(|.*\brequire\s*\(|use\s+[\w:]+;)")


def code_counts(look, text, lines, lang, ol):
    """Exact counts of one source file: lines (blank, comment, code), definitions, classes, imports, tests, TODOs, env vars, constants."""
    import dl_prof as P
    blank = sum(1 for x in lines if not x.strip())
    comment = sum(1 for x in lines if x.strip() and COMMENT_RE.match(x))
    imports = [x.strip() for x in lines if IMPORT_RE.match(x)]
    todo = [i for i, x in enumerate(lines, 1) if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", x)]
    t = P.Tree()
    t.add(look.path.name, len(text.encode("utf-8", "replace")), text)
    funcs = [d for d in ol if d["kind"] == "def"]
    classes = [d for d in ol if d["kind"] == "class"]
    longest = max(range(len(lines)), key=lambda i: len(lines[i])) + 1 if lines else 0
    P.counts(look, [("lines", len(lines)), ("blank lines", blank), ("comment lines", comment), ("code lines", len(lines) - blank - comment),
                    ("definitions", len(ol) or t.defs or None), ("functions", len(funcs) or None), ("classes", len(classes) or t.classes or None),
                    ("imports", len(imports) or None), ("test functions", t.tests or None), ("TODO/FIXME", len(todo) or None),
                    ("environment variables", len(t.env) or None), ("constants", len(t.consts) or None), ("SQL tables created", len(t.sql_tables) or None),
                    ("longest line", f"{len(lines[longest - 1]):,} chars (line {longest})" if lines else None)], 93, f"{lang} counts")
    if t.env:
        look.line(f"Environment variables ({len(t.env)}): " + ", ".join(sorted(t.env)), 60)
    if t.consts:
        items = list(t.consts.items())
        look.line(f"Constants ({len(items)}): " + "; ".join(f"{k} = {v[1]}" for k, v in items[:40]), 45, "constants")
    if t.sql_tables:
        look.line(f"SQL tables created ({len(t.sql_tables)}): " + ", ".join(sorted(t.sql_tables)), 70)
    if imports:
        look.line(f"Imports ({len(imports)}): " + "; ".join(P.short(x, 60) for x in imports[:60]), 35)
    if todo:
        look.line(f"TODO/FIXME lines: " + ", ".join(map(str, todo[:40])), 35)
    if ol:
        for k in range(0, min(len(ol), 2000), 80):
            look.line(f"Definitions {k + 1}-{min(len(ol), k + 80)} of {len(ol)} (kind name @line):\n" + "\n".join(f"{d['kind']} {d['name']} @{d['line']}" for d in ol[k:k + 80]), 24, "outline")


def look_code(look):
    if look.path.is_dir():
        return look_repo(look)
    b = read_bytes(look, 8 << 20)
    text, enc = core.decode_text(b)
    ext = look.path.suffix.lower()
    if text is None and look.facts.get("text_by_content_model"):   # the content model calls it text although NULs or control bytes sit in it
        text, enc = core.lenient_text(b)
        look.flag("LENIENT-TEXT", "file", "NUL or control bytes read as spaces", "a content model said text; the byte-level detector said binary")
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
    import dl_prof as P
    prose = lang in ("Markdown", "Text") or ext in (".md", ".txt", ".rst", ".adoc", "", ".po", ".pot")
    if ext in (".po", ".pot") or (re.search(r'(?m)^msgid "', text) and re.search(r'(?m)^msgstr(\[\d+\])? "', text)):
        import dl_legacy
        if dl_legacy.po_facts(look, text):
            look.headline = look.headline or f"Gettext catalogue, {len(lines):,} lines"
    if prose:
        P.text_profile(look, text, 90, "Text")
    else:
        code_counts(look, text, lines, lang, ol)
    look.excerpt("First lines", "\n".join(lines[:15]), pri=20 if prose else 30)
    if rows:   # headers and signatures instead of bodies: as good for finding the place (Agentless), a fraction of the tokens
        look.write_text("skeleton.md", dl_skel.render(rows, len(lines)), f"signature skeleton: {len(rows)} definitions with line numbers and a doc remark", value=8)
        look.line(f"Skeleton: {len(rows)} definitions with their signatures in skeleton.md; the body of one is one call away.", 40)
        look.cmd("--func NAME", "the body of one function or class (--func list names them all)", None)
    else:
        look.write_text("head.txt", "\n".join(lines[:200]), "first 200 lines" + (f" of {len(lines):,}" if len(lines) > 200 else ""), inline=False if len(lines) <= 200 and look.size <= core.SOURCE_CONTENT_MAX else None,
                        partial=f"the first 200 of {len(lines):,} lines; the rest is NOT shown here (see the last lines and counts above)" if len(lines) > 200 else None)   # the whole file ends the stream
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
    langs = sorted(by_lang.items(), key=lambda kv: -kv[1][1])
    look.headline = f"Code repository, {len(files):,} files, {sum(s for _, s in files):,} bytes; " + ", ".join(f"{k} {v[0]:,}" for k, v in langs[:4])
    look.line(f"Code repository: {len(files)} files, {core.human(sum(s for _, s in files))} ({skipped} paths ignored by .gitignore; .git, node_modules and caches skipped).")
    import dl_prof as P
    tree, used, t0, texts = P.Tree(), 0, time.time(), {}
    for rel, sz in files:
        text = None
        if (P.is_text_name(rel) or P.is_manifest(rel)) and sz <= INNER_TEXT_MAX and used + sz <= 256 << 20 and time.time() - t0 < 90:
            try:
                text, _enc = core.decode_text((root / rel).read_bytes())
                used += sz
            except OSError:
                text = None
            if text is not None and (P.is_manifest(rel) and rel.count("/") <= 2 or rel.lower().endswith((".csv", ".tsv", ".jsonl"))):
                texts[rel] = text
        tree.add(rel, sz, text)
    tree.emit(look, "Repository", 92, [("ignored paths", skipped or None)])
    for n in sorted((n for n in texts if P.is_manifest(n)), key=lambda n: (n.count("/"), n))[:30]:
        for ln in P.manifest_lines(n, texts[n]):
            look.line(ln, 80 if n.count("/") == 0 else 60, "manifest")
    inner_tables(look, {n: t for n, t in texts.items() if not P.is_manifest(n)})
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
    base = struct.unpack_from("<Q", b, opt + 24)[0] if magic == 0x20B else struct.unpack_from("<I", b, opt + 28)[0]
    osv = struct.unpack_from("<HH", b, opt + 40)
    soi, _hs, csum, _sub, dllc = struct.unpack_from("<IIIHH", b, opt + 56)
    dllflags = [n for bit, n in ((0x40, "ASLR"), (0x20, "high-entropy ASLR"), (0x100, "DEP/NX"), (0x4000, "control-flow guard"), (0x400, "no SEH"), (0x1000, "AppContainer")) if dllc & bit]
    return {"image_base": base, "image_size": soi, "checksum": csum, "linker": f"{b[opt + 2]}.{b[opt + 3]}", "os_version": f"{osv[0]}.{osv[1]}", "mitigations": dllflags, "characteristics": chars,
            "machine": PE_MACHINES.get(machine, hex(machine)), "timestamp": ts, "subsystem": SUBSYS.get(subsystem, str(subsystem)),
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
            look.line(f"PE header: entry point RVA 0x{info['entry_rva']:x}, image base 0x{info['image_base']:x}, image size {info['image_size']:,} B, {len(info['sections'])} sections, "
                      f"linker {info['linker']}, minimum OS {info['os_version']}, mitigations: {', '.join(info['mitigations']) or 'none'}, header checksum {'set' if info['checksum'] else 'zero'}; "
                      f"{len(info['imports'])} imported DLLs.", 76)
            look.line("Section table (name, virtual size, raw size, rights): " + "; ".join(f"{x['name']} {x['vsize']:,} / {x['raw']:,} {x['perms']}" for x in info["sections"][:16]) + ".", 47)
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
            import dl_cls
            w = dl_cls.parse_wasm(b)
            look.headline = f"WebAssembly module: {len(w['imports'])} imports, {len(w['exports'])} exports, {w['imported_funcs'] + w['functions']} functions"
            for k, t in enumerate(dl_cls.wasm_lines(w)):
                look.line(t, 97 - k)
            look.fact("exports", [n for n, _ in w["exports"]])
        elif st == "java-class":
            import dl_cls
            c = dl_cls.parse_class(b)
            look.headline = f"Java class {c['name']}: {len(c['methods'])} methods, {len(c['fields'])} fields, Java {c['release']}"
            for k, t in enumerate(dl_cls.class_lines(c)):
                look.line(t, 97 - k)
            look.fact("methods", [m["name"] for m in c["methods"]])
        elif st == "dex":
            look.line("Android Dalvik executable (dex).")
        else:
            look.line(f"Binary of kind {st}.")
    except (struct.error, ValueError, IndexError) as e:
        look.flag("PARSE-ERROR", "header", str(e)[:100], "the header is truncated or malformed; strings and entropy still ran")
    look.fact("entropy", round(core.entropy(b[:4 << 20]), 3))
    st_list = [x for x in core.strings_of(b, 8, STRINGS_CAP) if wordy(x[2])]   # machine-code bytes that happen to be printable are not strings
    lines = [f"{o:08x} {k} {s[:300]}" for o, k, s in st_list]
    if lines:
        look.write_text("strings.txt", "\n".join(lines), f"ASCII and UTF-16LE strings (min 8, {len(lines)} shown, capped at {STRINGS_CAP})", value=-5)
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


_WORD = re.compile(r"[a-z]{4,}|[A-Za-z]{3,}[_./\:-][A-Za-z]{2,}|[A-Z][A-Z0-9]*_[A-Z0-9_]{3,}|https?://|\d{1,4}[.:/-]\d{1,4}[.:/-]\d{1,4}")


def wordy(s):
    """True when a printable run reads like text (a word, a path, a constant name, a version or date) rather than code bytes."""
    s = s.strip()
    if len(s) < 6:
        return False
    if not _WORD.search(s):
        return False
    return sum(c.isalnum() or c in " _./\\:-,'\"()%=@#<>[]{}$&*+?!;" for c in s) / len(s) >= 0.85


# ================================================================= archives
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_MEMBERS = 10000
MAX_TOTAL = 2 << 30
MAX_RATIO = 200
MAX_DEPTH = 2
TAR_LIST_SECONDS = U.byte_cap("TARLIST", 90)   # listing a compressed tar reads the whole stream: stop after this long and say PARTIAL


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
                members.append(dict(name=i.filename, size=i.file_size, packed=i.compress_size, kind=kind, enc=bool(i.flag_bits & 1), offset=i.header_offset,
                                    mtime="%04d-%02d-%02d %02d:%02d:%02d" % i.date_time))
        extra["format"] = "zip"
    elif tarfile.is_tarfile(p):
        t0 = time.time()
        with tarfile.open(p, "r:*") as t:
            for m in t:
                kind = "dir" if m.isdir() else "symlink" if m.issym() else "hardlink" if m.islnk() else "device" if (m.isdev() or m.isfifo()) else "file"
                members.append(dict(name=m.name, size=m.size, packed=0, kind=kind, enc=False, offset=m.offset_data, target=m.linkname,
                                    mtime=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(m.mtime)) if m.mtime else None))
                if len(members) > MAX_MEMBERS + 1:
                    break
                if time.time() - t0 >= TAR_LIST_SECONDS:   # a multi-GB .tar.xz is one stream: no print without a cap
                    extra["partial"] = True
                    break
        extra["format"] = "tar"
    return members, extra


# What a finding means. WIDE: the archive looks hostile, so no member is looked at or extracted (exit 2). EXTRACT_ONLY: the archive is too big to
# write out safely, but members are still read in memory under their own byte caps. Every other rule excludes only the member it names.
WIDE_RULES = {"unsafe-name", "unsafe-link", "overlap", "nesting"}
EXTRACT_ONLY_RULES = {"too-many-members", "too-large"}


def link_target_in_tree(m):
    """A link whose target is a relative path that stays inside the archive is harmless: it is listed and never followed.
    None when the listing does not show the target (a zip stores it as file content)."""
    tgt = m.get("target")
    if not tgt:
        return None
    t = tgt.replace("\\", "/")
    if t.startswith("/") or re.match(r"^[A-Za-z]:", t):
        return False
    base = [] if m["kind"] == "hardlink" else [x for x in m["name"].replace("\\", "/").split("/")[:-1] if x not in ("", ".")]
    depth = len(base)
    for part in t.split("/"):
        if part in ("", "."):
            continue
        depth += -1 if part == ".." else 1
        if depth < 0:
            return False
    return True


def screen_members(look, members, depth):
    """-> list of (rule, member, detail) findings. The safety screen from the plan, run on the listing only. split_screen() says what each finding blocks."""
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
            hostile = r.startswith(("absolute", "path traversal"))
            refusals.append(("unsafe-name" if hostile else "reserved-name", m["name"], r))
        if m["kind"] in ("symlink", "hardlink"):
            inside = link_target_in_tree(m)
            if inside is False:
                refusals.append(("unsafe-link", m["name"], f"{m['kind']} -> {m.get('target')} (leaves the archive)"))
            elif inside is None:
                refusals.append(("link", m["name"], f"{m['kind']} (target not shown in the listing)"))
        elif m["kind"] == "device":
            refusals.append(("device", m["name"], "device or fifo"))
        key = m["name"].replace("\\", "/").rstrip("/").lower()
        if key in seen and m["kind"] != "dir":
            refusals.append(("duplicate-name", m["name"], "same name twice"))
        seen.add(key)
        if m["packed"] and m["size"] / max(1, m["packed"]) > MAX_RATIO:
            refusals.append(("ratio", m["name"], f"ratio {m['size'] // max(1, m['packed'])}:1 (limit {MAX_RATIO}:1)"))
        if m["packed"] and m.get("offset") is not None:   # a 7-Zip listing gives no offsets: nothing to compare
            ranges.append((m["offset"], m["offset"] + m["packed"], m["name"]))
    ranges.sort()
    for a, b in zip(ranges, ranges[1:]):
        if b[0] < a[1]:
            refusals.append(("overlap", b[2], f"shares bytes with {a[2]}"))
            break
    if depth > MAX_DEPTH:
        refusals.append(("nesting", "archive", f"zip inside zip {depth} levels deep (limit {MAX_DEPTH})"))
    return refusals


def split_screen(refusals):
    """-> (wide, extract_only, excluded_names). wide: the archive is refused whole. extract_only: --extract is refused, member looks still run.
    excluded_names: members left out of member looks and extraction (a duplicated name is left out under every copy)."""
    wide = [r for r in refusals if r[0] in WIDE_RULES]
    xonly = [r for r in refusals if r[0] in EXTRACT_ONLY_RULES]
    excluded = {r[1] for r in refusals if r[0] not in WIDE_RULES and r[0] not in EXTRACT_ONLY_RULES}
    return wide, xonly, excluded


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

    def copy(src, name):
        nonlocal total
        out = target(name)
        out.parent.mkdir(parents=True, exist_ok=True)
        with src, open(out, "wb") as dst:
            while True:
                chunk = src.read(1 << 16)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_TOTAL or time.time() - t0 > core.TIMEOUT:
                    raise ValueError("extraction limit hit (bytes or time)")
                dst.write(chunk)
        written.append(out)

    if zipfile.is_zipfile(p) and look.subtype != "tar":
        with zipfile.ZipFile(p) as z:
            for name in which:
                info = z.getinfo(name)
                if not (info.is_dir() or info.flag_bits & 1):
                    copy(z.open(info), name)
    else:
        with tarfile.open(p, "r:*") as t:
            for name in which:
                m = t.getmember(name)
                if m.isfile():
                    copy(t.extractfile(m), name)
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
        out.append(f"{len(nested)} members are archives themselves, e.g. {', '.join(nested[:2])}.")
    risky = [m["name"] for m in files if m["name"].lower().endswith(RISKY_EXT)]
    if risky:
        out.append(f"{len(risky)} runnable-looking members (never run), e.g. {', '.join(risky[:3])}.")
    notable = [m["name"] for m in files if os.path.basename(m["name"]).lower() in ("readme", "readme.md", "package.json", "setup.py", "pyproject.toml", "manifest.json", "install.ps1", "install.sh", "license")]
    if notable:
        out.append("Notable files: " + ", ".join(notable[:4]))
    return out


INNER_TEXT_MAX = 4 << 20      # bytes of one member read in memory (never written to disk)
INNER_TOTAL_MAX = 96 << 20    # bytes read over all members
INNER_TABLE_MAX = 32 << 20    # a CSV/TSV/JSON member up to this size gets its own profile


def member_reader(look, fmt):
    """-> (open function name -> bytes, closer). Reads members in memory with a size cap; zip and tar only."""
    if fmt == "zip":
        z = zipfile.ZipFile(look.path)

        def read(name, cap):
            info = z.getinfo(name)
            if info.flag_bits & 1:
                return None
            with z.open(info) as f:
                return f.read(cap + 1)
        return read, z.close
    if fmt == "tar":
        t = tarfile.open(look.path, "r:*")

        def read(name, cap):
            m = t.getmember(name)
            if not m.isfile():
                return None
            return t.extractfile(m).read(cap + 1)
        return read, t.close
    sz = look.tool("7z")
    if sz:
        def read(name, cap):   # streamed to memory: `7z e -so` writes nothing to disk
            r = core.run_tree([sz, "e", "-so", "-y", str(look.path), name], 40)
            return r.stdout[:cap + 1] if r.returncode == 0 else None
        return read, (lambda: None)
    return None, (lambda: None)


NEST_OPEN = (".zip", ".jar", ".war", ".whl", ".nupkg", ".tar", ".tgz", ".tar.gz", ".tar.xz", ".tar.bz2", ".txz", ".tbz2")
SMALL_NOTE = 600              # a text member this short is quoted whole
SMALL_ANY = 65536             # a member this small is read whatever its name: a file with no extension is often text
INNER_NEST_MAX = 48 << 20     # a nested archive up to this size is opened in memory


def _is_textname(name):
    import dl_prof as P
    return P.is_text_name(name) or P.is_manifest(name)


def nested_items(b, outer, depth, budget):
    """Members of an archive held in memory -> (name, size, text or None); one more level for archives inside it (depth 2 at most).
    Reads only text-like members of up to 4 MB; budget[0] counts the bytes read so far over the whole look."""
    out = []
    try:
        if zipfile.is_zipfile(io.BytesIO(b)):
            z = zipfile.ZipFile(io.BytesIO(b))
            infos = [i for i in z.infolist() if not i.is_dir()][:5000]

            def get(i):
                return None if i.flag_bits & 1 else z.open(i).read(INNER_TEXT_MAX + 1)
            ent = [(i.filename, i.file_size, i) for i in infos]
        else:
            t = tarfile.open(fileobj=io.BytesIO(b), mode="r:*")
            ms = [m for m in t.getmembers() if m.isfile()][:5000]

            def get(m):
                return t.extractfile(m).read(INNER_TEXT_MAX + 1)
            ent = [(m.name, m.size, m) for m in ms]
    except Exception:
        return out
    for name, size, h in ent:
        text = None
        if depth < 2 and name.lower().endswith(NEST_OPEN) and size <= INNER_NEST_MAX and budget[0] + size <= INNER_TOTAL_MAX:
            try:
                nb = get(h) if size <= INNER_TEXT_MAX else None
            except Exception:
                nb = None
            if nb is not None:
                budget[0] += len(nb)
                for n2, s2, t2 in nested_items(nb, name, depth + 1, budget):
                    out.append((f"{name}!/{n2}", s2, t2))
        elif size <= INNER_TEXT_MAX and (_is_textname(name) or 0 < size <= SMALL_ANY) and budget[0] + size <= INNER_TOTAL_MAX:
            try:
                bb = get(h)
            except Exception:
                bb = None
            if bb is not None:
                budget[0] += len(bb)
                text, _enc = core.decode_text(bb)
        out.append((name, size, text))
    return out


def archive_contents(look, members, fmt):
    """What is inside, read in memory: tree stats (lines, languages, tests, env vars, constants), every manifest / README / licence /
    changelog, and a field profile of each table (CSV, TSV, JSON, JSONL) member. Nothing is extracted to disk."""
    import dl_prof as P
    read, close = member_reader(look, fmt)
    tree = P.Tree()
    files = [m for m in members if m["kind"] == "file"]
    used, t0 = 0, time.time()
    texts = {}
    opened, small, xml_done = [], {}, 0
    try:
        for m in files:
            name, size = m["name"], m["size"]
            text = None
            if read and not m["enc"] and name.lower().endswith(NEST_OPEN) and size <= INNER_NEST_MAX and used + size <= INNER_TOTAL_MAX and time.time() - t0 < 60:
                try:
                    nb = read(name, INNER_NEST_MAX)
                except Exception:
                    nb = None
                if nb is not None and len(nb) <= INNER_NEST_MAX:
                    used += len(nb)
                    n_in = 0
                    for iname, isize, itext in nested_items(nb, name, 1, [used]):
                        tree.add(f"{name}!/{iname}", isize, itext)
                        n_in += 1
                        if itext is not None and len(itext) <= SMALL_NOTE and not P.is_manifest(iname):
                            small[f"{name}!/{iname}"] = itext
                        if itext is not None and (P.is_manifest(iname) or iname.lower().endswith((".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".toml", ".xml", ".properties", ".ini", ".cfg", ".txt", ".md"))):
                            texts[f"{name}!/{iname}"] = itext
                    opened.append(f"{name} ({n_in} inner files)")
            want = read and not m["enc"] and (P.is_text_name(name) or P.is_manifest(name) or 0 < size <= SMALL_ANY) and size <= max(INNER_TEXT_MAX, INNER_TABLE_MAX if name.lower().endswith((".csv", ".tsv", ".json", ".jsonl", ".ndjson")) else 0)
            if want and used + size <= INNER_TOTAL_MAX and time.time() - t0 < 60:
                try:
                    b = read(name, max(INNER_TEXT_MAX, INNER_TABLE_MAX))
                except Exception:
                    b = None
                if b is not None:
                    used += len(b)
                    text, _enc = core.decode_text(b)
                    if name.lower().endswith((".xml", ".vml", ".xaml")) and xml_done < 10:   # parsed whatever its line layout: one-line XML is not a 60-character head
                        import dl_xmlvals
                        xml_done += 1 if dl_xmlvals.member_lines(look, name, b) else 0
                    if text is not None and len(text) <= SMALL_NOTE and not P.is_manifest(name):
                        small[name] = text
                    if text is not None and (P.is_manifest(name) or name.lower().endswith((".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".toml", ".xml", ".properties", ".ini", ".cfg"))):
                        texts[name] = text
            tree.add(name, size, text)
    finally:
        close()
    for n, t in list(small.items())[:20]:
        if t.strip():
            look.line(f"Small text member {n}: " + " | ".join(x.strip() for x in t.strip().splitlines()[:8])[:SMALL_NOTE], 64, "small")
    if opened:
        look.line("Archives inside this archive, opened in memory (nested names are written outer!/inner): " + "; ".join(opened[:10]) + ".", 91)
    tree.emit(look, "Contents", 90, [("members", len(members)), ("folders", sum(1 for m in members if m["kind"] == "dir") or None),
                                     ("encrypted members", sum(1 for m in members if m["enc"]) or None), ("bytes read to look inside", used)])
    # member dates
    dates = sorted(m["mtime"] for m in files if m.get("mtime"))
    if dates:
        look.line(f"Member dates: earliest {dates[0]}, latest {dates[-1]} ({len(set(d[:10] for d in dates))} distinct days).", 70)
    manis = sorted((n for n in texts if P.is_manifest(n)), key=lambda n: (n.count("/"), n))
    for n in manis[:40]:
        base = n.rsplit("/", 1)[-1].lower()
        pri = 86 if base in ("manifest.mf", "metadata", "pkg-info", "package.json", "pyproject.toml", "pom.properties", "pom.xml", "cargo.toml", "setup.py", "setup.cfg") else 74
        for ln in P.manifest_lines(n, texts[n]):
            look.line(ln, pri, "manifest")
    if len(manis) > 40:
        look.line(f"{len(manis) - 40} more manifests or READMEs not shown: " + ", ".join(manis[40:80]), 30)
    inner_tables(look, texts)
    other = [n for n in texts if not P.is_manifest(n) and n.lower().endswith((".yaml", ".yml", ".toml", ".properties", ".ini", ".cfg", ".xml"))][:12]
    for n in other:
        t = texts[n]
        kv = [ln.strip() for ln in t.splitlines() if ln.strip() and not ln.lstrip().startswith(("#", ";", "<!--"))][:40]
        look.line(f"Config member {n} ({len(t.splitlines())} lines): " + " | ".join(P.short(x, 80) for x in kv), 40, "config")


MEMBER_LOOK_EXT = {".xlsx", ".xlsm", ".xls", ".ods", ".docx", ".doc", ".odt", ".pptx", ".odp", ".pdf", ".sqlite", ".sqlite3", ".db", ".parquet", ".avro", ".orc", ".npz", ".npy", ".dta",
                   ".mid", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".eml", ".ics", ".vcf", ".torrent", ".plist", ".pyc", ".class", ".wasm", ".exe", ".dll", ".deb", ".stl",
                   ".glb", ".log", ".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".epub", ".duckdb", ".pcap", ".evtx", ".ipynb"}
MEMBER_LOOK_N = 8             # members of a document or media type that get a look of their own, in place
MEMBER_LOOK_BYTES = 40 << 20
MEMBER_LOOK_TOKENS = 420      # facts carried up from one member's look


def member_looks(look, members, fmt):
    """After the safety screen passed: the members that are documents, tables, media or binaries get their own look (written under the look folder,
    never run), and their top facts are carried up here, because a list of names says nothing about what the file inside holds."""
    if getattr(look, "depth", 0) >= 1 or look.quick or not hasattr(core, "recurse_into"):
        return
    read, close = member_reader(look, fmt)
    if not read:
        return
    import dl_write
    files = [m for m in members if m["kind"] == "file" and not m["enc"] and 0 < m["size"] <= MEMBER_LOOK_BYTES and os.path.splitext(m["name"])[1].lower() in MEMBER_LOOK_EXT]
    t0, done = time.time(), 0
    try:
        for m in files[:MEMBER_LOOK_N]:
            if time.time() - t0 > 150:
                look.line(f"Member looks stopped after {done} members (time cap); the rest are named in the list.", 30)
                break
            try:
                b = read(m["name"], MEMBER_LOOK_BYTES)
            except Exception:
                b = None
            if b is None or len(b) > MEMBER_LOOK_BYTES:
                continue
            d = look.out / "members" / f"{done + 1:02d}"
            d.mkdir(parents=True, exist_ok=True)
            fp = d / re.sub(r"[^\w.\-]+", "_", os.path.basename(m["name"].replace("\\", "/")))
            fp.write_bytes(b)
            tier = "quick" if os.path.splitext(fp.name)[1].lower() in (".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a", ".mp4", ".mkv", ".mov", ".avi", ".webm") and len(b) > (8 << 20) else "standard"
            c = core.recurse_into(look, fp, m["name"], tier)
            done += 1
            chunks = [x for x in (c.stream or []) if x["sec"] in ("watch", "key")]
            chunks.sort(key=lambda x: -x["pri"])
            used, picked = 0, []
            for x in chunks:
                if used + x["tok"] > MEMBER_LOOK_TOKENS and picked:
                    break
                picked.append(x["text"])
                used += x["tok"]
            if picked:
                look.line(f"Member {m['name']} ({c.type}/{c.subtype}), looked at in place: " + " | ".join(" ".join(t.split()) for t in picked), 66, "member")
    finally:
        close()


def inner_tables(look, texts):
    """Each CSV/TSV/JSON/JSONL member: rows, columns and an exact field profile (sums, counts, extremes)."""
    import dl_prof as P
    k = 0
    for n, t in texts.items():
        low = n.lower()
        if not low.endswith((".csv", ".tsv", ".json", ".jsonl", ".ndjson")) or k >= 8 or P.is_manifest(n):
            continue
        k += 1
        try:
            if low.endswith((".csv", ".tsv")):
                import dl_delim as D
                delim = D.sniff_dialect(t, "\t" if low.endswith(".tsv") else ",")[0]
                rows = list(csv.reader(io.StringIO(t, newline=""), delimiter=delim))
                if not rows:
                    continue
                head, body = rows[0], rows[1:]
                norm = D.normalizer(D.decimal_comma_columns(t, delim, len(head)))
                if norm:
                    body = [norm(r) if len(r) == len(head) else r for r in body]
                good = [(i + 2, r) for i, r in enumerate(body) if len(r) == len(head)]
                p = P.Profiler(True, "line")
                cols = p.columns([h.lstrip("﻿").strip() or f"column {i + 1}" for i, h in enumerate(head)])
                for ln, r in good:
                    p.add_row(cols, r, ln)
                sp = P.SecondPass(p)
                names = [f.name for f in cols]
                for ln, r in good:
                    sp.add_row(names, r, ln)
                look.line(f"Member table {n}: {len(body):,} data rows, {len(head)} columns, {len(body) - len(good)} rows with the wrong field count. Columns (exact over every row, positions are member line numbers):\n"
                          + "\n".join("  " + x for x in p.field_lines()), 72, "profile")
                for x in p.stats_lines() + sp.lines():
                    look.line(f"{n}: {x}", 34, "aggregates")
                for x in p.enum_lines():
                    look.line(f"{n}: {x}", 28, "values")
            else:
                import json as _j
                if low.endswith((".jsonl", ".ndjson")):
                    recs = [(i, _j.loads(x)) for i, x in enumerate(t.splitlines(), 1) if x.strip()]
                    p, extra = P.profile(recs, False, "line")
                    P.emit(look, p, extra, f"Member {n} (JSON Lines)", 70, 28)
                else:
                    P.doc_profile(look, _j.loads(t), f"Member {n}", 70)
        except Exception as e:
            look.line(f"Member {n}: could not be profiled ({type(e).__name__}: {P.short(e, 80)})", 40)


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
                members.append(dict(name=cur["Path"], size=int(cur.get("Size") or 0), packed=int(cur.get("Packed Size") or 0), kind=kind, enc=cur.get("Encrypted") == "+", offset=None))
            cur = {}
            continue
        if "=" in ln:
            k, v = ln.split("=", 1)
            (cur if in_files else extra).__setitem__(k.strip(), v.strip())
    if in_files and cur.get("Path"):
        members.append(dict(name=cur["Path"], size=int(cur.get("Size") or 0), packed=int(cur.get("Packed Size") or 0), kind="file", enc=cur.get("Encrypted") == "+", offset=None))
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
        keep = bytearray()
        inner = re.sub(r"\.(gz|bz2|xz|tgz)$", "", p.name, flags=re.I) or "member"
        if inner == p.name or "." not in inner:
            inner = (inner if inner != p.name else p.stem) or "member"
        unpacked = look.path_for(f"unpacked/{inner}")
        too_big = False
        try:
            with opener(p, "rb") as f, open(unpacked, "wb") as w:
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    n += len(chunk)
                    if len(keep) <= INNER_TABLE_MAX:
                        keep += chunk
                    if n > UNWRAP_MAX or n > MAX_RATIO * 5 * max(1, look.size):
                        too_big = True
                        break
                    w.write(chunk)
        except (OSError, EOFError, lzma.LZMAError) as e:
            look.flag("CORRUPT", "stream", str(e)[:100], "")
        ratio = n / max(1, look.size)
        look.line(f"Single {st} stream: {core.human(look.size)} packed, {'at least ' if too_big else ''}{core.human(n)} unpacked (ratio {ratio:.0f}:1).", 89)
        look.fact("unpacked_bytes_at_least" if too_big else "unpacked_bytes", n)
        if too_big:
            unpacked.unlink(missing_ok=True)
            look.exit_code = 2
            look.flag("REFUSED", "stream", f"ratio {ratio:.0f}:1, {core.human(n)}+", "possible compression bomb or over the unpack cap; not unpacked")
            return
        import dl_prof as P
        P.counts(look, [("packed bytes", look.size), ("unpacked bytes", n)])
        d = core.detect(unpacked)
        if d["type"] not in ("archive", "unknown") and core.HANDLERS.get(d["type"]):   # look at the one member as the file it is
            unwrap(look, unpacked, d, st)
            return
        if n <= INNER_TABLE_MAX:   # the one member, read in memory: profile it like the file it is
            text, _enc = core.decode_text(bytes(keep))
            if text is not None:
                look.line(f"Unpacked member {inner}: {text.count(chr(10)):,} lines, {len(text):,} characters (read in memory, nothing written).", 88)
                if inner.lower().endswith((".csv", ".tsv", ".json", ".jsonl", ".ndjson")):
                    inner_tables(look, {inner: text})
                else:
                    P.text_profile(look, text, 70, "Member text")
        return
    depth = 0
    if extra.get("format") == "zip":
        depth = zip_depth(read_bytes(look, 64 << 20)) if look.size < 64 << 20 else 0
    refusals = screen_members(look, members, depth)
    wide, xonly, excluded = split_screen(refusals)
    if extra.get("partial"):
        look.flag("PARTIAL", "listing", f"stopped after {len(members):,} members ({TAR_LIST_SECONDS} s time cap on the compressed stream)", "member counts, sizes and the screen cover the part listed only")
    nfile = sum(1 for m in members if m["kind"] == "file")
    total = sum(m["size"] for m in members)
    ratios = [m["size"] / max(1, m["packed"]) for m in members if m["packed"]]
    look.fact("members", len(members))
    look.fact("files", nfile)
    look.fact("uncompressed_bytes", total)
    look.fact("max_ratio", round(max(ratios), 1) if ratios else 0)
    look.fact("nesting_depth", depth)
    cut = " (PARTIAL: listing stopped at the time cap)" if extra.get("partial") else ""
    look.headline = f"{st} archive, {len(members):,}{'+' if cut else ''} members, {nfile:,} files, {core.human(total)} unpacked{cut}"
    look.line(f"Archive ({extra.get('format', st)}): {len(members)}{'+' if cut else ''} members, {nfile} files, {core.human(total)} uncompressed ({core.human(look.size)} packed), largest ratio {max(ratios) if ratios else 0:.0f}:1" + (f", nesting depth {depth}" if depth else "") + (". PARTIAL: the compressed stream was listed until the time cap; the real archive has more." if cut else "."))
    if extra.get("format") == "zip":   # container-level key/value text: the archive comment and member comments
        try:
            with zipfile.ZipFile(p) as zz:
                zc = zz.comment.decode("utf-8", "replace").strip()
                mc = [(i.filename, i.comment.decode("utf-8", "replace").strip()) for i in zz.infolist() if i.comment]
            if zc or mc:
                look.line("Zip comments: " + (f"archive comment {zc[:300]!r}" if zc else "no archive comment") + (f"; {len(mc)} member comments: " + "; ".join(f"{n}: {c[:80]}" for n, c in mc[:10]) if mc else ""), 88, "props")
        except (zipfile.BadZipFile, OSError):
            pass
    for ln in archive_overview(members):
        look.line(ln)
    try:
        archive_contents(look, members, extra.get("format"))
    except Exception as e:  # the listing stands even when a member cannot be read
        look.fail("member contents (manifests, tables, tree stats)", "stdlib", e)
    if not wide and extra.get("format") in ("zip", "tar", "7z", "iso", "rar"):
        try:
            member_looks(look, [m for m in members if m["name"] not in excluded], extra.get("format"))
        except Exception as e:
            look.fail("member looks (documents and media inside the archive)", "stdlib", e)
    rows =[(m["name"], m["size"], m["packed"], f"{m['size'] / max(1, m['packed']):.1f}" if m["packed"] else "", m["kind"], "encrypted" if m["enc"] else "") for m in members[:2000]]
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
    blocked = wide or xonly
    verdict = {"extract": not blocked, "reasons": [dict(rule=r, member=m, detail=d) for r, m, d in refusals], "excluded_members": sorted(excluded)}
    if wide:
        look.exit_code = 2
        for r, m, d in wide[:12]:
            look.flag("REFUSED", m, f"{r}: {d}", "the safety screen refuses the archive")
        look.line("Safety screen: REFUSED. " + "; ".join(f"{r} ({m})" for r, m, d in wide[:4]))
    elif xonly or excluded:
        for r, m, d in xonly[:3]:
            look.flag("EXTRACT-LIMIT", m, f"{r}: {d}", "--extract is not offered; members are still read in memory under their own caps")
        left = [x for x in refusals if x[0] not in WIDE_RULES and x[0] not in EXTRACT_ONLY_RULES]
        for r, m, d in [x for x in left if x[0] == "ratio"][:6]:
            look.flag("REFUSED", m, f"{r}: {d}", "this member is not read or extracted (possible compression bomb); the rest of the archive is")
        look.line("Safety screen: passed for reading" + ("" if not xonly else "; extraction refused (" + "; ".join(f"{r}: {d}" for r, m, d in xonly[:2]) + ")")
                  + (f"; {len(excluded)} member(s) left out of member looks and extraction: " + "; ".join(f"{m} ({r})" for r, m, d in left[:4]) + (" ..." if len(left) > 4 else "") if excluded else "") + ".")
    else:
        look.line("Safety screen: passed (names, links, ratios, overlaps).")
    look.write_text("screen.json", json.dumps(verdict, indent=1), "extraction screen verdict", "json")
    want_n = look.recurse
    if (look.extract or want_n) and extra.get("format") not in ("zip", "tar"):
        look.skip("extraction of members", f"{extra.get('format', st)} archives are listed and screened only; extraction is built for zip and tar", None, f'7z x "{p}" -o<empty folder>  (after the screen above passed)')
        look.step("list and screen", "7-Zip")
        return
    if (look.extract or want_n) and not blocked:
        pick = [m["name"] for m in members if m["kind"] == "file" and not m["enc"] and m["name"] not in excluded]
        pick = pick if look.extract else pick[:want_n]
        try:
            done = safe_extract(look, members, pick, look.out / "extract")
            look.line(f"Extracted {len(done)} files to `{look.out / 'extract'}`.")
            look.fact("extracted", len(done))
            for d in done[:want_n]:
                core.recurse_into(look, d, str(d.relative_to(look.out / "extract")))
        except (ValueError, OSError, KeyError, tarfile.TarError, zipfile.BadZipFile) as e:
            look.flag("EXTRACT-STOPPED", "extract", str(e)[:150], "")
    elif (look.extract or want_n) and blocked:
        look.exit_code = 2
        look.line("--extract was given but the screen refused: nothing was written.")
    elif not look.extract and st != "epub":
        look.skip("member contents", "listed only; pass --extract (or --recurse N) after the screen passes", None, "python look.py FILE --extract")
    if st == "epub" and not wide:   # a book: its structure leads; the package listing above moves to --more
        look.items = [(it[0], min(it[1], 35), *it[2:]) for it in look.items]
        import dl_books
        dl_books.look_epub(look)
    look.step("list and screen", "stdlib")
    look.ask_human("Do you trust where this archive came from?", "Should the members be extracted and looked at (--extract / --recurse N)?")


UNWRAP_MAX = 2 << 30   # bytes: a single compressed stream is unpacked to the look folder up to this size (the ratio screen still applies)


def unwrap(look, inner, d, outer_kind):
    """A single compressed stream (x.csv.gz, x.log.xz, x.pcap.gz, x.json.bz2): run the inner file's own look on the unpacked copy,
    so the member gets every count its type gets uncompressed. The outer identity (archive/gzip) stays."""
    keep = (look.path, look.size, look.type, look.subtype)
    look.fact("unpacked_from", str(look.path))
    look.fact("unpacked", str(inner))
    look.fact("inner_type", f"{d['type']}/{d['subtype']}")
    look.path, look.size, look.type, look.subtype = Path(inner), Path(inner).stat().st_size, d["type"], d["subtype"]
    look.line(f"One {outer_kind} member, {inner.name} ({d['type']}/{d['subtype']}, {core.human(look.size)} unpacked into the look folder): every fact below is about it.", 98, "identity")
    try:
        mod, fn = core.HANDLERS[d["type"]]
        getattr(__import__(mod), fn)(look)
        core.add_source_content(look)
    finally:
        inner_head = look.headline
        look.path, look.size, look.type, look.subtype = keep
        if inner_head:
            look.headline = f"{outer_kind} of {inner.name}: {inner_head}"


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
                    ms, t1 = [], time.time()
                    for mm in lt:   # member by member: a huge layer stops at the time cap instead of listing for minutes
                        ms.append(mm)
                        if time.time() - t1 >= TAR_LIST_SECONDS:
                            break
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
    if font is not None:
        try:
            font_details(look, font, facts)
        except Exception as e:
            look.fail("font metrics", "fontTools", e)
    for k, v in facts.items():
        look.fact(k, v)
    if facts.get("family") or facts.get("glyphs"):
        look.headline = f"Font {facts.get('full_name') or facts.get('family')!r} ({st}): {facts.get('glyphs', '?')} glyphs, {'variable' if facts.get('variable') else 'static'}; {len(facts.get('tables', []))} tables"
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


def font_details(look, font, facts):
    """Name records, design metrics, style bits and layout features: the facts a type designer or a web developer asks first."""
    h = font["head"]
    labels = {0: "copyright", 1: "family", 2: "subfamily", 3: "unique id", 4: "full name", 5: "version string", 6: "PostScript name", 7: "trademark", 8: "manufacturer",
              9: "designer", 11: "vendor URL", 12: "designer URL", 13: "licence", 14: "licence URL", 16: "typographic family", 17: "typographic subfamily"}
    got = {}
    for rec in font["name"].names:
        if rec.nameID in labels and rec.nameID not in got:
            try:
                got[rec.nameID] = rec.toUnicode()
            except Exception:
                pass
    look.line("Name records: " + "; ".join(f"{labels[i]} = {got[i][:90]}" for i in sorted(got)) + ".", 74)
    bits = []
    bits.append(f"{h.unitsPerEm} units per em, font revision {float(h.fontRevision):.3f}")
    bits.append(f"glyph box x {h.xMin}..{h.xMax}, y {h.yMin}..{h.yMax}")
    bits.append("macStyle: " + ", ".join(n for bit, n in ((1, "bold"), (2, "italic"), (4, "underline")) if h.macStyle & bit) if h.macStyle else "macStyle: regular")
    if "OS/2" in font:
        o = font["OS/2"]
        sel = [n for bit, n in ((1, "italic"), (32, "bold"), (64, "regular"), (512, "oblique")) if o.fsSelection & bit]
        bits.append(f"OS/2 weight class {o.usWeightClass}, width class {o.usWidthClass}, fsSelection {'+'.join(sel) or 'none'}, typo ascender {o.sTypoAscender}, typo descender {o.sTypoDescender}, "
                    f"line gap {o.sTypoLineGap}, win ascent {o.usWinAscent}, win descent {o.usWinDescent}"
                    + (f", x-height {o.sxHeight}, cap height {o.sCapHeight}" if getattr(o, "version", 0) >= 2 and getattr(o, "sxHeight", 0) else ""))
    if "hhea" in font:
        hh = font["hhea"]
        bits.append(f"hhea ascent {hh.ascent}, descent {hh.descent}, line gap {hh.lineGap}")
    if "post" in font:
        bits.append(f"italic angle {font['post'].italicAngle}, fixed pitch {'yes' if font['post'].isFixedPitch else 'no'}")
    try:
        import datetime
        epoch = datetime.datetime(1904, 1, 1)
        bits.append(f"head created {(epoch + datetime.timedelta(seconds=h.created)).date()}, modified {(epoch + datetime.timedelta(seconds=h.modified)).date()}")
    except Exception:
        pass
    look.line("Design metrics: " + "; ".join(bits) + ".", 73)
    feats = {}
    for tab in ("GSUB", "GPOS"):
        if tab in font and getattr(font[tab].table, "FeatureList", None):
            feats[tab] = sorted({r.FeatureTag for r in font[tab].table.FeatureList.FeatureRecord})
    scripts = sorted({r.ScriptTag for tab in ("GSUB", "GPOS") if tab in font and getattr(font[tab].table, "ScriptList", None) for r in font[tab].table.ScriptList.ScriptRecord})
    if feats or scripts:
        look.line("Layout features: " + "; ".join(f"{t} {', '.join(v)}" for t, v in feats.items()) + (f"; scripts {', '.join(scripts)}" if scripts else "") + ".", 66)
    look.line(f"cmap subtables: {len(font['cmap'].tables)}; kern table {'present' if 'kern' in font else 'absent'}; hinting {'TrueType instructions (fpgm/prep)' if 'fpgm' in font or 'prep' in font else 'none or unhinted'}; "
              f"glyph outlines {'CFF (OpenType)' if 'CFF ' in font or 'CFF2' in font else 'TrueType quadratic'}.", 60)
    facts["units_per_em"] = h.unitsPerEm


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
