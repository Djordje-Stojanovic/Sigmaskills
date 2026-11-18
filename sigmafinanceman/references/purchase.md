# Purchases and hardware

A purchase is an investment in avoided cost: a GPU saves rented GPU-hours, a car saves taxis and rentals, a machine saves outsourcing. Compare every way to get the same use over the same life. `finman.py purchase item.json` does it. The input format: [assets/purchase-example.json](../assets/purchase-example.json).

## The model

Every option delivers the same use: `uses_per_month` units (GPU-hours, km, machine-hours, `unit` names them) for `life_years`. Monthly cash flows, discounted at `discount_rate` (default: the US 10-year Treasury from FRED; set your own cost of money, for example a loan rate).

| Option | Cost in today's money |
|---|---|
| Buy | price + (running cost per use x uses + fixed monthly cost - income), discounted - resale value at the end, discounted |
| Rent | rent per use x uses, discounted |
| Lease | upfront + (lease payment + running + fixed) for the lease months, then rent for the rest of the life; a lease longer than the life adds the payments still owed, or `termination_fee` |

- **Total cost of ownership** is the buy line: every cost of owning, less what you sell it for.
- **Payback** = months until the monthly saving (rent avoided - running - fixed + any income) repays the price.
- **One cash-flow series** (buy minus rent): -price, the saving each month, the resale at the end. NPV, IRR, payback, break-even and the winner all come from it.
- **NPV of buying** = that series discounted = rent cost - buy cost. Positive: buying wins.
- **IRR of buying** = the yearly return of that series; when no rate or several rates solve it, the report says so and the NPV decides.
- **Break-even use** = the use a month at which buying and renting cost the same. Below it, rent.
- **Depreciation** = declining balance from the price to the resale value: the same share of value lost each year. Hardware loses most in the first years.

Bear: rent prices 30 % lower and half the resale value (a new generation arrives). Bull: rent 20 % higher, resale 30 % higher. The grid crosses use with the rent price.

## Inputs and live data

| Input | Where it comes from |
|---|---|
| `price` | today's street price: a retailer page, with the date. Fetch it; a remembered price is the last resort and is labelled as one. |
| `rent_per_use` | for a GPU, set `gpu` (for example `"RTX 5090"`) and leave this out: the median of live single-GPU offers on vast.ai (public search, no key). Otherwise a rental quote. |
| `running_per_use` | power: watts / 1000 x hours x price per kWh (the utility bill); fuel: litres per km x price |
| `fixed_monthly` | insurance, storage, rack space, servicing |
| `resale_value` | sold listings of the same item at the same age (eBay sold, local marketplaces). Hardware: the last generation's used price today is the best guide. |
| `lease` | the lessor's quote: `monthly`, `months`, `upfront`, and `termination_fee` when early return is allowed |
| `income_monthly` | income only an owner gets (rented out, billed to a client); it lowers the cost of buying and the break-even |

Every input can be a number or `{"value": ..., "source": "..."}`; give the source.

## By kind

- **GPU or AI hardware.** Utilisation decides everything: a GPU idle 20 hours a day costs more than renting. Power is the main running cost (a 575 W card at 0.30 $/kWh costs about 0.17 $ an hour with the rest of the PC). New generations cut both rent prices and resale value: the bear case is the base case for most cards older than one generation.
- **Car.** For personal use it is spending, not an investment; the model still finds the cheapest way to get the kilometres. Insurance, tax, parking and servicing go in `fixed_monthly`; fuel or electricity per km in `running_per_use`. A car loses 15-25 % in the first year.
- **Machine or tool for a business.** Count the hours it will truly run, the operator's time, and the downtime; a lease often includes service. Tax write-offs (depreciation) shift the answer: add them to `income_monthly` when they apply.

## Traps

- Full utilisation assumed: plan the hours you will really use.
- The list price instead of the street price, or a resale value from asking prices.
- Leaving out power, cooling, insurance or your own time.
- Buying at the top of a shortage, when rent prices are about to fall.
- Comparing a 4-year purchase with a 1-year rental quote: the same use over the same life, always.
- Comparing a part with a service: a rented GPU-hour includes the server around the card, the power supply, the network and someone who replaces a failed part. Put the whole machine in `price`, or only the share of a PC you would not own otherwise.
- The default `discount_rate` (the 10-year Treasury) when the purchase goes on a card or a loan: set it to that rate.

A thing that cuts a bill (solar panels, a heat pump, insulation) is a purchase too. `rent_per_use` is the price of the unit you stop buying (the grid price per kWh); `uses_per_month` is the units you really replace, not the units produced, averaged over the life; `resale_value` is zero unless it raises the sale price of the house. Solar output falls about 0.5 % a year (median of about 2,000 measured rates, [Jordan and Kurtz, NREL, 2013](https://docs.nlr.gov/docs/fy12osti/51664.pdf)), so over 20 years the average use is about 95 % of year one. Test a lower grid price as the bear case.

## Playbook

**A business or asset you buy to rent out (for example GPUs).** Check: demand, who pays, what supply is coming, and what replaces the asset. Numbers: monthly revenue = hours in the month × utilisation × price per GPU-hour × (1 − platform fee). Costs: power (kilowatts × hours × price per kilowatt-hour, with cooling), hosting, internet, repairs, financing, tax. Net cash = revenue − costs. Payback = all-in price / net cash per month. Break-even utilisation = fixed monthly cost / (hours × price × (1 − fee)). Depreciation: the resale value falls as new generations arrive and supply grows, so test a lower price per GPU-hour and a lower utilisation. Default (ours): the base case pays back within half the expected useful life, and the stress case still pays back within the full life. Compare with renting the same capacity yourself: if you use it on your own work, its value is the rent you avoid. Size: no more than you can lose if the price per hour halves. Sell: when the price per hour falls under the cost of power and hosting plus a margin, or when the payback case fails. Mistakes: assuming full utilisation, ignoring power and downtime, and buying at the top of a shortage.

**Cars.** Check: for personal use, a car is spending, not an investment: it usually loses value. As a trade or collector buy, check the price against recent sales, the condition and history, and the market for that model. Numbers: buy price + inspection + repairs + registration and tax + insurance + storage + holding days; compare with a realistic sale price after fees. Margin of safety = (sale price − all costs − buy price) / buy price. Size: small; each car is illiquid. Sell: a set holding limit or target. Mistakes: loving the car, hidden repairs, paying retail and hoping to sell at retail, and loans on an asset that drops.
