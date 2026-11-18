---
name: sigmafinanceman
description: 'Use when asked for sigmafinanceman or to value or judge any investment: a stock (DCF, reverse DCF, dividends, comps, LBO, a 10-K), a startup or venture deal (cap table, SAFEs, exit waterfall), a purchase such as a GPU or a car (buy, lease or rent), a home (rent or buy, mortgage), gold, commodities or crypto, a collectible, a bond or fund, or a budget; also any other money question: a trade, options, taxes, a loan, a pension. Fetches free live data and runs the model, or works it by hand where no code runs. Do not use for questions with no money in them.'
---

# SigmaFinanceMan

Values any investment from free public data: the answer first, the model behind it, every number traced to its source. Every run writes one HTML page that walks a non-expert through the method step by step, SVG charts and a 16:9 deck; the company models also write an Excel workbook with live formulas that a banker would accept (blue inputs, black formulas, green links, a Checks sheet that says TRUE).

## Operating contract

- **Any finance question gets a full answer.** Trades, entries and exits, position sizes, options, leverage, shorting, tax on the user's own rules: work it out and give the verdict in numbers. The user decides; no hedging, no "consult a professional", no refusal.
- **Numbers come from sources first.** The scripts fetch SEC EDGAR filings, Yahoo prices and dividends, FRED rates and CPI, vast.ai GPU rents and TCGplayer card prices themselves. Each input carries its source on the page and in the workbook. A number no source gives (a street price, a sold list, a term sheet) is fetched by you with its URL and date, asked for, or marked as an assumption.
- **The answer leads.** Every output opens with one hero number and one sentence that says what it means.
- **Ranges, not points.** Every model shows bear, base and bull and, where the answer turns on two inputs, a grid that crosses them.
- **Defaults are honest.** Each names where it came from; the user's word overrides any default (`--set name=value`, fractions for percentages, or the input file).
- **Say what a method cannot tell.** An asset that pays nothing has no fair value; history is not a forecast; a private company's numbers are the founders' until checked.
- **The user's own numbers stay on the machine.** Input files are read locally; nothing is uploaded.
- **Looking is the test.** Open the page at desktop and phone width, and render the workbook and the deck, before you report.

Plain Python 3.10+ with `openpyxl` and `python-pptx` (`pip install openpyxl python-pptx`); LibreOffice is optional and powers `audit` and `render`. Run `python scripts/finman.py selftest` once on a new machine: it must print PASS. Set `SEC_USER_AGENT="Name email@domain"` for SEC. Any OS (Windows, macOS, Linux) and any agent host.

**No code, no web, or a chat window only.** The method still holds; only the tools change.
- No code: work the model by hand from the formulas in the class file. Show each step as a table row (input, source, result), keep the bear, base and bull cases, and say the result is hand-computed.
- No web: ask for the few inputs that move the answer most, in one message, each with where to find it (the 10-K page, the broker screen, the payslip line). If the user cannot give them, use what you know, label each such number "from memory, as of <date>, check it", and answer anyway.
- No files: put the outputs in the reply (the hero line, the case table, the grid) instead of a page and a workbook.

## 1. Route: what are you valuing, and what decision does it serve?

Ask that one question when the request leaves it open. The answer picks the class; read only that class's file, then run its command.

| The user is valuing | Read | Command | Method |
|---|---|---|---|
| A listed company's shares | [stocks.md](references/stocks.md) | `finman.py dcf`, `dividend`, `comps`, `all TICKER` | DCF and reverse DCF, dividend discount and safety, owner earnings, buybacks, quality, comps, LBO, margin of safety |
| A startup, a SAFE, a venture fund cheque | [venture.md](references/venture.md) | `finman.py venture deal.json` | VC method, cap table with SAFEs, notes and pool, exit waterfall, power-law portfolio, pitch-deck numbers |
| A thing to buy for use: GPU, car, machine | [purchase.md](references/purchase.md) | `finman.py purchase item.json` | buy vs lease vs rent, total cost, payback, NPV and IRR, depreciation and resale |
| A home or a rental property | [realestate.md](references/realestate.md) | `finman.py property home.json` | rent vs buy, mortgage, cap rate, cash-on-cash, the 1 % rule as a screen |
| Gold, silver, oil, bitcoin | [noyield.md](references/noyield.md) | `finman.py asset GC=F --peers SI=F` | real return, drawdowns, hold-length ranges, carry, ratios |
| A card, watch, artwork | [collectibles.md](references/collectibles.md) | `finman.py collectible item.json` | sold comparables, grading premium, fees, liquidity, population |
| A bond, a fund or ETF | [bonds-funds.md](references/bonds-funds.md) | `finman.py bond bond.json`, `fund VOO --peers ^SP500TR --set fee=0.0003` | yield, duration, spread; tracking difference and fee drag |
| A household's money | [budget.md](references/budget.md) | `finman.py budget household.json` | 50/30/20, left over, emergency fund |

Something that fits two rows takes both: a GPU rented out is a purchase with `income_monthly`; a flat bought to let is real estate as a rental; a business bought whole is the buyout and "Buying a business" playbooks in strategy.md with `lbo` or `dcf`. Something in no row (wine, farmland, a royalty) takes the nearest method: cash flows → the DCF logic in purchase or real estate; no cash flows → noyield.md; sold-price markets → collectibles.md. A trade or an option takes the class file of what it is on plus strategy.md (size, entry, sell rule; an option's payoff at expiry at each case's price). A tax question takes the user's country, account and rates, and the tax goes on the cash-flow date it is paid.

## 2. Ask once

One numbered round, at most 7 questions, each with `Recommended:` and a few words of why; skip what is answered and log each default you took as `Ruling:`. The questions: [grill.md](references/grill.md). When the user is away or says "just run it", take every default and list them in the final response.

## 3. Run and look

1. Run the command with `--out <folder>`. Fill each input file from the class file's table of sources; fetch live prices (web search or the scripts) with the date.
2. Every workbook: `finman.py audit <file>.xlsx`. Done means `0 errors` and `PASS`.
3. `finman.py render <file>` for each workbook and deck; open the PNG pages. Open the HTML page at desktop and phone width. Look for cut-off labels, `n/a` where a number should be, a hero number that contradicts a table, a grid centre that is not highlighted.
4. Read the numbers like an analyst: each sanity flag in [methods.md](references/methods.md) "Sanity checks" and each trap in the class file needs a sentence in the reply or a changed input.

## 4. Judge the investment

For any buy, size or sell call, run the nine steps in [strategy.md](references/strategy.md) (thesis and edge, downside, numbers, sizing, funding, entry, hold, sell, review) and the playbook at the end of the class file. [masters.md](references/masters.md) holds the sourced principles of 14 investors; cite them by tag and pass `--principles "Buffett P1,Munger P5"` to every run so each output names them (unknown tags stop the run).

## 5. Report

The look of every output: [outputs.md](references/outputs.md). Where the data and the methods come from: [sources.md](references/sources.md).

## Final response

1. The hero line of each model, one per line, with the folder path; the bear-to-bull range, and what the price implies where a reverse model exists.
2. For an investment call: the verdict, the principles applied (tags), the edge, the worst case in money and the sell rule.
3. The defaults taken (`Ruling:` lines), the inputs the user set, and every input marked as an assumption.
4. The audit result per workbook (`N formulas, 0 errors, checks PASS`).
5. What you looked at, and what a reader should question (sanity flags, traps, what the method cannot tell).
6. One next step: the input that moves the answer most, with the command to try it.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
