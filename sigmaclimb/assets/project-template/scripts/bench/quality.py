"""quality.py - the serving example's quality judge (stage 2). Another target writes quality.json its own way.

  python quality.py bands runs/0001 runs/0002 runs/0003   SETUP, before aa.py: bands from the A/A runs -> quality_bands.json
  python quality.py OUT                                    after gate.py and ToolEvalBench: OUT/gate.json -> OUT/quality.json

quality.json = {"ok": bool, "fails": [...]}. verdict.py reads only that. Bands come from A/A runs, never from zero:
greedy output is not reproducible run to run on this hardware.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANDS = os.path.join(HERE, "quality_bands.json")
DRIFT_KEYS = ("tf_top1", "tf_dlp", "dec_dlp", "dec_prefix")


def gate_of(folder):
    g = json.load(open(os.path.join(folder, "gate.json"), encoding="utf-8"))
    te = os.path.join(folder, "tooleval.json")
    if os.path.exists(te):  # ToolEvalBench points ride along with the gate
        s = json.load(open(te, encoding="utf-8"))["scores"]
        g = dict(g, tooleval_points=s["total_points"], tooleval_max=s["max_points"])
    return g


def fails_of(g, t):
    fails = []
    if g["tf_top1"] < t["tf_top1_min"] - 0.002:
        fails.append(f"tf_top1 {g['tf_top1']:.4f} < {t['tf_top1_min']:.4f}")
    if g["tf_dlp"] > max(1.5 * t["tf_dlp_max"], t["tf_dlp_max"] + 0.01):
        fails.append(f"tf_dlp {g['tf_dlp']:.4f} > band {t['tf_dlp_max']:.4f}")
    if g["dec_dlp"] > max(1.5 * t["dec_dlp_max"], t["dec_dlp_max"] + 0.01):
        fails.append(f"dec_dlp {g['dec_dlp']:.4f} > band {t['dec_dlp_max']:.4f}")
    if g["dec_prefix"] < t["dec_prefix_min"] - 0.15:
        fails.append(f"dec_prefix {g['dec_prefix']:.3f} < band {t['dec_prefix_min']:.3f}")
    if g["reliability_ok"] < t["reliability_min"]:
        fails.append(f"reliability {g['reliability_ok']}/{g['reliability_total']} < {t['reliability_min']}")
    if g["empty_outputs"] > 0:
        fails.append(f"{g['empty_outputs']} empty outputs")
    if g["looping_outputs"] > t["looping_max"]:
        fails.append(f"{g['looping_outputs']} looping outputs")
    # ToolEvalBench runs at T=1 and is not deterministic: a regression alarm, not a ranker
    if "tooleval_min" in t and g.get("tooleval_points", -1) < t["tooleval_min"] - max(3, 2 * t.get("tooleval_range", 0)):
        fails.append(f"ToolEvalBench {g.get('tooleval_points')}/{g.get('tooleval_max')} below its band")
    return fails


def judge(out):
    if not os.path.exists(BANDS):  # baseline and A/A runs: no bands yet, they make them
        res = {"ok": True, "fails": [], "note": "no quality_bands.json yet (A/A run)"}
    else:
        t, g = json.load(open(BANDS, encoding="utf-8")), gate_of(out)
        fails = fails_of(g, t)
        drift = [f for f in fails if f.split(" ")[0] in DRIFT_KEYS]
        # owner rule: numerics may drift when task quality is not worse (tools >= the A/A minimum, nothing else failed)
        if drift and len(drift) == len(fails) and g.get("tooleval_points", -1) >= t.get("tooleval_min", 10 ** 9):
            res = {"ok": True, "fails": [], "note": "drift accepted: " + "; ".join(drift)}
        else:
            res = {"ok": not fails, "fails": fails}
    json.dump(res, open(os.path.join(out, "quality.json"), "w", encoding="utf-8"), indent=1)
    print("QUALITY", "ok" if res["ok"] else "FAIL: " + "; ".join(res["fails"]))


def bands(runs):
    gates = [gate_of(os.path.join(r, "raw")) for r in runs]
    tools = [g["tooleval_points"] for g in gates if "tooleval_points" in g]
    t = {"tf_top1_min": min(g["tf_top1"] for g in gates), "tf_dlp_max": max(g["tf_dlp"] for g in gates),
         "dec_dlp_max": max(g["dec_dlp"] for g in gates), "dec_prefix_min": min(g["dec_prefix"] for g in gates),
         "reliability_min": min(g["reliability_ok"] for g in gates), "looping_max": max(g["looping_outputs"] for g in gates)}
    if tools:
        t.update(tooleval_min=min(tools), tooleval_range=max(tools) - min(tools))
    json.dump(t, open(BANDS, "w", encoding="utf-8"), indent=1)
    print(json.dumps(t, indent=1))


if __name__ == "__main__":
    a = [x.rstrip("/\\") for x in sys.argv[1:]]
    bands(a[1:]) if a[:1] == ["bands"] else judge(a[0])
