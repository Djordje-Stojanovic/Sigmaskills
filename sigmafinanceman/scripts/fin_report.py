"""Turns a model result into one report: a hero line (the answer first), a small KPI row, tables and charts.

The HTML page, the SVG charts and the slide deck all draw this one structure, so the three never disagree.
Table cell: a number (formatted by the column's format) or text. Formats: money, pct, x (multiple), ps (per share), text, int.
Chart kinds: waterfall (steps), bars (series over labels), hbars (label, value), football (label, low, high + a marker line).
"""
import fin_models as F


def T(title, columns, rows, formats, totals=(), note=None, double=()):
    return {"title": title, "columns": columns, "rows": rows, "formats": formats, "totals": list(totals), "double": list(double), "note": note}


def sources_of(a):
    return [(F.LABELS.get(k, k), v["value"], v["source"]) for k, v in a.items()]


def dcf_report(f, a, r, grid):
    ws, gs, vals = grid
    v = lambda k: a[k]["value"]
    rows = r["rows"]
    yrs = [f"Y{x['year']}" for x in rows]
    proj = T("Free cash flow projection ($m)", ["Line"] + yrs,
             [["Revenue"] + [x["revenue"] for x in rows], ["Growth"] + [x["growth"] for x in rows],
              ["EBIT"] + [x["ebit"] for x in rows], ["NOPAT"] + [x["nopat"] for x in rows], ["D&A"] + [x["da"] for x in rows],
              ["Capex"] + [-x["capex"] for x in rows], ["Change in working capital"] + [-x["dnwc"] for x in rows],
              ["Unlevered free cash flow"] + [x["fcf"] for x in rows], ["Discount period"] + [x["period"] for x in rows],
              ["PV of free cash flow"] + [x["pv"] for x in rows]],
             ["text"] + ["money"] * len(yrs), totals=[7, 9],
             )
    proj["row_formats"] = {1: "pct", 8: "num1"}
    bs_date, price_date = a["debt"]["source"].split("balance sheet of ")[-1][:10], f.get("market", {}).get("price_time", "")
    bridge = T(f"Enterprise value to value per share ($m), valued on {price_date}", ["Step", "Value"],
               [["PV of free cash flows", r["pv_fcf"]], ["PV of terminal value", r["pv_tv"]], [f"Enterprise value at {f['fiscal_year_ends'][-1]}", r["ev_fye"]],
                [f"Enterprise value at {bs_date} (rolled forward, less cash earned since)", r["ev"]],
                ["Less debt", -v("debt")], ["Plus cash and investments", v("cash")], ["Less minority interest", -v("minority")],
                ["Less preferred stock", -v("preferred")], ["Plus equity-method stakes (book)", v("investments")],
                [f"Equity value at {bs_date}", r["equity_bs"]], [f"Equity value at {price_date} (x (1 + cost of equity) for the days between)", r["equity"]],
                ["Diluted shares today (m)", v("shares")], ["Value per share", r["value_per_share"]]],
               ["text", "money"], totals=[2, 3, 10], double=[12])
    bridge["row_formats"] = {12: "ps"}
    ig, im, iw = F.implied(a, "growth_y1"), F.implied(a, "ebit_margin", -0.5, 0.95), F.implied_rate(a)
    rev_dcf = T("What the price implies (reverse DCF)", ["Input", "Model", "Price implies"],
                [["Discount rate (WACC)", r["wacc"], iw], ["Revenue growth, year 1", v("growth_y1"), ig], ["EBIT margin", v("ebit_margin"), im]],
                ["text", "pct", "pct"],
                note="Each row moves one input until the DCF value equals the price, all else held. Blank: no value reaches the price. "
                     "Growth fades to the terminal rate in a straight line, so implied year-1 growth can look extreme; the implied "
                     "discount rate is the steadier read. Compare it with the risk-free rate.")
    sc = F.scenarios(a)
    scen = T("Bear, base and bull", ["Case", "Growth, year 1", "EBIT margin", "Value per share", "vs price"],
             [[x["name"], x["growth_y1"], x["ebit_margin"], x["value_per_share"], (x["value_per_share"] / v("price") - 1) if v("price") else None]
              for x in sc], ["text", "pct", "pct", "ps", "pct"],
             note=f"Bear and bull move year-1 growth by {F.pct(F.SCENARIO_STEP['growth_y1'], 0)} and the EBIT margin by "
                  f"{F.pct(F.SCENARIO_STEP['ebit_margin'], 0)} from the base case.")
    y1, yn = rows[0], rows[-1]
    n = len(rows)
    steps = [
        f"Start from what the company sold: revenue of ${F.money(v('revenue_base'))}m in the last fiscal year (10-K).",
        f"Grow it: {F.pct(v('growth_y1'))} in year 1 ({a['growth_y1']['source']}), slowing each year to {F.pct(r['g'])} "
        f"by year {n}. Revenue in year {n}: ${F.money(yn['revenue'])}m.",
        f"Keep the operating profit: an EBIT margin of {F.pct(v('ebit_margin'))} gives ${F.money(y1['ebit'])}m in year 1; "
        f"after {F.pct(v('tax_rate'))} tax, ${F.money(y1['nopat'])}m.",
        f"Turn profit into cash: add back D&A, subtract capex and the extra working capital. Free cash flow: "
        f"${F.money(y1['fcf'])}m in year 1, ${F.money(yn['fcf'])}m in year {n}.",
        f"Price the waiting: shareholders want {F.pct(r['ke'])} a year (risk-free {F.pct(v('rf'))} + beta {v('beta'):.2f} x "
        f"{F.pct(v('erp'))} premium); blended with the cheaper debt, the discount rate (WACC) is {F.pct(r['wacc'])}.",
        f"Discount: a dollar in year {n} is worth {1 / (1 + r['wacc']) ** yn['period']:.2f} today. The {n} years of cash are "
        f"worth ${F.money(r['pv_fcf'])}m today.",
        f"Everything after year {n} (terminal value): year-{n} cash growing {F.pct(r['g'])} a year forever, worth "
        f"${F.money(r['pv_tv'])}m today, {F.pct(r['tv_share'])} of the total.",
        f"Move it to today: enterprise value ${F.money(r['ev_fye'])}m at the year-end becomes ${F.money(r['ev'])}m on the balance "
        f"sheet of {bs_date}; less debt ${F.money(v('debt'))}m, plus cash ${F.money(v('cash'))}m"
        + (f", less minority interest ${F.money(v('minority'))}m" if v("minority") else "")
        + (f", less preferred ${F.money(v('preferred'))}m" if v("preferred") else "")
        + (f", plus equity-method stakes ${F.money(v('investments'))}m at book" if v("investments") else "")
        + f": equity worth ${F.money(r['equity'])}m on {price_date}.",
        f"Split over {F.money(v('shares'))}m diluted shares today: {F.per_share(r['value_per_share'])} a share, "
        f"{F.pct(r['upside'])} against the price of {F.per_share(v('price'))}.",
        "Turn it round: " + (f"the price implies a discount rate of {F.pct(iw)} (the model uses {F.pct(r['wacc'])}; the 10-year Treasury pays "
                             f"{F.pct(v('rf'))})" if iw is not None else "no discount rate up to 50 % gives the price")
        + (f", or year-1 growth of {F.pct(ig)} instead of {F.pct(v('growth_y1'))}." if ig is not None and abs(ig) <= 0.25 else "."),
    ]
    sens = T("Value per share: WACC (rows) by terminal growth (columns)", ["WACC"] + [F.pct(g) for g in gs],
             [[F.pct(w)] + vals[i] for i, w in enumerate(ws)], ["text"] + ["ps"] * len(gs))
    sens["center"] = (2, 3)
    inputs = T("Inputs and where they come from", ["Input", "Value", "Source"],
               [[k, val, s] for k, val, s in sources_of(a)], ["text", "auto", "text"])
    inner = [vals[i][j] for i in (1, 2, 3) for j in (1, 2, 3)]
    verdict = "under" if (r["upside"] or 0) > 0 else "over"
    return {
        "kind": "dcf", "title": f"{f['name']} ({f['ticker']}) DCF",
        "subtitle": f"Latest 10-K: fiscal year ended {f['fiscal_year_ends'][-1]} (filed {f.get('last_10k') or 'date not in the SEC facts'}). "
                    f"Balance sheet of {bs_date}; valued on {price_date}. Money in $ millions.",
        "hero": {"value": F.per_share(r["value_per_share"]), "label": "DCF value per share, base case",
                 "line": f"{F.pct(r['upside'])} vs the price of {F.per_share(v('price'))}: the market price looks {verdict}valued on these inputs."},
        "kpis": [("Enterprise value", F.money(r["ev"])), ("WACC", F.pct(r["wacc"])), ("Terminal growth", F.pct(r["g"])),
                 ("Terminal value share of EV", F.pct(r["tv_share"])), ("Range (inner 3x3)", f"{F.per_share(min(inner))} to {F.per_share(max(inner))}"),
                 ("Price implies WACC", F.pct(iw))],
        "steps": steps,
        "tables": [bridge, scen, rev_dcf, proj, sens, inputs],
        "charts": [{"kind": "waterfall", "title": "From cash flows to value per share ($m)",
                    "steps": [("PV of cash flows", r["pv_fcf"], "part"), ("PV of terminal value", r["pv_tv"], "part"),
                              ("Enterprise value", r["ev_fye"], "total"), ("Roll to " + bs_date, r["ev"] - r["ev_fye"], "delta"),
                              ("Debt", -v("debt"), "delta"), ("Cash", v("cash"), "delta"), ("Minority interest", -v("minority"), "delta"),
                              ("Preferred", -v("preferred"), "delta"), ("Equity-method stakes", v("investments"), "delta"),
                              ("Roll to " + price_date, r["equity"] - r["equity_bs"], "delta"), ("Equity value", r["equity"], "total")]},
                   {"kind": "bars", "title": "Revenue and free cash flow ($m)", "labels": yrs,
                    "series": [("Revenue", [x["revenue"] for x in rows], "total"), ("Free cash flow", [x["fcf"] for x in rows], "part")]}],
        "notes": [f"Mid-year discounting (periods 0.5 to {n - 0.5}) from the fiscal year-end; the terminal value is discounted at the last "
                  "period, as the cash flows are. The value then rolls to the balance-sheet date at WACC, less the year-1 cash already earned, "
                  "and to the price date at the cost of equity.",
                  f"Growth costs capital: capex fades to D&A plus {F.pct(v('ppe_pct'))} of each extra dollar of sales (PP&E / revenue), and the "
                  f"terminal cash flow pays for growth: ${F.money(r['fcf_terminal'])}m.",
                  f"Terminal value is {F.pct(r['tv_share'])} of enterprise value; 50-75 % is normal, above 75 % the answer leans on the "
                  "terminal assumptions, under 40 % the terminal inputs may be too low.",
                  "The scenarios and the reverse DCF are computed in Python; the workbook holds the base case: change an input there to test one."],
        "sources": [f["source"], f["market"]["source"], f.get("rf_source", "")],
    }


