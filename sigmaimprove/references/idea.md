# Idea and ticket formats

## Ranked list

Show this first, so the user sees the whole set before the detail:

```markdown
| # | Idea | Category | Impact | Effort | Door |
|---|---|---|---|---|---|
| 1 | <short name> | B1 Perceived latency | High | M | two-way |

Scanned, nothing strong: <category IDs>. Not applicable: <category IDs>.
```

## One idea

Present each idea in this shape, and keep each one to about a screen.

```markdown
### IMP-### — <short name>

**Category:** <ID and name>.

**Problem:** <what is weak or missing, for whom, with the evidence: what you saw when you used it, plus `path:line` or asset where relevant>.

**Options:**

| Option | Impact | Effort | Risk | Door | Kano |
|---|---|---|---|---|---|
| A. <name> | High | M | <risk> | two-way | delighter |
| B. <name> | … | … | … | … | … |
| C. Leave it | — | — | <cost of not acting> | — | — |

**Sketches:** <one text sketch per option that changes something the user sees: an ASCII layout, a level map, a storyboard of three beats, a before/after of a screen or a command. Keep each sketch small.>

**Recommendation:** <option, and why it beats the others>. **Signal:** <how we will know it worked>.
```

Example sketch (a game level option):

```text
Option A — Fire level with a boss
  [Start]──lava bridge──[Checkpoint]──rising-lava climb──[Boss arena]
  Beat 1: learn the "heat meter" safely     Beat 2: combine heat + jumping
  Beat 3: boss uses the heat mechanic against the player
```

## Ticket

When the user chooses an idea, write one ticket per idea:

```markdown
# <Idea name>

## Why

<The problem and who it hurts, with the evidence, in plain words.>

## Decision

<The chosen option and the reason. Name the rejected options in one line each, so nobody reopens them without new information.>

## What to build

<The change from the user's point of view: what they will see and do. Include the chosen sketch.>

## Acceptance

- [ ] <observable result>
- [ ] <observable result>
- [ ] <signal that shows it worked, and how to check it>

## Constraints

<What must not change, the budget, and the door type.>
```

GitHub or another tracker: title `<Idea name>`, the body above, and existing labels only. Local files: `.scratch/sigmaimprove/NN-<slug>.md`, numbered in the order the user ranked them.
