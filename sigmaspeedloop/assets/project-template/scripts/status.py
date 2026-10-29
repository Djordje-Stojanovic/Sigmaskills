"""status.py - the one command the host's stop check reads. Prints one line.

LOOP FINISHED ...  only when: an instance was rented (state/instance.json), it no longer exists on
Vast (the owner destroyed it), and REPORT.md exists. Anything else prints LOOP RUNNING ...
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VASTAI = os.environ.get("VASTAI") or shutil.which("vastai") or "vastai"  # set VASTAI when the CLI is not on PATH


def vast_instances():
    # No --api-key: the CLI's stored login carries the 2FA session; an explicit key bypasses it and gets 401.
    out = subprocess.run([VASTAI, "show", "instances", "--raw"], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:200])
    data = json.loads(out.stdout or "null")
    if not isinstance(data, list):  # an error object is never proof that the box is gone
        raise RuntimeError(str(data)[:200])
    return {str(i["id"]) for i in data}


def main():
    passes = 0
    results = os.path.join(ROOT, "results.tsv")
    if os.path.exists(results):
        passes = max(0, len(open(results, encoding="utf-8").read().splitlines()) - 1)
    inst_file = os.path.join(ROOT, "state", "instance.json")
    if not os.path.exists(inst_file):  # during SETUP the instance file still lives in state.tmp/
        inst_file = os.path.join(ROOT, "state.tmp", "instance.json")
    if not os.path.exists(inst_file):
        print(f"LOOP RUNNING: no instance rented yet, {passes} passes")
        return
    inst = str(json.load(open(inst_file, encoding="utf-8"))["id"])
    try:
        alive = inst in vast_instances()
    except Exception as e:
        need = " NEED VAST EMAIL CODE (2FA session expired)." if "Two Factor" in str(e) else ""
        print(f"LOOP RUNNING: cannot reach Vast ({str(e)[:120]}), instance {inst}, {passes} passes.{need}")
        return
    report = os.path.exists(os.path.join(ROOT, "REPORT.md"))
    if not alive and report:
        print(f"LOOP FINISHED: instance {inst} destroyed by owner, REPORT.md written, {passes} passes")
    elif not alive:
        print(f"LOOP RUNNING: instance {inst} is gone, REPORT.md not written yet, {passes} passes")
    else:
        print(f"LOOP RUNNING: instance {inst} alive, {passes} passes")


if __name__ == "__main__":
    main()
    sys.exit(0)