def lbo_report(f, a, r, grid):
    es, xs, vals = grid
    rows = r["rows"]
    yrs = [f"Y{x['year']}" for x in rows]
    sched = T("Debt schedule and cash flow ($m)", ["Line"] + yrs,
              [["EBITDA"] + [x["ebitda"] for x in rows], ["Capex"] + [-x["capex"] for x in rows],
               ["Change in working capital"] + [-x["dnwc"] for x in rows], ["Interest"] + [-x["interest"] for x in rows],
               ["Tax"] + [-x["tax"] for x in rows], ["Free cash flow"] + [x["fcf"] for x in rows],
               ["Debt repaid"] + [-x["paydown"] for x in rows], ["Revolver drawn"] + [x["draw"] for x in rows],
               ["Debt at year end"] + [x["debt"] for x in rows],
               ["Cash at year end"] + [x["cash"] for x in rows]], ["text"] + ["money"] * len(yrs), totals=[5, 8])
    su = T("Sources and uses at entry ($m)", ["Item", "Value"],
           [["Entry enterprise value", r["ev0"]], ["Fees", r["ev0"] * a["fees"]["value"]], ["Total uses", r["ev0"] * (1 + a["fees"]["value"])],
            ["Senior debt", r["debt0"]], ["Minority interest (stays)", a["minority"]["value"]], ["Sponsor equity", r["equity0"]],
            ["Total sources", r["debt0"] + a["minority"]["value"] + r["equity0"]]],
           ["text", "money"], totals=[2, 6], double=[6])
    sens = T("IRR: entry multiple (rows) by exit multiple (columns)", ["Entry"] + [F.mult(x) for x in xs],
             [[F.mult(e)] + vals[i] for i, e in enumerate(es)], ["text"] + ["pct"] * len(xs))
    sens["center"] = (2, 3)
    inputs = T("Inputs and where they come from", ["Input", "Value", "Source"], [[k, val, s] for k, val, s in sources_of(a)], ["text", "auto", "text"])
    return {
        "kind": "lbo", "title": f"{f['name']} ({f['ticker']}) LBO",
        "subtitle": f"Take-private at a {F.pct(a['premium']['value'], 0)} premium, {a['leverage']['value']:.1f}x senior debt, {int(a['years']['value'])}-year hold. $ millions.",
        "hero": {"value": F.pct(r["irr"]), "label": "Sponsor IRR, base case",
                 "line": f"{F.mult(r['moic'])} money multiple: {F.money(r['equity0'])} in, {F.money(r['exit_equity'])} out at {F.mult(r['exit'])} exit."},
        "kpis": [("Entry EV", F.money(r["ev0"])), ("Entry multiple", F.mult(r["entry"])), ("Debt at entry", F.money(r["debt0"])),
                 ("Debt left at exit", F.money(rows[-1]["debt"])), ("Exit EV", F.money(r["exit_ev"]))],
        "tables": [su, sched, sens, inputs],
        "charts": [{"kind": "bars", "title": "Debt paid down ($m)", "labels": ["Entry"] + yrs,
                    "series": [("Debt", [r["debt0"]] + [x["debt"] for x in rows], "total")]},
                   {"kind": "waterfall", "title": "Equity in to equity out ($m)",
                    "steps": [("Equity in", r["equity0"], "total"), ("Value created", r["exit_equity"] - r["equity0"], "delta"),
                              ("Equity out", r["exit_equity"], "total")]}],
        "notes": ["Interest is charged on the opening debt of each year (no circular reference).",
                  "All free cash flow repays debt until it is gone, then builds cash; a shortfall is drawn on a revolver at the debt rate.",
                  "Exit equity = exit EV - debt + cash - minority interest, never below zero.",
                  "IRR = money multiple ^ (1 / years) - 1: no dividends during the hold."],
        "sources": [f["source"], f["market"]["source"]],
    }


