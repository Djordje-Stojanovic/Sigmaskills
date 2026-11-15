"""record.py - append one results.tsv row built from a run's raw files (no hand-typed numbers).

  python scripts/record.py --run runs/0005 --pass 5 --idea prefill-chunk --category scheduler --work CODE \
      --part prefill --desc "what changed; hypothesis + evidence; what happened; what it rules out" [--verdict KEEP]

The verdict comes from runs/<n>/verdict.json, the minutes and the score share from raw/meta.json (seconds per
stage), the cost from state/instance.json "dph" or project.json "cost_per_hour". CLIMB_WHO names the finder.
"""
import argparse, datetime, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def clean(s):
    return str(s).replace("\t", " ").replace("\r", " ").replace("\n", "; ")


def fmt(x, nd=4):
    return "" if x is None else (f"{x:.{nd}g}" if isinstance(x, float) else str(x))


def jload(path):
    return json.load(open(path, encoding="utf-8-sig")) if os.path.exists(path) else {}


def main():
    ap = argparse.ArgumentParser()
    for a in ("run", "pass", "idea", "category", "work", "desc"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--part", default="", help="the part of the profile this idea attacks")
    ap.add_argument("--verdict")
    ap.add_argument("--parent", default="")
    a = ap.parse_args()
    run = os.path.join(ROOT, a.run.rstrip("/\\"))
    v, meta, sc = jload(os.path.join(run, "verdict.json")), jload(os.path.join(run, "raw", "meta.json")), \
        jload(os.path.join(run, "raw", "score.json"))
    q = os.path.join(run, "raw", "quality.json")
    verdict = a.verdict or v.get("verdict")
    if not verdict:
        sys.exit("no verdict given and no verdict.json")
    stages = meta.get("stage_s") or {}
    total = sum(stages.values())
    proj = jload(os.path.join(ROOT, "project.json"))
    inst = jload(os.path.join(ROOT, "state", "instance.json")) or jload(os.path.join(ROOT, "state.tmp", "instance.json"))
    per_hour = inst.get("dph", proj.get("cost_per_hour", 0))
    quality = "" if not os.path.exists(q) else ("ok" if jload(q).get("ok") else "fail: " + "; ".join(jload(q).get("fails", [])))
    row = {
        "pass": a.__dict__["pass"], "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "parent": a.parent, "idea_id": a.idea, "category": a.category, "work_type": a.work, "part": a.part,
        "who": os.environ.get("CLIMB_WHO", ""), "machine": proj.get("machine", ""), "verdict": verdict,
        "vs_champion": fmt(v.get("vs_champion")), "vs_start": fmt(v.get("vs_start")),
        "probes": " ".join(f"{k}={fmt(x)}" for k, x in sorted((sc.get("probes") or {}).items()) if x is not None),
        "quality": quality, "minutes": fmt(total / 60, 3) if total else "",
        "score_share": fmt(stages.get("score", 0) / total, 2) if total else "",
        "cost_usd": fmt(total / 3600 * per_hour, 3) if total else "", "description": clean(a.desc),
    }
    hdr = open(os.path.join(ROOT, "results.tsv"), encoding="utf-8").readline().rstrip("\n").split("\t")
    with open(os.path.join(ROOT, "results.tsv"), "a", encoding="utf-8") as fh:
        fh.write("\t".join(clean(row[h]) for h in hdr) + "\n")
    print("recorded", row["pass"], row["idea_id"], row["verdict"], row["vs_champion"])


if __name__ == "__main__":
    main()
