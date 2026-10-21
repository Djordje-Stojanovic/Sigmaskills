# Outputs: the Ledger look

One visual system for the workbook, the deck, the charts and the page: a white ruled sheet, navy rules, Calibri, banker colours. Calibri ships with every Office install, and LibreOffice and Google Slides substitute Carlito at the same widths, so nothing reflows. The tokens live once in `scripts/fin_svg.py` (`TOK`); the workbook and the deck read them from there.

## Tokens

| Token | Hex | Use |
|---|---|---|
| bg | #FFFFFF | page and slide ground |
| ink | #1B1F24 | text |
| muted | #5F6B7A | labels, sources |
| rule | #D5DAE1 | table rules, grid lines |
| panel | #F2F4F7 | total rows on slides |
| navy | #0B2545 | headers, totals, the hero number, the selected bar |
| gain / loss | #17633B / #D92D20 | only a gain and a loss (or pass and fail); never a part of a total |
| steel | #8A9BB0 | parts of a total, ranges, peers; the value is always printed beside the bar |
| marker | #8A5200 | the price line; its label sits in a navy tag |
| center | #BDD7EE | the base-case cell of a sensitivity grid |
| input / link | #0000FF / #008000 | workbook fonts: typed input / link to another sheet (formulas are black) |

Number formats: money `#,##0_);(#,##0);"-"_)`, percent `0.0%`, multiple `0.0"x"`, per share `$#,##0.00_);($#,##0.00)`. Negatives in brackets. The `_)` pad keeps positive digits in line with bracketed negatives; the page copies it with a hidden `)`.

## The three fixes from the design audit (2026-10-21)

1. **Exact tables.** Digits line up (the pad above). Each header aligns with its column. 22 px between stacked tables. Totals bold with a thin top rule; the final line (value per share, equity out, left over) has a double bottom rule.
2. **The answer first, colour roles clean.** One hero number at 44 px (60 pt on the title slide), then one sentence, then a small KPI row. Green and red only for gain and loss; parts of a total (PV of cash flows, PV of terminal value, savings) are steel. Green and red differ in lightness, and brackets and pass/fail words carry the meaning without colour.
3. **Phone and slides readable.** Each chart is drawn twice: wide, and narrow for a phone (labels above bars, no sideways scroll). Tables scroll inside their box with the first column frozen; the workbook freezes the first column too. Slide body text 18 pt, chart labels and tables 12 pt or more.

## Workbook

Sheets: `Inputs` (blue, each with a source comment), `Historicals` (filed numbers, blue, comment = us-gaap tag and period), the model sheet (green link block, then black formulas), and `Checks` (TRUE/FALSE ties, `All checks` at the bottom). Landscape, one page wide when printed. The sensitivity grid is odd-sized with the base case in the centre.

## Deck

16:9, blank layout, Calibri. Slide 1: title, the hero number, its sentence, five KPIs. Then one slide per chart (native PowerPoint charts, editable: the waterfall is a stacked column with an invisible base series and the value under each category; the football field is a stacked bar with a transparent first series and the price as its own row), one slide per table (14 rows a slide), and a notes-and-sources slide.

## Charts and page

`<stem>-chartN.svg` is the wide chart, standalone. `<stem>.html` holds the hero, the KPI row, both chart widths (CSS picks one), every table, notes and sources; it runs offline with no script. `<stem>.report.json` is the report data every writer drew from, and `<stem>.cells.json` names the workbook cells that hold the headline numbers (`audit` compares them).
