---
name: sigmaclimb
description: Use when asked for sigmaclimb, a speed loop or a hill climb, or to make anything measurable or judgeable better one kept-or-reverted change at a time (a speed, a size, a render, a look, a text). Owner interview, profile, locked scorer, quality check. Do not use for code review, bug hunts or a goal nobody can score or judge.
---

# SigmaClimb

SigmaClimb turns "make X better" into a loop that a scorer decides. Each pass makes one change. A scorer the agent cannot edit says keep or revert. What the owner protects may not get worse. The loop first finds where the time (or the cost, or the flaw) sits, then attacks the biggest part, for an hour or with no end date.

It fits the speed of a served model (language, image, video, voice), a build, a file size, a render, a text such as a two-minute stock pitch. [examples.md](references/examples.md) holds eight fields, two worked loops and the lessons.

**The measurer is a script or the owner.** A script gives a reproducible number, a diff or a mechanical check. Where no number exists, the owner, or people he names, pick between blind pairs (`measurer: pairs`). A model never scores or passes content.

## Musk's Algorithm (run in order before starting)

1. "Make the requirements less dumb. The requirements are always dumb to some degree [...] no matter how smart the person who gave you those requirements [...] otherwise you could get the perfect answer to the wrong question."
2. "Try to delete whatever the step is, the part or the process step. [...] If you're not forced to put back at least 10% of what you delete, you're not deleting enough."
3. "Only the third thing is try to optimize it or simplify it. [...] The most common mistake of smart engineers is to optimize a thing that should not exist."
4. "Any given thing can be sped up. [...] But you shouldn't speed things up until it's optimized."
5. "The fifth thing is to automate it. I have gone backwards so many times where I automated something, sped it up, simplified it, and then deleted it."

## The seven parts of every loop

The grill fills each part and writes it to `project.json`.

| Part | What it holds | Default when the owner says "recommended" |
|---|---|---|
| **Target** | what is changed: a program, a file, a recipe, a text | what the owner points at |
| **Score** | what must get better, and in which direction | his own words, made countable |
| **Guards** | what may not get worse, and how much worse still counts as the same | the quality he names; side effects on every other probe |
| **Measurer** | what turns two versions into better, same or worse | a script when a number exists; blind pairs when not |
| **Noise** | how much the measurer moves when nothing changed | 3 runs of the unchanged target |
| **Budget** | the longest one command and one pass may run; the hours and money of the run | from one timed run, agreed before anything else runs |
| **Stop rule** | when the loop ends | he writes a `STOP` file, or `run_hours` is used up; then `REPORT.md` |

Every threshold is a setting in `project.json` with its reason, derived from measurement (the smallest gain is twice the measured spread); the owner may change any.

## Rules for every target

- **One change per pass**, made by a script or a patch. Bundles of small changes lose.
- **Fix the work, then time it.** Same output size, steps and instances in every run. The verdict reads the run's raw files, never the target's own report.
- **Score first.** Stage 1 runs every score probe. Only a stage-1 win gets stage 2, the quality check, on the same running target. A check over a quarter of a pass: make it cheaper or ask the owner.
- **Same state for both sides.** One job at a time on the machine and one fixed warm-up; cold and warm are two probes when both matter. A live switch gets an ABAB test of minutes on one running target first. Where a restart lets drift rival the gain, bracket the change (control, candidate, control); it must beat both.
- **One probe takes new input every run**, with the same amount of work. A probe that repeats its input measures the cached path only.
- **Side effects count.** Every pass runs the whole score. A probe with weight 0 is a guard: it never scores, and it may not drop past its band. Bands come from the noise runs, never from zero.

## The loop cannot hang

An unattended run dies from a command that never returns, or a turn that ends with nothing set to wake it. Detail per harness: [run.md](references/run.md).

1. **Every command has a cap.** Every test, scorer and eval runs through `climb.py run`, which kills a step at `budget.step_seconds` and a pass at `budget.pass_seconds`. A killed step is a CRASH: revert, one row, next idea. The same idea killed twice is dead.
2. **A pass is atomic.** Champion plus one change, measured, then KEEP (promote, commit) or revert. It always ends with one new `results.tsv` row and the target equal to the champion.
3. **State lives in files** (`climb.md`, `results.tsv`, `ideas.tsv`, `state/`), never in the agent's memory.
4. **Scope anchor.** The first lines of `climb.md` name Target, Score, Guards and Out of scope. A side quest becomes an `ideas.tsv` row.
5. **End a turn while a command runs only when the harness will wake you.**
6. **Watchdog:** the harness's own. On a wake run `python climb.py status`; `LOOP STALLED` means kill the pass, record a CRASH, take the next idea.
7. **Every turn ends with the status line.**

## One agent or a crew

The owner picks, in the first grill question. In a crew, one orchestrator owns `climb.md`, `results.tsv`, `ideas.tsv` and the champion; each worker returns one candidate; two measurements never overlap on one machine; only the orchestrator promotes. Compute is the local machine first, else the skill `sigmacollab`. Crew shapes and the long-run prompt: run.md.

## The phases

1. **Grill.** Time the unchanged target once, then one round with the owner: [grill.md](references/grill.md). It asks first for one agent or a crew and for how long, then for the time budget: the longest any test or scorer command may run, and the longest a pass may take. Done when he says "yes" to the written answers.
2. **Scaffold** one project folder from [assets/project-template/](assets/project-template/). The target's shell commands (start, warmup, score, quality, stop) go into `steps` of `project.json`; rename `_gitignore` to `.gitignore`; fill the scope anchor of `climb.md`.
3. **Bring up and lock.** Run the unchanged target `repeats` times (`climb.py run ... --full`); `climb.py lock` then writes the noise bands and the hash lock. After the lock, an edit to the scorer is a migration: log it and measure the champion again.
4. **Profile.** Measure where the score goes, part by part, and the ceiling from measured hardware when one exists. Write the table to `climb.md`; say early if a target sits above the ceiling. Every idea names the part it attacks. Refresh after each KEEP and at every plateau.
5. **Loop** until the stop rule holds, then write `REPORT.md`. Ideas run in order of share x odds (the part's share of the profile times the odds it wins), and only `climb.py verdict` decides. The pass, the verdicts, how a run cheats and the block, the held-out check (off by default), steering, research and hand-off: [loop.md](references/loop.md).

The grill and the lock come before pass 1: a scorer rebuilt later throws away every result measured before it.

## Talking to the owner

- Say what a thing does before you name it, in plain words, never the skill's own: "KEEP" is "the change is better and stays" (the word list is in loop.md).
- Start with what changed for him; say what is not done or not verified. One noisy run is not a gain.
- Decide what a rule decides; a real choice is one table with a recommended answer.

## Final response

What changed for the owner, the verdict with its two numbers (against the champion before, against the start), the next step, the status line.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
