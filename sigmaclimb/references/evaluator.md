# The evaluator: honest, cheap, sized to the target

The evaluator is the product. A loop with a weak judge optimizes garbage. Only `scripts/bench/verdict.py` decides, and
it reads raw files and `project.json`. The measurer behind it can be a script, the owner picking blind pairs, or a
judge he accepts. Version history: `evaluator.lock` "migrations".

## Contents
1. A pass in two stages
2. The quality check, sized to the target
3. Noise: same state for both sides
4. A probe with new input
5. Verdict rules
6. The serving example: real settings
7. The serving example: quality check
8. The serving example: score probes and weights
9. Pitfalls of the serving example

## 1. A pass in two stages

| Stage | What | Ends the pass when |
|---|---|---|
| 0 | invariants: the change touches nothing locked | an invariant breaks (VOID) |
| start + warm-up | the target starts; a fixed warm-up, the same for both sides | it crashes |
| 1 score | every score probe; then `verdict.py` on the score alone | the verdict is not `STAGE1-WIN` |
| 2 quality | the quality check, on the same running target | never: the final verdict reads it |

`run_experiment.sh` records the seconds of every stage in `raw/meta.json`. The score stage should be at least half
of a pass; `status.py` says when it is not. A slower idea costs only stage 1.

## 2. The quality check, sized to the target

- The interview sets it (`interview.md`, question 6). Default: at most a quarter of a pass
  (`quality_share_max`). A frame comparison takes seconds; a model eval suite takes minutes.
- It runs on every stage-1 winner, including changes that cannot alter the output (they get it once, too).
- Its bands come from the noise runs, never from zero. It writes `raw/quality.json`: `{"ok": bool, "fails": [...]}`.
- If it outgrows its share: run a smaller fixed subset on every winner, and the full check before the final report.

## 3. Noise: same state for both sides

- Run the unchanged target `repeats` times (default 3). `aa.py` writes each probe's spread and the score spread.
- The smallest gain that counts is twice the score spread unless `project.json` sets `min_gain`. A probe may drop by
  twice its own spread unless `max_drop` is set.
- A fixed warm-up before the measured part, identical for champion and candidate. Do not clear caches or restart
  "fresh" by default: a cold start adds the noise it was meant to remove. If cold and warm both matter to the
  owner, measure both on purpose, as two probes.
- When the change is a live switch (a setting the target reads at run time), test A and B on one running target,
  interleaved (ABAB). It costs minutes and cancels drift. Use it as a 10-minute kill test before a scored pass.
- A confirmation run only when the gain is under `confirm_below` (2) times the smallest gain. One run and at most one
  confirmation per idea.
- A new machine is a new baseline: measure the champion there before you judge a candidate.

## 4. A probe with new input

Every score has at least one probe whose input is new in every run: new text, a new scene, a new instance, a new
camera path, with the amount of work fixed. A probe that repeats its input measures only the path that some cache
already knows. The serving example's `prefill_new` probe reads text made fresh for each run.

## 5. Verdict rules (`verdict.py`)

1. VOID: a scorer file changed (hash), an invariant broke, or the target wrote a VOID status.
2. CRASH: the run status is not OK, or there is no score.
3. The score: the weighted geometric mean of the probe ratios against the champion (or the share of blind pairs
   won). Every verdict prints it against the champion before and against the start.
4. REJECT if the quality check failed.
5. KEEP: gain >= the smallest gain, and no probe dropped past its band. Without a quality check yet: STAGE1-WIN.
6. ARCHIVE: not a clean win (the score wins but a probe dropped, or one probe is clearly up but the score is
   short). The owner rules.
7. Else REJECT.

`promote` makes the new champion: it needs the quality check, a confirmation when the gain is small, and a held-out
PASS only in `required` mode (`held-out.md`). `--owner "<his words>"` promotes on his word.

## 6. The serving example: real settings (`common.py`, `project.json`)

- Server-side sampling as the owner uses it (for example T=1.0, top_p 0.95, top_k 20), a fixed seed per request.
- Thinking on if the owner never turns it off. Effort per probe = the owner's mix. Read the client config.
- `max_tokens` = the owner's value. Measure a fixed slice and stop client-side (`stop_after=N`), only after the
  event's tokens were timed.
- Decode rate = tokens after the first / time after the first token. Never request wall time.
- Greedy (T=0) only for the fidelity check. Speed probes use the real sampler: speculative-decode acceptance differs.

## 7. The serving example: quality check (`gate.py`, ToolEvalBench, `quality.py`)

- **Teacher-forced fidelity**: `/v1/completions`, `prompt_logprobs`, `max_tokens=1`, T=0 on a large fixed text mix.
  Per position: top-1 agreement, mean |delta logprob|.
- **Decode fidelity**: greedy chat prompts, common-prefix length and |delta logprob|.
- **Needles** at long context, empty-output and looping checks.
- **ToolEvalBench** at real sampling: a regression alarm, not a ranker. A drop below the A/A minimum minus
  max(3, 2 x A/A range) fails.
- References come from the baseline run (`launch.ps1 -Record`); copy them home after every record run.
- `quality.py bands runs/A runs/B runs/C` (before `aa.py`) turns the A/A runs into bands; on the box `quality.py`
  judges each run and writes `quality.json`. Drift rule: a fidelity-only failure passes when the tool score is at
  least the A/A minimum and nothing else failed.
- This check took longer than the speed probes in the first project. Size it with question 6 of the interview.

## 8. The serving example: score probes and weights

| Probe | What | Direction |
|---|---|---|
| `short` | fixed prompts at the owner's daily effort levels, a fixed token slice, decode rate | higher |
| `long` | long context, high effort, a fixed slice of thinking, decode rate | higher |
| `prefill` | unique salted prompts at several lengths, 1 output token, geometric mean rate | higher |
| `prefill_new` | text made fresh for this run, fixed length, 1 output token | higher |
| `ttft_128k` | first-token time at the longest context (weight 0: a guard) | lower |
| `warm`, `miss` | inside the agent replay: summed warm first-token time; prefix-cache miss share | lower |
| `replay` | real agent sessions at once, consecutive turns, a fixed token count per turn | lower (wall time) |
| `c2`, `c3` | 2 and 3 concurrent requests, fixed tokens each, aggregate rate | higher |

- The owner orders the probes in the interview; the weights in `project.json` follow that order, and each scored
  probe gets a real weight. Probes he does not rank become guards (weight 0).
- Salt every request outside the replay. In the replay, one salt per run in the system prompt.

## 9. Pitfalls of the serving example

- Parallel probes with natural stops measure output-length spread. Fix the length (`min_tokens`, `ignore_eos`).
- `prompt_logprobs` dict keys are token ids. Compare by id, not text.
- `ignore_eos` inflates speculative acceptance. Use it only in throughput probes.
- A replay that cuts points far apart caps the cache hit rate. Use consecutive real turns.
- Read the server log's kernel roster once. Backends and graph mode explain silent fallbacks.
- A greedy replay hides sampling-only gains. Keep the sampled decode probe.
