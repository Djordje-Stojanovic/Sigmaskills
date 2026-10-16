"""look.py gate: the cheap first question, answered in one line (about 30 tokens, no analysis).

    READ <path> (~N tokens)                      small text: stop, use your own Read
    LOOK <quick|standard|deep> <path> - <why>    too big to read, binary or media: run look.py

The test is code, not taste: text over DIRECT_MAX_TOKENS (or over --budget), anything that is not valid text, any audio, video or image.
"""
import argparse
import os
from pathlib import Path

import dl_core as core

MEDIA = {"video", "audio", "image"}
QUICK_KINDS = {"font", "3d", "notebook"}   # small structured files: a metadata look is usually enough


def decide(path, budget=None):
    """-> (verdict 'READ'|'LOOK', tier or None, tokens, reason)."""
    p = Path(path)
    if p.is_dir():
        return "LOOK", "quick", 0, "folder: a map only; read its files with your own tools"
    d = core.detect(p)
    t, st, size = d["type"], d["subtype"], p.stat().st_size
    toks = core.direct_tokens(size) if size else 0
    limit = min(core.DIRECT_MAX_TOKENS, budget) if budget else core.DIRECT_MAX_TOKENS
    if t in MEDIA and not (t == "image" and st == "svg" and toks <= limit):
        return "LOOK", "standard", toks, f"{t} ({st}): you cannot see or hear it"
    if d["type"] == "unknown" and st == "empty":
        return "READ", None, 0, "empty file"
    if t == "image" and st == "svg":
        return "READ", None, toks, "small SVG text"
    text_ok = core.direct_eligible(p, t, st, min(size, core.DIRECT_MAX_BYTES)) if size <= core.DIRECT_MAX_BYTES else False
    if text_ok and toks <= limit:
        return "READ", None, toks, "small text"
    binary = t in ("binary", "archive", "font", "3d", "office", "pdf", "unknown") or st in ("sqlite", "parquet", "arrow")
    if binary:
        return "LOOK", "quick" if t in QUICK_KINDS else "standard", toks, f"{t} ({st}): binary or container"
    if t in ("data", "code", "email", "web", "notebook") or core.decode_text(core.read_head(p, 4096))[0] is not None:
        return "LOOK", "standard", toks, f"text of ~{toks} tokens is over {limit}: schema, counts and a sample instead of the whole"
    return "LOOK", "standard", toks, f"{t} ({st})"


def main(argv):
    ap = argparse.ArgumentParser(prog="look.py gate")
    ap.add_argument("target")
    ap.add_argument("--budget", type=int, help="tokens the caller can spend reading directly (default 25,000)")
    o = ap.parse_args(argv)
    if not os.path.exists(o.target):
        print(f"No such file or folder: {o.target}")
        return 1
    v, tier, toks, why = decide(o.target, o.budget)
    if v == "READ":
        print(f"READ {o.target} (~{toks} tokens)")
    else:
        print(f"LOOK {tier} {o.target} - {why}")
    return 0
