"""look.py gate: the cheap first question, answered in one line (about 30 tokens, no analysis).

    READ <path> (~N tokens)                      plain text (CSV, JSON, code, logs ...): read or query it with your own tools
    READ <path> (~N tokens, over one read ...)   the same, too big for one read: query it (python, grep), never summarise it
    LOOK <quick|standard|deep> <path> - <why>    media, scans, binaries, containers, or text that needs the look (not UTF-8,
                                                 or email/web/notebook over one read: parts, attachments, outputs)

The test is code, not taste. Plain text is decided on the first 64 KB only, so the gate costs the same on a 60 MB file.
Measured (17-10, ticket 83 P0.14b): on data files a plain agent with code beats a summary; on media, scans and binaries the
look is the only way in on a machine without the tools.
"""
import argparse
import os
from pathlib import Path

import dl_core as core

MEDIA = {"video", "audio", "image"}
QUICK_KINDS = {"font", "3d", "notebook"}   # small structured files: a metadata look is usually enough
PLAIN_FAMILIES = {"data", "code", "log", "subtitle"}   # plain text: the agent reads or queries it itself, any size
EMBEDDED_FAMILIES = {"email", "web", "notebook"}       # text that carries attachments, pages or outputs: direct only when small
BINARY_SUBTYPES = {"sqlite", "parquet", "arrow", "avro", "xlsx", "ods"}


def head_kind(p):
    """'utf8' (plain text), 'text' (decodes, but not UTF-8: the look decodes it), or 'binary'. Reads 64 KB at most."""
    head = core.read_head(p, 65536)
    if not head:
        return "utf8"
    if b"\0" not in head:
        try:
            head.decode("utf-8")
            return "utf8"
        except UnicodeDecodeError as e:
            if e.start >= len(head) - 3:   # a multi-byte character cut by the 64 KB read
                return "utf8"
    text, _ = core.decode_text(head)
    return "text" if text is not None else "binary"


def decide(path, budget=None):
    """-> (verdict 'READ'|'LOOK', tier or None, tokens, reason)."""
    p = Path(path)
    if p.is_dir():
        return "LOOK", "quick", 0, "folder: a map only; read its files with your own tools"
    d = core.detect(p)
    t, st, size = d["type"], d["subtype"], p.stat().st_size
    if t == "code" and p.suffix.lower() in (".html", ".htm", ".xhtml"):
        t, st = "web", "html"   # a fragment with no <html> tag is still a web page: hidden text and injected instructions live there
    toks = core.direct_tokens(size) if size else 0
    limit = min(core.DIRECT_MAX_TOKENS, budget) if budget else core.DIRECT_MAX_TOKENS
    if t in MEDIA and not (t == "image" and st == "svg" and toks <= limit):
        return "LOOK", "standard", toks, f"{t} ({st}): you cannot see or hear it"
    if t == "unknown" and st == "empty":
        return "READ", None, 0, "empty file"
    if t == "image" and st == "svg":
        return "READ", None, toks, "small SVG text"
    if t in PLAIN_FAMILIES and st not in BINARY_SUBTYPES:
        kind = head_kind(p)
        if kind == "utf8":
            if budget and toks > budget:
                return "LOOK", "standard", toks, f"text of ~{toks} tokens is over your --budget {budget}: schema, counts and a sample"
            if toks <= core.DIRECT_MAX_TOKENS:
                return "READ", None, toks, "plain text"
            return "READ", None, toks, "plain text, over one read: query it with python (csv, json) or grep, not one Read"
        if kind == "text":
            return "LOOK", "standard", toks, f"{t} ({st}) is not UTF-8 text: the look decodes it and flags the encoding"
    text_here = t in EMBEDDED_FAMILIES and head_kind(p) == "utf8"
    if text_here and size <= core.DIRECT_MAX_BYTES and toks <= limit and core.direct_eligible(p, t, st, size):
        return "READ", None, toks, "small text"
    binary = t in ("binary", "archive", "font", "3d", "office", "pdf", "unknown") or st in BINARY_SUBTYPES or (t in EMBEDDED_FAMILIES and not text_here)
    if binary:
        return "LOOK", "quick" if t in QUICK_KINDS else "standard", toks, f"{t} ({st}): binary or container"
    if t in EMBEDDED_FAMILIES:
        return "LOOK", "standard", toks, f"{t} ({st}) over one read: its parts, attachments or outputs need the look"
    return "LOOK", "standard", toks, f"{t} ({st})"


def main(argv):
    ap = argparse.ArgumentParser(prog="look.py gate")
    ap.add_argument("target")
    ap.add_argument("--budget", type=int, help="tokens the caller can spend reading directly (default: one read, 25,000)")
    o = ap.parse_args(argv)
    if not os.path.exists(o.target):
        print(f"No such file or folder: {o.target}")
        return 1
    v, tier, toks, why = decide(o.target, o.budget)
    if v == "READ":
        if why.startswith("plain text, over one read"):
            print(f"READ {o.target} (~{toks} tokens, over one read: query it with python or grep)")
        else:
            print(f"READ {o.target} (~{toks} tokens)")
    else:
        print(f"LOOK {tier} {o.target} - {why}")
    return 0
