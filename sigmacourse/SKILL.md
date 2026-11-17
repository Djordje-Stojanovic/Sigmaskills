---
name: sigmacourse
description: 'Use when asked for sigmacourse or to plan or build a tutorial, guide, course or curriculum of any length, subject, audience or medium. It starts from what the learner can do at the end, derives the parts and its own process from that, and covers delivery: design, interface, performance, accessibility. Do not use for live tutoring.'
---

# SigmaCourse

Plan and build teaching of any size, on any subject, for any audience, in any medium. The course decides how much process it gets. Nothing here sorts a course by length: a one-pager ends with almost no process and a program of a thousand hours with a lot, because each step below runs only when the course itself needs it. When a local skill builds courses with your own stack, use it to build; it runs steps 1 to 3 here first.

## Operating contract

- **The user decides.** Subject, size, depth, voice, media, real people as teachers, generated likenesses: all the user's call. Add no limits of your own. The newest word wins over every default here; when it clashes with a rule, say once what it costs, then do it. The only confirm: an action that deletes the repo or publishes a secret. Save the user's words verbatim.
- **One question at a time, your pick first.** The recommended answer and its reason, then the other options. Ask only what changes the plan. "Just build it": draft every answer as a guess and ask for corrections once.
- **Realism.** Every number has a source or a stated assumption. Every goal sits next to its real base rate. Counts and sums run in a script, never in prose. No secrets in any file, brief or prompt. Plain words: short sentences, one idea each, active voice.

## 1. The end state

Write one line per separate ability the learner must have at the end: "At the end, the learner can <do what> on <real material> to <what standard>." Two lines are separate when a learner could have one without the other. The size is the learner time the user names, on any scale; when they name none, the map sets it. **Done when** every line names a real task, real material and a standard someone else could judge.

## 2. The ability map

1. Under each end line, write what the learner must be able to do just before it. Repeat for each new line until you reach what the learner can already do. Ask when you do not know. Merge duplicates: one ability, one node.
2. For each node write: the proof task, the practice it needs (how many tries, with feedback, before the proof is likely to pass; an estimate with its reason), and the medium the proof needs (step 4).
3. Give each node its minutes: teach, practice, proof. Reading and speaking time come from a rate you state for this audience, video from its real runtime. A script sums the minutes and counts the nodes and the longest prerequisite chain (one node needs no script).
4. Fit the size. Over it: cut practice on the easiest nodes first, then the end line that matters least to the user; say which. Under it: finish short and say so, or, if the user wants the full size, add practice on the hardest nodes. Never pad with new topics.
5. The outline is the map in order: each node after what it needs. One new idea per part. Nothing goes in that no end line needs. **Done when** the script prints the node count, the longest chain and the total minutes, and every outline item names the end line it serves.

## 3. The process the map needs

Read the map, then run each step whose condition is true. Write the result as a short table: step, true or false, the fact from the map that decided it. That table is the proof that the course, not a size, chose the process.

