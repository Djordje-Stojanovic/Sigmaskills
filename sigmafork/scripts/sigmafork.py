#!/usr/bin/env python3
"""SigmaFork helper: copy a repo so the copy never writes into the original.

  python sigmafork.py copy   SRC DEST [--exclude PATTERN ...] [--no-git] [--keep-heavy]
  python sigmafork.py scan   DEST --source SRC [--map OLD=NEW ...] [--json]
  python sigmafork.py fix    DEST --source SRC [--map OLD=NEW ...]
  python sigmafork.py verify DEST --source SRC
  python sigmafork.py stats  DEST [--json] [--exclude PATTERN ...]
  python sigmafork.py guide  DEST [--source SRC] [--out FILE] [--check] [--exclude PATTERN ...]
  python sigmafork.py selftest

copy    Copies SRC to a new, empty DEST. Skips caches and installed dependencies (node_modules, venvs,
        __pycache__) unless --keep-heavy. A link (symlink or junction) that points inside SRC is made
        again inside DEST, pointing at the same place in the copy; a link that points outside SRC is
        copied as real files. It never overwrites a file. Log: DEST/.sigmafork/copy.json.
scan    Finds every spelling of the source path in the copy's text files (C:\\x, C:/x, C:\\\\x, /c/x,
        /mnt/c/x, file:///C:/x), links into the source, git remotes into the source, other absolute
        paths outside the copy, and relative paths that climb out of it.
fix     Rewrites each source spelling to the same spelling of DEST (and each --map pair). Bytes only,
        so line endings and encodings stay. Log: DEST/.sigmafork/paths.json.
verify  Exit 0 when nothing in the copy can reach the source; exit 1 lists what still can.
stats   Counts what the repo really holds: files, folders, code lines (no blank lines, no comment lines),
        doc lines, languages, the biggest code files. Leaves out installed dependencies, build output,
        caches, venvs and generated files (lock files, minified bundles, "do not edit" headers), and says
        how much it left out.
guide   Makes DEST/ONBOARDING.html from the course template when it is missing, then writes the stats
        and the copy facts (copy.json, paths.json, verify with --source) into its data block. The page
        draws the numbers band, the folder explorer and the isolation figure from that block. Run it
        again after any change. --check lists what is still wrong: FILL left and no data block (exit 1);
        long paragraphs, chip-heavy text, terms without a definition, too few figures (fixes, exit 0).

Standard library only. Exit codes: 0 fine, 1 hits remain or a check failed, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HEAVY = {"node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
         ".next", ".turbo", ".parcel-cache", ".gradle", ".tox", ".cache"}
NOISE = {".DS_Store", "Thumbs.db", "desktop.ini"}
SKIP_SCAN_DIRS = HEAVY | {".git", ".sigmafork", ".hg", ".svn"}
MAX_SCAN_BYTES = 5 * 1024 * 1024
LOG_DIR = ".sigmafork"
NAME_CHAR = rb"[A-Za-z0-9_\-]"


# ---------- path spellings ----------

def _parts(root: str):
    """(drive letter or '', [components]) of an absolute path written Windows or POSIX style."""
    r = root.replace("\\", "/").rstrip("/")
    m = re.match(r"^([A-Za-z]):(/.*)?$", r)
    if m:
        return m.group(1), [p for p in (m.group(2) or "").split("/") if p]
    return "", [p for p in r.split("/") if p]


def spellings(root: str):
    """Every way a text file may write this absolute path: list of (style, string)."""
    drive, comps = _parts(root)
    if not drive:
        posix = "/" + "/".join(comps)
        return [("posix", posix)]
    body = comps
    return [
        ("file", "file:///" + drive + ":/" + "/".join(body)),
        ("escaped", drive + ":\\\\" + "\\\\".join(body)),
        ("back", drive + ":\\" + "\\".join(body)),
        ("fwd", drive + ":/" + "/".join(body)),
        ("wsl", "/mnt/" + drive.lower() + "/" + "/".join(body)),
        ("gitbash", "/" + drive.lower() + "/" + "/".join(body)),
    ]


def render(root: str, style: str) -> str:
    """The new root written in the same style as the hit it replaces."""
    drive, comps = _parts(root)
    if not drive:  # the copy lives on a POSIX path: every style becomes that path
        return ("file://" if style == "file" else "") + "/" + "/".join(comps)
    return dict(spellings(root))[style] if style != "posix" else drive + ":/" + "/".join(comps)


def _tail(root: str) -> bytes:
    """The last folder name, lower case: every spelling of the root contains it."""
    comps = _parts(root)[1]
    return (comps[-1] if comps else root).lower().encode()


def pattern(old: str):
    """One bytes regex for all spellings of old, longest first, ending at a path boundary."""
    alts, styles = [], {}
    for style, text in sorted(spellings(old), key=lambda s: -len(s[1])):
        alts.append(re.escape(text.encode()))
        styles[text.lower()] = style
    flags = re.IGNORECASE if _parts(old)[0] else 0
    rx = re.compile(b"(?:" + b"|".join(alts) + b")(?!" + NAME_CHAR + rb"|\.[A-Za-z0-9_])", flags)
    return rx, styles


# ---------- walking ----------

def _is_link(p: Path) -> bool:
    return p.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(p))


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _real(p) -> Path:
    return Path(os.path.realpath(p))


def text_files(dest: Path):
    for dirpath, dirnames, filenames in os.walk(dest):
        dirnames[:] = [d for d in dirnames if d not in SKIP_SCAN_DIRS and not _is_link(Path(dirpath, d))]
        for name in filenames:
            p = Path(dirpath, name)
            if _is_link(p):
                continue
            try:
                if p.stat().st_size > MAX_SCAN_BYTES:
                    continue
                with open(p, "rb") as fh:
                    head = fh.read(8192)
                    if b"\0" in head:
                        continue
                    data = head + fh.read()
            except OSError:
                continue
            yield p, data
    cfg = dest / ".git" / "config"
    if cfg.is_file():
        yield cfg, cfg.read_bytes()


def links(dest: Path):
    for dirpath, dirnames, filenames in os.walk(dest):
        for name in list(dirnames) + filenames:
            p = Path(dirpath, name)
            if _is_link(p):
                yield p
        dirnames[:] = [d for d in dirnames if not _is_link(Path(dirpath, d)) and d != ".git"]


# ---------- copy ----------

def _excluded(rel: str, name: str, patterns) -> bool:
    return any(fnmatch.fnmatch(rel, pat.rstrip("/")) or ("/" not in pat and fnmatch.fnmatch(name, pat))
               for pat in patterns)


def _make_link(link: Path, target: Path, is_dir: bool) -> str:
    if os.name == "nt" and is_dir:
        try:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            return "junction"
        except (ImportError, OSError):
            pass
    try:
        os.symlink(target, link, target_is_directory=is_dir)
        return "symlink"
    except OSError:
        return ""


def cmd_copy(src: Path, dest: Path, excludes, no_git: bool, keep_heavy: bool) -> int:
    src = _real(src)
    if not src.is_dir():
        print(f"source is not a folder: {src}", file=sys.stderr)
        return 2
    if dest.exists() and any(dest.iterdir()):
        print(f"destination exists and is not empty, nothing copied: {dest}", file=sys.stderr)
        return 1
    if _inside(_real(dest), src):
        print("destination is inside the source; pick a folder outside it", file=sys.stderr)
        return 2
    dest.mkdir(parents=True, exist_ok=True)
    skip_names = set() if keep_heavy else set(HEAVY)
    if no_git:
        skip_names.add(".git")
    log = {"source": str(src), "dest": str(_real(dest)), "excludes": excludes, "files": 0, "bytes": 0,
           "skipped": [], "links_relinked": [], "links_copied": [], "biggest": []}
    later = []  # links inside the source are made after the copy, so their targets exist
    sizes = []

    def walk(cur: Path):
        for entry in sorted(os.scandir(cur), key=lambda e: e.name):
            try:
                one(entry)
            except OSError as e:  # a reserved name (nul, con), a locked file, a path too long
                log["skipped"].append(f"{Path(entry.path).relative_to(src).as_posix()} (error: {e.strerror or e})")

    def one(entry):
        p = Path(entry.path)
        rel = p.relative_to(src).as_posix()
        out = dest / rel
        if entry.name in NOISE or entry.name in skip_names or _excluded(rel, entry.name, excludes):
            log["skipped"].append(rel)
            return
        if _is_link(p):
            target = _real(p)
            if _inside(target, src):
                later.append((out, dest / target.relative_to(src), target.is_dir(), rel))
            elif target.is_dir():
                shutil.copytree(target, out, symlinks=False, ignore=shutil.ignore_patterns(*HEAVY))
                log["links_copied"].append(f"{rel} -> {target}")
            elif target.is_file():
                shutil.copy2(target, out)
                log["links_copied"].append(f"{rel} -> {target}")
            else:
                log["skipped"].append(f"{rel} (broken link)")
            return
        if entry.is_dir(follow_symlinks=False):
            out.mkdir(exist_ok=True)
            walk(p)
        elif entry.is_file(follow_symlinks=False):
            if out.exists():
                log["skipped"].append(f"{rel} (exists, not overwritten)")
                return
            shutil.copy2(p, out)
            size = entry.stat(follow_symlinks=False).st_size
            log["files"] += 1
            log["bytes"] += size
            sizes.append((size, rel))

    walk(src)
    for out, target, is_dir, rel in later:
        how = _make_link(out, target, is_dir) if target.exists() else ""
        if how:
            log["links_relinked"].append(f"{rel} -> {target} ({how})")
        elif target.is_dir():
            shutil.copytree(target, out, symlinks=False)
            log["links_copied"].append(f"{rel} -> {target} (link failed, copied)")
        elif target.is_file():
            shutil.copy2(target, out)
            log["links_copied"].append(f"{rel} -> {target} (link failed, copied)")
        else:
            log["skipped"].append(f"{rel} (link target was excluded: {target})")
    log["biggest"] = [f"{s / 1e6:.1f} MB {r}" for s, r in sorted(sizes, reverse=True)[:10]]
    (dest / LOG_DIR).mkdir(exist_ok=True)
    (dest / LOG_DIR / "copy.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"copied {log['files']} files, {log['bytes'] / 1e6:.1f} MB -> {dest}")
    print(f"skipped {len(log['skipped'])} entries; links remade {len(log['links_relinked'])}, "
          f"links copied as files {len(log['links_copied'])}")
    print(f"log: {dest / LOG_DIR / 'copy.json'}")
    return 0


# ---------- scan / fix / verify ----------

ABS_WIN = re.compile(rb"(?<![A-Za-z0-9])([A-Za-z]):((?:[\\/]{1,2}[^\s\"'`<>|*?\r\n\\/:;,)\]]+)+)")
ABS_HOME = re.compile(rb"(?<![\w.])(/(?:home|Users|mnt/[a-z])/[^\s\"'`<>|\r\n/]+(?:/[^\s\"'`<>|\r\n/]+)?)")
REL_UP = re.compile(rb"(?<![\w.])((?:\.\.[\\/]){1,8})([A-Za-z0-9_\-][^\s\"'`<>|*?\r\n\\/)]*)")


def _line(data: bytes, pos: int) -> int:
    return data.count(b"\n", 0, pos) + 1


def scan(dest: Path, source: str, maps):
    dest_r = _real(dest)
    rx, _ = pattern(source)
    map_rx = [(old, pattern(old)[0], _tail(old)) for old, _ in maps]
    src_tail = _tail(source)
    roots = [_parts(str(dest_r)), _parts(source)]  # paths under these are not "outside"
    report = {"source_hits": [], "git_remotes": [], "links_into_source": [], "map_hits": [],
              "outside_paths": {}, "climbs_out": []}
    for p, data in text_files(dest):
        rel = p.relative_to(dest).as_posix()
        low = data.lower()  # cheap substring checks first: the regexes run only where they can match
        if src_tail in low:
            for m in rx.finditer(data):
                key = "git_remotes" if rel == ".git/config" else "source_hits"
                report[key].append(f"{rel}:{_line(data, m.start())}: {m.group(0).decode(errors='replace')}")
        for old, mrx, tail in map_rx:
            if tail in low:
                for m in mrx.finditer(data):
                    report["map_hits"].append(f"{rel}:{_line(data, m.start())}: {old}")
        if rel == ".git/config":
            continue
        if b":\\" in data or b":/" in data:
            for m in ABS_WIN.finditer(data):
                drive = m.group(1).decode().upper()
                comps = [c for c in re.split(r"[\\/]+", m.group(2).decode(errors="replace")) if c]
                if any(rd and drive == rd.upper() and [c.lower() for c in comps[:len(rc)]] == [c.lower() for c in rc]
                       for rd, rc in roots):
                    continue
                depth = 3 if comps and comps[0].lower() in ("users", "home") else 2
                key = f"{drive}:\\" + "\\".join(comps[:depth])
                report["outside_paths"][key] = report["outside_paths"].get(key, 0) + 1
        if b"/home/" in data or b"/Users/" in data or b"/mnt/" in data:
            for m in ABS_HOME.finditer(data):
                key = m.group(1).decode(errors="replace")
                report["outside_paths"][key] = report["outside_paths"].get(key, 0) + 1
        if b".." not in data:
            continue
        for m in REL_UP.finditer(data):
            target = os.path.normpath(os.path.join(str(p.parent), m.group(0).decode(errors="replace")))
            if not _inside(Path(target), dest_r) and not _inside(Path(target), Path(dest)):
                report["climbs_out"].append(f"{rel}:{_line(data, m.start())}: {m.group(0).decode(errors='replace')}")
    src_r = _real(source) if Path(source).exists() else Path(source)
    for link in links(dest):
        target = _real(link)
        if _inside(target, src_r):
            report["links_into_source"].append(f"{link.relative_to(dest).as_posix()} -> {target}")
    report["outside_paths"] = dict(sorted(report["outside_paths"].items(), key=lambda kv: -kv[1]))
    return report


def cmd_scan(dest: Path, source: str, maps, as_json: bool) -> int:
    r = scan(dest, source, maps)
    if as_json:
        print(json.dumps(r, indent=2))
        return 0
    print(f"Source spellings found (fix rewrites these): {len(r['source_hits'])}")
    for h in r["source_hits"][:40]:
        print("  " + h)
    if len(r["source_hits"]) > 40:
        print(f"  ... {len(r['source_hits']) - 40} more (--json for all)")
    for key, title in [("git_remotes", "Git remotes into the source (set to the upstream URL or remove)"),
                       ("links_into_source", "Links into the source (remake inside the copy)"),
                       ("map_hits", "Hits for --map pairs (fix rewrites these)"),
                       ("climbs_out", "Relative paths that climb out of the copy (check each)")]:
        print(f"{title}: {len(r[key])}")
        for h in r[key][:20]:
            print("  " + h)
    print(f"Other absolute paths outside the copy (review; remap with --map OLD=NEW): {len(r['outside_paths'])}")
    for k, n in list(r["outside_paths"].items())[:25]:
        print(f"  {n:5d}  {k}")
    return 0


def cmd_fix(dest: Path, source: str, maps) -> int:
    pairs = [(source, str(_real(dest)))] + maps
    compiled = [(pattern(old), new, _tail(old)) for old, new in pairs]
    changed = {}
    for p, data in text_files(dest):
        rel = p.relative_to(dest).as_posix()
        if rel == ".git/config":
            continue
        new_data = data
        low = data.lower()
        for (rx, styles), new, tail in compiled:
            if tail not in low:
                continue
            def repl(m, styles=styles, new=new):
                return render(new, styles[m.group(0).decode().lower()]).encode()
            new_data, n = rx.subn(repl, new_data)
            if n:
                changed[rel] = changed.get(rel, 0) + n
        if new_data != data:
            p.write_bytes(new_data)
    (dest / LOG_DIR).mkdir(exist_ok=True)
    (dest / LOG_DIR / "paths.json").write_text(json.dumps({"pairs": pairs, "changed": changed}, indent=2), encoding="utf-8")
    print(f"rewrote {sum(changed.values())} paths in {len(changed)} files; log: {dest / LOG_DIR / 'paths.json'}")
    return 0


def cmd_verify(dest: Path, source: str) -> int:
    r = scan(dest, source, [])
    bad = r["source_hits"] + r["git_remotes"] + r["links_into_source"]
    if bad:
        print(f"NOT ISOLATED: {len(bad)} ways the copy can still reach {source}")
        for h in bad[:60]:
            print("  " + h)
        return 1
    print(f"ISOLATED: no path, link or git remote in {dest} reaches {source}")
    print(f"review: {len(r['outside_paths'])} other absolute path roots, {len(r['climbs_out'])} relative paths that leave the copy (scan lists them)")
    return 0


# ---------- stats: what the repo holds, without scaffolding ----------

SCAFFOLD = HEAVY | {".git", ".hg", ".svn", LOG_DIR, "build", "dist", "out", "tmp", "temp", ".tmp", "coverage",
                    "htmlcov", "target", "vendor", "bower_components", "site-packages", ".eggs", ".nyc_output",
                    ".svelte-kit", ".nuxt", ".angular", ".terraform", ".serverless", ".vercel", ".expo"}
LOCK_NAMES = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock",
              "pipfile.lock", "uv.lock", "cargo.lock", "composer.lock", "gemfile.lock", "go.sum", "flake.lock"}
GENERATED_ENDS = ("-lock.json", ".lock", ".min.js", ".min.css", ".map", ".bundle.js", ".chunk.js", ".pb.go",
                  "_pb2.py", "_pb2_grpc.py", ".generated.ts", ".g.dart", ".designer.cs")
GENERATED_MARKS = (b"@generated", b"do not edit", b"auto-generated", b"autogenerated", b"generated by")
C_LIKE = ("//", "/*", "*", "*/")
LANGS = {  # extension: (language, kind, comment prefixes)
    ".py": ("Python", "code", ("#",)), ".pyw": ("Python", "code", ("#",)), ".ipynb": ("Notebook", "data", ()),
    ".js": ("JavaScript", "code", C_LIKE), ".mjs": ("JavaScript", "code", C_LIKE), ".cjs": ("JavaScript", "code", C_LIKE),
    ".jsx": ("JavaScript", "code", C_LIKE), ".ts": ("TypeScript", "code", C_LIKE), ".tsx": ("TypeScript", "code", C_LIKE),
    ".mts": ("TypeScript", "code", C_LIKE), ".vue": ("Vue", "code", C_LIKE + ("<!--",)), ".svelte": ("Svelte", "code", C_LIKE + ("<!--",)),
    ".html": ("HTML", "code", ("<!--",)), ".htm": ("HTML", "code", ("<!--",)), ".css": ("CSS", "code", ("/*", "*", "*/")),
    ".scss": ("CSS", "code", C_LIKE), ".less": ("CSS", "code", C_LIKE), ".go": ("Go", "code", C_LIKE),
    ".rs": ("Rust", "code", C_LIKE), ".java": ("Java", "code", C_LIKE), ".kt": ("Kotlin", "code", C_LIKE),
    ".kts": ("Kotlin", "code", C_LIKE), ".scala": ("Scala", "code", C_LIKE), ".swift": ("Swift", "code", C_LIKE),
    ".c": ("C", "code", C_LIKE), ".h": ("C", "code", C_LIKE), ".cc": ("C++", "code", C_LIKE), ".cpp": ("C++", "code", C_LIKE),
    ".hpp": ("C++", "code", C_LIKE), ".cs": ("C#", "code", C_LIKE), ".m": ("Objective-C", "code", C_LIKE),
    ".php": ("PHP", "code", C_LIKE + ("#",)), ".rb": ("Ruby", "code", ("#",)), ".lua": ("Lua", "code", ("--",)),
    ".sql": ("SQL", "code", ("--", "/*", "*", "*/")), ".r": ("R", "code", ("#",)), ".jl": ("Julia", "code", ("#",)),
    ".dart": ("Dart", "code", C_LIKE), ".zig": ("Zig", "code", ("//",)), ".ex": ("Elixir", "code", ("#",)),
    ".exs": ("Elixir", "code", ("#",)), ".hs": ("Haskell", "code", ("--",)), ".clj": ("Clojure", "code", (";",)),
    ".sh": ("Shell", "code", ("#",)), ".bash": ("Shell", "code", ("#",)), ".zsh": ("Shell", "code", ("#",)),
    ".fish": ("Shell", "code", ("#",)), ".ps1": ("PowerShell", "code", ("#",)), ".psm1": ("PowerShell", "code", ("#",)),
    ".bat": ("Batch", "code", ("rem ", "::")), ".cmd": ("Batch", "code", ("rem ", "::")),
    ".glsl": ("GLSL", "code", C_LIKE), ".frag": ("GLSL", "code", C_LIKE), ".vert": ("GLSL", "code", C_LIKE),
    ".wgsl": ("WGSL", "code", C_LIKE), ".gd": ("GDScript", "code", ("#",)), ".tf": ("Terraform", "code", ("#", "//")),
    ".md": ("Markdown", "docs", ()), ".mdx": ("Markdown", "docs", ()), ".rst": ("reStructuredText", "docs", ()),
    ".txt": ("Text", "data", ()), ".adoc": ("AsciiDoc", "docs", ()),
    ".json": ("JSON", "data", ()), ".jsonl": ("JSON", "data", ()), ".yaml": ("YAML", "data", ()), ".yml": ("YAML", "data", ()),
    ".toml": ("TOML", "data", ()), ".ini": ("INI", "data", ()), ".cfg": ("INI", "data", ()), ".xml": ("XML", "data", ()),
    ".csv": ("CSV", "data", ()), ".tsv": ("CSV", "data", ()), ".svg": ("SVG", "data", ()),
}
NAMED = {"dockerfile": ("Dockerfile", "code", ("#",)), "makefile": ("Makefile", "code", ("#",)),
         "justfile": ("Makefile", "code", ("#",))}
TREE_DEPTH, TREE_KIDS, TREE_FILES = 4, 24, 6


def _is_scaffold_dir(path: Path, name: str, extra) -> bool:
    low = name.lower()
    return (low in SCAFFOLD or low.endswith(".egg-info") or (path / "pyvenv.cfg").is_file()
            or any(fnmatch.fnmatch(name, pat) for pat in extra))


def _lang(name: str):
    low = name.lower()
    if low in NAMED:
        return NAMED[low]
    return LANGS.get(os.path.splitext(low)[1])


def _is_generated(name: str, head: bytes) -> bool:
    low = name.lower()
    return low in LOCK_NAMES or low.endswith(GENERATED_ENDS) or any(m in head[:1024].lower() for m in GENERATED_MARKS)


def count_lines(data: bytes, prefixes) -> tuple[int, int, int]:
    """(code, comment, blank) lines. A comment line starts with one of the prefixes (after spaces);
    a /* ... */ block counts as comment lines until it closes."""
    code = comment = blank = 0
    in_block = False
    block = "/*" in prefixes
    for raw in data.decode("utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s:
            blank += 1
        elif in_block:
            comment += 1
            if "*/" in s:
                in_block = False
        elif prefixes and s.lower().startswith(prefixes):
            comment += 1
            if block and s.startswith("/*") and "*/" not in s[2:]:
                in_block = True
        else:
            code += 1
    return code, comment, blank


def _node(name: str):
    return {"n": name, "f": 0, "c": 0, "d": 0, "k": {}, "top": []}


def stats(root: Path, extra_excludes=()) -> dict:
    """Count the repo the way a reader means it: files and folders it owns, code lines without blanks and
    comment lines, doc lines; installed dependencies, build output, caches, venvs and generated files left out."""
    root = Path(root)
    out = {"name": root.name, "files": 0, "folders": 0, "code": 0, "comments": 0, "blank": 0, "docs": 0, "data": 0,
           "code_files": 0, "other_files": 0, "langs": {}, "left_out": {}, "generated": 0, "generated_lines": 0,
           "biggest": []}
    tree = _node(root.name)
    biggest = []
    left = out["left_out"]
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        rel = here.relative_to(root)
        keep = []
        for d in dirnames:
            p = here / d
            if _is_link(p):
                continue
            if _is_scaffold_dir(p, d, extra_excludes):
                n = sum(len(fs) for _, _, fs in os.walk(p))
                key = d.lower() if d.lower() in SCAFFOLD else ("venv" if (p / "pyvenv.cfg").is_file() else d)
                left[key] = left.get(key, 0) + n
                continue
            keep.append(d)
        dirnames[:] = sorted(keep)
        out["folders"] += len(keep)
        chain = [tree]
        for part in rel.parts:
            chain.append(chain[-1]["k"].setdefault(part, _node(part)))
        for name in filenames:
            p = here / name
            if name in NOISE or _is_link(p):
                continue
            if rel == Path(".") and name == "ONBOARDING.html":
                continue  # the course does not count itself
            out["files"] += 1
            for n in chain:
                n["f"] += 1
            lang = _lang(name)
            if not lang:
                out["other_files"] += 1
                continue
            try:
                size = p.stat().st_size
                if size > MAX_SCAN_BYTES:
                    out["other_files"] += 1
                    continue
                data = p.read_bytes()
            except OSError:
                continue
            if b"\0" in data[:8192]:
                out["other_files"] += 1
                continue
            language, kind, prefixes = lang
            code, comment, blank = count_lines(data, prefixes)
            lines = code + comment + blank
            if _is_generated(name, data) or (kind == "code" and lines and len(data) / lines > 300):
                out["generated"] += 1
                out["generated_lines"] += lines
                continue
            if kind == "code":
                out["code"] += code
                out["comments"] += comment
                out["blank"] += blank
                out["code_files"] += 1
                lg = out["langs"].setdefault(language, {"files": 0, "code": 0})
                lg["files"] += 1
                lg["code"] += code
                relp = (rel / name).as_posix()
                biggest.append((code, relp, language))
                for n in chain:
                    n["c"] += code
                leaf = chain[-1]
                leaf["top"].append((code, name, language))
            elif kind == "docs":
                out["docs"] += code + comment
                for n in chain:
                    n["d"] += code + comment
            else:
                out["data"] += code + comment
    out["langs"] = [{"name": k, **v} for k, v in sorted(out["langs"].items(), key=lambda kv: -kv[1]["code"])]
    out["biggest"] = [{"path": r, "code": c, "lang": lg} for c, r, lg in sorted(biggest, reverse=True)[:12]]
    out["left_out"] = dict(sorted(left.items(), key=lambda kv: -kv[1]))
    out["tree"] = _prune(tree, 0)
    return out


def _prune(node, depth):
    """The tree for the page: folders by code lines (then files), the biggest code files of each folder,
    the rest folded into one 'more' row so the page stays small."""
    kids = sorted(node["k"].values(), key=lambda k: (-k["c"], -k["d"], -k["f"], k["n"]))
    shown = kids[:TREE_KIDS] if depth < TREE_DEPTH else []
    rest = kids[len(shown):]
    out = {"n": node["n"], "f": node["f"], "c": node["c"], "d": node["d"]}
    k = [_prune(x, depth + 1) for x in shown]
    if rest:
        k.append({"n": f"{len(rest)} more folders", "f": sum(x["f"] for x in rest), "c": sum(x["c"] for x in rest),
                  "d": sum(x["d"] for x in rest), "more": 1})
    if k:
        out["k"] = k
    tops = sorted(node["top"], reverse=True)[:TREE_FILES]
    if tops and depth <= TREE_DEPTH:
        out["t"] = [[n, c, lg] for c, n, lg in tops if c]
    return out


def cmd_stats(dest: Path, as_json: bool, excludes) -> int:
    s = stats(dest, excludes)
    if as_json:
        print(json.dumps(s, indent=1))
        return 0
    print(f"{s['name']}: {s['files']:,} files in {s['folders']:,} folders")
    print(f"code: {s['code']:,} lines in {s['code_files']:,} files (no blank lines, no comment lines); "
          f"comments {s['comments']:,}; docs {s['docs']:,} lines; data and config {s['data']:,} lines")
    print("languages: " + ", ".join(f"{l['name']} {l['code']:,}" for l in s["langs"][:8]))
    print(f"left out: {s['generated']:,} generated files ({s['generated_lines']:,} lines); scaffolding folders: "
          + (", ".join(f"{k} {v:,} files" for k, v in list(s["left_out"].items())[:8]) or "none"))
    return 0


# ---------- guide: the course page ----------

DATA_RX = re.compile(r'(<script type="application/json" id="sigmafork-data">)(.*?)(</script>)', re.S)
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "guide-template.html"


def _fork_facts(dest: Path, source: str | None) -> dict:
    facts = {}
    log = dest / LOG_DIR
    try:
        c = json.loads((log / "copy.json").read_text(encoding="utf-8"))
        facts.update(copied_files=c.get("files", 0), copied_mb=round(c.get("bytes", 0) / 1e6, 1),
                     links_remade=len(c.get("links_relinked", [])), links_copied=len(c.get("links_copied", [])),
                     skipped=len(c.get("skipped", [])), source_name=Path(c.get("source", "")).name)
    except (OSError, ValueError):
        pass
    try:
        p = json.loads((log / "paths.json").read_text(encoding="utf-8"))
        ch = p.get("changed", {})
        facts.update(paths_rewritten=sum(ch.values()), files_rewritten=len(ch),
                     remapped=max(len(p.get("pairs", [])) - 1, 0))
    except (OSError, ValueError):
        pass
    if source:
        r = scan(dest, source, [])
        facts["isolated"] = not (r["source_hits"] or r["git_remotes"] or r["links_into_source"])
        if not facts.get("source_name"):
            comps = _parts(source)[1]
            facts["source_name"] = comps[-1] if comps else ""
    return facts


def guide_check(html: str) -> tuple[list, list]:
    """(blocking, fixes). Blocking: FILL left, no data. Fixes: long paragraphs, chip-heavy text, undefined terms,
    too few figures. A check is a fix list, not a taste judge."""
    blocking, fixes = [], []
    for m in re.finditer(r"\bFILL\b", html):
        blocking.append(f"line {html.count(chr(10), 0, m.start()) + 1}: FILL left")
    m = DATA_RX.search(html)
    if not m or not m.group(2).strip().startswith("{"):
        blocking.append("no repo data: run `sigmafork.py guide <copy>`")
    figures = len(re.findall(r"<figure\b", html))
    if figures < 6:
        fixes.append(f"{figures} figures; the course wants 6 or more (map, numbers, explorer, story, flow, isolation)")
    body = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", html, flags=re.S)
    for pm in re.finditer(r"<p\b[^>]*>(.*?)</p>", body, re.S):
        inner = pm.group(1)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
        words = len(text.split())
        sentences = len(re.findall(r"[.!?](?:\s|$)", text))
        chips = len(re.findall(r"<code\b", inner))
        line = body.count("\n", 0, pm.start()) + 1
        if words > 70 or sentences > 3:
            fixes.append(f"line ~{line}: {words} words, {sentences} sentences; split it (3 sentences, 70 words at most)")
        if chips > 3:
            fixes.append(f"line ~{line}: {chips} inline code chips; move commands into a code block, write names plainly")
    for tm in re.finditer(r'<(?:span|abbr|dfn)[^>]*class="term"[^>]*>', body):
        if "data-def=" not in tm.group(0):
            fixes.append(f"term without data-def: {tm.group(0)[:60]}")
    return blocking, fixes


def cmd_guide(dest: Path, out: Path | None, source: str | None, check: bool, excludes) -> int:
    out = out or dest / "ONBOARDING.html"
    if check:
        if not out.is_file():
            print(f"no guide at {out}", file=sys.stderr)
            return 1
        blocking, fixes = guide_check(out.read_text(encoding="utf-8", errors="replace"))
        for b in blocking:
            print("BLOCK " + b)
        for f in fixes:
            print("FIX   " + f)
        print(f"guide check: {len(blocking)} blocking, {len(fixes)} fixes")
        return 1 if blocking else 0
    if not out.exists():
        shutil.copyfile(TEMPLATE, out)
        print(f"new guide from the template: {out}")
    with open(out, encoding="utf-8", newline="") as fh:  # keep the file's line endings
        html = fh.read()
    if not DATA_RX.search(html):
        print("the guide has no sigmafork-data block; start again from assets/guide-template.html", file=sys.stderr)
        return 1
    data = {"stats": stats(dest, excludes), "fork": _fork_facts(dest, source)}
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(DATA_RX.sub(lambda m: m.group(1) + blob + m.group(3), html, count=1))
    s = data["stats"]
    print(f"wrote repo data into {out}: {s['files']:,} files, {s['folders']:,} folders, {s['code']:,} code lines")
    return 0


# ---------- selftest ----------

def cmd_selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sigmafork-"))
    try:
        src, dest = tmp / "Orig_Repo", tmp / "out" / "Copy"
        (src / "docs").mkdir(parents=True)
        (src / "node_modules" / "x").mkdir(parents=True)
        (src / "animations" / "2026-01-01-film").mkdir(parents=True)
        (src / "animations" / "_template").mkdir(parents=True)
        (src / "skills" / "real").mkdir(parents=True)
        (src / "skills" / "real" / "SKILL.md").write_text("x", encoding="utf-8")
        s = str(src)
        d, comps = _parts(s)
        fwd = (d + ":/" if d else "/") + "/".join(comps)
        body = f"a = r'{s}\\docs'\r\nb = \"{fwd}/x\"\r\nc = '{s}_other'\r\n"
        if d:
            body += f"d = \"{d}:\\\\" + "\\\\".join(comps) + "\\\\y\"\r\ne = /" + d.lower() + "/" + "/".join(comps) + "/z\r\n"
        (src / "docs" / "conf.py").write_bytes(body.encode())
        (src / "animations" / "_template" / "t.txt").write_text("t", encoding="utf-8")
        (src / "animations" / "2026-01-01-film" / "big.txt").write_text("f", encoding="utf-8")
        linked = _make_link(src / "skills" / "alias", src / "skills" / "real", True)
        assert cmd_copy(src, dest, ["animations/2*"], False, False) == 0
        assert not (dest / "node_modules").exists() and not (dest / "animations" / "2026-01-01-film").exists()
        assert (dest / "animations" / "_template" / "t.txt").exists()
        assert cmd_copy(src, dest, [], False, False) == 1, "copy must refuse a non-empty destination"
        if linked:
            assert _inside(_real(dest / "skills" / "alias"), _real(dest)), "link must point into the copy"
        assert cmd_verify(dest, s) == 1
        assert cmd_fix(dest, s, []) == 0
        assert cmd_verify(dest, s) == 0
        out = (dest / "docs" / "conf.py").read_bytes()
        assert b"\r\n" in out and f"{s}_other".encode() in out, "line endings and look-alike names stay"
        assert (src / "docs" / "conf.py").read_bytes() == body.encode(), "the source is never changed"
        print("selftest ok" + ("" if linked else " (links not testable here)"))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("copy")
    c.add_argument("src")
    c.add_argument("dest")
    c.add_argument("--exclude", action="append", default=[], help="glob on the relative path or a name, e.g. animations/2*")
    c.add_argument("--no-git", action="store_true", help="leave out .git (a fresh history)")
    c.add_argument("--keep-heavy", action="store_true", help="also copy node_modules, venvs and caches")
    for name in ("scan", "fix", "verify"):
        p = sub.add_parser(name)
        p.add_argument("dest")
        p.add_argument("--source", required=True, help="the original repo's absolute path")
        if name != "verify":
            p.add_argument("--map", action="append", default=[], help="OLD=NEW, another absolute root to rewrite")
        if name == "scan":
            p.add_argument("--json", action="store_true")
    st = sub.add_parser("stats")
    st.add_argument("dest")
    st.add_argument("--json", action="store_true")
    st.add_argument("--exclude", action="append", default=[], help="another folder name or glob to leave out")
    g = sub.add_parser("guide")
    g.add_argument("dest")
    g.add_argument("--source", help="the original's absolute path: adds the verify result (never written in the page)")
    g.add_argument("--out", help="the guide file (default DEST/ONBOARDING.html)")
    g.add_argument("--check", action="store_true", help="list what is still wrong in the guide")
    g.add_argument("--exclude", action="append", default=[], help="another folder name or glob to leave out")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return cmd_selftest()
    if a.cmd == "copy":
        return cmd_copy(Path(a.src), Path(a.dest), a.exclude, a.no_git, a.keep_heavy)
    dest = Path(a.dest)
    if a.cmd in ("stats", "guide") and not dest.is_dir():
        print(f"not a folder: {dest}", file=sys.stderr)
        return 2
    if a.cmd == "stats":
        return cmd_stats(dest, a.json, a.exclude)
    if a.cmd == "guide":
        return cmd_guide(dest, Path(a.out) if a.out else None, a.source, a.check, a.exclude)
    if not dest.is_dir():
        print(f"not a folder: {dest}", file=sys.stderr)
        return 2
    maps = []
    for pair in getattr(a, "map", []):
        if "=" not in pair:
            print(f"--map needs OLD=NEW: {pair}", file=sys.stderr)
            return 2
        maps.append(tuple(pair.split("=", 1)))
    if a.cmd == "scan":
        return cmd_scan(dest, a.source, maps, a.json)
    if a.cmd == "fix":
        return cmd_fix(dest, a.source, maps)
    return cmd_verify(dest, a.source)


if __name__ == "__main__":
    sys.exit(main())
