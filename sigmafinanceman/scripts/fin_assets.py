"""Models for every asset class beyond the DCF family: dividend stocks, startups and venture, purchases, real estate,
assets with no cash flows (gold, commodities, crypto), collectibles, bonds and funds.

Each model is a pure function of its inputs (no network: the CLI fetches the data and passes it in), and each has a
report builder that returns the same report structure as fin_report.py, so the page, the SVG charts and the deck draw it.
Inputs carry their source as {"value", "source"} where a number came from outside; money is in plain currency units here
(not millions), because a house, a GPU or a card is priced in units.
"""
import math
import statistics

import fin_models as F
from fin_report import T

pct, cur, div, clamp = F.pct, F.per_share, F.div, F.clamp


money0 = F.money


# ---------- shared maths ----------

def npv(rate, flows):
    """Flows at t = 0, 1, 2 ... periods; the first is today."""
    return sum(c / (1 + rate) ** t for t, c in enumerate(flows))


def bisect(fn, lo, hi, n=100):
    """The x in [lo, hi] where fn changes sign; None when it does not."""
    flo, fhi = fn(lo), fn(hi)
    if flo is None or fhi is None or flo * fhi > 0:
        return None
    for _ in range(n):
        mid = (lo + hi) / 2
        if (fn(mid) > 0) == (fhi > 0):
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def irr_roots(flows):
    """Every rate per period from -99 % to +100,000 % at which the NPV is zero.
    shortcut: two roots closer than one grid step (5 % apart in 1 + rate) can hide; fine for money flows."""
    grid = [-0.99 + 0.01 * i for i in range(99)] + [0.001 * 1.05 ** k for k in range(300)]
    f = lambda r: npv(r, flows)
    return [x for a, b in zip(grid, grid[1:]) if (x := bisect(f, a, b)) is not None and (f(a) != 0 or a == grid[0])]


def irr(flows, lo=None, hi=None):
    """The IRR when exactly one rate solves the flows; None when none or several do (irr_note says which)."""
    roots = irr_roots(flows)
    return roots[0] if len(roots) == 1 else None


def irr_note(flows, per_year=1):
    """'' when the IRR is unique; otherwise the reason it is blank, for the report."""
    roots = [(1 + x) ** per_year - 1 for x in irr_roots(flows)]
    if len(roots) == 1:
        return ""
    if not roots:
        return "IRR n/a: no rate makes these cash flows worth zero; read the NPV."
    return "IRR n/a: " + " and ".join(pct(x) for x in roots) + " both solve these cash flows; read the NPV."


def pmt(rate, n, pv):
    """Level payment that repays pv over n periods at rate per period."""
    return pv / n if rate == 0 else pv * rate / (1 - (1 + rate) ** -n)


def pctile(xs, p):
    xs = sorted(xs)
    return xs[0] if len(xs) == 1 else F._q(xs, p)


def I(v, source):
    return {"value": v, "source": source}


def val(d, k, default=None):
    x = d.get(k, default)
    return x["value"] if isinstance(x, dict) and "value" in x else x


def sources_table(inputs, title="Inputs and where they come from"):
    rows = [[k, v["value"], v["source"]] for k, v in inputs.items() if isinstance(v, dict) and "source" in v]
    return T(title, ["Input", "Value", "Source"], rows, ["text", "auto", "text"])


# ---------- 1. dividend stocks: DDM, dividend safety, owner earnings, capital return, quality, margin of safety ----------

def annual_dps(dividends, today, first_day=None):
    """Dividends per share by calendar year, plus the trailing twelve months. Every complete year from the first payment (or the
    first full year of the price history) to last year is listed; a year with no payment is 0, a suspension."""
    by = {}
    for d, a in dividends:
        by[int(d[:4])] = by.get(int(d[:4]), 0.0) + a
    year = int(today[:4])
    start = min(by) if by else year
    if first_day:   # a history that opens mid-year has a partial first year
        start = max(start, int(first_day[:4]) + (first_day[5:7] != "01"))
    full = {y: by.get(y, 0.0) for y in range(start, year)}
    y0 = f"{year - 1}{today[4:]}"
    ttm = sum(a for d, a in dividends if y0 < d <= today)
    return full, ttm


def streak(full):
    """Years in a row, counted back from the last full year, in which the dividend was paid and not cut (1 % slack for rounding)."""
    ys = sorted(full)
    n = 0
    for a, b in zip(reversed(ys[:-1]), reversed(ys[1:])):
        if full[b] <= 0 or full[b] < full[a] * 0.99:
            break
        n += 1
    return n


def gordon_g(ke, d0, price):
    """Growth for ever that the price implies: price = d0 (1 + g) / (ke - g) solved for g."""
    return (ke * price - d0) / (price + d0) if price else None


def ddm_value(d0, ke, g1, g2, years=5):
    """Two-stage dividend discount: `years` of g1 growth, then g2 for ever. None when ke <= g2."""
    if ke <= g2:
        return None
    pv, d = 0.0, d0
    for t in range(1, years + 1):
        d *= 1 + g1
        pv += d / (1 + ke) ** t
    return pv + d * (1 + g2) / (ke - g2) / (1 + ke) ** years


def dividend_inputs(f, h, o=None):
    o = o or {}
    _, hist, last = F.view(f)
    full, ttm = annual_dps(h["dividends"], f["market"]["price_time"], (h.get("dates") or [None])[0])
    ys = sorted(full)
    g5 = F.cagr(full[ys[-6]], full[ys[-1]], 5) if len(ys) >= 6 else None
    g10 = F.cagr(full[ys[-11]], full[ys[-1]], 10) if len(ys) >= 11 else None
    rf, beta = f["rf"], clamp(f["market"]["beta"] or 1.0, 0.6, 2.0)
    a = {"price": I(f["market"]["price"], f"Yahoo chart price {f['market']['price_time']}"),
         "dps_ttm": I(ttm, "dividends paid in the last 12 months, Yahoo chart dividend events"),
         "rf": I(rf, f"US 10-year Treasury, FRED DGS10 {f.get('rf_date', '')}"),
         "beta": I(beta, "5-year monthly beta vs the S&P 500, Yahoo chart, held 0.6-2.0"),
         "erp": I(0.05, "equity risk premium, market standard 5 %"),
         "g1": I(clamp(g5 if g5 is not None else 0.03, 0.0, 0.10), "5-year dividend-per-share CAGR, held 0-10 %"),
         "g2": I(min(0.025, rf), "long-run growth 2.5 %, never above the risk-free rate"),
         "years": I(5, "years of stage-1 growth")}
    for k, v in o.items():
        if k in a:
            a[k] = I(v, "set by the user")
    a["ke"] = I(o.get("ke", a["rf"]["value"] + a["beta"]["value"] * a["erp"]["value"]),
                "set by the user" if "ke" in o else "cost of equity = rf + beta x ERP (CAPM)")
    return a, {"full": full, "ttm": ttm, "g5": g5, "g10": g10, "streak": streak(full)}


DDM_STEP = 0.03   # bear and bull move stage-1 dividend growth by 3 points


def dividend(f, h, o=None):
    a, d = dividend_inputs(f, h, o)
    v = lambda k: a[k]["value"]
    base = ddm_value(v("dps_ttm"), v("ke"), v("g1"), v("g2"), int(v("years")))
    scen = [(n, v("g1") + s * DDM_STEP, ddm_value(v("dps_ttm"), v("ke"), v("g1") + s * DDM_STEP, v("g2"), int(v("years"))))
            for n, s in (("Bear", -1), ("Base", 0), ("Bull", 1))]
    kes, g2s = F.axis(v("ke"), 0.005), F.axis(v("g2"), 0.005)
    grid = [[ddm_value(v("dps_ttm"), k, v("g1"), g, int(v("years"))) for g in g2s] for k in kes]
    implied_g1 = bisect(lambda g: ddm_value(v("dps_ttm"), v("ke"), g, v("g2"), int(v("years"))) - v("price"), -0.5, 0.6)
    implied_g = gordon_g(v("ke"), v("dps_ttm"), v("price"))
    # dividend safety from the 10-K cash-flow statement
    ends, hist, last = F.view(f)
    R = F.ratios(f)
    debt, cash = F.debt_and_cash(last)
    ebitda = (last("ebit") or 0) + (last("da") or 0)
    fcf = (last("cfo") or 0) - (last("capex") or 0)
    divs, buys, ni = last("dividends") or 0, last("buybacks") or 0, last("net_income")
    shares = F.shares_now(f)[0]
    mcap = v("price") * shares if shares else None
    safety = [("Dividend under 75 % of free cash flow", div(divs, fcf), lambda x: 0 <= x <= 0.75, pct),
              ("Dividend under 75 % of net income", div(divs, ni), lambda x: 0 <= x <= 0.75, pct),
              ("Free cash flow covers the dividend 1.3x+", div(fcf, divs), lambda x: x >= 1.3, F.mult),
              ("Net debt / EBITDA 3.0x or less", div(debt - cash, ebitda), lambda x: x <= 3.0, F.mult),
              ("EBIT covers interest 5x+", div(last("ebit"), last("interest")), lambda x: x >= 5, F.mult),
              ("No cut in 10+ years", d["streak"], lambda x: x >= 10, lambda x: f"{x} years"),
              ("Revenue not shrinking (3 years)", F.cagr(hist("revenue")[-4], hist("revenue")[-1], 3) if len(ends) >= 4 else None,
               lambda x: x >= 0, pct)]
    safety = [{"test": n, "value": x, "shown": fm(x) if x is not None else "n/a", "pass": bool(x is not None and t(x))} for n, x, t, fm in safety]
    passed = sum(s["pass"] for s in safety)
    verdict = "looks safe" if passed >= 6 else "needs watching" if passed >= 4 else "looks at risk"
    # owner earnings (Buffett, 1986 letter): net income + D&A - maintenance capex; maintenance capex taken as min(capex, D&A)
    maint = min(last("capex") or 0, last("da") or 0)
    owner = (ni or 0) + (last("da") or 0) - maint
    owner_strict = (ni or 0) + (last("da") or 0) - (last("capex") or 0)
    # capital return by year
    sh = hist("shares_diluted")
    cap_rows = [[e[:4], hist("dividends")[i], hist("buybacks")[i], hist("sbc")[i], sh[i],
                 div(sh[i], sh[i - 1]) - 1 if i and sh[i - 1] else None] for i, e in enumerate(ends)]
    share_cagr = F.cagr(sh[0], sh[-1], len(sh) - 1)
    # quality and moat checks
    gms = [r["gross_margin"] for r in R if r["gross_margin"] is not None]
    roics = [r["roic"] for r in R if r["roic"] is not None]
    wacc = F.dcf(F.dcf_inputs(f))["wacc"]
    quality = [("ROIC above the cost of capital, 5-year average", statistics.mean(roics) - wacc if roics else None, lambda x: x > 0,
                lambda x: f"{pct(x)} spread"),
               ("Gross margin steady (st. dev. under 3 points)", statistics.pstdev(gms) if len(gms) > 1 else None, lambda x: x < 0.03, pct),
               ("Gross margin 40 %+ (pricing power)", gms[-1] if gms else None, lambda x: x >= 0.40, pct),
               ("Cash conversion (FCF / net income) 80 %+", R[-1]["cash_conversion"], lambda x: x >= 0.8, pct),
               ("Share count falling", share_cagr, lambda x: x < 0, lambda x: f"{pct(x)} a year"),
               ("Stock pay under 5 % of revenue", R[-1]["sbc_pct"], lambda x: x < 0.05, pct)]
    quality = [{"test": n, "value": x, "shown": fm(x) if x is not None else "n/a", "pass": bool(x is not None and t(x))} for n, x, t, fm in quality]
    dcf_v = F.dcf(F.dcf_inputs(f))["value_per_share"]
    return {"a": a, "d": d, "base": base, "scen": scen, "grid": (kes, g2s, grid), "implied_g1": implied_g1, "implied_g": implied_g,
            "safety": safety, "verdict": verdict, "passed": passed, "owner": owner, "owner_strict": owner_strict, "maint": maint,
            "mcap": mcap, "fcf": fcf, "ni": ni or 0, "da": last("da") or 0, "divs": divs, "buys": buys, "cap_rows": cap_rows, "share_cagr": share_cagr, "quality": quality,
            "wacc": wacc, "dcf_value": dcf_v, "yield": div(v("dps_ttm"), v("price")),
            "shareholder_yield": div(divs + buys, mcap), "buyback_yield": div(buys, mcap),
            "mos_ddm": 1 - v("price") / base if base else None, "mos_dcf": 1 - v("price") / dcf_v if dcf_v and dcf_v > 0 else None}


