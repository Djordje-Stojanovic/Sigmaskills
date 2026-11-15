# Worked example: make a model serve faster on a rented GPU

The first SigmaClimb project. `SKILL.md` holds the method for any target. This file holds what is true only when the
target is a served model: the GPU host, the engine, the probes and the files of `assets/project-template/`.
The other files in this folder (`evaluator.md`, `lessons.md`, `case-study-la125.md`, `setup-vast.md`) are also about
this example.

## What changes per project

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

The GPU host is usually Vast.ai ([setup-vast.md](setup-vast.md)); for new rentals use the skill `sigmavast`. Another
rental works the same way: keep its key in the project's `secrets/`, and give `scripts/box.ps1` its SSH host and port.

## Phase 1: what to pin with the owner

- **What "faster" means:** exact weights and revision, engine, image and launch recipe (read the recipe file
  read-only); the real workload (streams, context, chat or agents, image size, clip length); the priority order,
  which becomes the score weights in `project.json`.
- **The real request settings:** sampler, thinking and effort levels as the owner's client sends them, output limit.
  A greedy scorer measures a workload nobody runs.
- **What "no quality loss" means:** forbidden changes (more quantization, precision cuts, other weights, lossy
  samplers, fewer steps), the drift policy, the keep floor and the single-probe rule.
- **Invariants and budget:** memory budget, context, served name, credit, hours, the owner's own machines (read-only
  at most), and which sub-agents the owner allows.
- **Logistics:** where the API keys live, the project folder, git or not, charts.

## Phase 2: scaffold

Copy `assets/project-template/` into `<workspace>/Projects/<Model-Engine>/` and rename `_gitignore` to `.gitignore`
(package managers drop dot-files). Then adapt, in this order: `project.json` (weights, floors, offer filters),
`box/serve_base.sh` (the owner's recipe, flag for flag), `scripts/bench/invariants.py`, the probes in
`scripts/bench/` (rewrite them for a non-LLM model), `scripts/bench/build_replay.py` (the owner's real agent logs as
traces), then `GOAL.md` and the TSV files. Seed `ideas.tsv` with a research round; every idea carries `p=NN%`.

## Phase 3: bring up the box

Follow [setup-vast.md](setup-vast.md). The points that cost hours before:

- Rent **one** box with real filters, after a short test rental. The instance image is the serving image.
- Probe `io_uring`, disk, RAM and driver first. A blocked syscall gets a code fallback, never a weaker sandbox.
- Download weights in the background and **check every file's sha256** against the source.
- Run `box/smoke.py` before you spend a baseline. Copy the reference outputs home after every record run.
- Never print a secret. Never change the owner's payment settings.

## Phase 4: the four stages of the scorer, and the held-out check

Read [evaluator.md](evaluator.md). Four stages, each a script:

1. `invariants.py`: a broken invariant makes the run VOID before launch.
2. `gate.py` plus a task-quality suite: the fidelity gate.
3. `speed.py`: probes at the owner's real settings. **Every replay or throughput turn writes a fixed number of
   tokens** (`max_tokens = min_tokens`), or wall time measures the sampled answer length instead of speed.
4. `verdict.py`: the weighted geometric mean against the champion median, the keep floor, the single-probe rule,
   and no probe below its A/A band.

The held-out check for serving: a second prompt pack (new text, new salts, a replay of agent sessions that are not in
the scorer's replay) and the same gate and score on it. Keep it on the owner's PC, not in the repo and not on the
box; the main session asks for PASS or FAIL only. See [evaluator.md](evaluator.md) section 10.

After the lock, any edit to `scripts/bench/` is an evaluator migration: log it in `evaluator.lock`, push the files to
the box (it keeps its own copy) and measure the champion again. Measure the real memory-bandwidth ceiling with a
read-only probe; a spec-sheet number is not a ceiling.

## Phase 5: serving-only steps of a pass

- Step 1 also asks: does the flag exist in the installed engine, and what is its default? Several ideas were on by
  default already.
- `candidate/serve.sh` = the champion plus ONE change. `scripts/bench/verdict.py runs/<n>` decides.
- Profile the path you have never profiled before you optimize it.
- Noise is large: a champion can swing 10 % between identical runs.
- A trade (one probe up, one down) is an ARCHIVE; the owner rules on it, from a table.

## Finish

When the owner has destroyed the box, write `REPORT.md` (see `SKILL.md`).
