# Public stocks

The deepest class. A share is a slice of a business, so its value is the cash the business will hand its owners. Every formula, input and default of the company models: [methods.md](methods.md).

## The commands

| The user wants | Command | Main output |
|---|---|---|
| What is it worth (intrinsic) | `finman.py dcf TICKER` | value per share, bear/base/bull, what the price implies (reverse DCF), WACC x growth grid, the method in 10 steps |
| Is the dividend worth it, and safe | `finman.py dividend TICKER` | dividend discount value, safety tests, owner earnings, capital return, quality, margin of safety |
| Cheap or dear against peers | `finman.py comps TICKER --peers A,B,C` | multiples table, quartiles, football field |
| Could a buyout work | `finman.py lbo TICKER` | IRR and money multiple, entry x exit grid |
| The full model | `finman.py three TICKER` | income statement, balance sheet, cash flow, 5 years out |
| Health over time | `finman.py ratios TICKER` | 22 ratios over 5 fiscal years |
| Anything wrong in the books | `finman.py analyze TICKER` | red flags, common-size, Altman Z, Piotroski F |
| Would Buffett buy it | `finman.py score TICKER` | 10 pass/fail tests |
| How was the quarter | `finman.py earnings TICKER` | latest quarter vs a year ago and the prior quarter |
| Everything | `finman.py all TICKER --peers A,B,C` | all of the above; the dividend model only when the last 10-K shows a dividend |

Peers for comps: 4 to 8 companies with the same business model and a similar size; say why each one is in. Route to the Financial Services pack (`dcf-model`, `comps-analysis`, `3-statement-model`) when the user brings their own model template or a paid data feed (FactSet, S&P, Daloopa); this skill owns the run from free public data.

## Pick the lens

| The business | Lead with | Then |
|---|---|---|
| Grows, reinvests most cash | `dcf` and its reverse DCF | `comps`, `score` |
| Mature, pays out most cash | `dividend` (DDM, safety, owner earnings) | `dcf` as the cross-check |
| Loses money today | reverse DCF on margin and growth; EV/Revenue in `comps` | runway from the 10-Q cash and the burn |
| Cyclical (steel, chips, shipping) | mid-cycle margins: `--set ebit_margin=` the 10-year average, not the last year | `analyze` for the balance sheet |
| Bank or insurer | price / book and return on equity; a DCF of a lender's free cash flow means nothing | `ratios` |
| Asset-heavy and indebted, a buyout target | `lbo` | `three` |

## Dividend discount model

Value = every future dividend, discounted at the cost of equity. Two stages: the dividend grows `g1` a year for 5 years, then `g2` for ever.

`V = sum over t = 1..5 of D0 (1 + g1)^t / (1 + ke)^t + D5 (1 + g2) / (ke - g2) / (1 + ke)^5`

| Input | Default | Source |
|---|---|---|
| `dps_ttm` (D0) | dividends paid in the last 12 months | Yahoo chart dividend events |
| `g1` | 5-year dividend-per-share CAGR, held 0-10 % | the same events, complete calendar years |
| `g2` | 2.5 %, never above the risk-free rate | convention |
| `ke` | rf + beta x 5 % (CAPM) | FRED DGS10, Yahoo beta |

Bear and bull move `g1` by 3 points. The grid crosses `ke` with `g2`. The reverse model finds the `g1` that gives the price, and the one-stage Gordon form gives `g = (ke x P - D0) / (P + D0)`, from P = D0 (1 + g) / (ke - g): the growth for ever that the price assumes. Override with `--set g1=0.06 --set ke=0.08`.

The DDM undervalues a company that returns cash through buybacks: read it beside shareholder yield and the DCF.

## Dividend safety

Seven pass/fail tests on the last 10-K. Six or more pass: the dividend looks safe. Four or five: it needs watching. Fewer: it looks at risk.

1. Dividends under 75 % of free cash flow (CFO - capex): the cash test, the one that matters most.
2. Dividends under 75 % of net income.
3. Free cash flow covers the dividend 1.3 times.
4. Net debt / EBITDA 3.0x or less.
5. EBIT covers interest 5 times.
6. No cut in 10 years (1 % slack for rounding). The history read is 20 years, so a longer streak shows as "19+".
7. Revenue not shrinking over 3 years.

A one-year failure of test 1 can be a one-off (a tax deposit, an acquisition paid in cash): read the cash-flow statement before calling a cut.

## Owner earnings