def streak_txt(d):
    """The history read is finite: a streak as long as the history says so."""
    return f"{d['streak']}+ years" if d["streak"] >= len(d["full"]) - 1 else f"{d['streak']} years"


def tests_table(title, tests):
    t = T(title, ["Test", "Value", "Result"], [[x["test"], x["shown"], "pass" if x["pass"] else "fail"] for x in tests], ["text", "text", "text"])
    t["status_col"] = 2
    return t


def dividend_report(f, r):
    a, d = r["a"], r["d"]
    v = lambda k: a[k]["value"]
    kes, g2s, grid = r["grid"]
    full = d["full"]
    ys = sorted(full)[-15:]
    sens = T("DDM value: cost of equity (rows) by long-run growth (columns)", ["Cost of equity"] + [pct(g) for g in g2s],
             [[pct(k)] + row for k, row in zip(kes, grid)], ["text"] + ["ps"] * len(g2s))
    sens["center"] = (2, 3)
    scen = T("Bear, base and bull (dividend discount model)", ["Case", "Dividend growth, years 1-5", "Value per share", "vs price"],
             [[n, g, x, (x / v("price") - 1) if x else None] for n, g, x in r["scen"]], ["text", "pct", "ps", "pct"],
             note=f"Bear and bull move the stage-1 dividend growth by {pct(DDM_STEP, 0)}; the cost of equity and the long-run growth stay.")
    rev = T("What the price implies", ["Input", "Model", "Price implies"],
            [["Dividend growth, years 1-5", v("g1"), r["implied_g1"]], ["Growth for ever (one stage, Gordon)", v("g2"), r["implied_g"]]],
            ["text", "pct", "pct"], note="Each row moves one input until the model value equals the price. Blank: no value in -50 % to 60 % does.")
    owner = T(f"Owner earnings, fiscal {f['fiscal_year_ends'][-1][:4]} ($m)", ["Line", "Value"],
              [["Net income", r["ni"]], ["Plus D&A", r["da"]],
               ["Less maintenance capex (the smaller of capex and D&A)", -r["maint"]], ["Owner earnings", r["owner"]],
               ["Owner earnings, all capex counted as maintenance", r["owner_strict"]], ["Market value of the shares", r["mcap"]],
               ["Owner-earnings yield", div(r["owner"], r["mcap"])]], ["text", "money"], totals=[3])
    owner["row_formats"] = {6: "pct"}
    cap = T("Capital return by fiscal year ($m)", ["Year", "Dividends", "Buybacks", "Stock pay", "Diluted shares (m)", "Share count change"],
            r["cap_rows"], ["text", "money", "money", "money", "num1", "pct"],
            note="Buybacks that do not shrink the share count only offset stock pay: count the shares, not the dollars.")
    hist_t = T("Dividend per share by calendar year", ["Year", "Dividend", "Growth"],
               [[str(y), full[y], (full[y] / full[y - 1] - 1) if (y - 1) in full and full[y - 1] else None] for y in ys], ["text", "ps", "pct"])
    mos = T("Margin of safety", ["Value from", "Value per share", "Margin of safety"],
            [["Dividend discount model, base", r["base"], r["mos_ddm"]], ["DCF, base (finman.py dcf)", r["dcf_value"], r["mos_dcf"]]],
            ["text", "ps", "pct"], note="Margin of safety = 1 - price / value. Want 25 % or more; negative means the price is above the value.")
    steps = [
        f"Start from the cash a shareholder gets: {cur(v('dps_ttm'))} a share in dividends over the last 12 months, a "
        f"{pct(r['yield'])} yield at {cur(v('price'))}.",
        f"Check the payer can afford it: the dividend took {pct(div(r['divs'], r['fcf']))} of free cash flow last year; "
        f"{r['passed']} of {len(r['safety'])} safety tests pass, so the dividend {r['verdict']}.",
        f"Grow it: {pct(v('g1'))} a year for {int(v('years'))} years (the 5-year history was {pct(d['g5'])}), then "
        f"{pct(v('g2'))} for ever.",
        f"Price the waiting: shareholders want {pct(v('ke'))} a year (risk-free {pct(v('rf'))} + beta {v('beta'):.2f} x "
        f"{pct(v('erp'))}).",
        f"Discount every future dividend to today and add them up: {cur(r['base'])} a share.",
        "Turn it round: " + (f"the price is right if the dividend grows {pct(r['implied_g1'])} a year for {int(v('years'))} years."
                             if r["implied_g1"] is not None else "no growth rate in range gives the price."),
        f"Look past the dividend: owner earnings (what the owners could take out and keep the business as it is) are "
        f"${money0(r['owner'])}m, a {pct(div(r['owner'], r['mcap']))} yield; buybacks add {pct(r['buyback_yield'])}.",
        f"Check the moat: {sum(q['pass'] for q in r['quality'])} of {len(r['quality'])} quality tests pass "
        f"(returns above the cost of capital, steady margins, cash that matches profit).",
        f"Compare: the DCF gives {cur(r['dcf_value'])}. The margin of safety is {pct(r['mos_ddm'])} on the dividend model "
        f"and {pct(r['mos_dcf'])} on the DCF; want 25 % or more.",
    ]
    inner = [x for row in grid[1:4] for x in row[1:4] if x]
    ff = [("Dividend model bear-bull", r["scen"][0][2], r["scen"][2][2]), ("Dividend model grid (inner 3x3)", min(inner), max(inner)),
          ("52-week range", f["market"]["low_52w"], f["market"]["high_52w"])]
    if r["dcf_value"] and r["dcf_value"] > 0:
        ff.append(("DCF base", r["dcf_value"], r["dcf_value"]))
    return {"kind": "dividend", "title": f"{f['name']} ({f['ticker']}) dividend and capital return",
            "subtitle": f"Dividends from Yahoo chart events; cash flows from the 10-K for fiscal {f['fiscal_year_ends'][-1][:4]}.",
            "hero": {"value": cur(r["base"]), "label": "Dividend discount value per share, base case",
                     "line": (f"{pct(r['mos_ddm'])} margin of safety at {cur(v('price'))}" if (r["mos_ddm"] or 0) >= 0 else
                              f"the price of {cur(v('price'))} is {F.mult(v('price') / r['base'])} this value")
                             + f"; yield {pct(r['yield'])}, the dividend {r['verdict']} ({r['passed']} of {len(r['safety'])} tests), "
                             f"{streak_txt(d)} without a cut."},
            "kpis": [("Yield", pct(r["yield"])), ("Shareholder yield", pct(r["shareholder_yield"])), ("FCF payout", pct(div(r["divs"], r["fcf"]))),
                     ("5y dividend growth", pct(d["g5"])), ("Years without a cut", streak_txt(d)), ("Price implies growth", pct(r["implied_g1"]))],
            "steps": steps,
            "tables": [tests_table("Dividend safety", r["safety"]), scen, rev, mos, owner, tests_table("Quality and moat", r["quality"]),
                       cap, sens, hist_t, sources_table(a)],
            "charts": [{"kind": "football", "title": "Value per share against the price", "rows": ff, "marker": ("Price", v("price"))},
                       {"kind": "bars", "title": "Dividend per share by year", "labels": [str(y) for y in ys],
                        "series": [("Dividend per share", [full[y] for y in ys], "total")], "fmt": "ps"},
                       {"kind": "bars", "title": "Dividends and buybacks ($m)", "labels": [x[0] for x in r["cap_rows"]],
                        "series": [("Dividends", [x[1] for x in r["cap_rows"]], "total"), ("Buybacks", [x[2] for x in r["cap_rows"]], "part")]}],
            "notes": ["The dividend model values only the cash paid out. Omitting future distributions through buybacks can understate "
                      "the payout value: read shareholder yield and the DCF beside it.",
                      "A yield far above the company's own history usually means the market expects a cut: read the safety table first.",
                      "Maintenance capex is not filed; the smaller of capex and D&A stands in for it, and the strict line counts all capex."],
            "sources": [f["source"], f["market"]["source"], f.get("rf_source", "")]}


# ---------- 2. startups and venture: cap table, SAFEs, notes, pool, rounds, waterfall, VC method, power law ----------

def _convert_price(sec, P, S0, X, C):
    """Conversion price of one SAFE or note at a priced round with price P.
    Post-money SAFE: cap over the capitalization with every converting security (YC post-money safe; the new pool top-up excluded).
    Pre-money SAFE and note: cap over the pre-money shares with the pool, without the converting securities."""
    disc = P * (1 - sec.get("discount", 0)) if sec.get("discount") else None
    if sec.get("cap"):
        base = S0 + C if sec.get("type", "post") == "post" and sec["kind"] == "safe" else S0 + X
        capp = sec["cap"] / base
        return min(P, capp, disc or P)   # YC: the holder gets the greater share count, so never above the round price
    return disc or P


def priced_round(S0, pool_free, rnd, converting=()):
    """One priced round. S0 = fully diluted shares before it; pool_free = unallocated pool shares before it.
    The new pool top-up and the converting securities sit in the pre-money (the usual term sheet), so the price is
    P = pre-money / (S0 + pool top-up + converted shares). Solved by fixed-point iteration."""
    X = C = 0.0
    conv = {}
    for _ in range(500):
        P = rnd["pre_money"] / (S0 + X + C)
        N = rnd["amount"] / P
        post = S0 + X + C + N
        X_new = max(0.0, rnd.get("pool_target", 0) * post - pool_free)
        conv = {s["name"]: s["owed"] / _convert_price(s, P, S0, X, C) for s in converting}
        C_new = sum(conv.values())
        if abs(X_new - X) < 1e-9 * post and abs(C_new - C) < 1e-9 * post:
            break
        X, C = X_new, C_new
    else:
        raise SystemExit(f"{rnd['name']}: the SAFE, note and pool terms have no solution at {rnd['pre_money']:,.0f} pre-money "
                         "(a cap below the money it holds?); check the terms")
    if abs(P * (S0 + X + C + N) - rnd["pre_money"] - rnd["amount"]) > 1e-6 * rnd["pre_money"]:
        raise SystemExit(f"{rnd['name']}: post-money is not pre-money + amount; check the terms")
    return {"price": P, "new_shares": N, "pool_add": X, "converted": conv, "post_shares": S0 + X + C + N,
            "post_money": P * (S0 + X + C + N), "pool_free": pool_free + X}


