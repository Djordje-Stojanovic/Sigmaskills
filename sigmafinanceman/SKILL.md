---
name: sigmafinanceman
description: 'The finance analyst: DCF, LBO, trading comps, three-statement models, ratios, statement analysis with red flags, a value-investing scorecard, earnings reviews and personal budgets, from public filings (SEC EDGAR) or the user''s own numbers. Asks one question round, then builds Excel with live formulas in banker colours, a slide deck, SVG charts and an HTML page, and checks every workbook. Use to value a company, model a deal, compare peers, read a 10-K, review a quarter or plan a budget. Do not use to place trades or move money, for tax filing, or for live intraday market data.'
---

# SigmaFinanceMan

Turn a ticker or a household's numbers into a finished analysis: the answer first, the model behind it, every input traced to its source. One run gives the same numbers in four forms: an Excel workbook with live formulas (change an input, the model moves), a 16:9 deck, SVG charts and one HTML page. The bar is a model a banker would accept: blue inputs, black formulas, green links, a balanced balance sheet, a sensitivity grid whose centre is the base case, and a Checks sheet that says TRUE.

## Operating contract

- **Numbers come from sources, never from memory.** Company figures come from SEC EDGAR company facts (the 10-K and 10-Q XBRL), prices and beta from Yahoo chart data, the risk-free rate from FRED. Each input carries its source in the workbook (cell comment) and on the page. A number the sources do not give is asked for or marked as an assumption.
- **Formulas over typed numbers.** Only filed figures, market data and assumptions are typed (blue). Every calculation is a formula. The Python maths and the workbook formulas are two builds of one model; `audit` proves they agree.
- **The answer leads.** Every output opens with one hero number, one sentence that says what it means, then the detail.
- **Defaults are honest.** Each default says where it came from (for example "3-year revenue CAGR, held 0-25 %"). The user's word overrides any default.
- **The user's own numbers stay on the machine.** A budget is read from a local file; nothing is uploaded.
- **Looking is the test.** An exit code is not proof: render the workbook and the deck and look at the pages before you report.

The helper is plain Python 3.10+ with `openpyxl` and `python-pptx` (`pip install openpyxl python-pptx`). LibreOffice is optional and powers `audit` and `render`. Run `python scripts/finman.py selftest` once on a new machine: it must print PASS.

## 1. Ask once

Read what the user gave: tickers, a filing, a spreadsheet, a budget. Then ask one numbered round, at most 7 questions, each with `Recommended:` and a few words of why. Skip what is already answered; log each answer you took for the user as `Ruling:`. The questions and their defaults: [grill.md](references/grill.md). When the user is away or says "just run it", take every default and list them in the final response.

## 2. Pick the models

| The user wants | Command | Main output |
|---|---|---|
| What is it worth (intrinsic) | `finman.py dcf TICKER` | value per share, WACC x growth grid |
| Could a buyout work | `finman.py lbo TICKER` | IRR and money multiple, entry x exit grid |
| Cheap or dear against peers | `finman.py comps TICKER --peers A,B,C` | multiples table, quartiles, football field |
| The full model | `finman.py three TICKER` | income statement, balance sheet, cash flow, 5 years out |
| Health over time | `finman.py ratios TICKER` | 22 ratios over 5 fiscal years |
| Anything wrong in the books | `finman.py analyze TICKER` | red flags, common-size, Altman Z, Piotroski F |
| Would Buffett buy it | `finman.py score TICKER` | 10 pass/fail tests |
| How was the quarter | `finman.py earnings TICKER` | latest quarter vs a year ago and the prior quarter |
| Where does my money go | `finman.py budget FILE.json` | 50/30/20 split, left over, 12-month fund path |
| Everything on one company | `finman.py all TICKER --peers A,B,C` | all of the above except budget |

Peers for comps: 4 to 8 companies with the same business model and a similar size; say why each one is in. Override any input with `--set name=value` (fractions for percentages, for example `--set terminal_g=0.02`). The input names, every formula and the defaults: [methods.md](references/methods.md). The budget file format: [budget.md](references/budget.md).

## 3. Run and audit

1. Set `SEC_USER_AGENT="Name email@domain"` (SEC asks for a contact). Run the commands with `--out <folder>`; the default formats are `xlsx,pptx,svg,html`.
2. Run `finman.py audit <file>.xlsx` on every workbook. It recalculates the file in LibreOffice and lists formula errors and the Checks sheet. Done means `0 errors` and `PASS` for each workbook.
3. Run `finman.py render <file>` on each workbook and deck, and open the PNG pages. Open the HTML page at desktop and phone width. Look for: cut-off labels, `n/a` where a number should be, a hero number that contradicts a table, a sensitivity centre that is not highlighted.
4. Read the numbers like an analyst. Terminal value above 75 % of EV, a WACC under the risk-free rate, an IRR above 40 %, a negative EBITDA multiple: each needs a sentence in the reply or a changed input. The checks per model: [methods.md](references/methods.md) "Sanity checks".

## 4. Report

The look of every output (the Ledger system: tokens, banker colours, number formats, chart rules) is in [outputs.md](references/outputs.md). Where the data and the folded-in methods come from: [sources.md](references/sources.md).

## Final response

1. The hero line of each model, one per line, with the folder path.
2. The defaults you took (`Ruling:` lines) and the inputs the user set.
3. The audit result per workbook (`N formulas, 0 errors, checks PASS`).
4. What you looked at, and anything a reader should question (the sanity flags).
5. One next step: the input whose change moves the answer most, with the command to try it.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
