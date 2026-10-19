# The plan file

Name: `sigmataste-plan-DD-MM-YYYY.md` (today's date). Plain, short English. Every finding is about THIS target, with an anchor. Keep the section names below: other tools read them.

```markdown
# SigmaTaste plan: <target> (DD-MM-YYYY)

Target: <what, where it lives, how it was seen (screenshots, contact sheet, rendered at which size)>
Medium and mode: <web page | dashboard | terminal UI | deck | doc | image | video> · <Persuade | Read | Operate | Experience>
Brand sources: <files read, or "none found">
Lenses: <the chosen ones>
Answers: <one line per question, the owner's or `Ruling: <what> — <why>`>

## Direction

One paragraph: the point of view this target should have, the one bold place, and what gets quieter so it can stand out. Name the subject's own world that the look comes from. If the brand already fixes the direction, say how the plan sharpens it.

## Ranked changes

| # | Change | Lenses | Where | What a stranger sees after | Effort | Verify |
|---|---|---|---|---|---|---|
| 1 | <one move, concrete> | <lens names> | <file:line, selector, slide, timestamp> | <the visible difference> | S/M/L | <how to check: before/after screenshot at the same size, squint, swap test, measured contrast, read aloud> |

Big moves first. Polish last or in "Later".

## Findings by lens

### <Lens name>

- <anchor>: <what is there now> → <the change> (feeds change #N)

One line "Nothing big here" when the lens found nothing worth a change.

## Wait-what fixes

One line per item, from [wait-what.md](wait-what.md): `<check> · <anchor> · <what is wrong> → <what to do> · <why>`. Checks: glossary in sync, glossary current (update, merge, retire or delete, with a reason), DESIGN.md clashes. The builder applies what is true. A check with nothing to say gets one line.

## Keep

What already works or is the brand's identity, so the builder does not "fix" it.

## Not judged

What could not be seen (no render, missing pages, sound, live data) and why.

## Later

Small polish and sightings outside the chosen lenses, one line each.

## Next step

Name one: `/sigmaloop` to run this plan unattended, `/sigmaship` to ship it as one ticket, or `/implement-spec` (or the host's spec runner) to build from it. Say what the builder should read first (this file, the brand sources).
```

## Rules for the content

- One change can serve several lenses. Write it once in the table and point to it from each lens.
- "Verify" is a check a builder can run, never a score: a before and after screenshot at the size people see it, the squint test, the swap test, a contrast number from a tool, reduced motion turned on, the text read aloud.
- No numbers you did not measure. "Contrast 3.1:1 (measured with <tool>)" is fine; "contrast looks low" is a sighting for the builder to measure.
- No new facts in copy changes. Rewrites of headlines or labels keep the target's claims; mark missing proof as `[NEED: <what>]`.
