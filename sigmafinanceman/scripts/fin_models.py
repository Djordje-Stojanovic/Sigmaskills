"""The finance maths of sigmafinanceman as pure functions: plain dicts in, plain dicts out, no network, no files.

Money is in millions of the filing currency, shares in millions, per-share values in currency units. Every model returns
`assumptions` (name -> {value, source}), the computed rows, and a `report` (hero line, tables, charts) that the writers draw.
The xlsx writer rebuilds the same maths as live formulas; `selftest` checks both agree.
"""
import math
import statistics

M = 1e6
LABELS = {  # one plain name per input and per filed line, used in every output
    "revenue_base": "Revenue, last fiscal year", "growth_y1": "Revenue growth, year 1", "ebit_margin": "EBIT margin", "tax_rate": "Tax rate",
    "da_pct": "D&A % of revenue", "capex_pct_y0": "Capex % of revenue, today", "nwc_pct": "Working capital % of revenue",
    "rf": "Risk-free rate (10-year)", "beta": "Beta", "erp": "Equity risk premium", "kd": "Pre-tax cost of debt", "debt": "Debt",
    "cash": "Cash and investments", "shares": "Diluted shares (m)", "price": "Share price", "terminal_g": "Terminal growth",
    "ppe_pct": "PP&E % of revenue", "investments": "Equity-method stakes (book)", "preferred": "Preferred stock",
    "years_to_bs": "Years, fiscal year-end to balance sheet", "years_to_price": "Years, balance sheet to price date",
    "years": "Projection years", "ebitda_ltm": "EBITDA, normalized", "premium": "Takeover premium", "entry_multiple": "Entry EV / EBITDA",
    "leverage": "Debt / EBITDA at entry", "rate": "Debt interest rate", "fees": "Deal fees % of EV", "sweep": "Cash sweep",
    "exit_multiple": "Exit EV / EBITDA", "cogs_pct": "Cost of revenue %", "opex_pct": "Operating costs %", "interest_rate": "Interest rate on debt",
    "dso": "Receivable days", "dio": "Inventory days", "dpo": "Payable days", "payout": "Payout incl. buybacks",
    "revenue": "Revenue", "cogs": "Cost of revenue", "gross_profit": "Gross profit", "rnd": "R&D", "sga": "SG&A", "ebit": "Operating income (EBIT)",
    "interest": "Interest expense", "pretax": "Pre-tax income", "tax": "Income tax", "net_income": "Net income", "eps": "Diluted EPS",
    "shares_diluted": "Diluted shares (m)", "da": "D&A", "sbc": "Stock-based pay", "cfo": "Operating cash flow", "capex": "Capex",
    "dividends": "Dividends paid", "buybacks": "Share buybacks", "st_investments": "Short-term investments", "receivables": "Receivables",
    "inventory": "Inventory", "current_assets": "Current assets", "ppe": "PP&E (net)", "assets": "Total assets", "payables": "Payables",
    "current_liabilities": "Current liabilities", "debt_current": "Debt due within a year", "debt_noncurrent": "Long-term debt",
    "short_borrowings": "Commercial paper", "liabilities": "Total liabilities", "equity": "Shareholders' equity",
    "retained_earnings": "Retained earnings", "minority": "Minority interest", "shares_basic": "Basic shares (m)",
    "commercial_paper": "Commercial paper", "debt_current_all": "Debt due within a year (total)", "debt_total": "Long-term debt incl. current",
    "cash_st": "Cash and short-term investments", "cash_restricted_incl": "Cash incl. restricted", "restricted_cash": "Restricted cash",
    "liab_equity": "Liabilities and equity", "equity_total": "Equity incl. minority", "cash_all": "Cash and short-term investments"}
FILED = {**LABELS, "cash": "Cash and equivalents", "short_borrowings": "Short-term borrowings", "debt": "Total debt (read from the lines above)"}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def div(a, b):
    return a / b if (a is not None and b not in (None, 0)) else None


def cagr(first, last, years):
    if not first or not last or first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1 / years) - 1


def money(x, unit="m"):
    if x is None:
        return "n/a"
    s = f"{abs(x):,.0f}"
    return f"({s})" if x < 0 else s


def pct(x, nd=1):
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def per_share(x, cur="$"):
    if x is None:
        return "n/a"
    return f"({cur}{abs(x):,.2f})" if x < 0 else f"{cur}{x:,.2f}"


def mult(x):
    return "n/a" if x is None else f"{x:.1f}x"


# ---------- the facts of one company, in millions ----------

def view(f):
    """Short accessors over the normalized facts: hist(concept) -> list over fiscal years (millions), last(concept)."""
    ends = f["fiscal_year_ends"]
    A = f["annual"]
    scale = lambda c, v: v if v is None or c == "eps" else v / M

    def hist(c):
        return [scale(c, A.get(c, {}).get(e)) for e in ends]

    def last(c, default=None):
        v = hist(c)[-1]
        return default if v is None else v
    return ends, hist, last


def balance(f, date=None):
    """(date, get): get(concept) -> millions on one balance-sheet date, default the newest filed (a 10-Q when newer than the 10-K)."""
    date = date or f.get("bs_date") or f["fiscal_year_ends"][-1]

    def get(c):
        v = f["annual"].get(c, {}).get(date)
        if v is None:
            v = (f.get("quarters", {}).get(c) or {}).get(date)
        return None if v is None else v / M
    return date, get


def debt_and_cash(last):
    """Last fiscal year's total debt and cash (0 when not filed), as fin_assets reads them."""
    return last("debt", 0) or 0, last("cash_all", 0) or 0


def check_debt(f, debt, o=()):
    """Stop when the debt read looks incomplete: interest above 12 % of it, or interest with no debt at all."""
    i = view(f)[2]("interest")
    if "debt" not in o and i and i > 0 and (not debt or i / debt > 0.12):
        raise SystemExit(f"{f['ticker']}: debt looks incomplete (interest {i:,.0f}m a year on {debt or 0:,.0f}m of debt read from "
                         f"us-gaap {f['tags'].get('debt') or 'none'}). Read total debt on the balance sheet of the latest 10-K or 10-Q "
                         "and pass --set debt=<millions>")


