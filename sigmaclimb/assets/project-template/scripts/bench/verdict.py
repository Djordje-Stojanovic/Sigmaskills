"""verdict.py - the only thing that decides. It reads raw files and project.json, never the agent's summary.

  python scripts/bench/verdict.py runs/<n>                                   -> runs/<n>/verdict.json + one line
  python scripts/bench/verdict.py promote runs/<n> [runs/<m>] [--owner "his words"]  -> the only writer of state/champion.json

A run holds raw/score.json, raw/quality.json ({"ok": bool, "fails": [...]}, written by stage 2 only),
raw/meta.json ({"status": "OK", "stage_s": {...}}) and raw/change (a copy of the change).
score.json: {"probes": {name: value}} when project.json "measurer" is "script";
            {"pairs": {"champion": {"won", "lost", "tied"}, "start": {...}}} when it is "pairs" (blind pairs, judged).
Every number comes from project.json and evaluator.lock. This file holds no threshold of its own.

Verdicts: VOID (scorer edited, invariant broken), CRASH (the run failed), REJECT, ARCHIVE (a trade: the owner
rules), STAGE1-WIN (the score wins, the quality check has not run yet: never a KEEP), KEEP.
"""
import datetime, hashlib, json, math, os, statistics, sys, time

ROOT = os.environ.get("CLIMB_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHAMPION = os.path.join(ROOT, "state", "champion.json")


def jload(path, default=None):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def raw(run, name):
    return jload(os.path.join(ROOT, run, "raw", name))


def sha(path):
    """Line endings do not count: a Windows checkout and the box hold the same file."""
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest() if os.path.exists(path) else None


def change_hash(run):
    return sha(os.path.join(ROOT, run, "raw", "change"))


def project():
    return jload(os.path.join(ROOT, "project.json"), {})


def lock_problem(lock):
    if lock is None:
        return "no evaluator.lock yet: run aa.py on the A/A runs first"
    bench = os.path.join(ROOT, "scripts", "bench")
    for rel, digest in lock["files"].items():
        if sha(os.path.join(bench, rel)) != digest:
            return f"scorer file changed: {rel}"
    return None


def champion(lock):
    t = lock["thresholds"]
    return jload(CHAMPION) or {"runs": t["baseline_runs"], "probes": t["baseline_probes"],
                               "start": t["baseline_probes"], "history": []}


def ratios(cand, ref, lower):
    """Per probe, candidate against a reference. Above 1 is better, whatever the probe's direction."""
    out = {}
    for k, v in cand.items():
        r = ref.get(k)
        if v and r and v > 0 and r > 0:
            out[k] = r / v if k in lower else v / r
    return out


def weighted(r, weights):
    """Weighted geometric mean. A probe with weight 0 is a guard: it never scores, but it may not drop."""
    w = {k: weights[k] for k in r if weights.get(k)}
    tot = sum(w.values())
    return math.exp(sum(w[k] / tot * math.log(r[k]) for k in w)) if tot else None


def missing(cand, champ, p):
    """Scored or guard probes the champion measured and the candidate did not: a gap is never a pass."""
    return sorted(k for k in p.get("weights", {}) if champ.get(k) and not cand.get(k))


def share(p):
    n = p and p["won"] + p["lost"] + p["tied"]
    return (p["won"] + p["tied"] / 2) / n if n else None


def min_gain(p, t):
    return p["min_gain"] if p.get("min_gain") is not None else 2 * t["score_spread"]


def max_drop(p, t, k):
    return p["max_drop"] if p.get("max_drop") is not None else 2 * t["spread"].get(k, 0)


def show(out, pairs):
    if out.get("vs_champion") is None:
        return ""
    if pairs:
        start = "n/a" if out.get("vs_start") is None else f"{out['vs_start']:.0%}"
        return f" | won {out['vs_champion']:.0%} of pairs against the champion before, {start} against the start"
    start = "n/a" if out.get("vs_start") is None else f"x{out['vs_start']:.3f}"
    return f" | x{out['vs_champion']:.3f} against the champion before, {start} against the start"


def decide(run):
    p, lock = project(), jload(os.path.join(ROOT, "evaluator.lock"))
    pairs = p.get("measurer") == "pairs"
    meta, sc, q = raw(run, "meta.json") or {}, raw(run, "score.json") or {}, raw(run, "quality.json")
    inv = jload(os.path.join(ROOT, run, "invariants.json"))
    status = str(meta.get("status", "no meta.json"))
    out = {"run": run, "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    if (bad := lock_problem(lock)):
        out.update(verdict="VOID", why=bad)
    elif p.get("invariants", True) and inv is None:
        out.update(verdict="VOID", why="no invariants.json: the change was not checked against the locked settings")
    elif inv is not None and not inv.get("ok"):
        out.update(verdict="VOID", why="invariant broken: " + "; ".join(inv.get("problems", [])))
    elif status.startswith("VOID"):
        out.update(verdict="VOID", why=status)
    elif status != "OK":
        out.update(verdict="CRASH", why=f"run status {status}")
    elif not sc.get("pairs" if pairs else "probes"):
        out.update(verdict="CRASH", why="no score in raw/score.json")
    elif not pairs and (gone := missing(sc["probes"], champion(lock)["probes"], p)):
        out.update(verdict="CRASH", why=f"probes the champion has are missing: {gone}")
    else:
        t, champ = lock["thresholds"], champion(lock)
        mg = min_gain(p, t)
        if pairs:
            vc, vs = share(sc["pairs"].get("champion")), share(sc["pairs"].get("start"))
            gain, drops, ups = None if vc is None else vc - 0.5, {}, {}
        else:
            lower = set(p.get("lower_is_better", []))
            r = ratios(sc["probes"], champ["probes"], lower)
            vc = weighted(r, p.get("weights", {}))
            vs = weighted(ratios(sc["probes"], champ["start"], lower), p.get("weights", {}))
            gain = None if vc is None else vc - 1
            drops = {k: round(v, 4) for k, v in r.items() if v < 1 - max_drop(p, t, k)}
            ups = {k: round(v, 4) for k, v in r.items() if v > 1 + max(mg, max_drop(p, t, k))}
            out.update(ratios=r)
        out.update(vs_champion=vc, vs_start=vs, gain=gain, min_gain=mg, champion_runs=champ["runs"])
        win = gain is not None and gain > 0 and gain >= mg
        if gain is None:
            out.update(verdict="CRASH", why="the score shares no probe or pair with the champion")
        elif q is not None and not q.get("ok"):
            out.update(verdict="REJECT", why="quality check failed: " + "; ".join(q.get("fails", [])))
        elif win and not drops:
            out.update(verdict="KEEP" if q is not None else "STAGE1-WIN",
                       why=f"gain {gain:+.4f} >= {mg:.4f}, no probe dropped past its band"
                           + ("" if q is not None else "; the quality check runs next"))
        elif win or ups:
            out.update(verdict="ARCHIVE", why=f"not a clean win: up {ups or 'the score'}, down {drops or 'nothing'}; the owner rules")
        else:
            out.update(verdict="REJECT", why=f"gain {gain:+.4f} < {mg:.4f}" + (f"; drops {drops}" if drops else ""))
    json.dump(out, open(os.path.join(ROOT, run, "verdict.json"), "w", encoding="utf-8"), indent=1)
    print(f"VERDICT {out['verdict']}: {out['why']}{show(out, pairs)}")
    return out


def heldout_answer(run, p):
    """PASS | FAIL quality | FAIL gain | another change | None, from heldout.py's answer file."""
    d = (p.get("heldout") or {}).get("dir")
    r = jload(os.path.join(d, "results", os.path.basename(run) + ".json")) if d else None
    if r is None:
        return None
    return r["result"] if r.get("change") == change_hash(run) else "another change (stale answer)"


def promote(run, confirm, owner=None):
    p = project()
    out, q = decide(run), raw(run, "quality.json")
    mode = (p.get("heldout") or {}).get("mode", "off")
    answer = heldout_answer(run, p) if mode != "off" else None
    why = None
    if out["verdict"] in ("VOID", "CRASH"):
        why = f"{run} is {out['verdict']}: {out['why']}"
    elif q is None:
        why = f"the quality check has not run on {run}: every new champion passes it"
    elif not q.get("ok"):
        why = f"{run} failed the quality check"
    elif out["verdict"] != "KEEP" and not owner:
        why = f"{run} is {out['verdict']}; only the owner's word (--owner) promotes it"
    elif not owner and out["gain"] < p.get("confirm_below", 2) * out["min_gain"] and not confirm:
        why = f"gain {out['gain']:+.4f} is under {p.get('confirm_below', 2)} x the smallest gain: run one confirmation first"
    for c in confirm:
        if why:
            break
        if decide(c)["verdict"] != "KEEP":
            why = f"confirmation run {c} is not a KEEP"
        elif change_hash(c) != change_hash(run):
            why = f"confirmation run {c} is another change"
    if not why and mode == "required" and not owner and answer != "PASS":
        why = f"held-out check (required): {answer or 'no answer yet'} for {run}"
    if why:
        print(f"REFUSED: {why}")
        return 1
    if mode == "advisory":
        print(f"held-out check (advisory, does not block): {answer or 'not run'}")
    lock = jload(os.path.join(ROOT, "evaluator.lock"))
    old, runs = champion(lock), [run, *confirm]
    probes = {}
    for x in runs:
        for k, v in ((raw(x, "score.json") or {}).get("probes") or {}).items():
            probes.setdefault(k, []).append(v)
    score_file = os.path.join(ROOT, run, "raw", "score.json")
    entry = {"runs": runs, "utc": out["utc"], "vs_champion": out["vs_champion"], "vs_start": out["vs_start"],
             "heldout": answer, "owner": owner, "who": os.environ.get("CLIMB_WHO", ""),
             "keep_to_champion_min": round((time.time() - os.path.getmtime(score_file)) / 60, 1)}
    new = {"runs": runs, "probes": {k: statistics.median(v) for k, v in probes.items()}, "start": old["start"],
           "history": old.get("history", []) + [entry]}
    os.makedirs(os.path.dirname(CHAMPION), exist_ok=True)
    json.dump(new, open(CHAMPION + ".tmp", "w", encoding="utf-8"), indent=1)
    os.replace(CHAMPION + ".tmp", CHAMPION)
    print(f"PROMOTED: champion = {runs}" + (f", on the owner's word: {owner}" if owner else "") + show(out, p.get("measurer") == "pairs"))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    owner = a[a.index("--owner") + 1] if "--owner" in a else None
    if owner is not None:
        del a[a.index("--owner"):a.index("--owner") + 2]
    a = [x.rstrip("/\\") for x in a]
    if a[:1] == ["promote"] and len(a) > 1:
        sys.exit(promote(a[1], a[2:], owner))
    if len(a) != 1:
        sys.exit(__doc__)
    decide(a[0])
