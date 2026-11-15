"""gate.py - stage 1 quality gate (no LLM judge). Runs against the live server on the box.

  python3 gate.py --record REFDIR            baseline: save reference logprobs and generations
  python3 gate.py --ref REFDIR --out FILE    any run: compare against the references

1a teacher-forced fidelity (~60k positions): score fixed texts with prompt_logprobs; compare per-token logprobs.
1b decode fidelity: 24 prompts, greedy 512 tokens at effort low and medium, top-5 logprobs; compare the
   common prefix with the reference.
1c reliability (40 checks, 4 at a time): tool calls parse with the right tool and arguments, JSON parses,
   needle found at 64k and 128k, no empty or looping output.
Gate v3 (2026-10-23, owner: the v2 gate was too short). Gate v4: 1c keeps only the needles; tool calls and JSON moved to ToolEvalBench (74 scenarios).
"""
import argparse, glob, json, math, os, re, sys

from common import HERE, chat_stream, completion_logprobs, long_document, write_json, SESSION, BASE, MODEL

REAL = {"effort": "low"}  # evaluator v2: thinking always on, the owner's daily effort
TF_PROMPT_LOGPROBS = 2    # top-2 + the actual token per position keeps 60k positions small


def _replay_text(path, start_frac, n_chars):
    msgs = json.load(open(path, encoding="utf-8"))["messages"]
    s = "\n".join(f"<{m['role']}>\n{m.get('content') or json.dumps(m.get('tool_calls', ''))}" for m in msgs)
    a = int(len(s) * start_frac)
    return s[a:a + n_chars]


_TRACES = sorted(glob.glob(os.path.join(HERE, "replay", "*.json")))
TF_REPLAY = [_replay_text(p, f, 40_000) for p in _TRACES for f in (0.2, 0.7)]  # real agent text

TF_TEXTS = [  # raw texts, scored token by token (teacher forced)
    long_document(6000),
    long_document(60000)[-6000:],
    "The French Revolution began in 1789 and transformed the political landscape of Europe. " * 3
    + "It abolished feudal privileges, proclaimed the rights of man, and ended the absolute monarchy. "
      "Historians still debate whether economic hardship or Enlightenment ideas mattered more.",
    "def binary_search(items: list[int], target: int) -> int:\n    lo, hi = 0, len(items) - 1\n"
    "    while lo <= hi:\n        mid = (lo + hi) // 2\n        if items[mid] == target:\n            return mid\n"
    "        if items[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n",
    '{"employees": [{"name": "Ana", "age": 31, "department": "R&D", "skills": ["rust", "sql", "go"]},'
    ' {"name": "Marko", "age": 45, "department": "Sales", "skills": ["crm", "excel", "german"]}]}',
    "Die Spannung stieg, als der Zug langsam in den Bahnhof einfuhr. Niemand wusste, wer aussteigen würde. "
    "Ona je čekala na peronu, držeći pismo koje nikada nije poslala.",
    "Solve: 7823 * 4519. First, 7823 * 4500 = 35,203,500. Then 7823 * 19 = 148,637. "
    "Adding gives 35,352,137. So the answer is 35,352,137.",
    long_document(400000)[-24000:],
] + TF_REPLAY

DECODE_PROMPTS = [  # chat prompts, greedy, thinking on; first half effort low, second half medium
    "What are the main differences between TCP and UDP? Be concise.",
    "Write a Python function that implements binary search on a sorted list. Include type hints and docstring.",
    "Generate a JSON array of 3 fictional employees with fields: name, age, department. Output ONLY valid JSON.",
    "What is 7823 * 4519? Show only the answer.",
    "Explain in two sentences why the sky is blue.",
    "Write a bash one-liner that counts lines in all .py files under the current directory.",
    "Translate to German: 'The meeting is moved to Thursday because the server migration is late.'",
    "List three risks of running a database migration on a Friday afternoon.",
    "Write a haiku about a GPU that never sleeps.",
    "Refactor this to a list comprehension: out = []\nfor x in xs:\n    if x % 2 == 0:\n        out.append(x * x)",
    "What does HTTP status 429 mean and how should a client react?",
    "Summarize the idea of speculative decoding in LLM inference in three bullet points.",
    "Write a SQL query that returns the top 5 customers by total order value in 2025.",
    "Explain what a race condition is and show a tiny Python example that has one.",
    "Write a PowerShell command that lists the 10 largest files under C:\\AI recursively.",
    "Erkläre in drei Sätzen, wie ein Transformer-Modell Text verarbeitet.",
    "Objasni ukratko razliku između TCP i UDP protokola.",
    "Given a list of intervals, write a Python function that merges overlapping ones.",
    "What is the time complexity of building a binary heap from n elements, and why?",
    "Write a regex that matches ISO dates like 2026-10-23 and explain each part.",
    "Draft a short git commit message for a fix that stops a cache from leaking memory.",
    "A train leaves at 14:35 and arrives at 18:10. How long is the trip in minutes?",
    "Write a TypeScript function that debounces another function by 300 ms.",
    "List the steps to safely rotate an API key used by three services.",
]

