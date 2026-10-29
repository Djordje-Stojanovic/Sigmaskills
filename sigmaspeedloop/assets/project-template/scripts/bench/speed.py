"""speed.py - stage 2 speed probes, evaluator v2: the owner's real settings, fixed.

  python3 speed.py --out FILE

Real settings in every request: thinking on, server sampling (T=1.0, top_p 0.95, top_k 20) with fixed seeds,
max_tokens 65536, reasoning effort low / medium (daily) and xhigh (sometimes). Requests stop client-side
after a fixed token count so the probes fit ~10 minutes; the server sees the real request shape.

2a short decode: Albond's 5 prompts at effort low and medium, 512 tokens each (chat, Open WebUI)
2b long thinking: 64k-token context, effort xhigh, 3072 tokens of thinking (decode deep in a long turn)
2c prefill: unique long prompts at 16k / 64k / 128k tokens, 1 output token (prompt reading only)
2d agent replay (v6): 3 real agent sessions at once (efforts medium / low / xhigh), 4 consecutive turns each
   1024 tokens per turn, prefix cache ON
2e parallel: 3 concurrent requests, effort low, 512 tokens each, aggregate tok/s (v7: also 2 concurrent)
2f chat (v6): normal conversation at ~100k tokens, effort low, model answers fed back, 5 rounds
Every request outside 2d starts with a unique salt line, so the prefix cache cannot help.
"""
import argparse, glob, json, math, os, statistics, threading, time

from common import HERE, chat_stream, long_document, metrics_snapshot, salt, write_json

ALBOND = [
    ("qa", "What are the main differences between TCP and UDP? Be concise."),
    ("code", "Write a Python function that implements binary search on a sorted list. Include type hints and docstring."),
    ("json", "Generate a JSON array of 10 fictional employees with fields: name, age, department, salary, email, "
             "skills (array of 3). Output ONLY valid JSON, no explanation."),
    ("math", "What is 7823 * 4519? Show only the answer."),
    ("longcode", "Write a complete Python implementation of a red-black tree with insert, delete, search, and "
                 "in-order traversal. Include all rotation methods."),
]
SHORT_EFFORTS = ("low", "medium")
SHORT_TOKENS = 512
LONG_CONTEXT_CHARS = int(64_000 * 3.6)
LONG_TOKENS = 3072
PREFILL_CHARS = {"16k": 16_000 * 3.6, "64k": 64_000 * 3.6, "128k": 128_000 * 3.6}
PREFILL_REPS = {"16k": 2, "64k": 1, "128k": 1}
REPLAY_EFFORTS = ("medium", "low", "xhigh")       # trace1, trace2, trace3
REPLAY_TURNS = 4                                 # v6: trace["warm_cuts"], 4 consecutive turns
REPLAY_TOKENS = 1024                             # v8: every turn writes exactly this many tokens
PARALLEL_TOKENS = 512


def geomean(xs):
    xs = [x for x in xs if x]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def short_decode_probe():
    chat_stream([{"role": "user", "content": salt() + "Say hello."}], effort="low", stop_after=32, seed=1)  # warm-up
    rows = []
    for e_i, effort in enumerate(SHORT_EFFORTS):
        for p_i, (name, prompt) in enumerate(ALBOND):
            r = chat_stream([{"role": "user", "content": salt() + prompt}], effort=effort, stop_after=SHORT_TOKENS,
                            seed=100 + 10 * e_i + p_i)
            rows.append({"prompt": name, "effort": effort, "decode_tps": r["decode_tps"],
                         "tokens": r["completion_tokens"], "ttft_s": r["ttft_s"], "finish": r["finish_reason"]})
    return {"rows": rows, "decode_tps_geo": geomean([r["decode_tps"] for r in rows])}


def long_thinking_probe():
    doc = long_document(LONG_CONTEXT_CHARS)
    r = chat_stream([{"role": "user", "content": salt() + doc + "\n\nReview the code above: find the three most "
                     "likely bugs or design problems and propose fixes."}], effort="xhigh", stop_after=LONG_TOKENS,
                    seed=7)
    return {k: r[k] for k in ("ttft_s", "prompt_tokens", "completion_tokens", "decode_tps", "finish_reason")}


