#!/usr/bin/env python3
"""Keep SigmaHuman on blader/humanizer: a vendored upstream copy plus our patch layer, one update command.

The upstream copy is upstream/humanizer-SKILL.md at the commit in upstream/UPSTREAM.json. Sections A to F of
references/patterns.md (the 26 numbered patterns) are that file's "## A." block, byte for byte. Everything else is
the patch layer and stays ours: SKILL.md, references/lanes.md, section G of patterns.md, scripts/factcheck.py.

    python3 scripts/upstream.py check            offline: patterns.md A-F equals the vendored copy (exit 1 when not)
    python3 scripts/upstream.py status           online: is a newer upstream commit or release out? (exit 1 when behind)
    python3 scripts/upstream.py sync [--ref R]   online: vendor R (default: the newest commit on main), rewrite A-F,
                                                 the licence and the version lines; prints what changed upstream outside
                                                 A-F, so the patch layer can take it by hand

Standard library only. GitHub's API allows 60 calls an hour without a token; set GITHUB_TOKEN (or GH_TOKEN) for more. sync uses up to 6.
"""
from __future__ import annotations

import argparse
import base64
import difflib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
UP_DIR = SKILL / "upstream"
UP_SKILL = UP_DIR / "humanizer-SKILL.md"
UP_META = UP_DIR / "UPSTREAM.json"
PATTERNS = SKILL / "references" / "patterns.md"
LICENSE = SKILL / "references" / "LICENSE-humanizer.txt"
VERSIONED = [SKILL / "SKILL.md", PATTERNS, SKILL / "references" / "sources.md"]
API = "https://api.github.com/repos/blader/humanizer"
BLOCK_START = re.compile(r"^## A\. ", re.M)


def upstream_block(text: str) -> str:
    """Sections A to F of upstream SKILL.md: from '## A.' up to '## When not to act'."""
    start = BLOCK_START.search(text)
    end = text.find("\n## When not to act")
    if not start or end < 0:
        raise SystemExit("upstream SKILL.md no longer has '## A.' ... '## When not to act': update upstream.py by hand")
    return text[start.start():end + 1]


def patterns_block(text: str) -> tuple[int, int]:
    """Span of sections A to F in our patterns.md: from '## A.' up to '## G.'."""
    start = BLOCK_START.search(text)
    end = text.find("\n## G. ")
    if not start or end < 0:
        raise SystemExit("patterns.md lacks '## A.' or '## G.'")
    return start.start(), end + 1


def get(path: str) -> dict | list:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "sigmahuman"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(name: str, ref: str) -> str:
    data = get(f"/contents/{name}?ref={ref}")
    return base64.b64decode(data["content"]).decode("utf-8")


def cmd_check() -> int:
    ours = PATTERNS.read_text(encoding="utf-8")
    a, b = patterns_block(ours)
    if ours[a:b] != upstream_block(UP_SKILL.read_text(encoding="utf-8")):
        print("patterns.md sections A-F differ from upstream/humanizer-SKILL.md: run `upstream.py sync --ref <commit>`")
        return 1
    meta = json.loads(UP_META.read_text(encoding="utf-8"))
    print(f"ok: patterns A-F = blader/humanizer {meta['version']} ({meta['commit'][:7]})")
    return 0


def latest() -> tuple[str, str, str]:
    commit = get("/commits?per_page=1")[0]
    releases = get("/releases?per_page=1")
    return commit["sha"], commit["commit"]["committer"]["date"][:10], (releases[0]["tag_name"] if releases else "")


def cmd_status() -> int:
    meta = json.loads(UP_META.read_text(encoding="utf-8"))
    sha, date, tag = latest()
    behind = sha != meta["commit"]
    print(f"vendored {meta['version']} {meta['commit'][:7]} ({meta['date']}); upstream main {sha[:7]} ({date}), release {tag}")
    if behind:
        print("behind: run `python3 scripts/upstream.py sync`, then read its notes for the patch layer")
    return 1 if behind else 0


def bump_versions(text: str, old: tuple[str, str], new: tuple[str, str]) -> str:
    """Swap the vendored version and short commit for the new ones; other versions (the v2.5.1 merge note) stay."""
    text = re.sub(r"(blader/humanizer(?:\]\([^)]*\))?\s*)" + re.escape(old[0]) + r"(?![\w.])", rf"\g<1>{new[0]}", text)
    return text.replace(f"commit {old[1]}", f"commit {new[1]}")


def cmd_sync(ref: str | None) -> int:
    meta = json.loads(UP_META.read_text(encoding="utf-8"))
    sha, date, tag = latest()
    if ref:
        info = get(f"/commits/{ref}")
        sha, date = info["sha"], info["commit"]["committer"]["date"][:10]
    new_skill = fetch("SKILL.md", sha)
    old_skill = UP_SKILL.read_text(encoding="utf-8")
    m = re.search(r"^\s*version:\s*['\"]?([\d.]+)", new_skill, re.M)
    version = "v" + m.group(1) if m else (tag or meta["version"])
    ours = PATTERNS.read_text(encoding="utf-8")
    a, b = patterns_block(ours)
    PATTERNS.write_text(ours[:a] + upstream_block(new_skill) + ours[b:], encoding="utf-8", newline="\n")
    LICENSE.write_text(fetch("LICENSE", sha), encoding="utf-8", newline="\n")
    UP_SKILL.write_text(new_skill, encoding="utf-8", newline="\n")
    for f in VERSIONED:
        f.write_text(bump_versions(f.read_text(encoding="utf-8"), (meta["version"], meta["commit"][:7]), (version, sha[:7])),
                     encoding="utf-8", newline="\n")
    UP_META.write_text(json.dumps({"repo": "blader/humanizer", "version": version, "commit": sha, "date": date,
                                   "synced": time.strftime("%Y-%m-%d")}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"synced blader/humanizer {meta['commit'][:7]} -> {sha[:7]} ({version}); patterns A-F, licence, version lines")
    outside = [l for l in difflib.unified_diff(
        (old_skill[:old_skill.find("## A. ")] + old_skill[old_skill.find("\n## When not to act"):]).splitlines(),
        (new_skill[:new_skill.find("## A. ")] + new_skill[new_skill.find("\n## When not to act"):]).splitlines(),
        lineterm="", n=0) if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    if outside:
        print(f"{len(outside)} changed lines upstream outside A-F (method, voice, when not to act): fold them into SKILL.md by hand:")
        print("\n".join(outside[:80]))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("status")
    s = sub.add_parser("sync")
    s.add_argument("--ref", help="commit or tag (default: the newest commit on main)")
    args = p.parse_args(argv)
    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "status":
        return cmd_status()
    return cmd_sync(args.ref)


if __name__ == "__main__":
    sys.exit(main())
