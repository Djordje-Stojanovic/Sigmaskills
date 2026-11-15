---
name: sigmaclimb
description: Use when asked for sigmaclimb (earlier names sigmaspeedloop, speed loop, hill climb) or to improve anything measurable one scripted keep-or-revert change at a time. Model serving speed, a render, a kernel, an algorithm, a training run. Locked scorer, quality gate, held-out check. Do not use for code review, bug hunts or work with no scoring script.
---

# SigmaClimb

Turn "make X better on measure M" into a loop that a script judges. The agent makes one change per pass. A scorer it
cannot edit (the "evaluator" in the template files) says keep or revert. Quality may never go down. A check on
inputs the agent never sees makes gaming visible.

The method comes from a real multi-day project: Qwen3.8-Flash-Next 125B NVFP4 on a rented DGX Spark, about 110 runs
and 9 champions ([case study](references/case-study-la125.md)). The loop itself does not care what it improves. The
serving details (GPU, vLLM, probes, Vast.ai) are one worked example:
[example-model-serving.md](references/example-model-serving.md). **Read it and [lessons.md](references/lessons.md)
before you rent anything.**

The skill is host-neutral. Any agent that can run a shell, keep files and wait on a background job can drive it. Long
unattended runs use the host's own loop mode; [loop.md](references/loop.md) has the prompt and the host notes. Use the
shell native to the machine: PowerShell on Windows, POSIX shell elsewhere.

## The method: seven parts, for any target

1. **One change per pass**, made by script or patch. Bundles of small changes lost.
2. **A locked scorer.** The scorer runs the target and measures it. Keep its folder read-only to the agent where the
   host allows; a hash in `evaluator.lock` voids the pass on any edit. It reads raw output files, never the agent's summary.
3. **Noise first.** Run the unchanged target at least 3 times before pass 1 (these are the "A/A runs"). The spread sets
   the floor: a gain inside the noise is "inside noise", not a win.
4. **A quality gate.** What may never get worse (answers, pixels, precision, correctness), checked on every pass
   against a reference recorded from the baseline. The gate beats the score.
5. **A held-out check (required).** See below.
6. **Keep or revert.** KEEP needs: gate ok, score beyond the floor, a confirmation run, and the held-out check. All
   else is reverted, except an ARCHIVE (one probe up, one down), which the owner rules on. A failure that can recur goes to `ruled_out.tsv` with the condition that reopens it.
7. **A chart that names who found each champion**, and the machine it was measured on.

## The held-out check (required)

The agent sees every input the scorer uses. After 100 passes against the same inputs, it can have tuned to those inputs.
For a code change (a kernel, a solver, a render) it can also special-case them: hard-code the answers, cache them, or
detect the benchmark. A fixed gate cannot catch that. A held-out check can:

- **Sealed inputs.** A second input set: new seeds, new shapes, new scenes, new instances, new prompts. The owner (or
  a script the loop cannot read) writes it and the runner that uses it. `scripts/bench/heldout.py init` makes the
  folder: inputs mode 0700 under a second user (or on another machine), a results folder the loop can read but not
  write. The agent never opens the inputs. If the target has no such place, the owner runs the check by hand at each KEEP.
- **Pass or fail only.** The runner prints PASS or FAIL and nothing else. A number is a leak: each number tells the
  agent where to push. The loop writes the answer, word for word, in the results description.
- **Same gate, same score.** On the sealed set, the gate must pass, and the score gain must be at least half of the
  gain of the KEEP run (`runs/<n>/verdict.json`), with the same sign. The owner sets the share at `init` (default 0.5).
- **When.** At every KEEP, after its confirmation run, before promotion. Until the PASS the champion stays, and the
  loop tests other ideas on it. One look per KEEP. No look on a REJECT.
- **The code enforces it.** `python scripts/bench/verdict.py promote runs/<n> runs/<confirm>` is the only writer of
  `state/champion.json`. It refuses (one line, with the reason) unless every run is KEEP and a PASS exists for that
  exact change: same run, same change file (`runs/<n>/serve.sh`), same `project.json` and `evaluator.lock`, same score,
  in a results folder the loop's user cannot write, written by the locked `heldout.py`. A champion that did not come
  through `promote` (and is not the A/A baseline) makes every later verdict VOID.
- **Spent means replaced.** After about 10 looks, or if the agent saw the set (a log, an error message), the owner
  builds a new one and the loop says so in `insights.md`.
- **Last look.** The owner runs the final check on the final champion, on his own setup. That is the real truth.

Agree what it holds in phase 4, before the lock. A project with no held-out check is not ready for pass 1: `promote`
refuses without one. The gate holds only when the loop's user and the sealing user differ, or the results folder is a
read-only mount; root can write everywhere, so a loop run as root gets no gate.

## Works for any target

Four things change per project: the **target and its recipe**, the **score** (what "better" means to the owner), the
**gate** (what "no loss" means) and the **idea list** (the levers of this target).

| Target | Score | Gate: what may not get worse | Held-out inputs |
|---|---|---|---|
| Model serving (LLM, image, video, audio) | tokens/s, first-token time, latency, frames/s | logprob fidelity, needles, tool tests, same-seed image metric | fresh prompts and sessions, new seeds |
| Render | ms per frame | same-seed image metric (SSIM, LPIPS) against a reference | scenes, camera paths and seeds the agent never saw |
| Kernel | time per call, GB/s, TFLOPS | output equals a reference implementation within a tolerance | random inputs, odd shapes and dtypes from a sealed seed |
| Algorithm or solver | time to solve, or cost of the answer | a verifier says the answer is valid (and as good as the reference) | instances from a sealed generator |
| Training run | validation loss at a fixed budget | metric code, data and budget unchanged | a second validation split the loop never reads |