def shares_now(f):
    """(millions, source): the newest cover-page count x the diluted / basic ratio of the last fiscal year, so a buyback after the
    year-end counts; the weighted diluted count when the cover is older than the year-end. (None, why) when neither is filed."""
    _, _, last = view(f)
    d, b = last("shares_diluted"), last("shares_basic")
    cover, when = (f.get("shares_cover") or 0) / M, f.get("shares_cover_date") or ""
    if cover and when >= f["fiscal_year_ends"][-1]:
        ratio = max(1.0, d / b) if d and b else 1.0
        return cover * ratio, f"SEC cover page: {cover:,.1f}m shares outstanding on {when}, x diluted / basic {ratio:.4f} (last fiscal year)"
    if d:
        return d, src(f, "shares_diluted") + " (weighted, millions; no cover-page count after the year-end)"
    return None, "unavailable: no share count filed"


def overrides(out, o, model):
    """Apply --set values; a name the model does not have stops the run instead of being ignored."""
    bad = [k for k in o if k not in out]
    if bad:
        raise SystemExit(f"{model} has no input named {', '.join(bad)}. Its inputs: {', '.join(out)}")
    for k, val in o.items():
        out[k] = {"value": val, "source": "set by the user"}
    return out


def _days(a, b):
    import datetime as dt
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def src(f, concept):
    return f"SEC 10-K company facts, us-gaap:{f['tags'].get(concept) or 'n/a'}, FY end {f['fiscal_year_ends'][-1]}"


# ---------- DCF ----------

def dcf_inputs(f, o=None):
    """Default DCF assumptions read from the filings and the market; `o` overrides any of them by name."""
    o = o or {}
    ends, hist, last = view(f)
    rev = hist("revenue")
    n_hist = min(3, len(rev) - 1)
    g0 = cagr(rev[-1 - n_hist], rev[-1], n_hist) if n_hist > 0 else 0.05
    margins = [div(e, r) for e, r in zip(hist("ebit")[-3:], rev[-3:]) if div(e, r) is not None]
    date, get = balance(f)
    debt, cash = get("debt"), get("cash_all")
    if debt is None and not last("interest"):
        debt = 0.0                                   # no debt line and no interest: a company without debt
    check_debt(f, debt, o)
    for k, val in (("cash", cash), ("debt", debt)):
        if val is None and k not in o:
            raise SystemExit(f"{f['ticker']}: {k} is not in the SEC facts for {date}: read it on the balance sheet and pass --set {k}=<millions>")
    shares, shares_src = shares_now(f)
    if not shares and "shares" not in o:
        raise SystemExit(f"{f['ticker']}: no share count filed: pass --set shares=<millions, diluted>")
    mkt = f.get("market", {})
    if mkt.get("currency", "USD") != "USD" and "price" not in o:
        raise SystemExit(f"{f['ticker']}: the price is quoted in {mkt['currency']} and the filings are in USD. Convert it and pass "
                         "--set price=<USD per ordinary share> (an ADR: divide by the ordinary shares each ADR holds)")
    tax_rate = div(last("tax"), last("pretax"))
    da, capex, ppe = last("da"), last("capex"), last("ppe")
    parts = {"receivables": last("receivables"), "inventory": last("inventory"), "payables": last("payables")}
    nwc = (parts["receivables"] or 0) + (parts["inventory"] or 0) - (parts["payables"] or 0)
    missing = [k for k, x in parts.items() if x is None]
    rf = f.get("rf", 0.042)
    beta = mkt.get("beta")
    kd_raw = div(last("interest"), debt)
    fy_end, price_day = ends[-1], mkt.get("price_time") or date
    na = lambda x, dflt, text: (x, text) if x is not None else (dflt, f"unavailable (not filed); default {dflt:g} used")
    a = {
        "revenue_base": (rev[-1], src(f, "revenue")),
        "growth_y1": (clamp(g0 if g0 is not None else 0.05, 0.0, 0.25), f"{n_hist}-year revenue CAGR, held 0-25 %"),
        "ebit_margin": (statistics.mean(margins) if margins else 0.15, "average EBIT margin, last 3 fiscal years"),
        "tax_rate": (clamp(tax_rate if tax_rate is not None else 0.21, 0.10, 0.30), "effective tax rate, last fiscal year, held 10-30 %"),
        "da_pct": na(div(da, rev[-1]), 0.03, src(f, "da") + " / revenue (the largest D&A line filed)"),
        "capex_pct_y0": na(div(capex, rev[-1]), 0.04, src(f, "capex") + " / revenue; fades to the steady-state share by the last year"),
        "ppe_pct": na(div(ppe, rev[-1]), 0.0, src(f, "ppe") + " / revenue: the capital each extra dollar of sales needs"),
        "nwc_pct": (div(nwc, rev[-1]) or 0.0, f"(receivables + inventory - trade payables) / revenue, last fiscal year"
                    + (f"; unavailable, left out: {', '.join(missing)}" if missing else "")),
        "rf": (rf, f.get("rf_source_label") or f"US 10-year Treasury {f.get('rf_date', '')} ({(f.get('rf_source') or 'FRED DGS10').split('?')[0]})"),
        "beta": (clamp(beta, 0.6, 2.0), f"5-year monthly beta vs S&P 500 ({mkt.get('beta_months', '?')} matched months, Yahoo chart), held 0.6-2.0")
        if beta is not None else (1.0, "unavailable (under 24 matched months); 1.0 used"),
        "erp": (0.05, "equity risk premium, market standard 5 %"),
        "kd": (clamp(kd_raw, rf, rf + 0.04) if kd_raw else rf + 0.01, "interest expense / debt, held between rf and rf + 4 %"),
        "debt": (debt, f"total debt on the balance sheet of {date}: long-term + current + short-term borrowings, each balance once "
                       f"(us-gaap {f['tags'].get('debt') or 'none filed'})"),
        "cash": (cash, f"cash + short-term investments on the balance sheet of {date} (us-gaap {f['tags'].get('cash_all')})"),
        "minority": (get("minority") or 0, (f"us-gaap:MinorityInterest on {date}" if get("minority") is not None else "no us-gaap:MinorityInterest filed, so 0")
                     + "; the part of subsidiaries that outside owners hold"),
        "preferred": (get("preferred") or 0, f"us-gaap:PreferredStockValue on {date} (book value)" if get("preferred") else "no preferred stock filed, so 0"),
        "investments": (get("investments") or 0, f"us-gaap:EquityMethodInvestments on {date} at book value; their profit is not in EBIT. "
                        "Listed stakes: use the market value from the 10-K note" if get("investments") else "no equity-method stakes filed, so 0"),
        "shares": (shares, shares_src),
        "price": (mkt.get("price") or 0, f"Yahoo chart price {mkt.get('price_time', '')}"),
        "terminal_g": (min(0.025, rf), "terminal growth 2.5 %, never above the risk-free rate"),
        "years": (5, "projection years"),
        "years_to_bs": (max(0, _days(fy_end, date)) / 365, f"fiscal year-end {fy_end} to the balance sheet of {date}: the value rolls forward"),
        "years_to_price": (max(0, _days(date, price_day)) / 365, f"balance sheet {date} to the price date {price_day}: equity grows at the cost of equity"),
    }
    out = {k: {"value": v, "source": s} for k, (v, s) in a.items()}
    return overrides(out, o, "dcf")


