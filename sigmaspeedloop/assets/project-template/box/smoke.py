"""smoke.py - 1-minute check that the server supports what the bench needs. Run from /root/work/bench."""
import json, sys, time
sys.path.insert(0, "/root/work/bench")
from common import chat_stream, completion_logprobs, SESSION, BASE, MODEL
from gate import TOOLS, prompt_lp, chat_logprobs

ok = True
try:
    r = completion_logprobs("def add(a, b):\n    return a + b\n")
    pl = prompt_lp(r)
    print("prompt_logprobs positions:", len(pl), "sample:", json.dumps(pl[1])[:200])
except Exception as e:
    ok = False
    print("prompt_logprobs FAILED:", str(e)[:300])
try:
    c = chat_logprobs("Say hi in five words.", 64)
    print("chat logprobs tokens:", len(c["tokens"]), "text:", c["text"][:80].replace("\n", " "))
except Exception as e:
    ok = False
    print("chat logprobs FAILED:", str(e)[:300])
s = chat_stream([{"role": "user", "content": "Count from 1 to 40."}], 256)
print("stream: ttft %.2f s, decode %.1f tok/s, %d tokens, finish %s" % (s["ttft_s"], s["decode_tps"] or 0, s["completion_tokens"], s["finish_reason"]))
t = chat_stream([{"role": "user", "content": "What's the weather in Vienna?"}], 512, tools=TOOLS,
                extra={"chat_template_kwargs": {"enable_thinking": False}})
print("tool calls:", t["tool_calls"], "text:", t["text"][:80])
print("SMOKE", "OK" if ok and t["tool_calls"] else "PROBLEM")
