# Owner grill

One question round fills `project.json` and `SPEC_DRAFT.md`. Run `/grilling` when installed, using this list. Ask all questions in one numbered message. **"All recommended"** (option 1 everywhere) is a complete answer: log each default as a `Ruling:` line and start.

## Before you ask: measure once

Run the unchanged target once or twice first and time every step (`start`, `warmup`, `score`, `quality`, `stop`). Defaults come from that trial run, never from another project. Check the host's live model list or the repo's model page so Question 1 recommends models the host offers.

## Question shape

Every question offers four options:

1. **Best-practice default (Recommended)**: a general rule across fields.
2. **Project-fit default**: drawn from the trial run, the repo, or the owner's words.
3. **Wildcard**: one creative, practical suggestion worth considering.
4. **Write your own.**

Example (fill with the trial run's numbers):

> **2. Hard time budget.** Cap for one command (`budget.step_seconds`) and one pass (`budget.pass_seconds`) before `climb.py` kills it as `CRASH`?
> 1. *(Recommended)* `step_seconds: 120`, `pass_seconds: 300`: 3x slowest trial step (40 s) and 3x trial pass (95 s).
> 2. `step_seconds: 60`, `pass_seconds: 180`: a tighter cap matching low trial variance (38 s, 40 s).
> 3. Fast screening: `step_seconds: 45` on a smaller stage-1 probe, full probe only on `--full` wins.
> 4. Write your own.

## Question 1: Crew size and run length

Ask this first. It chooses single-agent or multi-agent and sets `budget.run_hours` (an hour cap, or `null` until the owner writes `STOP`).

- **Single agent:** Read the host's live model list (or repo model page) and recommend which offered model fits best and why (speed, depth, context, quota). Never guess a model id.
- **Multi-agent:** Compute candidate shapes from the work and machine, such as **2 parallel**, **3 + 1 orchestrator**, or **5 + 1 orchestrator**, and pick a workspace topology:
  - **One shared worktree and branch:** only when tracks touch separate files and commit by path.
  - **One worktree per agent:** default for local parallel edits and builds.
  - **Remote compute per agent** (`sigmacollab`): when measuring on one machine would overlap or local hardware cannot hold parallel runs.
- **What decides:** independent idea tracks, free CPU cores and memory, and whether timing runs collide on one machine ([run.md](run.md)).

Feeds for options 1–3:
- **1:** Single agent on the best live model for serial tracks or one measurement slot; `3 + 1` in separate worktrees when tracks split cleanly. `run_hours: null` (until `STOP`) or an overnight window.
- **2:** Crew size capped by measured trial load and free cores; `run_hours` matched to the owner's deadline.
- **3:** `2` or `5 + 1` on remote compute per worker (`sigmacollab`) so each worker measures on its own machine.

## Question 2: Hard time budget

Ask this second. It sets `budget.step_seconds` (per `steps` command) and `budget.pass_seconds` (whole pass).

State plainly: **`python climb.py run` refuses to start until both are numbers. Over either cap, `climb.py` kills the process tree and marks the pass `CRASH`, never waited on.**

Feeds for options 1–3:
- **1:** `step_seconds` = ~3x slowest measured trial step; `pass_seconds` = ~3x measured trial pass.
- **2:** Cap tuned to trial jitter and slowest stage (`warmup`, `score`, or `quality`).
- **3:** Tight stage-1 probe cap for fast screening, longer cap for `--full` checks.

## Questions 3–10: The seven parts and logistics

Skip questions the owner already answered; echo those for confirmation. Skip what loop rules decide (one change per pass, bold design change every third pass, category switch after 3 passes without a win, revert on `CRASH` or `REJECT`).

| # | Topic & key | Option 1 (Best-practice) | Option 2 (Project-fit) | Option 3 (Wildcard) |
|---|---|---|---|---|
| 3 | **Target & invariants** (`steps`) | Change only what the owner named; lock the rest | Files, flags, or sections found in the repo | Delete unused parts or steps first (Musk step 2) |
| 4 | **Score** (`steps.score`) | Owner's goal made countable on real inputs; ranked weights, unranked probes are weight-0 guards | Workload, sizes, or probes from the trial run | Fresh-input probe changing every run |
| 5 | **Guards** (`steps.quality`) | Quality holds within noise; check <= 25% of a pass | Existing tests, diff, or mechanical check in the repo | Fast proxy guard on stage 1, full check on `--full` |
| 6 | **Measurer** (`measurer`) | `script` when a number exists; `pairs` when not | Existing benchmark, profiler, or blind-pair rubric | Mechanical script guards plus owner blind pairs |
| 7 | **Noise & held-out** (`repeats`, `min_gain`, `heldout`) | `repeats: 3`, `min_gain` = 2x spread, `heldout: off` | Higher `repeats` if trials drifted; owner's machine as held-out | `heldout: advisory` on a second input set |
| 8 | **Money budget** | Local ($0); if rented, spend cap plus meter command | Live `sigmacollab` rate times planned `run_hours` | Cost cap per KEEP |
| 9 | **Stop rule** (`budget.run_hours`) | `STOP` file (or `run_hours` elapsed) and `REPORT.md` | Specific target score or wall-clock time | Stop after N passes without a KEEP |
| 10 | **Keys & machines** | Secrets in `secrets/` (path only, never printed); owner's other machines untouched; git on | Host, branch, and credential paths in this workspace | Run timed passes on an isolated rented box (`sigmacollab`) |

## When no number exists (blind pairs)

**A model never scores or passes content.** The measurer is a script (a reproducible metric, diff, or mechanical check) or human blind pairs (`measurer: pairs`).

For a goal with no number (a two-minute pitch, a visual look, prose flow), show two real versions (the start and one quick change) and ask:

> **"Here are two versions. Which is better, and what did you look at?"**

- Record the answer verbatim as the fixed pair question.
- Set `"measurer": "pairs"`. The owner (or people he names) picks between champion and candidate on the same input in random order, labels hidden.
- Run mechanical guards as scripts (length, reading time, facts kept, format).
- Use `sigmacreatearena` for blind-pair mechanics; run A/A pairs (champion vs itself) for noise.

## Sign-off

1. Write answers to `SPEC_DRAFT.md`, adding `Ruling: <what> - <why> - <cost if wrong>` per default taken.
2. Write `project.json` (`steps`, `budget`, `measurer`, `repeats`, `min_gain`, `heldout`).
3. Get the owner's `"yes"` before scaffolding or locking ([loop.md](loop.md)).