def comps_report(c, dcf_range=None):
    t, peers, st = c["target"], c["peers"], c["stats"]
    cols = ["Company", "Price", "Market cap", "EV", "LTM revenue", "LTM EBITDA", "EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E", "Growth", "EBIT margin"]
    fm = ["text", "ps", "money", "money", "money", "money", "x", "x", "x", "x", "pct", "pct"]
    row = lambda r: [r["ticker"], r["price"], r["mcap"], r["ev"], r["revenue"], r["ebitda"], r["ev_rev"], r["ev_ebitda"], r["ev_ebit"], r["pe"], r["growth"], r["ebit_margin"]]
    rows = [row(r) for r in peers]
    for k, lab in (("max", "Maximum"), ("q3", "75th percentile"), ("median", "Median"), ("q1", "25th percentile"), ("min", "Minimum")):
        rows.append([lab, None, None, None, None, None] + [(st[m] or {}).get(k) for m in ("ev_rev", "ev_ebitda", "ev_ebit", "pe")] + [None, None])
    rows.append(row(t))
    table = T("Trading comparables ($m, LTM)", cols, rows, fm, totals=[len(peers) + 2], double=[len(rows) - 1])
    ff = [("52-week range", t["low_52w"], t["high_52w"])]
    names = {"ev_ebitda": "EV/EBITDA 25th-75th", "pe": "P/E 25th-75th", "ev_rev": "EV/Revenue 25th-75th"}
    for m in ("ev_ebitda", "pe", "ev_rev"):
        if m in c["implied"]:
            ff.append((names[m], c["implied"][m]["q1"], c["implied"][m]["q3"]))
    if dcf_range:
        ff.append(("DCF (inner 3x3)", dcf_range[0], dcf_range[1]))
    med = c["implied"].get("ev_ebitda", {}).get("median")
    return {
        "kind": "comps", "title": f"{t['name']} ({t['ticker']}) trading comparables",
        "subtitle": f"Peers: {', '.join(p['ticker'] for p in peers)}. LTM to {t['ltm_asof']}; prices from Yahoo chart data.",
        "hero": {"value": F.per_share(med), "label": "Implied value per share at the peer median EV/EBITDA",
                 "line": f"{F.pct(F.div(med, t['price']) - 1 if med and t['price'] else None)} vs the price of {F.per_share(t['price'])}; "
                         f"{t['ticker']} trades at {F.mult(t['ev_ebitda'])} EV/EBITDA against a peer median of {F.mult((st['ev_ebitda'] or {}).get('median'))}."},
        "kpis": [("Market cap", F.money(t["mcap"])), ("EV", F.money(t["ev"])), ("EV/EBITDA", F.mult(t["ev_ebitda"])), ("P/E", F.mult(t["pe"])),
                 ("Peers", str(len(peers)))],
        "tables": [table],
        "charts": [{"kind": "football", "title": "Football field: value per share", "rows": ff, "marker": ("Price", t["price"])},
                   {"kind": "hbars", "title": "EV/EBITDA by company", "rows": sorted([(r["ticker"], r["ev_ebitda"]) for r in peers + [t]
                                                                                       if r["ev_ebitda"]], key=lambda x: -x[1]), "fmt": "x",
                    "highlight": t["ticker"]}],
        "notes": ["EV = market cap + debt - cash and short-term investments + minority interest + preferred - equity-method stakes; "
                  "leases are left out. Balance sheet and shares are the newest filed; a loss gives no EV/EBITDA or P/E value.",
                  "Quartiles are Excel QUARTILE.INC over the peers only; the target is not in its own statistics."],
        "sources": ["SEC company facts per ticker (data.sec.gov)", "Yahoo chart prices"],
    }


