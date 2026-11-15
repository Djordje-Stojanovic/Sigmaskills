"""invariants.py - stage 0. Diff a candidate serve.sh against the frozen baseline for locked settings.

  python scripts/bench/invariants.py candidate/serve.sh runs/<n>   -> runs/<n>/invariants.json
"""
import json, os, re, shlex, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "scripts", "bench", "baseline_serve.sh")

LOCKED_FLAGS = ["--served-model-name", "--max-model-len", "--max-num-seqs", "--kv-cache-dtype", "--quantization",
                "--dtype", "--gpu-memory-utilization", "--override-generation-config", "--default-chat-template-kwargs",
                "--reasoning-parser", "--tool-call-parser", "--tokenizer", "--revision", "--chat-template",
                "--hf-overrides"]
LOCKED_ENV = ["VLLM_MXFP8_LM_HEAD", "VLLM_B12X_MOE_FP4_FORCE_A16", "VLLM_B12X_MOE_FP4_LAYER_MAX_INPUT_SCALE"]
FORBIDDEN_ENV = {"B12X_DYNAMIC_DETERMINISTIC_OUTPUT": "0"}
OWNER_OK_DRAFTERS = set()  # draft models the owner approved in writing (path on the box), e.g. {"/root/models/x"}
# kv-cache-dtype-skip-layers is allowed only for the MTP draft layer (owner approved 2026-10-22)
ALLOWED_SKIP_LAYERS = {"48"}


def parse(path):
    text = open(path, encoding="utf-8").read().replace("\\\n", " ")
    env = dict(re.findall(r"^export (\w+)=(\S*)", text, flags=re.M))
    m = re.search(r"vllm serve (.*)$", text, flags=re.M | re.S)
    toks = shlex.split(m.group(1)) if m else []
    model = toks[0] if toks else None
    flags, i = {}, 1
    while i < len(toks):
        t = toks[i]
        if t.startswith("--"):
            k, _, v = t.partition("=")
            if not v and i + 1 < len(toks) and not toks[i + 1].startswith("--"):
                v = toks[i + 1]
                i += 1
            flags[k] = v or True
        i += 1
    return model, env, flags


def check(cand_path):
    bm, be, bf = parse(BASE)
    cm, ce, cf = parse(cand_path)
    problems = []
    if cm != bm:
        problems.append(f"model path {cm} != {bm}")
    for f in LOCKED_FLAGS:
        if bf.get(f) != cf.get(f):
            problems.append(f"{f}: {cf.get(f)} != baseline {bf.get(f)}")
    for e in LOCKED_ENV:
        if be.get(e) != ce.get(e):
            problems.append(f"env {e}: {ce.get(e)} != baseline {be.get(e)}")
    for e, bad in FORBIDDEN_ENV.items():
        if ce.get(e) == bad:
            problems.append(f"env {e}={bad} is forbidden")
    skip = cf.get("--kv-cache-dtype-skip-layers")
    if skip and set(str(skip).split(",")) - ALLOWED_SKIP_LAYERS:
        problems.append(f"--kv-cache-dtype-skip-layers {skip}: only the MTP layer {ALLOWED_SKIP_LAYERS} may skip fp8")
    spec = cf.get("--speculative-config")
    if spec:
        sc = json.loads(spec)
        # Owner OK 2026-10-24 02:17: one named drafter only (verified by the target, output lossless).
        owner_ok = sc.get("method") == "dflash" and sc.get("model") in OWNER_OK_DRAFTERS
        if sc.get("method") not in ("mtp", None) and not owner_ok:
            problems.append(f"speculative method {sc.get('method')} (new drafter model = model change)")
        if str(sc.get("rejection_sample_method", "")).lower() in ("synthetic", "fly"):
            problems.append("lossy rejection sampler")
    diff = {"flags": {k: (bf.get(k), cf.get(k)) for k in set(bf) | set(cf) if bf.get(k) != cf.get(k)},
            "env": {k: (be.get(k), ce.get(k)) for k in set(be) | set(ce) if be.get(k) != ce.get(k)}}
    return {"ok": not problems, "problems": problems, "diff_vs_baseline": diff}


if __name__ == "__main__":
    res = check(sys.argv[1])
    os.makedirs(os.path.join(ROOT, sys.argv[2]), exist_ok=True)
    json.dump(res, open(os.path.join(ROOT, sys.argv[2], "invariants.json"), "w", encoding="utf-8"), indent=1)
    print("INVARIANTS", "OK" if res["ok"] else "BROKEN: " + "; ".join(res["problems"]))
