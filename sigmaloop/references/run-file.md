# The run file

The variables of one run. The rules live in [flow.md](flow.md); the run file never repeats them. Replace each `<...>`; a line the answers left empty goes.

```markdown
# Run: <title>

Flow: <absolute path of the installed sigmaloop/references/flow.md>. Read it and this file at the start of every turn.
Handoff: <path>. Owner's words: <path>. Owner page: <path or url>.

## Stop line
<The command and the text it prints at done, and/or a date, time and zone.>

## Crew
| Role | Model ids, in fallback order | Slots |
|---|---|---|
| Planner | <ids> | 1 |
| Builder | <ids> | <N> |
| Reviewer | <ids, another family than the builder> | one per READY |
Landing: <one feature branch `<branch>` and one PR | a PR per ticket>. Merge: <squash, the repo's rule>.

## Order
<The ranked list (id, one line, size), or the tracker query that gives it.>

## Off-limits
- <What the run must not touch>. "<his sentence>" (<date>)
Pre-authorised: <list>. Spend: <what, limit per period, the command that prints used>, or none.
```

Keep it under 60 KB: the handoff is rewritten each turn, never appended to. A limit with no quote of his starts with `model:` and may be dropped if it blocks the run.
