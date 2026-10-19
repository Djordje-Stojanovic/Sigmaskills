# The question round

One message, numbered, at most 10 questions. Each line: the question, then `Recommended: <answer>` and a few words of why, drawn from step 1. The user can reply "all recommended" or change single numbers. Ask only what the target cannot answer: if a brand file already fixes the palette, state it as given and do not ask.

## 1. Which lenses (always first)

A multi-select. Show all 14 with one line each, mark the recommended ones, and offer three shortcuts: **all**, **the recommended set**, or **one lens** by name.

| Lens | It asks |
|---|---|
| First glance | In one second, is there one thing to see first? |
| Only this one | Swap the name: does it still work for a rival? |
| Spent defaults | Which looks are the AI or template default, not a choice? |
| Type | Do the type roles tell apart, with a real scale? |
| Colour | Does each colour have a role, and does the accent mean "here"? |
| One bold place | Is there one memorable element, and what is the one cut? |
| Rhythm | Does every section, slide or scene use the same layout? |
| Motion | Does each move have a reason, and should it move at all? |
| Feel | Do press, hover, focus, empty and loading states feel cared for? |
| Interface words | Do labels and buttons say what they do? |
| Prose | Does the writing read as default AI or template prose? |
| The pitch | Is the argument clear in five seconds, with proof and one action? |
| Everyone | Can people with low vision, keyboard only or reduced motion use it? |
| Charts | Does each chart answer one question at a glance? |

How to recommend: pick the lenses where step 1 saw the biggest gap, then add the ones the mode needs. Persuade: first glance, only this one, one bold place, the pitch, type. Operate: first glance, colour, feel, charts, everyone, interface words. Read: type, prose, rhythm, everyone. Experience: first glance, only this one, colour, motion. A target with no motion, no charts or no prose drops that lens. "All" is right for a first pass on something the owner cares about a lot; say so if you recommend it.

## 2-10. The rest (ask only what applies)

2. **What do you expect?** A bold new direction, or the same look made sharper? And the one feeling a stranger should leave with. Recommended: from the mode and what you saw; for a first pass on a generic-looking target, a new direction.
3. **Scope.** Which pages, screens, slides, scenes or files. Recommended: the first thing people see plus the one most-used screen or section.
4. **Who sees it, and where.** Audience and the real viewing scene (phone in a feed, desk monitor, projector, terminal, TV). Recommended: what the repo or brand says, else the most likely scene.
5. **Brand and what must not change.** Locked fonts, colours, logo, layout, tone. Recommended: everything in the brand sources you found, named by file.
6. **Constraints.** Stack, no new dependencies, performance budget, deadline, who builds it (agent, human, both). Recommended: the repo's own stack and no new runtime dependency unless a lens needs one.
7. **References.** Two or three things the owner loves, and one they hate, in this category. Recommended: none needed; the plan proposes its own direction and names the reference it uses.
8. **How bold.** Ambition from 1 (polish only) to 3 (new point of view), as a word: polish, sharpen, or rethink. Recommended: from question 2 and the mode.
9. **Plan path.** Recommended: `sigmataste-plan-DD-MM-YYYY.md` at the target repo root.
10. **Next step.** `/sigmaloop` (run unattended), `/sigmaship` (ship as one ticket), `/implement-spec` or the host's spec runner (build from the plan), or just read it. Recommended: `/sigmaship` for a plan with up to about five changes; `/sigmaloop` for more.

## After the reply

- A blank takes the recommendation. Add it to the plan as `Ruling: <what> — <why>`.
- A reply that contradicts the brand sources wins (the owner decides), and the plan notes the conflict once.
- The lens choice is final for this run. Do not add lenses the owner did not pick, even when you saw something; put such a sighting in one line under "Later".
