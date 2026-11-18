# Methods, inputs and defaults

Money is in millions of the filing currency, shares in millions. `scripts/fin_models.py` holds the maths; `scripts/fin_xlsx.py` writes the same maths as formulas, one column per projection year. Override an input with `--set name=value` (fractions for percentages); a name the model does not have stops the run and lists the names it has. A value set this way is never fetched, so `--set price= --set beta= --set rf=` runs with Yahoo and FRED down.

## Inputs (DCF; the other models reuse them)

| Name | Default | Source |
|---|---|---|
| `revenue_base` | last fiscal-year revenue | 10-K |
| `growth_y1` | 3-year revenue CAGR, held 0-25 % | 10-K series |
| `ebit_margin` | average EBIT margin of the last 3 years | 10-K |
| `tax_rate` | income tax / pre-tax income, held 10-30 % | 10-K |
| `da_pct` | D&A / revenue; the largest D&A line filed (a part-line can come first) | cash-flow statement |
| `capex_pct_y0` | capex / revenue, last year | cash-flow statement |
| `ppe_pct` | PP&E / revenue: the plant each extra dollar of sales needs | balance sheet |
| `nwc_pct` | (receivables + inventory - trade payables) / revenue; a missing line is named in the source | balance sheet |
| `rf` | US 10-year Treasury | FRED DGS10 |
| `beta` | 5-year monthly beta vs the S&P 500, months matched by date, held 0.6-2.0; 1.0 under 24 months | Yahoo chart data |
| `erp` | 5.0 % | market standard |
| `kd` | interest expense / debt, held between rf and rf + 4 % | 10-K |
| `debt`, `cash` | long-term + current debt + short-term borrowings, each balance once; cash + short-term investments, restricted cash out | newest balance sheet (10-Q or 10-K) |
| `minority`, `preferred`, `investments` | us-gaap MinorityInterest, PreferredStockValue, EquityMethodInvestments (book); 0 when not filed | newest balance sheet |
| `shares` | newest cover-page count x diluted / basic of the last year | 10-Q or 10-K cover |
| `years_to_bs`, `years_to_price` | fiscal year-end to the balance sheet; balance sheet to the price date | dates of the filings and the price |
| `price` | last price | Yahoo chart data |
| `terminal_g` | 2.5 %, never above rf | convention |
| `years` | 5 | convention |

## DCF

- Growth fades in a straight line from `growth_y1` toward `terminal_g`: year i grows `g1 - (g1 - gT) x (i - 1) / N`.
- Capex fades from its last share of revenue to the steady state by the last year: D&A + `ppe_pct` x g / (1 + g), the plant that terminal growth needs.
- Unlevered FCF = EBIT x (1 - tax) + D&A - capex - nwc_pct x change in revenue.
- WACC = (E x (rf + beta x ERP) + D x kd x (1 - tax)) / (E + D), with E = price x shares at market value. WACC must be above g: at or below it the run stops and names the rates, and grid cells read `n/a`.
- Mid-year discounting from the fiscal year-end: periods 0.5 ... N - 0.5. Terminal cash flow = year-N revenue x (1 + g) x EBIT margin x (1 - tax) - g x year-N revenue x (`ppe_pct` + `nwc_pct`); terminal value = that / (WACC - g), discounted at period N - 0.5.
- The valuation date is the price date. EV rolls to the newest balance sheet: EV x (1 + WACC)^s - s x year-1 FCF (that cash is in the balance sheet now). Equity there = EV - debt + cash - minority - preferred + equity-method stakes, then x (1 + ke)^t to the price date. Value per share = equity / today's diluted shares.
- Grid: WACC +/- 0.5 and 1.0 points (rows) by terminal growth +/- 0.5 and 1.0 points (columns); each cell is a full DCF formula (SUMPRODUCT over the cash-flow row), so the centre equals the model.

- Bear, base and bull: year-1 growth -/+ 5 points and EBIT margin -/+ 3 points (`SCENARIO_STEP` in `fin_models.py`); the rest of the model stays. Python only: the workbook holds the base case.
- Reverse DCF (`implied`, `implied_rate`): bisection moves one input (the discount rate, year-1 growth, the EBIT margin, each with the rest held) until the value per share equals the price. Blank when no value in range reaches it. Lead with the rate: the forced fade makes implied growth swing (KO on 2026-11-17: 33.8 % year-1 growth, or a 4.94 % WACC against a 5.12 % Treasury).
- The page's ten steps restate this section with the run's own numbers, in plain words, so a reader without finance training can follow each one.

