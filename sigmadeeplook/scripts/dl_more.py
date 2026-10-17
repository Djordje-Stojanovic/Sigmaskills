"""look.py FILE --more [N] | --from K | --remaining: read the rest of a look in steps, from a cursor saved in the look folder.

The stream (ranked chunks with token costs) is in look.json. The cursor (cursor.json) is how many chunks the agent has been given.
--more prints the next window and moves the cursor, so no chunk is repeated and none is skipped. --from K re-reads from chunk K
and moves the cursor only forward. --remaining prints what is left and what kind of content it is, and moves nothing.
"""
import json
from pathlib import Path

import dl_core as core
import dl_write as W


def load(out):
    try:
        return json.loads((Path(out) / "look.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def remaining_text(lj, pos, detail=False):
    stream = lj["stream"]
    rest = [c for c in stream[pos:] if W.shown(c, detail)]
    if not rest:
        return "Nothing remains in this look. Drill down with --at / --page / --sheet / --sql / --grep / --speaker (see Read next).\n"
    by = {}
    for c in rest:
        k = c["tag"] if c.get("tag") and c["tag"] not in ("finding", "limits", "file", "drill", "identity") else W.HEADINGS.get(c["sec"], c["sec"]).lower()
        n, t = by.get(k, (0, 0))
        by[k] = (n + 1, t + c["tok"])
    lines = [f"remaining ~{W.tok(W.cost(rest, detail))} tokens in {len(rest)} chunks (chunks {pos}-{len(stream) - 1}):"]
    lines += [f"- {k}: {n} chunks, ~{W.tok(t)} tokens" for k, (n, t) in sorted(by.items(), key=lambda kv: -kv[1][1])]
    lines.append("next: --more [N] prints the next N tokens (default ladder: to ~3k in all, then ~10k in all, then 5k at a time)")
    return "\n".join(lines) + "\n"


def run(out, sha, n=None, from_k=None, remaining=False, detail=False):
    """-> (text, exit). The caller has already made sure a look exists in `out`."""
    lj = load(out)
    if not lj or not lj.get("stream"):
        return "No stored look for this file; run look.py on it first.\n", 1
    stream = lj["stream"]
    pos = core.load_cursor(out, lj.get("sha256", sha))
    if remaining:
        return remaining_text(lj, pos, detail), 0
    start = pos if from_k is None else max(0, min(int(from_k), len(stream)))
    if n:
        want = n
    elif from_k is not None:
        want = 2000
    else:
        want = W.next_ladder(W.printed_cumulative(stream, pos, detail))
    if start >= len(stream):
        return "-- end of the stream: nothing more in this look. Drill down with --at / --page / --sheet / --sql / --grep / --speaker (see Read next).\n", 0
    chunks, nxt = W.window(stream, start, max(1, want - W.OVERHEAD), detail)   # the recap and the footer are part of the requested size
    text = W.render_window(chunks, start, detail) + W.footer(stream, start, nxt, 0, detail=detail)
    core.save_cursor(out, max(pos, nxt), lj.get("sha256", sha))
    return text, 0
