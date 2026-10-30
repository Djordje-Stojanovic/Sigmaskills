# The course grill

What to cover, in order, with a recommended default for each question. The method: one question at a time, recommended answer first, its reason, one concrete example. After each answer, add the pinned line to the running spec table and reflect it back in one plain paragraph. A vague word ("great", "deep", "properly") gets pinned to a number, a comparison or a named judge before you move on.

Every default is a starting point. The user's answer replaces it.

Scale S asks areas 0–6. M asks all areas, one or two questions each. L and XL ask all areas in depth, over several sessions when needed.

Ask once, early: "Describe one course piece you would love, and one you would hate." Later: "What result after a month of building would make you angry?"

## 0. Scale
- How big is this? Offer S, M, L, XL from SKILL.md with the hours each means. Default: the smallest scale that reaches the goal. Recompute after area 3 and say so if the goal needs a bigger scale.

## 1. The learner
- Who learns: the user alone, a team, or an audience? Default: one named learner; a course of one allows personalization no mass course can.
- Background, past courses, where they stalled and why. A stall point becomes a design rule (for example "every module ends in one whole real task").
- How they like to learn (reading, video, audio, doing). Say plainly that matching "learning styles" has weak evidence: preferences shape delivery and motivation; the method follows evidence (retrieval, spacing, worked examples, practice on real material).
- Conditions that change design (attention, decision paralysis, language, time). Default for decision paralysis: one pre-committed default per choice and a decision deadline.
- Placement. Default: a short adaptive test, fewest questions for the most information, before the course.

## 2. The goal and its real odds
- The goal as a number and a date. Ask "why" until you reach the real goal; confirm the number serves it.
- The bar as a named comparison ("as good as N years beside X").
- The base rate: what share of comparable learners reach this, and in how long. Sourced, or marked as an assumption with the reason. It sits next to the goal on every page that shows the goal.
- What the course can promise and what it cannot.

## 3. Scope, hours and depth
- Core hours and hours a week. Default: compute from the skill map (area 13) and the scale; let the bar decide, not a round number.
- Finite (a done ladder, then maintenance) or ongoing? Default: finite.
- Build first, learn after, or a pilot block first? Default: build first for L and XL when the user wants a finished, polished course; pilot first when the user wants to start soon.
- Real work during the course: what the learner does on real material each block.
- Out of scope: what the course never touches.

## 4. Variety: shapes, tasks and levels
- Show the shape catalog from `variety.md`. Which shapes fit; which to rename in the field's words; which to drop or add.
- Mix ranges per block. Default: the catalog ranges, drawn at random per lesson with a seed; the writer may override with a logged reason.
- Task types and levels L1–L10. Default: levels scattered every week, the floor rising by block.
- If the user asks for one fixed lesson pattern: keep what they want from it (they know what to expect) and name what it costs (the same structure every time dulls attention and retention; one task type trains one skill). Recommend first: a stable page frame with varied shapes, tasks and levels inside, with the mix ranges and sameness rules from `variety.md`. Offer their fixed pattern as the second option. When they asked for a file before answering, write both in it: the recommended design first, their pattern second, each complete, and ask which one stands.
- Feedback. Default: blunt and immediate; answers open only after the learner commits.

## 5. The done ladder and the evaluator
- How the build knows a piece is good. Default: scripts check numbers, sources and counts; a fresh agent on a stronger model reviews what no script can; no external judge unless the user wants one; user review packs on a cadence for L and XL.
- What counts as an hour: only accepted (gated) pieces, counted by script.
- The done list size for the scale, and the line a script prints when done.

## 6. Runtime and crew
- Which host runs the loop (Claude Code `/goal` or `/loop`, Codex `/goal`, Antigravity, pi, T3 Code). Default: the host the user already uses.
- How many agents at once, which models and efforts, who writes, who reviews, who does research and books. Default: writers on a mid model; reviews and the hardest work one model up; research, harvests and transcripts on the small model; every slot busy; jobs dynamic (any free slot takes the next unblocked row).
- Machines, render boxes, accounts, usage limits, restart windows.

## 7. Media
- Video kinds and tiers (`variety.md`). Which, how many, what share of hours. Default: video 15–25% of block hours; every lesson has a video that teaches what the text cannot.
- The long-lecture bar: one real lecture the user loves becomes the rubric.
- Generated media of any kind, including likenesses and cloned voices of real people: the user's call. Ask which of the user's own tools and machines make video, voice, images and 3D, and their limits.
- Audio versions, dialogues, diagrams in every lesson, explorables per week.

## 8. Case files
- What a case file is in this field (a real past decision with the outcome hidden; a real performance to diagnose; a real bug).
- How many, on which axes (`variety.md`). Default: equal outcome bands; at least one surprise case per block; only the material people had at the time.

## 9. Personas and guest teachers
- Which real or invented people teach. Which guests, for which block.
- Depth: full persona (a source floor, for example 100 sources) or quick.
- Does the user already have persona sheets? Default: use them byte for byte.
- Realism test. Default: blind pairs with SigmaCreateArena.
- Who teaches each lesson; who speaks when teachers disagree. Default: one teacher per lesson; disagreements become a debate lesson.

## 10. Lab tools
- Which tools the learner uses inside the course. Merge duplicates; add what the design needs.
- Polish bar. Default: the ten points in `build.md`.

## 11. History track
- Is there one? Eras, hours, mandatory or not. Default for L and XL: parallel from day one, mandatory by the end, hours reported apart from core.

## 12. Life strand
- Should the course make the learner better outside the subject too (sleep, health, focus)? Default for L and XL: one 30–60 minute lecture and one practice task per block, the evidence first and the teachers' real habits beside it.

## 13. Skill map
- Every skill the goal needs. For each: which shapes, tasks and case kinds train it, and how it is measured. Default: every skill gets at least 2% of core hours.

## 14. Sources and books
- Source floors per teacher and per topic; allowed source kinds; corpora to harvest in full.
- Book list: after the design is done, one list; the user buys; files go in `books/`.
- Data: free sources only, or paid; the user's own APIs.

## 15. Look and stack
- App or plain files? Default for S and M: Markdown files plus scripts. For L and XL: content as data (MDX or JSON), scripts for every number, local-first.
- Look: an existing design file? Default: follow it; else SigmaDesign; SigmaTaste on every new page type.

## 16. Secrets and confirms
- Where keys live (environment or an ignored folder). Which actions need a confirm. Default: only deleting the repo or publishing a secret.
