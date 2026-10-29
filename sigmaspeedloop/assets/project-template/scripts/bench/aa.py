"""aa.py - turn the BASELINE + A/A runs into noise bands and write evaluator.lock (SETUP only).

  python scripts/bench/aa.py runs/0001 runs/0002 runs/0003

Spread of a component = largest |run / median - 1| over the runs. The gate band = the worst value any
baseline run showed against the references. Every file in scripts/bench/ is hashed into the lock.
"""
import hashlib, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verdict import ROOT, extract, ratios, score  # noqa: E402

COMPONENT_KEYS = ("replay_wall_s", "decode_greedy", "decode_sampled", "prefill_geo", "c3_tps",
                  "c2_tps", "warm_ttft_sum", "warm_miss")  # the keys ratios() reads from the champion


def main(runs, tool_runs=None):
    rows = [extract(r) for r in runs]
    med = {}
    for k in COMPONENT_KEYS:  # a key that no run has stays None, and ratios() skips that component
        vals = [x[k] for x in rows if x.get(k) is not None]
        med[k] = statistics.median(vals) if vals else None
    med["replay_version"] = max((x.get("replay_version") or 0) for x in rows)
    rows = [dict(x, replay_version=x.get("replay_version") or 0) for x in rows]
    rats = [ratios(x, med) for x in rows]
    spread = {k: max(abs(r[k] - 1) for r in rats) for k in rats[0]}
    score_spread = max(abs(score(r) - 1) for r in rats)
    gates = [x["gate"] for x in rows]
    # v4 runs (full 74-scenario ToolEvalBench, 4 needles) set the reliability/tool bands; all runs share the
    # fidelity and speed code, so those bands use every run
    v4 = [g for r, g in zip(runs, gates) if r in (tool_runs or [])] or [g for g in gates if g.get("tooleval_max", 0) > 50] or gates
    thresholds = {
        "spread": spread, "score_spread": score_spread,
        "tf_top1_min": min(g["tf_top1"] for g in gates), "tf_dlp_max": max(g["tf_dlp"] for g in gates),
        "dec_dlp_max": max(g["dec_dlp"] for g in gates), "dec_prefix_min": min(g["dec_prefix"] for g in gates),
        "reliability_min": min(g["reliability_ok"] for g in v4), "looping_max": max(g["looping_outputs"] for g in gates),
        "bw_median": statistics.median(b for x in rows for b in x["bw"]),
        "tooleval_min": min(g.get("tooleval_points", 0) for g in v4),
        "tooleval_range": max(g.get("tooleval_points", 0) for g in v4) - min(g.get("tooleval_points", 0) for g in v4),
        "baseline_runs": runs, "baseline_median": med,
    }
    bench = os.path.join(ROOT, "scripts", "bench")
    files = {}
    for dirpath, _, names in os.walk(bench):
        for n in sorted(names):
            if n.endswith(".pyc"):
                continue
            p = os.path.join(dirpath, n)
            files[os.path.relpath(p, bench).replace("\\", "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    lock = {"created_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
            "thresholds": thresholds, "files": files}
    json.dump(lock, open(os.path.join(ROOT, "evaluator.lock"), "w", encoding="utf-8"), indent=1)
    print(json.dumps({"spread": spread, "score_spread": score_spread, "keep_floor": max(0.02, 2 * score_spread),
                      "gate": {k: v for k, v in thresholds.items() if k.startswith(("tf_", "dec_", "rel", "loop"))},
                      "bw_median": thresholds["bw_median"]}, indent=1))


if __name__ == "__main__":
    args = [r.rstrip("/\\") for r in sys.argv[1:]]
    tool = [r for r in args if r.startswith("tool=")]
    main([r for r in args if not r.startswith("tool=")], [t[5:] for t in tool])
