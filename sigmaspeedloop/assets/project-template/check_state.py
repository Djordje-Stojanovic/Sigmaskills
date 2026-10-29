"""check_state.py - validates state-file structure. Exit 0 = clean. Run after every append."""
import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FILES = ["ideas.tsv", "ruled_out.tsv", "results.tsv"]
VERDICTS = {"BASELINE", "AA", "KEEP", "ARCHIVE", "REJECT", "VOID", "CRASH", "RECON"}

problems = []
for name in FILES:
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        problems.append(f"{name}: missing")
        continue
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    if not lines:
        problems.append(f"{name}: empty (header missing)")
        continue
    cols = lines[0].split("\t")
    n = len(cols)
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != n:
            problems.append(f"{name}:{i}: {len(parts)} cols, expected {n}")
            continue
        if name == "results.tsv" and parts[cols.index("verdict")] not in VERDICTS:
            problems.append(f"{name}:{i}: unknown verdict {parts[cols.index('verdict')]!r}")
        if name == "ideas.tsv" and parts[1] not in {"pending", "trying"}:
            problems.append(f"{name}:{i}: status must be pending|trying (done rows move to results.tsv)")

if os.path.exists(os.path.join(ROOT, "ideas.tsv")):
    pending = sum(1 for l in open(os.path.join(ROOT, "ideas.tsv"), encoding="utf-8").read().splitlines()[1:]
                  if l.split("\t")[1:2] == ["pending"])
    if pending < 3:
        problems.append(f"ideas.tsv: only {pending} pending ideas (rule: >= 3) - refill now")

print("STATE: CLEAN" if not problems else "STATE: " + str(len(problems)) + " problem(s)\n  " + "\n  ".join(problems))
sys.exit(0 if not problems else 1)
