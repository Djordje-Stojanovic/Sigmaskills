"""status.py - the one status line the host's stop check reads, and the loop's own speed.

LOOP FINISHED ... only when REPORT.md exists and the target is gone: the rented instance (state/instance.json) no
longer exists, or, with no rented instance, the owner wrote a STOP file. Anything else prints LOOP RUNNING ...
The second half measures the loop: minutes per idea, minutes from a KEEP to its new champion, and the share of a
pass that measures the score. A share under half means: fix the loop before the next idea.
"""
import csv, json, os, shutil, statistics, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VASTAI = os.environ.get("VASTAI") or shutil.which("vastai") or "vastai"  # set VASTAI when the CLI is not on PATH
SETUP = {"BASELINE", "AA", "RECON"}


def vast_instances():
    # No --api-key: the CLI's stored login carries the 2FA session; an explicit key bypasses it and gets 401.
    out = subprocess.run([VASTAI, "show", "instances", "--raw"], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:200])
    data = json.loads(out.stdout or "null")
    if not isinstance(data, list):  # an error object is never proof that the box is gone
        raise RuntimeError(str(data)[:200])
    return {str(i["id"]) for i in data}


def loop_speed(root=ROOT):
    """(minutes per idea, minutes from the last KEEP to its champion, median score share of the last 5 passes)."""
    rows = []
    path = os.path.join(root, "results.tsv")
    if os.path.exists(path):
        rows = [r for r in csv.DictReader(open(path, encoding="utf-8"), delimiter="\t") if r["verdict"] not in SETUP]
    minutes = sum(float(r["minutes"]) for r in rows if r.get("minutes"))
    ideas = {r["idea_id"] for r in rows}
    champ = os.path.join(root, "state", "champion.json")
    hist = json.load(open(champ, encoding="utf-8")).get("history", []) if os.path.exists(champ) else []
    shares = [float(r["score_share"]) for r in rows[-5:] if r.get("score_share")]
    return (minutes / len(ideas) if ideas else None, hist[-1]["keep_to_champion_min"] if hist else None,
            statistics.median(shares) if shares else None)


def speed_text(root=ROOT):
    per_idea, to_champ, share = loop_speed(root)
    f = lambda x, unit: "n/a" if x is None else f"{x:.0f} {unit}"
    text = (f"loop: {f(per_idea, 'min')} per idea, {f(to_champ, 'min')} from a KEEP to its champion, "
            f"{'n/a' if share is None else f'{share:.0%}'} of a pass measures the score")
    return text + (" - UNDER HALF: fix the loop before the next idea" if share is not None and share < 0.5 else "")


def main():
    passes = 0
    results = os.path.join(ROOT, "results.tsv")
    if os.path.exists(results):
        passes = max(0, len(open(results, encoding="utf-8").read().splitlines()) - 1)
    report = os.path.exists(os.path.join(ROOT, "REPORT.md"))
    tail = f"{passes} passes | {speed_text()}"
    inst_file = os.path.join(ROOT, "state", "instance.json")
    if not os.path.exists(inst_file):  # during SETUP the instance file still lives in state.tmp/
        inst_file = os.path.join(ROOT, "state.tmp", "instance.json")
    if not os.path.exists(inst_file):
        stop = os.path.exists(os.path.join(ROOT, "STOP"))
        print(f"LOOP FINISHED: owner wrote STOP, REPORT.md written, {tail}" if stop and report else
              f"LOOP RUNNING: no rented instance{', STOP seen, REPORT.md not written yet' if stop else ''}, {tail}")
        return
    inst = str(json.load(open(inst_file, encoding="utf-8"))["id"])
    try:
        alive = inst in vast_instances()
    except Exception as e:
        need = " NEED VAST EMAIL CODE (2FA session expired)." if "Two Factor" in str(e) else ""
        print(f"LOOP RUNNING: cannot reach Vast ({str(e)[:120]}), instance {inst}.{need} {tail}")
        return
    if not alive and report:
        print(f"LOOP FINISHED: instance {inst} destroyed by owner, REPORT.md written, {tail}")
    elif not alive:
        print(f"LOOP RUNNING: instance {inst} is gone, REPORT.md not written yet, {tail}")
    else:
        print(f"LOOP RUNNING: instance {inst} alive, {tail}")


if __name__ == "__main__":
    main()
    sys.exit(0)
