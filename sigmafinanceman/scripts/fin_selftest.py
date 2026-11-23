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
           "liabilities": k(r(0.7)), "equity": k(r(0.8)), "retained_earnings": k(r(0.5)), "debt": k([200] * 5), "cash_all": k([200] * 5)}
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


def history_fixture(start=2005, years=20, growth=0.10, div0=0.0):
    """A monthly price series growing `growth` a year, with quarterly dividends growing 5 % a year when div0 > 0."""
    dates, closes, divs = [], [], []
    for k in range(years * 12 + 1):
        y, m = start + k // 12, k % 12 + 1
        dates.append(f"{y}-{m:02d}-01")
        closes.append(100 * (1 + growth) ** (k / 12))
        if div0 and m in (3, 6, 9, 12):
            divs.append((f"{y}-{m:02d}-15", div0 * 1.05 ** (y - start) / 4))
    return {"dates": dates, "closes": closes, "adj": closes, "dividends": divs,
            "meta": {"currency": "USD", "regularMarketPrice": closes[-1]}, "source": "fixture"}


def assets(out):
    """Every asset-class model against an answer worked out by hand, and its report through every writer."""
    import fin_assets as A
    import finman
    ok = True
    ok &= check("IRR of -100 then +110 is 10 %", abs(A.irr([-100, 110]) - 0.10) < 1e-9)
    ok &= check("Mortgage payment: 100,000 at 6 % over 30 years = 599.55", abs(A.mortgage(100000, 0.06, 30)[0] - 599.55) < 0.01)
    ok &= check("Mortgage is repaid at the end", A.mortgage(100000, 0.06, 30)[1][-1]["balance"] < 1e-6)
    ok &= check("DDM with one growth rate equals Gordon D1 / (ke - g)", abs(A.ddm_value(2.0, 0.08, 0.03, 0.03) - 2.0 * 1.03 / 0.05) < 1e-9)
    # dividend model on Sample Co with a dividend history
    f = sample()
    f["history"] = history_fixture(2007, 20, 0.05, 1.0)
    f["market"] = dict(f["market"], price_time="2027-03-01")
    r = A.dividend(f, f["history"])
    back = A.ddm_value(r["a"]["dps_ttm"]["value"], r["a"]["ke"]["value"], r["implied_g1"], r["a"]["g2"]["value"])
    ok &= check("Dividend model: the implied growth gives back the price", abs(back - 20.0) < 1e-6, F.pct(r["implied_g1"]))
    ok &= check("Dividend history: 5 % growth and no cut read back", abs(r["d"]["g5"] - 0.05) < 1e-9 and r["d"]["streak"] == 19)
    # comps: minority interest belongs in EV
    p = sample()
    p["annual"]["minority"] = {e: 30e6 for e in ENDS}
    ok &= check("Comps EV adds minority interest", abs(F.comp_row(p)["ev"] - F.comp_row(sample())["ev"] - 30) < 1e-9)
    # venture: post-money SAFE, pool top-up, two rounds, waterfall
    deal = {"founders": [{"name": "F", "shares": 9e6}], "pool": 1e6,
            "safes": [{"name": "SAFE", "amount": 1e6, "cap": 10e6, "type": "post"}],
            "rounds": [{"name": "Seed", "pre_money": 16e6, "amount": 4e6, "pool_target": 0.10},
                       {"name": "A", "pre_money": 60e6, "amount": 15e6, "pool_target": 0.10}], "exits": [5e6, 500e6]}
    v = A.venture(deal)
    seed = v["tables"][1][1]
    tot = sum(h["shares"] for h in seed.values())
    ok &= check("Post-money SAFE owns amount / cap before the new money and the pool top-up",
                abs(seed["SAFE"]["shares"] / (9e6 + 1e6 + seed["SAFE"]["shares"]) - 0.10) < 1e-9)
    ok &= check("Seed: post-money = pre + raised; new money owns raised / post; pool = target",
                abs(v["rounds"][0]["post_money"] - 20e6) < 1e-3 and abs(seed["Seed"]["shares"] / tot - 0.2) < 1e-9
                and abs(seed["Option pool"]["shares"] / tot - 0.10) < 1e-9)
    low, high = v["falls"][0][1], v["falls"][1][1]
    last = v["tables"][2][1]
    ok &= check("Waterfall pays out exactly the exit", abs(sum(low.values()) - 5e6) < 1e-3 and abs(sum(high.values()) - 500e6) < 1e-3)
    ok &= check("Low exit: preferences first, founders get nothing", low["F"] < 1e-6)
    ok &= check("High exit: every investor converts, payout = ownership of the shares left after the free pool is cancelled",
                abs(high["A"] / 500e6 - last["A"]["shares"] / (sum(h["shares"] for h in last.values()) - v["pool_free"])) < 1e-9)
    # purchase: at the break-even use, buying and renting cost the same
    gp = {"price": 2000, "life_years": 4, "resale_value": 500, "uses_per_month": 200, "rent_per_use": 0.6, "running_per_use": 0.15,
          "fixed_monthly": 5, "discount_rate": 0.05}
    pr = A.purchase(gp)
    ok &= check("Purchase: at the break-even use, buy = rent", abs(A.purchase(gp, uses=pr["breakeven_uses"])["npv_buy_vs_rent"]) < 1e-6)
    pm = A.property_model({"price": 300000, "rent_monthly": 1500, "mortgage_rate": 0.06, "horizon_years": 10})
    ok &= check("Property: cap rate = NOI / price", abs(pm["cap_rate"] - pm["noi"] / 300000) < 1e-12)
    # no cash flows: 10 % a year, flat prices, no carry -> 10 % real, no fall
    cpi = [(d, 100.0) for d in history_fixture()["dates"]]
    ny = A.no_yield(history_fixture(), cpi, {"carry": 0, "spread": 0})
    ok &= check("No-yield asset: 10 % a year reads back, real = nominal at flat CPI, no drawdown",
                abs(ny["nominal_cagr"] - 0.10) < 1e-9 and abs(ny["real_cagr"] - 0.10) < 1e-9 and ny["max_dd_real"] == 0
                and abs(ny["cases"][1][1] - 0.10) < 1e-9)
    cd = {"sales": [{"date": f"2026-0{i}-01", "price": x, "grade": "raw"} for i, x in enumerate((100, 110, 120, 130, 140), start=1)],
          "fees": {"sell_pct": 0.1, "shipping": 5}, "buy_price": 90}
    co = A.collectible(cd)
    ok &= check("Collectible: base = median sale x (1 - fees) - shipping", abs(co["cases"][1][1] - (120 * 0.9 - 5)) < 1e-9)
    ok &= check("Bond at a yield equal to its coupon prices at par", abs(A.bond_price(100, 0.05, 10, 0.05) - 100) < 1e-9)
    bd = A.bond({"coupon": 0.05, "years": 10, "price": 95})
    ok &= check("Bond yield to maturity gives back the price", abs(A.bond_price(100, 0.05, 10, bd["ytm"]) - 95) < 1e-6)
    fd = A.fund(history_fixture(), history_fixture(), 0.001)
    ok &= check("Fund that matches its benchmark: no tracking difference", abs(fd["diff"]) < 1e-12 and fd["te"] < 1e-12)
    reps = [("dividend", A.dividend_report(f, r)), ("venture", A.venture_report(deal, v)), ("purchase", A.purchase_report(gp, pr)),
            ("property", A.property_report({"price": 300000, "rent_monthly": 1500, "mortgage_rate": 0.06}, pm)),
            ("asset", A.no_yield_report("TEST", history_fixture(), "fixture", ny)), ("collectible", A.collectible_report(cd, co)),
            ("bond", A.bond_report({"coupon": 0.05, "years": 10}, bd)), ("fund", A.fund_report("F", "B", history_fixture(), fd))]
    for name, rep in reps:
        files = finman.write_outputs(rep, f"asset-{name}", out, {"pptx", "svg", "html"})
        for x in files:
            if x.endswith(".svg"):
                xml.dom.minidom.parse(x)
        page = (out / f"asset-{name}.html").read_text(encoding="utf-8")
        ok &= check(f"{name}: page, charts and deck written; the page walks the method", len(files) >= 2 and 'class="steps"' in page)
    return ok


