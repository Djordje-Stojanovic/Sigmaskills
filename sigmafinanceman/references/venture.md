# Startups and venture

A startup has no cash flows to discount, so its value is the share of one exit you will own. Three questions decide a cheque: what the company can be worth at the exit, how much of it you still own then, and how often an outcome like that comes. `finman.py venture deal.json` answers all three. The input format, with every key used: [assets/venture-example.json](../assets/venture-example.json). Made-up numbers are fine for a private company; mark them as such in `source`.

## The VC method

Work back from the exit.

1. Exit equity = exit revenue x an EV multiple - `exit_net_debt`, or a direct `exit_value` (equity).
2. Ownership you keep = 1 - the dilution of the later rounds (`future_dilution`; 40-60 % from seed to exit is common).
3. Ownership needed today = investment x target multiple / (exit value x ownership kept).
4. Most the post-money can be = exit value x ownership kept / target multiple.

Target multiples: 10-30x at seed, 5-10x at Series A, 3-5x later, as a fund needs its few winners to pay for the rest. The page sets the round's real post-money against the maximum.

## The cap table

Fully diluted shares: founders, the option pool (granted and free), converted SAFEs and notes, and each round's preferred shares.

- **Option pool shuffle.** The pool top-up a round asks for (`pool_target`, a share of the post-money) sits in the pre-money. The earlier holders pay for it, not the new money. A 10 % pool in the pre-money cuts the real pre-money by about that much.
- **Post-money SAFE** (YC form, `"type": "post"`). Before the round's new money, the holder owns amount / cap of the company with every SAFE and note counted in. Converts at the lowest of the round price, the cap price and the discount price (round price x (1 - discount)): a cap above the round never costs the holder shares.
- **Pre-money SAFE** (`"type": "pre"`) and **convertible note.** The cap price is the cap over the shares before them, pool included. A note converts principal plus interest (simple, `rate` x `months` / 12); `"pref_basis": "balance"` sets its preference on that balance when the note says so.
- **Priced round.** Price per share = pre-money / (shares before + pool top-up + converted shares). The new money gets amount / price shares. The model solves the loop (the conversions depend on the price, the price on the conversions) by iteration, and stops with the round's name when the terms have no solution (a SAFE larger than its cap).
- SAFEs and notes convert into the first priced round's preferred, with a liquidation preference equal to the cash they paid.

Check after each round: post-money = pre-money + amount, the new money owns amount / post-money, and the pool is at its target. The selftest proves all three.

## Liquidation preferences and the waterfall

At an exit, preferred holders choose: take their preference (1x = their money back, `liq_pref` sets the multiple) or convert to common and share by ownership.

- **Non-participating** (the norm): the larger of the two. The model converts the cheapest preference first and repeats until no holder gains by switching.
- **Participating** (`"participating": true`): the preference and then a share as common. Expensive for founders in a modest exit.
- Preferences here are pari passu (paid side by side). A senior stack pays the newest round first; say so when a term sheet has it.
- Only granted options share in an exit: `options_granted` on a round (granted since the last round) and at the top level (granted since the last round, before the exit). The free pool is cancelled at the sale. Granted options exercise at `option_strike` when common's price beats it.

The `exits` list sets the waterfall's columns; the low, middle and high exits are the bear, base and bull cases. Read the low exit first: that is where preferences bite.

## Term-sheet clauses that move the money

| Clause | What it does | Founder-friendly default |
|---|---|---|
| Anti-dilution | in a down round, re-prices the investor's conversion. Full ratchet: to the new low price. Broad-based weighted average: part of the way, weighted by the new shares. | broad-based weighted average |
| Pro rata | the right to buy into later rounds to keep the ownership | for lead investors only |
| Liquidation preference | 1x non-participating is the market norm; above 1x or participating shifts a modest exit to the investors | 1x non-participating |
| Option pool | sized in the pre-money; a pool larger than the next 18 months of hires costs the founders for nothing | the hiring plan, not a round number |
| Vesting | founders' and staff shares earn over 4 years with a 1-year cliff; acceleration on a sale (single or double trigger) | double trigger |
| Board | who controls the company between rounds | founders hold the majority at seed |

