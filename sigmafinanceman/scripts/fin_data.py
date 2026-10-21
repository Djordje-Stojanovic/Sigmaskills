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
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("SIGMAFIN_CACHE") or Path.home() / ".cache" / "sigmafinanceman")
SEC_UA = os.environ.get("SEC_USER_AGENT") or "sigmafinanceman research admin@example.com"
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# Concept -> the us-gaap tags that carry it; per period the first tag that has a value wins. A tuple of tags is summed
# (MSFT reports D&A in two tags).
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
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet", "DepreciationAndAmortization",
           ("Depreciation", "AmortizationOfIntangibleAssets"), "Depreciation"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "st_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "inventory": ["InventoryNet"],
    "current_assets": ["AssetsCurrent"],
    "ppe": ["PropertyPlantAndEquipmentNet"],
    "assets": ["Assets"],
    "payables": ["AccountsPayableCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "debt_current": ["LongTermDebtCurrent", "DebtCurrent"],
    "debt_noncurrent": ["LongTermDebtNoncurrent"],
    "short_borrowings": ["CommercialPaper", "ShortTermBorrowings"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
}
FLOWS = {"revenue", "cogs", "gross_profit", "rnd", "sga", "ebit", "interest", "pretax", "tax", "net_income", "eps", "shares_diluted",
         "da", "sbc", "cfo", "capex", "dividends", "buybacks"}


def _get(url, headers, ttl=86400, binary=False):
    """GET with a 24 h file cache. Returns text (or bytes)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + (".bin" if binary else ".txt"))
    if f.exists() and time.time() - f.stat().st_mtime < ttl:
        return f.read_bytes() if binary else f.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={**headers, "Accept-Encoding": "gzip"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
            break
        except urllib.error.HTTPError as e:   # SEC answers 429 when a client goes over 10 requests a second
            if e.code not in (429, 503) or attempt == 2:
                raise
            time.sleep(2 + 3 * attempt)
        except OSError:                       # a reset connection (FRED does this now and then): try again
            if attempt == 2:
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


def company_facts(ticker):
    cik, title = cik_of(ticker)
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
            if kind == "ytd" and not (170 <= d <= 290):
                continue
            key = (start, end) if kind == "ytd" else end
        if key not in out or e.get("filed", "") >= out[key][1]:
            out[key] = (e["val"], e.get("filed", ""), form)
    return out


def series(gaap, concept, kind):
    """{key: value} for a concept and the tags used. Each period takes the first tag in CONCEPTS order that has it, so a company
    that moved to a new tag (MSFT interest, 2024) keeps every year. A tuple of tags is summed over the periods all its tags share."""
    out, used = {}, []
    for tag in CONCEPTS[concept]:
        if isinstance(tag, tuple):
            parts = [_pick(gaap, t, kind) for t in tag]
            keys = set(parts[0]).intersection(*parts[1:]) if all(parts) else set()
            got, name = {k: sum(p[k][0] for p in parts) for k in keys}, "+".join(tag)
        else:
            got, name = {k: v[0] for k, v in _pick(gaap, tag, kind).items()}, tag
        new = {k: v for k, v in got.items() if k not in out}
        if new:
            out.update(new)
            used.append(name)
    return out, (", ".join(used) or None)


def fundamentals(ticker, years=5):
    """The normalized facts of one company: annual values per fiscal-year end, the latest quarters, LTM sums, and their tags."""
    raw, url, cik, title = company_facts(ticker)
    gaap = raw["facts"].get("us-gaap") or raw["facts"].get("ifrs-full") or {}
    rev, _ = series(gaap, "revenue", "fy")
    if not rev:
        raise SystemExit(f"{ticker}: no annual revenue in the SEC company facts")
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
    # a missing gross profit is revenue - cost of revenue; a missing cost of revenue is revenue - gross profit
    for e in ends:
        r, g, k = annual["revenue"].get(e), annual["gross_profit"].get(e), annual["cogs"].get(e)
        if g is None and r is not None and k is not None:
            annual["gross_profit"][e] = r - k
        if k is None and r is not None and g is not None:
            annual["cogs"][e] = r - g
    dei = raw["facts"].get("dei", {})
    so = [x for x in (dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares") or [])]
    cover = max(so, key=lambda x: (x.get("filed", ""), x["end"])) if so else None
    out = {"ticker": ticker.upper(), "name": title, "cik": cik, "source": url, "fiscal_year_ends": ends, "annual": annual, "tags": tags,
           "quarters": {c: {k: v for k, v in sorted(q.items())[-12:]} for c, q in quarters.items()},
           "ytd": {c: {f"{k[0]}..{k[1]}": v for k, v in sorted(q.items())[-8:]} for c, q in ytd.items()},
           "shares_cover": cover["val"] if cover else None, "shares_cover_date": cover["end"] if cover else None,
           "last_10k": max((e for e in _entries(gaap, CONCEPTS["revenue"][0]) if e.get("form", "").startswith("10-K")),
                           key=lambda e: e.get("filed", ""), default={}).get("filed")}
    out["ltm"] = ltm(out)
    return out


def ltm(f):
    """Last twelve months per flow concept: the latest fiscal year plus the newer year-to-date minus the year-ago year-to-date."""
    fy_end = f["fiscal_year_ends"][-1]
    out = {}
    for c in FLOWS:
        fy = f["annual"][c].get(fy_end)
        if fy is None:
            continue
        val, asof = fy, fy_end
        newer = sorted((k for k in f["ytd"].get(c, {}) if k.split("..")[1] > fy_end), key=lambda k: k.split("..")[1])
        if newer and c != "eps":
            cur = newer[-1]
            s, e = cur.split("..")
            prior = next((k for k in f["ytd"][c] if abs(_days(k.split("..")[0], s) - 365) < 15 and abs(_days(k.split("..")[1], e) - 365) < 15), None)
            if prior:
                val, asof = fy + f["ytd"][c][cur] - f["ytd"][c][prior], e
        out[c] = val
        out.setdefault("_asof", asof)
    return out


def price_history(ticker, rng="5y", interval="1mo"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={rng}&interval={interval}"
    d = json.loads(_get(url, {"User-Agent": WEB_UA}, ttl=6 * 3600))["chart"]["result"][0]
    closes = d["indicators"].get("adjclose", [{}])[0].get("adjclose") or d["indicators"]["quote"][0]["close"]
    return d["meta"], [c for c in closes if c is not None], url


def market(ticker):
    """Price, 52-week range and 5-year monthly beta against the S&P 500 (Yahoo chart data)."""
    meta, monthly, url = price_history(ticker)
    _, idx, _ = price_history("^GSPC")
    _, daily, _ = price_history(ticker, "1y", "1d")
    n = min(len(monthly), len(idx))
    a = [monthly[-n:][i + 1] / monthly[-n:][i] - 1 for i in range(n - 1)]
    b = [idx[-n:][i + 1] / idx[-n:][i] - 1 for i in range(n - 1)]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (len(a) - 1)
    var = sum((y - mb) ** 2 for y in b) / (len(b) - 1)
    return {"price": meta["regularMarketPrice"], "currency": meta.get("currency", "USD"),
            "price_time": dt.datetime.fromtimestamp(meta["regularMarketTime"], dt.timezone.utc).strftime("%Y-%m-%d"),
            "low_52w": min(daily), "high_52w": max(daily), "beta": round(cov / var, 2), "beta_months": len(a), "source": url}


def risk_free():
    """The latest US 10-year Treasury yield (FRED DGS10), as a fraction."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=" + (dt.date.today() - dt.timedelta(days=30)).isoformat()
    rows = [r.split(",") for r in _get(url, {"User-Agent": "sigmafinanceman/0.1"}, ttl=6 * 3600).strip().splitlines()[1:]]
    rows = [r for r in rows if len(r) == 2 and r[1] not in (".", "")]
    return float(rows[-1][1]) / 100, rows[-1][0], url


def company(ticker, years=5, with_market=True):
    """Fundamentals plus market data and the risk-free rate: the one input every model reads."""
    f = fundamentals(ticker, years)
    if with_market:
        f["market"] = market(ticker)
        f["rf"], f["rf_date"], f["rf_source"] = risk_free()
    return f


def is_num(x):
    return isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x))
