#!/usr/bin/env python3
"""SigmaFork helper: copy a repo so the copy never writes into the original.

  python sigmafork.py copy   SRC DEST [--exclude PATTERN ...] [--no-git] [--keep-heavy]
  python sigmafork.py scan   DEST --source SRC [--map OLD=NEW ...] [--json]
  python sigmafork.py fix    DEST --source SRC [--map OLD=NEW ...]
  python sigmafork.py verify DEST --source SRC
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
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return cmd_selftest()
    if a.cmd == "copy":
        return cmd_copy(Path(a.src), Path(a.dest), a.exclude, a.no_git, a.keep_heavy)
    dest = Path(a.dest)
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