def wacc_of(a):
    v = lambda k: a[k]["value"]
    ke = v("rf") + v("beta") * v("erp")
    e = v("price") * v("shares")
    d = v("debt")
    w = (e * ke + d * v("kd") * (1 - v("tax_rate"))) / (e + d) if e + d else ke
    return w, ke, e


def capex_steady(a):
    """Capex share of revenue in the steady state: replace what wears out (D&A) and add the plant that terminal growth needs."""
    v = lambda k: a[k]["value"]
    return v("da_pct") + v("ppe_pct") * v("terminal_g") / (1 + v("terminal_g"))


def terminal_fcf(rev_n, nopat_margin, g, capital_pct):
    """Cash flow of the first year after the forecast: next year's NOPAT less the capital that growth g needs
    (g x last revenue x (PP&E + working capital) / revenue). Same as NOPAT x (1 - g / return on new capital)."""
    return rev_n * (1 + g) * nopat_margin - g * rev_n * capital_pct


def dcf(a, wacc=None, g=None):
    """The DCF rows and the valuation. wacc and g override the computed ones (the sensitivity grid uses them).
    value_per_share is None when WACC is not above g: the growth formula has no finite answer."""
    v = lambda k: a[k]["value"]
    n = int(v("years"))
    w0, ke, mcap = wacc_of(a)
    w = w0 if wacc is None else wacc
    g = v("terminal_g") if g is None else g
    rows = []
    prev = v("revenue_base")
    g1 = v("growth_y1")
    steady = capex_steady(a)
    for i in range(1, n + 1):
        growth = g1 - (g1 - v("terminal_g")) * (i - 1) / n
        rev = prev * (1 + growth)
        capex_pct = v("capex_pct_y0") + (steady - v("capex_pct_y0")) * i / n
        ebit = rev * v("ebit_margin")
        nopat = ebit * (1 - v("tax_rate"))
        da = rev * v("da_pct")
        capex = rev * capex_pct
        dnwc = v("nwc_pct") * (rev - prev)
        fcf = nopat + da - capex - dnwc
        period = i - 0.5
        pv = fcf / (1 + w) ** period
        rows.append({"year": i, "growth": growth, "revenue": rev, "ebit": ebit, "nopat": nopat, "da": da, "capex_pct": capex_pct,
                     "capex": capex, "dnwc": dnwc, "fcf": fcf, "period": period, "pv": pv})
        prev = rev
    pv_fcf = sum(r["pv"] for r in rows)
    out = {"rows": rows, "wacc": w, "ke": ke, "mcap": mcap, "g": g, "pv_fcf": pv_fcf}
    if w <= g:
        return {**out, "tv": None, "pv_tv": None, "ev_fye": None, "ev": None, "equity_bs": None, "equity": None, "value_per_share": None,
                "upside": None, "tv_share": None, "fcf_terminal": None}
    fcf_t = terminal_fcf(rows[-1]["revenue"], v("ebit_margin") * (1 - v("tax_rate")), g, v("ppe_pct") + v("nwc_pct"))
    tv = fcf_t / (w - g)
    pv_tv = tv / (1 + w) ** (n - 0.5)
    ev_fye = pv_fcf + pv_tv
    s = v("years_to_bs")
    ev = ev_fye * (1 + w) ** s - s * rows[0]["fcf"]   # at the balance-sheet date; the cash earned since the year-end is in that sheet
    equity_bs = ev - v("debt") + v("cash") - v("minority") - v("preferred") + v("investments")
    equity = equity_bs * (1 + ke) ** v("years_to_price")
    price = equity / v("shares") if v("shares") else None
    return {**out, "fcf_terminal": fcf_t, "tv": tv, "pv_tv": pv_tv, "ev_fye": ev_fye, "ev": ev, "equity_bs": equity_bs, "equity": equity,
            "value_per_share": price, "upside": (price / v("price") - 1) if price is not None and v("price") else None,
            "tv_share": pv_tv / ev_fye if ev_fye else None}


def axis(center, step):
    return [center + step * k for k in (-2, -1, 0, 1, 2)]


def dcf_grid(a):
    base = dcf(a)
    ws, gs = axis(base["wacc"], 0.005), axis(base["g"], 0.005)
    return ws, gs, [[dcf(a, w, g)["value_per_share"] for g in gs] for w in ws]


def implied(a, key="growth_y1", lo=-0.5, hi=1.0):
    """Reverse DCF: the value of one input (`key`) at which the DCF value per share equals the market price.
    None when no value in [lo, hi] reaches the price."""
    price = a["price"]["value"]
    val = lambda x: dcf({**a, key: {"value": x, "source": ""}})["value_per_share"]
    return _solve(lambda x: None if val(x) is None else val(x) - price, lo, hi) if price else None


