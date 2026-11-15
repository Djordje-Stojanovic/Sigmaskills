"""common.py - shared client helpers for the bench scripts (runs on the Vast box against localhost:8000)."""
import json, os, time, uuid

import requests

BASE = os.environ.get("BENCH_BASE", "http://localhost:8000")
MODEL = os.environ.get("BENCH_MODEL", "qwen")  # the --served-model-name of your server; set BENCH_MODEL in run_experiment.sh
HERE = os.path.dirname(os.path.abspath(__file__))
SESSION = requests.Session()


def salt():
    """A unique first line defeats the prefix cache without changing the task."""
    return f"[run {uuid.uuid4().hex[:12]}]\n"


REAL_MAX_TOKENS = 65536  # the owner's client output limit (evaluator v2)


def chat_stream(messages, max_tokens=REAL_MAX_TOKENS, temperature=None, tools=None, extra=None, timeout=900,
                effort=None, stop_after=None, seed=None):
    """Streamed chat completion. Returns timing and token counts measured from the stream.

    Evaluator v2 defaults match real use: server sampling (T=1.0, top_p 0.95, top_k 20), thinking on,
    max_tokens 65536. `effort` sets reasoning_effort (low | medium | xhigh). `stop_after` closes the stream
    once that many completion tokens arrived (the request is cancelled server-side), so long real-shaped
    requests fit the time budget. ttft = time to the first generated token (reasoning or content);
    decode_tps = tokens after the first one divided by the time after the first one.
    """
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True, "continuous_usage_stats": True}}
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    if effort:
        body["reasoning_effort"] = effort
        body["chat_template_kwargs"] = {"reasoning_effort": effort}
    if tools:
        body["tools"] = tools
    if extra:
        body.update(extra)
    t0 = time.perf_counter()
    t_first = t_last = None
    usage, text, reasoning, tool_args, finish = {}, [], [], {}, None
    with SESSION.post(f"{BASE}/v1/chat/completions", json=body, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        for raw in r.iter_lines():
            if not raw or not raw.startswith(b"data: "):
                continue
            data = raw[6:]
            if data == b"[DONE]":
                break
            ev = json.loads(data)
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                got = d.get("content") or d.get("reasoning_content") or d.get("reasoning") or d.get("tool_calls")
                if got:
                    now = time.perf_counter()
                    t_first = t_first or now
                    t_last = now
                if d.get("content"):
                    text.append(d["content"])
                if d.get("reasoning_content") or d.get("reasoning"):
                    reasoning.append(d.get("reasoning_content") or d.get("reasoning"))
                for tc in d.get("tool_calls") or []:
                    slot = tool_args.setdefault(tc.get("index", 0), {"name": "", "arguments": ""})
                    fn = tc.get("function") or {}
                    slot["name"] += fn.get("name") or ""
                    slot["arguments"] += fn.get("arguments") or ""
                finish = ch.get("finish_reason") or finish
            # stop only after this event's tokens were timed, so ttft exists even for stop_after=1
            if stop_after and t_first and usage.get("completion_tokens", 0) >= stop_after:
                finish = "client_stop"
                break
    t_end = time.perf_counter()
    n_out = usage.get("completion_tokens", 0)
    decode_s = (t_last - t_first) if (t_first and t_last) else 0.0
    return {
        "ttft_s": (t_first - t0) if t_first else None,
        "wall_s": t_end - t0,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": n_out,
        "decode_tps": (n_out - 1) / decode_s if decode_s > 0 and n_out > 1 else None,
        "text": "".join(text),
        "reasoning": "".join(reasoning),
        "tool_calls": [tool_args[k] for k in sorted(tool_args)],
        "finish_reason": finish,
    }


def completion_logprobs(prompt, max_tokens=1, prompt_logprobs=5, logprobs=5, timeout=900):
    """Raw /v1/completions with prompt logprobs (teacher-forced scoring of every prompt token)."""
    body = {"model": MODEL, "prompt": prompt, "max_tokens": max_tokens, "temperature": 0.0,
            "logprobs": logprobs, "prompt_logprobs": prompt_logprobs}
    r = SESSION.post(f"{BASE}/v1/completions", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


def metrics_snapshot():
    """Spec-decode counters from /metrics (for MTP acceptance)."""
    out = {}
    try:
        for line in SESSION.get(f"{BASE}/metrics", timeout=30).text.splitlines():
            if line.startswith("vllm:spec_decode_num_") and "_total{" in line and "per_pos" not in line:
                name = line.split("{")[0].replace("vllm:spec_decode_", "")
                out[name] = out.get(name, 0.0) + float(line.rsplit(" ", 1)[1])
            if line.startswith("vllm:prefix_cache_") and "_total{" in line:
                name = line.split("{")[0].replace("vllm:", "")
                out[name] = out.get(name, 0.0) + float(line.rsplit(" ", 1)[1])
    except Exception as e:  # metrics are diagnostic only
        out["error"] = str(e)
    return out


def long_document(n_chars, seed_dirs=("/usr/local/lib/python3.12/dist-packages/vllm",)):
    """Deterministic long text built from vLLM's own source files (same text on every run)."""
    parts, total = [], 0
    for d in seed_dirs:
        for root, _, files in sorted(os.walk(d)):
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                try:
                    s = open(os.path.join(root, f), encoding="utf-8").read()
                except Exception:
                    continue
                parts.append(f"\n# file: {f}\n{s}")
                total += len(s)
                if total >= n_chars:
                    return "".join(parts)[:n_chars]
    return "".join(parts)[:n_chars]


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
