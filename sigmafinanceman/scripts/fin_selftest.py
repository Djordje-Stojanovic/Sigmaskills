"""Offline self-test: a fictional company (Sample Co), every model against an independent answer, every writer, and, when
LibreOffice is installed, every workbook recalculated and compared with the Python numbers. Prints PASS or FAIL per case."""
import json
import tempfile
import xml.dom.minidom
from pathlib import Path

import fin_models as F
import fin_report as RP
import fin_svg as S

ENDS = ["2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31", "2026-12-31"]


def sample(flat=False):
    """Sample Co: $m figures written in dollars, as SEC facts are. flat=True gives a no-growth company with a known DCF answer."""
    rev = [1000, 1000, 1000, 1000, 1000] if flat else [800, 880, 950, 1030, 1100]
    k = lambda xs: {e: x * 1e6 for e, x in zip(ENDS, xs)}
    r = lambda share: [x * share for x in rev]
    ann = {"revenue": k(rev), "cogs": k(r(0.4)), "gross_profit": k(r(0.6)), "rnd": k(r(0.1)), "sga": k(r(0.2)), "ebit": k(r(0.2)),
           "interest": k([10] * 5), "pretax": k([x - 10 for x in r(0.2)]), "tax": k([(x - 10) * 0.25 for x in r(0.2)]),
           "net_income": k([(x - 10) * 0.75 for x in r(0.2)]), "eps": {e: v for e, v in zip(ENDS, [1.5, 1.7, 1.8, 2.0, 2.1])},
           "shares_diluted": k([100] * 5), "da": k(r(0.05)), "sbc": k(r(0.02)), "cfo": k(r(0.2)), "capex": k(r(0.05)),
           "dividends": k(r(0.03)), "buybacks": k([0] * 5), "cash": k([200] * 5), "st_investments": k([0] * 5), "receivables": k(r(0.1)),
           "inventory": k(r(0.05)), "current_assets": k(r(0.5)), "ppe": k(r(0.6)), "assets": k(r(1.5)), "payables": k(r(0.05)),
           "current_liabilities": k(r(0.25)), "debt_current": k([20] * 5), "debt_noncurrent": k([180] * 5), "short_borrowings": k([0] * 5),
           "liabilities": k(r(0.7)), "equity": k(r(0.8)), "retained_earnings": k(r(0.5))}
    if flat:
        ann["capex"] = ann["da"]
    f = {"ticker": "SMPL", "name": "Sample Co", "cik": 0, "source": "fixture", "fiscal_year_ends": ENDS, "annual": ann,
         "tags": {c: "fixture" for c in ann}, "quarters": {}, "ytd": {}, "shares_cover": 100e6, "last_10k": "2027-02-15",
         "market": {"price": 20.0, "low_52w": 15.0, "high_52w": 25.0, "beta": 1.0, "beta_months": 60, "source": "fixture", "price_time": "2027-03-01"},
         "rf": 0.04, "rf_date": "2027-03-01", "rf_source": "fixture"}
    f["ltm"] = {c: ann[c][ENDS[-1]] for c in ("revenue", "ebit", "da", "net_income")}
    f["ltm"]["_asof"] = ENDS[-1]
    q = {}
    for c in ("revenue", "gross_profit", "ebit", "net_income", "eps", "cfo"):
        q[c] = {}
        for y, e in enumerate(ENDS[-3:]):
            yr = int(e[:4])
            for qi, md in enumerate(("03-31", "06-30", "09-30")):
                q[c][f"{yr}-{md}"] = ann[c][e] / 4 * (1 + 0.01 * qi)
    f["quarters"] = q
    return f


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
    return ok


