---
name: sigmaclimb
description: Use when asked for sigmaclimb (earlier names sigmaspeedloop, speed loop, hill climb) or to make anything measurable or judgeable better one kept-or-reverted change at a time (a speed, a size, a render, a look, a text). Owner interview, profile, locked scorer, quality check. Do not use for code review, bug hunts or a goal nobody can score or judge.
---

# SigmaClimb

SigmaClimb turns "make X better" into a loop that a scorer judges. Each pass makes one change. A scorer the agent
cannot edit says keep or revert. What the owner protects may not get worse. The loop finds where the time (or the
cost, or the flaw) sits first, and attacks the biggest part.

It works for any goal in any field: a frame rate, a file size at the same quality, a film's look, a book, a build,
a served model. The method names the parts of a loop; an interview with the owner fills them in. No field, unit or
number of one project is built in. [examples.md](references/examples.md) shows six fields side by side. The template's
worked example is a served model: [example](references/example-model-serving.md), [evaluator](references/evaluator.md), [setup](references/setup-vast.md), [case study](references/case-study-la125.md).

One agent runs the loop from start to end. It starts no sub-agent: not for research, ideas or a second opinion.
A judge model may still be the measurer (a scored call with a fixed question). The skill is host-neutral: any agent
that can run a shell, keep files and wait on a background job can drive it. Long unattended runs use the host's own
loop mode ([loop.md](references/loop.md)). Use the shell native to the machine.

## The seven parts of every loop

A part is a slot in the loop, not an agent. The interview fills every slot and writes the answers to `project.json`.

| Part | What it holds | Default when the owner says "recommended" |
|---|---|---|
| **Target** | the thing that is changed: a program, a file, a recipe, a text | what the owner points at |
| **Score** | what must get better, and in which direction | the owner's own words, made countable |
| **Guards** | what may not get worse, each with how much worse still counts as the same | the quality the owner names; side effects on every other probe |
| **Measurer** | whatever turns two versions into better, same or worse: a script, the owner picking blind pairs, a judge | a script when a number exists; blind pairs when it does not |
| **Noise** | how much the measurer moves when nothing changed | 3 runs of the unchanged target |
| **Budget** | the time and money of one pass and of the whole run | measured on the first run, then agreed |
| **Stop rule** | when the loop ends | the owner says stop, and `REPORT.md` exists |

Numbers come from measurement, not from this file: the smallest gain that counts is twice the measured spread; a
confirmation run is needed only when the gain is under twice that; the quality check takes at most a quarter of a
pass; after 3 passes without a win in one idea category, the loop changes category. Each is a setting in
`project.json` with its reason, and the owner may change any of them.

## Rules for every target

- **One change per pass**, made by a script or a patch. Bundles of small changes lose.
- **Fix the work, then time it.** Same output size, same steps, same instances in every run. The scorer measures; the
  target never reports its own score. Raw outputs are saved per run, and the verdict reads them, never a summary.
- **Measure first.** Stage 1 runs every score probe. Only a stage-1 win gets stage 2, the quality check, on the
  same running target. A change that cannot alter the output (order of work, caching, scheduling) still gets it once.
- **Size the quality check to the target.** A frame comparison takes seconds; a full model eval takes minutes. If
  it takes more than a quarter of a pass, make it cheaper or ask the owner.
- **Same state for both sides.** A fixed warm-up before the measured part, the same for champion and candidate. Never
  "fresh and empty" by default: a cold start adds noise. If cold and warm both matter, measure both, as two probes.
- **A/B on one live target** when the change can be switched at run time: ABAB, interleaved. It costs minutes and
  cancels drift. A 10-minute kill test like this comes before a scored pass whenever the idea allows it.
- **One probe uses new input every run**: new text, a new scene, a new instance, with the same amount of work. A probe
  that repeats its input measures the cached path only.
- **Side effects count.** An idea that only one probe can show still runs the whole score. A probe with weight 0 is a
  guard: it never scores, but it may not drop past its noise band.
- **Bands come from the noise runs**, never from zero.

## How a run cheats, and the block

| Shortcut | Block |
|---|---|
| Edit the scorer, its inputs or its parser | Hash lock in `evaluator.lock`; any edit makes the pass VOID |
| Do less work (shorter output, fewer steps, lower precision) | Fixed work per probe; the quality check; the invariants list |
| Reuse results left by an earlier run | A fresh seed or salt per request; the new-input probe |
| Best of N runs, or re-run until it wins | One verdict per pass; at most one confirmation; every run saved |
| Win by luck on a noisy machine | The noise floor; champion and candidate in the same state |
| Buy the win with more memory, clock or cores | Invariants; peak use recorded |
| Claim a result it did not run | Raw files under `runs/<id>/raw/`; the verdict reads them |
| Tune to the visible inputs | The new-input probe; the held-out check where the owner wants it |

