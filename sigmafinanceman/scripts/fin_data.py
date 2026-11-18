"""Public data for sigmafinanceman: SEC EDGAR company facts (10-K and 10-Q numbers), Yahoo chart prices, FRED 10-year yield.

Standard library only. Every reader caches its answer for 24 h in ~/.cache/sigmafinanceman (SIGMAFIN_CACHE overrides) and names its
source URL, so each number in a model can cite where it came from. SEC asks for a contact in the User-Agent: set SEC_USER_AGENT to
"<name> <email>"; the default works but names no person.
"""
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("SIGMAFIN_CACHE") or Path.home() / ".cache" / "sigmafinanceman")
SEC_UA = os.environ.get("SEC_USER_AGENT") or "sigmafinanceman research admin@example.com"
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
FRED_UA = "curl/8.0"   # FRED refuses browser agents and stalls on unknown ones

# Concept -> the us-gaap tags that carry it; per period the first tag that has a value wins (MAX_OF: the largest wins, as a
# part-line can come first). A tuple of tags is summed (MSFT reports D&A in two tags). Debt tags are disjoint balances: a
# component (CommercialPaper inside KO's NotesAndLoansPayable) only fills a period no wider tag covers.
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "rnd": ["ResearchAndDevelopmentExpense"],
    "sga": ["SellingGeneralAndAdministrativeExpense", ("SellingAndMarketingExpense", "GeneralAndAdministrativeExpense")],
    "ebit": ["OperatingIncomeLoss"],
    "interest": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "shares_basic": ["WeightedAverageNumberOfSharesOutstandingBasic"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet", "DepreciationAndAmortization",
           ("Depreciation", "AmortizationOfIntangibleAssets"), "Depreciation"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "cash_st": ["CashCashEquivalentsAndShortTermInvestments"],
    "cash_restricted_incl": ["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "restricted_cash": ["RestrictedCashAndCashEquivalents", "RestrictedCashAndCashEquivalentsAtCarryingValue", "RestrictedCash"],
    "st_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
                       "OtherShortTermInvestments"],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "inventory": ["InventoryNet"],
    "current_assets": ["AssetsCurrent"],
    "ppe": ["PropertyPlantAndEquipmentNet"],
    "assets": ["Assets"],
    "payables": ["AccountsPayableCurrent", "AccountsPayableTradeCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "debt_current": ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
    "debt_noncurrent": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
    "short_borrowings": ["ShortTermBorrowings", "NotesAndLoansPayable", "CommercialPaper"],
    "commercial_paper": ["CommercialPaper"],
    "debt_current_all": ["DebtCurrent"],
    "debt_total": ["LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities", "DebtLongtermAndShorttermCombinedAmount",
                   "LongTermDebt", "DebtAndCapitalLeaseObligations"],
    "liabilities": ["Liabilities"],
    "liab_equity": ["LiabilitiesAndStockholdersEquity"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "equity_total": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "investments": ["EquityMethodInvestments"],
    "preferred": ["PreferredStockValue"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "minority": ["MinorityInterest"],
}
FLOWS = {"revenue", "cogs", "gross_profit", "rnd", "sga", "ebit", "interest", "pretax", "tax", "net_income", "eps", "shares_diluted",
         "shares_basic", "da", "sbc", "cfo", "capex", "dividends", "buybacks"}
MAX_OF = {"da"}                                   # MCD: DepreciationDepletionAndAmortization 457 is a part; D&A 2,199 is the line
NOT_ADDITIVE = {"eps", "shares_diluted", "shares_basic"}   # averages and ratios: never summed or subtracted across periods


def _get(url, headers, ttl=86400, binary=False, timeout=40, tries=3):
    """GET with a 24 h file cache. Returns text (or bytes)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + (".bin" if binary else ".txt"))
    if f.exists() and time.time() - f.stat().st_mtime < ttl:
        return f.read_bytes() if binary else f.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={**headers, "Accept-Encoding": "gzip"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
            break
        except urllib.error.HTTPError as e:   # SEC answers 429 when a client goes over 10 requests a second
            if e.code not in (429, 503) or attempt == tries - 1:
                raise
            time.sleep(2 + 3 * attempt)
        except OSError:                       # a reset connection (FRED does this now and then): try again
            if attempt == tries - 1:
                raise
            time.sleep(2 + 3 * attempt)
    f.write_bytes(body)
    return body if binary else body.decode("utf-8")


def cik_of(ticker):
    data = json.loads(_get("https://www.sec.gov/files/company_tickers.json", {"User-Agent": SEC_UA}))
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"]), row["title"]
    raise SystemExit(f"{ticker}: no SEC CIK found (a US filer's ticker is needed; check the spelling)")


def company_facts(ticker, cik=None):
    cik, title = (cik, ticker.upper()) if cik else cik_of(ticker)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    return json.loads(_get(url, {"User-Agent": SEC_UA})), url, cik, title


def _days(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def _entries(gaap, tag):
    units = (gaap.get(tag) or {}).get("units") or {}
    for unit in ("USD", "USD/shares", "shares"):
        if unit in units:
            return units[unit]
    return []


def _pick(gaap, tag, kind):
    """{period end: (value, filed, form)} for one tag. kind: 'fy' (10-K, ~1 year), 'q' (any form, ~1 quarter),
    'ytd' (10-Q year to date, keyed by (start, end)), 'bs' (instant, any form). The latest filing wins per period."""
    out = {}
    for e in _entries(gaap, tag):
        form = e.get("form", "")
        if not form.startswith(("10-K", "10-Q", "20-F", "40-F")):
            continue
        start, end = e.get("start"), e["end"]
        if kind == "bs":
            if start:
                continue
            key = end
        else:
            if not start:
                continue
            d = _days(start, end)
            if kind == "fy" and not (350 <= d <= 380 and form.startswith(("10-K", "20-F", "40-F"))):
                continue
            if kind == "q" and not (80 <= d <= 100):
                continue
            if kind == "ytd" and not (80 <= d <= 290):   # Q1 is a year to date too
                continue
            key = (start, end) if kind == "ytd" else end
        if key not in out or e.get("filed", "") >= out[key][1]:
            out[key] = (e["val"], e.get("filed", ""), form)
    return out


def series(gaap, concept, kind):
    """{key: value} for a concept and the tags used. Each period takes the first tag in CONCEPTS order that has it, so a company
    that moved to a new tag (MSFT interest, 2024) keeps every year. A tuple of tags is summed over the periods all its tags share."""
    out, used = {}, []
    big = concept in MAX_OF
    for tag in CONCEPTS[concept]:
        if isinstance(tag, tuple):
            parts = [_pick(gaap, t, kind) for t in tag]
            keys = set(parts[0]).intersection(*parts[1:]) if all(parts) else set()
            got, name = {k: sum(p[k][0] for p in parts) for k in keys}, "+".join(tag)
        else:
            got, name = {k: v[0] for k, v in _pick(gaap, tag, kind).items()}, tag
        new = {k: v for k, v in got.items() if k not in out or (big and v > out[k])}
        if new:
            out.update(new)
            used.append(name)
    return out, (", ".join(used) or None)


DEBT_PARTS = ("debt_noncurrent", "debt_current", "short_borrowings", "commercial_paper", "debt_current_all", "debt_total")


def debt_of(get):
    """Total debt on one balance-sheet date from disjoint lines; None when no debt line is filed. get(concept) -> value or None.
    The larger of the parts and a filed total wins, as a total tag holds at least the long-term debt."""
    nc, cur, stb, cp, dc, tot = (get(c) for c in DEBT_PARTS)
    if all(x is None for x in (nc, cur, stb, dc, tot)):
        return None
    if dc is not None:
        current = dc                  # DebtCurrent already holds short borrowings and current maturities (PEP 10-K)
    elif stb is not None and cur is not None and cp is not None and stb >= cur + cp:
        current = stb                 # PEP 10-Q: the short-term line already holds the current long-term debt and the paper
    else:
        current = (cur or 0) + (stb or 0)
    return max((nc or 0) + current, tot or 0)


def cash_of(get):
    """Cash and short-term investments on one date: the combined line when filed, else cash + short-term investments."""
    both = get("cash_st")
    if both is not None:
        return both
    c = get("cash")
    return None if c is None else c + (get("st_investments") or 0)


def fundamentals(ticker, years=5, cik=None):
    """The normalized facts of one company: annual values per fiscal-year end, the latest quarters, LTM sums, and their tags.
    cik: read this SEC filer instead of the ticker's (a predecessor that holds the 10-K history)."""
    raw, url, cik, title = company_facts(ticker, cik)
    gaap = raw["facts"].get("us-gaap") or raw["facts"].get("ifrs-full") or {}
    rev, _ = series(gaap, "revenue", "fy")
    if not rev:
        qs = sorted(series(gaap, "revenue", "ytd")[0])
        raise SystemExit(f"{ticker}: the SEC company facts for CIK {cik} hold no 10-K revenue" +
                         (f", only 10-Q periods from {qs[0][0]} to {qs[-1][1]}: a new registrant (such as a new holding company) "
                          "has its 10-K history under the predecessor's CIK" if qs else "") + f". Pass that filer's number with --set cik=<CIK> "
                         f"(EDGAR company search lists it), or check the facts at {url}")
    ends = sorted(rev)[-years:]
    annual, tags, quarters, ytd = {}, {}, {}, {}
    for c in CONCEPTS:
        vals, tag = series(gaap, c, "bs" if c not in FLOWS else "fy")
        if c not in FLOWS:   # a balance-sheet value: the instant on each fiscal-year end
            annual[c] = {e: vals.get(e) for e in ends}
        else:
            annual[c] = {e: vals.get(e) for e in ends}
        tags[c] = tag
        if c in FLOWS:
            quarters[c] = series(gaap, c, "q")[0]
            ytd[c] = series(gaap, c, "ytd")[0]
        else:
            quarters[c] = vals
    for c in ("shares_diluted", "shares_basic"):   # MCD files share counts in millions (716.4): scale them to shares
        for d in (annual[c], quarters[c], ytd[c]):
            for k, v in d.items():
                if v is not None and 0 < v < 1e5:
                    d[k] = v * 1e6
    # a missing gross profit is revenue - cost of revenue; a missing cost of revenue is revenue - gross profit
    for d in (annual, quarters):   # a missing line read from lines that are filed
        for e in set(d["assets"]) | set(d["liab_equity"]):
            tot = d["equity_total"].get(e)
            if tot is None and d["equity"].get(e) is not None:
                tot = d["equity"][e] + (d["minority"].get(e) or 0)
            if d["liabilities"].get(e) is None and d["liab_equity"].get(e) is not None and tot is not None:
                d["liabilities"][e] = d["liab_equity"][e] - tot   # never assets - parent equity: that hides minority interest
            if d["cash"].get(e) is None and d["cash_restricted_incl"].get(e) is not None:
                d["cash"][e] = d["cash_restricted_incl"][e] - (d["restricted_cash"].get(e) or 0)
    for d in (annual, quarters):   # one total debt and one cash line per date, so every model and the workbook read the same number
        dates = set().union(*(d[c] for c in DEBT_PARTS + ("cash", "cash_st"))) & (set(ends) if d is annual else set(d["assets"]) | set(ends))
        d["debt"] = {e: debt_of(lambda c: d[c].get(e)) for e in sorted(dates)}
        d["cash_all"] = {e: cash_of(lambda c: d[c].get(e)) for e in sorted(dates)}
    tags["debt"] = "; ".join(t for t in (tags[c] for c in DEBT_PARTS) if t) or None
    tags["cash_all"] = "; ".join(t for t in (tags[c] for c in ("cash_st", "cash", "st_investments")) if t) or None
    for e in ends:
        r, g, k = annual["revenue"].get(e), annual["gross_profit"].get(e), annual["cogs"].get(e)
        if g is None and r is not None and k is not None:
            annual["gross_profit"][e] = r - k
        if k is None and r is not None and g is not None:
            annual["cogs"][e] = r - g
    dei = raw["facts"].get("dei", {})
    so = [x for x in (dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares") or [])]
    cover = max(so, key=lambda x: (x.get("filed", ""), x["end"])) if so else None
    if cover and 0 < cover["val"] < 1e5:
        cover = dict(cover, val=cover["val"] * 1e6)
    tenk = [e for t in CONCEPTS["revenue"] for e in _entries(gaap, t) if e.get("form", "").startswith("10-K") and e["end"] == ends[-1]]
    bs_dates = sorted(set(quarters["assets"]) & set(quarters["liab_equity"])) or sorted(quarters["assets"])
    out = {"ticker": ticker.upper(), "name": title, "cik": cik, "source": url, "fiscal_year_ends": ends, "annual": annual, "tags": tags,
           "quarters": {c: {k: v for k, v in sorted(q.items())[-12:]} for c, q in quarters.items()},
           "ytd": {c: {f"{k[0]}..{k[1]}": v for k, v in sorted(q.items(), key=lambda kv: kv[0][1])[-16:]} for c, q in ytd.items()},
           "shares_cover": cover["val"] if cover else None, "shares_cover_date": cover["end"] if cover else None,
           "bs_date": max(bs_dates[-1], ends[-1]) if bs_dates else ends[-1],
           "last_10k": max((e.get("filed", "") for e in tenk), default=None)}
    out["ltm"] = ltm(out)
    return out


def ltm(f):
    """Last twelve months per flow concept: the latest fiscal year plus the newer year-to-date (Q1 included) minus the year-ago
    year-to-date. EPS and share counts are not additive: they keep the fiscal-year value. `_asof` is revenue's date; `_asof_of`
    holds each line's own."""
    fy_end = f["fiscal_year_ends"][-1]
    out, dates = {}, {}
    for c in FLOWS:
        fy = f["annual"][c].get(fy_end)
        if fy is None:
            continue
        val, asof = fy, fy_end
        newer = sorted((k for k in f["ytd"].get(c, {}) if k.split("..")[1] > fy_end and 0 < _days(fy_end, k.split("..")[0]) <= 10),
                       key=lambda k: k.split("..")[1])   # a year to date of the new fiscal year starts the day after its end
        if newer and c not in NOT_ADDITIVE:
            cur = newer[-1]
            s, e = cur.split("..")
            prior = next((k for k in f["ytd"][c] if abs(_days(k.split("..")[0], s) - 365) < 15 and abs(_days(k.split("..")[1], e) - 365) < 15), None)
            if prior:
                val, asof = fy + f["ytd"][c][cur] - f["ytd"][c][prior], e
        out[c], dates[c] = val, asof
    out["_asof"], out["_asof_of"] = dates.get("revenue", fy_end), dates
    return out


def price_history(ticker, rng="5y", interval="1mo"):
    """(meta, {month 'YYYY-MM': adjusted close}, unadjusted quote dict, url)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={rng}&interval={interval}"
    d = json.loads(_get(url, {"User-Agent": WEB_UA}, ttl=6 * 3600))["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    closes = (d["indicators"].get("adjclose") or [{}])[0].get("adjclose") or q["close"]
    month = lambda t: (dt.date(1970, 1, 1) + dt.timedelta(seconds=t)).strftime("%Y-%m")
    return d["meta"], {month(t): c for t, c in zip(d.get("timestamp", []), closes) if c is not None}, q, url


def beta_of(asset, index):
    """Monthly beta from two {month: close} maps. A return counts only when both months exist in both series, so a gap never
    pairs a two-month move with a one-month one. (beta, months used); beta None under 24 months or a flat index."""
    nxt = lambda m: f"{int(m[:4]) + int(m[5:]) // 12}-{int(m[5:]) % 12 + 1:02d}"
    pairs = [(asset[nxt(m)] / asset[m] - 1, index[nxt(m)] / index[m] - 1) for m in sorted(asset)
             if m in index and nxt(m) in asset and nxt(m) in index]
    if len(pairs) < 24:
        return None, len(pairs)
    a, b = zip(*pairs)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    var = sum((y - mb) ** 2 for y in b)
    if var <= 0:
        return None, len(pairs)
    return round(sum((x - ma) * (y - mb) for x, y in pairs) / var, 2), len(pairs)


def market(ticker):
    """Price, 52-week range (unadjusted daily highs and lows) and 5-year monthly beta against the S&P 500 (Yahoo chart data)."""
    meta, monthly, _, url = price_history(ticker)
    _, idx, _, _ = price_history("^GSPC")
    _, _, daily, _ = price_history(ticker, "1y", "1d")
    beta, months = beta_of(monthly, idx)
    lows, highs = [x for x in daily.get("low") or [] if x], [x for x in daily.get("high") or [] if x]
    return {"price": meta["regularMarketPrice"], "currency": meta.get("currency", "USD"),
            "price_time": dt.datetime.fromtimestamp(meta["regularMarketTime"], dt.timezone.utc).strftime("%Y-%m-%d"),
            "low_52w": min(lows) if lows else None, "high_52w": max(highs) if highs else None, "beta": beta, "beta_months": months,
            "source": url}


def risk_free():
    """The latest US 10-year Treasury yield, as a fraction: FRED DGS10, else the Yahoo ^TNX chart.

    FRED does not answer some Linux clients at all (every read times out), so it gets one short try.
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=" + (dt.date.today() - dt.timedelta(days=30)).isoformat()
    try:
        rows = [r.split(",") for r in _get(url, {"User-Agent": FRED_UA}, ttl=6 * 3600, timeout=15, tries=1).strip().splitlines()[1:]]
        rows = [r for r in rows if len(r) == 2 and r[1] not in (".", "")]
        if rows:
            return float(rows[-1][1]) / 100, rows[-1][0], url
    except OSError:
        pass
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=5d&interval=1d"
    meta = json.loads(_get(url, {"User-Agent": WEB_UA}, ttl=6 * 3600))["chart"]["result"][0]["meta"]
    day = dt.datetime.fromtimestamp(meta["regularMarketTime"], dt.timezone.utc).strftime("%Y-%m-%d")
    return meta["regularMarketPrice"] / 100, day, url


def company(ticker, years=5, with_market=True, with_rf=True, cik=None):
    """Fundamentals plus market data and the risk-free rate: the one input every model reads. A caller that has the price and beta
    (or the rate) from --set skips that fetch."""
    f = fundamentals(ticker, years, cik)
    if with_market:
        f["market"] = market(ticker)
    if with_rf:
        f["rf"], f["rf_date"], f["rf_source"] = risk_free()
    return f


def is_num(x):
    return isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x))


# ---------- readers for the other asset classes ----------

def history(ticker, interval="1mo"):   # range=max thins the months; period1=0 returns every month (504 for KO vs 241 at 20y)
    """Dated closes and paid dividends from the Yahoo chart: {"dates", "closes", "dividends": [(date, amount)], "meta", "source"}."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?period1=0"
           f"&period2={int(time.time()) // 86400 * 86400}&interval={interval}&events=div")   # day-rounded: the 6 h cache still hits
    d = json.loads(_get(url, {"User-Agent": WEB_UA}, ttl=6 * 3600))["chart"]["result"][0]
    day = lambda t: (dt.date(1970, 1, 1) + dt.timedelta(seconds=t)).isoformat()   # Windows refuses pre-1970 timestamps
    q = d["indicators"]["quote"][0]["close"]   # price closes; the dividends are counted on their own
    adj = (d["indicators"].get("adjclose") or [{}])[0].get("adjclose") or q   # dividends reinvested: the total-return line
    rows = [(day(t), c, a) for t, c, a in zip(d.get("timestamp", []), q, adj) if c is not None and a is not None]
    divs = sorted((day(v["date"]), v["amount"]) for v in (d.get("events") or {}).get("dividends", {}).values())
    return {"dates": [r[0] for r in rows], "closes": [r[1] for r in rows], "adj": [r[2] for r in rows], "dividends": divs,
            "meta": d["meta"], "source": url}


def fred(series_id, start="1900-01-01"):
    """One FRED series as [(date, value)]; FRED marks a missing day with '.'."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    rows = [r.split(",") for r in _get(url, {"User-Agent": FRED_UA}, ttl=6 * 3600, timeout=30).strip().splitlines()[1:]]
    return [(r[0], float(r[1])) for r in rows if len(r) == 2 and r[1] not in (".", "")], url


def gpu_rent(gpu_name):
    """Live single-GPU rental offers on vast.ai (public search, no key): dollars per GPU-hour, sorted."""
    q = json.dumps({"gpu_name": {"eq": gpu_name}, "rentable": {"eq": True}, "num_gpus": {"eq": 1}})
    url = "https://console.vast.ai/api/v0/bundles/?q=" + urllib.parse.quote(q)
    offers = json.loads(_get(url, {"User-Agent": "sigmafinanceman/0.1"}, ttl=3600)).get("offers", [])
    return sorted(o["dph_total"] for o in offers if o.get("dph_total")), url


def card_price(query):
    """TCGplayer prices of Pokemon cards (pokemontcg.io, no key), e.g. 'name:charizard set.id:base1'. Market = recent sales."""
    url = "https://api.pokemontcg.io/v2/cards?select=id,name,set,rarity,tcgplayer&q=" + urllib.parse.quote(query)
    return json.loads(_get(url, {"User-Agent": "sigmafinanceman/0.1"}, ttl=6 * 3600)).get("data", []), url