def implied_rate(a):
    """The discount rate (WACC) at which the DCF value equals the price, other inputs held. More robust than implied growth,
    which a forced fade to terminal growth can push to odd values. None when no rate up to 50 % reaches the price."""
    price = a["price"]["value"]
    val = lambda w: dcf(a, wacc=w)["value_per_share"]
    return _solve(lambda w: val(w) - price, a["terminal_g"]["value"] + 1e-4, 0.5) if price else None


def _solve(gap, lo, hi):
    """Bisection on [lo, hi]; None when gap has the same sign (or no value) at both ends."""
    glo, ghi = gap(lo), gap(hi)
    if glo is None or ghi is None or glo * ghi > 0:
        return None
    for _ in range(60):   # bisection; the value rises with growth and with margin
        mid = (lo + hi) / 2
        if (gap(mid) > 0) == (ghi > 0):
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


SCENARIO_STEP = {"growth_y1": 0.05, "ebit_margin": 0.03}   # bear = base minus a step, bull = base plus a step


def scenarios(a):
    """Bear, base and bull: year-1 growth and EBIT margin each moved one SCENARIO_STEP; the rest of the model stays."""
    out = []
    for name, sign in (("Bear", -1), ("Base", 0), ("Bull", 1)):
        b = {**a, **{k: {"value": a[k]["value"] + sign * d, "source": f"{name.lower()} case"} for k, d in SCENARIO_STEP.items()}}
        out.append({"name": name, "growth_y1": b["growth_y1"]["value"], "ebit_margin": b["ebit_margin"]["value"],
                    "value_per_share": dcf(b)["value_per_share"]})
    return out


# ---------- LBO ----------

LBO_FROM_DCF = ("revenue_base", "growth_y1", "ebit_margin", "tax_rate", "da_pct", "capex_pct_y0", "ppe_pct", "nwc_pct", "terminal_g",
                "years", "price", "shares", "debt", "cash", "minority", "rf")


def lbo_inputs(f, o=None):
    """Price, shares, premium, the bridge and EBITDA are resolved (with --set) before the entry EV; the entry multiple follows from
    them unless set, and the exit multiple defaults to the resolved entry multiple."""
    o = dict(o or {})
    a = dcf_inputs(f, {k: v for k, v in o.items() if k in LBO_FROM_DCF})
    ends, hist, last = view(f)
    v = lambda k: a[k]["value"]
    # normalized: last revenue x the 3-year average EBIT margin + D&A, so one impairment year does not set the deal price
    ebitda = o.get("ebitda_ltm", v("revenue_base") * (v("ebit_margin") + v("da_pct")))
    premium = o.get("premium", 0.25)
    ev = v("price") * (1 + premium) * v("shares") + v("debt") - v("cash") + v("minority")
    if ebitda <= 0 and "entry_multiple" not in o:
        raise SystemExit(f"{f['ticker']}: normalized EBITDA is {ebitda:,.0f}m: an LBO needs positive EBITDA (--set ebitda_ltm=)")
    entry = o.get("entry_multiple", ev / ebitda if ebitda > 0 else None)
    x = {
        "ebitda_ltm": (ebitda, "last revenue x (3-year average EBIT margin + D&A share) (normalized)"),
        "premium": (premium, "take-private premium over the share price"),
        "entry_multiple": (entry, "entry EV / EBITDA: price x (1 + premium) x shares + debt - cash + minority interest"),
        "leverage": (5.0, "senior debt / EBITDA at entry, market standard 4-6x"),
        "rate": (a["rf"]["value"] + 0.035, "debt rate: risk-free + 3.5 %"),
        "fees": (0.02, "deal fees, % of entry EV"),
        "sweep": (1.0, "share of free cash flow that repays debt"),
        "exit_multiple": (None, "exit EV / EBITDA; default = the entry multiple"),
    }
    out = {k: {"value": val, "source": s} for k, (val, s) in x.items()}
    out["exit_multiple"]["value"] = o.get("exit_multiple", entry)
    for k in LBO_FROM_DCF:
        out[k] = a[k]
    return overrides(out, {k: val for k, val in o.items() if k not in LBO_FROM_DCF}, "lbo")


def lbo(a, entry=None, exit_=None):
    v = lambda k: a[k]["value"]
    n = int(v("years"))
    entry = v("entry_multiple") if entry is None else entry
    exit_ = v("exit_multiple") if exit_ is None else exit_
    ebitda0 = v("ebitda_ltm")
    ev0 = entry * ebitda0
    debt0 = v("leverage") * ebitda0
    minority = v("minority")
    equity0 = ev0 * (1 + v("fees")) - debt0 - minority   # the outside owners keep their stake: the sponsor does not buy it
    rows, prev, debt, cash = [], v("revenue_base"), debt0, 0.0
    g1 = v("growth_y1")
    steady = capex_steady(a)
    for i in range(1, n + 1):
        growth = g1 - (g1 - v("terminal_g")) * (i - 1) / n
        rev = prev * (1 + growth)
        ebit = rev * v("ebit_margin")
        da = rev * v("da_pct")
        ebitda = ebit + da
        capex = rev * (v("capex_pct_y0") + (steady - v("capex_pct_y0")) * i / n)
        dnwc = v("nwc_pct") * (rev - prev)
        interest = debt * v("rate")
        tax = max(0.0, ebit - interest) * v("tax_rate")
        fcf = ebitda - capex - dnwc - interest - tax
        pay = min(debt, max(0.0, fcf) * v("sweep"))
        draw = max(0.0, -(cash + fcf - pay))   # a shortfall is drawn on a revolver at the debt rate; cash never goes below zero
        debt += draw - pay
        cash += fcf - pay + draw
        rows.append({"year": i, "revenue": rev, "ebitda": ebitda, "capex": capex, "dnwc": dnwc, "interest": interest, "tax": tax,
                     "fcf": fcf, "paydown": pay, "draw": draw, "debt": debt, "cash": cash})
        prev = rev
    exit_ev = exit_ * rows[-1]["ebitda"]
    exit_equity = max(0.0, exit_ev - debt + cash - minority)   # limited liability: the sponsor loses at most its equity
    moic = exit_equity / equity0 if equity0 > 0 else None
    irr = moic ** (1 / n) - 1 if moic is not None and moic > 0 else (-1.0 if moic == 0 else None)
    return {"rows": rows, "ev0": ev0, "debt0": debt0, "equity0": equity0, "exit_ev": exit_ev, "exit_equity": exit_equity,
            "moic": moic, "irr": irr, "entry": entry, "exit": exit_}


