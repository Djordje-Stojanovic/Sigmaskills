"""Measure a change, compare it with the champion, and record the pass."""
import argparse
import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
CHAMPION = ROOT / "state/champion.json"
PASS = ROOT / "state/pass.json"
LOCK = ROOT / "evaluator.lock"
SETUP = {"BASELINE", "AA", "RECON"}


def jload(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


def raw(run, name):
    return jload(ROOT / run / "raw" / name)


def sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if path.is_file() else None


def change_hash(run):
    return sha(ROOT / run / "raw/change")


def project():
    return jload(ROOT / "project.json")


def lock_problem(lock):
    if lock is None:
        return "no evaluator.lock yet: run lock on the unchanged runs first"
    for rel, digest in lock["files"].items():
        if sha(ROOT / rel) != digest:
            return f"scorer file changed: {rel}"
    if lock.get("steps", project()["steps"]) != project()["steps"]:
        return "the step commands in project.json changed since the lock"


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
    return sorted(k for k in p.get("weights", {}) if champ.get(k) and not positive(cand.get(k)))


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


def decide(run, announce=True):
    p, lock = project(), jload(LOCK)
    pairs = p.get("measurer") == "pairs"
    meta = raw(run, "meta.json") or {}
    try:
        sc, q = (raw(run, "score.json") or {}, raw(run, "quality.json")) if meta.get("status") == "OK" else ({}, None)
    except ValueError as exc:
        sc, q, meta = {}, None, {"status": f"unreadable raw file: {exc}"}
    inv = jload(ROOT / run / "invariants.json")
    status = str(meta.get("status", "no meta.json"))
    out = {"run": run, "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    if status == "TIMEOUT":
        out.update(verdict="CRASH", why=meta["reason"])
    elif (bad := lock_problem(lock)):
        out.update(verdict="VOID", why=bad)
    elif p.get("invariants", True) and inv is None:
        out.update(verdict="VOID", why="no invariants.json: the change was not checked against the locked settings "
                                     "(write it before the pass, or set \"invariants\": false when nothing is locked)")
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
    if announce:
        save(ROOT / run / "verdict.json", out)
        print(f"VERDICT {out['verdict']}: {out['why']}{show(out, pairs)}")
    return out


def heldout_answer(run, p):
    """PASS | FAIL quality | FAIL gain | another change | None, from the held-out answer file."""
    d = (p.get("heldout") or {}).get("dir")
    r = jload(ROOT / d / "results" / (Path(run).name + ".json")) if d else None
    if r is None:
        return None
    return r["result"] if r.get("change") == change_hash(run) else "another change (stale answer)"


def promote(run, confirm, owner=None):
    p = project()
    out = decide(run)
    q = raw(run, "quality.json") if out["verdict"] not in ("CRASH", "VOID") else None
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
        if (ROOT / c).resolve() == (ROOT / run).resolve():
            why = f"confirmation run {c} is the run itself: measure the change once more"
        elif decide(c)["verdict"] != "KEEP":
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
    lock = jload(LOCK)
    old, runs = champion(lock), [run, *confirm]
    probes = {}
    for x in runs:
        for k, v in ((raw(x, "score.json") or {}).get("probes") or {}).items():
            probes.setdefault(k, []).append(v)
    score_file = ROOT / run / "raw/score.json"
    entry = {"runs": runs, "utc": out["utc"], "vs_champion": out["vs_champion"], "vs_start": out["vs_start"],
             "heldout": answer, "owner": owner, "who": os.environ.get("CLIMB_WHO", ""),
             "keep_to_champion_min": round((time.time() - score_file.stat().st_mtime) / 60, 1)}
    new = {"runs": runs, "probes": {k: statistics.median(v) for k, v in probes.items()}, "start": old["start"],
           "history": old.get("history", []) + [entry]}
    save(CHAMPION, new)
    print(f"PROMOTED: champion = {runs}" + (f", on the owner's word: {owner}" if owner else "") + show(out, p.get("measurer") == "pairs"))
    return 0


def bands(runs, p):
    if p.get("measurer") == "pairs":
        values = [share(((raw(r, "score.json") or {}).get("pairs") or {}).get("champion")) for r in runs]
        if None in values:
            sys.exit("NOT LOCKED: a noise run has no pairs")
        return {}, {}, max(abs(v - 0.5) for v in values)
    rows = [(raw(r, "score.json") or {}).get("probes") or {} for r in runs]
    med = {k: statistics.median(x[k] for x in rows if x.get(k) is not None)
           for k in {k for x in rows for k in x} if any(x.get(k) is not None for x in rows)}
    rats = [ratios(x, med, set(p.get("lower_is_better", []))) for x in rows]
    spread = {k: max((abs(r[k] - 1) for r in rats if k in r), default=0) for k in med}
    scores = [weighted(r, p.get("weights", {})) for r in rats]
    if None in scores or not scores:
        bad = [r for r, s in zip(runs, scores) if s is None]
        sys.exit(f"NOT LOCKED: {bad or runs} has no scored probe; a noise band from nothing would make every gain count")
    return med, spread, max(abs(s - 1) for s in scores)


def lock_runs(runs):
    p = project()
    if len({(ROOT / run).resolve() for run in runs}) != len(runs):
        sys.exit("NOT LOCKED: the same run is named twice; a noise band needs separate runs")
    for run in runs:
        if (raw(run, "meta.json") or {}).get("status") != "OK":
            sys.exit(f"NOT LOCKED: {run} did not finish successfully")
        if (raw(run, "quality.json") or {"ok": True}).get("ok") is not True:
            sys.exit(f"NOT LOCKED: {run} failed its quality check")
    med, spread, score_spread = bands(runs, p)
    files = {rel: sha(ROOT / rel) for rel in ["climb.py", *p["locked"]]}
    for rel, digest in files.items():
        if digest is None:
            sys.exit(f"NOT LOCKED: missing scorer file: {rel}")
    lock = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files, "steps": p["steps"],
            "thresholds": {"spread": spread, "score_spread": score_spread, "baseline_runs": runs, "baseline_probes": med}}
    save(LOCK, lock)
    floor = p["min_gain"] if p.get("min_gain") is not None else 2 * score_spread
    print(json.dumps({"spread": spread, "score_spread": score_spread, "min_gain": floor}, indent=1))
    if len(runs) < p.get("repeats", 3):
        print(f"WARNING: {len(runs)} runs; project.json asks for {p.get('repeats', 3)} to see the noise")


def execute(command, cwd, log, deadline, env=None, stderr=subprocess.STDOUT):
    """A shell step or a held-out check and its children share one deadline."""
    proc = subprocess.Popen(command, shell=isinstance(command, str), cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=stderr, start_new_session=os.name != "nt")
    try:
        return proc.wait(timeout=max(0, deadline - time.monotonic()))
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        # shortcut: a child that left the tree or the group (a detached process, setsid) survives; the stop step ends it
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=30)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=30)
        raise