def ratios_report(f, R):
    keys = [("Gross margin", "gross_margin", "pct"), ("EBIT margin", "ebit_margin", "pct"), ("Net margin", "net_margin", "pct"),
            ("Return on equity", "roe", "pct"), ("Return on assets", "roa", "pct"), ("Return on invested capital", "roic", "pct"),
            ("Revenue growth", "revenue_growth", "pct"), ("Current ratio", "current", "x"), ("Quick ratio", "quick", "x"),
            ("Debt / equity", "debt_equity", "x"), ("Debt / EBITDA", "debt_ebitda", "x"), ("Interest cover", "interest_cover", "x"),
            ("Asset turnover", "asset_turnover", "x"), ("Receivable days", "dso", "num1"), ("Inventory days", "dio", "num1"),
            ("Payable days", "dpo", "num1"), ("Free cash flow ($m)", "fcf", "money"), ("FCF margin", "fcf_margin", "pct"),
            ("Cash conversion (FCF / NI)", "cash_conversion", "x"), ("Diluted EPS", "eps", "ps"), ("Payout ratio", "payout", "pct"),
            ("Stock pay / revenue", "sbc_pct", "pct")]
    yrs = [r["end"][:4] for r in R]
    rows = [[lab] + [r[k] for r in R] for lab, k, _ in keys]
    t = T("Ratios by fiscal year", ["Ratio"] + yrs, rows, ["text"] + ["auto"] * len(yrs))
    t["row_formats"] = {i: fm for i, (_, _, fm) in enumerate(keys)}
    last = R[-1]
    return {"kind": "ratios", "title": f"{f['name']} ({f['ticker']}) ratios",
            "subtitle": f"Five fiscal years from the 10-K filings, latest year ended {f['fiscal_year_ends'][-1]}.",
            "hero": {"value": F.pct(last["roic"]), "label": "Return on invested capital, latest year",
                     "line": f"EBIT margin {F.pct(last['ebit_margin'])}, FCF margin {F.pct(last['fcf_margin'])}, debt {F.mult(last['debt_ebitda'])} EBITDA."},
            "kpis": [("Gross margin", F.pct(last["gross_margin"])), ("ROE", F.pct(last["roe"])), ("Current ratio", F.mult(last["current"])),
                     ("Interest cover", F.mult(last["interest_cover"])), ("Cash conversion", F.mult(last["cash_conversion"]))],
            "tables": [t],
            "charts": [{"kind": "bars", "title": "Margins by year", "labels": yrs, "fmt": "pct",
                        "series": [("Gross", [r["gross_margin"] for r in R], "part"), ("EBIT", [r["ebit_margin"] for r in R], "total"),
                                   ("Net", [r["net_margin"] for r in R], "muted")]}],
            "notes": ["ROIC = EBIT x (1 - tax rate) / (equity + debt - cash)."], "sources": [f["source"]]}


