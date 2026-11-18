---
name: sigmataste
description: Use when asked for sigmataste or a taste pass on a page, app, deck, doc, image or film. Asks one round, then writes a ranked plan of visible changes (14 lenses). Do not use to build them or hunt bugs.
---

# SigmaTaste

Look at one target through taste lenses, ask the owner one round of questions, then write `sigmataste-plan-DD-MM-YYYY.md`: the few changes that make a big visible difference, ranked, each with how to verify it. Then stop. SigmaTaste plans; it does not build. Invoked together with a skill that builds (SigmaShip), it brings its lenses into that run instead: no plan file, no stop.

The bar: a stranger sees the difference before and after. A plan full of small fixes nobody would notice has failed, even when every fix is right.

## Operating contract

- **One file out.** Write only the plan, at the repo root or the path the user names. Change nothing else in the target: no code, no assets, no commit. Close any server you start.
- **One round.** Ask once (step 2). If the user already answered, or says "use the recommended answers", write without asking; log each answer you took on their behalf as `Ruling:` in the plan.
- **Lenses are ways of seeing, not scores.** No points, pass marks or fixed counts of findings. A lens that finds nothing big says so in one line.
- **The target's own brand wins.** Read its style sources first: design tokens, a `DESIGN.md` or brand guide, theme files, the channel or company look. A look the brand chose is identity, never a defect; leaving the brand is a finding.
- **Evidence from looking.** Base findings on what you saw rendered: a screenshot, the page, a contact sheet of a video, the deck in a browser, the doc as a reader gets it. Anchor each finding (file and line, selector, slide, timestamp, screenshot name). Use whatever render or screenshot tool this host has; when one fails, try another way to see it (a headless browser, an export to image, frames pulled with a video tool). What you still cannot render goes under "Not judged".
- **Words go to the writing skill.** The prose lens finds what reads as default writing; for the rewrite voice point to `/sigmawrite` (or the installed equivalent) instead of copying its rules.

## 1. Look briefly

No questions yet. In a few minutes, find:

1. **The target and its medium**, and where people see it (phone feed, desk monitor, projector, terminal).
2. **The mode.** *Persuade* (landing page, thumbnail, cover, pitch), *Read* (article, docs, report), *Operate* (dashboard, tool, admin) or *Experience* (film, game, artwork). Persuade earns one bold idea; Operate earns calm and consistency.
3. **The brand sources**, and any owner notes on taste (past verdicts, references they like).
4. **One look** at the size people see it: one or two screenshots (phone and desktop for a page; a contact sheet for a video). Note which lenses would find the most.

## 2. Ask one round

One numbered message, at most 10 questions, each with `Recommended:` and a few words of why. The first is always the lens choice: a multi-select of all 14 lenses with your recommended set. The questions and how to pick each recommendation: [questions.md](references/questions.md). Wait for the reply; no second round.

## 3. Look hard, one lens at a time

Each lens is one file in [references/lenses/](references/lenses/): what it sees, the generic tells it catches, the fix moves, how to verify. For each chosen lens, read its file and look at the target again through it. A finding names the place, what is there now, and what a stranger would see after the change, on THIS target only. Skip anything the brand already decided. Sources, adoption and licences: [sources.md](references/sources.md).

Also run the three checks in [wait-what.md](references/wait-what.md) (glossary in sync, glossary current, the target against the repo's `DESIGN.md`), skipping one whose source is missing. They use judgment, never block, and move nothing; their result is the plan's "Wait-what fixes" section.

## 4. Rank by visible difference

Merge findings into changes: one new type scale can fix five type findings. Rank by how much a stranger would notice, then by effort. Big moves first (a new point of view, one bold place, a real type scale, colour with roles); polish last or under "Later". Cut anything only a checklist would want.

Then the generic test on your own plan: would you write the same plan for any similar target? Where yes, make that change specific to this one, or cut it.

## 5. Write the plan, then stop

Write `sigmataste-plan-DD-MM-YYYY.md` (today's date) from the template in [plan.md](references/plan.md): direction, ranked changes with a verify step each, findings by lens, wait-what fixes, what to keep, what was not judged, and the next step. Start no work.

## Final response

1. The plan path.
2. The direction in one sentence and the top three changes, one line each.
3. The next step, named: `/sigmaloop` to run the plan unattended, `/sigmaship` to ship it as one ticket, or `/implement-spec` (or the host's own spec runner) to build it.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