Rules that carry over to every row:

- Use the owner's real sizes, settings and sampler. A scorer for a workload nobody runs measures nothing.
- Fix the work, then time it: same output length, same steps, same instances. Never time a free-running answer.
- Seed every request. Bust every cache the target has, unless the cache is what you measure.
- The scorer measures time itself. The target never reports its own time.
- Bands come from A/A runs, never from zero.
- A change that alters numerics or precision must pass the gate, or it is rejected. The owner's precision, sampler and
  step count stay as they are unless he rules otherwise.

The serving case has its own probes, weights and files: [evaluator.md](references/evaluator.md) and
[example-model-serving.md](references/example-model-serving.md).

## How a run cheats, and the block

| Shortcut | Block |
|---|---|
| Edit the scorer, its inputs or its parser | Hash lock; the agent cannot write to the scorer folder |
| Special-case the visible inputs | The held-out check |
| Do less work (shorter output, fewer steps, lower precision) | Fixed work per probe; the gate; invariants list |
| Reuse results from a cache or a file left by an earlier run | Fresh process, fresh salt or seed, cache cleared |
| Best of N runs, or re-run until it wins | Median of at least 3; one verdict per pass; all reps saved |
| Win by luck on a noisy box | A/A floor; the champion measured again in the same session |
| Buy the win with more memory, clock or cores | Invariants; peak memory recorded |
| Claim a result it did not run | Raw outputs saved under `runs/<id>/`; the verdict reads them |

The serving version, with its numbers, is `assets/project-template/docs/03_ANTI_GAMING.md`.

## The five phases

1. **Grill** the owner until the spec is concrete. Output: `SPEC_DRAFT.md`, signed off with a "yes". Pin: what
   "better" means and in which order; the real workload and settings; what "no loss" means, and the forbidden
   changes; the invariants and the budget; where the keys live; which sub-agents are allowed.
2. **Scaffold** one project folder from [assets/project-template/](assets/project-template/). The template is the
   serving example; replace the content, keep the structure ([loop.md](references/loop.md) has the file map).
3. **Bring up** the target once: a first start, a smoke test, a baseline run that records the gate's references.
4. **Build and lock the scorer**: invariants, gate, score probes, verdict, **held-out check**, at least 3 A/A runs,
   then `aa.py` writes `evaluator.lock`. After the lock, any edit to the scorer is a migration: log it, measure the
   champion again.
5. **Run the loop** until the owner stops it, then write `REPORT.md`.

Never skip or reorder phases 1 and 4. The first project rebuilt its scorer four times because phase 1 did not pin the
owner's real use, and every result measured before the final scorer was lost.

## Phase 5: the loop

`GOAL.md` holds the pass procedure. Each pass:

1. Pop the `pending` idea with the highest `p=%`. Check what it changes and what the default is today.
2. `candidate/` = the champion plus ONE change. Run it; keep a background waiter alive; never poll.
3. The verdict script decides. `record.py` writes the results row from the raw files.
4. A KEEP needs a confirmation run, then the held-out check. Promote with `verdict.py promote`, which checks both; keep a revert point.
5. A failure that can recur goes to `ruled_out.tsv` with a reopen condition. One line to `insights.md`.
6. `check_state.py`, `plot_progress.py`, then rewrite `PROGRESS.md` as one table: champion against the owner's current
   setup.

**Idea queue.** Every idea carries `p=NN%`. Drop low-odds ideas fast: run the best odds first, and write a dead idea
into `ruled_out.tsv` the moment evidence kills it. Do not run a queue in order of age. A plateau (5 passes with no
KEEP) means a research round, and the next two ideas come from another category.

**Habits that paid off** (the 5070 training project, [lessons.md](references/lessons.md) section 12):

- Each commit or row states: the bottleneck, the hypothesis, and the evidence for it.
- Search the results for the idea before you run it. A repeat costs a full pass.
- When two changes score the same, keep the one that deletes code.
- Never change more than one category (flag, kernel, schedule, data) in one pass.
- Write each result so a fresh session can learn from it: what changed, why, what happened, what it rules out.

**Charts.** `plot_progress.py` reads `results.tsv` and writes `progress.png`. The
[speedloop repo](https://github.com/Djordje-Stojanovic/speedloop) holds the results of finished projects and two more
tools: `tools/chart.py` turns `wins.tsv` into `chart.png` and `TABLE.md` (one row per win), and `tools/progress.py`
turns `progress.json` into `progress.png`. The timeline names each champion's finder in the legend and lists
champions #1 to #N once, in a key under the picture. In `progress.json`, a segment's `who` names the model or agent
that FOUND its champion, not the one that measured it again at home (`base`). A segment from another machine sets
`align`, which scales its numbers; say so in `note`.

Research rounds, outside-model prompts, sub-agent rules and the hand-off when the session ends:
[loop.md](references/loop.md).

**Finish:** when the owner stops the run, write `REPORT.md`: every pass in plain English, the champion against the
owner's setup, the final recipe and its diff, what failed and why, what to try next.

## Talking to the owner

- Short sentences, tables for numbers, and say what is not done or not verified.
- A status answer gives the time, the pass and its stage, the last verdicts, champion against home, credit left.
- Never claim a gain from one noisy run. Every decision comes as a table with a recommended answer.

## Final response

At the end of a phase or a pass: the phase or pass id, the verdict with its key numbers, the next step, and the
loop's status line.

## Personal instructions

<sigmaskills-custom>
</sigmaskills-custom>
