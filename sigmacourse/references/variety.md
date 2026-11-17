# Variety

Variety exists so the learner can use an ability on material they have not seen. Draw it from the map, never from a template: the number of shapes, task types and media follows the number of lessons and what each proof needs.

Each lesson declares four fields in its front matter, and a script checks the mix:

- `shape:` one lesson shape;
- `tasks:` one or more task types;
- `level:` the hardest item in it, on the ladder below;
- `media:` the media pieces it carries, each with a spec id.

Draw at random from the shapes that fit the lesson's node, seeded by the lesson id, so a rerun gives the same draw. The writer may override a draw that does not fit and logs why (`mix_override: <reason>`). The page frame stays the same (where the video sits, where the task sits, where the answer opens); the content does not.

## Shapes (examples; the grill drops, renames and adds in the field's words)

Work first, then teach · Guess, then reveal · Hunt for something hard to find in real material · Error hunt in real work · Guided build with checkpoints · Derivation with a problem set · Timed drill · Read a real document, then decide by a deadline · Case discussion · Compare a success and a failure from the same start · Book chapter, then a task · Video that pauses and asks · Long lecture · Documentary · Teacher debate · Interview a teacher · Oral defence · Explorable (move a control, see the effect) · Branching scenario · Quick mixed quiz · Write or teach back · Field task revisited later · Explain, example, practice (for fast basics).

## Task types (examples)

In your head · pen and paper · spreadsheet · recall from memory · predict before the reveal · estimate · spot the error · rank or sort · build from blank · write · speak · teach back · timed drill · open-book research · capstone · pick the best of several strong candidates · decide with a deadline.

## Levels

An ordered ladder; the grill renames it for the field: recognise · recall · explain in your words · apply to a worked example · do it on real material · analyse a real case with no clean answer · exam level of the field's best schools · working-professional level · senior-expert level · live decision under real uncertainty. Each part sits higher on the ladder than the parts it needs, and the end lines set the top.

## Sameness checks (script, per unit of progress the spec names)

1. No two lessons in a row share a shape, when the unit has more than one shape that fits.
2. No fixed opener or closer: flag the same first-sentence pattern, heading sequence or closing line in consecutive lessons.
3. Case outcomes stay hidden until the learner commits, in no fixed order, and some cases surprise (the obvious call failed).
4. Old abilities come back in quizzes and cases, as the spacing plan in SKILL.md step 4 lists.
5. A lesson fits the learner's real sitting length (the grill asks); longer work splits into sittings.

The reviewer, not a script, judges: does the lesson teach one thing well, and would the learner know what to do at once?

## Case files

When the field has cases (a past decision, a performance to diagnose, a bug), spread them on axes that a schema check counts: kind, outcome band, how much help, length, how much calculation, sub-field, region and era. Curated cases show the base rate of their kind beside them; a set of unpicked cases shows the real distribution.

## Media

A piece of media earns its place by teaching what text cannot: a demonstration, a real moment on tape, a mechanism in motion, a voice. One that reads the text aloud fails review. Every piece ends in active work. Kinds to draw from: a film per module, a lesson video, a slice of real footage, a long lecture, a short explainer, an animation from calculated data, a 3D shot where depth teaches, an audio version, diagrams and charts. Generated images serve atmosphere only, never data.

When the user names a lecture they love, fetch it, check its title, date and length, and write it as the rubric for long lectures. Estimate render hours from measured speeds before an unattended run.
