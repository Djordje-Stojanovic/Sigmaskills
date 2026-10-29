---
name: sigmaspeedloop
description: Make any AI model serve faster on a rented GPU with no quality loss, one scripted keep-or-revert change at a time. Use for speed loops, inference or KV tuning. Do not use for training or code review.
---

# SigmaSpeedLoop

Turn "make model X faster on GPU Y" into a loop that a script judges. One change per pass. A locked evaluator
decides keep or revert from raw files. Quality may never go down, and the owner's weights, precision and sampler
stay as they are.

The method comes from a real multi-day project: Qwen3.8-Flash-Next 125B NVFP4 on a rented DGX Spark (GB10), about
110 runs and 9 champions. Prefill rose 32 %, and warm agent turns started 58 % sooner
([case study](references/case-study-la125.md)). That project also lost hours to avoidable mistakes.
**Read [lessons.md](references/lessons.md) before you rent anything.**

The skill is host-neutral. Any agent that can run a shell, keep files and wait on a background job can drive it.
Long unattended runs use the host's own loop mode; [loop.md](references/loop.md) has the prompt and the host notes.
Use the shell native to the machine: PowerShell on Windows, POSIX shell elsewhere. The template's `.ps1` helpers
have the same few steps a POSIX port needs.

## Works for any model, engine and GPU

Only four things change per project:

1. The **recipe** (how the engine starts) and its **invariants** (what may never change).
2. The **speed probes** and their weights (what "faster" means for this owner).
3. The **fidelity gate** (what "no quality loss" means).
4. The **idea list** (levers of this engine and this GPU).

| Model type | Typical engines | Speed probes | Fidelity gate |
|---|---|---|---|
| LLM, multimodal LLM | vLLM, SGLang, llama.cpp, TensorRT-LLM | decode, prefill and first token, warm agent turns, parallel streams | logprob fidelity, needles, a tool-use suite |
| Image | ComfyUI, diffusers | latency per image, images per minute, VRAM | same-seed image metric (LPIPS, SSIM) |
| Video | ComfyUI, diffusers | latency per frame or clip, VRAM | per-frame and temporal metric |
| Audio, music, speech | diffusers, custom servers | real-time factor, time to first chunk | mel or CLAP distance, word error rate |

The GPU host is usually Vast.ai ([setup-vast.md](references/setup-vast.md)). Another rental works the same way:
keep its key in the project's `secrets/`, and give `scripts/box.ps1` its SSH host and port.

## The five phases

1. **Grill** the owner until the spec is concrete. Output: `SPEC_DRAFT.md`, signed off with a "yes".
2. **Scaffold** one project folder from [assets/project-template/](assets/project-template/).
3. **Bring up** one box: rent, image, weights with verified hashes, first start, smoke test.
4. **Build and lock the evaluator**: a baseline, at least 3 A/A restarts, then `aa.py` writes `evaluator.lock`.
5. **Run the loop** until the owner destroys the box, then write `REPORT.md`.

Never skip or reorder phases 1 and 4. The first project rebuilt its evaluator four times because phase 1 did not
pin the owner's real usage, and every result measured before the final evaluator was lost.

## Phase 1: grill the owner

Ask in numbered rounds. Give every question a recommended answer the owner can accept with "yes". Pin these:

- **What "faster" means:** exact weights and revision, engine, image and launch recipe (read the recipe file
  read-only); the real workload (streams, context, chat or agents, image size, clip length); the priority order,
  which becomes the score weights in `project.json`.
- **The real request settings:** sampler, thinking and effort levels as the owner's client sends them, output limit.
  A greedy evaluator measures a workload nobody runs.
- **What "no quality loss" means:** forbidden changes (more quantization, precision cuts, other weights, lossy
  samplers, fewer steps), the drift policy, the keep floor and the single-probe rule.
- **Invariants and budget:** memory budget, context, served name, credit, hours, the owner's own machines (read-only
  at most), and which sub-agents the owner allows.
- **Logistics:** where the API keys live, the project folder, git or not, charts.

## Phase 2: scaffold

Copy `assets/project-template/` into `<workspace>/Projects/<Model-Engine>/` and rename `_gitignore` to `.gitignore`
(package managers drop dot-files). Then adapt, in this order:
`project.json` (weights, floors, offer filters), `box/serve_base.sh` (the owner's recipe, flag for flag),
`scripts/bench/invariants.py`, the probes in `scripts/bench/` (rewrite them for a non-LLM model),
`scripts/bench/build_replay.py` (the owner's real agent logs as traces), then `GOAL.md` and the TSV files. Seed
`ideas.tsv` with a research round; every idea carries `p=NN%`. The file map is in [loop.md](references/loop.md).

## Phase 3: bring up the box

Follow [setup-vast.md](references/setup-vast.md). The points that cost hours before:

- Rent **one** box with real filters, after a short test rental. The instance image is the serving image.
- Probe `io_uring`, disk, RAM and driver first. A blocked syscall gets a code fallback, never a weaker sandbox.
- Download weights in the background and **check every file's sha256** against the source.
- Run `box/smoke.py` before you spend a baseline. Copy the reference outputs home after every record run.
- Never print a secret. Never change the owner's payment settings.

## Phase 4: build and lock the evaluator

Read [evaluator.md](references/evaluator.md). Four stages, each a script:

1. `invariants.py`: a broken invariant makes the run VOID before launch.
2. `gate.py` plus a task-quality suite: the fidelity gate.
3. `speed.py`: probes at the owner's real settings. **Every replay or throughput turn writes a fixed number of
   tokens** (`max_tokens = min_tokens`), or wall time measures the sampled answer length instead of speed.
4. `verdict.py`: the weighted geometric mean against the champion median, the keep floor, the single-probe rule,
   and no probe below its A/A band.

After the lock, any edit to `scripts/bench/` is an evaluator migration: log it in `evaluator.lock`, push the files
to the box (it keeps its own copy) and measure the champion again. Measure the real memory-bandwidth ceiling with a
read-only probe; a spec-sheet number is not a ceiling.

## Phase 5: the loop

`GOAL.md` holds the pass procedure. Each pass:

1. Pop the `pending` idea with the highest `p=%`. Check that its flag exists and what its default is in the
   installed engine. Several ideas were on by default already.
2. `candidate/serve.sh` = the champion plus ONE change. Launch it, and keep a background waiter alive; never poll.
3. `scripts/bench/verdict.py runs/<n>` decides. `scripts/record.py` writes the results row from the raw files.
4. A KEEP needs a confirmation run. Promote only when it confirms; keep a revert point in `checkpoints/`.
5. A failure that can recur goes to `ruled_out.tsv` with a reopen condition. One line to `insights.md`.
6. `check_state.py`, `plot_progress.py`, then rewrite `PROGRESS.md` as one table: champion against the owner's
   current setup.

Rules learned the hard way (all in [lessons.md](references/lessons.md)):

- Profile the path you have never profiled before you optimize it.
- Noise is large: a champion can swing 10 % between identical runs. Say "inside noise" when it is.
- Bundles of small changes lost. A switch that changes numerics fails the gate.
- A trade (one probe up, one down) is an ARCHIVE; the owner rules on it, from a table.

Research rounds, outside-model prompts, sub-agent rules and the hand-off when the session ends:
[loop.md](references/loop.md).

**Finish:** when the owner has destroyed the box, write `REPORT.md`: every pass in plain English, the champion
against the owner's setup, the final recipe and its diff, what failed and why, what to try next.

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