def heldout(action, run):
    p = project()
    cfg = p["heldout"]
    if not cfg["dir"]:
        sys.exit("set heldout.dir in project.json first")
    d = ROOT / cfg["dir"]
    if action == "selftest":
        run = champion(jload(LOCK))["runs"][0]
    elif not (jload(d / "selftest.json") or {}).get("ok"):
        return print("BROKEN: run heldout selftest first")
    cap = p.get("budget", {}).get("step_seconds")
    if not positive(cap):
        sys.exit("Set a positive budget.step_seconds before running the held-out check.")
    try:
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
            rc = execute([sys.executable, d / "check.py", ROOT, ROOT / run], d, log, time.monotonic() + cap,
                         stderr=subprocess.DEVNULL)
            log.seek(0)
            last = json.loads(log.read().strip().splitlines()[-1])
        quality, gain = rc == 0 and last["quality_ok"] is True, float(last["gain"])
    except (subprocess.TimeoutExpired, OSError, ValueError, TypeError, KeyError, IndexError):
        quality, gain = False, None
    if action == "selftest":
        save(d / "selftest.json", {"ok": quality, "run": run})
        return print("SELFTEST PASS" if quality else f"SELFTEST FAIL: the unchanged champion {run} failed the held-out quality check")
    answer = d / "results" / (Path(run).name + ".json")
    if gain is None:
        answer.unlink(missing_ok=True)
        return print("BROKEN: check.py crashed or printed no answer line")
    visible = jload(ROOT / run / "verdict.json")["gain"]
    result = "FAIL quality" if not quality else "PASS" if gain > 0 and gain >= cfg["share"] * visible else "FAIL gain"
    save(answer, {"run": Path(run).name, "change": change_hash(run), "result": result})
    print(result)


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def run_pass(run, change, full):
    cfg = project()
    caps = cfg.get("budget") or {}
    if not all(positive(caps.get(k)) for k in ("step_seconds", "pass_seconds")):
        print("Set budget.step_seconds and budget.pass_seconds to positive numbers before running a pass.")
        return 2
    change = (ROOT / change).resolve()
    out = ROOT / run / "raw"
    if (out / "DONE").exists():
        print(f"{run} already holds a finished run: take a new run id, its files are evidence.")
        return 2
    change_bytes = change.read_bytes()
    (out.parent / "verdict.json").unlink(missing_ok=True)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "change").write_bytes(change_bytes)
    env = dict(os.environ, CLIMB_OUT=str(out), CLIMB_CHANGE=str(change))
    state = {"run": run, "started": time.time(), "pid": os.getpid(), "finished": False}
    save(PASS, state)
    deadline = time.monotonic() + caps["pass_seconds"]
    meta = {"status": "OK", "stage_s": {}}

    def step(name):
        started = time.monotonic()
        cmd = cfg["steps"].get(name)
        meta["stage_s"][name] = 0
        if not cmd:
            return True
        # Cleanup gets its full step budget even after the pass deadline.
        cap = "step_seconds"
        end = started + caps[cap]
        if name != "stop" and deadline < end:
            cap, end = "pass_seconds", deadline
        reason = f"{name} exceeded {cap}={caps[cap]}s"
        try:
            if started >= end:
                raise subprocess.TimeoutExpired(cmd, 0)
            with (out / "progress.log").open("a", encoding="utf-8") as log:
                rc = execute(cmd, ROOT, log, end, env)
            if rc == 0:
                return True
            if meta["status"] == "OK":
                meta.update(status=f"{name} exited {rc}")
        except subprocess.TimeoutExpired:
            if meta["status"] == "TIMEOUT":
                reason = meta["reason"] + "; " + reason
            meta.update(status="TIMEOUT", reason=reason)
        except OSError as exc:
            if meta["status"] == "OK":
                meta["status"] = f"{name} failed: {exc}"
        finally:
            meta["stage_s"][name] = round(time.monotonic() - started, 4)
        return False

    try:
        if all(step(name) for name in ("start", "warmup", "score")):
            if (out / "status").exists():
                meta["status"] = (out / "status").read_text().strip()
            save(out / "meta.json", meta)
            if full or decide(run, announce=False)["verdict"] == "STAGE1-WIN":
                step("quality")
    except (KeyboardInterrupt, ValueError) as exc:
        meta["status"] = f"interrupted or unreadable output: {exc}"
        raise
    finally:
        step("stop")
        if meta["status"] == "OK" and (out / "status").exists():
            meta["status"] = (out / "status").read_text().strip()
        save(out / "meta.json", meta)
        (out / "DONE").touch()
        save(PASS, {**state, "finished": True})
    print(f"RUN {run}: {meta.get('reason', meta['status'])}")