A down round triggers anti-dilution and often a new pool. Put the protected series' clause on its round, `"anti_dilution": "full"` or `"broad"` (broad-based weighted average); at a later round below its price the model gives that series its extra shares before the new money. Another formula (narrow-based, a pay-to-play) is not in the model: say so beside the waterfall. Secondary sales (founders or early staff sell some shares in a round) take cash off the table without new dilution; they count in the cap table as a transfer, not as new shares.

## From the exit price to each holder's cash

**What the price buys.** An EV/revenue multiple prices the business before debt and cash. A signed offer may price the shares instead. From an EV: add the cash the buyer takes over, subtract the debt to repay and the seller's deal costs, then apply the working-capital adjustment the offer names. Read how the offer defines cash, debt and normal working capital: one customer deposit must not cut the proceeds twice. The waterfall splits whatever number sits in `exits` among the holders, so put the equity there, not the EV.

**When it arrives.** Cash at closing, escrow, earn-outs and buyer shares each get their own date, condition and amount. Put an earn-out only in the case where its target is met. Follow the merger agreement on how later payments meet the preferences. Example, terms assumed: an offer of 100m EV, 4m cash taken over, 20m debt repaid, 4m seller costs leaves 80m for the holders. An investor with 20 % on conversion and a 20m non-participating preference takes the 20m preference (conversion pays 16m); common splits 60m. A 40m earn-out raises the total to 120m. If the agreement measures the choice on all proceeds, the investor now converts, takes 24m in all, and the earn-out pays it 4m. Paying the 20m preference again on the second payment would count it twice.

**An option grant or a job offer.** An employee asks the investor's question with three changes: common sits under every preference, options cost the strike to exercise, and the cash given up is salary.

1. Ownership = options / fully diluted shares. A count of options with no share total cannot be valued: ask for the total.
2. Common's price per share at each exit = a founder's take in the waterfall / that founder's shares. The grant is worth options x max(0, that price - strike). In a modest exit the preference stack can leave common with nothing.
3. Later rounds dilute the grant too: multiply the ownership by (1 - `future_dilution`).
4. Weight the exits by their odds (strategy.md, "Weigh the cases"); most outcomes are zero.
5. Set it against the cash given up: the salary gap over the vesting years, plus the exercise cost and its tax.

