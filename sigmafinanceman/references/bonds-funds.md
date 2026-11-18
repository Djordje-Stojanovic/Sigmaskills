# Bonds and funds

## Bonds

A bond is a loan with fixed payments, so its maths is exact; the risks are rates, default and inflation. `finman.py bond bond.json` ([assets/bond-example.json](../assets/bond-example.json)) takes the coupon, the years left, the price (or the yield) and the payments a year.

- **Yield to maturity**: the one rate that makes the payments worth the price. It assumes every payment arrives and is reinvested at the same rate.
- **Current yield** = coupon / price.
- **Spread** = the yield - the Treasury of the nearest maturity (FRED `DGS1` to `DGS30`, fetched when `treasury` is left out). The spread pays for default risk and lower liquidity.
- **Duration**: Macaulay (the weighted average time of the payments) and modified (the price change for a 1-point move in yield, in %). **Convexity** corrects for large moves.
- Rate shocks of ±1 and ±2 points; bear, base and bull = the one-year total return if yields rise a point, stay, or fall a point.

Credit: look up the rating (S&P, Moody's, Fitch) and the issuer's interest cover with `finman.py ratios TICKER`. A spread far above other bonds of the same rating is the market's warning. Inflation: compare with TIPS (FRED `DFII10`) for the real yield. Callable bonds cap the gain when rates fall.

### The bond the user can buy, and what it is likely to pay

**The quote.** Read the prospectus for the identifier, currency, coupon dates, maturity, day count and call rights. Take a dated offer to buy and a dated bid to sell, with the size quoted: yesterday's trade in a large block says little about a small order. US corporate bonds: the TRACE trade history in [FINRA's fixed-income data](https://www.finra.org/finra-data/fixed-income).

**Clean and dirty.** A quote is the clean price, without accrued interest. The buyer pays the dirty price: clean plus the interest accrued since the last coupon, plus commission. Example, terms assumed: 1,000 face, 6 % a year paid twice a year, clean price 98, bought halfway through a coupon period. The buyer pays 980 + 15 = 995 and collects the next full coupon of 30. A model that pays 980 and collects 30 hands the buyer 15 that was the seller's. `bond` takes the clean price per 100 and a whole number of coupon periods: between coupon dates, expect its yield to be off by a few hundredths of a point. A yield of 6 % compounded twice a year is 6.09 % effective a year: say which one you quote.

**Calls.** Compute the yield to each call date and quote the lowest (yield to worst). The yield to a call is the y that solves price = sum of coupon / (1 + y)^t + call price / (1 + y)^n, with n the periods to the call. `bond` with `years` set to the time to the call does this, but it repays at face, so a call price above par reads low: solve that one by hand. Example, assumed: pay 105 for a 6 % annual coupon, called at 100 in a year. The return is 106 / 105 - 1 = 0.95 % (`bond` gives the same with `"years": 1, "freq": 1`). The current yield of 5.71 % leaves out the 5 of principal lost at the call. A make-whole call pays the larger of par and the remaining payments discounted at the Treasury yield plus the spread the prospectus names.

**Default.** Expected return = yield - default rate a year x (1 - recovery). Senior unsecured bonds recovered a mean of 44.9 per 100 of face in default, 1982-2004 ([Moody's, Default and Recovery Rates of Corporate Bond Issuers, 1920-2004](https://www.bu.edu/econ/files/2015/01/Moodys_Default_1920-2004.pdf), Exhibit 27); take the default rate for the rating from Moody's or S&P's newest annual default study. Example, default rate assumed: 4 % a year at 45 % recovery costs 4 x 0.55 = 2.2 points of yield a year, so a spread below that pays nothing for the risk. Live spreads: FRED `BAMLH0A0HYM2` (high yield) and `BAMLC0A0CM` (investment grade). For one bond, pick a default date, stop the coupons there, and put the recovery on the date it is likely to arrive. Rank matters: a holding-company bond can recover less than a subsidiary bond backed by the operating assets. Example, assumed: bought at 90, default with 40 recovered and no coupon in between loses 50, or 55.6 % of the price paid.

**Inflation.** The 10-year Treasury yield less the TIPS yield (FRED `T10YIE`) is the inflation the market expects. A nominal bond beats the TIPS only if inflation comes in under it.

**A bond fund never matures.** It replaces the bonds that mature, so a 5-year duration is a price sensitivity, not a date when the money comes back at par. Check the prospectus for a target maturity before you compare the fund with one bond held to the end.

## Funds and ETFs

A fund's job is to deliver its index at the lowest cost. `finman.py fund TICKER --peers BENCHMARK --set fee=0.0003` compares total returns (Yahoo adjusted closes, dividends reinvested):

- **Tracking difference** = fund return - benchmark return a year. It is the real cost of owning the fund: fee, cash drag, trading and dividend tax. Use a total-return benchmark (`^SP500TR`, not `^GSPC`).
- **Tracking error** = the standard deviation of the monthly gap, a year. Low means the fund does what it says.
- **Fee drag**: what the fee costs on 10,000 over 10, 20 and 30 years at the benchmark's return. Yahoo's chart data has no expense ratio: take it from the fund's fact sheet.

Check what the fund holds (the top 10 and the sector mix on the issuer's page), whether it holds the assets or swaps for them, its size and trading volume (spread), and the tax on its dividends in the user's country. A second fund that holds the same index adds cost, not diversification.

## What an index can return

The index fund is the default for anyone with no edge (strategy.md step 1), so every other asset is judged against it. Its last 10 years are not the forecast. Build the return from its parts:

Return a year = dividend yield + net buyback yield + growth of earnings + the change in the price paid per unit of earnings.

- Dividend and buyback yield: the fund's fact sheet and the index provider.
- Growth of earnings: over long spans, tie it to the growth of the economy in money terms (real growth plus inflation); a faster number needs a reason.
- The change in valuation is the part nobody can forecast. Take zero in the base case. In the bear case the earnings multiple falls back toward its long-run average: from 30x to 20x over 10 years costs (20 / 30)^(1/10) - 1 = -4.0 % a year.

Set the earnings yield (earnings / price) beside the real 10-year yield (FRED `DFII10`): the gap is what shares pay for their risk. The cyclically adjusted P/E (price over 10 years of average real earnings, on [Robert Shiller's data page](http://www.econ.yale.edu/~shiller/data.htm)) shows how much the price already assumes; it says little about the next year.

## Where the holder lives

- The US taxes most US income paid to foreign persons at 30 %, less where a tax treaty with the holder's country sets a lower rate ([IRS, NRA withholding](https://www.irs.gov/individuals/international-taxpayers/nra-withholding)). A fund domiciled elsewhere pays its own treaty rate inside the fund. Ask the holder's country and read both.
- An EU broker may not sell a packaged product to a retail client without a key information document (PRIIPs Regulation (EU) No 1286/2014), and most US-domiciled ETFs publish none. Value the UCITS fund the user can buy, against the net-return index its fact sheet names.
- An accumulating fund reinvests the dividends; a distributing one pays them out. The tax can differ by country; the return before tax does not.
- Returns are in the fund's currency. Convert to the holder's currency before you compare (strategy.md, "One cash-flow sheet, one yardstick").

## Traps

- Buying a long bond for safety: a 20-year bond loses 12-15 % of its price when yields rise one point (its duration).
- Reaching for yield into junk ratings without the spread to pay for the defaults.
- Comparing a fund's price return with an index's total return.
- Thematic ETFs sold as diversified.

## Playbook

Check: low cost, wide, and simple (Buffett, 2013). Numbers: cost ratio, tracking gap, tax treatment, the mix of the fund (stocks and bonds), and your horizon. Size: the core of the plan for anyone with no edge. Buy on a schedule and in parts; never time the entry. Sell: only to meet the plan's goal, to rebalance, or to pay for a need. Mistakes: selling in a crash, adding a second fund that holds the same thing, paying for a fund that charges more than the index, and treating a thematic ETF as a diversified one.
