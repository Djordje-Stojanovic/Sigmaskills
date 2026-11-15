"""build_replay.py - freeze the owner's real agent sessions into OpenAI-format replay traces (run once, locally).

Each trace holds the full message list of one session (system + user + assistant tool calls + tool results)
and 6 cut points. Replaying a cut = sending messages[:cut] and letting the model write the next assistant turn.
Cuts are chosen so the estimated context grows from ~10k to ~120k tokens, like a real agent session.
"""
import glob, json, os, sys

SESSIONS = os.path.expanduser(r"~\.pi\agent\sessions")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay")
CHARS_PER_TOKEN = 3.2          # rough estimate; the real token count is logged by the server
MIN_TOK, MAX_TOK, CUTS = 10_000, 120_000, 6


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")


def convert(path):
    system, tools, msgs = None, None, []
    for line in open(path, encoding="utf-8"):
        o = json.loads(line)
        m = o.get("message")
        if not m:
            continue
        role = m.get("role")
        if role == "system" and system is None:
            secs = m.get("sections") or {}
            system = "\n\n".join(v for v in secs.values() if isinstance(v, str))
            tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                                        "parameters": t.get("parameters") or {"type": "object"}}}
                     for t in (m.get("toolsAdded") or [])]
        elif role == "user":
            t = text_of(m.get("content", ""))
            if t.strip():
                msgs.append({"role": "user", "content": t})
        elif role == "assistant":
            calls = [{"id": c["id"], "type": "function",
                      "function": {"name": c["name"], "arguments": json.dumps(c.get("arguments") or {})}}
                     for c in m.get("content", []) if c.get("type") == "toolCall"]
            a = {"role": "assistant", "content": text_of(m.get("content", []))}
            if calls:
                a["tool_calls"] = calls
            msgs.append(a)
        elif role == "toolResult":
            msgs.append({"role": "tool", "tool_call_id": m.get("toolCallId", ""), "content": text_of(m.get("content", []))})
    if not system or not tools:
        return None
    return {"system": system, "tools": tools, "messages": [{"role": "system", "content": system}] + msgs}


def cuts_for(trace):
    sizes, total = [], 0
    for i, m in enumerate(trace["messages"]):
        total += len(json.dumps(m))
        sizes.append(total / CHARS_PER_TOKEN)
    # a cut sits right before an assistant message, so the model writes that turn
    cand = [i for i, m in enumerate(trace["messages"]) if m["role"] == "assistant" and MIN_TOK <= sizes[i - 1] <= MAX_TOK]
    if len(cand) < CUTS * 2:
        return None
    picks = [cand[round(k * (len(cand) - 1) / (CUTS - 1))] for k in range(CUTS)]
    return picks, [round(sizes[p - 1]) for p in picks]


def main():
    files = sorted(glob.glob(os.path.join(SESSIONS, "*", "*.jsonl")), key=os.path.getmtime, reverse=True)
    os.makedirs(OUT, exist_ok=True)
    chosen, projects = [], set()
    for f in files:
        if not (800_000 <= os.path.getsize(f) <= 8_000_000):
            continue
        project = os.path.basename(os.path.dirname(f))
        if project in projects:
            continue
        trace = convert(f)
        if not trace:
            continue
        c = cuts_for(trace)
        if not c:
            continue
        last = c[0][-1]
        trace["messages"] = trace["messages"][:last]          # nothing after the last cut is needed
        trace.update(source=f, project=project, cuts=c[0], est_tokens=c[1])
        del trace["system"]
        name = f"trace{len(chosen) + 1}.json"
        json.dump(trace, open(os.path.join(OUT, name), "w", encoding="utf-8"), ensure_ascii=False)
        chosen.append(name)
        projects.add(project)
        print(name, project, "cuts", c[0], "est tokens", c[1])
        if len(chosen) == 3:
            break
    if len(chosen) < 3:
        sys.exit("fewer than 3 usable sessions")


if __name__ == "__main__":
    main()