def analysis_report(f, R, flags, z, pf):
    _, hist, _ = F.view(f)
    ends = f["fiscal_year_ends"]
    rev = hist("revenue")
    cs = []
    for lab, c in (("Revenue", "revenue"), ("Cost of revenue", "cogs"), ("Gross profit", "gross_profit"), ("R&D", "rnd"),
                   ("Operating income", "ebit"), ("Tax", "tax"), ("Net income", "net_income")):
        cs.append([lab] + [F.div(x, r) for x, r in zip(hist(c), rev)])
    common = T("Common-size income statement (share of revenue)", ["Line"] + [e[:4] for e in ends], cs, ["text"] + ["pct"] * len(ends), totals=[6])
    bs = []
    ta = hist("assets")
    for lab, c in (("Cash", "cash"), ("Receivables", "receivables"), ("Inventory", "inventory"), ("PP&E", "ppe"), ("Total assets", "assets"),
                   ("Payables", "payables"), ("Total liabilities", "liabilities"), ("Equity", "equity")):
        bs.append([lab] + [F.div(x, t) for x, t in zip(hist(c), ta)])
    common_bs = T("Common-size balance sheet (share of total assets)", ["Line"] + [e[:4] for e in ends], bs, ["text"] + ["pct"] * len(ends), totals=[4])
    yoy = []
    for lab, c in (("Revenue", "revenue"), ("Operating income", "ebit"), ("Net income", "net_income"), ("Operating cash flow", "cfo"),
                   ("Capex", "capex"), ("Receivables", "receivables"), ("Total debt", None)):
        h = hist(c or "debt")
        yoy.append([lab] + [None] + [F.div(b, a) - 1 if a and b is not None else None for a, b in zip(h, h[1:])])
    growth = T("Year-on-year growth", ["Line"] + [e[:4] for e in ends], yoy, ["text"] + ["pct"] * len(ends))
    ft = T("Red-flag checks (latest year vs the year before)", ["Check", "Result", "Measured", "Why it matters"],
           [[x["check"], "n/a" if x["flag"] is None else "FLAG" if x["flag"] else "clear", x["measure"], x["why"]] for x in flags], ["text"] * 4)
    ft["status_col"] = 1
    known = sum(1 for _, ok in pf[1] if ok is not None)
    pt = T(f"Piotroski F-score: {pf[0]} of 9 ({known} measurable)", ["Signal", "Result"],
           [[n, "n/a" if ok is None else "pass" if ok else "fail"] for n, ok in pf[1]], ["text", "text"])
    pt["status_col"] = 1
    n_flags = sum(1 for x in flags if x["flag"])
    n_known = sum(1 for x in flags if x["flag"] is not None)
    return {"kind": "analysis", "title": f"{f['name']} ({f['ticker']}) statement analysis",
            "subtitle": f"Common-size statements, growth and forensic checks, fiscal years {ends[0][:4]}-{ends[-1][:4]}.",
            "hero": {"value": f"{n_flags} of {n_known}", "label": "red-flag checks raised" + (f" ({len(flags) - n_known} unavailable)" if n_known < len(flags) else ""),
                     "line": f"Altman Z {z:.1f} ({'safe' if z and z > 2.99 else 'grey' if z and z > 1.81 else 'distress'} zone), Piotroski F-score {pf[0]} of 9."
                     if z else f"Piotroski F-score {pf[0]} of 9."},
            "kpis": [("Altman Z", f"{z:.2f}" if z else "n/a"), ("Piotroski F", f"{pf[0]} / 9"), ("Revenue growth", F.pct(R[-1]["revenue_growth"])),
                     ("Cash conversion", F.mult(R[-1]["cash_conversion"])), ("Stock pay / revenue", F.pct(R[-1]["sbc_pct"]))],
            "tables": [ft, common, common_bs, growth, pt],
            "charts": [{"kind": "bars", "title": "Net income and operating cash flow ($m)", "labels": [e[:4] for e in ends],
                        "series": [("Net income", hist("net_income"), "part"), ("Operating cash flow", hist("cfo"), "total")]}],
            "notes": ["A flag is a question for the notes of the 10-K, not a verdict.", "Altman Z: above 2.99 safe, 1.81-2.99 grey, below 1.81 distress."],
            "sources": [f["source"]]}


