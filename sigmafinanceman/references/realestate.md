# Real estate

A home is two things at once: a place to live (the rent you stop paying) and a leveraged bet on one local price. `finman.py property home.json` runs both views: rent vs buy for an owner, and the rental numbers for an investor. The input format: [assets/property-example.json](../assets/property-example.json). The mortgage rate defaults to the Freddie Mac 30-year fixed (FRED `MORTGAGE30US`); set the user's own offer with `--set mortgage_rate=0.055`.

## Mortgage maths

Payment = loan x r / (1 - (1 + r)^-n), with r the monthly rate and n the months. The schedule splits each year into interest and principal; early payments are mostly interest. Total interest over the loan is often as large as the loan.

## Rent vs buy

Both sides spend the same each year; the cheaper side invests the difference at `invest_return`.

- **Owner.** Pays the down payment, buying costs (`closing_buy_pct`), the mortgage, property tax (`tax_pct`), insurance, upkeep (`upkeep_pct`, 1 % of the price a year is a common rule) and fees (`hoa_monthly`). Owns the home, which grows at `appreciation`, less the selling costs (`closing_sell_pct`) and the loan left.
- **Renter.** Pays rent growing at `rent_growth` and invests the down payment and the buying costs.
- **Result.** Owner's wealth minus renter's at the horizon, and the first year buying wins.

The answer swings on three inputs: price growth, the mortgage rate and the return the renter earns. The grid crosses the first two; bear and bull move price growth by -3 and +2 points.

## As a rental

| Measure | Formula | Read it as |
|---|---|---|
| Net operating income (NOI) | rent x 12 x (1 - vacancy - management) - tax - insurance - upkeep - fees | before the mortgage |
| Cap rate | NOI / price | the unlevered yield; compare with the mortgage rate and the 10-year |
| Cash-on-cash | (NOI - yearly mortgage) / (down payment + buying costs) | the cash return on your own money |
| Debt service cover | NOI / yearly mortgage | lenders want 1.25x+ |
| The 1 % rule | monthly rent / price | a screen only: it ignores every cost and the rate |
| Price / yearly rent | price / (rent x 12) | years of gross rent to pay the price |
| IRR | down payment and costs out; yearly cash flow; sale less the loan at the end | the full return on the cash put in |

A cap rate below the mortgage rate means the debt costs more than the building earns: the deal works only if prices rise.

## All-in costs to count

Buying costs (transfer tax, notary, agent: 2-10 % by country), selling costs (agent and fees: 5-7 %), property tax, insurance, upkeep (1-2 % a year; more for old buildings), owners' association fees, vacancy (5-8 %), management (8-10 % of rent), and capital items (roof, heating) as a reserve.

## Free data

FRED: `MORTGAGE30US` (30-year fixed), `MORTGAGE15US`, `CSUSHPINSA` (Case-Shiller US home prices), `CUSR0000SEHA` (US rent of primary residence, CPI). Local rents and prices: listing sites (asking prices; discount them), land-registry sold prices where public (UK Land Registry, many EU registries). Tax rates: the local authority.

## Traps

- Counting rent and ignoring costs; using the 1 % rule as a verdict.
- A floating rate priced as if it stays.
- No reserve for empty months and repairs.
- Comparing a mortgage payment with rent without the down payment's lost return.
- Assuming the past price growth of one hot area continues.

## Playbook

Check: location, the tenant market, the condition, the rules (rent control, tax, costs), and the exit. Numbers: net operating income divided by price (cap rate), cash-on-cash return, debt service cover, repairs and vacancy reserves, tax and fees both ways, and the IRR with a sale at the end. Size: one property is a large, illiquid bet; hold a cash reserve for repairs and empty months. Funding: a fixed rate and a payment that survives a year of no rent. Sell: the thesis broke, a better use of the equity exists, or the area changes. Mistakes: counting rent and ignoring costs, a floating rate, no reserve, and buying with emotion.
