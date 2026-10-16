#!/usr/bin/env python3
"""SigmaDeepLook: look.py <file|dir|URL> [options]   |   look.py doctor | selftest | gallery

Turns any file into facts (look.json), text (LOOK.md and artifacts) and a few pictures sized for the model.
Stdout is LOOK.md. Core is stdlib only; optional tools are used when found and become "Not looked at" rows when not.
Use `python` on Windows and `python3` elsewhere. Do not run it with -I (that hides installed packages).

  look.py FILE [--out DIR] [--reader claude|claude-hires|gemini|small] [--deep] [--extract] [--recurse N]
               [--allow-network] [--fresh] [--json] [--no-tools] [--at SEC --len SEC] [--mode overview|sweep]
  look.py doctor                          # which tools and packages are present, with install lines
  look.py selftest [--tier full|bare]     # the 10 numeric checks on the bundled fixtures (needs a repo checkout)
  look.py gallery DIR -o gallery.html     # one page over many looks
Exit: 0 looked, 1 internal error, 2 refused by a safety rule, 3 unknown type.
"""
import argparse
import json
import os
import sys
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
    "unknown": ("dl_bins", "look_unknown"),
}


def analyse(path, out, opts, sha=None, depth=0):
    """Look at one path. Always writes LOOK.md, look.json and view.html into `out`. -> the Look."""
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
    mod, fn = HANDLERS.get(look.type, HANDLERS["unknown"])
    try:
        getattr(__import__(mod), fn)(look)
    except Exception as e:  # one broken step must never lose the Identity block
        look.exit_code = 1
        look.flag("INTERNAL-ERROR", f"{mod}.{fn}", f"{type(e).__name__}: {e}", traceback.format_exc().strip().splitlines()[-2][:200])
    look.finish()
    return look


def recurse_into(look, path, label):
    """Look at an extracted member or attachment one level down. -> the child Look."""
    n = len(look.children) + 1
    child_opts = argparse.Namespace(**{**vars(look.opts), "recurse": 0, "out": None})
    c = analyse(path, look.out / "children" / f"{n:02d}", child_opts, depth=getattr(look, "depth", 0) + 1)
    look.children.append({"label": label, "dir": str(c.out), "type": c.type, "sha256": c.sha})
    look.line(f"- member {label}: {c.type}/{c.subtype}, details in `{c.out / 'LOOK.md'}`")
    return c


core.recurse_into = recurse_into


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
    print("\nTiers: bare = Python only; partial = some optional tools missing (each becomes a Not-looked-at row); full = everything the file type can use.")
    return 0


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) > 1 and argv[1] == "doctor":
        return doctor()
    if len(argv) > 1 and argv[1] == "selftest":
        import dl_selftest
        return dl_selftest.main(argv[2:])
    if len(argv) > 1 and argv[1] == "gallery":
        import dl_view
        return dl_view.gallery_main(argv[2:])
    ap = argparse.ArgumentParser(prog="look.py", description="Look inside any file.")
    ap.add_argument("target", help="file, directory or (with --allow-network) URL")
    ap.add_argument("--out", help="output folder (default: the cache folder keyed by sha256)")
    ap.add_argument("--reader", default="claude", choices=sorted(core.READERS))
    ap.add_argument("--deep", action="store_true", help="slow tools: bigger speech model, decompilers, more frames")
    ap.add_argument("--extract", action="store_true", help="archives and mail: write members and attachments (after the safety screen)")
    ap.add_argument("--recurse", type=int, default=0, metavar="N", help="look at the first N members or attachments too")
    ap.add_argument("--allow-network", action="store_true", help="allow URLs and model downloads (off by default)")
    ap.add_argument("--fresh", action="store_true", help="ignore a stored look of the same file")
    ap.add_argument("--json", action="store_true", help="print look.json instead of LOOK.md")
    ap.add_argument("--no-tools", action="store_true", help="bare tier: Python standard library only")
    ap.add_argument("--at", type=float, help="video: zoom window start (seconds)")
    ap.add_argument("--len", type=float, default=10.0, dest="length", help="video: zoom window length (seconds)")
    ap.add_argument("--mode", default="overview", choices=("overview", "sweep"), help="video: overview sheet, or sweep pages that cover the whole film")
    o = ap.parse_args(argv[1:])
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
    sha = core.sha256_dir(p) if p.is_dir() else core.sha256_file(p)
    out = core.out_dir_for(sha, o.out)
    stored = out / "look.json"
    if stored.exists() and not o.fresh:
        try:
            old = json.loads(stored.read_text(encoding="utf-8"))
            if old.get("sha256") == sha and old.get("opts_key") == core.opts_key(o) and (out / "LOOK.md").exists() and o.at is None and old.get("mode") == o.mode:
                print((stored.read_text(encoding="utf-8") if o.json else (out / "LOOK.md").read_text(encoding="utf-8")))
                return old.get("exit", 0)
        except (OSError, ValueError):
            pass
    core.clean_own_dir(out)
    look = analyse(p, out, o, sha)
    print(look.out.joinpath("look.json" if o.json else "LOOK.md").read_text(encoding="utf-8"))
    return look.exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
