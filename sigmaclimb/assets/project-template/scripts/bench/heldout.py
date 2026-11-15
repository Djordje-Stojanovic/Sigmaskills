"""heldout.py - the held-out check: the same quality check and score on inputs the loop never tuned to.
Off by default (project.json "heldout": {"mode": "off" | "advisory" | "required"}). references/held-out.md says when.

  python heldout.py selftest PROJECT_DIR           once, before first use: the unchanged champion must pass the quality stage
  python heldout.py check PROJECT_DIR runs/<n>     prints PASS, FAIL quality or FAIL gain; no numbers

DIR = project.json heldout.dir. DIR/check.py is the owner's script: it gets PROJECT_DIR and a run folder, runs the
change on the held-out inputs on the SAME machine as the candidates, and prints as its last line
{"quality_ok": true, "gain": 0.04}: the quality check there, and the gain there in the visible score's unit
(ratio - 1, or share of pairs won - 0.5). Everything else it prints is thrown away.
PASS = quality_ok and gain >= share x the visible gain (runs/<n>/verdict.json). Answers go to DIR/results/<run>.json.
"""
import hashlib, json, os, subprocess, sys


def _hash(path):
    """The same hash as verdict.py: line endings do not count."""
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest() if os.path.exists(path) else None


def _run_check(d, project, run):
    """The owner's script on one run: (quality_ok, gain), or None when it crashed or printed no answer."""
    try:
        run = os.path.abspath(os.path.join(project, run))  # check.py runs in DIR: give it paths that work there
        p = subprocess.run([sys.executable, os.path.join(d, "check.py"), project, run], cwd=d, capture_output=True, text=True)
        r = json.loads(p.stdout.strip().splitlines()[-1])
        return (p.returncode == 0 and r["quality_ok"] is True), float(r["gain"])
    except Exception:  # a crash or bad output is a broken check, not an answer
        return None


def selftest(project, d):
    champ = json.load(open(os.path.join(project, "state", "champion.json"), encoding="utf-8"))["runs"][0] \
        if os.path.exists(os.path.join(project, "state", "champion.json")) else \
        json.load(open(os.path.join(project, "evaluator.lock"), encoding="utf-8"))["thresholds"]["baseline_runs"][0]
    r = _run_check(d, project, champ)
    ok = r is not None and r[0]
    json.dump({"ok": ok, "run": champ}, open(os.path.join(d, "selftest.json"), "w"))
    print("SELFTEST PASS" if ok else f"SELFTEST FAIL: the unchanged champion {champ} does not pass the quality stage "
          "on the held-out set. The check is broken: fix it, and do not use it until it passes.")


def check(project, d, share, run):
    st = os.path.join(d, "selftest.json")
    if not os.path.exists(st) or not json.load(open(st))["ok"]:
        return print("BROKEN: run heldout.py selftest first; a check that fails the champion teaches nothing")
    visible = json.load(open(os.path.join(project, run, "verdict.json"), encoding="utf-8"))["gain"]
    change = _hash(os.path.join(project, run, "raw", "change"))
    r = _run_check(d, project, run)
    if r is None:
        return print("BROKEN: check.py crashed or printed no answer line")
    result = "FAIL quality" if not r[0] else "PASS" if r[1] > 0 and r[1] >= share * visible else "FAIL gain"
    os.makedirs(os.path.join(d, "results"), exist_ok=True)
    json.dump({"run": os.path.basename(run), "change": change, "result": result},
              open(os.path.join(d, "results", os.path.basename(run) + ".json"), "w"))
    print(result)


if __name__ == "__main__":
    a = [x.rstrip("/\\") for x in sys.argv[1:]]
    if len(a) >= 2 and a[0] in ("selftest", "check"):
        a[1] = os.path.abspath(a[1])  # check.py runs in DIR, so a relative project path would point elsewhere
        h = json.load(open(os.path.join(a[1], "project.json"), encoding="utf-8")).get("heldout") or {}
        if not h.get("dir"):
            sys.exit("set heldout.dir in project.json first")
        selftest(a[1], h["dir"]) if a[0] == "selftest" else check(a[1], h["dir"], h.get("share", 0.5), a[2])
    else:
        sys.exit(__doc__)
