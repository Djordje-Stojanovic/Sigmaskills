"""aa.py - turn the runs of the unchanged target (A/A runs) into noise bands and write evaluator.lock.

  python scripts/bench/aa.py runs/0001 runs/0002 runs/0003

Spread of a probe = the largest |run / median - 1| over the runs; the score spread is the same for the weighted
score. With a pairs measurer each A/A run judges the unchanged target against itself, and the spread is the largest
|share won - 0.5|. Every file in scripts/bench/ is hashed into the lock. After the lock, an edit is a migration.
"""
import json, os, statistics, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verdict import ROOT, project, ratios, raw, sha, share, weighted  # noqa: E402


def bands(runs, p):
    if p.get("measurer") == "pairs":
        s = max(abs(share(raw(r, "score.json")["pairs"]["champion"]) - 0.5) for r in runs)
        return {}, {}, s
    rows = [raw(r, "score.json")["probes"] for r in runs]
    med = {k: statistics.median(x[k] for x in rows if x.get(k) is not None)
           for k in {k for x in rows for k in x} if any(x.get(k) is not None for x in rows)}
    rats = [ratios(x, med, set(p.get("lower_is_better", []))) for x in rows]
    spread = {k: max((abs(r[k] - 1) for r in rats if k in r), default=0) for k in med}
    return med, spread, max(abs((weighted(r, p.get("weights", {})) or 1) - 1) for r in rats)


def main(runs):
    p = project()
    med, spread, score_spread = bands(runs, p)
    bench = os.path.join(ROOT, "scripts", "bench")
    files = {}
    for dirpath, _, names in os.walk(bench):
        for n in sorted(names):
            if not n.endswith(".pyc"):
                path = os.path.join(dirpath, n)
                files[os.path.relpath(path, bench).replace("\\", "/")] = sha(path)
    lock = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files,
            "thresholds": {"spread": spread, "score_spread": score_spread, "baseline_runs": runs, "baseline_probes": med}}
    json.dump(lock, open(os.path.join(ROOT, "evaluator.lock"), "w", encoding="utf-8"), indent=1)
    floor = p["min_gain"] if p.get("min_gain") is not None else 2 * score_spread
    print(json.dumps({"spread": spread, "score_spread": score_spread, "min_gain": floor}, indent=1))
    if len(runs) < p.get("repeats", 3):
        print(f"WARNING: {len(runs)} runs; project.json asks for {p.get('repeats', 3)} to see the noise")


if __name__ == "__main__":
    main([r.rstrip("/\\") for r in sys.argv[1:]])