def score_report(f, sc, dcf_value):
    n = sum(1 for x in sc if x["pass"])
    t = T("Value-investing scorecard", ["Test", "Measured", "Result"], [[x["test"], x["shown"], "pass" if x["pass"] else "fail"] for x in sc],
          ["text", "text", "text"])
    t["status_col"] = 2
    return {"kind": "score", "title": f"{f['name']} ({f['ticker']}) value scorecard",
            "subtitle": "Ten tests in the Buffett and Graham tradition on the filed numbers; the last one uses the base-case DCF.",
            "hero": {"value": f"{n} of {len(sc)}", "label": "tests passed",
                     "line": f"DCF value {F.per_share(dcf_value)} against a price of {F.per_share(f['market']['price'])}."},
            "kpis": [(x["test"].split(" (")[0], x["shown"]) for x in sc[:5]],
            "tables": [t], "charts": [{"kind": "hbars", "title": "Pass (1) or fail (0) per test", "rows": [(x["test"], 1.0 if x["pass"] else 0.0) for x in sc],
                                       "fmt": "int", "status": True}],
            "notes": ["Owner earnings = net income + D&A - capex (Buffett, 1986 letter)."], "sources": [f["source"], f["market"]["source"]]}


def earnings_report(f, e):
    fm = lambda k: "ps" if k == "eps" else "money"
    rows = [[l["line"], l["now"], l["year_ago"], l["yoy"], l["prev"], l["qoq"]] for l in e["lines"]]
    t = T(f"Quarter ended {e['quarter_end']} ($m)", ["Line", "This quarter", "Year ago", "YoY", "Prior quarter", "QoQ"], rows,
          ["text", "money", "money", "pct", "money", "pct"])
    t["row_formats"] = {i: ("ps" if l["key"] == "eps" else None) for i, l in enumerate(e["lines"])}
    m = e["margins"]
    rev = e["lines"][0]
    q = e["rows"]
    return {"kind": "earnings", "title": f"{f['name']} ({f['ticker']}) earnings review",
            "subtitle": f"Quarter ended {e['quarter_end']} from the SEC filings (a fiscal Q4 = the 10-K year minus three 10-Q quarters).",
            "hero": {"value": F.pct(rev["yoy"]), "label": "revenue growth vs the same quarter a year ago",
                     "line": f"Gross margin {F.pct(m['gross_now'])} (a year ago {F.pct(m['gross_year_ago'])}), operating margin {F.pct(m['op_now'])} "
                             f"(a year ago {F.pct(m['op_year_ago'])})."},
            "kpis": [(l["line"], F.money(l["now"]) if l["key"] != "eps" else F.per_share(l["now"])) for l in e["lines"][:5]],
            "tables": [t],
            "charts": [{"kind": "bars", "title": "Revenue and operating income by quarter ($m)", "labels": [r["end"][:7] for r in q],
                        "series": [("Revenue", [r["revenue"] for r in q], "total"), ("Operating income", [r["ebit"] for r in q], "part")]}],
            "notes": ["No consensus estimates: free sources carry none, so the review compares against the company's own past.",
                      "A quarter not filed alone is a year to date minus the one before (fiscal Q4 = the year minus nine months). "
                      "EPS does not subtract, so a quarter without a filed EPS shows n/a."],
            "sources": [f["source"]]}


