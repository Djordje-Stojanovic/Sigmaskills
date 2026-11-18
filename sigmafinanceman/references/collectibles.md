# Collectibles

Trading cards, watches, art, sneakers, coins, stamps. They pay nothing while held, so the value is what the next buyer pays after every fee. The one honest yardstick is sold comparables: prices that cleared, never asking prices. `finman.py collectible item.json` does it. The input format: [assets/collectible-example.json](../assets/collectible-example.json).

## Sold comparables

Collect 10-30 sales of the same item in the same condition from the last 6-12 months. Each sale is `{"date", "price", "grade", "venue"}`.

- Per grade: the 25th percentile, median and 75th percentile sale, a trimmed mean (top and bottom 10 % dropped), sales a month (liquidity), and the trend (median of the newer half of sales over the older half).
- Bear, base and bull = the 25th, 50th and 75th percentile sale, less fees.
- Net to you = sale price x (1 - selling fees) - shipping. eBay takes about 13 % on most categories; auction houses take 15-25 % from the seller and add a buyer's premium of 20-28 %.
- Margin of safety = 1 - your price / base net.

One record sale is not a market. Drop lots that bundle items, damaged items and sales between related accounts.

## Grading

A grade (PSA, BGS, CGC for cards; certificates for watches) can multiply the price. The grading premium is the median sale of a grade over the median raw sale. Grade or sell raw: give `grade_odds` (your honest odds of each grade, for example PSA 10: 0.1, PSA 9: 0.5, PSA 8: 0.4) and the model sets the expected net graded value, less grading and shipping, against the raw net. The odds must add up to 1 and each grade needs sales; otherwise the answer is unavailable and names the missing grade. A `grade` with no sales of its own is unavailable too: it never borrows another grade's prices. Most cards do not pay for grading.

Population reports (PSA, BGS, CGC publish them per card) count the graded copies of each grade: `population`. A grade's price rests on how few exist; a fast-rising count pushes it down.

## Live data

| Item | Source |
|---|---|
| Pokémon cards | pokemontcg.io (no key): TCGplayer low, mid and high listings and the market price built from recent sales. Set `"pokemon": "name:charizard set.id:base1"`. With no sold list: `variant` (holofoil, reverseHolofoil, 1stEditionHolofoil) picks one price line; low and mid are asks and market mixes conditions. Bear = undercut the lowest ask, base = the middle ask (or market if lower), bull = the higher of the two, all labelled as asks. |
| Magic cards | Scryfall API (`api.scryfall.com/cards/named?exact=...`): daily TCGplayer and Cardmarket prices |
| Any item | eBay sold listings (filter "Sold items"); PriceCharting for cards and games; auction results (Heritage, Sotheby's, Christie's, Phillips) for art and watches |

Copy sold prices into `sales` with the date and venue; name each venue in `sources`.

## Fakes and condition

Check the certificate number on the grader's site against the photos. For raw items: compare with known fakes (weight, print pattern, serials), ask for the provenance, and buy from a seller who accepts returns. A watch needs its papers and a service record; art needs provenance and, above a few thousand, an expert opinion. A fake is a total loss: it is the bear case under the bear case.

## Traps

- Asking prices in place of sold prices.
- Forgetting the selling fees, shipping, insurance and storage.
- A thin market: two sales a month means a long wait or a discount to sell.
- Paying a graded price for a raw item "that would surely get a 10".
- Hype: a price that tripled in a month usually halves again.

## Playbook

Check: where you buy below where you sell, and who buys. Numbers: buy price + fees + shipping + returns + your hours = cost; margin = sale − cost; days to sell; turns per year. Annual return = margin per cycle × cycles per year. Size: stock you can sell within a set number of days; limit capital in any one item. Sell: set a markdown date when you buy. Mistakes: counting no time cost, stock that sits, no returns allowance, and a single platform that can close your account.
