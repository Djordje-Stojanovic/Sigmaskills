# Bonds and funds

## Bonds

A bond is a loan with fixed payments, so its maths is exact; the risks are rates, default and inflation. `finman.py bond bond.json` ([assets/bond-example.json](../assets/bond-example.json)) takes the coupon, the years left, the price (or the yield) and the payments a year.

- **Yield to maturity**: the one rate that makes the payments worth the price. It assumes every payment arrives and is reinvested at the same rate.
- **Current yield** = coupon / price.
- **Spread** = the yield - the Treasury of the nearest maturity (FRED `DGS1` to `DGS30`, fetched when `treasury` is left out). The spread pays for default risk and lower liquidity.
- **Duration**: Macaulay (the weighted average time of the payments) and modified (the price change for a 1-point move in yield, in %). **Convexity** corrects for large moves.
- Rate shocks of ±1 and ±2 points; bear, base and bull = the one-year total return if yields rise a point, stay, or fall a point.

Credit: look up the rating (S&P, Moody's, Fitch) and the issuer's interest cover with `finman.py ratios TICKER`. A spread far above other bonds of the same rating is the market's warning. Inflation: compare with TIPS (FRED `DFII10`) for the real yield. Callable bonds cap the gain when rates fall.

## Funds and ETFs

A fund's job is to deliver its index at the lowest cost. `finman.py fund TICKER --peers BENCHMARK --set fee=0.0003` compares total returns (Yahoo adjusted closes, dividends reinvested):

- **Tracking difference** = fund return - benchmark return a year. It is the real cost of owning the fund: fee, cash drag, trading and dividend tax. Use a total-return benchmark (`^SP500TR`, not `^GSPC`).
- **Tracking error** = the standard deviation of the monthly gap, a year. Low means the fund does what it says.
- **Fee drag**: what the fee costs on 10,000 over 10, 20 and 30 years at the benchmark's return. Yahoo's chart data has no expense ratio: take it from the fund's fact sheet.

Check what the fund holds (the top 10 and the sector mix on the issuer's page), whether it holds the assets or swaps for them, its size and trading volume (spread), and the tax on its dividends in the user's country. A second fund that holds the same index adds cost, not diversification.

## Traps

- Buying a long bond for safety: a 20-year bond loses 12-15 % of its price when yields rise one point (its duration).
- Reaching for yield into junk ratings without the spread to pay for the defaults.
- Comparing a fund's price return with an index's total return.
- Thematic ETFs sold as diversified.

## Playbook

Check: low cost, wide, and simple (Buffett, 2013). Numbers: cost ratio, tracking gap, tax treatment, the mix of the fund (stocks and bonds), and your horizon. Size: the core of the plan for anyone with no edge. Buy on a schedule and in parts; never time the entry. Sell: only to meet the plan's goal, to rebalance, or to pay for a need. Mistakes: selling in a crash, adding a second fund that holds the same thing, paying for a fund that charges more than the index, and treating a thematic ETF as a diversified one.