def raises(fn):
    try:
        fn()
    except SystemExit:
        return True
    return False


def asset_review_cases():
    """The counterexamples from the release reviews for the non-company models: each failed before its fix."""
    import fin_assets as A
    ok = True
    near = lambda a, b, tol=1e-6: a is not None and abs(a - b) <= tol
    # IRR: several roots, and a root above the old bracket
    ok &= check("IRR: -100, +230, -132 has two roots (10 %, 20 %): no single IRR, the note says so",
                A.irr([-100, 230, -132]) is None and "10.0%" in A.irr_note([-100, 230, -132]) and "20.0%" in A.irr_note([-100, 230, -132]))
    ok &= check("IRR: -100 then +1,200 is 1,100 %", near(A.irr([-100, 1200]), 11.0))
    # dividends
    ok &= check("Reverse Gordon: ke 10 %, D0 5, price 100 gives 4.7619 %", near(A.gordon_g(0.10, 5, 100), 0.047619, 1e-6))
    divs = [(f"{y}-06-15", 1 + 0.1 * (y - 2010)) for y in range(2010, 2023)]
    full, ttm = A.annual_dps(divs, "2026-03-01")
    ok &= check("Dividend suspended 2023-25 after 12 raises: streak 0, not 12", A.streak(full) == 0 and full.get(2024) == 0 and ttm == 0)
    # venture: cap-only SAFE never above the round price (10m shares, $1m SAFE, $20m cap, $5m pre, $1m new)
    v = A.venture({"founders": [{"name": "F", "shares": 10e6}], "safes": [{"name": "S", "amount": 1e6, "cap": 20e6, "type": "post"}],
                   "rounds": [{"name": "A", "pre_money": 5e6, "amount": 1e6}], "exits": [10e6]})
    ok &= check("Cap-only SAFE above the round's cap price converts at the round price: 2.5m shares", near(v["holders"]["S"]["shares"], 2.5e6, 1))
    ok &= check("SAFE terms with no solution stop the run ($1.2m capped at $1m)", raises(lambda: A.venture(
        {"founders": [{"name": "F", "shares": 1e6}], "safes": [{"name": "S", "amount": 1.2e6, "cap": 1e6, "type": "post"}],
         "rounds": [{"name": "A", "pre_money": 5e6, "amount": 1e6}]})))
    # the startup proof: no grants, so the free pool takes nothing; founders get 132.676m at 250m
    deal = {"founders": [{"name": "Founder A", "shares": 4.5e6}, {"name": "Founder B", "shares": 4.5e6}], "pool": 1e6,
            "safes": [{"name": "Angel SAFE", "amount": 750000, "cap": 8e6, "discount": 0.2, "type": "post"}],
            "rounds": [{"name": "Seed", "pre_money": 14e6, "amount": 3.5e6, "pool_target": 0.10},
                       {"name": "Series A", "pre_money": 45e6, "amount": 12e6, "pool_target": 0.12}], "exits": [250e6]}
    base = A.venture(deal)
    fall = base["falls"][0][1]
    ok &= check("Exit: the ungranted pool gets nothing; founders take 132.676m of 250m; payouts add up to the exit",
                fall["Option pool"] == 0 and near(fall["Founder A"] + fall["Founder B"], 132.676e6, 1e3) and near(sum(fall.values()), 250e6, 1e-3),
                f"{(fall['Founder A'] + fall['Founder B']) / 1e6:.3f}m")
    g = A.venture(dict(deal, options_granted=1e6, option_strike=1.0))
    gf = g["falls"][0][1]
    ok &= check("Granted options are paid net of the strike; payouts still add up to the exit",
                gf["Option pool"] > 0 and near(sum(gf.values()), 250e6, 1e-3) and g["pool_free"] < base["pool_free"])
    # anti-dilution: 100 preferred at $2, then a down round
    for kind in ("full", "broad"):
        d = A.venture({"founders": [{"name": "F", "shares": 900}], "rounds": [
            {"name": "Seed", "pre_money": 1800, "amount": 200, "anti_dilution": kind}, {"name": "A", "pre_money": 500, "amount": 500}], "exits": [1]})
        p2, sh = d["rounds"][1]["price"], d["holders"]["Seed"]["shares"]
        want = 200 / p2 if kind == "full" else 200 / (2 * (1000 + 500 / 2) / (1000 + d["rounds"][1]["new_shares"]))
        ok &= check(f"Down round, {kind} anti-dilution: the protected series gets its extra shares", p2 < 2 and sh > 100 and near(sh, want, 1e-6),
                    f"{sh:.2f}")
    nt = A.venture({"founders": [{"name": "F", "shares": 1e6}], "notes": [{"name": "N", "amount": 100, "rate": 0.10, "months": 12, "pref_basis": "balance"}],
                    "rounds": [{"name": "A", "pre_money": 1e6, "amount": 1e5}], "exits": [1]})
    ok &= check("Note with $10 interest on $100 and pref_basis balance: preference 110", near(nt["holders"]["N"]["pref"], 110))
    vc = A.vc_method({"vc": {"investment": 3e6, "exit_revenue": 100e6, "exit_multiple": 4, "exit_net_debt": 100e6, "target_multiple": 10}}, {})
    ok &= check("VC method: 4x revenue of 100m less 100m net debt, 10x target: post-money at most 30m", near(vc["post_max"], 30e6))
    pf = A.portfolio({"size": 10, "cheques": 10, "outcomes": [[0.5, 0], [0.47, 2], [0.03, 50]], "outlier_multiple": 50})
    ok &= check("Portfolio: the multiple without an outlier is conditional (0.94 / 0.97)", near(pf["multiple_without_outliers"], 0.94 / 0.97))
    dk = {x["test"][:8]: x for x in A.deck_numbers({"arr": 1e6, "stage": "A", "burn_monthly": 1e6 / 12, "net_new_arr": -0.5e6}, 25e6)}
    ok &= check("Deck: 25x ARR fails the Series A bar; shrinking ARR leaves the burn multiple n/a, not a pass",
                dk["Price / "]["pass"] is False and dk["Burn mul"]["pass"] is None)
    # purchase: one series (price 1,200, 12 months, ten $5 uses, $100 income, no costs)
    pc = {"price": 1200, "life_years": 1, "resale_value": 0, "uses_per_month": 10, "rent_per_use": 5, "discount_rate": 0, "income_monthly": 100}
    r = A.purchase(pc)
    ok &= check("Purchase with income: buying leads by 600, pays back in 8 months, 121.84 % a year, and wins",
                near(r["npv_buy_vs_rent"], 600) and r["payback_months"] == 8 and near(r["irr"], 1.2184, 1e-4) and r["buy"] < r["rent"],
                f"{r['npv_buy_vs_rent']:.0f}, {F.pct(r['irr'], 2)}")
    ok &= check("Purchase: income lowers the break-even use, and at it buy = rent",
                r["breakeven_uses"] < A.purchase(dict(pc, income_monthly=0))["breakeven_uses"]
                and near(A.purchase(pc, uses=r["breakeven_uses"])["npv_buy_vs_rent"], 0))
    ls = A.purchase(dict(pc, income_monthly=0, lease={"monthly": 100, "months": 24}))
    ok &= check("A 24-month lease used for 12 months still owes 2,400", near(ls["lease"], 2400))
    # rental IRR stops the mortgage at payoff: 120k flat, 60k down, 1-year 0 % loan, 2-year hold, 12k net rent
    pm = A.property_model({"price": 120000, "down_pct": 0.5, "mortgage_rate": 0, "loan_years": 1, "horizon_years": 2, "rent_monthly": 1000,
                           "vacancy": 0, "management": 0, "tax_pct": 0, "upkeep_pct": 0, "insurance_yearly": 0, "appreciation": 0,
                           "rent_growth": 0, "closing_buy_pct": 0, "closing_sell_pct": 0})
    ok &= check("Rental IRR after the loan is repaid: +13.62 %", near(pm["irr"], 0.1362, 1e-4), F.pct(pm["irr"], 2))
    # gold-like history: calendar months under water, net winners, independent windows, no window
    hx = {"dates": ["2000-01-01", "2000-02-01", "2000-07-01", "2000-08-01"], "closes": [100, 90, 95, 110], "meta": {}, "source": "fixture"}
    ny = A.no_yield(hx, [(d, 100.0) for d in hx["dates"]], {})
    rep = A.no_yield_report("T", hx, "fixture", ny)
    ok &= check("No-yield: 6 calendar months under water (not 2 observations); 4 missing months; no hold window, no hold label",
                ny["longest_under_months"] == 6 and ny.get("gaps") == 4 and not ny["cases"] and "hold" not in rep["hero"]["label"])
    slow = A.no_yield(history_fixture(growth=0.001), [(d, 100.0) for d in history_fixture()["dates"]], {})
    ok &= check("No-yield: 0.1 % a year less 0.4 % carry wins in no window (net, not gross); 20 years hold 2 separate 10-year windows",
                slow["share_positive"] == 0 and slow.get("independent") == 2)
    # bonds: a one-year zero at 10 % returns 10.25 % whatever rates do; 7.3 years is not 7.5; quotes are per 100
    z = A.bond({"coupon": 0, "years": 1, "price": 90.70295})
    ok &= check("One-year zero bought at 90.70295 returns 10.25 % in every case", all(near(x, 0.1025, 1e-6) for _, x in z["one_year"]))
    ok &= check("Bond with 7.3 years left prices off dated flows, not 7.5 years",
                abs(A.bond_price(100, 0.05, 7.3, 0.08) - A.bond_price(100, 0.05, 7.5, 0.08)) > 0.1 and near(A.bond_price(100, 0.05, 7.0, 0.05), 100))
    k = A.bond({"coupon": 0.06, "years": 5, "price": 98, "face": 1000})
    ok &= check("Face 1,000 quoted at 98: price per 100 reads 98, the yield equals face 100's",
                near(k["price"], 98) and near(k["ytm"], A.bond({"coupon": 0.06, "years": 5, "price": 98})["ytm"]))
    # funds: calendar time; no adjusted closes stops
    fh = {"dates": ["2020-01-01", "2020-02-01", "2022-01-01"], "closes": [100, 100, 121], "adj": [100, 100, 121], "dividends": [], "source": "f"}
    ok &= check("Fund with prices in Jan 2020, Feb 2020 and Jan 2022 (100, 100, 121) earns 10 % a year", near(A.fund(fh, fh, 0)["fund_cagr"], 0.10))
    ok &= check("Fund with dividends but no adjusted closes: total return marked unavailable",
                "unavailable" in A.fund(dict(fh, dividends=[("2021-01-01", 5)]), fh, 0)["unavailable"])
    # collectibles
    one_raw = {"sales": [{"date": "2026-01-01", "price": 100, "grade": "raw"}], "grade": "PSA 10"}
    ok &= check("PSA 10 asked with only a raw sale: unvalued", A.collectible(one_raw)["cases"] == [])
    ok &= check("Grade odds with a grade that has no sales: no grading answer",
                A.collectible(dict(one_raw, grade="raw", grade_odds={"PSA 9": 0.5, "raw": 0.5}))["grade_ev"] is None)
    live = [("Charizard Base holofoil market (2026/10/15)", 954.65), ("Charizard Base holofoil low (2026/10/15)", 499.99),
            ("Charizard Base holofoil mid (2026/10/15)", 587.98), ("Charizard Base 1stEditionHolofoil market (2026/10/15)", 9999.0)]
    ok &= check("Live prices from two variants: price unavailable until \"variant\" names one", A.collectible({}, live)["cases"] == [] and "variant" in A.collectible({}, live)["unavailable"])
    cz = A.collectible({"variant": "holofoil", "fees": {"sell_pct": 0, "shipping": 0}}, live)
    page = str(A.collectible_report({"variant": "holofoil"}, cz))
    ok &= check("Charizard: base = the middle ask (587.98), not the 954.65 market; no 'quick sale' of an ask",
                near(cz["cases"][1][1], 587.98) and "quick sale against" not in page and "ask" in cz["cases"][0][0])
    # unit formats: $0.17 a GPU-hour is money, a beta is a number, a rate is a percent
    t = A.sources_table({"running_per_use": A.I(0.17, "s"), "beta": A.I(0.6, "s"), "discount_rate": A.I(0.04, "s")})
    html = S.table_html(t)
    ok &= check("Input tables: 0.17 per GPU-hour and beta 0.6 print as numbers, a discount rate as a percent",
                "0.17" in html and "17.0%" not in html and "60.0%" not in html and "4.0%" in html)
    return ok


