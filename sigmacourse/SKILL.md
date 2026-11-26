---
name: sigmacourse
description: 'Use when asked for sigmacourse or to plan or build a tutorial, guide, course or curriculum of any length, subject, audience or medium. It starts from what the learner can do at the end, derives the parts and its own process from that, and covers delivery: design, interface, performance, accessibility. Do not use for live tutoring.'
---

# SigmaCourse

Plan and build teaching of any size, on any subject, for any audience, in any medium. Each step below runs only when the course needs it, so a one-pager gets almost no process and a thousand-hour program a lot. When a local skill builds courses with your own stack, it builds; it runs steps 1 to 3 here first.

## Operating contract

- **The user decides.** Subject, size, depth, voice, media, real people as teachers, generated likenesses: all the user's call. The newest word wins over every default here; when it clashes with a rule, say once what it costs, then do it. The only confirm: an action that deletes the repo or publishes a secret. Save the user's words verbatim.
- **Find the real need, then align.** One question at a time, your pick first, only while a wrong guess costs more than the question ([grill.md](references/grill.md)). Before the build, play the plan back in the user's words and wait for a yes; after the first built part, ask what is off and fix the plan, not only the part. "Just build it": guess every answer and ask for corrections once.
- **Realism.** Every number has a source or a stated assumption. Every promised result sits next to how often comparable learners reach it, or "no number found", never an invented one. Counts and sums run in a script, never in prose. No secrets in any file, brief or prompt.

## 1. The end state

Write one line per separate ability the learner must have at the end: "At the end, the learner can <do what> on <real material> to <what standard>." Two lines are separate when a learner could have one without the other. The size is the learner time the user names, on any scale; when they name none, the map's total from step 2 is the size; say it once and go on. **Done when** every line names a real task, real material and a standard someone else could judge.

## 2. The ability map

1. Under each end line, write what the learner must be able to do just before it. Repeat for each new line until you reach what the learner can already do. Ask when you do not know. Merge duplicates: one ability, one node. A wrong belief the learner holds that would block a node becomes a node. An end line is the last node of its chain.
2. For each node write: the proof task, the practice it needs (how many tries, with feedback, before the proof is likely to pass; an estimate with its reason), and the medium the proof needs (step 4).
3. Give each node its minutes: teach, practice, proof. Reading and speaking time come from a rate you state for this audience, video from its real runtime, practice from tries times the time of one try (measured, else a stated guess). Keep the map as data, one row per node (`id`, `needs`, the three minute counts, its end line); a script you write reads it, sums the minutes and counts the nodes and the longest prerequisite chain (one node needs no script).
4. Fit a named size. Over it: cut practice on the easiest nodes first, then the end line that matters least to the user; say which. Under it: finish short and say so, or, if the user wants the full size, add practice on the hardest nodes. Never pad with new topics.
5. The outline is the map in order: each node after what it needs. One part per node; a wrong-belief node makes a short first part. Nothing goes in that no end line needs. **Done when** the node count, the longest chain and the total minutes are printed (by the script, from two nodes up), and every outline item names the end line it serves.

## 3. The process the map needs

Read the map, then run each step whose condition is true. Write the result as a short table: step, true or false, the fact from the map that decided it. A named skill or tool is the known route: read it before its step; when it is missing, do the step another way and say which.

| Step | Run it when | Tool |
|---|---|---|
| Write in place, one file, the outline at its top until done | one agent session can draft and check all of it, text and media, with no handoff (say the estimate) | this skill |
| Plan file `course-plan.md` (end state, map, outline, media, sources) | the writer cannot, so the map must live outside the draft | this skill |
| Grill | an open answer would change a node, an order, a proof or a medium; depth follows what a wrong guess would cost | [grill.md](references/grill.md) |
| Playback, first-part review | always: one line beside the result for a piece one session builds, a block before the build for more | [grill.md](references/grill.md#alignment) |
| Placement check | the learner's start is unknown and some nodes may already be known | a short test on those nodes |
| Spaced review | the learner time spans more than one sitting | step 4 |
| Research | the course states a fact the user's sources do not hold | [research-and-books.md](references/research-and-books.md) |
| Fresh review by an agent that did not write it | always; its size follows the map (one read for one node, a batch review per part for many); with no second agent, hold it open and say so | SigmaReview lenses |
| Spec, done list, user sign-off | the build needs more than one agent session, so others must work from a written contract, or the user asks for one; leave out each spec line the course has no answer for | [repo-setup.md](references/repo-setup.md) |
| Queue and check script; run file and goal prompt | the first pair: more than one job to track; the second: more sessions than the user will watch | [repo-setup.md](references/repo-setup.md), [build.md](references/build.md), SigmaLoop for the user's harness ([hosts.md](references/hosts.md)); a decision map (`wayfinder` or `docs/course/map.md`) when open decisions block later parts |
| Personas | the user names real or invented teachers | [build.md](references/build.md#personas) |
| Variety draw | more than one lesson per ability, or the same task type would repeat | [variety.md](references/variety.md) |
| Delivery checks | the course has screens, pages or media a learner opens | step 5 |

Before any unattended run, read [lessons.md](references/lessons.md): what a real long build learned.

## 4. Teach by what works (each check is what the reviewer tests)

An item that cannot apply (a one-page reference has no spacing) is written "not needed: <reason>"; the user may drop any item, logged.

1. **Backward design.** The proof task is written before the teaching, on material the teaching did not use, so a pass shows transfer, not memory. Check: the part's last item is the proof task from the map, and its material appears nowhere earlier.
2. **Worked example before independent work.** Show a full solution, then a partly done one, then a blank one. Check: the first task is never cold, unless the part is a deliberate "try first, then teach" draw.
3. **Practice with feedback.** The learner does the task and sees what was right and wrong right after committing an answer. Where luck moves the result, the process is graded apart from the outcome. Check: every task has its answer key or rubric and the reason, opened only after the attempt.
4. **Retrieval and mastery.** The learner recalls before rereading. A failed proof sends the learner back to practice on fresh items, and what needs that node waits. Check: each part after the first asks for something from an earlier part, from memory; every proof names its pass mark and its retake path.
5. **Spacing.** Earlier abilities come back at growing gaps across the learner's real calendar. Check: the plan lists, per node, the later parts where it returns.
6. **Real material.** Tasks use real cases, data or tools of the field. Check: the material is named and stored, or the task says it is invented and why.
7. **Honest prerequisites.** The first page says what the learner must already be able to do. Check: every node that needs nothing before it appears in that list.
8. **Medium follows the proof.** Text for reasoning and reference, video for motion or a real moment, audio for listening and voice, interactive for a control the learner moves, live for judgement in front of people. Check: each part's medium names the reason. "Learning styles" are no reason; the evidence does not support them.

## 5. Delivery: design, interface, performance, accessibility

For anything a learner opens (a page, an app, a deck, a video, a print file; plain text: item 2 only), run the seven checks in [delivery.md](references/delivery.md): one design file first, the learner's path, phone and desktop, a performance budget, WCAG 2.2 AA, taste, and a check of the rendered thing. **Done when** each check that applies has its proof (screenshots, measurements, zero checker errors).

## Final response

One line per file written; the plan as played back and the user's answer; the step table from step 3; the map's numbers (nodes, longest chain, total minutes); the base rate beside any goal, with its source; for an unattended build, the goal prompt in one fenced `text` block; then the defaults taken and the steps the user must do first.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