Buffett's measure (1986 letter): net income + D&A and other non-cash charges - the capex needed to hold the business where it is. The 10-K does not split maintenance from growth capex, so the model takes the smaller of capex and D&A as maintenance and also shows the strict line with all capex. Owner-earnings yield = owner earnings / market value; compare with the 10-year yield.

## Capital return and buybacks

Per fiscal year: dividends, buybacks, stock pay, diluted shares, and the change in the share count.

- Shareholder yield = (dividends + buybacks) / market value.
- A buyback works only when the share count falls. Buybacks that match stock pay just stop dilution: count the shares, not the dollars.
- A buyback above intrinsic value destroys value for the owners who stay. Set the average price paid (buybacks / shares retired, from the 10-K equity note) against the DCF.
- Debt-funded buybacks raise the risk the safety tests catch.

## Quality and moat

Six tests from the filings: ROIC above the WACC on a 5-year average (the spread is the moat in numbers); gross margin steady (standard deviation under 3 points) and 40 %+ (pricing power); free cash flow at least 80 % of net income; a falling share count; stock pay under 5 % of revenue. Then name the moat in words: network effect, switching cost, scale cost advantage, brand, licence or patent. A moat the numbers do not show is a story.

## Margin of safety

Margin of safety = 1 - price / value. Want 25 % or more (Buffett P1). The dividend page shows it on the DDM and on the DCF. A negative margin means the price is above the value; say by how much ("the price is 2.4x this value").

## Special cases

- **Banks.** Debt is their raw material, so EV and a free-cash-flow DCF mean nothing. Value = book value x (ROE - g) / (ke - g): a bank earning its cost of equity is worth book. Check the loan losses, the deposit mix and the capital ratio (CET1) in the 10-K.
- **Insurers.** Price / book against ROE as for banks; add the combined ratio (claims and costs over premiums; under 100 % is an underwriting profit) and the float the premiums give to invest.
- **REITs.** Net income is depressed by property depreciation: use funds from operations (FFO = net income + real-estate depreciation - gains on sales) and AFFO (FFO - maintenance capex). Price / AFFO and the AFFO payout replace P/E and the earnings payout.
- **Conglomerates and holding companies.** Sum of the parts: value each segment (10-K segment note) with its own peers' multiple, add the net cash and listed stakes at market, and subtract a holding discount of 10-30 % if management takes a cost or allocates poorly.
- **Early, loss-making growth.** Reverse DCF on the margin it must reach; the rule of 40 (revenue growth + free-cash-flow margin, 40 %+ is strong) and net revenue retention for software; dilution from stock pay counted as a cost.

## The full equity bridge

The models subtract debt and minority interest and add cash. Read the 10-K notes for the rest before trusting a value per share: lease liabilities (when the EBITDA is before lease costs), unfunded pensions, preferred stock, equity stakes in other companies (add at market), and options and convertibles in the money (the diluted share count covers most of them).

## Free data and its limits

SEC EDGAR company facts cover US filers only; a foreign filer without XBRL facts has none. Yahoo dividends are cash amounts per share, adjusted for splits. Neither source has analyst estimates or the dividend tax of the user's country.

## Traps

- A yield far above the company's own history: the market expects a cut.
- Payout above 100 % of free cash flow for two years.
- Growth bought with acquisitions that the margins never show.
- Adjusted EBITDA that adds back stock pay: it is a real cost.
- Using last year's peak margin for a cyclical company.

## Playbook

**Growth stocks.** Check: durable growth, high return on new capital, a moat, a founder or manager who allocates well (Bezos P1, Huang P3). Numbers: revenue growth, gross margin, free cash flow margin, return on invested capital, share count, and a reverse DCF that shows the growth the price needs. Size: small to medium; the bad case is a halving or worse. Sell: the growth driver slows, the reverse test shows the price needs more than your bull case, or a better idea needs the money. Mistakes: paying for a story at any price, ignoring dilution from stock pay, and confusing a falling price with a falling business.

**Dividend stocks.** Check: the dividend is covered by free cash flow, not by earnings alone; debt is modest; the business holds its position. Numbers: payout of free cash flow, interest cover, dividend growth over ten years, total return, and tax on the payout. Size: part of an income plan, never the whole. Sell: a cut is likely (payout above free cash flow, falling revenue), or the yield is high only because the price fell. Mistakes: chasing yield into a failing firm, ignoring that a dividend leaves the company and the tax follows it, and holding one sector.