| Step | Run it when | Tool |
|---|---|---|
| Write in place, one file, the outline at its top until done | the writer can draft and check all of it in one sitting | this skill |
| Plan file `course-plan.md` (end state, map, outline, media, sources) | the writer cannot, so the map must live outside the draft | this skill |
| Grill | an open answer would change a node, an order, a proof or a medium. Ask only those areas | [grill.md](references/grill.md) |
| Placement check | the learner's start is unknown and some nodes may already be known | a short test on those nodes |
| Spaced review | the learner time spans more than one sitting | step 4 |
| Research | the course states a fact the user's sources do not hold | [research-and-books.md](references/research-and-books.md) |
| Fresh review by an agent that did not write it | always; its size follows the map (one read for one node, a batch review per part for many) | SigmaReview lenses |
| Spec, done list, user sign-off | the build needs more than one agent session, so others must work from a written contract | [repo-setup.md](references/repo-setup.md) |
| Queue, check script, run file, goal prompt | the build needs more sessions than the user will watch | [repo-setup.md](references/repo-setup.md), [build.md](references/build.md), SigmaLoop ([hosts.md](references/hosts.md)); a decision map (`wayfinder` or `docs/course/map.md`) when open decisions block later parts |
| Personas | the user names real or invented teachers | [build.md](references/build.md#personas) |
| Variety draw | more than one lesson per ability, or the same task type would repeat | [variety.md](references/variety.md) |
| Design system, interface, performance budget | the course has screens, pages or media a learner opens | step 5 |

Before any unattended run, read [lessons.md](references/lessons.md): what a real long build learned.

## 4. Teach by what works (each check is what the reviewer tests)

1. **Backward design.** The proof task is written before the teaching. Check: the part's last item is the proof task from the map.
2. **Worked example before independent work.** Show a full solution, then a partly done one, then a blank one. Check: the first task is never cold, unless the part is a deliberate "try first, then teach" draw.
3. **Practice with feedback.** The learner does the task and sees what was right and wrong right after committing an answer. Check: every task has its answer and the reason, opened only after the attempt.
4. **Retrieval.** The learner recalls before rereading. Check: each part after the first asks for something from an earlier part, from memory.
5. **Spacing.** Earlier abilities come back at growing gaps across the learner's real calendar. Check: the plan lists, per node, the later parts where it returns.
6. **Real material.** Tasks use real cases, data or tools of the field. Check: the material is named and stored, or the task says it is invented and why.
7. **Honest prerequisites.** The first page says what the learner must already be able to do. Check: every leaf of the map appears in that list.
8. **Medium follows the proof.** Text for reasoning and reference, video for motion or a real moment, audio for listening and voice, interactive for a control the learner moves, live for judgement in front of people. Check: each part's medium names the reason. "Learning styles" are no reason; the evidence does not support them.

## 5. Delivery: design, interface, performance, accessibility

Run this for anything a learner opens: a page, an app, a deck, a video, a print file. Scale each item to what exists: a single printed page needs type, layout and contrast; a course site needs all of it.

1. **One design file before the first screen.** Colour, type, spacing and components as tokens; light and dark. Use the project's existing design file when it has one. Else a design skill when installed (`impeccable`, Anthropic `frontend-design`, a Design.md look); else write the tokens yourself. Check: every screen uses only the tokens.
2. **The learner's path.** Every screen shows where the learner is, how far they are against the end lines, and the one next action. The learner can reach any finished part, leave and resume where they stopped. Answers open after the learner commits. Check: walk one learner from the first page to the last proof task with no dead end.
3. **Phone and desktop.** The layout works at the narrowest and widest screens the learner uses, by touch and by keyboard. Check: screenshots at both widths, no sideways scroll, no hidden action.
4. **A performance budget, written before the build.** Set it from the learner's slowest device and network (the grill asks): time until the first lesson is readable or playable, the weight of a page, the start time of a video. Check: measure each page type in the built course (Lighthouse or the browser's own tools); a miss is a defect. To climb a missed budget, SigmaClimb.
5. **Accessibility to WCAG 2.2 AA** (the common web standard). Contrast, readable text size, keyboard use, visible focus, alt text, captions and a transcript for every video and audio, reduced motion honoured. Check: an automatic checker (axe or the browser's own) with zero errors, plus one pass by keyboard only.
6. **Taste.** SigmaTaste on the first screen, chart, film or deck of each kind; act on its top items. Load `dataviz` (or the host's chart skill) before any chart. Video through HyperFrames when installed.
7. **Check the real thing.** Open the rendered course in a browser (`webapp-testing` when installed), play the media, read the console. Check: zero console errors, every page and media file loads, and the screenshots go into the review. A check that reads only source files does not count.

## Final response

One line per file written; the step table from step 3; the map's numbers (nodes, longest chain, total minutes); the base rate beside any goal, with its source; for an unattended build, the goal prompt in one fenced `text` block; then the defaults taken and the steps the user must do first.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