def lbo_grid(a):
    e, x = a["entry_multiple"]["value"], a["exit_multiple"]["value"]
    es, xs = axis(e, 1.0), axis(x, 1.0)
    return es, xs, [[lbo(a, en, ex)["irr"] for ex in xs] for en in es]


# ---------- comps ----------

def comp_row(f):
    """One company's trading row from its facts (LTM where the 10-Qs allow it)."""
    L = {k: (v / M if k != "eps" else v) for k, v in f["ltm"].items() if not k.startswith("_") and v is not None}
    _, hist, last = view(f)
    _, get = balance(f)
    debt, cash = get("debt"), get("cash_all") or 0
    if debt is None and not last("interest"):
        debt = 0.0
    check_debt(f, debt)
    shares = shares_now(f)[0]
    price = f.get("market", {}).get("price")
    if f.get("market", {}).get("currency", "USD") != "USD":
        raise SystemExit(f"{f['ticker']}: quoted in {f['market']['currency']}, filed in USD: comps need a USD price per ordinary share")
    mcap = price * shares if price and shares else None
    minority = get("minority") or 0   # outside owners of subsidiaries: their claim is in EV, as consolidated EBITDA counts all of it
    preferred = get("preferred") or 0
    investments = get("investments") or 0   # stakes whose profit sits outside EBITDA: out of EV
    ev = mcap + debt - cash + minority + preferred - investments if mcap is not None else None
    ebitda = (L.get("ebit") or 0) + (L.get("da") or 0) if L.get("ebit") is not None else None
    rev = hist("revenue")
    return {"ticker": f["ticker"], "name": f["name"], "price": price, "shares": shares, "mcap": mcap, "debt": debt, "cash": cash,
            "minority": minority, "preferred": preferred, "investments": investments, "ev": ev,
            "revenue": L.get("revenue"), "ebitda": ebitda, "ebit": L.get("ebit"), "net_income": L.get("net_income"),
            "ev_rev": div(ev, L.get("revenue")), "ev_ebitda": div(ev, ebitda), "ev_ebit": div(ev, L.get("ebit")),
            "pe": div(mcap, L.get("net_income")), "growth": div(rev[-1], rev[-2]) - 1 if len(rev) > 1 and rev[-2] else None,
            "ebit_margin": div(L.get("ebit"), L.get("revenue")), "ltm_asof": f["ltm"].get("_asof"),
            "low_52w": f.get("market", {}).get("low_52w"), "high_52w": f.get("market", {}).get("high_52w")}


def quartiles(xs):
    xs = sorted(x for x in xs if x is not None and x > 0)
    if not xs:
        return None
    q = lambda p: xs[0] if len(xs) == 1 else _q(xs, p)
    return {"max": xs[-1], "q3": q(0.75), "median": q(0.5), "q1": q(0.25), "min": xs[0]}


def _q(xs, p):   # Excel QUARTILE.INC
    k = (len(xs) - 1) * p
    lo = math.floor(k)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (k - lo)


def comps(target, peers):
    t = comp_row(target)
    rows = [comp_row(p) for p in peers]
    stats = {m: quartiles([r[m] for r in rows]) for m in ("ev_rev", "ev_ebitda", "ev_ebit", "pe")}
    implied = {}
    for m, base in (("ev_ebitda", t["ebitda"]), ("ev_rev", t["revenue"])):
        s = stats[m]
        if s and base and base > 0:   # a multiple of a loss is not a value
            implied[m] = {k: (s[k] * base - t["debt"] + t["cash"] - t["minority"] - t["preferred"] + t["investments"]) / t["shares"]
                          for k in ("q1", "median", "q3")}
    if stats["pe"] and t["net_income"] and t["net_income"] > 0:
        implied["pe"] = {k: stats["pe"][k] * t["net_income"] / t["shares"] for k in ("q1", "median", "q3")}
    return {"target": t, "peers": rows, "stats": stats, "implied": implied}


# ---------- ratios, statement analysis, red flags ----------

def ratios(f):
    ends, hist, last = view(f)
    H = {c: hist(c) for c in f["annual"]}
    out = []
    for i, e in enumerate(ends):
        g = lambda c: H[c][i]
        debt = g("debt")
        ebitda = (g("ebit") or 0) + (g("da") or 0) if g("ebit") is not None else None
        fcf = (g("cfo") - g("capex")) if g("cfo") is not None and g("capex") is not None else None
        nopat = g("ebit") * (1 - clamp(div(g("tax"), g("pretax")) or 0.21, 0, 0.4)) if g("ebit") is not None else None
        invested = g("equity") + debt - (g("cash_all") or 0) if g("equity") is not None and debt is not None else None
        prev = lambda c: H[c][i - 1] if i > 0 else None
        out.append({"end": e,
                    "gross_margin": div(g("gross_profit"), g("revenue")), "ebit_margin": div(g("ebit"), g("revenue")),
                    "net_margin": div(g("net_income"), g("revenue")), "roe": div(g("net_income"), g("equity")),
                    "roa": div(g("net_income"), g("assets")), "roic": div(nopat, invested if invested and invested > 0 else None),
                    "current": div(g("current_assets"), g("current_liabilities")),
                    "quick": div((g("current_assets") or 0) - (g("inventory") or 0), g("current_liabilities")),
                    "debt_equity": div(debt, g("equity")), "debt_ebitda": div(debt, ebitda) if ebitda and ebitda > 0 else None,
                    "interest_cover": div(g("ebit"), g("interest")), "asset_turnover": div(g("revenue"), g("assets")),
                    "dso": div((g("receivables") or 0) * 365, g("revenue")),
                    "dio": div((g("inventory") or 0) * 365, g("cogs")) if g("inventory") else None,
                    "dpo": div((g("payables") or 0) * 365, g("cogs")),
                    "fcf": fcf, "fcf_margin": div(fcf, g("revenue")), "cash_conversion": div(fcf, g("net_income")),
                    "eps": g("eps"), "payout": div(g("dividends"), g("net_income")),
                    "revenue_growth": div(g("revenue"), prev("revenue")) - 1 if prev("revenue") else None,
                    "sbc_pct": div(g("sbc"), g("revenue"))})
    return out


