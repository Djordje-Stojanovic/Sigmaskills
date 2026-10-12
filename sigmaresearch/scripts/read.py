#!/usr/bin/env python3
"""SigmaResearch reader: read.py <platform[,platform...]|all> <query|url> [options]

Platforms: reddit, hn, github, stackoverflow (so), youtube (yt), x.  Read-only, stdlib only.
Other commands: read.py selftest [--platforms a,b]   (live check, one fixed query per platform)
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True  # keep the installed skill folder byte-identical to the release
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sr_core as core  # noqa: E402
import sr_readers as rd  # noqa: E402


def run(platforms, target, limit=10, depth=3, threads=None, from_json=None):
    """Read each platform in parallel (per-host limits live in sr_core). Returns the normalized document."""
    names = []
    for p in platforms:
        p = rd.ALIASES.get(p, p)
        if p not in rd.READERS:
            raise SystemExit(f"unknown platform '{p}'. Use: {', '.join(rd.READERS)}")
        names.append(p)

    def one(name):
        kw = {"limit": limit, "depth": depth}
        if threads is not None:
            kw["threads"] = threads
        if name == "x":
            kw["from_json"] = from_json
        try:
            return name, rd.READERS[name](target, **kw)
        except Exception as e:  # a reader bug must not kill the other platforms
            return name, {"items": [], "gaps": [f"{name} reader error: {type(e).__name__}: {e}"], "route": "error"}

    with ThreadPoolExecutor(max(1, len(names))) as ex:
        results = list(ex.map(one, names))
    items, gaps, routes = [], [], {}
    for name, r in results:
        items += r["items"]
        gaps += [{"platform": name, "gap": g} for g in r["gaps"]]
        routes[name] = r["route"]
    items = core.score_items(items)
    stats = {"items": len(items), "platforms": sorted({i["platform"] for i in items}),
             "unique_sources": core.unique_sources(items), "pages": len({i.get("thread") or i["url"] for i in items}),
             "routes": routes}
    return {"query": target, "items": items, "gaps": gaps, "stats": stats}


def render(doc):
    lines = []
    for i in doc["items"]:
        sc = "-" if i["score"] is None else i["score"]
        head = f"[{i['rank']:.2f}] {i['platform']} {i['source']} | {i['kind']} | {i['date'][:10] or 'undated'} | score {sc} | {i['url']}"
        lines.append(head)
        if i["title"]:
            lines.append(f"  title: {i['title']}")
        lines.append(f"  \"{i['quote']}\"  ({i['scope']})")
    s = doc["stats"]
    lines.append(f"-- {s['items']} items, {s['unique_sources']} unique sources, {s['pages']} pages, platforms: {', '.join(s['platforms']) or 'none'}")
    for g in doc["gaps"]:
        lines.append(f"GAP [{g['platform']}] {g['gap']}")
    return "\n".join(lines)


def selftest(platforms):
    """Live check. PASS = enough items parsed. BLOCKED = host refused (reported, not bypassed). FAIL = reached but unparsed."""
    core.USE_CACHE = False  # a cache hit must not hide a blocked host
    bad = 0
    for p in platforms:
        q, need = rd.SELFTEST[p]
        doc = run([p], q, limit=max(need, 5), threads=0)
        n = len(doc["items"])
        if n >= need:
            status = "PASS"
        elif doc["gaps"]:
            status = "BLOCKED" if any(str(c) in g["gap"] for g in doc["gaps"] for c in (401, 403, 429)) else "UNAVAILABLE"
        else:
            status = "FAIL"
            bad += 1
        print(f"{status:11} {p:14} {n}/{need} items via {doc['stats']['routes'][p]}  query: {q}")
        for g in doc["gaps"]:
            print(f"            gap: {g['gap']}")
    return 1 if bad else 0


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("platform", help="reddit | hn | github | stackoverflow | youtube | x | comma list | all | selftest")
    ap.add_argument("target", nargs="?", default="", help="query or URL")
    ap.add_argument("--limit", type=int, default=10, help="items per platform (comments: top N by score)")
    ap.add_argument("--depth", type=int, default=3, help="comment depth")
    ap.add_argument("--threads", type=int, default=None, help="how many top threads to open and read comments of")
    ap.add_argument("--json", action="store_true", help="print the normalized document as JSON")
    ap.add_argument("--no-cache", action="store_true", help="skip the 24 h cache in ~/.cache/sigmaresearch")
    ap.add_argument("--from-json", help="x only: JSON file (or -) from the Chrome snippet in references/x.md")
    ap.add_argument("--platforms", help="selftest only: comma list")
    a = ap.parse_args(argv)
    core.USE_CACHE = not a.no_cache
    if a.platform == "selftest":
        return selftest((a.platforms.split(",") if a.platforms else list(rd.SELFTEST)))
    if not a.target and not a.from_json:
        ap.error("target (query or URL) is required")
    plats = list(rd.SELFTEST) + ["x"] if a.platform == "all" else a.platform.split(",")
    doc = run(plats, a.target, a.limit, a.depth, a.threads, a.from_json)
    print(json.dumps(doc, indent=2, ensure_ascii=False) if a.json else render(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
