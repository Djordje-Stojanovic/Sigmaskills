# Methods, inputs and defaults

Money is in millions of the filing currency, shares in millions. `scripts/fin_models.py` holds the maths; `scripts/fin_xlsx.py` writes the same maths as formulas. Override an input with `--set name=value` (fractions for percentages).

## Inputs (DCF; the other models reuse them)

| Name | Default | Source |
|---|---|---|
| `revenue_base` | last fiscal-year revenue | 10-K |
| `growth_y1` | 3-year revenue CAGR, held 0-25 % | 10-K series |
| `ebit_margin` | average EBIT margin of the last 3 years | 10-K |
| `tax_rate` | income tax / pre-tax income, held 10-30 % | 10-K |
| `da_pct` | D&A / revenue | cash-flow statement |
| `capex_pct_y0` | capex / revenue, last year | cash-flow statement |
| `nwc_pct` | (receivables + inventory - payables) / revenue | balance sheet |
| `rf` | US 10-year Treasury | FRED DGS10 |
| `beta` | 5-year monthly beta vs the S&P 500, held 0.6-2.0 | Yahoo chart data |
| `erp` | 5.0 % | market standard |
| `kd` | interest expense / debt, held between rf and rf + 4 % | 10-K |
| `debt`, `cash` | current + non-current debt + commercial paper; cash + short-term investments | balance sheet |
| `shares` | diluted weighted shares | 10-K |
| `price` | last price | Yahoo chart data |
| `terminal_g` | 2.5 %, never above rf | convention |
| `years` | 5 | convention |

## DCF

- Growth fades in a straight line from `growth_y1` toward `terminal_g`: year i grows `g1 - (g1 - gT) x (i - 1) / N`.
- Capex fades from its last share of revenue to the D&A share by the last year (steady state: the asset base grows with revenue, not ahead of it).
- Unlevered FCF = EBIT x (1 - tax) + D&A - capex - nwc_pct x change in revenue.
- WACC = (E x (rf + beta x ERP) + D x kd x (1 - tax)) / (E + D), with E = price x shares at market value.
- Mid-year discounting: periods 0.5 ... N - 0.5. Terminal value = FCF_N x (1 + g) / (WACC - g), discounted at period N - 0.5 (anthropics/financial-services `dcf-model`).
- Equity = EV - debt + cash. Value per share = equity / diluted shares.
- Grid: WACC +/- 0.5 and 1.0 points (rows) by terminal growth +/- 0.5 and 1.0 points (columns); each cell is a full DCF formula (SUMPRODUCT over the cash-flow row), so the centre equals the model.

## LBO

- EBITDA, normalized = last revenue x the 3-year average EBIT margin + D&A, so one impairment year does not set the price.
- Entry EV = price x (1 + 25 % premium) x shares + debt - cash; entry multiple = entry EV / EBITDA. Senior debt 5.0x EBITDA at rf + 3.5 %; fees 2 % of EV; 100 % cash sweep; exit multiple = entry multiple; 5-year hold.
- Interest on the opening debt (no circular reference). Tax on EBIT - interest, never below zero. Debt repaid = MIN(opening debt, free cash flow x sweep).
- MOIC = exit equity / sponsor equity; IRR = MOIC ^ (1 / years) - 1 (no interim dividends). Grid: entry multiple x exit multiple, +/- 1x and 2x.

## Comps

- LTM = the last fiscal year + the newer year-to-date - the year-ago year-to-date (10-Q), per flow line.
- EV = market cap + debt - cash; market cap uses the cover-page share count.
- Multiples: EV/Revenue, EV/EBITDA, EV/EBIT, P/E (a negative denominator shows `n/a`). Statistics are Excel `QUARTILE.INC`, `MEDIAN`, `MIN`, `MAX` over the peers only.
- Implied value per share = (peer multiple x target metric - debt + cash) / shares; P/E: multiple x net income / shares. The football field shows the 52-week range, the 25th-75th band per multiple and the DCF inner 3 x 3 range, with the price as a marker.

## Three-statement model

- Three filed years plus N projected. Revenue as in the DCF; cost of revenue and operating costs as shares of revenue; interest on the opening debt; tax on EBIT - interest; payouts (dividends + buybacks) = payout x net income, the payout being last year's (dividends + buybacks) / net income.
- Receivables, inventory and payables from days (DSO on revenue, DIO and DPO on cost of revenue).
- Cash is the plug: opening cash + operating cash flow - capex - payouts. PP&E rolls forward with capex - D&A; equity with net income - payouts. Debt and the "other" lines (filed totals the model does not split) stay flat.
- The balance check row (assets - liabilities - equity) must be 0 in every year.

## Ratios, statement analysis, red flags

- Ratios: margins, ROE, ROA, ROIC (EBIT x (1 - tax) / (equity + debt - cash)), current and quick ratio, debt/equity, debt/EBITDA, interest cover, asset turnover, receivable/inventory/payable days, FCF, FCF margin, cash conversion (FCF / net income), EPS, payout, stock pay / revenue.
- Common-size: income lines / revenue; balance-sheet lines / total assets. Growth: year on year.
- Red flags (latest year vs the year before): receivables grow 10+ points faster than revenue; inventory does too (only when inventory is above 2 % of revenue); Sloan accruals (net income - CFO) / assets above 10 %; gross margin down 3+ points; stock pay above 10 % of revenue; debt up 25 %+ while revenue grows under 5 %; CFO under 80 % of net income. A flag is a question for the 10-K notes, not a verdict.
- Altman Z (public form): 1.2 x working capital/TA + 1.4 x retained earnings/TA + 3.3 x EBIT/TA + 0.6 x market cap/liabilities + 1.0 x sales/TA. Above 2.99 safe, 1.81-2.99 grey, below distress.
- Piotroski F: nine binary signals (profit, cash flow, ROA up, cash above profit, leverage down, liquidity up, no new shares, gross margin up, asset turnover up).

## Value-investing scorecard

Ten pass/fail tests: average ROE 15 %+; ROIC 12 %+; gross margin 40 %+; net margin 10 %+; revenue CAGR 5 %+; EPS up in 60 %+ of years; debt/EBITDA 2.0x or less; FCF positive every year; owner-earnings yield (net income + D&A - capex over market cap) above the 10-year; price at most 75 % of the base-case DCF value (a 25 % margin of safety).

## Earnings review

The last quarters from the 10-Q filings; a fiscal Q4 is the 10-K year minus the three quarters before it (EPS so derived can differ by a cent). Year on year compares with the quarter four back; quarter on quarter with the one before. Free sources carry no consensus estimates: the review compares against the company's own past and says so.

## Budget

The 50/30/20 rule (needs, wants, savings) as the yardstick; left over = net pay - needs - wants - savings and counts as savings in the 12-month path; the emergency fund in months of needs.

## Sanity checks (say them in the reply)

| Signal | Why |
|---|---|
| Terminal value above 75 % of EV | the answer leans on the terminal year: show the grid |
| WACC under the risk-free rate, or within 1 point of terminal growth | the discounting is broken or the value explodes |
| Value per share more than 50 % off the price | name the input that drives it (often capex or growth) |
| IRR above 40 % or under 5 % | check the entry multiple and the leverage |
| Negative EBITDA or net income in comps | the multiple is `n/a`; use EV/Revenue |
| Balance check not 0, or a Checks line FALSE | the model is wrong: fix before reporting |
