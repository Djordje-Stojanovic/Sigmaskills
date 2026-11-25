# Worked example: make a model serve faster on a rented GPU

The first project. `SKILL.md` holds the method for any target. This file holds what is true only when the
target is a served model: the GPU host, the engine, the probes and the serving files of `assets/project-template/`
(the template README lists them). `evaluator.md` sections 6-9, `lessons.md`, `case-study-la125.md` and
`setup-vast.md` are also about this example.

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

For a new rental use the skill `sigmacollab`, which says where to rent first; the worked case ran on Vast.ai ([setup-vast.md](setup-vast.md)). Another
rental works the same way: keep its key in the project's `secrets/`, and give `scripts/box.ps1` its SSH host and port.

## Phase 1: what the interview pins for a served model

The questions are in `interview.md`; for a served model they mean:

- **What "faster" means:** exact weights and revision, engine, image and launch recipe (read the recipe file
  read-only); the real workload (streams, context, chat or agents, image size, clip length); the priority order,
  which becomes the score weights in `project.json`.
- **The real request settings:** sampler, thinking and effort levels as the owner's client sends them, output limit.
  A greedy scorer measures a workload nobody runs.
- **What "no quality loss" means:** forbidden changes (more quantization, precision cuts, other weights, lossy
  samplers, fewer steps) and the drift policy. The smallest gain comes from the noise runs (`min_gain` in
  `project.json`); a single-probe win is an ARCHIVE the owner rules on.
- **Invariants and budget:** memory budget, context, served name, credit, hours, the owner's own machines (read-only
  at most).
- **The quality check's size:** the full fidelity check plus a tool suite took longer than the speed probes in the
  first project. It runs only on a stage-1 winner; keep it within a quarter of a pass, or run a fixed subset.
- **Logistics:** where the API keys live, the project folder, git or not, charts.

## Phase 2: scaffold