def venture(data):
    """data: see references/venture.md. Returns the cap table after each round, the waterfall at each exit, the VC method and
    the portfolio maths."""
    holders = {fd["name"]: {"shares": float(fd["shares"]), "class": "common", "invested": 0.0, "pref": 0.0, "participating": False}
               for fd in data["founders"]}
    pool_free = float(data.get("pool", 0))
    holders["Option pool"] = {"shares": pool_free, "class": "common", "invested": 0.0, "pref": 0.0, "participating": False}
    converting = [dict(s, kind="safe", owed=float(s["amount"])) for s in data.get("safes", [])]
    for n in data.get("notes", []):
        owed = n["amount"] * (1 + n.get("rate", 0) * n.get("months", 0) / 12)   # simple interest, as most notes accrue
        converting.append(dict(n, kind="note", owed=owed))
    tables, history = [], []
    snap = lambda label: tables.append((label, {k: dict(h) for k, h in holders.items()}))
    snap("Founding")
    def grant(n, when):
        if n > pool_free + 1e-6:
            raise SystemExit(f"options_granted {when} is more than the free pool ({pool_free:,.0f})")
        return n
    for i, rnd in enumerate(data["rounds"]):
        pool_free -= grant(rnd.get("options_granted", 0), f"before {rnd['name']}")
        S0 = sum(h["shares"] for h in holders.values())
        prot = {k: h for k, h in holders.items() if h.get("anti_dilution")}
        extra = dict.fromkeys(prot, 0.0)
        for _ in range(200):   # anti-dilution: protected series get more shares, which lowers the price, which ...
            r = priced_round(S0 + sum(extra.values()), pool_free, rnd, converting if i == 0 else ())
            cp = {k: h["price"] if r["price"] >= h["price"] else r["price"] if h["anti_dilution"] == "full" else
                  h["price"] * (S0 + rnd["amount"] / h["price"]) / (S0 + r["new_shares"]) for k, h in prot.items()}   # broad-based average
            new = {k: h["invested"] / cp[k] - h["shares"] for k, h in prot.items()}
            if all(abs(new[k] - extra[k]) < 1e-9 * S0 for k in prot):
                break
            extra = new
        else:
            raise SystemExit(f"{rnd['name']}: the anti-dilution adjustment does not settle")
        for k, h in prot.items():
            h["shares"] += extra[k]
            h["price"] = cp[k]
        pref_mult, part = rnd.get("liq_pref", 1.0), rnd.get("participating", False)
        holders["Option pool"]["shares"] += r["pool_add"]
        pool_free = r["pool_free"]
        for s in (converting if i == 0 else ()):
            sh = r["converted"][s["name"]]   # a SAFE or note converts into the round's preferred (shadow series), preference = cash paid
            basis = s["owed"] if s.get("pref_basis") == "balance" else float(s["amount"])   # the contract says which
            holders[s["name"]] = {"shares": sh, "class": rnd["name"], "invested": float(s["amount"]), "pref": basis * pref_mult,
                                  "participating": part, "price": s["owed"] / sh}
        holders[rnd["name"]] = {"shares": r["new_shares"], "class": rnd["name"], "invested": float(rnd["amount"]),
                                "pref": float(rnd["amount"]) * pref_mult, "participating": part, "price": r["price"],
                                "anti_dilution": rnd.get("anti_dilution")}
        history.append(dict(r, name=rnd["name"], pre_money=rnd["pre_money"], amount=rnd["amount"]))
        snap(rnd["name"])
    exits = sorted(data.get("exits") or [data.get("exit", 0) * f for f in (0.25, 1, 4)])
    pool_free -= grant(data.get("options_granted", 0), "after the last round")
    at_exit = {k: dict(h) for k, h in holders.items()}   # the free pool is cancelled at a sale: only granted options share
    at_exit["Option pool"].update(shares=holders["Option pool"]["shares"] - pool_free, strike=float(data.get("option_strike", 0)))
    falls = [(e, waterfall(at_exit, e)) for e in exits]
    return {"holders": holders, "pool_free": pool_free, "tables": tables, "rounds": history, "falls": falls, "exits": exits,
            "vc": vc_method(data, holders), "portfolio": portfolio(data.get("fund")) if data.get("fund") else None,
            "deck": deck_numbers(data.get("deck"), history[-1]["post_money"] if history else None) if data.get("deck") else None}


def waterfall(holders, exit_value):
    """Exit proceeds per holder, net of what option holders pay to exercise. Options with a `strike` exercise when the price per
    common share beats it; their strike cash joins the exit money."""
    live = dict(holders)
    for _ in range(len(holders) + 1):
        cash = sum(h["strike"] * h["shares"] for h in live.values() if h.get("strike"))
        out = _waterfall(live, exit_value + cash)
        dead = [k for k, h in live.items() if h.get("strike") and h["shares"] and out[k] < h["strike"] * h["shares"]]
        if not dead:
            break
        for k in dead:
            del live[k]
    return {k: out[k] - live[k].get("strike", 0) * live[k]["shares"] if k in live else 0.0 for k in holders}


def _waterfall(holders, exit_value):
    """Preferred classes are paid pari passu up to their preference; a non-participating class converts to common when that pays
    more; participating classes take the preference and then share as common.
    shortcut: no participation caps, pari passu seniority; upgrade when a term sheet says otherwise."""
    pref = {k: h for k, h in holders.items() if h["pref"] > 0}
    converted = set()
    for _ in range(len(pref) + 1):
        stack = sum(h["pref"] for k, h in pref.items() if k not in converted)
        paid_pref = min(stack, exit_value)
        rest = exit_value - paid_pref
        common_sh = sum(h["shares"] for k, h in holders.items() if h["pref"] == 0 or k in converted or h["participating"])
        pps = rest / common_sh if common_sh else 0
        flip = [k for k, h in pref.items() if k not in converted and not h["participating"] and pps * h["shares"] > h["pref"]]
        if not flip:
            break
        converted.add(min(flip, key=lambda k: pref[k]["pref"] / pref[k]["shares"]))   # the cheapest preference converts first
    out = {}
    for k, h in holders.items():
        p = 0.0
        if h["pref"] > 0 and k not in converted:
            p += h["pref"] / stack * paid_pref if stack else 0
        if h["pref"] == 0 or k in converted or h["participating"]:
            p += pps * h["shares"]
        out[k] = p
    return out


def vc_method(data, holders):
    """VC method: the most a fund can pay today for its target multiple, after the dilution still to come."""
    vc = data.get("vc")
    if not vc:
        return None
    # exit_value is equity; revenue x an EV multiple is enterprise value, so the net debt comes off first
    exit_v = vc.get("exit_value") or vc["exit_revenue"] * vc["exit_multiple"] - vc.get("exit_net_debt", 0)
    keep = 1 - vc.get("future_dilution", 0.0)
    inv = vc["investment"]
    post_max = exit_v * keep / vc["target_multiple"]
    own_need = inv * vc["target_multiple"] / (exit_v * keep)
    return {"exit_value": exit_v, "keep": keep, "investment": inv, "post_max": post_max, "pre_max": post_max - inv,
            "ownership_needed": own_need, "target_multiple": vc["target_multiple"], "years": vc.get("years", 6),
            "irr": vc["target_multiple"] ** (1 / vc.get("years", 6)) - 1}


# (share of financings, multiple): Correlation Ventures, 21,640 US financings 2004-2013 (65 % under 1x, 25 % 1-5x, 6 % 5-10x,
# 4 % 10x+). The multiple in each band is assumed: 0.2x, the midpoints 3x and 7.5x, and 20x for 10x+.
POWER_LAW = [(0.65, 0.2), (0.25, 3.0), (0.06, 7.5), (0.04, 20.0)]


def portfolio(fund):
    """Power-law portfolio maths: cheque size, the exit that returns the fund, the odds of holding at least one outlier."""
    size, n = fund["size"], fund["cheques"]
    invest = size * (1 - fund.get("fees_share", 0.15))
    first = invest * (1 - fund.get("reserve", 0.5)) / n
    own = fund.get("ownership_at_exit", 0.08)
    dist = [tuple(x) for x in fund.get("outcomes", POWER_LAW)]
    if abs(sum(p for p, _ in dist) - 1) > 1e-6:
        raise SystemExit("fund.outcomes: the shares of cheques must add up to 1")
    exp_mult = sum(p * m for p, m in dist)
    p_out = sum(p for p, m in dist if m >= fund.get("outlier_multiple", 10))
    no_outlier = sum(p * m for p, m in dist if m < fund.get("outlier_multiple", 10)) / (1 - p_out) if p_out < 1 else None   # given no outlier
    return {"size": size, "cheques": n, "invest": invest, "first_cheque": first, "return_fund_exit": size / own, "ownership": own,
            "p_one_outlier": 1 - (1 - p_out) ** n, "p_outlier": p_out, "expected_multiple": exp_mult,
            "multiple_without_outliers": no_outlier, "dist": dist}


def deck_numbers(d, post_money):
    """The numbers a pitch deck shows, recomputed and set against the usual bars."""
    rows = []
    add = lambda name, x, bar, ok, fm, why="n/a": rows.append({"test": name, "value": x, "shown": fm(x) if x is not None else why,
                                                               "bar": bar, "pass": None if x is None else bool(ok(x))})
    add("Runway (months of cash at the net burn)", div(d.get("cash"), d.get("burn_monthly")), "18+ months", lambda x: x >= 18, lambda x: f"{x:.0f}")
    grew = (d.get("net_new_arr") or 0) > 0
    add("Burn multiple (net burn / net new ARR)", div(d.get("burn_monthly", 0) * 12, d.get("net_new_arr")) if grew else None, "under 2x",
        lambda x: x < 2, F.mult, "n/a: ARR did not grow")
    seed = str(d.get("stage", "seed")).lower() in ("seed", "pre-seed")
    add("Price / ARR (post-money / ARR)", div(post_money, d.get("arr")), "under 30x at seed" if seed else "under 20x at Series A",
        lambda x: x < (30 if seed else 20), F.mult)
    add("Revenue growth, year on year", d.get("growth"), "2-3x a year early on", lambda x: x >= 1.0, pct)
    add("Gross margin", d.get("gross_margin"), "70 %+ for software", lambda x: x >= 0.7, pct)
    ltv = div((d.get("arpa_monthly") or 0) * (d.get("gross_margin") or 0), d.get("churn_monthly"))
    add("LTV / CAC", div(ltv, d.get("cac")), "3x+", lambda x: x >= 3, F.mult)
    add("CAC payback (months)", div(d.get("cac"), (d.get("arpa_monthly") or 0) * (d.get("gross_margin") or 0)), "under 18", lambda x: x < 18,
        lambda x: f"{x:.0f}")
    return rows


