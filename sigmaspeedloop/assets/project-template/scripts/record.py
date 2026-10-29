"""record.py - append one results.tsv row built from a run's raw files (no hand-typed numbers).

  python scripts/record.py --run runs/0005 --pass 5 --idea mtp-prob-draft --category mtp --work CONTENT \
      --minutes 24.5 --desc "what changed; hypothesis + evidence; what happened; conclusion" [--verdict KEEP]

The verdict defaults to runs/<n>/verdict.json. Cost = minutes x the instance $/h.
"""
import argparse, datetime, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "bench"))
from verdict import extract  # noqa: E402


def clean(s):
    return str(s).replace("\t", " ").replace("\r", " ").replace("\n", "; ")


def fmt(x, nd=2):
    return "" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def main():
    ap = argparse.ArgumentParser()
    for a in ("run", "pass", "idea", "category", "work", "desc"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--minutes", type=float, required=True)
    ap.add_argument("--verdict")
    ap.add_argument("--parent", default="")
    a = ap.parse_args()
    run = a.run.rstrip("/\\")
    x = extract(run)
    v = json.load(open(os.path.join(ROOT, run, "verdict.json"))) if os.path.exists(os.path.join(ROOT, run, "verdict.json")) else {}
    verdict = a.verdict or v.get("verdict")
    if not verdict:
        sys.exit("no verdict given and no verdict.json")
    inst = os.path.join(ROOT, "state", "instance.json")
    if not os.path.exists(inst):
        inst = os.path.join(ROOT, "state.tmp", "instance.json")
    dph = json.load(open(inst, encoding="utf-8-sig"))["dph"]
    g, m = x.get("gate") or {}, x.get("meta") or {}
    hdr = open(os.path.join(ROOT, "results.tsv"), encoding="utf-8").readline().rstrip("\n").split("\t")
    row = {
        "pass": a.__dict__["pass"], "utc": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "parent": a.parent, "idea_id": a.idea, "category": a.category, "work_type": a.work,
        "image": os.environ.get("SPEEDLOOP_IMAGE_LABEL", "image"), "verdict": verdict, "score": fmt(v.get("score"), 4),
        "decode_tps": fmt(x.get("decode_greedy")), "decode_long_tps": fmt(x.get("decode_sampled")),
        "prefill_tps_64k": fmt(x.get("prefill_64k"), 1), "ttft_128k_s": fmt(x.get("ttft_128k")),
        "replay_wall_s": fmt(x.get("replay_wall_s"), 1), "replay_ttft_p50_s": fmt(x.get("replay_ttft_p50")),
        "c3_tps": fmt(x.get("c3_tps")), "mtp_accept": fmt(x.get("mtp_accept"), 3), "kv_tokens": fmt(m.get("kv_tokens")),
        "start_s": fmt(m.get("start_s")), "low_mem_gib": fmt(m.get("low_mem_gib")),
        "gate_top1": fmt(g.get("tf_top1"), 4), "gate_dlogp": fmt(g.get("tf_dlp"), 4),
        "gate_reliability": f"{g['reliability_ok']}/{g['reliability_total']}" if g else "",
        "minutes": fmt(a.minutes, 1), "cost_usd": fmt(a.minutes / 60 * dph, 3), "description": clean(a.desc),
    }
    with open(os.path.join(ROOT, "results.tsv"), "a", encoding="utf-8") as fh:
        fh.write("\t".join(row[h] for h in hdr) + "\n")
    print("recorded", row["pass"], row["idea_id"], row["verdict"], row["score"])


if __name__ == "__main__":
    main()