## LBO

- EBITDA, normalized = last revenue x the 3-year average EBIT margin + D&A, so one impairment year does not set the price.
- Price, shares, premium (25 %), the bridge and EBITDA are read first, `--set` included. Entry EV = price x (1 + premium) x shares + debt - cash + minority; entry multiple = entry EV / EBITDA unless set; exit multiple = entry multiple unless set. Senior debt 5.0x EBITDA at rf + 3.5 %; fees 2 % of EV; 100 % cash sweep; 5-year hold. Sponsor equity = EV x (1 + fees) - debt - minority (the outside owners keep their stake).
- Interest on the opening debt (no circular reference). Tax on EBIT - interest, never below zero. Debt repaid = MIN(opening debt, free cash flow x sweep). A shortfall draws a revolver at the debt rate; cash never goes below zero.
- Exit equity = MAX(0, exit EV - debt + cash - minority). MOIC = exit equity / sponsor equity; IRR = MOIC ^ (1 / years) - 1 (no interim dividends). Grid: entry multiple x exit multiple, +/- 1x and 2x.

## Comps

- LTM = the last fiscal year + the newer year-to-date (Q1 counts) - the year-ago year-to-date (10-Q), per flow line. EPS and share counts are not added or subtracted.
- EV = market cap + debt - cash + minority interest + preferred - equity-method stakes, all from the newest balance sheet; market cap uses today's share count. Consolidated EBITDA counts all of each subsidiary, so the outside owners' claim belongs in EV; the stakes' profit sits outside EBITDA, so they come out.
- Multiples: EV/Revenue, EV/EBITDA, EV/EBIT, P/E (a negative denominator shows `n/a`, and gives no implied value). Statistics are Excel `QUARTILE.INC`, `MEDIAN`, `MIN`, `MAX` over the peers only.
- Implied value per share = (peer multiple x target metric - debt + cash - minority interest) / shares; P/E: multiple x net income / shares. The football field shows the 52-week range, the 25th-75th band per multiple and the DCF inner 3 x 3 range, with the price as a marker.

## Three-statement model

- Three filed years plus N projected. Revenue as in the DCF; cost of revenue and operating costs as shares of revenue; interest on the opening debt; tax on EBIT - interest; payouts (dividends + buybacks) = payout x MAX(net income, 0), the payout being last year's (dividends + buybacks) / net income.
- Receivables, inventory and payables from days (DSO on revenue, DIO and DPO on cost of revenue).
- Cash is the plug: opening cash + operating cash flow - capex - payouts. PP&E rolls forward with capex - D&A; equity with net income - payouts. Debt and the "other" lines (filed totals the model does not split) stay flat.
- The balance check row (assets - liabilities - equity, equity incl. minority interest) must be 0 in every year. In the filed years it tests the filed totals; a missing total liabilities line is liabilities-and-equity minus total equity, never assets minus parent equity.

## Ratios, statement analysis, red flags

- Ratios: margins, ROE, ROA, ROIC (EBIT x (1 - tax) / (equity + debt - cash)), current and quick ratio, debt/equity, debt/EBITDA, interest cover, asset turnover, receivable/inventory/payable days, FCF, FCF margin, cash conversion (FCF / net income), EPS, payout, stock pay / revenue.
- Common-size: income lines / revenue; balance-sheet lines / total assets. Growth: year on year.
- Red flags (latest year vs the year before): receivables grow 10+ points faster than revenue; inventory does too (only when inventory is above 2 % of revenue); Sloan accruals (net income - CFO) / assets above 10 %; gross margin down 3+ points; stock pay above 10 % of revenue; debt up 25 %+ while revenue grows under 5 %; CFO under 80 % of net income. A flag is a question for the 10-K notes, not a verdict.
- Altman Z (public form): 1.2 x working capital/TA + 1.4 x retained earnings/TA + 3.3 x EBIT/TA + 0.6 x market cap/liabilities + 1.0 x sales/TA. Above 2.99 safe, 1.81-2.99 grey, below distress.
- Piotroski F: nine binary signals (profit, cash flow, ROA up, cash above profit, leverage down, liquidity up, no new shares, gross margin up, asset turnover up).

