---
name: sigmataste
description: Taste pass on a page, app, deck, doc, image or film. Asks one round, then writes a ranked plan of big visible changes from 14 lenses. Do not use to build them or hunt bugs.
---

# SigmaTaste

Look at one target through taste lenses, ask the owner one round of questions, then write `sigmataste-plan-DD-MM-YYYY.md`: the few changes that make a big visible difference, ranked, each with how to verify it. Then stop. SigmaTaste plans; it does not build.

The bar: a stranger sees the difference before and after. A plan full of small fixes that nobody would notice has failed, even when every fix is right.

## Operating contract

- **One file out.** Write only the plan. Change nothing else in the target: no code, no assets, no commit. The plan goes to the repo root, or to the path the user names.
- **One round.** Ask once (step 2), at most 10 questions, each with a recommended answer. If the user already answered, or says "use the recommended answers", do not ask: write. Log each answer you took on their behalf as `Ruling:` in the plan.
- **Lenses are ways of seeing, not scores.** No points, no pass marks, no fixed counts of findings. A lens that finds nothing big says so in one line.
- **The target's own brand wins.** Read its style sources first: design tokens, a `DESIGN.md` or brand guide, theme files, a style guide, the channel or company look. A look the brand chose is identity, never a defect. Every lens default yields to it. Leaving the brand is a finding; keeping it is not.
- **Evidence from looking.** Base findings on what you saw: a screenshot, a rendered page, a contact sheet of a video, the deck in a browser, the doc as a reader gets it. Anchor each finding (file and line, selector, slide number, timestamp, screenshot name). When you cannot render, say so in the plan under "Not judged".
- **Words go to SigmaWrite.** The prose lens finds what reads as default writing. For the rewrite voice, point to `/sigmawrite`; do not copy its rules.
- **Shell native to the machine:** PowerShell on Windows, POSIX shell elsewhere. Close any server you start before you stop.

## 1. Look briefly

No questions yet. In a few minutes, find:

1. **The target and its medium.** Web page or app, dashboard, terminal UI, slide deck, document, image or thumbnail, video or film. Note where people see it (phone feed, desk monitor, projector, terminal).
2. **The mode.** *Persuade* (landing page, thumbnail, cover, pitch), *Read* (article, docs, report), *Operate* (dashboard, tool, admin), or *Experience* (film, game, artwork). Ambition scales with the mode: Persuade earns one bold idea; Operate earns calm and consistency.
3. **The brand sources** from the contract above, and any owner notes on taste (past verdicts, references they like).
4. **One look at it.** Render or open it at the size people see it. Take one or two screenshots (phone and desktop for a page; a contact sheet for a video). Note which lenses would find the most.

## 2. Ask one round

Send one numbered message, at most 10 questions, each with `Recommended:` and a few words of why. The first question is always the lens choice: a multi-select of all 14 lenses (all, some, or one), with your recommended set from step 1. The list, the other questions and how to pick each recommendation: [questions.md](references/questions.md).

Wait for the reply. Do not ask a second round.

## 3. Look hard, one lens at a time

For each chosen lens, read its file in [references/lenses/](references/lenses/) and look at the target again through it. Each lens file says what it sees, the generic tells it catches, the fix moves, and how to verify. Write down findings on THIS target only: a finding names the place, what is there now, and what a stranger would see after the change. Skip anything the brand already decided.

The 14 lenses: [first glance](references/lenses/first-glance.md) · [only this one](references/lenses/only-this-one.md) · [spent defaults](references/lenses/spent-defaults.md) · [type](references/lenses/type.md) · [colour](references/lenses/colour.md) · [one bold place](references/lenses/one-bold-place.md) · [rhythm](references/lenses/rhythm.md) · [motion](references/lenses/motion.md) · [feel](references/lenses/feel.md) · [interface words](references/lenses/interface-words.md) · [prose](references/lenses/prose.md) · [the pitch](references/lenses/the-pitch.md) · [everyone](references/lenses/everyone.md) · [charts](references/lenses/charts.md). Sources, adoption and licences: [sources.md](references/sources.md).

## 3b. Wait-what checks

Also run the three checks in [references/wait-what.md](references/wait-what.md): glossary in sync, glossary current, and the target against the repo's `DESIGN.md`. They are not lenses, they never block, and they use your judgment, not fixed rules. Skip a check whose source is missing. Their result is one fix list, the plan's "Wait-what fixes" section. Nothing is moved or deleted.

## 4. Rank by visible difference

Merge findings from all lenses into changes. Several findings often share one fix (one new type scale fixes five type findings). Rank the changes by how much a stranger would notice, then by effort. Put the big moves first: a new point of view, one bold place, a real type scale, colour with roles. Polish goes last or into "Later". Cut anything that only a checklist would want.

Before you write, do the generic test on your own plan: would you write the same plan for any similar target? Where yes, make that change specific to this one, or cut it.

## 5. Write the plan, then stop

Write `sigmataste-plan-DD-MM-YYYY.md` (today's date) from the template in [plan.md](references/plan.md): the direction in one paragraph, the ranked changes with a verify step each, the per-lens findings, the wait-what fixes, what to keep, what was not judged, and the next step. Then stop. Do not start the work.

## Final response

1. The plan path.
2. The direction in one sentence and the top three changes, one line each.
3. The next step, named: `/sigmaloop` to run the plan unattended, `/sigmaship` to ship it as one ticket, or `/implement-spec` (or the host's own spec runner) to build it from the plan.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