def budget_report(b):
    cur = b["currency"]
    rows = [[l["name"], l["bucket"], l["amount"], F.div(l["amount"], b["net"])] for l in sorted(b["lines"], key=lambda l: (F.BUCKETS.index(l["bucket"]), -l["amount"]))]
    lines = T(f"Monthly lines ({cur})", ["Line", "Bucket", "Amount", "Share of pay"], rows, ["text", "text", "money", "pct"])
    split = T("50/30/20 check", ["Bucket", "Now", "Share", "Target", "Gap"],
              [[k, b["totals"][k], b["share"][k], b["target"][k], b["gap"][k]] for k in F.BUCKETS] + [["Left over", b["left"], F.div(b["left"], b["net"]), None, None]],
              ["text", "money", "pct", "pct", "money"], double=[3])
    steps = ([("Net pay", b["net"], "total")] + [(k.title(), -b["totals"][k], "delta") for k in ("needs", "wants")]
             + [("Savings", -b["totals"]["savings"], "part"), ("Left over", b["left"], "total")])   # saving is not a loss: steel, not red
    return {"kind": "budget", "title": "Monthly budget", "subtitle": f"Net pay {F.money(b['net'])} {cur} a month; the 50/30/20 rule as the yardstick.",
            "hero": {"value": f"{F.money(b['left'])} {cur}", "label": "left over each month",
                     "line": f"Needs {F.pct(b['share']['needs'], 0)}, wants {F.pct(b['share']['wants'], 0)}, savings {F.pct(b['share']['savings'], 0)} "
                             f"of net pay; the emergency fund covers {b['emergency_months']:.1f} months of needs." if b["emergency_months"] else ""},
            "kpis": [("Needs", F.money(b["totals"]["needs"])), ("Wants", F.money(b["totals"]["wants"])), ("Savings", F.money(b["totals"]["savings"])),
                     ("Cash added per month", F.money(b["left"])), ("Cash in 12 months", F.money(b["path"][-1])),
                     ("Cash runs out", f"month {b['gap_month']}" if b["gap_month"] is not None else "not within 12 months")],
            "tables": [split, lines],
            "charts": [{"kind": "waterfall", "title": f"Net pay to left over ({cur})", "steps": steps},
                       {"kind": "bars", "title": f"Emergency cash over 12 months ({cur})", "labels": [f"M{m}" for m in range(13)],
                        "series": [("Fund", b["path"], "total")]}],
            "notes": ["Savings lines leave the account (an ETF plan, extra repayments). The left-over, plus or minus, moves the emergency "
                      "cash in the 12-month path; a negative left-over spends it down."], "sources": ["the household's own numbers"]}