## Value-investing scorecard

Ten pass/fail tests (a missing input or a negative EBITDA or DCF value reads `n/a`, never a pass): average ROE 15 %+; ROIC 12 %+; gross margin 40 %+; net margin 10 %+; revenue CAGR 5 %+; EPS up in 60 %+ of years; debt/EBITDA 2.0x or less; FCF positive every year; owner-earnings yield (net income + D&A - capex over market cap) above the 10-year; price at most 75 % of the base-case DCF value (a 25 % margin of safety).

## Earnings review

The last quarters from the 10-Q filings; a quarter filed only as a year to date is that minus the one before (fiscal Q4 = the year minus nine months). EPS is not derived that way: a quarter without a filed EPS reads `n/a`. Year on year compares with the quarter four back; quarter on quarter with the one before. Free sources carry no consensus estimates: the review compares against the company's own past and says so.

## Budget

The 50/30/20 rule (needs, wants, savings) as the yardstick; left over = net pay - needs - wants - savings. Savings lines leave the account; the left-over, plus or minus, moves the emergency cash in the 12-month path, and the report names the first month it runs out. The emergency fund in months of needs.

## Tie out five numbers before you report

`finman.py fetch TICKER` shows what the model read. Hold each against the 10-K or 10-Q face statements and say in the reply which ones tie:

| Number | Test | When it fails |
|---|---|---|
| Debt | interest / debt between 2 % and 12 %; the face lines add up (KO 10-K: 42,119 + 1,822 + 1,551 = 45,492) | the run stops above 12 %: `--set debt=` |
| Shares | price x shares near the quoted market value | `--set shares=` (millions, diluted) |
| Cash | the "cash and short-term investments" line, restricted cash out | `--set cash=` |
| D&A | between 0.5x and 2x capex for a mature company | `--set da_pct=` from the cash-flow statement |
| Revenue, EBIT | the income statement to the million | name the tag; `--set revenue_base=` |

A company that moved to a new holding company files its history under the old CIK: `--set cik=` (XOM: 34088). Keep every balance on one date and say which: the model uses the newest balance sheet and names it.

## Make the forecast pay for growth

Growth needs capital. In a steady state, growth = reinvestment rate x return on new capital, where reinvestment is the share of after-tax operating profit kept for net capex and working capital. The model charges g x revenue x (PP&E + working capital) / revenue each terminal year. Worked check, all inputs assumed: next year's NOPAT 103, g 3 %, return on new capital 12 %, WACC 8 %. Keeping 3 / 12 = 25 % leaves 77.25 a year: 77.25 / (8 % - 3 %) = 1,545. Paying out all 103 gives 2,060; the extra 515 assumes growth is free. [Damodaran, stable growth](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/stablegrowthrate.htm)

When the return on new capital equals WACC, faster growth adds no value; below it, growth destroys value. Show the value with the spread faded to zero beside the value with a lasting edge. Start the forecast from profit after one-off items, named in the filing's notes; a charge called exceptional three years running is a cost of doing business. Check that cash collection grows with sales: supplier finance and customer prepayments move cash between years without earning it. Count stock pay once, as an operating cost or as future shares, never both.

## Sanity checks (say them in the reply)

| Signal | Why |
|---|---|
| Terminal value above 75 % of EV (under 40 %: the terminal inputs may be too low) | the answer leans on the terminal year: show the grid |
| Implied growth (reverse DCF) far above the filed 3-year growth | the price bets on a speed-up: say what would have to happen |
| WACC under the risk-free rate, or within 1 point of terminal growth | the discounting is broken or the value explodes |
| Value per share more than 50 % off the price | name the input that drives it (often capex or growth) |
| IRR above 40 % or under 5 % | check the entry multiple and the leverage |
| Negative EBITDA or net income in comps | the multiple is `n/a`; use EV/Revenue |
| Balance check not 0, or a Checks line FALSE | the model is wrong: fix before reporting |