def red_flags(f):
    """Forensic checks in the spirit of a red-flag auditor: each flag says what it measured and why it matters."""
    ends, hist, last = view(f)
    H = {c: hist(c) for c in f["annual"]}
    flags = []
    if len(ends) < 2:
        return flags
    i, j = -1, -2
    gr = lambda c: H[c][i] / H[c][j] - 1 if H[c][i] is not None and H[c][j] else None
    known = lambda *xs: all(x is not None for x in xs)   # a flag with a missing input is unavailable (None), never clear
    rg, arg, ig = gr("revenue"), gr("receivables"), gr("inventory")
    flags.append(("Receivables grow faster than revenue", arg > rg + 0.10 if known(arg, rg) else None,
                  f"receivables {pct(arg)} vs revenue {pct(rg)}", "sales booked before cash arrives"))
    material = (H["inventory"][i] or 0) > 0.02 * (H["revenue"][i] or 0)   # a tiny inventory line is noise, not a flag
    flags.append(("Inventory grows faster than revenue", (ig > rg + 0.10 if known(ig, rg) else None) if material else False,
                  f"inventory {pct(ig)} vs revenue {pct(rg)}", "unsold goods pile up"))
    ni, cfo, assets = H["net_income"][i], H["cfo"][i], H["assets"][i]
    accr = div(ni - cfo, assets) if known(ni, cfo) else None
    flags.append(("Profit not backed by cash (Sloan accruals)", accr > 0.10 if accr is not None else None,
                  f"(net income - CFO) / assets = {pct(accr)}", "earnings ahead of cash"))
    gm = [div(g, r) for g, r in zip(H["gross_profit"], H["revenue"])]
    drop = gm[j] - gm[i] if gm[i] is not None and gm[j] is not None else None
    flags.append(("Gross margin fell 3+ points", drop > 0.03 if drop is not None else None, f"{pct(gm[j])} -> {pct(gm[i])}", "pricing power or cost pressure"))
    sbc = div(H["sbc"][i], H["revenue"][i])
    flags.append(("Stock pay above 10 % of revenue", sbc > 0.10 if sbc is not None else None, f"SBC / revenue = {pct(sbc)}", "real cost hidden from adjusted profit"))
    dg = H["debt"][i] / H["debt"][j] - 1 if H["debt"][i] is not None and H["debt"][j] else None
    flags.append(("Debt up 25 %+ while revenue grows under 5 %", dg > 0.25 and rg < 0.05 if known(dg, rg) else None,
                  f"debt {pct(dg)}, revenue {pct(rg)}", "borrowing to stand still"))
    ccr = div(cfo, ni) if known(cfo, ni) else None
    flags.append(("Operating cash flow under 80 % of net income", (ni > 0 and ccr < 0.8) if ccr is not None else None,
                  f"CFO / net income = {mult(ccr) if ccr is not None else 'n/a'}", "earnings quality"))
    return [{"check": c, "flag": None if hit is None else bool(hit), "measure": m, "why": w} for c, hit, m, w in flags]


def altman_z(f):
    """Altman Z (public manufacturer form). Needs the market value of equity."""
    _, hist, last = view(f)
    ta = last("assets")
    mcap = (f.get("market", {}).get("price") or 0) * (shares_now(f)[0] or 0)
    parts = [div((last("current_assets", 0) or 0) - (last("current_liabilities", 0) or 0), ta), div(last("retained_earnings"), ta),
             div(last("ebit"), ta), div(mcap, last("liabilities")), div(last("revenue"), ta)]
    if None in parts:
        return None
    w = (1.2, 1.4, 3.3, 0.6, 1.0)
    return sum(a * b for a, b in zip(w, parts))


def piotroski(f):
    """Piotroski F-score, 0-9, with the nine signals named."""
    _, hist, last = view(f)
    H = {c: hist(c) for c in f["annual"]}
    if len(H["revenue"]) < 2:
        return None, []
    i, j = -1, -2
    roa = lambda k: div(H["net_income"][k], H["assets"][k])
    lev = lambda k: div(H["debt_noncurrent"][k], H["assets"][k])
    cur = lambda k: div(H["current_assets"][k], H["current_liabilities"][k])
    gm = lambda k: div(H["gross_profit"][k], H["revenue"][k])
    at = lambda k: div(H["revenue"][k], H["assets"][k])
    sh = lambda k: H["shares_diluted"][k]
    test = lambda x, y, op: None if x is None or y is None else op(x, y)   # a signal with a missing input is unavailable (None)
    gt, lt, le = (lambda x, y: x > y), (lambda x, y: x < y), (lambda x, y: x <= y)
    s = [("Positive net income", test(H["net_income"][i], 0, gt)),
         ("Positive operating cash flow", test(H["cfo"][i], 0, gt)),
         ("Return on assets up", test(roa(i), roa(j), gt)),
         ("Cash flow above net income", test(H["cfo"][i], H["net_income"][i], gt)),
         ("Long-term debt / assets down", test(lev(i), lev(j), lt)),
         ("Current ratio up", test(cur(i), cur(j), gt)),
         ("No new shares", test(sh(i), sh(j), le)),
         ("Gross margin up", test(gm(i), gm(j), gt)),
         ("Asset turnover up", test(at(i), at(j), gt))]
    return sum(1 for _, ok in s if ok), s


