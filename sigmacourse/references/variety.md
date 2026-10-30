# The variety system

A lesson is not one template. Each lesson declares four fields in its front matter, and a script checks the mix per block (a block is a unit of progress, for example one month of study):

- `shape:` one lesson shape (below);
- `tasks:` one or more task types;
- `level:` the hardest item in it, L1–L10;
- `media:` the media pieces it carries, each with a spec id.

The mix is drawn at random inside the ranges, seeded by the lesson id, so a rerun gives the same draw. The writer may override a draw that does not fit the learning goal and logs why (`mix_override: <reason>`). The page frame stays the same (where the video sits, where the task sits, where the answer opens). The content does not.

Scale: S uses 3–6 shapes and diagrams only; M uses about 10 shapes and lesson videos; L and XL use the full catalog.

The grill adapts every table to the subject: drop shapes that do not fit, rename them in the field's words, add missing ones. Keep the ranges summing to 100% per block.

## Lesson shapes

| Shape | What the learner does | Range per block |
|---|---|---|
| Work first, then teach | Attempts a real problem cold; the teaching answers what they got stuck on | 8–15% |
| Guess, then reveal | Writes a number or a call with a probability; the data opens after | 6–12% |
| Hunt | Finds something hard to find in real material | 4–8% |
| Error hunt | Finds the mistake in a real piece of work | 3–6% |
| Guided build | Builds a thing step by step with checkpoints | 8–12% |
| Two pages of maths or theory | Works a derivation and a problem set; a calc script holds the answers | 4–8% |
| Timed sprint | A drill under a clock | 2–5% |
| Read, then decide | Reads about five pages of a real document and decides by a deadline | 6–10% |
| Case discussion | A case, three questions, the learner's decision, then the teacher's call | 5–10% |
| Compare two | Two cases from the same start, one success and one failure | 3–6% |
| Book task | One chapter of a course book, then a task on real material | 2–5% |
| Video with in-video questions | The video pauses and asks; the answer is logged | 8–12% |
| Long lecture | 30–60 min with real examples, at the lecture bar the user named | 3–5% |
| Documentary | A narrated story of a person, a work or an era | 2–4% |
| Teacher debate | Two or three personas argue a real case; the learner moderates and rules | 3–6% |
| Interview a teacher | A persona session with a goal and a time limit | 2–5% |
| Oral defence | The learner defends their work to a persona | 2–4% |
| Explorable | Moves a number or a control and sees the effect, then answers | 3–6% |
| Branching scenario | A hard moment with choices and consequences | 1–3% |
| Quick quiz | Interleaved retrieval across old topics | 3–6% |
| Write or teach back | Writes a card, a section or a short lesson of their own | 2–5% |
| Field task | A live, real task whose outcome is unknown, revisited later | 1–3% |
| Teach, then do | The classic explain-example-practice lesson; for fast basics only | 0–15% |

## Rules that stop sameness (checked by script, per block)

1. No two lessons in a row share a shape. No shape three times in any five in a row.
2. At least 10 different shapes per block.
3. Every week holds at least one active-first lesson (work first, guess then reveal, hunt or error hunt), one video-led lesson, and one where a teacher speaks in their own voice.
4. A floor on interactivity patterns and visual kinds per block (set in the grill).
5. No fixed opener or closer: flag the same first-sentence pattern, heading sequence or closing line in three lessons in a row.
6. Case outcomes stay hidden until the learner commits, in no fixed order. At least one surprise case per block (the obvious call failed, or the bad one won).
7. Old topics come back: at least 20% of a block's quiz and case items come from earlier blocks.
8. Time follows shape: 10–60 min for most, up to 90 for a long lecture. Longer work splits into sessions of at most 90 min.

The reviewer, not a script, judges: does the lesson teach one thing well, and would the learner know what to do in the first 30 seconds?

## Task types

Every lesson names at least one; each block uses at least 12. In your head · pen and paper · calculator · spreadsheet (template given) · recall from memory · predict before the reveal · estimate (Fermi) · spot the error in real work · rank or sort · build from a blank page · write · speak · teach back · debate a teacher's persona · timed drill · open-book research · combined capstone · hunt hard-to-find information · pick the best of several strong candidates · decide with a deadline and a default.

## Levels

L1 recognise · L2 recall · L3 explain in your words · L4 apply to a worked example · L5 do it on real material · L6 analyse a real case with no clean answer · L7 top-university exam level · L8 working-professional level (real data, a deadline) · L9 senior-expert level · L10 live decision under real uncertainty. Levels scatter through every week and the floor rises by block (the grill sets when L6, L7 and L8 become weekly).

## Case files

Spread on axes; each axis is a table of shares that a schema check counts. Default axes:

- **kind** (field-specific: the teacher's own decision, the work as the case, a framework applied, a pass or miss, a failure or fraud, an autopsy, holding through a hard stretch, a live case);
- **outcome band**: equal shares, for example trash, bad, okay, good, legendary;
- **help**: H1 guided with point-in-time material · H2 light prompts · H3 no help · H4 hard workbook with several strong candidates, then compare with the teacher's pick and with what happened;
- **length**: snack 15–30 min · standard 1–2 h · deep 3–5 h · workbook 8–15 h;
- **calc**: none, light, full model (a floor share must compute something; answers from a calc script);
- **spread**: sub-field, region, era.

Curated case files teach, so each one shows the base rate of its kind beside it. A separate set of unchosen replays (sampled without picking winners) shows the real distribution.

## Media

| Tier | What it is | Typical tool |
|---|---|---|
| A flagship film | 10–30 min, one per module, documentary quality | HyperFrames or the user's video pipeline, narration, real footage |
| B lesson video | 1–15 min, one in every lesson | HyperFrames slide lecture or animated explainer from the finished lesson |
| C real footage slice | 3–15 min of a teacher's own talk, intro card and 2–3 questions | download, SigmaDeepLook transcript, cut at sentence ends |
| D long lecture | 30–60 min with real examples, at the named bar | persona script, HyperFrames, cloned voice, footage |
| E live explainer | 1–3 min, a teacher explains one point with a likeness | the user's video generator |
| F persona vlog | 1–3 min, a teacher talks to the learner about their block | likeness and cloned voice |
| G animation | under 2 min, a mechanism in motion | HyperFrames, numbers from calc data |
| H 3D shot | about 1 min where depth teaches | Three.js or the user's 3D tool |
| I case intro | 2 min that sets the scene as of the decision date | HyperFrames, footage of the time |

Audio: an audio version per lesson, dialogues in cloned voices (the user's voice tool). Diagrams and charts in every lesson (load `dataviz` before any chart). Generated images for atmosphere only, never for data.

**The video-per-lesson rule.** Every lesson has a video, and it teaches what the text does not: a demonstration, a real moment on tape, a mechanism in motion, or the teacher's own voice. A video that reads the lesson aloud fails review. Every video ends in active work.

**The long-lecture bar.** The user names one lecture they love. Fetch it, check its title, date and length, and write the bar as a rubric before the first long lecture.

**Render load.** Estimate GPU and machine hours per tier from measured speeds before the loop starts; batch heavy jobs into night windows when a machine is shared.

## Budget script

Every count and hour total above comes from one script (`tools/course_budget.py`), never from prose. To change a number, change the script, rerun it and paste the table.