## The held-out check

Off by default. It runs the same quality check and score on inputs the loop never tuned to, on the same machine as
the candidates. Modes in `project.json`: `off`, `advisory` (it reports, never blocks) and `required` (only when
the owner opts in, in his own words, in the interview). It answers `PASS`, `FAIL quality` or `FAIL gain`, and it
self-tests on the unchanged champion before first use: a check that fails the champion is broken, not strict. The
owner's word promotes in every mode (`verdict.py promote ... --owner "<his words>"`). When the owner has his own
machine, his run there is the held-out check: say that first. Details: [held-out.md](references/held-out.md).

## The phases

1. **Interview.** One round of questions to the owner, each with a recommended answer and its reason; "all
   recommended" is an answer. Run the target once or twice first, so the defaults come from measurement.
   Use `/grilling` when it is installed. The questions: [interview.md](references/interview.md). Output:
   `SPEC_DRAFT.md`, signed off with a "yes", and `project.json`.
2. **Scaffold** one project folder from [assets/project-template/](assets/project-template/). Its README says which
   files are the generic core and which belong to the worked example, and what to replace for another target.
3. **Bring up and lock.** Start the target once, record the quality references, run the unchanged target `repeats`
   times (the noise runs), then `aa.py` writes `evaluator.lock`. After the lock, an edit to the scorer is a
   migration: log it and measure the champion again.
4. **Profile.** Find where the score goes before any idea runs. Output: a table of the target's parts with their
   measured share of the score (time per stage, bytes per stream, flaws per chapter), in `PROGRESS.md`. Every idea
   names the part it attacks. Refresh the profile after each KEEP and at every plateau.
5. **Loop** until the stop rule holds, then write `REPORT.md`.

Never skip the interview or the lock. A scorer rebuilt after pass 1 throws away every result measured before it.

## Phase 5: the loop

`GOAL.md` holds the pass procedure. Each pass:

1. Take the `pending` idea with the highest **share x odds**: the share of its part in the profile times its chance
   of success (`p=NN%`). Search `results.tsv` and `ruled_out.tsv` first; a repeat costs a whole pass.
2. `candidate/` = the champion plus ONE change. Run `run_experiment.sh`: stage 1, and stage 2 only on a win. Keep a
   background waiter alive; never poll.
3. `verdict.py` decides; `record.py` writes the results row from the raw files. `STAGE1-WIN` is never a KEEP.
4. A KEEP becomes the champion with `verdict.py promote`. It needs the quality check, one confirmation run when the
   gain is small, and the held-out check only in `required` mode. Every scored verdict prints two numbers: against
   the champion before, and against the start.
5. One run and at most one confirmation per idea. Then show the table and move on. A dead idea goes to
   `ruled_out.tsv` with what it rules out and the condition that reopens it. One line to `insights.md`.
6. At a KEEP and at the end: commit, `plot_progress.py`, rewrite `PROGRESS.md` (champion against the start and the
   owner's current setup). Not after every pass.

**Idea queue.** Rank by share x odds, never by age. At least every third pass (`bold_every`) is a code or design
change, not a setting: structural work is wanted, and bold ideas are where the big gains live. A bold idea gets a
spike of up to two hours with a dry test that needs no target, before it costs a pass. An effort estimate is a guess:
read the target's source, and build the first hour of a "days" idea before you believe the estimate. After
`category_switch_after` passes without a KEEP in one category, change category and profile again.

**Habits that pay.** Each row states the part, the hypothesis and the evidence. When two changes score the same,
keep the one that deletes code. Write each result so a fresh session can learn from it: what changed, why, what
happened, what it rules out. More: [lessons.md](references/lessons.md).

**Finish.** When the stop rule holds, write `REPORT.md`: what changed for the owner first, then every pass in plain
words, the champion against the start, the final recipe and its diff, what failed and why, what to try next.

## Talking to the owner

- Use plain words, never the skill's own: [plain-words.md](references/plain-words.md) maps each term to a phrase
  ("KEEP" is "the change is better and stays"). Say what a thing does before you name it.
- Every report starts with what changed for the owner. Short sentences, tables for numbers, and say what is not
  done or not verified. Never claim a gain from one noisy run.
- Decide what a rule decides; do not hand decisions back. A real choice comes as a table with a recommended answer.
- Every turn ends with the status line of `scripts/status.py`. It also measures the loop: minutes per idea, minutes
  from a KEEP to its champion, and the share of a pass that measures the score. Under half: fix the loop before the
  next idea.

## Final response

At the end of a phase or a pass: what changed for the owner, the verdict with its two numbers, the next step, and the
status line.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
