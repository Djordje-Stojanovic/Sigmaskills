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
- **Risk**: volatility a year (log returns of back-to-back months x √12; missing months are counted and shown), the worst real fall from a peak, and the longest stretch below a real peak in calendar months.
- **Hold ranges** (bear, base, bull): the 10th percentile, median and 90th percentile real return a year over every window of `--set horizon=10` years (5 when the history is under 15 years), each window net of costs: (1 + gross) x (1 - carry) x (1 - spread)^(1/horizon) - 1, and the share that made money counted on that. Windows overlap: the report says how many separate holds fit back to back (20 years hold two 10-year holds). With no complete window it gives the full-period return under its own label. This is history, not a forecast.
- **Carry**: `--set carry=0.004` a year for storage and insurance of metal (0 by default for an ETF ticker: its price is already after the fee); `--set spread=0.02` for the round-trip cost of buying and selling (coins and bars carry 2-8 %; an ETF under 0.1 %).
- **A ratio** with `--peers`: now, the median, the range and the percentile of today.

## Ratios people use

- **Gold/silver.** Ounces of silver one ounce of gold buys. The long history runs from about 30 to above 100. A high ratio says silver is cheap against gold, not that either is cheap; it can stay stretched for years.
- **Gold against real yields.** Gold tends to fall when the real 10-year yield (FRED `DFII10`) rises: holding gold costs the yield you give up.
- **Oil/gold, copper/gold.** Gauges of growth against fear; signals for a macro view, not values.

## What this can and cannot tell you

It can tell you the range a holder lived through and what each hold length returned. It cannot tell you a fair value, a future return or a "cheap" price. A futures ticker (`GC=F`) is the front contract's quote: its change is not what a holder earned after rolling contracts (contango and backwardation) and holding collateral, so a fund can lag it for years. For a holder's return, run the fund's own ticker. Crypto has 10-15 years of history: one cycle of hold windows, so the bull case rests on a very young sample.

## How much history supports the range

**Name what the series measures** in one line: a spot price, one futures contract, a rolling futures strategy, an ETF share after its fee, or a total-return index. A continuous futures chart (`GC=F`, `CL=F`) jumps when the vendor switches contracts; nobody earned that jump. For a futures holding, use the index provider's excess-return or total-return series (total return = excess return + interest on Treasury bills; [S&P commodity index mathematics](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-commodity-index-math.pdf)) or rebuild the contracts held, the roll dates and the interest on the collateral. For an ETF, use the share the user can buy and add only the costs its price has not already paid.

**Check the dates first.** State the first and last month, the months expected, the months present, and the longest gap. Real returns run only to the last month with both a price and a CPI print. A price that can fall below zero (the May 2020 WTI future settled at -$37.63 on 20 April 2020, [CFTC](https://www.cftc.gov/PressRoom/PressReleases/8315-20)) has no log return there: use the change in money on the position.

**Count the independent periods.** Twenty years of monthly prices give 121 overlapping ten-year windows, but only two that do not overlap; two neighbouring windows share 119 of their 120 months. So "positive in 90 % of windows" is a share of starting months, not the odds for a buyer today. Beside the percentiles, give the worst month to have bought and to have sold, and what that holder got.

**Count costs before winners.** Example, all assumed: a 2 % round-trip spread and a 0.4 % yearly fee turn a real ten-year multiple of 1.05 into 1.05 x 0.98 x 0.996^10 = 0.99. The holder beat inflation before costs and lost to it after. For metal already owned, the cash a sale brings today is the starting value.

**A hedge is tested against what it hedges.** Name the loss it should offset and test both in the same months: the change in the user's combined holdings in that loss window, and the cash on hand to meet the bill. A metal that rose over twenty years can still have fallen in the month the cash was needed.

## Gold and commodities

Hold for a reason the model can name: a hedge against a falling currency or a crisis, a small part of a portfolio (5-10 % is a common range). Physical metal: buy from a dealer that buys back, at a spread you know, and insure the storage. Funds: check that the fund holds metal (allocated) and the fee. Commodity futures funds: read the roll cost.

## Crypto

Custody is part of the investment: an exchange that fails takes the coins (FTX, 2022). Self-custody moves the risk to you: a lost key is a lost coin. Count fees and tax on every swap. Volatility above 60 % a year means a fall of three-quarters is normal, not a tail.

Tokens other than bitcoin need three more checks:

- **Supply.** Market value = price x tokens in circulation; fully diluted value = price x every token that will exist. When the second is several times the first, locked tokens (team, investors, treasury) reach the market on a schedule: find the unlock dates before you buy.
- **Yield.** A staking yield paid in new tokens is mostly dilution. Real yield = (1 + staking yield) / (1 + supply growth) - 1: 5 % paid while supply grows 6 % is about -1 %.
- **Cash flows.** If the protocol earns fees that are burned or paid to holders, the token has a cash flow and this file no longer fits: value the fees like owner earnings (stocks.md) and say how much of them reach the holder.

**In the holder's currency.** `finman.py asset GC=F --peers EURUSD=X` adds a ratio table that is the gold price in euros (Yahoo `EURUSD=X` is dollars per euro): now, median, range and percentile. Every return on the page stays in US dollars and US CPI; say so.

## Traps

- Calling a price "cheap" because it fell: nothing anchors it.
- Ignoring the spread on coins and bars, and storage costs.
- Comparing nominal gold returns with real stock returns.
- Leverage on an asset that can fall 50-80 %.

## Playbook

Check: what gives it value (use, scarcity, a network), who holds it, how you hold it, and what you can lose entirely. Numbers: it has no cash flow, so no DCF. Use size, a stop, and the real cost of custody and fees. Treat it as a power-law bet with a capped loss (Altman P3: lose 1x if wrong, win 100x if right; Thiel P1). Size: an amount you can lose completely. Sell: write the exit plan first: the price, the date or the fact that sells it. Mistakes: borrowing to buy, trusting an exchange with your whole stake, buying because the price rose, and no plan to take profit.
