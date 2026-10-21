# The question round

One numbered round, at most 7 questions. Each question carries `Recommended:` and the reason in a few words. Skip a question the user already answered. When the user is away, take the recommended answer and log it as `Ruling: <answer> - <reason>`.

| # | Question | Recommended | Why |
|---|---|---|---|
| 1 | Which company (ticker) or which household file? | the ticker the user named | the filings are keyed by ticker |
| 2 | Which models? | `all` for a company, `budget` for a household | one run, one consistent set of numbers |
| 3 | Which peers for comps? | 4-8 same-model companies of similar size; name why each is in | comps are only as good as the peer set |
| 4 | Which outputs? | `xlsx,pptx,svg,html` | the workbook for checking, the deck for showing, the page for the phone |
| 5 | Any inputs to override (growth, margin, WACC parts, terminal growth, leverage)? | none: the filed-data defaults | each default names its source; change one later with `--set` |
| 6 | Projection years and scenario? | 5 years, base case | most analyses use 5; a bear or bull case is a `--set` run |
| 7 | Where do the files go? | a new folder named after the ticker and date | nothing is overwritten |

Defaults that the round never asks about (they are conventions): money in millions of the filing currency, mid-year discounting, banker colours, a 5 x 5 sensitivity grid with the base case in the centre.
