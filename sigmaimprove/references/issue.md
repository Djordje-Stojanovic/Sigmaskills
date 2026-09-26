# Entry and issue formats

## Category issue

One issue per category (or per merged group of categories). The title stays stable across runs, so later runs can find and update the issue:

```text
SigmaImprove · <category ID> <category name>
```

Body:

```markdown
## Where we stand

<Two to four sentences: how this product compares with the leaders and with the bar for this category, with the evidence. Name the leaders.>

| Measure | This product | Leaders (#1–3) | Bar |
|---|---|---|---|
| <e.g. cold start> | <value, how measured> | <value per leader, source> | <best-practice bar> |

<Leave the table out when nothing in this category can be measured.>

## Entries

| ID | Type | Title | Impact | Effort | Status |
|---|---|---|---|---|---|
| IMP-B1-01 | Idea | <short name> | High | M | open |
| IMP-B1-02 | Signal | <short name> | High | ? | open |

<Status: open, chosen, rejected, done. IDs never change or get reused.>

<One section per entry, in the shapes below.>

## History

- <YYYY-MM-DD>: <created / updated: what was added, done, or changed>.
```

## Idea

```markdown
### IMP-<cat>-NN — <short name> (Idea)

**Problem:** <what is weak or missing, for whom, with the evidence: what you saw or measured, plus `path:line` or asset where relevant, and what the leaders do>.

| Option | Impact | Effort | Risk | Door | Kano |
|---|---|---|---|---|---|
| A. <name> | High | M | <risk> | two-way | delighter |
| B. <name> | … | … | … | … | … |
| C. Leave it | — | — | <cost of not acting> | — | — |

**Sketches:** <one small text sketch per option that changes something the user sees: an ASCII layout, a level map, a three-beat storyboard, or a before/after of a screen or command>.

**Recommendation:** <option, and why it beats the others>. **Signal of success:** <how we will know it worked>.

**Done when:** <observable acceptance criteria for the recommended option>.
```

Example sketch (a game level option):

```text
Option A — Fire level with a boss
  [Start]──lava bridge──[Checkpoint]──rising-lava climb──[Boss arena]
  Beat 1: learn the "heat meter" safely     Beat 2: combine heat + jumping
  Beat 3: boss uses the heat mechanic against the player
```

## Signal

```markdown
### IMP-<cat>-NN — <short name> (Signal)

**What we see:** <the observation, with the evidence: a screenshot description, a measurement, or a code location>.

**Gap:** <how the leaders or the bar compare, with sources>.

**Questions to answer:** <two to four questions a person must decide before this becomes an Idea. Examples: Is this in scope for our audience? Which leader's approach fits us? What would we stop doing to afford it?>
```

## Local files

Without an issue tracker, write one file per category: `.scratch/sigmaimprove/<category ID>-<slug>.md`, with the same title as the first heading and the same body. Update the same file on later runs.
