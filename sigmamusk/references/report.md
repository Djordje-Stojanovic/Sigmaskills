# The issue and the report page

## The issue

Title: `sigmamusk: <the one change that buys the most>`. Under about 600 words; the page carries the detail. Every acceptance criterion names a command and a target, so SigmaShip can check it.

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

## The report page

One self-contained HTML file: the verdict as a big statement, the numbers as large figures, the delete list ranked with bars for the gain, then requirements, bottleneck, smallest ship and the issue link. Phone and dark mode work. Publish it as a private artifact when the host can; otherwise save it in the OS temp folder as `sigmamusk-<repo>-<yyyy-mm-dd>.html` and open it. Never inside the target repo.

A different look each run: pick one not used for this repo before (earlier SigmaMusk issues name theirs in the footer) and name it in the footer and the issue: mission control (near-black, amber telemetry, monospace figures) · starship steel (brushed grey, one orange accent) · blueprint (deep blue, white lines, grid paper) · Mars dawn (rust to dust pink, serif numbers) · Tesla white (white, black type, one red line) · Swiss grid (Helvetica-style, red and black) · broadsheet (newspaper columns, serif headline) · terminal (green on black, a blinking cursor).
