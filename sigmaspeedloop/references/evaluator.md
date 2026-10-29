# The evaluator (v8): honest, script-only, owner-real

The evaluator is the product. A loop with a weak judge optimizes garbage. No LLM judge, no agent ratings.
Only `scripts/bench/verdict.py` decides, and it reads raw files. Version history: `evaluator.lock` "migrations".

## Contents
1. Stages and timing
2. Real settings
3. Quality gate
4. ToolEvalBench (floor)
5. Speed probes and weights (v8)
6. Noise: A/A, floor, confirmation
7. Verdict rules
8. Pitfalls
9. Adapting probes to non-LLM models

## 1. Stages and timing (~40 min end to end)

| Stage | Script | Time |
|---|---|---|
| 0 invariant diff | `scripts/bench/invariants.py` (run by `launch.ps1`) | seconds |
| bandwidth probe before | `bw.py` | 10 s |
| server start (+ 1 s MemAvailable log) | `run_experiment.sh` | ~5 min (+ recompile) |
| fixed warm-up (3 x 256 tokens) | | 0.5 min |
| 1 quality gate | `gate.py` | ~8 min |
| 1b ToolEvalBench (97 scenarios) | in `run_experiment.sh` | ~9 min |
| 2 speed probes | `speed.py` | ~11 min |
| llama-benchy (forum-comparable) | in `run_experiment.sh` | ~3 min |
| stop + bandwidth probe after | | ~1 min |
| 3 verdict (local) | `verdict.py` | seconds |

## 2. Real settings (put them in `common.py` and `project.json`)

- Server-side sampling as the owner uses it (Qwen thinking: T=1.0, top_p 0.95, top_k 20), fixed seed per request.
- Thinking on if the owner never turns it off. Effort per probe = the owner's mix (low/medium daily, xhigh
  sometimes). Read the client config for the name mapping.
- `max_tokens` = the owner's value (65536). Measure a fixed slice and stop client-side (`stop_after=N`).
  Stop only after the event's tokens were timed.
- Decode rate = tokens after the first / time after the first token. Never request wall time.
- Greedy (T=0) is only for the fidelity gate. Speed probes use the real sampler, because speculative-decode
  acceptance differs under greedy.

## 3. Quality gate (`gate.py`)

- **Teacher-forced fidelity**: `/v1/completions`, `prompt_logprobs=2`, `max_tokens=1`, T=0 on ~75k positions
  (code, prose, multilingual, math, JSON, real agent text). Per position: top-1 agreement, mean |delta logprob|.
- **Decode fidelity**: 24 greedy chat prompts x 512 tokens, top-5 logprobs, common-prefix length and |delta logprob|.
- **Needles** at ~64k and ~128k tokens, empty-output and looping (6-gram) checks.
- References are recorded by the baseline run (`-Record`) and pulled to `refs/` (they die with the box).
- Greedy output is not reproducible on GB10 run to run: thresholds come from A/A, never from zero.

## 4. ToolEvalBench (floor)

- Command: `tool-eval-bench run --base-url http://localhost:8000/v1 --model <name> --hardmode --temperature 1.0
  --top-p 0.95 --top-k 20 --seed 42 --parallel 8 --no-live --json-file tooleval.json`, plus `--backend-kwargs`
  with `reasoning_effort` low and `max_tokens` 65536.
- Score = `scores.total_points / max_points` (97 scenarios -> 194 points). Champion band 154-169.
- It is a regression alarm at T=1, not a ranker. Floor `tooleval_min` = 155 in the la125 lock. A drop below
  `min - max(3, 2 x A/A range)` is a gate failure. Pin the version by commit. No context fill.

## 5. Speed probes and weights (v8, the la125 owner's priorities)

| Probe | What | Component | Weight |
|---|---|---|---|
| short decode | 5 fixed prompts x low/medium effort, 512 tokens, tok/s | short | **.30** |
| warm agent turns | inside the replay: the sum of first-token times of the 9 warm turns (inverted) | warm | **.20** |
| warm cache hits | inside the replay: champion miss share / candidate miss share | miss | **.10** |
| long thinking | 64k context, xhigh, 3072 tokens, tok/s | long | **.15** |
| prefill | unique salted prompts at 16k (x2), 64k, 128k, 1 output token, geo mean tok/s; TTFT 128k logged | prefill | **.10** |
| 2 agents | 2 concurrent requests, effort low, fixed 512 tokens each, aggregate tok/s | c2 | **.08** |
| agent replay (v8) | 3 real sessions at once, 4 consecutive real turns each (1 cold, 3 warm), **exactly 1024 tokens per turn** (`max_tokens = min_tokens`, `ignore_eos`), prefix cache on, a barrier between cold and warm turns | replay (wall time, inverted) | **.04** |
| 3 agents | 3 concurrent, fixed 512 tokens each, aggregate tok/s | c3 | **.03** |
| chat (logged only) | ~100k-token conversation, model answers fed back, 5 rounds; warm TTFT ~0.4 s | none | none |