def prefill_probe():
    out = {}
    for label, chars in PREFILL_CHARS.items():
        doc = long_document(int(chars))
        rows = []
        for _ in range(PREFILL_REPS[label]):
            r = chat_stream([{"role": "user", "content": salt() + doc + "\n\nName one function defined above."}],
                            effort="low", stop_after=1, seed=3)
            rows.append({"ttft_s": r["ttft_s"], "prompt_tokens": r["prompt_tokens"],
                         "prefill_tps": r["prompt_tokens"] / r["ttft_s"] if r["ttft_s"] else None})
        out[label] = {"runs": rows, "prefill_tps": statistics.median([x["prefill_tps"] for x in rows]),
                      "ttft_s": statistics.median([x["ttft_s"] for x in rows])}
    out["prefill_tps_geo"] = geomean([out[k]["prefill_tps"] for k in PREFILL_CHARS])
    return out


def replay_probe():
    traces = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(HERE, "replay", "*.json")))]
    rid = salt()  # one salt per run for all traces: turns of one session still share their prefix
    results = [[] for _ in traces]
    # v6: 4 consecutive real turns per trace (turn 1 cold, 2-4 warm, like an agent client). All cold turns finish
    # before any warm turn starts, so the warm hit rate and warm TTFT are measured on their own.
    cold_done = threading.Barrier(len(traces) + 1)
    warm_go = threading.Barrier(len(traces) + 1)

    errors = []

    def run(i, tr):
        try:
            msgs = [dict(m) for m in tr["messages"]]
            msgs[0]["content"] = rid + msgs[0]["content"]
            for t_i, cut in enumerate(tr["warm_cuts"]):
                if t_i == 1:
                    cold_done.wait()
                    warm_go.wait()
                # v8: fixed work per turn (min_tokens = max_tokens), so wall time no longer follows the sampled answer length
                r = chat_stream(msgs[:cut], tools=tr["tools"], effort=REPLAY_EFFORTS[i], max_tokens=REPLAY_TOKENS,
                                extra={"min_tokens": REPLAY_TOKENS, "ignore_eos": True},
                                seed=1000 + 10 * i + t_i)
                results[i].append({k: r[k] for k in ("ttft_s", "wall_s", "prompt_tokens", "completion_tokens", "decode_tps")})
        except BaseException as e:  # a failed request must not leave the other threads at a barrier for ever
            errors.append(e)
            cold_done.abort()
            warm_go.abort()

    before = metrics_snapshot()
    t0 = time.perf_counter()
    threads = [threading.Thread(target=run, args=(i, t)) for i, t in enumerate(traces)]
    for t in threads:
        t.start()
    try:
        cold_done.wait()
        mid = metrics_snapshot()
        warm_go.wait()
    except threading.BrokenBarrierError:
        pass
    for t in threads:
        t.join()
    if errors:
        raise errors[0]
    wall = time.perf_counter() - t0
    after = metrics_snapshot()

    def rate(a, b):
        q = b.get("prefix_cache_queries_total", 0) - a.get("prefix_cache_queries_total", 0)
        return (b.get("prefix_cache_hits_total", 0) - a.get("prefix_cache_hits_total", 0)) / q if q else None

    ttfts = [x["ttft_s"] for rs in results for x in rs if x["ttft_s"]]
    warm = [x["ttft_s"] for rs in results for x in rs[1:] if x["ttft_s"]]
    return {"version": 8, "wall_s": wall, "warm_ttft_sum_s": sum(warm), "turns": results, "efforts": REPLAY_EFFORTS,
            "ttft_p50_s": statistics.median(ttfts), "ttft_p90_s": sorted(ttfts)[int(0.9 * (len(ttfts) - 1))],
            "cold_ttft_p50_s": statistics.median([rs[0]["ttft_s"] for rs in results if rs[0]["ttft_s"]]),
            "warm_ttft_p50_s": statistics.median(warm) if warm else None, "warm_ttft_max_s": max(warm) if warm else None,
            "decode_tps_median": statistics.median([x["decode_tps"] for rs in results for x in rs if x["decode_tps"]]),
            "prefix_hit_rate": rate(before, after), "warm_hit_rate": rate(mid, after)}


CHAT_QUESTIONS = ("Summarize what we did so far in 3 short bullet points.",
                  "What is the riskiest part of the last change, in two sentences?",
                  "Which file would you look at next, and why? One short paragraph.",
                  "Name one test that would catch a regression here.")