def run():
    ok = True
    # 1. DCF against a hand-computed answer: no growth, capex = D&A, no working capital
    f = sample(flat=True)
    a = F.dcf_inputs(f, {"growth_y1": 0.0, "terminal_g": 0.0, "nwc_pct": 0.0})
    r = F.dcf(a, wacc=0.10)
    fcf = 1000 * 0.2 * (1 - a["tax_rate"]["value"])
    ev = sum(fcf / 1.1 ** (i - 0.5) for i in range(1, 6)) + fcf / 0.10 / 1.1 ** 4.5
    ok &= check("DCF equals the hand-computed value", abs(r["ev"] - ev) < 1e-6, f"EV {r['ev']:.3f} vs {ev:.3f}")
    f = sample()
    a = F.dcf_inputs(f)
    base = F.dcf(a)
    ws, gs, grid = F.dcf_grid(a)
    ok &= check("DCF sensitivity centre is the base case", abs(grid[2][2] - base["value_per_share"]) < 1e-9)
    ok &= check("DCF grid falls as WACC rises", all(grid[i][2] > grid[i + 1][2] for i in range(4)))
    # 2. LBO
    la = F.lbo_inputs(f)
    lr = F.lbo(la)
    es, xs, lg = F.lbo_grid(la)
    ok &= check("LBO sensitivity centre is the base IRR", abs(lg[2][2] - lr["irr"]) < 1e-12, F.pct(lr["irr"]))
    ok &= check("LBO debt never negative", min(x["debt"] for x in lr["rows"]) >= 0)
    # 3. three statements balance
    m = F.three_statement(f, F.three_inputs(f))
    worst = max(abs(x["check"]) for x in m["projection"])
    ok &= check("Three-statement balance sheet balances", worst < 1e-6, f"largest gap {worst:.2e}")
    # 4. quartiles = Excel QUARTILE.INC
    q = F.quartiles([1, 2, 3, 4])
    ok &= check("Quartiles match Excel QUARTILE.INC", (q["q1"], q["median"], q["q3"]) == (1.75, 2.5, 3.25))
    # 4b. a concept whose tag changed over the years: each period takes the first tag that has it (MSFT interest: 2024 on a new tag)
    import fin_data as D
    fy = lambda s, e, v, filed: {"start": s, "end": e, "val": v, "form": "10-K", "filed": filed}
    gaap = {"InterestExpense": {"units": {"USD": [fy("2022-07-01", "2023-06-30", 5, "2023-07-30"), fy("2023-07-01", "2024-06-30", 6, "2024-07-30")]}},
            "InterestExpenseNonoperating": {"units": {"USD": [fy("2023-07-01", "2024-06-30", 9, "2024-07-30"), fy("2024-07-01", "2025-06-30", 7, "2025-07-30")]}}}
    vals, tag = D.series(gaap, "interest", "fy")
    ok &= check("A concept merges its tags per period, the first tag wins", vals == {"2023-06-30": 5, "2024-06-30": 6, "2025-06-30": 7}
                and tag == "InterestExpense, InterestExpenseNonoperating", f"{vals} via {tag}")
    # 5. budget (the prototype household: 3,600 net, 700 left)
    hh = {"net_income_monthly": 3600, "emergency_fund": 5000, "currency": "EUR", "lines": [
        {"name": "Rent", "amount": 1200, "bucket": "needs"}, {"name": "Food", "amount": 450, "bucket": "needs"},
        {"name": "Transport", "amount": 150, "bucket": "needs"}, {"name": "Going out", "amount": 400, "bucket": "wants"},
        {"name": "Subscriptions", "amount": 100, "bucket": "wants"}, {"name": "Savings plan", "amount": 600, "bucket": "savings"}]}
    b = F.budget(hh)
    ok &= check("Budget leaves 700", abs(b["left"] - 700) < 1e-9)
    # 6. writers and (if LibreOffice is here) the recalculated workbooks
    import fin_pptx
    import fin_xlsx as X
    import finman
    out = Path(tempfile.mkdtemp(prefix="finman-selftest-"))
    peers = []
    for i, scale in enumerate((0.8, 1.2, 1.5)):
        p = sample()
        p["ticker"], p["market"] = f"PEER{i}", dict(p["market"], price=20.0 * scale)
        peers.append(p)
    args = type("A", (), {"set": None})()
    cache = {}
    lo = finman.soffice()
    for kind in finman.KINDS:
        rep, xl = finman.run_company(kind, f, args, peers, cache)
        files = finman.write_outputs(rep, f"smpl-{kind}", out, {"xlsx", "pptx", "svg", "html"}, xl)
        good = all(Path(x).stat().st_size > 0 for x in files) and len(files) >= 3
        for x in files:
            if x.endswith(".svg"):
                xml.dom.minidom.parse(x)
        ok &= check(f"{kind}: xlsx, pptx, svg and html written", good, f"{len(files)} files")
        if lo:
            cells = json.loads((out / f"smpl-{kind}.cells.json").read_text())
            expect = {}
            if kind == "dcf":
                expect = {cells["value_per_share"]: cache["dcf"][1]["value_per_share"]}
            if kind == "lbo":
                expect = {cells["irr"]: lr["irr"]}
            if kind == "three":
                expect = {cells["ni_last"]: m["projection"][-1]["net_income"]}
            good, lines = finman.audit(out / f"smpl-{kind}.xlsx", expect)
            ok &= check(f"{kind}: workbook recalculates with no errors, checks TRUE, cells = Python", good, lines[0])
    rep = RP.budget_report(b)
    files = finman.write_outputs(rep, "budget", out, {"xlsx", "pptx", "svg", "html"}, lambda p: X.budget_book(b, p))
    ok &= check("budget: files written", len(files) >= 4)
    if lo:
        good, lines = finman.audit(out / "budget.xlsx", {"Budget!" + json.loads((out / "budget.cells.json").read_text())["left"].split("!")[1]: 700.0})
        ok &= check("budget: workbook recalculates, left over = 700", good, lines[0])
    else:
        print("SKIP  workbook recalculation (LibreOffice not installed)")
    page = (out / "smpl-dcf.html").read_text(encoding="utf-8")
    ok &= check("HTML leads with the answer", page.index('class="hero"') < page.index("<table"))
    print("PASS" if ok else "FAIL", f"(files in {out})")
    return 0 if ok else 1