def scorecard(f, dcf_value=None):
    """A value-investing scorecard in the Buffett and Graham tradition: 10 pass/fail tests on the filed numbers."""
    R = ratios(f)
    _, hist, last = view(f)
    price = f.get("market", {}).get("price")
    shares = shares_now(f)[0]
    mcap = price * shares if price and shares else None
    rev, eps = hist("revenue"), hist("eps")
    fcfs = [r["fcf"] for r in R]
    owner = last("net_income") + (last("da") or 0) - last("capex") if last("net_income") is not None and last("capex") is not None else None
    debt = last("debt")
    ebitda = last("ebit") + (last("da") or 0) if last("ebit") is not None else None
    roes = [r["roe"] for r in R if r["roe"] is not None]
    rf = f.get("rf", 0.042)
    c = [("Return on equity 15 %+ (average)", statistics.mean(roes) if roes else None, lambda x: x >= 0.15, pct),
         ("Return on invested capital 12 %+", R[-1]["roic"], lambda x: x >= 0.12, pct),
         ("Gross margin 40 %+ (moat)", R[-1]["gross_margin"], lambda x: x >= 0.40, pct),
         ("Net margin 10 %+", R[-1]["net_margin"], lambda x: x >= 0.10, pct),
         ("Revenue CAGR 5 %+", cagr(rev[0], rev[-1], len(rev) - 1), lambda x: x >= 0.05, pct),
         ("EPS up in most years", sum(1 for a, b in zip(eps, eps[1:]) if a is not None and b is not None and b > a) / max(1, len(eps) - 1),
          lambda x: x >= 0.6, lambda x: f"{x * 100:.0f}% of years"),
         ("Debt / EBITDA 2.0x or less", div(debt, ebitda) if ebitda and ebitda > 0 else None, lambda x: x <= 2.0, mult),
         ("Free cash flow positive every year", min((x for x in fcfs if x is not None), default=None), lambda x: x > 0, money),
         ("Owner-earnings yield above the 10-year", div(owner, mcap), lambda x: x >= rf, pct),
         ("Price at least 25 % under DCF value", div(price, dcf_value) if dcf_value and dcf_value > 0 else None, lambda x: x <= 0.75,
          lambda x: f"price = {x * 100:.0f}% of value")]
    out = [{"test": n, "value": v, "shown": fmt(v) if v is not None else "n/a", "pass": bool(v is not None and test(v))} for n, v, test, fmt in c]
    return out


# ---------- earnings review ----------

def quarter_table(f, n=5):
    """The last n fiscal quarters, newest last. A quarter not filed alone is a year to date minus the one before it (six months
    minus Q1, nine minus six, the year minus nine). EPS is not additive, so a quarter without a filed EPS stays unavailable."""
    q = {c: dict(f["quarters"].get(c, {})) for c in ("revenue", "gross_profit", "ebit", "net_income", "eps", "cfo")}
    for c in q:
        if c == "eps":
            continue
        ytd = sorted((k.split("..")[0], k.split("..")[1], v) for k, v in f.get("ytd", {}).get(c, {}).items())
        for (s1, e1, v1), (s2, e2, v2) in zip(ytd, ytd[1:]):
            if s1 == s2 and 80 <= _days(e1, e2) <= 100 and e2 not in q[c]:
                q[c][e2] = v2 - v1
    for e in f["fiscal_year_ends"]:
        for c in q:
            if c == "eps":
                continue
            fy = f["annual"][c].get(e)
            if fy is None or e in q[c]:
                continue
            ytd9 = [v for k, v in f.get("ytd", {}).get(c, {}).items() if 260 <= _days(*k.split("..")) <= 290 and 80 <= _days(k.split("..")[1], e) <= 100]
            prior = sorted(k for k in q[c] if k < e and (_days(k, e) < 300))
            if ytd9:
                q[c][e] = fy - ytd9[0]
            elif len(prior) >= 3:
                q[c][e] = fy - sum(q[c][k] for k in prior[-3:])
    ends = sorted(q["revenue"])[-(n + 4):]
    rows = []
    for e in ends:
        r = {"end": e}
        for c in q:
            v = q[c].get(e)
            r[c] = v if v is None or c == "eps" else v / M
        rows.append(r)
    return rows[-n - 4:]


def earnings(f):
    rows = quarter_table(f, 5)
    if not rows:
        return None
    last = rows[-1]
    year_ago = next((r for r in rows if abs(_days(r["end"], last["end"]) - 365) < 20), None)
    prev = rows[-2] if len(rows) > 1 else None
    ch = lambda a, b, k: div(a.get(k), b.get(k)) - 1 if b and a.get(k) is not None and b.get(k) else None
    lines = []
    for k, label in (("revenue", "Revenue"), ("gross_profit", "Gross profit"), ("ebit", "Operating income"), ("net_income", "Net income"),
                     ("eps", "Diluted EPS"), ("cfo", "Operating cash flow")):
        lines.append({"line": label, "key": k, "now": last.get(k), "year_ago": (year_ago or {}).get(k), "prev": (prev or {}).get(k),
                      "yoy": ch(last, year_ago, k), "qoq": ch(last, prev, k)})
    gm = lambda r: div(r.get("gross_profit"), r.get("revenue")) if r else None
    om = lambda r: div(r.get("ebit"), r.get("revenue")) if r else None
    return {"quarter_end": last["end"], "rows": rows, "lines": lines,
            "margins": {"gross_now": gm(last), "gross_year_ago": gm(year_ago), "op_now": om(last), "op_year_ago": om(year_ago)}}


# ---------- personal budget ----------

BUCKETS = ("needs", "wants", "savings")


