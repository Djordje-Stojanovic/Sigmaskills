#!/usr/bin/env python3
"""SigmaDeepLook: look.py <file|dir|URL> [options]   |   look.py gate | doctor | selftest | gallery

Opt-in: run `look.py gate FILE` first (one line: READ or LOOK). A look turns a file that is too big to read, binary or media into a
ranked stream of facts. The first call prints step 1 (about 1,000 tokens); `--more [N]` prints the next part from a cursor;
drill-down flags (--at, --page, --sheet, --sql, --table, --func, --member, --grep, --speaker) read one part.
Core is stdlib only; optional tools are used when found and become "Not looked at" rows when not.
Use `python` on Windows and `python3` elsewhere. Do not run it with -I (that hides installed packages).

  look.py gate FILE [--budget N]                       READ <path> | LOOK quick|standard|deep <path>
  look.py FILE [--tier quick|standard|deep] [--budget N] [--out DIR] [--reader ...] [--detail] [--extract] [--recurse N]
               [--allow-network] [--fresh] [--json] [--no-tools] [--no-direct]
  look.py FILE --more [N] | --from K | --remaining    continue / re-read / what is left
  look.py FILE --at M:SS --len S | --page A-B | --sheet NAME [--range A1:H40] | --sql "SELECT ..." | --table T
               | --func NAME | --member PATH | --grep REGEX | --lines [NAME:]A-B | --speaker S2
  look.py doctor | selftest [--tier full|bare] | gallery DIR -o gallery.html
Exit: 0 looked, 1 internal error, 2 refused by a safety rule, 3 unknown type.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dl_core as core  # noqa: E402

HANDLERS = {  # type -> (module, function)
    "video": ("dl_media", "look_video"), "audio": ("dl_media", "look_audio"), "image": ("dl_media", "look_image"),
    "pdf": ("dl_docs", "look_pdf"), "office": ("dl_docs", "look_office"), "notebook": ("dl_docs", "look_notebook"),
    "email": ("dl_docs", "look_email"), "web": ("dl_docs", "look_web"),
    "binary": ("dl_bins", "look_binary"), "archive": ("dl_bins", "look_archive"), "font": ("dl_bins", "look_font"),
    "3d": ("dl_3d", "look_3d"), "code": ("dl_bins", "look_code"), "data": ("dl_data", "look_data"),
    "unknown": ("dl_bins", "look_unknown"), "log": ("dl_logs", "look_log"), "subtitle": ("dl_logs", "look_subtitle"),
    "cert": ("dl_extra", "look_cert"), "model": ("dl_extra", "look_model"), "diskimage": ("dl_extra", "look_diskimage"),
}
DRILL_FLAGS = ("ask", "page", "sheet", "sql", "table", "func", "member", "grep", "lines", "speaker")


def analyse(path, out, opts, sha=None, depth=0):
    """Look at one path. Always writes LOOK.md (step 1), look.json (with the ranked stream) and view.html into `out`. -> the Look."""
    p = Path(path).resolve()
    look = core.Look(p, out, opts)
    look.depth = depth
    look.size = 0 if p.is_dir() else p.stat().st_size
    look.sha = sha or (core.sha256_dir(p) if p.is_dir() else core.sha256_file(p))
    d = core.detect(p)
    look.type, look.subtype = d["type"], d["subtype"]
    look.detector = {"magic": d["magic"], "ext": d["ext"], "mismatch": d["mismatch"]}
    if d["mismatch"]:
        look.flag("MISMATCH", "extension", d["mismatch"], "the extension lies or the file was renamed; trust the bytes")
    direct = not getattr(opts, "no_direct", False) and depth == 0 and core.direct_eligible(p, look.type, look.subtype, look.size)
    mod, fn = HANDLERS.get(look.type, HANDLERS["unknown"])
    try:
        getattr(__import__(mod), fn)(look)
    except Exception as e:  # one broken step must never lose the Identity block
        look.exit_code = 1
        look.flag("INTERNAL-ERROR", f"{mod}.{fn}", f"{type(e).__name__}: {e}", traceback.format_exc().strip().splitlines()[-2][:200])
    if (look.type == "unknown" or d["mismatch"]) and not direct:
        import dl_adapt
        dl_adapt.magika_second_opinion(look)
    if direct:   # small plain text: still a full look with exact counts (stored, so --more works); reading it whole is also fine
        look.fact("direct_read", True)
        look.line(f"Small text file: the whole file is ~{core.direct_tokens(look.size):,} tokens, so reading it whole is also fine; every count in this look is exact.", 80, "note")
    core.add_source_content(look)
    look.finish()
    return look


def recurse_into(look, path, label):
    """Look at an extracted member or attachment one level down, at the quick tier. -> the child Look."""
    n = len(look.children) + 1
    child_opts = argparse.Namespace(**{**vars(look.opts), "recurse": 0, "out": None, "tier": "quick", "deep": False, "quick": True, "budget": None})
    c = analyse(path, look.out / "children" / f"{n:02d}", child_opts, depth=getattr(look, "depth", 0) + 1)
    look.children.append({"label": label, "dir": str(c.out), "type": c.type, "sha256": c.sha})
    look.line(f"member {label}: {c.type}/{c.subtype}, details in `{c.out / 'LOOK.md'}`", 40)
    return c


core.recurse_into = recurse_into
core.HANDLERS = HANDLERS


def doctor():
    import platform
    print(f"# SigmaDeepLook doctor\n\n- python {platform.python_version()} on {platform.system()} ({sys.executable})")
    print("- Do not run look.py with `python -I`: it hides installed packages.\n")
    print("| tool | status | install |\n|---|---|---|")
    for t in core.TOOLS:
        p = core.find_tool(t)
        print(f"| {t} | {'found: ' + p if p else 'missing'} | {'' if p else core.install_line(t)} |")
    print("\n| python package | status | install |\n|---|---|---|")
    for m in core.MODULES:
        ok = core.have_module(m)
        print(f"| {m} | {'found' if ok else 'missing'} | {'' if ok else core.install_line(m)} |")
    import dl_models
    print("\n| model | status | install |\n|---|---|---|")
    for m in core.MODELS:
        ok = dl_models.have_model(m)
        print(f"| {m} | {'cached' if ok else 'missing'} | {'' if ok else core.install_line(m)} |")
    print("\nTiers: bare = Python only; partial = some optional tools missing (each becomes a Not-looked-at row); full = everything the file type can use.")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="look.py", description="Look inside a file that is too big to read, binary or media.")
    ap.add_argument("target", help="file, directory or (with --allow-network) URL")
    ap.add_argument("--out", help="output folder (default: the cache folder keyed by sha256)")
    ap.add_argument("--reader", default="claude", choices=sorted(core.READERS))
    ap.add_argument("--tier", choices=core.TIERS, help="how much machine work: quick (metadata only, under 5 s), standard (default), deep (slowest tools)")
    ap.add_argument("--quick", action="store_true", help="same as --tier quick")
    ap.add_argument("--deep", action="store_true", help="same as --tier deep: biggest speech model, OCR on every second, decompilers, more frames")
    ap.add_argument("--budget", type=int, metavar="N", help="tokens printed in step 1 (default 1000)")
    ap.add_argument("--more", nargs="?", const=-1, type=int, metavar="N", help="print the next N tokens of the stored look from the cursor (default ladder: to ~3k in all, then ~10k, then 5k at a time)")
    ap.add_argument("--from", dest="from_k", type=int, metavar="K", help="re-read the stored look from chunk K (the cursor only moves forward)")
    ap.add_argument("--detail", action="store_true", help="add the ids, timings and every Read-next file that the concise default leaves out")
    ap.add_argument("--remaining", action="store_true", help="say how many tokens and what kind of content are left")
    ap.add_argument("--extract", action="store_true", help="archives and mail: write members and attachments (after the safety screen)")
    ap.add_argument("--recurse", type=int, default=0, metavar="N", help="look at the first N members or attachments too")
    ap.add_argument("--allow-network", action="store_true", help="allow URLs and model downloads (off by default)")
    ap.add_argument("--fresh", action="store_true", help="ignore a stored look of the same file")
    ap.add_argument("--json", action="store_true", help="print look.json instead of LOOK.md")
    ap.add_argument("--no-direct", "--force", action="store_true", dest="no_direct", help="leave out the 'small text file, read it whole' note (every file gets a full look either way)")
    ap.add_argument("--no-tools", action="store_true", help="bare tier: Python standard library only")
    ap.add_argument("--at", help="video, audio: window start, seconds or M:SS (video also builds a zoom sheet)")
    ap.add_argument("--len", type=float, default=10.0, dest="length", help="video, audio: window length in seconds")
    ap.add_argument("--query", metavar="TEXT", help="video: pick the contact-sheet tiles for this question (tiles follow the words spoken near it; a third stay evenly spread)")
    ap.add_argument("--mode", default="overview", choices=("overview", "sweep"), help="video: overview sheet, or sweep pages that cover the whole film")
    ap.add_argument("--page", help="pdf, office: pages A-B (text and cost)")
    ap.add_argument("--sheet", help="spreadsheet: sheet name (with --range A1:H40)")
    ap.add_argument("--range", help="spreadsheet: cell range for --sheet")
    ap.add_argument("--sql", help="csv, tsv, parquet, jsonl, sqlite: a read-only SELECT, LIMIT 50 enforced; the table is `t` (or the real table name in a database)")
    ap.add_argument("--table", help="database: profile and sample of one table")
    ap.add_argument("--func", help="binary: one function (decompiling needs Ghidra)")
    ap.add_argument("--member", help="archive: look at one member at the quick tier")
    ap.add_argument("--grep", metavar="REGEX", help="search the look's text artifacts (or the text file itself): 50 hits with line numbers")
    ap.add_argument("--lines", metavar="[NAME:]A-B", help="a window of at most 100 lines of one text artifact of the look (or of the text file itself)")
    ap.add_argument("--speaker", help="audio, video: the turns of one speaker, e.g. S2")
    ap.add_argument("--ask", metavar="QUESTION", help="one exact answer over the stored look: count, sum, mean, max, min, distinct, per-group or lookup on the file's tables, "
                    "with the filters and rows used; text files get the stated counts and best-matching lines")
    return ap


def parse_time(v):
    """'125', '2:05' or '1:02:05' -> seconds, else None."""
    if v is None:
        return None
    try:
        t = 0.0
        for x in str(v).split(":"):
            t = t * 60 + float(x)
        return t
    except ValueError:
        return None


def say(text, code=0):
    print(text.rstrip("\n"))
    return code


def step_one_cursor(stored):
    """The chunk index step 1 ended at, recomputed from a stored stream (a cached look restarts the cursor)."""
    import dl_write
    stream = stored.get("stream") or []
    return dl_write.window(stream, 0, dl_write.first_budget())[1] if stream else 0


def step_one_text(out, o):
    """LOOK.md (concise), or with --detail step 1 re-rendered from the stored stream with ids, timings and every Read-next file."""
    if getattr(o, "detail", False) and not o.json:
        try:
            import dl_write
            stream = json.loads((Path(out) / "look.json").read_text(encoding="utf-8")).get("stream") or []
            if stream:
                return dl_write.render_first(None, stream, getattr(o, "budget", None), detail=True)[0]
        except (OSError, ValueError):
            pass
    return (Path(out) / ("look.json" if o.json else "LOOK.md")).read_text(encoding="utf-8")


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) > 1 and argv[1] in ("doctor", "gate", "selftest", "gallery"):
        if argv[1] == "doctor":
            return doctor()
        if argv[1] == "gate":
            import dl_gate
            return dl_gate.main(argv[2:])
        if argv[1] == "selftest":
            import dl_selftest
            return dl_selftest.main(argv[2:])
        import dl_view
        return dl_view.gallery_main(argv[2:])
    o = build_parser().parse_args(argv[1:])
    o.at_raw, o.at = o.at, parse_time(o.at)
    if not o.allow_network:
        core.install_socket_guard()
    target = o.target
    if target.lower().startswith(("http://", "https://")):
        if not o.allow_network:
            print("Refused: a URL needs --allow-network (no network by default). Web research belongs to sigmaresearch.", file=sys.stderr)
            return 2
        import dl_docs
        target = dl_docs.fetch_url(target, o)
        if not target:
            return 1
    p = Path(target)
    if not p.exists():
        print(f"No such file or folder: {target}", file=sys.stderr)
        return 1
    asked_more = o.more is not None or o.remaining or o.from_k is not None
    drill = any(getattr(o, k) for k in DRILL_FLAGS) or o.at is not None
    sha = core.sha256_dir(p) if p.is_dir() else core.sha256_file(p)
    out = core.out_dir_for(sha, o.out)
    stored = out / "look.json"
    old = None
    if stored.exists():
        try:
            old = json.loads(stored.read_text(encoding="utf-8"))
            if old.get("sha256") != sha or not (out / "LOOK.md").exists():
                old = None
        except (OSError, ValueError):
            old = None
    if asked_more:
        if old is None:
            core.clean_own_dir(out)
            look = analyse(p, out, o, sha)
            print(look.out.joinpath("LOOK.md").read_text(encoding="utf-8").rstrip("\n"))
            print("(no stored look existed: that was step 1; run --more to continue)")
            return look.exit_code
        import dl_more
        return say(*dl_more.run(out, sha, None if o.more in (None, -1) else o.more, o.from_k, o.remaining, o.detail))
    if drill:
        if old is None:
            core.clean_own_dir(out)
            analyse(p, out, argparse.Namespace(**{**vars(o), "at": None}), sha)
            old = json.loads(stored.read_text(encoding="utf-8"))
        import dl_drill
        got = dl_drill.run(o, p, out, old)
        if got is not None:
            return say(*got)
    if old is not None and not o.fresh and old.get("opts_key") == core.opts_key(o) and old.get("mode") == o.mode:
        core.save_cursor(out, step_one_cursor(old), sha)
        return say(step_one_text(out, o), old.get("exit", 0))
    core.clean_own_dir(out)
    look = analyse(p, out, o, sha)
    return say(step_one_text(look.out, o), look.exit_code)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
