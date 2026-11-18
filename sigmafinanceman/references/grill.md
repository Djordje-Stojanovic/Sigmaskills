# The question round

One numbered round, at most 7 questions. Each question carries `Recommended:` and the reason in a few words. Skip a question the user already answered. When the user is away, take the recommended answer and log it as `Ruling: <answer> - <reason>`.

| # | Question | Recommended | Why |
|---|---|---|---|
| 1 | What are you valuing, and what decision does it serve (buy, sell, size, rent or buy, grade or sell raw)? | the asset and decision the user named | it picks the class file and its model (SKILL.md section 1) |
| 2 | Which models, and which inputs (ticker, input file, term sheet, sold list, quote)? | `all` for a company; the class command otherwise | one run, one consistent set of numbers |
| 3 | Which comparables (peers for comps, sold sales for a collectible, the rental price for a purchase)? | stocks: 4-8 same-model companies of similar size; others: the live source in the class file | a value is only as good as what it is compared with |
| 4 | Which outputs? | `xlsx,pptx,svg,html` | the workbook for checking, the deck for showing, the page for the phone |
| 5 | Any inputs to override (growth, margin, discount rate, use per month, price growth, carry)? | none: the defaults | each default names its source; change one later with `--set` |
| 6 | Projection years and scenario? For a buy, size or sell call: horizon, loss budget, funding? | 5 years, base case; horizon and loss budget from the user's plan | most analyses use 5; [strategy.md](strategy.md) sizes the bet from the loss budget |
| 7 | Where do the files go? | a new folder named after the asset and date | nothing is overwritten |

Defaults that the round never asks about (they are conventions): money in millions of the filing currency, mid-year discounting, banker colours, a 5 x 5 sensitivity grid with the base case in the centre.

For an investment call, read [strategy.md](strategy.md) first. Its nine steps decide what to ask in questions 1, 5 and 6: the edge, the worst case in money, the funding and the sell rule.