def budget(data):
    """data: {"net_income_monthly": N, "lines": [{"name", "amount", "bucket": needs|wants|savings}], "emergency_fund": X,
    "currency": "EUR"}. Returns the 50/30/20 split, what is left, and the 12-month cash path: savings lines leave the account
    (an ETF plan, extra repayments); the left-over, plus or minus, moves the emergency cash. `gap_month`: the first month it is below 0."""
    net = float(data["net_income_monthly"])
    lines = [dict(l, amount=float(l["amount"])) for l in data["lines"]]
    tot = {b: sum(l["amount"] for l in lines if l["bucket"] == b) for b in BUCKETS}
    spent = tot["needs"] + tot["wants"]
    left = net - spent - tot["savings"]
    target = {"needs": 0.5, "wants": 0.3, "savings": 0.2}
    monthly_save = left
    fund = float(data.get("emergency_fund", 0))
    path = [fund + left * m for m in range(13)]
    return {"net": net, "lines": lines, "totals": tot, "left": left, "share": {b: div(tot[b], net) for b in BUCKETS}, "target": target,
            "gap": {b: tot[b] - target[b] * net for b in BUCKETS}, "monthly_save": monthly_save, "path": path,
            "emergency_months": div(fund, tot["needs"]), "currency": data.get("currency", "EUR"),
            "gap_month": next((m for m, x in enumerate(path) if x < 0), None)}


# ---------- three-statement model ----------

def three_inputs(f, o=None):
    o = o or {}
    a = dcf_inputs(f, {k: v for k, v in (o or {}).items() if k in ("growth_y1", "tax_rate", "da_pct", "capex_pct_y0", "ppe_pct", "terminal_g", "years")})
    ends, hist, last = view(f)
    rev = last("revenue")
    cogs = last("cogs") or (rev - (last("gross_profit") or rev * 0.6))
    x = {
        "cogs_pct": (div(cogs, rev), "cost of revenue / revenue, last fiscal year"),
        "opex_pct": (div(rev - cogs - (last("ebit") or 0) - 0, rev), "(gross profit - EBIT) / revenue: operating costs incl. D&A in opex"),
        "interest_rate": (a["kd"]["value"], a["kd"]["source"]),
        "dso": (div((last("receivables") or 0) * 365, rev), "receivable days"),
        "dio": (div((last("inventory") or 0) * 365, cogs), "inventory days (on cost of revenue)"),
        "dpo": (div((last("payables") or 0) * 365, cogs), "payable days (on cost of revenue)"),
        "payout": (clamp(div((last("dividends") or 0) + (last("buybacks") or 0), last("net_income")) or 0, 0, 1),
                   "(dividends + buybacks) / net income, last fiscal year, held 0-100 %"),
    }
    out = {k: {"value": v, "source": s} for k, (v, s) in x.items()}
    for k in ("revenue_base", "growth_y1", "tax_rate", "da_pct", "capex_pct_y0", "ppe_pct", "terminal_g", "years"):
        out[k] = a[k]
    return overrides(out, o, "three")


def three_statement(f, a):
    """History (3 fiscal years) + 5 projected years. The balance sheet balances by construction: cash is the plug from the
    cash-flow statement; 'other' lines hold the filed totals that the model does not split."""
    v = lambda k: a[k]["value"]
    ends, hist, last = view(f)
    h = []
    for i in range(max(0, len(ends) - 3), len(ends)):
        g = lambda c: hist(c)[i] or 0
        cash = g("cash_all")
        ar, inv, ppe, ta = g("receivables"), g("inventory"), g("ppe"), g("assets")
        eq = hist("equity_total")[i] if hist("equity_total")[i] is not None else g("equity") + g("minority")   # parent + minority
        ap, debt, tl = g("payables"), g("debt"), hist("liabilities")[i] if hist("liabilities")[i] is not None else ta - eq
        h.append({"year": ends[i][:4] + "A", "revenue": g("revenue"), "cogs": g("cogs"), "opex": g("revenue") - g("cogs") - g("ebit"),
                  "ebit": g("ebit"), "interest": g("interest"), "tax": g("tax"), "net_income": g("net_income"), "da": g("da"),
                  "capex": g("capex"), "dividends": g("dividends") + g("buybacks"),
                  "cash": cash, "receivables": ar, "inventory": inv, "ppe": ppe, "other_assets": ta - cash - ar - inv - ppe, "assets": ta,
                  "payables": ap, "debt": debt, "other_liabilities": tl - ap - debt, "equity": eq, "liab_equity": tl + eq,
                  "check": ta - tl - eq})   # filed assets against filed liabilities + filed equity: not 0 by construction
    p, prev = [], h[-1]
    n = int(v("years"))
    g1 = v("growth_y1")
    for i in range(1, n + 1):
        growth = g1 - (g1 - v("terminal_g")) * (i - 1) / n
        rev = prev["revenue"] * (1 + growth)
        cogs = rev * v("cogs_pct")
        opex = rev * v("opex_pct")
        ebit = rev - cogs - opex
        interest = prev["debt"] * v("interest_rate")
        tax = max(0.0, ebit - interest) * v("tax_rate")
        ni = ebit - interest - tax
        da = rev * v("da_pct")
        capex = rev * (v("capex_pct_y0") + (capex_steady(a) - v("capex_pct_y0")) * i / n)
        ar, inv, ap = rev * v("dso") / 365, cogs * v("dio") / 365, cogs * v("dpo") / 365
        div_ = max(0.0, ni) * v("payout")   # a loss pays nothing out; it never adds cash
        cfo = ni + da - (ar - prev["receivables"]) - (inv - prev["inventory"]) + (ap - prev["payables"])
        cash = prev["cash"] + cfo - capex - div_
        ppe = prev["ppe"] + capex - da
        assets = cash + ar + inv + ppe + prev["other_assets"]
        equity = prev["equity"] + ni - div_
        le = ap + prev["debt"] + prev["other_liabilities"] + equity
        row = {"year": f"Y{i}", "revenue": rev, "cogs": cogs, "opex": opex, "ebit": ebit, "interest": interest, "tax": tax, "net_income": ni,
               "da": da, "capex": capex, "dividends": div_, "cfo": cfo, "cash": cash, "receivables": ar, "inventory": inv, "ppe": ppe,
               "other_assets": prev["other_assets"], "assets": assets, "payables": ap, "debt": prev["debt"],
               "other_liabilities": prev["other_liabilities"], "equity": equity, "liab_equity": le, "check": assets - le}
        p.append(row)
        prev = row
    return {"history": h, "projection": p}
