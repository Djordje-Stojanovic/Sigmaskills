# 03 — Anti-gaming rules

The loop is a strong optimizer. It will find every shortcut in the judge.
These rules close the known shortcuts. They become §INVARIANTS and §ANTI-GAMING in GOAL.md.

## Things the loop may never change

1. Model weights, revision, shard set, tokenizer, chat template.
2. Quantization (`modelopt_mixed`, FP4 weights), KV cache dtype (fp8), LM head precision.
3. `max_model_len` 262,144 and the served name from `box/model.env`.
4. Sampling defaults the users get (T 1.0, top_p 0.95, top_k 20) and thinking on.
5. The memory budget: GPU memory share 0.75, or whatever you sign (see questions). A KV pool gain bought by more memory is not a gain.
6. The benchmark scripts, prompt sets, reference outputs and thresholds. They are hashed in `evaluator.lock`. A hash mismatch voids the experiment.

## Known shortcuts and the rule that blocks each one

| Shortcut | How it fakes a win | Block |
|---|---|---|
| Broken numerics → repetitive text | MTP accepts more drafts, so decode "speeds up" | Logprob fidelity check on every stage-1 winner |
| Prefix cache hits on repeated prompts | Prefill and TTFT look 10–100x faster | Unique salt per request; the `prefill_new` probe reads text made fresh each run; cache tested only in its own probe |
| Shorter outputs | Fewer tokens, less wall time, higher "rate" | Speed is per token over fixed token counts; output length logged and compared |
| Disable thinking or cut max tokens | Less work | Request payloads are frozen and hashed |
| Lower max_model_len or max_num_seqs | Smaller KV, faster start | Invariants list |
| Raise GPU memory share | Bigger KV pool, bigger batches | Fixed budget; peak memory recorded |
| Cherry-pick the best of N runs | Luck looks like progress | One verdict per pass, at most one confirmation; all runs saved |
| Re-run until it wins | Same | One measured verdict per experiment; repeats only through the queue with a reason |
| Measure on a warm box, baseline on a cold one | Cache and clock effects | The same fixed warm-up for both sides; ABAB on one live server for live switches |
| Thermal or neighbour noise on the cloud box | Random wins | A/A spread sets the threshold; baseline re-run every N experiments to catch drift |
| Edit the benchmark or its parser | Anything | Hash lock; the worker cannot write to `scripts/bench/` |
| Tune to the visible prompts, probes and traces | A long loop fits the inputs it can read | The new-input probe; the owner's run on his own machine; the optional held-out check (the skill's `references/held-out.md`) |
| Claim a result without running it | Fake log | Raw outputs saved under `runs/<id>/`; the verdict script reads raw files, not the worker's summary |

## Verdict hierarchy (strongest first)

1. Invariant check (static diff of the recipe against the allowlist) — a fail is final.
2. Speed measurement (stage 1), against the champion before, beyond the noise floor. Not a win: the pass ends here.
3. Quality check (stage 2: logprob fidelity, needles, tool suite) on the same running server — a fail is final.
4. Held-out check, only in the mode the owner chose: it names its stage (PASS, FAIL quality, FAIL gain).
5. Final truth: the champion is measured again on the owner's own machine before it enters his real recipe. His word decides.

A weaker layer can never overrule a stronger one.