def table(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def record(a):
    run = ROOT / a.run
    v = jload(run / "verdict.json", {})
    verdict = a.verdict or v.get("verdict")
    if not verdict:
        sys.exit("no verdict given and no verdict.json")
    number = a.number if a.number is not None else int(run.name)
    if any(row["pass"] == str(number) for row in table("results.tsv")):
        sys.exit(f"pass {number} is already recorded")
    stages = (raw(run, "meta.json") or {}).get("stage_s", {})
    total = sum(stages.values())
    # A timed-out writer may have left a partial score or quality file.
    sc = {} if verdict == "CRASH" else raw(run, "score.json") or {}
    q = None if verdict == "CRASH" else raw(run, "quality.json")
    cfg = project()

    def fmt(value, digits=4):
        return "" if value is None else format(value, f".{digits}g")

    row = {
        "pass": number, "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "parent": a.parent, "idea_id": a.idea, "category": a.category, "work_type": a.work, "part": a.part,
        "who": os.environ.get("CLIMB_WHO", ""), "machine": cfg["machine"], "verdict": verdict,
        "vs_champion": fmt(v.get("vs_champion")), "vs_start": fmt(v.get("vs_start")),
        "probes": " ".join(f"{k}={fmt(x)}" for k, x in sorted(sc.get("probes", {}).items()) if x is not None),
        "quality": "" if q is None else "ok" if q.get("ok") else "fail: " + "; ".join(q.get("fails", [])),
        "minutes": fmt(total / 60, 3) if total else "", "score_share": fmt(stages.get("score", 0) / total, 2) if total else "",
        "cost_usd": fmt(total / 3600 * cfg["cost_per_hour"], 3) if total else "", "description": a.desc,
    }
    old = (ROOT / "results.tsv").read_text(encoding="utf-8")
    columns = old.splitlines()[0].split("\t")
    with (ROOT / "results.tsv").open("a", encoding="utf-8") as f:
        f.write(("" if old.endswith("\n") else "\n") + "\t".join(" ".join(str(row[k]).splitlines()).replace("\t", " ") for k in columns) + "\n")
    state = jload(PASS)
    if state and (ROOT / state["run"]).resolve() == run.resolve() and not state.get("finished"):  # a recorded pass is no longer stalled
        save(PASS, {**state, "finished": True})
    print("recorded", number, a.idea, verdict, row["vs_champion"])


def loop_speed(rows):
    rows = [r for r in rows if r["verdict"] not in SETUP]
    minutes = sum(float(r["minutes"]) for r in rows if r.get("minutes"))
    ideas = {r["idea_id"] for r in rows}
    hist = (jload(CHAMPION) or {}).get("history", [])
    shares = [float(r["score_share"]) for r in rows[-5:] if r.get("score_share")]
    return (minutes / len(ideas) if ideas else None, hist[-1]["keep_to_champion_min"] if hist else None,
            statistics.median(shares) if shares else None)


def status():
    cfg, rows = project(), table("results.tsv")
    minutes, delay, share = loop_speed(rows)
    def mins(x):
        return "n/a" if x is None else f"{x:.0f} min"
    tail = (f"{len(rows)} passes | loop: {mins(minutes)} per idea, {mins(delay)} from a KEEP to its champion, "
            f"{'n/a' if share is None else f'{share:.0%}'} of a pass measures the score")
    floor = cfg["score_share_min"]
    if share is not None and share < floor:
        tail += f" - UNDER {floor:.0%}: fix the loop before the next idea"
    hours = cfg["budget"].get("run_hours")
    stopped = (ROOT / "STOP").exists()
    if hours and rows and rows[0]["utc"]:
        first = datetime.datetime.fromisoformat(rows[0]["utc"].replace("Z", "+00:00"))
        stopped |= time.time() >= first.timestamp() + hours * 3600
    state, cap = jload(PASS), cfg["budget"].get("pass_seconds")
    cleanup = cfg["budget"].get("step_seconds") or 0  # the stop step runs after the pass cap, under its own step cap
    if stopped and (ROOT / "REPORT.md").exists():
        print(f"LOOP FINISHED: stop line met, REPORT.md written, {tail}")
    elif state and not state.get("finished") and positive(cap) and time.time() - state["started"] > cap + cleanup:
        print(f"LOOP STALLED: {state['run']} exceeded {cap}s; kill it, record the CRASH, take the next idea | {tail}")
    else:
        print(f"LOOP RUNNING: {tail}")


def check():
    cfg, problems = project(), []
    rows = {}
    for name, first in (("ideas.tsv", "id"), ("results.tsv", "pass")):
        path = ROOT / name
        rows[name] = []
        if not path.is_file():
            problems.append(f"{name}: missing")
            continue
        with path.open(encoding="utf-8") as f:
            fields = f.readline().rstrip("\n").split("\t")
            required = {"status", "notes"} if first == "id" else {"verdict", "idea_id", "category", "work_type", "minutes", "score_share"}
            if fields[0] != first or not required.issubset(fields):
                problems.append(f"{name}: missing or invalid header")
                continue
            for i, line in enumerate(f, 2):
                if not line.strip():
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) != len(fields):
                    problems.append(f"{name}:{i}: {len(parts)} cols, expected {len(fields)}")
                    continue
                row = dict(zip(fields, parts))
                rows[name].append(row)
                if first == "id":
                    if row["status"] not in {"pending", "trying", "dead"}:
                        problems.append(f"{name}:{i}: status must be pending|trying|dead")
                    elif row["status"] == "dead" and not row["notes"].strip():
                        problems.append(f"{name}:{i}: record why it failed and what would reopen it in notes")
                elif row["verdict"] not in SETUP | {"KEEP", "ARCHIVE", "REJECT", "VOID", "CRASH"}:
                    problems.append(f"{name}:{i}: unknown verdict {row['verdict']!r}")
    pending = sum(r["status"] == "pending" for r in rows["ideas.tsv"])
    if pending < 3:
        problems.append(f"ideas.tsv: only {pending} pending ideas (rule: >= 3) - refill now")
    passes = [r for r in rows["results.tsv"] if r["verdict"] not in SETUP]
    share = loop_speed(passes)[2]
    if share is not None and share < cfg["score_share_min"]:
        problems.append(f"the last passes spent {share:.0%} of their time measuring the score - fix the loop first")
    for path in sorted(ROOT.glob("runs/*/raw/meta.json"))[-5:]:
        stages = jload(path).get("stage_s", {})
        if stages.get("quality", 0) > cfg["quality_share_max"] * sum(stages.values()):
            problems.append(f"{path.parent.parent.name}: quality check exceeded {cfg['quality_share_max']:.0%} of a pass")
    n, b = cfg["category_switch_after"], cfg["bold_every"]
    tail = passes[-n:]
    if len(tail) == n and len({r["category"] for r in tail}) == 1 and not any(r["verdict"] == "KEEP" for r in tail):
        problems.append(f"{n} passes in category {tail[0]['category']!r} without a KEEP - change category and profile again")
    if len(passes) >= b and not any(r["work_type"] in ("CODE", "TEXT") for r in passes[-b:]):
        problems.append(f"no code or design change in the last {b} passes - the next pass is one")
    print("STATE: CLEAN" if not problems else f"STATE: {len(problems)} problem(s)\n  " + "\n  ".join(problems))
    return int(bool(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="cmd", required=True)
    run = commands.add_parser("run")
    run.add_argument("run")
    run.add_argument("change")
    run.add_argument("--full", action="store_true")
    commands.add_parser("verdict").add_argument("run")
    prom = commands.add_parser("promote")
    prom.add_argument("run")
    prom.add_argument("confirm", nargs="?")
    prom.add_argument("--owner")
    commands.add_parser("lock").add_argument("runs", nargs="+")
    rec = commands.add_parser("record")
    for key in ("run", "idea", "category", "part", "desc"):
        rec.add_argument("--" + key, required=True)
    rec.add_argument("--work", choices=("CODE", "SETTING", "TEXT"), required=True)
    rec.add_argument("--pass", dest="number", type=int)
    rec.add_argument("--parent", default="")
    rec.add_argument("--verdict")
    commands.add_parser("status")
    commands.add_parser("check")
    held = commands.add_parser("heldout").add_subparsers(dest="action", required=True)
    held.add_parser("check").add_argument("run")
    held.add_parser("selftest")
    a = parser.parse_args()
    if a.cmd == "run":
        return run_pass(a.run, a.change, a.full)
    if a.cmd == "verdict":
        decide(a.run)
    elif a.cmd == "promote":
        return promote(a.run, [a.confirm] if a.confirm else [], a.owner)
    elif a.cmd == "lock":
        lock_runs(a.runs)
    elif a.cmd == "heldout":
        heldout(a.action, getattr(a, "run", None))
    elif a.cmd == "record":
        record(a)
    elif a.cmd == "status":
        status()
    else:
        return check()


if __name__ == "__main__":
    sys.exit(main())