- Ask the owner for the order of these probes in phase 1, and derive the weights from it. Raw priority weights
  (0.35 / 0.25 / ... / 0.01) left two probes almost unscored; v8.2 kept the order and gave each probe a real weight.
- Weights are renormalized when a component is missing. Replay wall time compares only between runs of the same
  replay version.
- Score = weighted geometric mean of candidate/champion ratios. Weights live in `project.json`.
- Why v8: in v7 each replay turn stopped where the sampled answer ended. Two runs of the same recipe wrote 2,855 and
  6,758 tokens, and the wall time followed the length. A "+32 %" KEEP was luck.
- Salt every request outside the replay. In the replay, one salt per run in the system prompt.
- The recorded-answer replay hits the prefix cache ~87 %; real chat that feeds the model's own answers back hits
  100 %. Know which one you measure.
- Bandwidth probe before and after; a flip (< 75 % of median) = RERUN. Measure the true ceiling with a
  read-only probe (lessons 8.2).

## 6. Noise: A/A, floor, confirmation

- Baseline + >= 3 restarts of the unchanged recipe (5 used). `aa.py` writes per-probe spread and score spread
  into `evaluator.lock`.
- Real GB10 numbers at T=1: replay 8 % (up to 15 % on a new box), decode 3.7 %, prefill 1.9 %, c3 5.2 %,
  score 3 %. The champion itself swings about 10 % on 2-3 stream probes between identical runs.
- Keep floor = 5 % (owner ruling; the formula default is max(2 %, 2 x score spread)).
- Every KEEP gets a confirmation run. Borderline: judge the 2-3 run median. Champion reference = median of the
  runs in `state/champion.json`.
- A new box needs new reference runs. After the lock, editing `scripts/bench/` is an evaluator migration:
  log it in `evaluator.lock`, re-measure the champion.

## 7. Verdict rules (`verdict.py`)

1. VOID: evaluator hash mismatch, broken invariant, MemAvailable below floor during start.
2. CRASH: run status not OK. RERUN: bandwidth flip or missing probe.
3. Gate. Strict: any fidelity metric outside its A/A band fails. Drift rule (owner, 2026-10-23): a fidelity-only
   failure passes when ToolEvalBench >= champion A/A min and needles, empty and looping checks pass.
4. KEEP: gate ok, score >= 1 + floor (5 %), and no probe below 1 - max(2 %, 2 x its spread).
5. KEEP (single-probe rule): one probe >= +10 % and every other probe >= -5 % (`single_win`, `single_other_min`).
6. ARCHIVE: not KEEP, but one probe > 1 + max(5 %, 3 x spread). The owner decides the trade-off.
7. Else REJECT. Every KEEP is confirmed before promotion.

## 8. Pitfalls

- Parallel probes with natural stops measure output-length spread. Fix the length (`min_tokens`, `ignore_eos`).
- `prompt_logprobs` dict keys are token ids. Compare by id, not text.
- `ignore_eos` inflates speculative acceptance. Use it only in throughput probes.
- A replay that cuts points 20-80k tokens apart caps the hit rate at ~45 %. Use consecutive real turns.
- Read the server log's kernel roster once. Backends and cudagraph mode explain silent fallbacks.
- A 5-10 % delta on c2 or c3 can be noise (lessons 7.1).
- A greedy replay hides sampling-only gains. Keep the sampled decode probe.

## 9. Adapting probes to non-LLM models

Keep the structure: invariants, fidelity gate, speed probes, weights, A/A bands, verdict. Replace the content.
Rename the components in `project.json` "weights" and in `verdict.py` `extract()` / `ratios()`.

| Modality | Speed probes | Fidelity gate |
|---|---|---|
| Image (diffusers, ComfyUI) | latency per image at the owner's sizes and steps (p50, cold and warm); images per minute at 1, 2, 4 concurrent; peak VRAM | fixed seeds and prompts; same-seed output vs reference with an image metric (LPIPS, SSIM, PSNR; CLIP or FID on a set); A/A gives the band |
| Video | latency per frame and per clip; frames per second; time to first frame; peak VRAM | fixed-seed clips; per-frame LPIPS/SSIM plus a temporal metric (flow warp error) vs reference |
| Audio, music, TTS | real-time factor (audio seconds per wall second); time to first audio chunk; concurrent streams | fixed seeds; mel or waveform distance; CLAP or speaker similarity; ASR word error rate for speech |
| Speech to text | real-time factor; latency to final text | word error rate on a fixed set (must not rise) |
| Multimodal LLM | the LLM probes plus image-prefill latency at the owner's image sizes | the LLM gate plus fixed image Q&A with expected answers |

Rules that carry over:
- Use the owner's real sizes, steps and sampler.
- Put a fixed seed in every request.
- Bust caches where a cache exists.
- Stop client-side at a fixed slice. Use a fixed output size in throughput probes.
- Take bands from A/A, not from zero.
- A switch that changes numerics must pass the metric gate, or it is rejected.
- Quality may never drop: no lower precision, no fewer steps, no weaker scheduler, unless the owner rules it.