Ask for the strike, the latest preferred price, the latest common valuation (a 409A in the US), the vesting terms, the exercise window after leaving (a short one forces a cash decision on the way out) and whether early exercise is allowed. At an exit, read which awards accelerate, get cashed out or lapse. Tax on exercise: ask the user's country, the option type and the rates, compute it (for US non-qualified options, common's value when vested - the strike paid is income at exercise: [IRS Publication 525](https://www.irs.gov/publications/p525)), and put it on the date it is paid, often before any sale.

**Anti-dilution in numbers.** Broad-based weighted average: new conversion price = old price x (A + B) / (A + C). A = fully diluted shares before the down round, B = the shares the new money would buy at the old price, C = the shares it really buys. A full ratchet sets the conversion price to the new price.

**What a fund's investors get.** A company that returns ten times one cheque says little about the fund. Follow the limited partner's cash by date: capital calls, fees, distributions and the holdings left. The partnership agreement sets carry, the preferred return, any catch-up, and whether carry is paid deal by deal or on the whole fund. Example, all assumed: 85 % of the fund invested, 20 % carry on the whole fund's profit, no hurdle. A gross 3.0x on invested money is then 1 + (3.0 x 0.85 - 1) x 0.8 = 2.24x net.

Report three multiples on one date. DPI = cash distributed / cash paid in. RVPI = net asset value left / cash paid in. TVPI = DPI + RVPI. Example, assumed: paid in 10m, received 3m, the rest marked at 9m: DPI 0.3x, RVPI 0.9x, TVPI 1.2x. Halve the mark and TVPI falls to 0.75x while DPI stays 0.3x. Late in a fund's life, a high TVPI with a low DPI is a mark, not a return. Compute the net IRR on the real call and distribution dates, and say how much of it rests on the mark ([ILPA Performance Template definitions, 2025](https://ilpa.org/wp-content/uploads/2025/04/ILPA-Performance-Template-Definitions-Granular-Methodology-v1.1.pdf)).

## Power-law portfolio maths

Venture returns follow a power law: a few companies return the fund, most return little or nothing (Thiel P1, Leone P5). The `fund` block gives:

- First cheque = fund size x (1 - fees share) x (1 - reserve) / cheques. Hold back about half for follow-ons.
- The exit that returns the fund = fund size / ownership at exit. If no plausible exit of this company does it, the cheque cannot carry the fund.
- Chance of at least one outlier = 1 - (1 - p)^n, with p from the outcome shape (default: Correlation Ventures' 21,640 US financings 2004-2013, 65 % under 1x, 25 % 1-5x, 6 % 5-10x, 4 % 10x+, with an assumed 0.2x, 3x, 7.5x and 20x inside each band; an outlier is 10x+, `outlier_multiple`; set your own under `fund.outcomes`, shares adding up to 1).
- Expected gross multiple, and the expected multiple of a cheque that is not an outlier. The gap between them is the case for more shots.

Check sizing: a cheque you can lose in full (strategy.md step 4); spread over enough companies that the outlier odds are high; size each by the exit that would return the fund, not by conviction alone.

## Reading a pitch deck's numbers

The `deck` block recomputes what a deck claims and sets each against the usual bar:

| Number | How | Bar |
|---|---|---|
| Runway | cash / net monthly burn | 18+ months after the round |
| Burn multiple | net burn / net new ARR; n/a when ARR shrank | under 2x; under 1x is excellent |
| Price / ARR | post-money / ARR | under 30x at seed, under 20x from Series A (`deck.stage`) |
| Growth | ARR year on year | 2-3x a year early on |
| Gross margin | (revenue - cost of revenue) / revenue | 70 %+ for software, 40 %+ for hardware |
| LTV / CAC | (monthly revenue per account x gross margin / monthly churn) / CAC | 3x+ |
| CAC payback | CAC / (monthly revenue per account x gross margin) | under 18 months |

Ask for the raw table behind every chart: bookings are not revenue, GMV is not revenue, and "ARR" from one month of a seasonal business is a guess. Check the use of funds against the runway.

## Free data

Private companies publish nothing. SEC Form D (EDGAR full-text search) shows that a round was raised and its size; state registries show the founding date and officers; the company's own numbers come from the data room. Public comparables for the exit multiple come from `finman.py comps`.

## Traps

- Valuing by the last round's price: the last round priced one share class with its preferences, not the company.
- Forgetting the pool shuffle and the SAFE stack when you quote the founders' share.
- A high valuation with a 2x participating preference: the headline number hides the founder's real take.
- Too few cheques to hit an outlier.
- Uncapped SAFEs: the holder's share is unknown until the round.

## Playbook

Check: market size and risk layers (Andreessen P1, P4), founders, the cap table, the price, and the path to a sale or listing. Numbers: ownership after dilution, the return needed to be worth the fund's lock-up, and a 10x gain on invested capital in four to six years (Andreessen P2). Returns come from a few outliers (Thiel P1, Leone P5). Size: many small cheques, with money held back for follow-ons, and no cash you need. Sell: when a buyer offers a price above your hold case, or by a founder's 10-20% partial sale (Leone P1). Mistakes: too few shots, chasing a hot round, ignoring dilution and fees, and pricing by the last round (Leone calls protecting the last round's price a mistake).
