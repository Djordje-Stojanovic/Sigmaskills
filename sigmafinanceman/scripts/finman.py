#!/usr/bin/env python3
"""sigmafinanceman: finance models from public filings, as Excel (live formulas), slides, SVG charts and an HTML page.

  python finman.py dcf MSFT [--set growth_y1=0.12 --set terminal_g=0.02] [--out DIR] [--formats xlsx,pptx,svg,html]
  python finman.py lbo CROX | comps MSFT --peers AAPL,GOOGL,META | three MSFT | ratios MSFT | analyze MSFT | score MSFT | earnings MSFT
  python finman.py budget household.json           a personal monthly budget (format: references/budget.md)
  python finman.py dividend KO                     dividend discount model, dividend safety, owner earnings, buybacks, quality
  python finman.py venture deal.json               cap table with SAFEs, notes and pool; rounds; exit waterfall; VC method; power law
  python finman.py purchase gpu.json               buy vs lease vs rent, total cost, payback, NPV/IRR, depreciation (vast.ai rent live)
  python finman.py property flat.json              rent vs buy, mortgage, cap rate, cash-on-cash, the 1 % rule (FRED mortgage rate)
  python finman.py asset GC=F --peers SI=F         gold, commodities, crypto: real return, drawdowns, hold ranges, a ratio
  python finman.py collectible card.json           sold comparables, grading premium, fees, liquidity (pokemontcg.io prices live)
  python finman.py bond bond.json | fund VOO --peers ^SP500TR --set fee=0.0003
  python finman.py all MSFT --peers AAPL,GOOGL     every company model in one go
  add --principles "Buffett P1,Munger P3"          names the masters' principles the run applied in every output
  python finman.py audit FILE.xlsx                 recalculate in LibreOffice, list formula errors and the Checks sheet
  python finman.py render FILE.xlsx|FILE.pptx      PDF + PNG pages (LibreOffice + pdftoppm) to look at the file
  python finman.py fetch MSFT                      the normalized facts as JSON
  python finman.py selftest                        offline check of every model and writer (no network)

Data: SEC EDGAR company facts (10-K and 10-Q), Yahoo chart prices, FRED DGS10. Set SEC_USER_AGENT="name email" (SEC asks for it).
Needs Python 3.10+, openpyxl and python-pptx. LibreOffice is optional (audit, render).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fin_models as F  # noqa: E402
import fin_report as RP  # noqa: E402
import fin_svg as S  # noqa: E402

PRINCIPLES = []   # tags such as "Buffett P1", set by --principles; every writer prints them

KINDS = ("dcf", "lbo", "comps", "three", "ratios", "analyze", "score", "earnings", "dividend")
DCF_SETS = ("price", "beta", "rf", "erp", "debt", "cash", "shares", "minority", "preferred", "investments", "terminal_g")   # carried to score and comps
FETCH_SETS = ("cik",)   # read before the fetch, not model inputs
FILE_KINDS = ("venture", "purchase", "property", "collectible", "bond")   # read a JSON file of inputs
TICKER_KINDS = ("asset", "fund")                                         # price history only, no filings


def parse_sets(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[k.strip()] = float(v)
    return out


def parse_principles(text):
    """`--principles "Buffett P1,Munger P3"`: each tag must name a principle in references/masters.md."""
    tags = [t.strip() for t in (text or "").split(",") if t.strip()]
    if not tags:
        return tags
    masters = (HERE.parent / "references" / "masters.md").read_text(encoding="utf-8")
    known = set(re.findall(r"^- (\w+ P\d+)\.", masters, re.M))
    bad = [t for t in tags if t not in known]
    if bad:
        raise SystemExit(f"unknown principle: {', '.join(bad)} (tags are in references/masters.md, for example Buffett P1)")
    return tags


def write_outputs(rep, stem, out, formats, xlsx_fn=None):
    out.mkdir(parents=True, exist_ok=True)
    if PRINCIPLES:
        rep["notes"] = list(rep.get("notes", [])) + ["Principles applied: " + ", ".join(PRINCIPLES)]
    files = []
    if "xlsx" in formats and xlsx_fn:
        p, cells = xlsx_fn(str(out / f"{stem}.xlsx"))
        files.append(p)   # cells.json carries the Python numbers that `audit` compares with the recalculated cells
        (out / f"{stem}.cells.json").write_text(json.dumps(cells, indent=1), encoding="utf-8")
    if "pptx" in formats:
        import fin_pptx
        files.append(fin_pptx.deck(rep, str(out / f"{stem}.pptx")))
    if "svg" in formats:
        for i, c in enumerate(rep.get("charts", []), start=1):
            p = out / f"{stem}-chart{i}.svg"
            p.write_text(S.chart_svg(c), encoding="utf-8")
            files.append(str(p))
    if "html" in formats:
        p = out / f"{stem}.html"
        p.write_text(S.page(rep), encoding="utf-8")
        files.append(str(p))
    (out / f"{stem}.report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return files


def run_company(kind, f, args, peers=None, cache=None):
    """One model for one company: returns (report, xlsx builder)."""
    import fin_xlsx as X
    cache = cache if cache is not None else {}
    o = {k: v for k, v in parse_sets(args.set).items() if k not in FETCH_SETS}
    if kind in ("dcf", "score", "comps") and "dcf" not in cache:
        a = F.dcf_inputs(f, {k: v for k, v in o.items() if k in DCF_SETS} if kind != "dcf" else o)
        r = F.dcf(a)
        if r["value_per_share"] is None:
            raise SystemExit(f"WACC {F.pct(r['wacc'], 2)} is not above terminal growth {F.pct(r['g'], 2)}: the growth formula has no finite "
                             "value. Pass a lower --set terminal_g= or a higher --set erp= / --set beta=")
        cache["dcf"] = (a, r, F.dcf_grid(a))
    if kind == "dcf":
        a, r, g = cache["dcf"]
        return RP.dcf_report(f, a, r, g), lambda p: X.dcf_book(f, a, p)
    if kind == "lbo":
        a = F.lbo_inputs(f, o)
        return RP.lbo_report(f, a, F.lbo(a), F.lbo_grid(a)), lambda p: X.lbo_book(f, a, p)
    if kind == "comps":
        c = F.comps(f, peers)
        g = cache["dcf"][2][2]
        inner = [g[i][j] for i in (1, 2, 3) for j in (1, 2, 3) if g[i][j] is not None]
        return RP.comps_report(c, (min(inner), max(inner))), lambda p: X.comps_book(c, p)
    if kind == "three":
        a = F.three_inputs(f, {k: v for k, v in o.items() if k not in ("price", "beta", "rf")})   # market inputs: no part of this model
        m = F.three_statement(f, a)
        return RP.three_report(f, a, m), lambda p: X.three_book(f, a, m, p)
    if kind == "ratios":
        return RP.ratios_report(f, F.ratios(f)), lambda p: X.ratios_book(f, p)
    if kind == "analyze":
        fl = F.red_flags(f)
        return RP.analysis_report(f, F.ratios(f), fl, F.altman_z(f), F.piotroski(f)), lambda p: X.analysis_book(f, fl, p)
    if kind == "score":
        v = cache["dcf"][1]["value_per_share"]
        sc = F.scorecard(f, v)
        return RP.score_report(f, sc, v), lambda p: X.score_book(f, sc, v, p)
    if kind == "earnings":
        e = F.earnings(f)
        return RP.earnings_report(f, e), lambda p: X.earnings_book(f, e, p)
    if kind == "dividend":
        import fin_assets as A
        if "history" not in f:
            import fin_data as D
            f["history"] = D.history(f["ticker"])
        return A.dividend_report(f, A.dividend(f, f["history"], o)), None
    raise SystemExit(f"unknown model: {kind}")


def live(x, value, source):
    """An input the user left out, filled from a live source."""
    return x if x is not None else {"value": value, "source": source}


def run_asset(cmd, args):
    """One model for an asset class that has no SEC filings. Returns (report, file stem)."""
    import fin_assets as A
    import fin_data as D
    o = parse_sets(args.set)
    if cmd in FILE_KINDS:
        data = json.loads(Path(args.target).read_text(encoding="utf-8"))
        stem = Path(args.target).stem
    if cmd == "venture":
        return A.venture_report(data, A.venture(data)), stem
    if cmd == "purchase":
        if data.get("discount_rate") is None:
            rf, day, url = D.risk_free()
            data["discount_rate"] = {"value": rf, "source": f"US 10-year Treasury {day} ({url.split('&')[0]})"}
        if data.get("rent_per_use") is None and data.get("gpu"):
            prices, url = D.gpu_rent(data["gpu"])
            if not prices:
                raise SystemExit(f"vast.ai lists no {data['gpu']} offers: set rent_per_use in {args.target}")
            data["rent_per_use"] = {"value": A.pctile(prices, 0.5), "source": f"median of {len(prices)} live vast.ai offers for one "
                                    f"{data['gpu']}, $/GPU-hour ({url.split('?')[0]})"}
        for k, v in o.items():
            data[k] = {"value": v, "source": "set by the user"}
        return A.purchase_report(data, A.purchase(data)), stem
    if cmd == "property":
        if data.get("mortgage_rate") is None:
            rows, url = D.fred("MORTGAGE30US", "2025-01-01")
            data["mortgage_rate"] = {"value": rows[-1][1] / 100, "source": f"Freddie Mac 30-year fixed, FRED MORTGAGE30US {rows[-1][0]}"}
        for k, v in o.items():
            data[k] = {"value": v, "source": "set by the user"}
        return A.property_report(data, A.property_model(data)), stem
    if cmd == "collectible":
        ref = None
        if data.get("pokemon"):
            cards, url = D.card_price(data["pokemon"])
            ref = [(f"{c['name']} {c['set']['name']} {k} {lab} ({c['tcgplayer'].get('updatedAt', '')})", v)
                   for c in cards for k, p in c.get("tcgplayer", {}).get("prices", {}).items()
                   for lab, v in p.items() if lab in ("low", "mid", "high", "market") and v]
            data.setdefault("sources", []).append(url.split("&q=")[0] + " (TCGplayer prices)")
        return A.collectible_report(data, A.collectible(data, ref)), stem
    if cmd == "bond":
        if data.get("treasury") is None:
            n = min((1, 2, 3, 5, 7, 10, 20, 30), key=lambda x: abs(x - data["years"]))
            rows, url = D.fred(f"DGS{n}", "2025-01-01")
            data["treasury"], data["treasury_source"] = rows[-1][1] / 100, f"FRED DGS{n} ({n}-year Treasury) {rows[-1][0]}"
        return A.bond_report(data, A.bond(data)), stem
    h = D.history(args.target)
    if cmd == "asset":
        cpi, url = D.fred("CPIAUCSL")
        ratio = D.history(args.peers) if args.peers else None
        r = A.no_yield(h, cpi, o, ratio)
        return A.no_yield_report(args.target, h, f"FRED CPIAUCSL to {cpi[-1][0]}", r, args.peers or None, o), args.target.lower()
    if cmd == "fund":
        if not args.peers or "fee" not in o:
            raise SystemExit("fund needs --peers BENCHMARK and --set fee=0.0003 (the expense ratio from the fact sheet)")
        b = D.history(args.peers)
        return A.fund_report(args.target, args.peers, h, A.fund(h, b, o["fee"])), args.target.lower() + "-fund"
    raise SystemExit(f"unknown asset class: {cmd}")


def soffice():
    if os.environ.get("FINMAN_NO_SOFFICE"):  # tests: skip the slow real LibreOffice recalculation
        return None
    for c in (shutil.which("soffice"), shutil.which("libreoffice"), r"C:\Program Files\LibreOffice\program\soffice.exe",
              "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if c and Path(c).exists():
            return c
    return None


def recalc(path, outdir):
    """LibreOffice opens the workbook, computes every formula and saves the cached values next to them."""
    exe = soffice()
    if not exe:
        raise SystemExit("LibreOffice not found: install it, or open the file in Excel (it recalculates on open).")
    prof = Path(tempfile.mkdtemp(prefix="lo-"))
    subprocess.run([exe, f"-env:UserInstallation=file:///{prof.as_posix().lstrip('/')}", "--headless", "--calc", "--convert-to", "xlsx",
                    "--outdir", str(outdir), str(path)], check=True, capture_output=True, timeout=180)
    return Path(outdir) / Path(path).name


def audit(path, expect=None):
    """Formula errors, the Checks sheet, and the cells that must equal the Python numbers: `expect`, else the "expect" map in the
    <stem>.cells.json written beside the workbook. A workbook with no Python numbers to compare says so. Returns (ok, lines)."""
    from openpyxl import load_workbook
    side = Path(path).with_suffix(".cells.json")
    if expect is None and side.exists():
        expect = json.loads(side.read_text(encoding="utf-8")).get("expect")
    tmp = Path(tempfile.mkdtemp(prefix="finaudit-"))
    rc = recalc(path, tmp)
    wb = load_workbook(rc, data_only=True)
    raw = load_workbook(path)
    errors, formulas = [], 0
    for ws in raw.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    formulas += 1
                    v = wb[ws.title][c.coordinate].value
                    if isinstance(v, str) and v.startswith("#") or v is None:
                        errors.append(f"{ws.title}!{c.coordinate} = {v} ({c.value[:60]})")
    lines = [f"{formulas} formulas, {len(errors)} errors"] + errors[:20]
    ok = not errors
    if "Checks" in wb.sheetnames:
        ws = wb["Checks"]
        for r in range(4, ws.max_row + 1):
            name, val = ws[f"A{r}"].value, ws[f"B{r}"].value
            if name:
                lines.append(f"check {'PASS' if val is True else 'FAIL'}: {name}")
                ok &= val is True
    for ref, want in (expect or {}).items():
        sh, cell = ref.split("!")
        got = wb[sh.strip("'")][cell].value
        same = isinstance(got, (int, float)) and abs(got - want) <= max(1e-6, abs(want) * 0.005)
        lines.append(f"cell {'PASS' if same else 'FAIL'}: {ref} = {got} (Python {want})")
        ok &= same
    if not expect:
        lines.append("cells: no Python numbers to compare (no <stem>.cells.json with an expect map beside the file)")
    return ok, lines


def render(path, outdir=None):
    exe = soffice()
    if not exe:
        raise SystemExit("LibreOffice not found")
    outdir = Path(outdir or Path(path).parent / "render" / Path(path).suffix.lstrip("."))
    outdir.mkdir(parents=True, exist_ok=True)
    prof = Path(tempfile.mkdtemp(prefix="lo-"))
    subprocess.run([exe, f"-env:UserInstallation=file:///{prof.as_posix().lstrip('/')}", "--headless", "--convert-to", "pdf", "--outdir",
                    str(outdir), str(path)], check=True, capture_output=True, timeout=180)
    pdf = outdir / (Path(path).stem + ".pdf")
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", "70", str(pdf), str(outdir / Path(path).stem)], check=True)
    return pdf


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=KINDS + FILE_KINDS + TICKER_KINDS + ("all", "budget", "fetch", "audit", "render", "selftest"))
    ap.add_argument("target", nargs="?")
    ap.add_argument("--peers", default="")
    ap.add_argument("--set", action="append", help="override an input: name=value (fractions for percentages)")
    ap.add_argument("--out", default="finman-out")
    ap.add_argument("--formats", default="xlsx,pptx,svg,html")
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--principles", default="", help='principles this run applied (tags in references/masters.md), e.g. "Buffett P1,Munger P3"')
    args = ap.parse_args(argv)
    PRINCIPLES[:] = parse_principles(args.principles)
    import fin_xlsx
    fin_xlsx.PRINCIPLES[:] = PRINCIPLES
    out, formats = Path(args.out), set(args.formats.split(","))
    if args.cmd == "selftest":
        import fin_selftest
        return fin_selftest.run()
    if args.cmd == "audit":
        ok, lines = audit(args.target)
        print("\n".join(lines))
        print("PASS" if ok else "FAIL")
        return 0 if ok else 1
    if args.cmd == "render":
        print(render(args.target))
        return 0
    if args.cmd == "budget":
        import fin_xlsx as X
        b = F.budget(json.loads(Path(args.target).read_text(encoding="utf-8")))
        files = write_outputs(RP.budget_report(b), "budget", out, formats, lambda p: X.budget_book(b, p))
        print("\n".join(files))
        return 0
    if args.cmd in FILE_KINDS + TICKER_KINDS:
        rep, stem = run_asset(args.cmd, args)
        files = write_outputs(rep, re.sub(r"[^a-z0-9-]+", "-", stem.lower()).strip("-"), out, formats - {"xlsx"})
        print(f"{args.cmd}: {rep['hero']['value']} {rep['hero']['label']}")
        print("  " + "\n  ".join(files))
        return 0
    import fin_data as D
    o = parse_sets(args.set)   # read before any fetch: a value the user set is never fetched, so an outage cannot stop the run
    has_market = args.cmd not in ("fetch", "all", "comps") and {"price", "beta"} <= set(o)
    f = D.company(args.target, args.years, with_market=not has_market, with_rf="rf" not in o, cik=int(o["cik"]) if "cik" in o else None)
    if has_market:
        f["market"] = {"price": o["price"], "beta": o["beta"], "currency": "USD", "price_time": __import__("datetime").date.today().isoformat(),
                       "source": "set by the user", "beta_months": "set", "low_52w": None, "high_52w": None}
    if "rf" in o:
        f["rf"], f["rf_date"], f["rf_source"] = o["rf"], "set by the user", "set by the user"
    if args.cmd == "fetch":
        print(json.dumps(f, indent=1, default=str))
        return 0
    peers = [D.company(p, args.years) for p in args.peers.split(",") if p] if args.peers else []
    kinds = KINDS if args.cmd == "all" else (args.cmd,)
    if "comps" in kinds and not peers:
        if args.cmd == "comps":
            raise SystemExit("comps needs --peers A,B,C")
        kinds = tuple(k for k in kinds if k != "comps")
    if args.cmd == "all" and not F.view(f)[2]("dividends"):   # no dividend paid: nothing for the dividend model to value
        kinds = tuple(k for k in kinds if k != "dividend")
    cache = {}
    for kind in kinds:
        rep, xl = run_company(kind, f, args, peers, cache)
        files = write_outputs(rep, f"{f['ticker'].lower()}-{kind}", out, formats, xl)
        print(f"{kind}: {rep['hero']['value']} {rep['hero']['label']}")
        print("  " + "\n  ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