CHAT_STOP = 4096                                 # safety cap only; effort low answers end on their own


def chat_probe():
    """2f (v6) normal chat at ~100k tokens, effort low, 1 stream: the model's own answer (with its thinking)
    goes back into the history, then a short question. Owner: every next turn should hit ~95% cache."""
    tr = json.load(open(os.path.join(HERE, "replay", "trace3.json"), encoding="utf-8"))
    msgs = [dict(m) for m in tr["messages"][:tr["warm_cuts"][0]]]
    msgs[0]["content"] = salt() + msgs[0]["content"]
    rounds, t0 = [], time.perf_counter()
    for q_i in range(len(CHAT_QUESTIONS) + 1):
        a = metrics_snapshot()
        r = chat_stream(msgs, tools=tr["tools"], effort="low", stop_after=CHAT_STOP, seed=2000 + q_i,
                        extra={"tool_choice": "none"})
        b = metrics_snapshot()
        q = b.get("prefix_cache_queries_total", 0) - a.get("prefix_cache_queries_total", 0)
        h = b.get("prefix_cache_hits_total", 0) - a.get("prefix_cache_hits_total", 0)
        rounds.append({k: r[k] for k in ("ttft_s", "wall_s", "prompt_tokens", "completion_tokens", "decode_tps",
                                          "finish_reason")} | {"hit_rate": h / q if q else None})
        msgs.append({"role": "assistant", "content": r["text"], "reasoning_content": r["reasoning"]})
        if q_i < len(CHAT_QUESTIONS):
            msgs.append({"role": "user", "content": CHAT_QUESTIONS[q_i]})
    warm = rounds[1:]
    return {"wall_s": time.perf_counter() - t0, "rounds": rounds, "cold_ttft_s": rounds[0]["ttft_s"],
            "warm_ttft_p50_s": statistics.median([x["ttft_s"] for x in warm if x["ttft_s"]]),
            "warm_hit_rate_min": min(x["hit_rate"] or 0 for x in warm),
            "warm_hit_rate_mean": statistics.mean([x["hit_rate"] or 0 for x in warm])}


def parallel_probe(n=3):
    res = [None] * n

    def one(i):
        res[i] = chat_stream([{"role": "user", "content": salt() + ALBOND[1][1]}], effort="low",
                             stop_after=PARALLEL_TOKENS, seed=500 + i)

    t0 = time.perf_counter()
    ts = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    wall = time.perf_counter() - t0
    tokens = sum(r["completion_tokens"] for r in res)
    return {"wall_s": wall, "tokens": tokens, "aggregate_tps": tokens / wall,
            "per_stream_tps": [r["decode_tps"] for r in res]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    m0 = metrics_snapshot()
    res = {"version": 3, "short": short_decode_probe(), "long": long_thinking_probe()}
    m1 = metrics_snapshot()
    res["prefill"] = prefill_probe()
    res["parallel"] = parallel_probe()
    res["parallel2"] = parallel_probe(2)  # v7: 2 agents (owner priority 2)
    res["replay"] = replay_probe()
    res["chat"] = chat_probe()
    drafted = m1.get("num_draft_tokens_total", 0) - m0.get("num_draft_tokens_total", 0)
    accepted = m1.get("num_accepted_tokens_total", 0) - m0.get("num_accepted_tokens_total", 0)
    res["mtp_accept_decode_probe"] = accepted / drafted if drafted else None
    res["elapsed_s"] = time.time() - t0
    write_json(a.out, res)
    print(json.dumps({"short_tps": res["short"]["decode_tps_geo"], "long_tps": res["long"]["decode_tps"],
                      "prefill_tps_geo": res["prefill"]["prefill_tps_geo"], "c3_tps": res["parallel"]["aggregate_tps"], "c2_tps": res["parallel2"]["aggregate_tps"],
                      "replay_wall_s": res["replay"]["wall_s"],
                      "replay_warm_hit": res["replay"]["warm_hit_rate"], "chat_wall_s": res["chat"]["wall_s"],
                      "chat_warm_hit_min": res["chat"]["warm_hit_rate_min"], "mtp_accept": res["mtp_accept_decode_probe"],
                      "elapsed_s": res["elapsed_s"]}))
