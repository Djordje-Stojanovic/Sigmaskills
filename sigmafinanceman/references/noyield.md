# Gold, commodities and crypto

These pay nothing: no dividend, no rent, no coupon. All the return is the next buyer's price, so there is no DCF and no fair value. Say so in the reply. What history can still tell: how the price moved after inflation, how deep and long the falls were, and what a hold of a given length returned. `finman.py asset TICKER` does it from Yahoo monthly closes and US CPI (FRED `CPIAUCSL`).

| Asset | Ticker | Ratio partner (`--peers`) |
|---|---|---|
| Gold | `GC=F` (futures) or `GLD` (fund) | `SI=F` for gold/silver |
| Silver | `SI=F` | |
| Oil | `CL=F` (WTI), `BZ=F` (Brent) | |
| Copper | `HG=F` | `GC=F` for copper/gold, a growth gauge |
| Bitcoin, ether | `BTC-USD`, `ETH-USD` | `GC=F` for bitcoin priced in ounces of gold |

## What the model computes

- **Nominal and real return** a year over 1, 5, 10 years and the full history. Real = deflated by US CPI to today's dollars. Months are counted by the calendar; Yahoo skips some.
- **Risk**: volatility a year (monthly log returns x √12), the worst real fall from a peak, and the longest stretch below a real peak in months.
- **Hold ranges** (bear, base, bull): the 10th percentile, median and 90th percentile real return a year over every window of `--set horizon=10` years (5 when the history is under 15 years), less carry and spread. This is history, not a forecast.
- **Carry**: `--set carry=0.004` a year for storage and insurance of metal, or a fund's fee; `--set spread=0.02` for the round-trip cost of buying and selling (coins and bars carry 2-8 %; an ETF under 0.1 %).
- **A ratio** with `--peers`: now, the median, the range and the percentile of today.

## Ratios people use

- **Gold/silver.** Ounces of silver one ounce of gold buys. The long history runs from about 30 to above 100. A high ratio says silver is cheap against gold, not that either is cheap; it can stay stretched for years.
- **Gold against real yields.** Gold tends to fall when the real 10-year yield (FRED `DFII10`) rises: holding gold costs the yield you give up.
- **Oil/gold, copper/gold.** Gauges of growth against fear; signals for a macro view, not values.

## What this can and cannot tell you

It can tell you the range a holder lived through and what each hold length returned. It cannot tell you a fair value, a future return or a "cheap" price. A commodity future's price also includes the cost of rolling contracts (contango and backwardation), so a fund can lag the spot price for years. Crypto has 10-15 years of history: one cycle of hold windows, so the bull case rests on a very young sample.

## Gold and commodities

Hold for a reason the model can name: a hedge against a falling currency or a crisis, a small part of a portfolio (5-10 % is a common range). Physical metal: buy from a dealer that buys back, at a spread you know, and insure the storage. Funds: check that the fund holds metal (allocated) and the fee. Commodity futures funds: read the roll cost.

## Crypto

Custody is part of the investment: an exchange that fails takes the coins (FTX, 2022). Self-custody moves the risk to you: a lost key is a lost coin. Count fees and tax on every swap. Volatility above 60 % a year means a fall of three-quarters is normal, not a tail.

## Traps

- Calling a price "cheap" because it fell: nothing anchors it.
- Ignoring the spread on coins and bars, and storage costs.
- Comparing nominal gold returns with real stock returns.
- Leverage on an asset that can fall 50-80 %.

## Playbook

Check: what gives it value (use, scarcity, a network), who holds it, how you hold it, and what you can lose entirely. Numbers: it has no cash flow, so no DCF. Use size, a stop, and the real cost of custody and fees. Treat it as a power-law bet with a capped loss (Altman P3: lose 1x if wrong, win 100x if right; Thiel P1). Size: an amount you can lose completely. Sell: write the exit plan first: the price, the date or the fact that sells it. Mistakes: borrowing to buy, trusting an exchange with your whole stake, buying because the price rose, and no plan to take profit.