def three_report(f, a, m):
    h, p = m["history"], m["projection"]
    allr = h + p
    yrs = [r["year"] for r in allr]
    g = lambda k, sign=1: [sign * r[k] if r.get(k) is not None else None for r in allr]
    is_ = T("Income statement ($m)", ["Line"] + yrs, [["Revenue"] + g("revenue"), ["Cost of revenue"] + g("cogs", -1), ["Operating costs"] + g("opex", -1),
                                                    ["Operating income"] + g("ebit"), ["Interest"] + g("interest", -1), ["Tax"] + g("tax", -1),
                                                    ["Net income"] + g("net_income")], ["text"] + ["money"] * len(yrs), totals=[3, 6])
    bs = T("Balance sheet ($m)", ["Line"] + yrs, [["Cash and investments"] + g("cash"), ["Receivables"] + g("receivables"), ["Inventory"] + g("inventory"),
                                                ["PP&E"] + g("ppe"), ["Other assets"] + g("other_assets"), ["Total assets"] + g("assets"),
                                                ["Payables"] + g("payables"), ["Debt"] + g("debt"), ["Other liabilities"] + g("other_liabilities"),
                                                ["Equity (incl. minority)"] + g("equity"), ["Liabilities and equity"] + g("liab_equity"),
                                                ["Check (must be 0)"] + [r.get("check", r["assets"] - r["liab_equity"]) for r in allr]],
           ["text"] + ["money"] * len(yrs), totals=[5, 10], double=[10])
    cf = T("Cash flow, projected years ($m)", ["Line"] + [r["year"] for r in p],
           [["Net income"] + [r["net_income"] for r in p], ["D&A"] + [r["da"] for r in p], ["Operating cash flow"] + [r["cfo"] for r in p],
            ["Capex"] + [-r["capex"] for r in p], ["Dividends and buybacks"] + [-r["dividends"] for r in p],
            ["Change in cash"] + [r["cfo"] - r["capex"] - r["dividends"] for r in p]], ["text"] + ["money"] * len(p), totals=[2, 5])
    inputs = T("Inputs and where they come from", ["Input", "Value", "Source"], [[k, val, s] for k, val, s in sources_of(a)], ["text", "auto", "text"])
    worst = max(abs(r["check"]) for r in allr)
    return {"kind": "three", "title": f"{f['name']} ({f['ticker']}) three-statement model",
            "subtitle": f"Three filed years and {len(p)} projected years; cash is the plug from the cash-flow statement. $ millions.",
            "hero": {"value": F.money(p[-1]["net_income"]), "label": f"net income in {p[-1]['year']} ($m)",
                     "line": f"Revenue {F.money(p[-1]['revenue'])}, cash {F.money(p[-1]['cash'])}; the balance sheet balances in every year (largest gap {worst:.6f})."},
            "kpis": [("Revenue Y1", F.money(p[0]["revenue"])), ("Net income Y1", F.money(p[0]["net_income"])), ("Cash Y5", F.money(p[-1]["cash"])),
                     ("Equity Y5", F.money(p[-1]["equity"])), ("Balance check", "0 every year" if worst < 0.01 else f"off by {worst:.2f}")],
            "tables": [is_, bs, cf, inputs],
            "charts": [{"kind": "bars", "title": "Revenue and net income ($m)", "labels": yrs,
                        "series": [("Revenue", g("revenue"), "total"), ("Net income", g("net_income"), "part")]}],
            "notes": ["'Other' lines carry the filed totals the model does not split; they are held flat in the projection. Filed years "
                      "check filed assets against filed liabilities + filed equity (incl. minority interest).",
                      "Interest is charged on the opening debt; debt is held flat.",
                      "Dividends and buybacks keep their last-year share of net income (the payout input); a loss pays nothing out."],
            "sources": [f["source"]]}
