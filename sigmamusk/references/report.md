# The issue and the report page

## The issue

Title: `sigmamusk: <the one change that buys the most>`.

Body, in this order:

```markdown
## Verdict
<two or three blunt sentences with the key numbers>

## Measured
| Number | Value | Command |
|---|---|---|
| Lines of process / lines of product | 22,800 / 456 files | `git ls-files checks test | xargs wc -l` |

## Delete first (ranked by gain)
1. <part or process> — <gain, measured or estimated and labelled> — <file or command>

## Keep
- <part> — <why it earns its place>

## Dumb requirements
- "<requirement>" — owner: <name> — ask: <question>

## Bottleneck
<the constraint now, and how to remove it>

## Smallest ship
<the one task to do first>

## Do not automate yet
- <item>

## Acceptance criteria
- [ ] `<command>` shows <number> at or below <target> (now <value>).
- [ ] <the deleted part> is gone and `<test command>` passes.

Ship with: `sigmaship #<this issue>`
```

Every acceptance criterion names a command and a target, so SigmaShip can check it. Keep the issue under about 600 words; the page carries the detail.

## The report page

One self-contained HTML file: the verdict on top as a big statement, the measured numbers as large figures, the delete list as a ranked list with bars for the gain, then requirements, bottleneck, smallest ship and the issue link. It works on a phone and in dark mode.

**A different look every time.** Pick one look not used for this repo before (check earlier SigmaMusk issues for the look named in their footer), and name it in the page footer and the issue:

1. Mission control: near-black, amber and green telemetry, monospace figures.
2. Starship steel: brushed grey, one orange accent, condensed sans headings.
3. Blueprint: deep blue, white line work, grid paper.
4. Mars dawn: rust red to dust pink, large serif numbers.
5. Tesla white: pure white, black type, one red line, lots of space.
6. Swiss grid: strict grid, Helvetica-style type, red and black.
7. Broadsheet: newspaper columns, serif headline, ruled lines.
8. Terminal: green on black, a blinking cursor in the verdict.

Publish it as a private artifact when the host can publish pages; otherwise save it in the OS temp folder as `sigmamusk-<repo>-<yyyy-mm-dd>.html` and open it. Keep it out of the target repo.