Copy `assets/project-template/` into `<workspace>/Projects/<Model-Engine>/` and rename `_gitignore` to `.gitignore`
(package managers drop dot-files). Then adapt, in this order: `project.json` (weights, offer filters),
`box/serve_base.sh` (the owner's recipe, flag for flag), `scripts/bench/invariants.py`, the probes in
`scripts/bench/speed.py` (rewrite them for a non-LLM model), `scripts/bench/build_replay.py` (the owner's real agent
logs as traces), then `GOAL.md` and the TSV files. Seed `ideas.tsv` after the profile; every idea carries its part,
its share and `p=NN%`.

## Phase 3: bring up the box

Follow [setup-vast.md](setup-vast.md). The points that cost hours before:

- Rent **one** box with real filters, after a short test rental. The instance image is the serving image.
- Probe `io_uring`, disk, RAM and driver first. A blocked syscall gets a code fallback, never a weaker sandbox.
- Download weights in the background and **check every file's sha256** against the source.
- Run `box/smoke.py` before you spend a baseline. Copy the reference outputs home after every record run.
- Never print a secret. Never change the owner's payment settings.

## Phase 3, continued: the scorer, then the lock

Read [evaluator.md](evaluator.md). `launch.ps1` checks the invariants, pushes the scorer, the settings and the champion
to the box, and starts `run_experiment.sh`, which calls `target.sh`:

1. `invariants.py`: a broken invariant makes the run VOID before launch.
2. Stage 1, `speed.py`: probes at the owner's real settings, written to `raw/score.json`. **Every replay or
   throughput turn writes a fixed number of tokens** (`max_tokens = min_tokens`), or wall time measures the sampled
   answer length instead of speed. Count completion tokens from server usage stats or the real tokenizer (never
   streamed SSE chunks, which bundle tokens under speculative decoding), size prompts with the real tokenizer, and use
   a fixed prompt panel with medians so text type does not skew acceptance. The box runs `verdict.py` on the score;
   anything but a stage-1 win ends the pass.
3. Stage 2, `gate.py`, ToolEvalBench and `quality.py`: the quality check, on the same running server. When the KV pool
   is sized for N users, prove it with a concurrent full-length soak and exact-match needles at ~50 % and ~100 %
   context. On a greedy equivalence divergence (speculation on vs off), inspect logits at the split: a near-tie from
   different batch-size kernels is not a bug.
4. `verdict.py` at home: the final verdict from the pulled raw files.

Enforce the memory cap with a watchdog. On unified memory (integrated GPUs and shared-memory systems), GPU allocations
bypass cgroups and `MemAvailable`: sum driver residency (e.g. Linux DRM `drm-resident-*` deduplicated by client id)
plus process anonymous memory, and leave headroom.

The baseline runs with `-Record`, the A/A runs with `-Full`. Then `quality.py bands` and `aa.py` on those runs.

The owner's home machine is the held-out check for serving: he runs the champion there in his real use
(`held-out.md`).

After the lock, any edit to `scripts/bench/` is an evaluator migration: log it in `evaluator.lock`, push the files to
the box (it keeps its own copy) and measure the champion again.

## Phase 4: ceilings and serving profile

Measure the hardware first (device-copy bandwidth and large square GEMMs; a spec-sheet number is not a ceiling) and
compute practical ceilings from the checkpoint's actual tensor sizes:

- **Decode** (memory-bandwidth bound): bytes read per emitted token (dense + active routed experts + LM head + KV at
  context + recurrent state) ÷ measured bandwidth. With speculative decoding, divide target verify bytes by accepted
  length and add draft layer + draft LM head bytes.
- **Prefill** (compute bound): FLOPs per token (`2 × active linear params` plus causal attention) ÷ ~50 % of measured
  peak. **TTFT:** one forward pass + schedule. **Startup:** weight bytes ÷ disk/page-cache speed (with caches
  persisted). **KV:** bytes/token × layers that actually hold KV.

Report progress as a share of the practical ceiling, then time each part of one real request and agent turn (prompt
reading, first token, decode, scheduler gaps, cache hit rate, start time). Attack the biggest ceiling gap first.

## Lever order (cheapest first)

1. **Startup:** persist JIT, compile, autotune and graph caches across restarts; load weights eagerly where mmap is
   slow; cap compile workers on memory-tight machines.
2. **Decode graphs** (CUDA/XPU/HIP capture) first. Once graphs are on, stop fusing small kernels when time sits in the
   main GEMMs/GEMVs.
3. **Speculative decoding:** judge `accepted_length / step_time`, not acceptance alone. Prune the draft LM head's
   vocabulary, sweep draft length per concurrency and context, keep sampling on the GPU, and keep verify on
   decode-style attention.
4. **Concurrency and KV:** size the KV pool to N × context; on hybrid SSM/recurrent models, size state slots too (they
   often cap concurrency before KV); enable prefix caching explicitly and confirm cached tokens > 0.
5. **Prefill:** tune chunk size against decode stalls; swap in a faster attention library before writing one; treat
   int8/fp8 prefill GEMMs as a labelled quality trade; avoid grouped-MoE padding cliffs.
6. **Kernel thread and tile sizes:** defaults copied from larger GPUs often miss smaller cards.
7. **Kernel and ISA work** only after config levers plateau, gated by bit-exact or tight-tolerance checks across all
   served row counts.

## Phase 5: serving-only steps of a pass

- Step 1 also asks: does the flag exist in the installed engine, and what is its default? Several ideas were on by
  default already.
- `candidate/serve.sh` = the champion plus ONE change. `scripts/bench/verdict.py runs/<n>` decides.
- A flag that the engine reads at run time gets an ABAB test on one live server first: minutes, not a pass.
- Noise is large: a champion can swing 10 % between identical runs. Same warm-up both sides; never "fresh and empty".
- Never force-kill a server mid-batch or mid-prefill: abort requests, wait for drain, then stop with a timeout.
- A trade (one probe up, one down) is an ARCHIVE; the owner rules on it, from a table.

## Finish

When the owner has destroyed the box, write `REPORT.md` (see `SKILL.md`). Before publishing a tuned recipe, pin the base
image digest, engine/kernel commits and weights revision, build cleanly from those pins, prove the clean build matches
the champion within noise, and label which harness produced each number.

## Sources

Serving ceilings, lever order, unified-memory accounting, drain-before-stop, speculative-decoding per-step rules and
clean-build qualification draw on [sybil-solutions/inference-optimisation-skill](https://github.com/sybil-solutions/inference-optimisation-skill) (MIT).
