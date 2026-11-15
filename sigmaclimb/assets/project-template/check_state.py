"""check_state.py - validates state-file structure. Exit 0 = clean. Run after every append."""
import csv, glob, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from status import loop_speed  # noqa: E402
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

# the loop's own rules, every number from project.json
proj = json.load(open(os.path.join(ROOT, "project.json"), encoding="utf-8"))
share, floor = loop_speed(ROOT)[2], proj.get("score_share_min", 0.5)
if share is not None and share < floor:
    problems.append(f"the last passes spent {share:.0%} of their time measuring the score (score_share_min {floor:.0%}) - fix the loop first")
metas = [json.load(open(m, encoding="utf-8")) for m in sorted(glob.glob(os.path.join(ROOT, "runs", "*", "raw", "meta.json")))[-5:]]
q = [m["stage_s"]["quality"] / sum(m["stage_s"].values()) for m in metas if (m.get("stage_s") or {}).get("quality")]
if q and max(q) > proj.get("quality_share_max", 0.25):
    problems.append(f"the quality check took {max(q):.0%} of a pass (quality_share_max {proj.get('quality_share_max', 0.25):.0%}) - make it cheaper or ask the owner")
rows = []
if os.path.exists(os.path.join(ROOT, "results.tsv")):
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "results.tsv"), encoding="utf-8"), delimiter="\t")
            if r["verdict"] not in ("BASELINE", "AA", "RECON")]
n = proj.get("category_switch_after", 3)
tail = rows[-n:]
if len(tail) == n and len({r["category"] for r in tail}) == 1 and not any(r["verdict"] == "KEEP" for r in tail):
    problems.append(f"{n} passes in category {tail[0]['category']!r} without a KEEP - change category and profile again")
b = proj.get("bold_every", 3)
if len(rows) >= b and not any(r["work_type"].upper() in ("CODE", "DESIGN") for r in rows[-b:]):
    problems.append(f"no code or design change in the last {b} passes - the next pass is one")

print("STATE: CLEAN" if not problems else "STATE: " + str(len(problems)) + " problem(s)\n  " + "\n  ".join(problems))
sys.exit(0 if not problems else 1)