def stop_text(fn):
    try:
        fn()
    except SystemExit as e:
        return str(e)
    return None


def facts_fixture():
    """A company-facts file with the review's traps: KO debt lines (CommercialPaper inside NotesAndLoansPayable), trade payables
    only, no total liabilities, MCD share counts in millions and a part-line D&A first, restricted cash, a Q1 for LTM, and the
    10-K revenue on the second tag."""
    fy = lambda s, e, v, form="10-K", filed="2026-02-20": {"start": s, "end": e, "val": v, "form": form, "filed": filed}
    bs = lambda e, v, form="10-K": {"end": e, "val": v, "form": form, "filed": "2026-02-20"}
    usd = lambda *es: {"units": {"USD": list(es)}}
    m = 1e6
    gaap = {
        "Revenues": usd(fy("2024-01-01", "2024-12-31", 90 * m), fy("2025-01-01", "2025-12-31", 100 * m),
                        fy("2025-01-01", "2025-03-31", 20 * m, "10-Q"), fy("2026-01-01", "2026-03-31", 35 * m, "10-Q")),
        "OperatingIncomeLoss": usd(fy("2025-01-01", "2025-12-31", 20 * m)),
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [fy("2025-01-01", "2025-12-31", 716.4)]}},
        "DepreciationDepletionAndAmortization": usd(fy("2025-01-01", "2025-12-31", 457 * m)),
        "DepreciationAndAmortization": usd(fy("2025-01-01", "2025-12-31", 2199 * m)),
        "LongTermDebtAndCapitalLeaseObligations": usd(bs("2025-12-31", 42119 * m)),
        "LongTermDebtAndCapitalLeaseObligationsCurrent": usd(bs("2025-12-31", 1822 * m)),
        "NotesAndLoansPayable": usd(bs("2025-12-31", 1551 * m)),
        "CommercialPaper": usd(bs("2025-12-31", 1495 * m)),
        "AccountsPayableTradeCurrent": usd(bs("2025-12-31", 5649 * m)),
        "Assets": usd(bs("2025-12-31", 104816 * m)), "LiabilitiesAndStockholdersEquity": usd(bs("2025-12-31", 104816 * m)),
        "StockholdersEquity": usd(bs("2025-12-31", 32169 * m)), "MinorityInterest": usd(bs("2025-12-31", 2106 * m)),
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": usd(bs("2025-12-31", 100 * m)),
        "RestrictedCashAndCashEquivalents": usd(bs("2025-12-31", 70 * m)),
    }
    gaap["Revenues"]["units"]["USD"][1]["form"] = "10-K"
    gaap = {"RevenueFromContractWithCustomerExcludingAssessedTax": usd(fy("2023-01-01", "2023-12-31", 80 * m, filed="2024-02-01")), **gaap}
    dei = {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2026-01-31", "val": 705.8, "filed": "2026-02-20", "form": "10-K"}]}}}
    return {"facts": {"us-gaap": gaap, "dei": dei}}


def company_fixes(out, lo):
    """The company-side review findings, each with the reviewer's own numbers."""
    import finman
    import fin_data as D
    import fin_xlsx as X
    ok = True
    # data layer: debt, cash, payables, liabilities, shares, D&A, LTM, 10-K date
    ko = {"debt_noncurrent": 42119, "debt_current": 1822, "short_borrowings": 1551, "commercial_paper": 1495, "debt_total": 43941}
    ok &= check("KO debt: 42,119 + 1,822 + 1,551 = 45,492; commercial paper inside notes and loans is not added again",
                D.debt_of(ko.get) == 45492)
    pep = {"debt_noncurrent": 42321, "debt_current_all": 6861, "short_borrowings": 6861, "debt_total": 46351}
    pep_q = {"debt_noncurrent": 42612, "debt_current": 1600, "short_borrowings": 10602, "commercial_paper": 6100}
    ok &= check("PEP debt: 49,182 on the 10-K; the 10-Q short-term line already holds current maturities (53,214)",
                D.debt_of(pep.get) == 49182 and D.debt_of(pep_q.get) == 53214)
    ok &= check("No debt line filed reads unavailable, not 0", D.debt_of({}.get) is None and D.cash_of({}.get) is None)
    real = D.company_facts
    D.company_facts = lambda t, cik=None: (facts_fixture(), "fixture", 1, "Fixture Co")
    try:
        fx = D.fundamentals("FIX")
    finally:
        D.company_facts = real
    A, e = fx["annual"], "2025-12-31"
    ok &= check("Fixture debt 45,492m, payables 5,649m (trade tag), liabilities 70,541m (L&E - equity incl. minority)",
                A["debt"][e] == 45492e6 and A["payables"][e] == 5649e6 and A["liabilities"][e] == 70541e6,
                f"{A['debt'][e] / 1e6:,.0f} / {A['payables'][e] / 1e6:,.0f} / {A['liabilities'][e] / 1e6:,.0f}")
    ok &= check("Restricted cash comes off: 100 incl. restricted - 70 restricted = 30", A["cash"][e] == 30e6)
    ok &= check("MCD files shares in millions: 716.4 reads as 716.4m; cover 705.8 as 705.8m",
                A["shares_diluted"][e] == 716.4e6 and fx["shares_cover"] == 705.8e6)
    ok &= check("D&A takes the largest line (MCD 2,199, not the part-line 457)", A["da"][e] == 2199e6)
    ok &= check("LTM counts a new Q1: FY 100 + Q1 35 - prior Q1 20 = 115", fx["ltm"]["revenue"] == 115e6 and fx["ltm"]["_asof"] == "2026-03-31")
    ok &= check("10-K filing date read from any revenue tag (KO showed 'filed None')", fx["last_10k"] == "2026-02-20")
    # beta: returns pair by date
    idx = {f"{2020 + k // 12}-{k % 12 + 1:02d}": 100 * 1.01 ** k for k in range(40)}
    asset = {m_: v * (1.5 if m_ >= "2021-01" else 1.0) for m_, v in idx.items() if m_ != "2020-12"}   # a 50 % jump across a missing month
    beta, months = D.beta_of(asset, idx)
    ok &= check("Beta skips returns across a missing month instead of pairing them with an index month", months == 37 and beta is not None,
                f"{months} months")
    # shares today, preferred, the valuation date
    f = sample()
    f["annual"]["shares_basic"] = {e_: 90e6 for e_ in ENDS}
    f["annual"]["shares_diluted"] = {e_: 90e6 for e_ in ENDS}
    f["shares_cover"], f["shares_cover_date"] = 80e6, "2027-01-31"
    ok &= check("Shares today: a buyback to 80m after the year counts (weighted 90m would show $8.89, not $10, on $800m)",
                abs(F.shares_now(f)[0] - 80) < 1e-9 and abs(800 / F.shares_now(f)[0] - 10) < 1e-9)
    f = sample()
    a = F.dcf_inputs(f)
    base = F.dcf(a)
    pr = F.dcf({**a, "preferred": {"value": 100.0, "source": ""}})
    ok &= check("Preferred stock comes off equity: $100m on 100m shares = $1.00 a share before the roll",
                abs(base["equity_bs"] - pr["equity_bs"] - 100) < 1e-9)
    days = {**a, "years_to_price": {"value": 321 / 365, "source": ""}, "years_to_bs": {"value": 0.0, "source": ""}}
    r0 = F.dcf({**days, "years_to_price": {"value": 0.0, "source": ""}})
    r1 = F.dcf(days)
    ok &= check("Valuation date: equity rolls to the price date by (1 + ke)^(321/365) (KO 2025-12-31 to 2026-11-17)",
                abs(r1["equity"] / r0["equity"] - (1 + r1["ke"]) ** (321 / 365)) < 1e-12)
    s_ = 0.75
    r2 = F.dcf({**a, "years_to_bs": {"value": s_, "source": ""}, "years_to_price": {"value": 0.0, "source": ""}})
    ok &= check("Balance-sheet roll: EV x (1 + WACC)^s - s x year-1 cash", abs(r2["ev"] - (r2["ev_fye"] * (1 + r2["wacc"]) ** s_ - s_ * r2["rows"][0]["fcf"])) < 1e-9)
    # terminal value pays for growth; WACC > g
    tv = F.terminal_fcf(1000, 0.10, 0.03, 103 / 0.12 / 1000) / (0.08 - 0.03)
    ok &= check("Terminal value pays for growth: NOPAT 103, g 3 %, return on new capital 12 %, WACC 8 % -> 1,545 (not 2,060)",
                abs(tv - 1545) < 1e-9, f"{tv:,.2f}")
    eq = F.dcf(a, wacc=0.05, g=0.05)
    ws, gs, grid = F.dcf_grid({**a, "terminal_g": {"value": base["wacc"] - 0.004, "source": ""}})
    ok &= check("WACC = g = 5 % gives no value (was a division by zero); grid cells with WACC <= g are blank",
                eq["value_per_share"] is None and any(x is None for row in grid for x in row))
    iw = F.implied_rate(a)
    ok &= check("Reverse DCF: the implied discount rate gives back the price",
                iw is not None and abs(F.dcf(a, wacc=iw)["value_per_share"] - a["price"]["value"]) < 1e-6, F.pct(iw))
    # overrides
    ok &= check("An unknown --set name stops the run instead of being ignored", stop_text(lambda: F.dcf_inputs(f, {"betta": 1.0})) is not None)
    gb = sample()
    gb["market"] = dict(gb["market"], currency="GBP")
    ok &= check("A price in GBP against USD filings stops and names --set price=", "--set price=" in (stop_text(lambda: F.dcf_inputs(gb)) or ""))
    low = sample()
    low["annual"]["debt"] = {e_: 15e6 for e_ in ENDS}   # KO before the fix: 1,654m interest on 1,495m of commercial paper
    ok &= check("Debt far below what the interest implies stops and names --set debt=", "--set debt=" in (stop_text(lambda: F.dcf_inputs(low)) or "")
                and stop_text(lambda: F.dcf_inputs(low, {"debt": 200.0})) is None)
    # LBO: premium before the entry EV; minority; revolver; limited liability
    la = F.lbo_inputs(f, {"premium": 0.75})
    ok &= check("LBO: a 75 % premium sets entry EV 3,500 = 12.73x EBITDA 275, and exit follows", abs(la["entry_multiple"]["value"] - 3500 / 275) < 1e-9
                and la["exit_multiple"]["value"] == la["entry_multiple"]["value"], F.mult(la["entry_multiple"]["value"]))
    bad = F.lbo({**la, "ebit_margin": {"value": -0.10, "source": ""}})
    ok &= check("LBO: a cash shortfall draws the revolver; cash never goes negative; exit equity never below 0",
                min(x["cash"] for x in bad["rows"]) >= -1e-9 and bad["rows"][0]["draw"] > 0 and bad["exit_equity"] >= 0)
    mi = F.lbo({**la, "minority": {"value": 30.0, "source": ""}})
    ok &= check("LBO: minority interest is not bought at entry and stays at exit", abs(F.lbo(la)["equity0"] - mi["equity0"] - 30) < 1e-9)
    # three statements: a loss pays nothing out; filed equity includes minority
    t = F.three_inputs(f, {"opex_pct": 0.9})
    m3 = F.three_statement(f, t)
    ok &= check("Three statements: a loss with 60 % payout pays 0 (it never adds cash)",
                all(r["dividends"] == 0 for r in m3["projection"] if r["net_income"] < 0) and m3["projection"][0]["net_income"] < 0)
    nci = sample()
    nci["annual"]["minority"] = {e_: 30e6 for e_ in ENDS}
    hh = F.three_statement(nci, F.three_inputs(nci))["history"][-1]
    ok &= check("Three statements: filed years check assets against liabilities + equity incl. minority (a gap shows)", abs(hh["check"] + 30) < 1e-9,
                f"gap {hh['check']:.1f}")
    # scorecard, comps, flags: a missing or negative denominator is never a pass
    neg = sample()
    neg["annual"]["ebit"] = {e_: -100e6 for e_ in ENDS}
    sc = {x["test"]: x for x in F.scorecard(neg, -20.0)}
    ok &= check("Scorecard: negative EBITDA and a negative DCF value are n/a, not passes",
                not sc["Debt / EBITDA 2.0x or less"]["pass"] and sc["Debt / EBITDA 2.0x or less"]["value"] is None
                and not sc["Price at least 25 % under DCF value"]["pass"])
    neg["annual"]["da"] = {e_: 0.0 for e_ in ENDS}
    neg["ltm"] = dict(neg["ltm"], ebit=-100e6, da=0.0, net_income=-80e6)
    cp = F.comps(neg, [sample(), sample()])
    ok &= check("Comps: no EV/EBITDA or P/E value for a loss-making target", "ev_ebitda" not in cp["implied"] and "pe" not in cp["implied"])
    gap = sample()
    gap["annual"]["cfo"][ENDS[-1]] = None
    gap["annual"]["receivables"][ENDS[-1]] = None
    fl = {x["check"]: x["flag"] for x in F.red_flags(gap)}
    ok &= check("Red flags: unknown CFO and receivables read n/a, never a flag or a crash",
                fl["Profit not backed by cash (Sloan accruals)"] is None and fl["Receivables grow faster than revenue"] is None)
    nod = sample()
    nod["annual"]["debt_noncurrent"] = {e_: None for e_ in ENDS}
    pf = dict(F.piotroski(nod)[1])
    ok &= check("Piotroski: missing debt in both years is n/a, not a point", pf["Long-term debt / assets down"] is None)
    # quarters: EPS is not subtracted
    qf = sample()
    qr = F.quarter_table(qf, 5)
    ok &= check("Earnings: a fiscal-Q4 EPS is not derived by subtraction (100,100,100,50 shares: 1.571 vs the true 2)",
                all(r["eps"] is None for r in qr if r["end"] in ENDS) and any(r["revenue"] for r in qr if r["end"] in ENDS))
    # budget: deficits spend the cash
    bd = F.budget({"net_income_monthly": 1000, "emergency_fund": 3000, "lines": [
        {"name": "Needs", "amount": 1100, "bucket": "needs"}, {"name": "ETF", "amount": 200, "bucket": "savings"}]})
    ok &= check("Budget: 1,000 in, 1,100 needs, 200 ETF, 3,000 fund: cash is gone in month 10 (was 5,400 after a year)",
                bd["path"][10] == 0 and bd["gap_month"] == 11 and bd["path"][12] == -600)
    # the report bridge draws every step; the workbook follows the horizon and audit compares cells
    rep = RP.dcf_report(f, a, base, F.dcf_grid(a))
    wf = rep["charts"][0]["steps"]
    ok &= check("Waterfall: the steps after EV (minority included) add up to the equity bar",
                any(n_ == "Minority interest" for n_, _, _ in wf) and abs(wf[2][1] + sum(x for _, x, k in wf[3:-1]) - wf[-1][1]) < 1e-6)
    a3 = F.dcf_inputs(f, {"years": 3})
    p3 = out / "smpl-dcf-3y.xlsx"
    _, cells = X.dcf_book(f, a3, str(p3))
    ok &= check("Workbook models the same horizon as Python: 3 years -> value cell expected at Python's 3-year value",
                abs(cells["expect"][cells["value_per_share"]] - F.dcf(a3)["value_per_share"]) < 1e-12 and len(F.dcf(a3)["rows"]) == 3)
    if lo:
        p3.with_suffix(".cells.json").write_text(json.dumps(cells), encoding="utf-8")
        good, lines = finman.audit(p3)
        ok &= check("Audit compares the 3-year workbook's cells with Python", good and sum(1 for x in lines if x.startswith("cell PASS")) >= 3, lines[0])
    # --set values are read before any fetch
    seen = {}
    real_company = D.company
    D.company = lambda t, years=5, with_market=True, with_rf=True, cik=None: seen.update(market=with_market, rf=with_rf) or sample()
    try:
        finman.main(["dcf", "SMPL", "--set", "price=100", "--set", "beta=1", "--set", "rf=0.04", "--formats", "html", "--out", str(out / "sets")])
    finally:
        D.company = real_company
    ok &= check("dcf with --set price, beta and rf fetches neither Yahoo nor FRED", seen == {"market": False, "rf": False})
    return ok


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
    ig = F.implied(a, "growth_y1")
    back = F.dcf({**a, "growth_y1": {"value": ig, "source": ""}})["value_per_share"]
    ok &= check("Reverse DCF: the implied growth gives back the price", ig is not None and abs(back - a["price"]["value"]) < 1e-6,
                f"{F.pct(ig)} -> {F.per_share(back)}")
    ok &= check("Reverse DCF: None when no growth reaches the price",
                F.implied({**a, "price": {"value": 1e6, "source": ""}}, "growth_y1") is None)
    sc = [x["value_per_share"] for x in F.scenarios(a)]
    ok &= check("Scenarios: bear < base < bull, base = the model", sc[0] < sc[1] < sc[2] and abs(sc[1] - base["value_per_share"]) < 1e-9)
    mi = F.dcf({**a, "minority": {"value": 50.0, "source": ""}})
    ok &= check("Minority interest comes off the equity value", abs(base["equity_bs"] - mi["equity_bs"] - 50.0) < 1e-9)
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
    f["history"] = history_fixture(2007, 20, 0.05, 1.0)
    f["market"] = dict(f["market"], price_time="2027-03-01")
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
        if lo and xl:   # audit reads the Python numbers from the cells.json the writer saved beside the workbook
            good, lines = finman.audit(out / f"smpl-{kind}.xlsx")
            compared = sum(1 for x in lines if x.startswith("cell "))
            ok &= check(f"{kind}: workbook recalculates with no errors, checks TRUE, cells = Python", good,
                        f"{lines[0]}, {compared} cells compared")
    rep = RP.budget_report(b)
    files = finman.write_outputs(rep, "budget", out, {"xlsx", "pptx", "svg", "html"}, lambda p: X.budget_book(b, p))
    ok &= check("budget: files written", len(files) >= 4)
    if lo:
        good, lines = finman.audit(out / "budget.xlsx", {"Budget!" + json.loads((out / "budget.cells.json").read_text())["left"].split("!")[1]: 700.0})
        ok &= check("budget: workbook recalculates, left over = 700", good, lines[0])
    else:
        print("SKIP  workbook recalculation (LibreOffice not installed)")
    ok &= assets(out)
    ok &= asset_review_cases()
    ok &= company_fixes(out, lo)
    page = (out / "smpl-dcf.html").read_text(encoding="utf-8")
    ok &= check("HTML leads with the answer", page.index('class="hero"') < page.index("<table"))
    ok &= check("HTML walks the method step by step before the tables",
                page.count("<li>") >= 10 and page.index('class="steps"') < page.index("<table"))
    print("PASS" if ok else "FAIL", f"(files in {out})")
    return 0 if ok else 1
