"""look.py selftest: the 10 numeric checks over the bundled fixtures (needs a repository checkout or --fixtures DIR).

    python look.py selftest [--tier full|bare|both] [--fixtures DIR] [--only a,b] [--keep DIR]

The truth file (truth.json, next to the fixtures) lists, per fixture, the expected type and exit code, and seeded facts as regular
expressions with the tools each one needs. A fact whose tool is missing must show up as a "Not looked at" row with an install line.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import dl_core as core

HERE = Path(__file__).resolve().parent
LOOK = HERE / "look.py"
SECTIONS = ["Key facts", "Watch out", "Map", "Read next", "Not looked at"]
STEP1_MAX = 1150   # step 1 prints about 1,000 tokens; the header and the footer line are the slack
CHECKS = ["exit code", "type", "LOOK.md contract", "seeded facts", "image budget", "no stray writes", "no network", "nothing executed", "time", "view.html"]
LIMIT = {"bare": 10.0, "full": 60.0}


def find_fixtures(arg):
    for c in ([Path(arg)] if arg else []) + [HERE.parent.parent / "test" / "sigmadeeplook", HERE.parent.parent.parent / "test" / "sigmadeeplook"]:
        if (c / "truth.json").exists():
            return c
    return None


def available(need):
    if need == "faster_whisper":
        import dl_media
        fake = type("L", (), {"deep": False})()
        return core.have_module("faster_whisper") and dl_media.pick_model(fake) is not None
    return bool(core.find_tool(need)) if need in core.TOOLS else core.have_module(need)


def snapshot(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        for n in fns:
            p = Path(dp) / n
            try:
                s = p.stat()
                out[str(p)] = (s.st_size, s.st_mtime_ns)
            except OSError:
                pass
        for d in dns:
            out[str(Path(dp) / d) + os.sep] = 0
    return out


def hay_of(out):
    parts = [(out / "LOOK.md").read_text(encoding="utf-8", errors="replace")]
    lj = json.loads((out / "look.json").read_text(encoding="utf-8"))
    parts.append(json.dumps({k: v for k, v in lj.items() if k not in ("exec_log",)}, separators=(", ", ": ")))
    for a in lj.get("artifacts", []):
        p = Path(a["path"])
        if a["kind"] in ("text", "json") and p.exists() and p.stat().st_size < 1_000_000:
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts), lj


def contract(out, lj):
    """The LOOK.md v2 contract: title, identity line, sections in order, footer line, step 1 within ~1,000 tokens, Read-next files exist."""
    import dl_util
    md = (out / "LOOK.md").read_text(encoding="utf-8")
    if lj.get("tier") == "direct":
        return None if re.match(r"Read this file directly: .+ \(~\d+ tokens\)", md) else "direct look lacks the one-line verdict"
    if not md.startswith("# "):
        return "no title line"
    lines = md.splitlines()
    if not re.search(r"sha [0-9a-f]{12}\b", lines[1]) or "folder:" not in lines[1]:
        return "identity line lacks sha or folder"
    plain = re.sub(r"```.*?```", "", md, flags=re.S)
    heads = re.findall(r"^## (.+?)\s*$", plain, re.M)
    base = [re.sub(r" \(continued\)$", "", h) for h in heads]
    order = [SECTIONS.index(h) for h in base if h in SECTIONS]
    if len(order) != len(base) or order != sorted(order):
        return f"sections {heads}"
    if not [x for x in lines if x.strip()][-1].startswith("-- chunks"):
        return "no footer line"
    n = dl_util.est_tokens(md)
    if n > STEP1_MAX:
        return f"step 1 is {n} tokens (limit {STEP1_MAX})"
    rn = plain.split("## Read next")[1] if "## Read next" in plain else ""
    rn = re.split(r"\n## |\n-- chunks", rn)[0]
    for m in re.finditer(r"^- `([^`]+)`:", rn, re.M):
        if m.group(1).startswith(("--", "python")):
            continue
        p = out / m.group(1)
        if not p.exists() or p.stat().st_size == 0:
            return f"Read next path missing or empty: {m.group(1)}"
    return None

def image_problem(lj):
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for a in lj.get("artifacts", []):
        if a["kind"] != "image":
            continue
        wh = core.image_size(a["path"])
        if Image and not wh:
            try:
                with Image.open(a["path"]) as im:
                    wh = im.size
            except Exception as e:
                return f"{Path(a['path']).name} does not open: {e}"
        if wh is None:
            return f"{Path(a['path']).name} unreadable"
        if max(wh) > core.MAX_IMG_EDGE:
            return f"{Path(a['path']).name} is {wh[0]}x{wh[1]} (limit {core.MAX_IMG_EDGE})"
    return None


def view_problem(out):
    v = out / "view.html"
    if not v.exists():
        return "view.html missing"
    from urllib.parse import unquote, urlparse
    html = v.read_text(encoding="utf-8")
    for m in re.finditer(r'(?:src|href)="([^"]+)"', html):
        ref = m.group(1)
        if ref.startswith(("#", "data:")):
            continue
        if ref.startswith("file:"):
            p = Path(unquote(urlparse(ref).path.lstrip("/") if re.match(r"file:///[A-Za-z]:", ref) else urlparse(ref).path))
        elif re.match(r"[a-z]+:", ref):
            return f"external reference {ref[:40]}"
        else:
            p = out / unquote(ref)
        if not p.exists():
            return f"missing file {ref[:60]}"
    return None


def run_one(name, spec, fx, tier, work):
    out = work / "out" / tier / name.replace("/", "_")
    cwd = work / "cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(LOOK), str(fx / name), "--out", str(out), "--fresh"] + (["--no-tools"] if tier == "bare" else []) + spec.get("args", [])
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(cwd))
    return r, time.time() - t0, out


def check_facts(spec, hay, lj, tier):
    """-> (found, skip_ok, missing[], total) for the seeded facts under the rules of the tier."""
    found = skip_ok = 0
    missing = []
    rows = [s for s in lj.get("steps", []) if s["status"] in ("skipped", "failed")]
    for f in spec.get("facts", []):
        needs = f.get("needs", [])
        ok = re.search(f["re"], hay, re.I | re.S) is not None
        reach = not needs or (tier != "bare" and all(available(n) for n in needs))
        if ok:
            found += 1
        elif not reach and any(r["tool"].lower() in [n.lower() for n in needs] and r["install"] for r in rows):
            skip_ok += 1
        else:
            missing.append(f["id"])
    return found, skip_ok, missing


def main(argv):
    ap = argparse.ArgumentParser(prog="look.py selftest")
    ap.add_argument("--tier", default="both", choices=("full", "bare", "both"))
    ap.add_argument("--fixtures")
    ap.add_argument("--only", default="")
    ap.add_argument("--keep", help="keep the outputs in this folder")
    ap.add_argument("--json", action="store_true")
    o = ap.parse_args(argv)
    fx_root = find_fixtures(o.fixtures)
    if not fx_root:
        print("selftest needs the fixtures: run it from a Sigmaskills checkout (test/sigmadeeplook/) or pass --fixtures DIR", file=sys.stderr)
        return 1
    truth = json.loads((fx_root / "truth.json").read_text(encoding="utf-8"))
    fx = fx_root / "fixtures"
    names = [n for n in truth if not n.startswith("_") and (not o.only or n in o.only.split(","))]
    tiers = ["bare", "full"] if o.tier == "both" else [o.tier]
    ok_all = True
    for tier in tiers:
        work = Path(o.keep) / tier if o.keep else Path(tempfile.mkdtemp(prefix="sdl-selftest-"))
        work.mkdir(parents=True, exist_ok=True)
        before = snapshot(fx)
        before_cwd = snapshot(work / "cwd") if (work / "cwd").exists() else {}
        res = {c: [0, 0] for c in CHECKS}
        facts_found = facts_skip = facts_total = bare_total = bare_found = avail_total = avail_found = 0
        fails = []
        per = {}
        for name in names:
            spec = truth[name]
            try:
                r, dt, out = run_one(name, spec, fx, tier, work)
            except Exception as e:
                fails.append((name, "run", repr(e)))
                for c in CHECKS:
                    res[c][1] += 1
                continue
            problems = {}
            if not (out / "look.json").exists():
                for c in CHECKS:
                    res[c][1] += 1
                fails.append((name, "no output", (r.stderr or r.stdout)[-300:]))
                continue
            hay, lj = hay_of(out)
            if r.returncode != spec.get("exit", 0):
                problems["exit code"] = f"exit {r.returncode}, expected {spec.get('exit', 0)}"
            if lj["type"] != spec["type"]:
                problems["type"] = f"{lj['type']} (expected {spec['type']})"
            c3 = contract(out, lj)
            if c3:
                problems["LOOK.md contract"] = c3
            found, skip_ok, missing = check_facts(spec, hay, lj, tier)
            for fb in spec.get("forbid", []):
                p = out / fb.get("in", "LOOK.md")
                if p.exists() and re.search(fb["re"], p.read_text(encoding="utf-8", errors="replace")):
                    missing.append("forbidden:" + fb["re"])
            for ap_ in spec.get("absent", []):
                if (out / ap_).exists():
                    missing.append("exists:" + ap_)
            for pp in spec.get("present", []):
                if tier == "bare" and pp.get("needs") or any(not available(n) for n in pp.get("needs", [])):
                    continue
                if not (out / pp["path"]).exists():
                    missing.append("absent:" + pp["path"])
            tot = len(spec.get("facts", []))
            facts_total += tot
            facts_found += found
            facts_skip += skip_ok
            for f in spec.get("facts", []):
                if not f.get("needs"):
                    bare_total += 1
                    bare_found += 1 if re.search(f["re"], hay, re.I | re.S) else 0
                elif tier != "bare" and all(available(n) for n in f["needs"]):
                    avail_total += 1
                    avail_found += 1 if re.search(f["re"], hay, re.I | re.S) else 0
            if missing:
                problems["seeded facts"] = ", ".join(missing)
            ip = image_problem(lj)
            if ip:
                problems["image budget"] = ip
            fx_inside = [e for e in lj.get("exec_log", []) if str(fx).lower() in str(e).lower()]
            canary = list(fx.rglob("CANARY")) + list((work / "cwd").rglob("CANARY"))
            if fx_inside or canary:
                problems["nothing executed"] = f"{fx_inside or canary}"
            if lj.get("network_attempts"):
                problems["no network"] = f"{lj['network_attempts']} attempts"
            if dt > LIMIT[tier]:
                problems["time"] = f"{dt:.1f}s > {LIMIT[tier]}s"
            vp = view_problem(out)
            if vp:
                problems["view.html"] = vp
            for c in CHECKS:
                res[c][0 if c not in problems else 1] += 1
            per[name] = (r.returncode, round(dt, 1), lj["tier"], f"{found}+{skip_ok}/{tot}")
            for c, why in problems.items():
                fails.append((name, c, why))
        after = snapshot(fx)
        after_cwd = snapshot(work / "cwd") if (work / "cwd").exists() else {}
        strays = [k for k in set(before) | set(after) if before.get(k) != after.get(k)] + [k for k in set(before_cwd) | set(after_cwd) if before_cwd.get(k) != after_cwd.get(k)]
        res["no stray writes"] = [len(names), 0] if not strays else [0, len(strays)]
        if strays:
            fails.append(("(all)", "no stray writes", ", ".join(strays[:5])))
        print(f"\n## selftest, tier {tier}: {len(names)} fixtures\n")
        print("| # | check | pass | fail |\n|---|---|---|---|")
        for i, c in enumerate(CHECKS, 1):
            print(f"| {i} | {c} | {res[c][0]} | {res[c][1]} |")
        rate = lambda a, b: f"{100 * a / b:.0f} %" if b else "n/a"
        print(f"\nseeded facts: {facts_found} found + {facts_skip} shown as Not-looked-at rows of {facts_total} "
              f"(found only: {rate(facts_found, facts_total)}); stdlib-reachable facts found {bare_found}/{bare_total} ({rate(bare_found, bare_total)})"
              + (f"; facts whose tools are present found {avail_found}/{avail_total} ({rate(avail_found, avail_total)})" if tier != "bare" else ""))
        for name, row in per.items():
            print(f"  {name:<14} exit {row[0]} {row[1]:>5}s tier {row[2]:<7} facts {row[3]}")
        for name, c, why in fails:
            print(f"FAIL {name}: {c}: {why}")
        tier_ok = not fails and bare_found == bare_total and (tier == "bare" or avail_found == avail_total or avail_found / max(1, avail_total) >= 0.95)
        print(f"RESULT {tier}: {'PASS' if tier_ok else 'FAIL'}")
        ok_all = ok_all and tier_ok
        if not o.keep:
            shutil.rmtree(work, ignore_errors=True)
    return 0 if ok_all else 1
