"""verdict.py - the only thing that decides KEEP. Reads raw files, never the worker's summary.

  python scripts/bench/verdict.py runs/<n>      -> runs/<n>/verdict.json + one summary line

Champion numbers = median over the runs listed in state/champion.json. Thresholds come from evaluator.lock.
"""
import hashlib, json, math, os, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Score weights live in project.json ("weights"). Components a run lacks are dropped and the rest renormalized.
# Defaults = the la125 owner mix (v7): 1-stream decode and agent turns first, then 2 agents, prefill, 3 agents.
def _weights():
    p = os.path.join(ROOT, "project.json")
    w = {"short": 0.30, "warm": 0.20, "miss": 0.10, "long": 0.15, "prefill": 0.10, "c2": 0.08, "replay": 0.04, "c3": 0.03}  # v8.2 default
    if os.path.exists(p):
        w = json.load(open(p, encoding="utf-8")).get("weights", w)
    return w


WEIGHTS = _weights()


def load(run, name):
    p = os.path.join(ROOT, run, "raw", name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def extract(run):
    """Raw numbers of one run. Higher is better for every component (replay is inverted)."""
    s, g, m = load(run, "speed.json"), load(run, "gate.json"), load(run, "meta.json") or {}
    te, tt = load(run, "tooleval.json"), load(run, "tooleval_time.json")
    if g is not None and te:  # ToolEvalBench TC-01..TC-25 points ride along with the gate
        g = dict(g, tooleval_points=te["scores"]["total_points"], tooleval_max=te["scores"]["max_points"],
                 tooleval_wall_s=(tt or {}).get("wall_s"))
    out = {"meta": m, "gate": g, "bw": [x["copy_gbps"] for x in (load(run, "bw_before.json"), load(run, "bw_after.json")) if x]}
    if s:  # evaluator v2 (real settings): decode = short decode (low/medium) and long xhigh thinking
        out.update(
            replay_wall_s=s["replay"]["wall_s"], decode_greedy=s["short"]["decode_tps_geo"],
            decode_sampled=s["long"]["decode_tps"], prefill_geo=s["prefill"]["prefill_tps_geo"],
            c3_tps=s["parallel"]["aggregate_tps"], c2_tps=(s.get("parallel2") or {}).get("aggregate_tps"),
            prefill_64k=s["prefill"]["64k"]["prefill_tps"],
            ttft_128k=s["prefill"]["128k"]["ttft_s"], replay_ttft_p50=s["replay"]["ttft_p50_s"],
            mtp_accept=s.get("mtp_accept_decode_probe"), replay_version=s["replay"].get("version"),
            warm_miss=1 - (s["replay"].get("warm_hit_rate") or 0),
            warm_ttft_sum=sum(x["ttft_s"] for rs in s["replay"]["turns"] for x in rs[1:] if x.get("ttft_s")))
    return out


def ratios(cand, champ):
    """candidate / champion per score component (>1 = candidate faster)."""
    return {
        # replay wall time compares only between runs of the same replay version (v8 = fixed-length turns)
        **({"replay": champ["replay_wall_s"] / cand["replay_wall_s"]}
           if cand.get("replay_version") == champ.get("replay_version") else {}),
        "warm": champ["warm_ttft_sum"] / cand["warm_ttft_sum"],
        "short": cand["decode_greedy"] / champ["decode_greedy"],
        "long": cand["decode_sampled"] / champ["decode_sampled"],
        **({"miss": champ["warm_miss"] / cand["warm_miss"]} if cand.get("warm_miss") and champ.get("warm_miss") else {}),
        "prefill": cand["prefill_geo"] / champ["prefill_geo"],
        "c3": cand["c3_tps"] / champ["c3_tps"],
        **({"c2": cand["c2_tps"] / champ["c2_tps"]} if cand.get("c2_tps") and champ.get("c2_tps") else {}),
    }


def single_probe_win(cand, champ, t):
    """Owner rule 2026-10-24: one probe >= +10% while every other probe stays >= -5% is a KEEP,
    even when the weighted score dilutes it (e.g. long thinking +14%, rest flat)."""
    win, other = t.get("single_win", 0.10), t.get("single_other_min", 0.95)
    p = {"short": cand["decode_greedy"] / champ["decode_greedy"], "long": cand["decode_sampled"] / champ["decode_sampled"],
         "warm": champ["warm_ttft_sum"] / cand["warm_ttft_sum"], "prefill": cand["prefill_geo"] / champ["prefill_geo"],
         "c3": cand["c3_tps"] / champ["c3_tps"]}
    if cand.get("replay_version") == champ.get("replay_version"):
        p["replay"] = champ["replay_wall_s"] / cand["replay_wall_s"]
    if cand.get("c2_tps") and champ.get("c2_tps"):
        p["c2"] = cand["c2_tps"] / champ["c2_tps"]
    best = max(p, key=p.get)
    if p[best] >= 1 + win and all(v >= other for k, v in p.items() if k != best):
        return {best: round(p[best], 4)}
    return None


def score(r):
    w = {k: WEIGHTS[k] for k in WEIGHTS if k in r}
    tot = sum(w.values())
    return math.exp(sum(w[k] / tot * math.log(r[k]) for k in w))


def champion():
    runs = json.load(open(os.path.join(ROOT, "state", "champion.json"), encoding="utf-8"))["runs"]
    rows = [extract(r) for r in runs]
    keys = ("replay_wall_s", "decode_greedy", "decode_sampled", "prefill_geo", "c3_tps", "c2_tps", "warm_ttft_sum", "warm_miss")
    out = {"replay_version": max((x.get("replay_version") or 0) for x in rows)}
    for k in keys:
        vals = [x[k] for x in rows if x.get(k) is not None]
        out[k] = statistics.median(vals) if vals else None
    return out, runs


def lock_ok(lock):
    bench = os.path.join(ROOT, "scripts", "bench")
    for rel, digest in lock["files"].items():
        p = os.path.join(bench, rel)
        if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != digest:
            return False, rel
    return True, None


DRIFT_KEYS = ("tf_top1", "tf_dlp", "dec_dlp", "dec_prefix")


def gate_ok(g, t):
    """Owner decision 2026-10-23: numerics may drift (e.g. mbt 4096 picks other kernels) if quality is not
    worse. A drift-only failure passes when ToolEvalBench >= the champion's lowest A/A score (no slack) and
    needles, empty and looping checks pass. Any other failure stays final."""
    fails = _gate_fails(g, t)
    drift = [f for f in fails if f.split(" ")[0] in DRIFT_KEYS]
    other = [f for f in fails if f not in drift]
    if drift and not other and g.get("tooleval_points", -1) >= t.get("tooleval_min", 10**9):
        return True, [f"drift accepted (tools {g.get('tooleval_points')} >= {t.get('tooleval_min')}): " + "; ".join(drift)]
    return not fails, fails


def _gate_fails(g, t):
    fails = []
    if g is None:
        return ["no gate.json"]
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
    # ToolEvalBench runs at T=1.0 (real use) and is not deterministic: it is a regression alarm, not a ranker.
    # Reject only a drop beyond the A/A noise: min - max(3 points, 2 x A/A range). Fidelity stays the main veto.
    if "tooleval_min" in t:
        allow = max(3, 2 * t.get("tooleval_range", 0))
        if g.get("tooleval_points", -1) < t["tooleval_min"] - allow:
            fails.append(f"ToolEvalBench {g.get('tooleval_points')}/{g.get('tooleval_max')} < band "
                         f"{t['tooleval_min']} - {allow}")
    return fails


def decide(run):
    lock = json.load(open(os.path.join(ROOT, "evaluator.lock"), encoding="utf-8"))
    t = lock["thresholds"]
    cand = extract(run)
    inv = json.load(open(os.path.join(ROOT, run, "invariants.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(ROOT, run, "invariants.json")) else {"ok": False, "problems": ["invariants.json missing"]}
    out = {"run": run, "status": cand["meta"].get("status")}
    ok, bad = lock_ok(lock)
    if not ok:
        out.update(verdict="VOID", why=f"evaluator file changed: {bad}")
    elif not inv["ok"]:
        out.update(verdict="VOID", why="invariant broken: " + "; ".join(inv["problems"]))
    elif out["status"] == "MEMFLOOR":
        out.update(verdict="VOID", why=f"MemAvailable fell to {cand['meta'].get('low_mem_gib')} GiB during start (floor 4)")
    elif out["status"] != "OK":
        out.update(verdict="CRASH", why=f"run status {out['status']}")
    elif any(b < t["bw_median"] * 0.75 for b in cand["bw"]) or len(cand["bw"]) < 2:
        out.update(verdict="RERUN", why=f"bandwidth flip or missing probe: {cand['bw']} vs median {t['bw_median']}")
    else:
        gok, fails = gate_ok(cand["gate"], t)
        champ, champ_runs = champion()
        r = ratios(cand, champ)
        sc = score(r)
        floor = t.get("keep_floor", max(0.02, 2 * t["score_spread"]))  # owner set 0.05 on 2026-10-24
        drops = {k: r[k] for k in r if r[k] < 1 - max(0.02, 2 * t["spread"].get({"short": "decode", "long": "decode"}.get(k, k), t["spread"].get("c3", 0.02)))}
        clear_wins = {k: r[k] for k in r if r[k] > 1 + max(0.05, 3 * t["spread"].get({"short": "decode", "long": "decode"}.get(k, k), t["spread"].get("c3", 0.02)))}
        out.update(ratios=r, score=sc, floor=floor, champion_runs=champ_runs, gate_fails=fails)
        if not gok:
            out.update(verdict="REJECT", why="quality gate: " + "; ".join(fails))
        elif sc >= 1 + floor and not drops:
            out.update(verdict="KEEP", why=f"score {sc:.4f} >= {1 + floor:.4f}, no probe dropped past its band")
        elif (single := single_probe_win(cand, champ, t)):
            out.update(verdict="KEEP", why=f"single-probe win {single} (owner rule 2026-10-24), score {sc:.4f}")
        elif clear_wins:
            out.update(verdict="ARCHIVE", why=f"score {sc:.4f} below keep, but clear single win {clear_wins}; drops {drops}")
        else:
            out.update(verdict="REJECT", why=f"score {sc:.4f} < {1 + floor:.4f}" + (f"; drops {drops}" if drops else ""))
    json.dump(out, open(os.path.join(ROOT, run, "verdict.json"), "w", encoding="utf-8"), indent=1)
    print(f"VERDICT {out['verdict']}: {out['why']}")
    return out


if __name__ == "__main__":
    decide(sys.argv[1].rstrip("/\\"))
