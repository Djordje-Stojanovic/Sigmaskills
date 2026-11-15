"""heldout.py - the held-out check. The owner seals a set once. The loop gets PASS or FAIL and nothing else.

  python heldout.py init SEALED_DIR [--share 0.5] [--looks 10]   owner, once, as the sealing user (not the loop's user)
  python heldout.py check PROJECT_DIR runs/<n>                   run as the sealing user; prints PASS or FAIL, nothing more

SEALED_DIR/inputs/    mode 0700. check.py (the owner's script) and the sealed inputs live here. The loop cannot read them.
SEALED_DIR/results/   mode 0755. One <run>.json per check. Only the sealing user can write it; verdict.py reads it.
SEALED_DIR/heldout.py a copy of this file. verdict.py compares it with the copy in scripts/bench (the hash lock).
SEALED_DIR/share      the share of the visible gain the sealed set must show (default 0.5).
SEALED_DIR/max_looks  how many runs may be looked at before the set is spent (default 10). One look per run: a second
                      check of the same run prints the stored answer. A spent set prints FAIL and writes nothing.
Trust: the sealing user owns SEALED_DIR, so the loop's user cannot write results/. verdict.py refuses a results folder
that the loop's user owns or can write. check.py runs the candidate: it must not run it as the sealing user, or the
candidate can read the inputs and print its own answer. The change must not move while check runs (fingerprint before = after).

inputs/check.py gets PROJECT_DIR and runs/<n>. Its last stdout line is {"gate_ok": true, "ratio": 1.04}: the quality
gate on the sealed inputs, and the score ratio there (above 1 is better). Everything else it prints is thrown away.
PASS = gate_ok and ratio - 1 >= share * (visible score - 1). A crash, a timeout or bad output is FAIL.
"""
import hashlib, json, os, shutil, subprocess, sys

CHANGE = ("serve.sh",)  # the files in runs/<n>/ that ARE the change. Another target: list its patch, script and every file they load.


def _sha(*paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(open(p, "rb").read() if os.path.exists(p) else b"\0missing")
        h.update(b"\0")
    return h.hexdigest()


def fingerprint(project, run):
    """Which change, under which settings. A result for any other fingerprint is stale."""
    return {"run": os.path.basename(run.rstrip("/\\")), "change": _sha(*[os.path.join(project, run, c) for c in CHANGE]),
            "config": _sha(os.path.join(project, "project.json"), os.path.join(project, "evaluator.lock"))}


def init(sealed, share, looks):
    for sub, mode in (("inputs", 0o700), ("results", 0o755)):
        os.makedirs(os.path.join(sealed, sub), exist_ok=True)
        os.chmod(os.path.join(sealed, sub), mode)
    os.chmod(sealed, 0o755)
    shutil.copyfile(os.path.abspath(__file__), os.path.join(sealed, "heldout.py"))
    for name, value in (("share", share), ("max_looks", looks)):
        open(os.path.join(sealed, name), "w").write(str(value))
    stub = os.path.join(sealed, "inputs", "check.py")
    if not os.path.exists(stub):  # never overwrite the owner's script
        open(stub, "w").write('"""Write the sealed check here. Last stdout line: {"gate_ok": true, "ratio": 1.0}"""\n'
                              'import sys\nsys.exit("check.py is not written yet")\n')
        os.chmod(stub, 0o600)
    print(f"sealed set ready: {sealed}\n"
          f"1. Write {sealed}/inputs/check.py and put the sealed inputs beside it (as this user).\n"
          f'2. Put "sealed_dir": "{sealed}" in project.json.\n'
          f"3. Let the loop's user run only the check: <loop-user> ALL=({os.environ.get('USER', 'sealuser')}) NOPASSWD: "
          f"{sys.executable} {sealed}/heldout.py check <PROJECT_DIR> runs/[0-9][0-9][0-9][0-9]\n"
          f"4. Re-run init after any edit of scripts/bench/heldout.py, then migrate the lock.")


def check(project, run):
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "results", os.path.basename(run) + ".json")
    if os.path.exists(out):  # one look per run: the answer was given once and stays
        return print(json.load(open(out))["result"])
    if len(os.listdir(os.path.dirname(out))) >= int(open(os.path.join(here, "max_looks")).read()):
        return print("FAIL")  # the set is spent; the owner makes a new one
    ok, visible, before = False, 0.0, fingerprint(project, run)
    try:
        visible = json.load(open(os.path.join(project, run, "verdict.json")))["score"]
        share = float(open(os.path.join(here, "share")).read())
        p = subprocess.run([sys.executable, os.path.join(here, "inputs", "check.py"), project, run],
                           cwd=os.path.join(here, "inputs"), capture_output=True, text=True)
        r = json.loads(p.stdout.strip().splitlines()[-1])
        ok = (p.returncode == 0 and r["gate_ok"] is True and visible > 1 and r["ratio"] - 1 >= share * (visible - 1)
              and fingerprint(project, run) == before)  # a change that moved during the check is not the one checked
    except Exception:  # shortcut: any failure is FAIL, never a message that could leak an input
        ok = False
    res = dict(before, visible_score=round(visible, 6), result="PASS" if ok else "FAIL")
    with open(out + ".tmp", "w") as f:
        json.dump(res, f)
    os.chmod(out + ".tmp", 0o644)  # the loop's user reads it, never writes it
    os.replace(out + ".tmp", out)
    print(res["result"])


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "init":
        opt = lambda flag, default: a[a.index(flag) + 1] if flag in a else default
        init(a[1], float(opt("--share", 0.5)), int(opt("--looks", 10)))
    elif len(a) == 3 and a[0] == "check":
        check(a[1], a[2].rstrip("/\\"))
    else:
        sys.exit(__doc__)
