# Data and the methods folded in

## Data routes

| Data | Route | Notes |
|---|---|---|
| Filed numbers (10-K, 10-Q) | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | one JSON per company; `fin_data.CONCEPTS` lists the us-gaap tags tried per line; per period the first tag with a value wins (companies change tags over the years), a tuple is summed (D&A split over two tags). Annual = a 10-K period of 350-380 days; the newest filing wins per period. SEC wants `SEC_USER_AGENT` with a contact and at most 10 requests a second. |
| Ticker to CIK | `https://www.sec.gov/files/company_tickers.json` | US filers only; a foreign filer without XBRL facts has no data here |
| Price, 52-week range, beta | `https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>` | monthly closes over 5 years against `^GSPC` give the beta |
| Risk-free rate | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10` | FRED refuses browser user agents; the reader sends its own |

Every answer is cached for 24 h (6 h for prices) in `~/.cache/sigmafinanceman` (`SIGMAFIN_CACHE` moves it). When a route fails: the company facts have no line for a concept (a missing tag shows `n/a`; name the tag in the reply and ask for the number from the filing), Yahoo blocks (pass the price with `--set price=...`), FRED fails (pass `--set rf=...`).

## What was folded in, and from where

Read on 2026-10-21 (shallow clones; the skill files of each). Licences listed per the parts rule; none limits use here.

| Source | Licence | Taken |
|---|---|---|
| [anthropics/financial-services](https://github.com/anthropics/financial-services) (model-builder, pitch-agent, earnings-reviewer, statement-auditor agents and their `dcf-model`, `lbo-model`, `3-statement-model`, `comps-analysis`, `audit-xls`, `xlsx-author`, `pptx-author`, `earnings-analysis` skills) | Apache-2.0 | formulas over typed numbers; blue/black/green; a source comment on every input; odd sensitivity grids with the base case in the centre and full formulas per cell; mid-year discounting and the terminal-value checks; QUARTILE statistics for comps; balance and cash checks; the headless xlsx/pptx file contract; beat/miss against the company's own past when no consensus exists |
| [wshobson/agents](https://github.com/wshobson/agents) `quant-analyst` | MIT | risk-adjusted view and parameter sensitivity as a default output (the grids) |
| [zubair-trabzada/ai-finance-claude](https://github.com/zubair-trabzada/ai-finance-claude) `finance-budget` | MIT | the 50/30/20 split, sinking funds as monthly twelfths, the emergency fund in months |
| [googlarz/finance-assistant](https://github.com/googlarz/finance-assistant) | CC BY 4.0 | local-only household data, one profile file |
| [will2025btc/buffett-perspective](https://github.com/will2025btc/buffett-perspective) | MIT | moat, circle of competence, margin of safety and owner earnings as scorecard tests |
| [jeremylongshore/excel-analyst-pro-skill-md](https://github.com/jeremylongshore/excel-analyst-pro-skill-md) | proprietary licence: read, nothing copied | the recalculate-and-scan step before a workbook ships (our `audit`) |
| [openaccountants/openaccountants](https://github.com/openaccountants/openaccountants) | AGPL-3.0: read, nothing copied | the forensic stance of the red-flag checks (a flag is a question, not a verdict) |
| Sloan (1996), Altman (1968), Piotroski (2000) | published methods | the red-flag thresholds, Altman Z, Piotroski F |

## The masters (masters.md, strategy.md)

Read on 2026-10-23: 68 pages fetched (28 read in full, 40 full texts searched for the quote), 53 of them carry a quote. Each of the 140 quotes was matched word for word against its page twice: once by the research lane, once by an independent script. A quote that did not match was dropped, never paraphrased. Wikiquote and quote sites were leads only. Third-party transcripts (Ackman's Holy Grail of Investing interview, Leone's 2026 London summit talk) are named by outlet in the source line: check the recording when a decision depends on one. Owner earnings come from the Berkshire 1986 letter; the index-fund advice from the 2013 letter.

