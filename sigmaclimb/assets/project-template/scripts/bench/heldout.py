"""heldout.py - the held-out check. The owner seals a set once. The loop gets PASS or FAIL and nothing else.

  python heldout.py init SEALED_DIR [--share 0.5]     owner, once, as the sealing user (the loop's user must not be it)
  python heldout.py check PROJECT_DIR runs/<n>        run as the sealing user; prints PASS or FAIL, nothing more

SEALED_DIR/inputs/    mode 0700. check.py (the owner's script) and the sealed inputs live here. The loop cannot read them.
SEALED_DIR/results/   mode 0755. One <run>.json per check. Only the sealing user can write it; verdict.py reads it.
SEALED_DIR/heldout.py a copy of this file. verdict.py compares it with the copy in scripts/bench (the hash lock).
SEALED_DIR/share      the share of the visible gain the sealed set must show (default 0.5).

inputs/check.py gets PROJECT_DIR and runs/<n>. Its last stdout line is {"gate_ok": true, "ratio": 1.04}: the quality
gate on the sealed inputs, and the score ratio there (above 1 is better). Everything else it prints is thrown away.
PASS = gate_ok and ratio - 1 >= share * (visible score - 1). A crash, a timeout or bad output is FAIL.
"""
import hashlib, json, os, shutil, subprocess, sys

CHANGE = "serve.sh"  # the file in runs/<n>/ that IS the change. Another target: name its patch or script here.


def _sha(*paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(open(p, "rb").read() if os.path.exists(p) else b"\0missing")
        h.update(b"\0")
    return h.hexdigest()


def fingerprint(project, run):
    """Which change, under which settings. A result for any other fingerprint is stale."""
    return {"run": os.path.basename(run.rstrip("/\\")), "change": _sha(os.path.join(project, run, CHANGE)),
            "config": _sha(os.path.join(project, "project.json"), os.path.join(project, "evaluator.lock"))}


def init(sealed, share):
    for sub, mode in (("inputs", 0o700), ("results", 0o755)):
        os.makedirs(os.path.join(sealed, sub), exist_ok=True)
        os.chmod(os.path.join(sealed, sub), mode)
    os.chmod(sealed, 0o755)
    shutil.copyfile(os.path.abspath(__file__), os.path.join(sealed, "heldout.py"))
    open(os.path.join(sealed, "share"), "w").write(str(share))
    stub = os.path.join(sealed, "inputs", "check.py")
    if not os.path.exists(stub):  # never overwrite the owner's script
        open(stub, "w").write('"""Write the sealed check here. Last stdout line: {"gate_ok": true, "ratio": 1.0}"""\n'
                              'import sys\nsys.exit("check.py is not written yet")\n')
        os.chmod(stub, 0o600)
    print(f"sealed set ready: {sealed}\n"
          f"1. Write {sealed}/inputs/check.py and put the sealed inputs beside it (as this user).\n"
          f'2. Put "sealed_dir": "{sealed}" in project.json.\n'
          f"3. Let the loop's user run only the check: <loop-user> ALL=({os.environ.get('USER', 'sealuser')}) NOPASSWD: "
          f"{sys.executable} {sealed}/heldout.py check <PROJECT_DIR> runs/*\n"
          f"4. Re-run init after any edit of scripts/bench/heldout.py, then migrate the lock.")


def check(project, run):
    here = os.path.dirname(os.path.abspath(__file__))
    ok, visible = False, 0.0
    try:
        visible = json.load(open(os.path.join(project, run, "verdict.json")))["score"]
        share = float(open(os.path.join(here, "share")).read())
        p = subprocess.run([sys.executable, os.path.join(here, "inputs", "check.py"), project, run],
                           cwd=os.path.join(here, "inputs"), capture_output=True, text=True)
        r = json.loads(p.stdout.strip().splitlines()[-1])
        ok = p.returncode == 0 and r["gate_ok"] is True and visible > 1 and r["ratio"] - 1 >= share * (visible - 1)
    except Exception:  # shortcut: any failure is FAIL, never a message that could leak an input
        ok = False
    res = dict(fingerprint(project, run), visible_score=round(visible, 6), result="PASS" if ok else "FAIL")
    out = os.path.join(here, "results", res["run"] + ".json")
    with open(out + ".tmp", "w") as f:
        json.dump(res, f)
    os.chmod(out + ".tmp", 0o644)  # the loop's user reads it, never writes it
    os.replace(out + ".tmp", out)
    print(res["result"])


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "init":
        init(a[1], a[a.index("--share") + 1] if "--share" in a else 0.5)
    elif len(a) == 3 and a[0] == "check":
        check(a[1], a[2].rstrip("/\\"))
    else:
        sys.exit(__doc__)