TOOLS = [
    {"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city",
     "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a text file from disk",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "run_bash", "description": "Run a bash command and return its output",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search the web",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Replace exact text in a file",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"},
                    "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "create_ticket", "description": "Create an issue in the tracker",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "priority": {"type": "string",
                    "enum": ["low", "medium", "high"]}}, "required": ["title", "priority"]}}},
]
TOOL_CASES = [  # (prompt, expected tool, required argument)
    ("What's the weather in Vienna right now?", "get_weather", "city"),
    ("Show me the contents of /etc/hostname.", "read_file", "path"),
    ("How much disk space is free on this machine? Check it.", "run_bash", "command"),
    ("Find the latest vLLM release notes online.", "search_web", "query"),
    ("Open the file src/main.rs so we can look at it.", "read_file", "path"),
    ("List the running docker containers.", "run_bash", "command"),
    ("Is it raining in Belgrade? Check the weather.", "get_weather", "city"),
    ("Read the README.md in the project root.", "read_file", "path"),
    ("Show the last 20 lines of /var/log/syslog.", "run_bash", "command"),
    ("Look up the current price of a DGX Spark online.", "search_web", "query"),
    ("In config.yaml replace 'port: 8000' with 'port: 8080'.", "edit_file", "new_text"),
    ("In main.py change the text 'DEBUG = True' to 'DEBUG = False'.", "edit_file", "old_text"),
    ("Open a high priority ticket titled 'vLLM crashes on start'.", "create_ticket", "priority"),
    ("Create a low priority ticket: 'Update the docs for la125'.", "create_ticket", "title"),
    ("How many CPU cores does this machine have? Find out.", "run_bash", "command"),
    ("What's the weather like in Tokyo today?", "get_weather", "city"),
    ("Search the web for 'GB10 memory bandwidth'.", "search_web", "query"),
    ("Print the contents of package.json.", "read_file", "path"),
    ("Check which python version is installed.", "run_bash", "command"),
    ("File a medium priority ticket called 'Benchmark noise too high'.", "create_ticket", "title"),
]
JSON_CASES = [
    "Return ONLY a JSON object with keys name (string), age (integer), tags (array of 2 strings) for a fictional person.",
    "Return ONLY a JSON array of 4 objects, each with keys id (integer) and done (boolean).",
    "Return ONLY a JSON object mapping three European capitals to their countries.",
    "Return ONLY a JSON object with key steps: an array of 3 short strings describing how to boil an egg.",
    "Return ONLY a JSON object describing a book: title, author, year (integer), genres (array).",
    "Return ONLY a JSON array of 5 prime numbers.",
    "Return ONLY a JSON object with keys ok (boolean) and errors (empty array).",
    "Return ONLY a JSON object: a tiny config with host, port (integer) and tls (boolean).",
    "Return ONLY a JSON array of 3 objects with keys city and population (integer).",
    "Return ONLY a JSON object with nested key a containing key b with value 42.",
    "Return ONLY a JSON object mapping the numbers one, two, three to their digits.",
    "Return ONLY a JSON object with key matrix: a 2x2 array of integers.",
    "Return ONLY a JSON object with keys start and end as ISO date strings in 2026.",
    "Return ONLY a JSON array of 3 short commit messages.",
]
NEEDLE = "The secret code for the vault is BLUE-4471."
NEEDLE_CASES = [(230_000, 0.1), (230_000, 0.9), (460_000, 0.3), (460_000, 0.8)]  # ~64k and ~128k tokens


def needle_doc(pos_frac, n_chars=100_000):
    doc = long_document(n_chars)
    cut = int(len(doc) * pos_frac)
    return doc[:cut] + "\n" + NEEDLE + "\n" + doc[cut:]


def prompt_lp(resp):
    """Per prompt position: the top-1 token id and the logprobs of every token vLLM returned there
    (the top-k plus the actual prompt token). Keys are token ids, so decoding quirks cannot matter."""
    out = []
    for pos in resp["choices"][0].get("prompt_logprobs") or []:
        if not pos:
            continue
        top = max(pos.items(), key=lambda kv: kv[1]["logprob"])[0]
        out.append({"top": top, "lp": {k: v["logprob"] for k, v in pos.items()}})
    return out


def gen_lp(resp_choice):
    """Tokens and top-5 logprobs of a chat completion (non-streamed)."""
    content = (resp_choice.get("logprobs") or {}).get("content") or []
    return [{"tok": c["token"], "lp": c["logprob"], "top": {t["token"]: t["logprob"] for t in c.get("top_logprobs") or []}}
            for c in content]


def decode_effort(i):
    return "low" if i < len(DECODE_PROMPTS) // 2 else "medium"


def chat_logprobs(prompt, max_tokens=512, effort="low"):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0.0, "logprobs": True, "top_logprobs": 5,
            "chat_template_kwargs": {"reasoning_effort": effort}}  # greedy so runs compare token by token
    r = SESSION.post(f"{BASE}/v1/chat/completions", json=body, timeout=900)
    r.raise_for_status()
    ch = r.json()["choices"][0]
    msg = ch["message"]
    return {"tokens": gen_lp(ch), "text": (msg.get("reasoning_content") or msg.get("reasoning") or "") + (msg.get("content") or "")}


