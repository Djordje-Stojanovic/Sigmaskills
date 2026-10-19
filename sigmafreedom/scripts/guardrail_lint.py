"""Guardrail lint: no new model-authored prohibition may land in an agent-facing doc (plan 2026-10-17, D8, owner 2026-10-17).

Why: models add "never / not allowed / do not use" lines unprompted, and a later agent reads them as law. The freedom sweep removed
the old ones; this lint keeps them out. It flags only freedom-limiting language (a ban on what the owner may use, run, install or
share); craft guidance and mechanical guards ("never post twice") are outside its patterns.

  python tools/guardrail_lint.py                 lint this repo's agent-facing docs (exit 1 on a new prohibition)
  python tools/guardrail_lint.py --list          print every hit, allowed ones marked
  python tools/guardrail_lint.py --selftest      prove the lint fails on a ban and passes on a keep (the negative test)
  python tools/guardrail_lint.py PATH...         lint specific files or folders

Allowlist: guardrail_allowlist.txt next to this script, one substring per line (# comments). A flagged line that contains an
allowlisted substring is a keep the owner can veto: delete the line and the lint flags it again.

Use it
  When to use  Before a commit, and after any doc that steers an agent changes.
  You see      "no new prohibition" with a file count, or the offending file:line lines.
  If not       Delete the line, or add its substring to guardrail_allowlist.txt (a keep the owner can veto).
  Level        easy, under a second
"""
import re
import sys
import tempfile
from pathlib import Path

BAD = re.compile(
    r"must not (use|run|install|deploy|share|help|assist|be used)"
    r"|not allowed|forbidden|we will not"
    r"|(never|do not) (use|run|install|deploy|share)\b"
    r"|(is|are|remains) banned|banned until"
    r"|against the (terms|rules|law)"
    r"|risk of (ban|suspension)"
    r"|evasion|evade (detection|platform)"
    r"|refuse to (help|do|run|install|assist)|decline to",
    re.I,
)
COMMENT = re.compile(r"^\s*# ")
OWNER = re.compile(r"\(owner\b|\bowner[: ]|\bowner (word|rule|decision|call)\b", re.I)   # the owner wrote it: never a finding          # a comment is '# ' at the line start; a kept fragment may begin with '##' or '###'


SKIP = {"node_modules", ".venv", "venv", "__pycache__", "vendor", ".git", "dist", "build", "out",
        "site-packages", ".next", "coverage", ".scratch", ".pi", ".history", "changelog", "archive",
        "archives", "animations", "library", "thumbs", "fixtures", "evidence", "tests", "test"}
EXTRA = ("lazy_toolkits/lahelp.txt",)          # instruction files outside docs/ go here


def targets(root, given):
    """The agent-facing docs of any repo, or the paths the caller named. Discovery, not a lab's layout: the root
    steering docs (CLAUDE/AGENTS/README/CONTRIBUTING and friends), everything under docs/ and .github/, every skill
    card (SKILL.md) with its references, plus EXTRA. Scratch notes, plans, changelogs, archives and test fixtures are
    not instructions and stay out. A photo website, a local LLM config, a hacking toolkit, a game and a book all count."""
    if given:
        out = []
        for g in given:
            p = Path(g)
            out += [q for q in (p.rglob("*") if p.is_dir() else [p]) if q.is_file() and q.suffix in (".md", ".txt")]
        return sorted(set(out))
    skill_dirs = {p.parent for p in root.rglob("SKILL.md") if p.is_file()}
    out = set()
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in (".md", ".txt", ".rst"):
            continue
        if p.name.lower() in ("guardrail_allowlist.txt", "secret-allow", ".secret-allow"):
            continue   # the keep-list quotes flagged lines; scanning it can never converge
        rel = p.relative_to(root)
        if any(part in SKIP for part in rel.parts[:-1]):
            continue
        top = rel.parts[0].lower()
        if (len(rel.parts) == 1 or top in ("docs", "doc", "documentation", ".github")
                or p.name.lower() == "skill.md" or any(d in p.parents for d in skill_dirs)):
            out.add(p)
    out |= {root / e for e in EXTRA if (root / e).is_file()}
    return sorted(out)


def allows(path):
    f = Path(path).parent / "guardrail_allowlist.txt"
    if not f.exists():
        f = Path(__file__).resolve().parent / "guardrail_allowlist.txt"
    if not f.exists():
        return []
    return [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not COMMENT.match(ln)]


def lint(files, allow):
    """-> [(file, line number, text)] for every hit that no allowlist substring covers."""
    bad = []
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(lines, 1):
            if not BAD.search(line):
                continue
            if any(a in line for a in allow) or OWNER.search(line):
                continue
            bad.append((f, n, line.strip()[:160]))
    return bad


def selftest():
    """The negative test: a ban fails, an allowlisted keep and plain craft pass."""
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        ban = t / "ban.md"
        ban.write_text("Never install that tool on this machine.\n", encoding="utf-8")
        keep = t / "keep.md"
        keep.write_text("A video never posts twice; one post per run.\n", encoding="utf-8")
        ok = t / "ok.md"
        ok.write_text("Never install the plugin twice; the pin is in traefik.yml.\n", encoding="utf-8")
        if not lint([ban], []):
            print("selftest FAILED: a ban passed the lint")
            return 1
        if lint([keep], []):
            print("selftest FAILED: mechanical guard flagged")
            return 1
        if lint([ok], ["Never install the plugin twice"]):
            print("selftest FAILED: allowlisted keep flagged")
            return 1
        print("selftest PASS: ban fails, mechanical guard passes, allowlisted keep passes")
        return 0


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles print the docs' arrows and dashes
    except Exception:
        pass
    if "--keep" in argv:                  # an explicit keep, at the owner's word: append the line and a dated reason
        text = argv[argv.index("--keep") + 1]
        why = argv[argv.index("--why") + 1] if "--why" in argv else "owner said so"
        f = Path(__file__).resolve().parent / "guardrail_allowlist.txt"
        with f.open("a", encoding="utf-8") as h:
            h.write(f"# keep (owner {__import__('datetime').date.today().isoformat()}): {why}\n{text}\n")
        print(f"kept: {text[:70]}")
        return 0
    if {"-h", "--help"} & set(argv):      # the website's docs test runs every lab script with --help: answer before any scan
        print(__doc__)
        return 0
    if "--selftest" in argv:
        return selftest()
    root = Path(__file__).resolve().parents[1]
    given = [a for a in argv if not a.startswith("--")]
    files = targets(root, given)
    allow = allows(Path(__file__).resolve().parent / "guardrail_allowlist.txt")
    hits = lint(files, allow)
    if "--list" in argv:
        for f, n, line in hits:
            print(f"{f}:{n}: {line}")
        print(f"{len(hits)} hit(s) outside the allowlist, {len(files)} file(s) scanned")
        return 0 if not hits else 1
    for f, n, line in hits:
        print(f"{f}:{n}: {line}")
    if hits:
        print(f"guardrail lint: {len(hits)} new prohibition line(s) in agent-facing docs. Delete them, or add the line's "
              f"substring to guardrail_allowlist.txt (a keep the owner can veto).")
        return 1
    print(f"guardrail lint: {len(files)} agent-facing file(s), no new prohibition")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