def venture_report(data, r):
    cur_ = data.get("currency", "USD")
    m = lambda x: f"{money0(x)}"
    last_label, last = r["tables"][-1]
    names = list(last)
    cols = ["Holder"] + [lab for lab, _ in r["tables"]]
    own = []
    for k in names:
        row = [k]
        for _, snap in r["tables"]:
            tot = sum(h["shares"] for h in snap.values())
            row.append(div(snap[k]["shares"], tot) if k in snap else None)
        own.append(row)
    own_t = T("Ownership after each round (fully diluted)", cols, own, ["text"] + ["pct"] * (len(cols) - 1))
    cap = T(f"Cap table after {last_label}", ["Holder", "Class", "Shares", "Ownership", "Price per share", "Invested", "Preference"],
            [[k, h["class"], h["shares"], div(h["shares"], sum(x["shares"] for x in last.values())), h.get("price"), h["invested"], h["pref"]]
             for k, h in last.items()], ["text", "text", "int", "pct", "ps", "money", "money"])
    rounds = T(f"Priced rounds ({cur_})", ["Round", "Pre-money", "Raised", "Post-money", "Price per share", "Pool top-up (shares)", "Converted (shares)"],
               [[x["name"], x["pre_money"], x["amount"], x["post_money"], x["price"], x["pool_add"], sum(x["converted"].values())] for x in r["rounds"]],
               ["text", "money", "money", "money", "ps", "int", "int"],
               note="The pool top-up and the converting SAFEs and notes sit in the pre-money, so they dilute the earlier holders, not the new money.")
    fall_rows = [[k] + [f[k] for _, f in r["falls"]] for k in names]
    fall_t = T(f"Exit waterfall ({cur_})", ["Holder"] + [f"Exit {m(e)}" for e in r["exits"]], fall_rows, ["text"] + ["money"] * len(r["exits"]),
               note=f"Preferences are paid first, pari passu; a non-participating holder converts to common when that pays more. The option "
                    f"pool is paid only for granted options, net of the strike; {m(r['pool_free'])} ungranted options are cancelled at the sale.")
    moic = T("Multiple on money by exit", ["Investor"] + [f"Exit {m(e)}" for e in r["exits"]],
             [[k] + [div(f[k], last[k]["invested"]) for _, f in r["falls"]] for k in names if last[k]["invested"]],
             ["text"] + ["x"] * len(r["exits"]))
    tables = [own_t, rounds, cap, fall_t, moic]
    founders = [fd["name"] for fd in data["founders"]]
    f_own = sum(div(last[k]["shares"], sum(x["shares"] for x in last.values())) for k in founders)
    mid = r["falls"][len(r["falls"]) // 2]
    steps = [f"Start with the founders: {', '.join(founders)} own 100 % of {m(sum(fd['shares'] for fd in data['founders']))} shares"
             + (f", with {m(data.get('pool', 0))} more set aside for staff options." if data.get("pool") else ".")]
    for s in data.get("safes", []) + data.get("notes", []):
        steps.append(f"{s['name']}: {cur_} {m(s['amount'])} in, no price yet; it converts at the first priced round at the cap of "
                     f"{m(s.get('cap'))}" + (f" or a {pct(s['discount'], 0)} discount, whichever is cheaper." if s.get("discount") else "."))
    for x in r["rounds"]:
        steps.append(f"{x['name']}: {cur_} {m(x['amount'])} at {m(x['pre_money'])} pre-money gives a post-money of {m(x['post_money'])} and a "
                     f"price of {cur(x['price'])} a share; the pool grows by {m(x['pool_add'])} shares first, inside the pre-money.")
    steps.append(f"After {last_label} the founders hold {pct(f_own)} together: every round, SAFE and pool top-up took a slice.")
    steps.append(f"At an exit of {m(mid[0])}, preferences are paid first; then the rest is split by shares. The founders get "
                 f"{m(sum(mid[1][k] for k in founders))}.")
    kpis = [("Founders after the last round", pct(f_own)), ("Post-money", m(r["rounds"][-1]["post_money"]) if r["rounds"] else "n/a"),
            ("Preference stack", m(sum(h["pref"] for h in last.values())))]
    vc = r["vc"]
    if vc:
        tables.append(T("VC method", ["Line", "Value"],
                        [["Exit equity value (EV less net debt)", vc["exit_value"]], ["Kept after later dilution", vc["keep"]], ["Target multiple", vc["target_multiple"]],
                         ["Investment", vc["investment"]], ["Ownership needed today", vc["ownership_needed"]],
                         ["Most the post-money can be", vc["post_max"]], ["Most the pre-money can be", vc["pre_max"]],
                         ["Target multiple as a yearly return", vc["irr"]]], ["text", "money"]))
        tables[-1]["row_formats"] = {1: "pct", 2: "x", 4: "pct", 7: "pct"}
        steps.append(f"VC method: to make {vc['target_multiple']:.0f}x on {m(vc['investment'])} from a {m(vc['exit_value'])} exit after "
                     f"{pct(1 - vc['keep'], 0)} more dilution, the fund needs {pct(vc['ownership_needed'])} today: a post-money of at most "
                     f"{m(vc['post_max'])}" + (f"; the {r['rounds'][0]['name']} post-money of {m(r['rounds'][0]['post_money'])} is "
                                               f"{'under' if r['rounds'][0]['post_money'] <= vc['post_max'] else 'over'} that." if r["rounds"] else "."))
        kpis.append(("VC method max post-money", m(vc["post_max"])))
    p = r["portfolio"]
    if p:
        tables.append(T("Portfolio maths (power law)", ["Line", "Value"],
                        [["Fund size", p["size"]], ["Cheques", p["cheques"]], ["Investable after fees", p["invest"]],
                         ["First cheque (rest held for follow-ons)", p["first_cheque"]], ["Ownership at exit per company", p["ownership"]],
                         ["Exit one company needs to return the fund", p["return_fund_exit"]], ["Chance one cheque is an outlier", p["p_outlier"]],
                         ["Chance the portfolio holds at least one", p["p_one_outlier"]], ["Expected gross multiple", p["expected_multiple"]],
                         ["Expected multiple of a cheque that is not an outlier", p["multiple_without_outliers"]]], ["text", "money"]))
        tables[-1]["row_formats"] = {1: "int", 4: "pct", 6: "pct", 7: "pct", 8: "x", 9: "x"}
        tables.append(T("Outcome shape used", ["Share of cheques", "Multiple"], [[a, b] for a, b in p["dist"]], ["pct", "x"],
                        note="Correlation Ventures, 21,640 US financings 2004-2013: 65 % returned under 1x, 4 % 10x or more. The multiple "
                             "inside each band is assumed. Set your own under fund.outcomes."))
        steps.append(f"Portfolio: with {p['cheques']} cheques and a {pct(p['p_outlier'])} chance each of an outlier, the odds of holding at "
                     f"least one are {pct(p['p_one_outlier'])}. A cheque that is not an outlier makes {F.mult(p['multiple_without_outliers'])} on average, gross: the "
                     "outliers are the return.")
    if r["deck"]:
        t = T("Pitch-deck numbers against the usual bars", ["Number", "Value", "Bar", "Result"],
              [[x["test"], x["shown"], x["bar"], "n/a" if x["pass"] is None else "pass" if x["pass"] else "fail"] for x in r["deck"]],
              ["text", "text", "text", "text"])
        t["status_col"] = 3
        tables.append(t)
    return {"kind": "venture", "title": f"{data.get('company', 'Startup')} cap table and exit waterfall",
            "subtitle": f"Inputs from {data.get('source', 'the user')}. Money in {cur_}.",
            "hero": {"value": pct(f_own), "label": f"founders' fully diluted ownership after {last_label}",
                     "line": f"At a {m(mid[0])} exit the founders take {m(sum(mid[1][k] for k in founders))} and the investors "
                             f"{m(sum(v for k, v in mid[1].items() if last[k]['invested']))}."},
            "kpis": kpis, "steps": steps, "tables": tables,
            "charts": [{"kind": "hbars", "title": f"Who owns what after {last_label}",
                        "rows": sorted([(k, div(h["shares"], sum(x["shares"] for x in last.values()))) for k, h in last.items()], key=lambda x: -x[1]),
                        "fmt": "pct"},
                       {"kind": "bars", "title": f"Proceeds by exit value ({cur_})", "labels": [m(e) for e in r["exits"]],
                        "series": [("Founders", [sum(f[k] for k in founders) for _, f in r["falls"]], "total"),
                                   ("Investors", [sum(v for k, v in f.items() if last[k]["invested"]) for _, f in r["falls"]], "part")]}],
            "notes": ["Only granted options (options_granted) share in an exit, net of option_strike; the free pool is cancelled. The cap "
                      "tables count the whole pool, as fully diluted tables do.",
                      "Preferences are pari passu (all preferred holders paid side by side); a senior stack pays the newest round first.",
                      "Post-money SAFEs (YC form) convert on the capitalization that includes every SAFE and note; pre-money SAFEs and notes on the shares before them."],
            "sources": [data.get("source", "the user's term sheets")]}


# ---------- 3. purchases and hardware: buy vs lease vs rent, TCO, payback, NPV/IRR, depreciation, resale ----------

def purchase(p, uses=None, rent=None, resale=None):
    """p: see references/purchase.md. Monthly model over the life; all three options deliver the same use.
    uses, rent and resale override the base case (the scenarios and the grid use them)."""
    life = int(p["life_years"] * 12)
    r_m = (1 + val(p, "discount_rate")) ** (1 / 12) - 1
    uses = val(p, "uses_per_month") if uses is None else uses
    rent = val(p, "rent_per_use") if rent is None else rent
    price = val(p, "price")
    resale = val(p, "resale_value") if resale is None else resale
    run_use = val(p, "running_per_use", 0) or 0         # power per hour, fuel per km: paid by the owner, inside the rent price
    fixed = val(p, "fixed_monthly", 0) or 0             # insurance, storage, upkeep: paid by the owner
    income = val(p, "income_monthly", 0) or 0           # earned only by owning (renting it out): it lowers the cost of buying
    annuity = sum(1 / (1 + r_m) ** t for t in range(1, life + 1))
    disc_end = 1 / (1 + r_m) ** life
    # one monthly series, buy minus rent: NPV, IRR, payback, break-even and the winner all read it
    saving = rent * uses - run_use * uses - fixed + income
    flows = [-price] + [saving] * (life - 1) + [saving + resale]
    rent_cost = rent * uses * annuity
    buy = rent_cost - npv(r_m, flows)
    lease = p.get("lease")
    lease_cost = None
    if lease:
        n, months = min(life, int(lease["months"])), int(lease["months"])
        lease_cost = lease.get("upfront", 0) + sum((lease["monthly"] + run_use * uses + fixed) / (1 + r_m) ** t for t in range(1, n + 1))
        lease_cost += sum(rent * uses / (1 + r_m) ** t for t in range(n + 1, life + 1))   # after the lease ends, rent covers the rest
        if months > life:   # still owed after the use ends: the quoted exit fee, or every remaining payment
            lease_cost += lease["termination_fee"] * disc_end if "termination_fee" in lease else                 sum(lease["monthly"] / (1 + r_m) ** t for t in range(life + 1, months + 1))
    m_irr = irr(flows)
    payback = next((t for t in range(1, life + 1) if saving * t >= price), None) if saving > 0 else None
    margin = rent - run_use
    breakeven = (price + (fixed - income) * annuity - resale * disc_end) / (margin * annuity) if margin > 0 else None
    return {"buy": buy, "rent": rent_cost, "lease": lease_cost, "npv_buy_vs_rent": npv(r_m, flows), "saving": saving,
            "irr": (1 + m_irr) ** 12 - 1 if m_irr is not None else None, "irr_note": irr_note(flows, 12),
            "payback_months": payback, "breakeven_uses": breakeven,
            "per_use_buy": buy / (uses * life) if uses else None, "life": life, "uses": uses, "rent_rate": rent, "resale": resale}


def depreciation(price, resale, years):
    """Declining balance from price to resale over the life: the same share of value is lost each year."""
    rate = 1 - (resale / price) ** (1 / years) if price > 0 and resale > 0 else 1.0
    return rate, [(y, price * (1 - rate) ** y) for y in range(years + 1)]


PURCHASE_CASES = (("Bear", 0.7, 0.5), ("Base", 1.0, 1.0), ("Bull", 1.2, 1.3))   # (rent price x, resale x)


def purchase_report(p, r):
    unit, c = p.get("unit", "use"), p.get("currency", "USD")
    price, life_y = val(p, "price"), int(p["life_years"])
    rate, dep = depreciation(price, val(p, "resale_value"), life_y)
    scen = [(n, purchase(p, rent=val(p, "rent_per_use") * k, resale=val(p, "resale_value") * s)) for n, k, s in PURCHASE_CASES]
    us = [r["uses"] * f for f in (0.5, 0.75, 1, 1.25, 1.5)]
    rs = [r["rent_rate"] * f for f in (0.6, 0.8, 1, 1.2, 1.4)]
    grid = [[purchase(p, uses=u, rent=x)["npv_buy_vs_rent"] for x in rs] for u in us]
    sens = T(f"Buying beats renting by ({c}, present value): {unit}s a month (rows) by rent per {unit} (columns)",
             [f"{unit.title()}s a month"] + [cur(x) for x in rs], [[f"{u:,.0f}"] + row for u, row in zip(us, grid)], ["text"] + ["money"] * 5)
    sens["center"] = (2, 3)
    opts = [["Buy (price + running costs - resale)", r["buy"]], [f"Rent ({cur(r['rent_rate'])} per {unit})", r["rent"]]]
    if r["lease"] is not None:
        opts.append([f"Lease ({cur(p['lease']['monthly'])} a month for {p['lease']['months']} months)", r["lease"]])
    tco = T(f"Total cost of the same use over {life_y} years ({c}, present value)", ["Option", "Cost"], opts, ["text", "money"],
            note=f"Discounted at {pct(val(p, 'discount_rate'))} a year. Lower is better.")
    sc = T("Bear, base and bull", ["Case", f"Rent per {unit}", "Resale", "Buying beats renting by", "Yearly return of buying", "Payback (months)"],
           [[n, x["rent_rate"], x["resale"], x["npv_buy_vs_rent"], x["irr"], x["payback_months"]] for n, x in scen],
           ["text", "ps", "money", "money", "pct", "auto"],
           note="Bear: rent prices 30 % lower and half the resale value (a new generation arrives). Bull: rent 20 % higher, resale 30 % higher.")
    dep_t = T(f"Value over time (declining balance, {pct(rate)} a year)", ["Year", "Value"], [[str(y), v] for y, v in dep], ["text", "money"])
    best = min([("buy", r["buy"]), ("rent", r["rent"])] + ([("lease", r["lease"])] if r["lease"] is not None else []), key=lambda x: x[1])[0]
    steps = [f"Price the purchase: {c} {money0(price)} today ({p['price']['source'] if isinstance(p['price'], dict) else 'the user'}).",
             f"Price the alternative: renting the same {unit} costs {cur(r['rent_rate'])} "
             f"({p['rent_per_use']['source'] if isinstance(p['rent_per_use'], dict) else 'the user'}).",
             f"Count the use: {r['uses']:,.0f} {unit}s a month for {life_y} years. Owning also costs "
             f"{cur(val(p, 'running_per_use', 0) or 0)} per {unit} to run and {money0(val(p, 'fixed_monthly', 0) or 0)} a month fixed.",
             f"Count what you get back: it loses about {pct(rate)} of its value a year and sells for {money0(val(p, 'resale_value'))} at the end.",
             f"Bring every cost to today at {pct(val(p, 'discount_rate'))} a year: buying costs {money0(r['buy'])}, renting {money0(r['rent'])}"
             + (f", leasing {money0(r['lease'])}." if r["lease"] is not None else "."),
             f"So {best} is cheapest. " + (f"The savings repay the price in {r['payback_months']} months" if r["payback_months"] else
                                          f"The savings alone do not repay the price within {r['life']} months; the resale does")
             + (f". Buying returns {pct(r['irr'])} a year against renting." if r["irr"] is not None else ". " + r["irr_note"]),
             f"Break-even use: buying wins above {r['breakeven_uses']:,.0f} {unit}s a month." if r["breakeven_uses"] else
             "Renting costs less per use than running your own: buying never wins on use alone."]
    return {"kind": "purchase", "title": f"Buy, lease or rent: {p.get('item', 'the purchase')}",
            "subtitle": f"Same use in each option over {life_y} years. Money in {c}.",
            "hero": {"value": money0(r["npv_buy_vs_rent"]), "label": f"{c} saved by buying instead of renting (present value)",
                     "line": f"{best.title()} is cheapest; "
                             + (f"the savings repay the price in {r['payback_months']} months" if r["payback_months"] else
                                "the savings alone never repay the price: the resale value decides it")
                             + f"; buying breaks even at {(r['breakeven_uses'] or 0):,.0f} {unit}s a month against {r['uses']:,.0f} planned."},
            "kpis": [("Cost per " + unit + " owned", cur(r["per_use_buy"])), ("Rent per " + unit, cur(r["rent_rate"])),
                     ("Payback", f"{r['payback_months']} months" if r["payback_months"] else "not from savings"), ("Return of buying", pct(r["irr"])),
                     ("Break-even use", f"{(r['breakeven_uses'] or 0):,.0f}/month")],
            "steps": steps, "tables": [tco, sc, sens, dep_t, sources_table({k: v for k, v in p.items() if isinstance(v, dict)})],
            "charts": [{"kind": "hbars", "title": f"Total cost over {life_y} years ({c}, present value)", "rows": [(o[0].split(" (")[0], o[1]) for o in opts],
                        "highlight": best.title()},
                       {"kind": "bars", "title": f"Value of the {p.get('item', 'item')} by year ({c})", "labels": [f"Y{y}" for y, _ in dep],
                        "series": [("Value", [v for _, v in dep], "total")]}],
            "notes": ["Buy and rent deliver the same use; a rent price already includes the owner's power, upkeep and margin.",
                      "Tax (depreciation write-offs, VAT) is left out; add it with income_monthly or a lower price when it applies.",
                      "The resale value is the biggest unknown for fast-moving hardware: read the bear case."] + ([r["irr_note"]] if r["irr_note"] else []),
            "sources": [v["source"] for v in p.values() if isinstance(v, dict) and "source" in v]}


# ---------- 4. real estate: mortgage, rent vs buy, cap rate, cash-on-cash, the 1 % rule ----------

def mortgage(principal, rate, years):
    n, r = years * 12, rate / 12
    pay = pmt(r, n, principal)
    bal, sched = principal, []
    for y in range(1, years + 1):
        i_y = p_y = 0.0
        for _ in range(12):
            i = bal * r
            i_y, p_y, bal = i_y + i, p_y + pay - i, bal - (pay - i)
        sched.append({"year": y, "interest": i_y, "principal": p_y, "balance": max(0.0, bal)})
    return pay, sched


def property_model(p, appreciation=None, rate=None):
    v = lambda k, d=None: val(p, k, d)
    price, horizon = v("price"), int(v("horizon_years", 10))
    rate = v("mortgage_rate") if rate is None else rate
    g = v("appreciation", 0.03) if appreciation is None else appreciation
    down = price * v("down_pct", 0.2)
    loan = price - down
    pay, sched = mortgage(loan, rate, int(v("loan_years", 30)))
    buy_cost = price * v("closing_buy_pct", 0.03)
    yearly_own = price * (v("tax_pct", 0.011) + v("upkeep_pct", 0.01)) + v("insurance_yearly", 1500) + 12 * v("hoa_monthly", 0)
    rent0 = v("rent_monthly")
    # investor view: the home is let at market rent
    gross = rent0 * 12
    noi = gross * (1 - v("vacancy", 0.05) - v("management", 0.08)) - yearly_own
    debt_service = pay * 12
    cash_in = down + buy_cost
    # rent vs buy over the horizon: both sides spend the same each year; the cheaper side invests the difference
    inv = v("invest_return", 0.06)
    renter = cash_in        # the renter invests the down payment and the buying costs
    owner_side = 0.0        # the owner's side portfolio when owning costs less than renting
    rows = []
    for y in range(1, horizon + 1):
        rent_y = rent0 * 12 * (1 + v("rent_growth", 0.03)) ** (y - 1)
        own_y = debt_service * (y <= v("loan_years", 30)) + yearly_own * (1 + g) ** (y - 1)
        renter = renter * (1 + inv) + max(0.0, own_y - rent_y)
        owner_side = owner_side * (1 + inv) + max(0.0, rent_y - own_y)
        home = price * (1 + g) ** y
        bal = sched[y - 1]["balance"] if y <= len(sched) else 0.0
        owner = home * (1 - v("closing_sell_pct", 0.06)) - bal + owner_side
        rows.append({"year": y, "home": home, "balance": bal, "owner": owner, "renter": renter, "rent": rent_y, "own_cost": own_y})
    sale = rows[-1]["home"] * (1 - v("closing_sell_pct", 0.06)) - rows[-1]["balance"]
    # each year: collected rent less that year's costs, less the loan payments only while the loan runs
    noi_y = lambda y: rent0 * 12 * (1 + v("rent_growth", 0.03)) ** (y - 1) * (1 - v("vacancy", 0.05) - v("management", 0.08))         - yearly_own * (1 + g) ** (y - 1)
    flows = [-cash_in] + [noi_y(y) - (debt_service if y <= len(sched) else 0.0) for y in range(1, horizon + 1)]
    flows[-1] += sale
    return {"price": price, "down": down, "loan": loan, "payment": pay, "sched": sched, "noi": noi, "cap_rate": noi / price,
            "coc": (noi - debt_service) / cash_in, "dscr": div(noi, debt_service), "one_pct": rent0 / price, "grm": price / gross,
            "gross_yield": gross / price, "cash_in": cash_in, "rows": rows, "advantage": rows[-1]["owner"] - rows[-1]["renter"],
            "breakeven_year": next((x["year"] for x in rows if x["owner"] >= x["renter"]), None), "irr": irr(flows), "irr_note": irr_note(flows),
            "rate": rate, "appreciation": g, "yearly_own": yearly_own, "total_interest": sum(s["interest"] for s in sched)}


def property_report(p, r):
    c, v = p.get("currency", "USD"), lambda k, d=None: val(p, k, d)
    ag = [r["appreciation"] + d for d in (-0.02, -0.01, 0, 0.01, 0.02)]
    rg = [r["rate"] + d for d in (-0.01, -0.005, 0, 0.005, 0.01)]
    grid = [[property_model(p, a, x)["advantage"] for x in rg] for a in ag]
    sens = T(f"Buying beats renting after {v('horizon_years', 10)} years by ({c}): price growth (rows) by mortgage rate (columns)",
             ["Price growth"] + [pct(x) for x in rg], [[pct(a)] + row for a, row in zip(ag, grid)], ["text"] + ["money"] * 5)
    sens["center"] = (2, 3)
    scen = [(n, property_model(p, r["appreciation"] + d)) for n, d in (("Bear", -0.03), ("Base", 0), ("Bull", 0.02))]
    sc = T("Bear, base and bull", ["Case", "Price growth a year", "Buy minus rent at the end", "Rental IRR"],
           [[n, x["appreciation"], x["advantage"], x["irr"]] for n, x in scen], ["text", "pct", "money", "pct"],
           note="Bear: prices grow 3 points slower than the base case (flat or falling in most inputs). Bull: 2 points faster.")
    inv = T("As a rental", ["Measure", "Value", "Read it as"],
            [["Gross yield (rent x 12 / price)", r["gross_yield"], "before any cost"],
             ["Net operating income (a year)", r["noi"], "rent after vacancy, management, tax, insurance and upkeep; before the mortgage"],
             ["Cap rate (NOI / price)", r["cap_rate"], "compare with the mortgage rate and the 10-year yield"],
             ["Cash-on-cash (NOI - mortgage) / cash in", r["coc"], "the yearly cash return on your own money"],
             ["Debt service cover (NOI / mortgage)", r["dscr"], "lenders want 1.25x+"],
             ["The 1 % rule (monthly rent / price)", r["one_pct"], "a quick screen only; it ignores every cost"],
             ["Price / yearly rent", r["grm"], "years of gross rent to pay the price"],
             [f"IRR over {v('horizon_years', 10)} years with a sale", r["irr"], "after every cost and the loan, on the cash put in"]],
            ["text", "auto", "text"])
    inv["row_formats"] = {0: "pct", 1: "money", 2: "pct", 3: "pct", 4: "x", 5: "pct", 6: "num1", 7: "pct"}
    path = T(f"Rent or buy, year by year ({c})", ["Year", "Home value", "Mortgage left", "Owner's wealth", "Renter's wealth", "Rent", "Owning costs"],
             [[str(x["year"]), x["home"], x["balance"], x["owner"], x["renter"], x["rent"], x["own_cost"]] for x in r["rows"]],
             ["text"] + ["money"] * 6, note="Owner's wealth = home after selling costs - mortgage left + savings; the renter invests the down "
                                           "payment and buying costs, and whichever side pays less each year invests the difference.")
    am = T(f"Mortgage: {c} {money0(r['loan'])} at {pct(r['rate'], 2)} ({c}, by year)", ["Year", "Interest", "Principal", "Balance"],
           [[str(s["year"]), s["interest"], s["principal"], s["balance"]] for s in r["sched"][:max(10, int(v('horizon_years', 10)))]],
           ["text", "money", "money", "money"])
    steps = [f"The price: {c} {money0(r['price'])}; the same home rents for {money0(v('rent_monthly'))} a month.",
             f"The loan: {pct(v('down_pct', 0.2), 0)} down ({money0(r['down'])}), {money0(r['loan'])} borrowed at {pct(r['rate'], 2)} over "
             f"{v('loan_years', 30)} years: {money0(r['payment'])} a month, {money0(r['total_interest'])} of interest in total.",
             f"The costs a renter never sees: tax, insurance, upkeep and fees of {money0(r['yearly_own'])} a year, plus "
             f"{pct(v('closing_buy_pct', 0.03), 0)} to buy and {pct(v('closing_sell_pct', 0.06), 0)} to sell.",
             f"The renter's side: the down payment and buying costs stay invested at {pct(v('invest_return', 0.06), 0)} a year.",
             f"After {v('horizon_years', 10)} years at {pct(r['appreciation'])} price growth, the owner is "
             f"{'ahead' if r['advantage'] >= 0 else 'behind'} by {money0(abs(r['advantage']))}; "
             + (f"buying wins from year {r['breakeven_year']}." if r["breakeven_year"] else "buying does not catch up within the horizon."),
             f"As a rental it yields a {pct(r['cap_rate'])} cap rate and {pct(r['coc'])} cash-on-cash; the 1 % rule reads "
             f"{pct(r['one_pct'], 2)}, a screen, not a verdict."]
    return {"kind": "property", "title": f"Rent or buy: {p.get('item', 'the home')}",
            "subtitle": f"Over {v('horizon_years', 10)} years. Money in {c}.",
            "hero": {"value": money0(r["advantage"]), "label": f"{c}: owner's wealth minus renter's after {v('horizon_years', 10)} years",
                     "line": (f"Buying wins from year {r['breakeven_year']}" if r["breakeven_year"] else "Buying never catches up in this horizon")
                             + f"; as a rental: cap rate {pct(r['cap_rate'])}, "
                             f"cash-on-cash {pct(r['coc'])}, IRR {pct(r['irr'])}."},
            "kpis": [("Monthly payment", money0(r["payment"])), ("Cap rate", pct(r["cap_rate"])), ("Cash-on-cash", pct(r["coc"])),
                     ("Debt cover", F.mult(r["dscr"])), ("1 % rule", pct(r["one_pct"], 2))],
            "steps": steps, "tables": [sc, inv, path, sens, am, sources_table({k: x for k, x in p.items() if isinstance(x, dict)})],
            "charts": [{"kind": "bars", "title": f"Wealth: owner against renter ({c})", "labels": [f"Y{x['year']}" for x in r["rows"]],
                        "series": [("Owner", [x["owner"] for x in r["rows"]], "total"), ("Renter", [x["renter"] for x in r["rows"]], "part")]},
                       {"kind": "waterfall", "title": f"From rent to cash flow, year 1 ({c})",
                        "steps": [("Rent", v("rent_monthly") * 12, "total"),
                                  ("Vacancy and management", -v("rent_monthly") * 12 * (v("vacancy", 0.05) + v("management", 0.08)), "delta"),
                                  ("Tax, insurance, upkeep", -r["yearly_own"], "delta"), ("Net operating income", r["noi"], "total"),
                                  ("Mortgage", -r["payment"] * 12, "delta"), ("Cash flow", r["noi"] - r["payment"] * 12, "total")]}],
            "notes": ["Tax on rent and on the sale, and mortgage-interest deductions, depend on the country and are left out.",
                      "Price growth is the biggest assumption: read the grid before the hero number."] + ([r["irr_note"]] if r["irr_note"] else []),
            "sources": [x["source"] for x in p.values() if isinstance(x, dict) and "source" in x]}


# ---------- 5. assets with no cash flows: gold, commodities, crypto ----------

def monthly(dates, closes):
    """One close per month (the last of the month)."""
    m = {}
    for d, c in zip(dates, closes):
        m[d[:7]] = c
    return sorted(m.items())


def no_yield(h, cpi, o=None, ratio=None):
    """h: history(); cpi: [(date, CPI)]. Nominal and real return, risk, drawdowns, rolling-horizon outcomes, carry."""
    o = o or {}
    px = monthly(h["dates"], h["closes"])
    cp = dict((d[:7], v) for d, v in cpi)
    last_cpi = cpi[-1][1]
    real = [(m, c * last_cpi / cp[m]) for m, c in px if m in cp]   # ends at the last CPI month
    mi = lambda m: int(m[:4]) * 12 + int(m[5:7])   # months count by the calendar: Yahoo skips some months
    span = lambda a, b: (mi(b) - mi(a)) / 12
    yrs = span(px[0][0], px[-1][0])
    nom_cagr = (px[-1][1] / px[0][1]) ** (1 / yrs) - 1
    real_cagr = (real[-1][1] / real[0][1]) ** (1 / span(real[0][0], real[-1][0])) - 1
    rets = [math.log(b[1] / a[1]) for a, b in zip(px, px[1:]) if mi(b[0]) - mi(a[0]) == 1]   # consecutive months only
    vol = statistics.stdev(rets) * math.sqrt(12) if len(rets) > 1 else None
    gaps = mi(px[-1][0]) - mi(px[0][0]) + 1 - len(px)
    peak, mdd, longest = 0, 0, 0
    for i, (m, c) in enumerate(real):
        if c >= real[peak][1]:
            peak = i
        else:
            longest = max(longest, mi(m) - mi(real[peak][0]))   # calendar months since the peak
            mdd = min(mdd, c / real[peak][1] - 1)
    hz = int(o.get("horizon", 10 if yrs >= 15 else 5))
    rd = {mi(m): c for m, c in real}
    carry = o.get("carry", 0 if h["meta"].get("instrumentType") == "ETF" else 0.004)   # an ETF's price is already after its fee
    spread = o.get("spread", 0.02)   # buy-sell spread, paid once over the holding
    roll = [((rd[k + hz * 12] / c) ** (1 / hz)) * (1 - carry) * (1 - spread) ** (1 / hz) - 1 for k, c in rd.items() if k + hz * 12 in rd]
    cases = [(n, pctile(roll, q)) for n, q in (("Bear (10th percentile)", 0.1), ("Base (median)", 0.5), ("Bull (90th percentile)", 0.9))] if roll else []
    pd = {mi(m): c for m, c in px}
    yr = lambda n: (px[-1][1] / pd[mi(px[-1][0]) - 12 * n]) ** (1 / n) - 1 if mi(px[-1][0]) - 12 * n in pd else None
    out = {"px": px, "real": real, "years": yrs, "nominal_cagr": nom_cagr, "real_cagr": real_cagr, "vol": vol, "max_dd_real": mdd,
           "longest_under_months": longest, "horizon": hz, "roll": roll, "cases": cases, "carry": carry, "spread": spread, "gaps": gaps,
           "independent": int(span(real[0][0], real[-1][0]) // hz), "futures": h["meta"].get("instrumentType") == "FUTURE",
           "price": h["meta"].get("regularMarketPrice", px[-1][1]), "y1": yr(1), "y5": yr(5), "y10": yr(10),
           "share_positive": sum(1 for x in roll if x > 0) / len(roll) if roll else None}
    if ratio:
        pr = dict(monthly(ratio["dates"], ratio["closes"]))
        rs = [(m, c / pr[m]) for m, c in px if pr.get(m)]
        now = rs[-1][1]
        out["ratio"] = {"now": now, "median": pctile([x for _, x in rs], 0.5), "lo": min(x for _, x in rs), "hi": max(x for _, x in rs),
                        "percentile": sum(1 for _, x in rs if x <= now) / len(rs), "series": rs}
    return out


def no_yield_report(ticker, h, cpi_src, r, ratio_ticker=None, o=None):
    name = h["meta"].get("longName") or h["meta"].get("shortName") or ticker
    cur_ = h["meta"].get("currency", "USD")
    ret = T("Return over time (a year, compounded)", ["Period", "Nominal", "Real (after US CPI)"],
            [["1 year", r["y1"], None], ["5 years", r["y5"], None], ["10 years", r["y10"], None],
             [f"Full history ({r['years']:.0f} years, from {r['px'][0][0]})", r["nominal_cagr"], r["real_cagr"]]], ["text", "pct", "pct"])
    risk = T("Risk", ["Measure", "Value"],
             [["Volatility (a year)", r["vol"]], ["Worst fall from a peak, real", r["max_dd_real"]],
              ["Longest time below a real peak (months)", r["longest_under_months"]],
              [f"Share of {r['horizon']}-year holds that made money, real, after costs", r["share_positive"]]], ["text", "auto"],
             note=f"Volatility uses back-to-back months only; {r['gaps']} months are missing from the price history." if r["gaps"] else None)
    risk["row_formats"] = {0: "pct", 1: "pct", 2: "int", 3: "pct"}
    cases = T(f"Bear, base and bull: real return a year over any {r['horizon']}-year hold, after costs", ["Case", "Real return a year"],
              [[n, x] for n, x in r["cases"]] or [[f"No complete {r['horizon']}-year hold in the history", None]], ["text", "pct"],
              note=f"From {len(r['roll'])} overlapping {r['horizon']}-year windows, each after {pct(r['carry'])} a year carry and a "
                   f"{pct(r['spread'])} round-trip spread. They share most of their months: the history holds only {r['independent']} "
                   "separate holds back to back. A share of past start dates, not the odds for a buyer today.")
    tables = [cases, ret, risk]
    steps = [f"The price now: {cur(r['price'], '')} {cur_} ({h['source'].split('?')[0]}).",
             ("These are continuous front-month futures prices: the quoted price change, not what a holder earned after rolling "
              "contracts and holding collateral. " if r["futures"] else "") + f"Over {r['years']:.0f} years it compounded {pct(r['nominal_cagr'])} a year; after US inflation, {pct(r['real_cagr'])}.",
             f"It pays nothing: no rent, no dividend, no coupon. All the return is the next buyer's price, so there is no DCF and no fair value.",
             f"The ride: {pct(r['vol'])} volatility a year; the worst real fall was {pct(r['max_dd_real'])}, and it once stayed below a real "
             f"peak for {r['longest_under_months']} calendar months.",
             f"Holding costs: about {pct(r['carry'])} a year to store and insure (or the fund fee), and {pct(r['spread'])} to buy and sell.",
             f"Across every {r['horizon']}-year hold in the history, the real yearly return after costs ran from {pct(r['cases'][0][1])} "
             f"(bear) to {pct(r['cases'][2][1])} (bull), median {pct(r['cases'][1][1])}; only {r['independent']} of those holds fit back to back."
             if r["cases"] else f"The history has no complete {r['horizon']}-year hold."]
    kpis = [("Real return a year", pct(r["real_cagr"])), ("Volatility", pct(r["vol"])), ("Worst real fall", pct(r["max_dd_real"])),
            (f"{r['horizon']}y holds that made money", pct(r["share_positive"]))]
    charts = [{"kind": "bars", "title": f"Real price by year ({cur_}, today's money)",
               "labels": [m[:4] for m, _ in r["real"][::12]], "series": [("Real price", [c for _, c in r["real"][::12]], "total")]}]
    if r.get("ratio"):
        q = r["ratio"]
        tables.insert(1, T(f"{ticker} / {ratio_ticker} ratio", ["Measure", "Value"],
                           [["Now", q["now"]], ["Median of the history", q["median"]], ["Lowest", q["lo"]], ["Highest", q["hi"]],
                            ["Percentile of now", q["percentile"]]], ["text", "num1"], note="A high ratio says the first is dear against the second, "
                                                                                           "not that either is dear; ratios can stay stretched for years."))
        tables[1]["row_formats"] = {4: "pct"}
        steps.append(f"Against {ratio_ticker}: the ratio is {q['now']:.1f}, against a median of {q['median']:.1f} (percentile {pct(q['percentile'], 0)}).")
        kpis.append((f"{ratio_ticker} ratio", f"{q['now']:.1f}"))
        charts.append({"kind": "bars", "title": f"{ticker} / {ratio_ticker} ratio by year", "labels": [m[:4] for m, _ in q["series"][::12]],
                       "series": [("Ratio", [x for _, x in q["series"][::12]], "total")], "fmt": "num1"})
    return {"kind": "asset", "title": f"{name}: what history says",
            "subtitle": f"Monthly closes from Yahoo chart data, deflated by US CPI (FRED CPIAUCSL). Prices in {cur_}.",
            "hero": {"value": pct(r["cases"][1][1]) if r["cases"] else pct(r["real_cagr"]),
                     "label": f"median real return a year over a {r['horizon']}-year hold, after costs" if r["cases"] else
                              f"real return a year from {r['real'][0][0]} to {r['real'][-1][0]}, before costs",
                     "line": f"Bear {pct(r['cases'][0][1])}, bull {pct(r['cases'][2][1])}; {pct(r['share_positive'], 0)} of past "
                             f"{r['horizon']}-year holds beat inflation after costs, but the windows overlap: the history fits only {r['independent']} "
                             f"back to back. "
                             "No cash flow, so no fair value: this is a range, not a target." if r["cases"] else
                             f"No complete {r['horizon']}-year hold in the history, so no range."},
            "kpis": kpis, "steps": steps, "tables": tables, "charts": charts,
            "notes": ["What this can tell you: how the price has moved, how deep and long the falls were, and what a hold of this length has returned.",
                      "What it cannot tell you: a fair value or a future return. Nothing pays the holder, so the price is whatever the next buyer pays.",
                      "Futures prices (GC=F, SI=F) are the front contract's quote; rolling costs and collateral income are left out, so a "
                      "coin, a bar or an ETF can earn more or less. For an ETF's own ticker the fee is already in the price: carry 0."],
            "sources": [h["source"], cpi_src]}


# ---------- 6. collectibles: sold comparables, grading premium, fees, liquidity, population ----------

def collectible(data, live=None):
    """data: see references/collectibles.md. live: optional [(label, price)] reference prices fetched from an API."""
    fees = data.get("fees", {})
    sell_pct = fees.get("sell_pct", 0.13)
    ship = fees.get("shipping", 0)
    net = lambda x: x * (1 - sell_pct) - ship
    by = {}
    for s in data.get("sales", []):
        by.setdefault(s.get("grade", "raw"), []).append(s)
    grades = []
    for g, ss in by.items():
        ps = sorted(s["price"] for s in ss)
        k = int(len(ps) * 0.1)
        trimmed = ps[k:len(ps) - k] or ps
        dates = sorted(s["date"] for s in ss)
        span = max(1.0, (int(dates[-1][:4]) * 12 + int(dates[-1][5:7])) - (int(dates[0][:4]) * 12 + int(dates[0][5:7])) + 1)
        half = sorted(ss, key=lambda s: s["date"])
        old, new = half[:len(half) // 2], half[len(half) // 2:]
        trend = div(statistics.median(s["price"] for s in new), statistics.median(s["price"] for s in old)) - 1 if len(ss) >= 4 else None
        grades.append({"grade": g, "n": len(ps), "q1": pctile(ps, 0.25), "median": pctile(ps, 0.5), "q3": pctile(ps, 0.75),
                       "trimmed": statistics.mean(trimmed), "per_month": len(ps) / span, "trend": trend, "first": dates[0], "last": dates[-1]})
    G = {g["grade"]: g for g in grades}
    raw = G.get("raw")
    for g in grades:
        g["premium"] = div(g["median"], raw["median"]) if raw else None
    odds = data.get("grade_odds")
    grade_ev = None
    if odds and raw and abs(sum(odds.values()) - 1) < 1e-6 and all(k in G for k, p in odds.items() if p):   # a grade with no sales has no price: no answer
        exp = sum(p * net(G[k]["median"]) for k, p in odds.items() if p)
        grade_ev = {"expected_net": exp, "cost": fees.get("grading_cost", 0) + ship, "raw_net": net(raw["median"]),
                    "gain": exp - fees.get("grading_cost", 0) - ship - net(raw["median"])}
    key = G.get(data.get("grade", "raw")) if data.get("grade") or "raw" in G else (grades[0] if grades else None)
    buy = data.get("buy_price")
    cases = [(n, net(key[q])) for n, q in (("Bear (25th percentile sale)", "q1"), ("Base (median sale)", "median"), ("Bull (75th percentile sale)", "q3"))] if key else []
    unavailable = f"Price unavailable: add sold comparables graded {data['grade']} to sales." if grades and not key else ""
    if not grades and live:   # no sold list: one variant's TCGplayer prices; low and mid are asks, market mixes conditions
        variants = sorted({lab.rsplit(" (", 1)[0].rsplit(" ", 2)[-2] for lab, _ in live})
        pick = data.get("variant") or (variants[0] if len(variants) == 1 else None)
        if pick not in variants:
            unavailable = f'Price unavailable: set "variant" to one of {", ".join(variants)}; their prices differ.'
        live = [(lab, p) for lab, p in live if lab.rsplit(" (", 1)[0].rsplit(" ", 2)[-2] == pick]
        first = lambda kind: next((p for lab, p in live if lab.rsplit(" (", 1)[0].endswith(kind)), None)
        mk, lo, mid = first("market"), first("low"), first("mid")
        if mid:   # an ask is what a seller hopes for; the market line mixes conditions, so it never sits above the asks as the base
            cases = [("Bear (undercut the lowest ask)", net(lo or mid)), ("Base (sell at the middle ask)", net(min(mid, mk or mid))),
                     ("Bull (TCGplayer market: recent sales, conditions mixed)", net(max(mid, mk or mid)))]
    pop = data.get("population") or {}
    return {"unavailable": unavailable, "grades": grades, "key": key, "asks_only": bool(cases) and not grades, "cases": cases, "buy": buy, "grade_ev": grade_ev, "live": live or [], "pop": pop,
            "pop_total": sum(pop.values()), "fees": {"sell_pct": sell_pct, "shipping": ship, **fees},
            "mos": 1 - buy / cases[1][1] if buy and cases and cases[1][1] > 0 else None,
            "hold": data.get("hold_years"), "net": net}


def collectible_report(data, r):
    c = data.get("currency", "USD")
    tables = []
    if r["cases"]:
        tables.append(T(f"What you would get after fees ({c})", ["Case", "Net to you", "vs your price"],
                        [[n, x, (x / r["buy"] - 1) if r["buy"] else None] for n, x in r["cases"]], ["text", "ps", "pct"],
                        note=f"Net = sale price x (1 - {pct(r['fees']['sell_pct'])} selling fees) - {cur(r['fees']['shipping'])} shipping."))
    if r["grades"]:
        tables.append(T(f"Sold comparables by grade ({c})", ["Grade", "Sales", "25th", "Median", "75th", "Trimmed mean", "Sales a month",
                                                              "Trend (newer vs older half)", "Premium vs raw"],
                        [[g["grade"], g["n"], g["q1"], g["median"], g["q3"], g["trimmed"], g["per_month"], g["trend"], g["premium"]] for g in r["grades"]],
                        ["text", "int", "ps", "ps", "ps", "ps", "num1", "pct", "x"], note="Sold prices only; asking prices are what sellers hope for."))
    if r["live"]:
        tables.append(T(f"Live reference prices ({c})", ["Source line", "Price"], [[k, v] for k, v in r["live"]], ["text", "ps"],
                        note="TCGplayer via pokemontcg.io: 'market' is built from recent sales of any condition; low, mid and high are "
                             "current asks."))
    if r["grade_ev"]:
        e = r["grade_ev"]
        tables.append(T(f"Grade it or sell it raw? ({c})", ["Line", "Value"],
                        [["Expected net after grading (by the odds given)", e["expected_net"]], ["Grading and shipping cost", -e["cost"]],
                         ["Net if sold raw", -e["raw_net"]], ["Gain from grading", e["gain"]]], ["text", "ps"], totals=[3]))
    if r["pop"]:
        tables.append(T("Population report", ["Grade", "Graded copies", "Share"], [[k, n, n / r["pop_total"]] for k, n in r["pop"].items()],
                        ["text", "int", "pct"], note="A grade's price rests on how few exist; a rising population count pushes it down."))
    k = r["key"]
    base = r["cases"][1][1] if r["cases"] else None
    steps = [f"Find what it sells for, not what it is listed at: {k['n']} sold {k['grade']} copies from {k['first']} to {k['last']}, median "
             f"{cur(k['median'])}." if k else r["unavailable"] if r["unavailable"] else
             "No sold list was given, so one variant's TCGplayer asks stand in: what sellers ask, not what buyers paid. Add sold "
             "listings for your condition to price it.",
             f"Take off the cost of selling: {pct(r['fees']['sell_pct'])} in fees and {cur(r['fees']['shipping'])} shipping leave {cur(base)} in the base case.",
             (f"Read the spread: the middle half of sales runs from {cur(r['cases'][0][1])} to {cur(r['cases'][2][1])} net." if k else
              f"Read the spread: from {cur(r['cases'][0][1])} (if you undercut the lowest ask) to {cur(r['cases'][2][1])} net; no bid "
              "is known, so a quick sale may fetch less.")
             if r["cases"] else "",
             f"Liquidity: about {k['per_month']:.1f} sales a month; a thin market means a wide spread and a long wait." if k else "",
             f"Margin of safety at your price of {cur(r['buy'])}: {pct(r['mos'])}." if r["buy"] else "",
             "Before you pay: check the card (or watch, or print) is real, the grade matches the slab's certificate number, and the "
             "population report is not growing fast."]
    return {"kind": "collectible", "title": f"{data.get('item', 'Collectible')}: sold comparables",
            "subtitle": f"Prices in {c}. Sources: {', '.join(data.get('sources', ['the user']))}.",
            "hero": {"value": cur(base), "label": "net to you if it sells at the middle ask, after fees (an ask, not a sale)" if r["asks_only"]
                     else "net to you in the base case, after fees",
                     "line": f"Range {cur(r['cases'][0][1])} to {cur(r['cases'][2][1])}"
                             + (f"; margin of safety {pct(r['mos'])} at {cur(r['buy'])}." if r["buy"] else ".") if r["cases"] else r["unavailable"]},
            "kpis": [("Median sale", cur(k["median"]) if k else "n/a"), ("Sales a month", f"{k['per_month']:.1f}" if k else "n/a"),
                     ("Selling fees", pct(r["fees"]["sell_pct"]))],
            "steps": [s for s in steps if s], "tables": tables,
            "charts": [{"kind": "football", "title": f"Net to you after fees ({c})",
                        "rows": [(g["grade"], r["net"](g["q1"]), r["net"](g["q3"])) for g in r["grades"]]
                        + ([("Live: lowest to middle ask", r["cases"][0][1], r["cases"][1][1])] if r["asks_only"] else []),
                        "marker": ("Your price" if r["buy"] else "Base", r["buy"] or base)}] if r["cases"] else [],
            "notes": ["Collectibles pay nothing while held: the return is the next buyer's price less fees, storage and insurance.",
                      "One record sale is not a market: use the median and the spread, and drop outliers (the trimmed mean drops the top and bottom 10 %)."],
            "sources": data.get("sources", ["the user's sold listings"])}


# ---------- 7. bonds and funds ----------

def bond_flows(face, coupon, years, freq=2):
    """[(periods from today, cash)] and the accrued interest. Settlement between coupon dates: the first coupon comes in a
    fraction a of a period, and the seller has earned (1 - a) of it."""
    n = math.ceil(years * freq - 1e-9)
    a, c = years * freq - (n - 1), face * coupon / freq
    return [(a + k, c + (face if k == n - 1 else 0)) for k in range(n)], c * (1 - a)


def bond_price(face, coupon, years, y, freq=2):
    """Clean price: the value of the payments less the accrued interest the buyer pays the seller on top."""
    flows, acc = bond_flows(face, coupon, years, freq)
    return sum(cf / (1 + y / freq) ** t for t, cf in flows) - acc


def bond(b):
    """b["price"] is a clean quote per 100 of face; the cash paid is quote x face / 100 plus accrued interest."""
    face, cpn, yrs, freq = b.get("face", 100), b["coupon"], b["years"], b.get("freq", 2)
    if "price" in b:
        clean = b["price"] * face / 100
        ytm = bisect(lambda y: bond_price(face, cpn, yrs, y, freq) - clean, -0.05, 1.0)
    else:
        ytm = b["yield"]
        clean = bond_price(face, cpn, yrs, ytm, freq)
    cfs, acc = bond_flows(face, cpn, yrs, freq)
    dirty, r = clean + acc, ytm / freq
    mac = sum(t / freq * cf / (1 + r) ** t for t, cf in cfs) / dirty
    mod = mac / (1 + r)
    conv = sum(cf * t * (t + 1) / (1 + r) ** (t + 2) for t, cf in cfs) / (dirty * freq ** 2)
    shocks = [(d, (bond_price(face, cpn, yrs, ytm + d, freq) + acc) / dirty - 1) for d in (-0.02, -0.01, 0, 0.01, 0.02)]
    # one-year total return if rates move by d at once: payments received in the year (kept as cash) + the rest priced a year on
    hold = lambda d: (sum(cf for t, cf in cfs if t <= freq) + sum(cf / (1 + (ytm + d) / freq) ** (t - freq) for t, cf in cfs if t > freq)) / dirty - 1
    one_year = [(d, hold(d)) for d in (0.01, 0, -0.01)]
    return {"price": 100 * clean / face, "accrued": 100 * acc / face, "ytm": ytm, "current_yield": face * cpn / clean, "macaulay": mac,
            "modified": mod, "convexity": conv, "shocks": shocks, "one_year": one_year,
            "spread": ytm - b["treasury"] if b.get("treasury") is not None else None}


def bond_report(b, r):
    t = T("Price change if yields move at once", ["Yield change", "Price change"], [[f"{d * 100:+.0f} points", x] for d, x in r["shocks"]], ["text", "pct"])
    sc = T("Bear, base and bull: one-year total return", ["Case", "Yields move", "Total return"],
           [[n, f"{d * 100:+.0f} points", x] for n, (d, x) in zip(("Bear", "Base", "Bull"), r["one_year"])], ["text", "text", "pct"])
    m = T("The bond", ["Measure", "Value"],
          [["Price (per 100 face)", r["price"]], ["Yield to maturity", r["ytm"]], ["Current yield (coupon / price)", r["current_yield"]],
           ["Spread over the Treasury of the same length", r["spread"]], ["Macaulay duration (years)", r["macaulay"]],
           ["Modified duration", r["modified"]], ["Convexity", r["convexity"]], ["Accrued interest paid to the seller (per 100 face)", r["accrued"]]],
          ["text", "auto"])
    m["row_formats"] = {0: "num", 1: "pct", 2: "pct", 3: "pct", 4: "num1", 5: "num1", 6: "num1", 7: "num"}
    steps = [f"The bond pays {pct(b['coupon'], 2)} a year on its face for {b['years']} years and costs {r['price']:.2f} per 100.",
             f"The one rate that makes the payments worth the price is the yield to maturity: {pct(r['ytm'], 2)}.",
             (f"Against the Treasury of the same length ({pct(b['treasury'], 2)}, {b.get('treasury_source', 'FRED')}), that is "
              f"{pct(r['spread'], 2)} extra for the credit risk and the lower liquidity.") if r["spread"] is not None else "",
             f"Rate risk: a 1-point rise in yields cuts the price about {pct(-r['shocks'][3][1])} (modified duration {r['modified']:.1f}).",
             f"Held a year: {pct(r['one_year'][1][1])} if yields stay, {pct(r['one_year'][0][1])} if they rise a point (payments in the "
             "year kept as cash; a bond that matures inside the year returns its yield whatever rates do)."]
    return {"kind": "bond", "title": f"Bond: {b.get('name', 'the bond')}", "subtitle": "Prices per 100 of face value; yields a year.",
            "hero": {"value": pct(r["ytm"], 2), "label": "yield to maturity", "line": f"Duration {r['modified']:.1f}: each point of yield moves the price about "
                                                                                     f"{r['modified']:.1f} %. Spread over Treasuries {pct(r['spread'], 2)}."},
            "kpis": [("Price", f"{r['price']:.2f}"), ("Current yield", pct(r["current_yield"])), ("Duration", f"{r['modified']:.1f}")],
            "steps": [s for s in steps if s], "tables": [m, sc, t], "charts": [],
            "notes": ["The yield assumes every payment arrives on time and is reinvested at the same yield; a default or a call breaks that."],
            "sources": [b.get("source", "the user"), b.get("treasury_source", "")]}


def fund(h, bench, fee):
    """Tracking difference and tracking error against a benchmark, and what the fee costs over time."""
    bare = [x["source"].split("?")[0].rsplit("/", 1)[-1] for x in (h, bench) if x["dividends"] and x["adj"] == x["closes"]]
    unavailable = (f"Total return unavailable for {', '.join(bare)}: no adjusted closes, so these are price returns without dividends. "
                   "Fill it with a series that reinvests dividends.") if bare else ""
    a, b = dict(monthly(h["dates"], h["adj"])), dict(monthly(bench["dates"], bench["adj"]))
    ms = sorted(set(a) & set(b))
    mi = lambda m: int(m[:4]) * 12 + int(m[5:7])
    pairs = [(x, y) for x, y in zip(ms, ms[1:]) if mi(y) - mi(x) == 1]   # tracking error on back-to-back months only
    ra = [a[y] / a[x] - 1 for x, y in pairs]
    rb = [b[y] / b[x] - 1 for x, y in pairs]
    yrs = (mi(ms[-1]) - mi(ms[0])) / 12   # calendar time
    ca, cb = (a[ms[-1]] / a[ms[0]]) ** (1 / yrs) - 1, (b[ms[-1]] / b[ms[0]]) ** (1 / yrs) - 1
    te = statistics.stdev(x - y for x, y in zip(ra, rb)) * math.sqrt(12) if len(ra) > 1 else None
    drag = [(n, 10000 * ((1 + cb) ** n - (1 + cb - fee) ** n)) for n in (10, 20, 30)]
    return {"unavailable": unavailable, "fund_cagr": ca, "bench_cagr": cb, "diff": ca - cb, "te": te, "years": yrs, "drag": drag, "fee": fee, "from": ms[0]}


def fund_report(ticker, bench_t, h, r):
    t = T("Fund against its benchmark (total return a year)", ["Measure", "Value"],
          [["Fund", r["fund_cagr"]], ["Benchmark", r["bench_cagr"]], ["Tracking difference (fund - benchmark)", r["diff"]],
           ["Tracking error (st. dev. of the monthly gap, a year)", r["te"]], ["Fee (expense ratio)", r["fee"]]], ["text", "pct"],
          note=r["unavailable"] or f"From {r['from']}, {r['years']:.1f} years of Yahoo adjusted closes (dividends reinvested).")
    d = T("What the fee costs on 10,000 at the benchmark's return", ["Years", "Cost of the fee"], [[f"{n} years", x] for n, x in r["drag"]], ["text", "money"])
    return {"kind": "fund", "title": f"{ticker} against {bench_t}", "subtitle": "Total return from Yahoo adjusted closes.",
            "hero": {"value": pct(r["diff"], 2), "label": "tracking difference a year (fund minus benchmark)",
                     "line": f"Tracking error {pct(r['te'], 2)}; the {pct(r['fee'], 2)} fee costs {money0(r['drag'][2][1])} on 10,000 over 30 years."},
            "kpis": [("Fund return a year", pct(r["fund_cagr"])), ("Benchmark", pct(r["bench_cagr"])), ("Fee", pct(r["fee"], 2))],
            "steps": [f"The fund returned {pct(r['fund_cagr'])} a year and its benchmark {pct(r['bench_cagr'])}.",
                      f"The gap ({pct(r['diff'], 2)} a year) is what owning it cost: fees, cash drag, trading and tax on dividends.",
                      f"The monthly gap wobbles by {pct(r['te'], 2)} a year (tracking error): low means the fund does what it says.",
                      f"A {pct(r['fee'], 2)} fee looks small; compounded over 30 years it takes {money0(r['drag'][2][1])} of every 10,000."],
            "tables": [t, d], "charts": [{"kind": "hbars", "title": "Cost of the fee on 10,000", "rows": [(f"{n} years", x) for n, x in r["drag"]]}],
            "notes": ["Yahoo's chart data carries no expense ratio: pass the fee from the fund's fact sheet with --set fee=0.0003."],
            "sources": [h["source"]]}