def looping(text):
    words = text.split()
    if len(words) < 60:
        return False
    grams = [" ".join(words[i:i + 6]) for i in range(len(words) - 5)]
    return len(set(grams)) / len(grams) < 0.35


def _tool_case(case):
    prompt, tool, arg = case
    r = chat_stream([{"role": "user", "content": prompt}], tools=TOOLS, stop_after=4096, seed=11, **REAL)
    ok = False
    for tc in r["tool_calls"]:
        try:
            ok = ok or (tc["name"] == tool and arg in json.loads(tc["arguments"] or "{}"))
        except Exception:
            pass
    return {"kind": "tool", "prompt": prompt, "ok": ok, "calls": r["tool_calls"]}


def _json_case(prompt):
    r = chat_stream([{"role": "user", "content": prompt}], stop_after=4096, seed=12, **REAL)
    t = re.sub(r"^```(?:json)?|```$", "", r["text"].strip(), flags=re.M).strip()
    try:
        json.loads(t)
        ok = True
    except Exception:
        ok = False
    return {"kind": "json", "prompt": prompt, "ok": ok, "text": r["text"][:400]}


def _needle_case(case):
    n_chars, frac = case
    msgs = [{"role": "user", "content": needle_doc(frac, n_chars) + "\n\nWhat is the secret code for the vault? Answer with the code only."}]
    r = chat_stream(msgs, stop_after=4096, seed=13, **REAL)
    return {"kind": "needle", "pos": frac, "ok": "BLUE-4471" in r["text"], "text": r["text"][:200],
            "prompt_tokens": r["prompt_tokens"]}


def reliability():
    """Pass/fail checks, 4 requests at a time (owner idea: like parallel agents; not token-compared)."""
    from concurrent.futures import ThreadPoolExecutor
    # v4: tool calls and JSON are scored by the full ToolEvalBench suite (run_experiment.sh); needles stay here
    jobs = [(_needle_case, c) for c in NEEDLE_CASES]
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda job: job[0](job[1]), jobs))


def record(refdir):
    os.makedirs(refdir, exist_ok=True)
    tf = [prompt_lp(completion_logprobs(t, prompt_logprobs=TF_PROMPT_LOGPROBS, logprobs=1)) for t in TF_TEXTS]
    dec = [chat_logprobs(p, effort=decode_effort(i)) for i, p in enumerate(DECODE_PROMPTS)]
    write_json(os.path.join(refdir, "tf.json"), tf)
    write_json(os.path.join(refdir, "decode.json"), dec)
    print("recorded", len(tf), "tf texts,", len(dec), "decode prompts")


def compare(refdir, out):
    ref_tf = json.load(open(os.path.join(refdir, "tf.json"), encoding="utf-8"))
    ref_dec = json.load(open(os.path.join(refdir, "decode.json"), encoding="utf-8"))
    tf_agree = tf_n = 0
    tf_dlp = []
    for text, ref in zip(TF_TEXTS, ref_tf):
        cur = prompt_lp(completion_logprobs(text, prompt_logprobs=TF_PROMPT_LOGPROBS, logprobs=1))
        for a, b in zip(cur, ref):
            tf_n += 1
            tf_agree += a["top"] == b["top"]
            shared = set(a["lp"]) & set(b["lp"])
            # the actual prompt token is the one present in both dicts with a rank; compare all shared tokens
            if shared:
                tf_dlp.append(sum(abs(a["lp"][k] - b["lp"][k]) for k in shared) / len(shared))
    dec_prefix, dec_dlp, empties, loops = [], [], 0, 0
    for i, (prompt, ref) in enumerate(zip(DECODE_PROMPTS, ref_dec)):
        cur = chat_logprobs(prompt, effort=decode_effort(i))
        n = 0
        for a, b in zip(cur["tokens"], ref["tokens"]):
            if a["tok"] != b["tok"]:
                break
            dec_dlp.append(abs(a["lp"] - b["lp"]))
            n += 1
        dec_prefix.append(n / max(len(ref["tokens"]), 1))
        empties += not cur["text"].strip()
        loops += looping(cur["text"])
    rel = reliability()
    res = {
        "tf_top1": tf_agree / max(tf_n, 1),
        "tf_dlp": sum(tf_dlp) / max(len(tf_dlp), 1),
        "tf_positions": tf_n,
        "dec_prefix": sum(dec_prefix) / len(dec_prefix),
        "dec_dlp": sum(dec_dlp) / max(len(dec_dlp), 1),
        "dec_prefix_each": dec_prefix,
        "empty_outputs": empties,
        "looping_outputs": loops,
        "reliability_ok": sum(r["ok"] for r in rel),
        "reliability_total": len(rel),
        "reliability": rel,
    }
    write_json(out, res)
    print(json.dumps({k: v for k, v in res.items() if k not in ("reliability", "dec_prefix_each")}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--record")
    ap.add_argument("--ref")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.record:
        record(a.record)
    elif a.ref and a.out:
        compare(a.ref, a.out)
    else:
        sys.exit("use --record DIR or --ref DIR --out FILE")
