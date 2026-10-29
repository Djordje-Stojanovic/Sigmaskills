# GOAL.md - <MODEL> speed loop on Vast.ai (run file: re-read at the start of EVERY turn)

Host: <the agent host and its loop mode, for example Claude Code /goal or Codex /goal>. Stop line: the owner destroys the Vast instance. Spec: `SPEC_DRAFT.md`.
Fill every <...> from the signed spec before the first run; leave nothing in angle brackets.

## Mission
Make <MODEL> faster (decode, prefill/TTFT, agent replay, parallel requests) on one rented <GPU>, with zero
loss in quality or reliability, measured under the owner's real settings. One change per pass; keep it only
if `scripts/bench/verdict.py` says KEEP and a confirmation re-run agrees.

## Each turn
1. Read this file, `PROGRESS.md`, the last 40 lines of `insights.md`, the head of `ideas.tsv`, `state/champion.md`.
2. Recover first: `state/pass.json` STARTED without FINISHED -> finish it from raw files or mark CRASH.
3. No `state/` -> SETUP. Else the next step of the current pass.
4. Never end a turn without a live background `scripts/wait.ps1` unless the instance is gone.
5. End every turn by printing `python scripts/status.py`.

## SETUP (once)
1. Vast login with 2FA email code (`references/setup-vast.md` of the skill). Never pass `--api-key` later.
2. Test rental (5 min, cheap image): SSH, nvidia-smi, io_uring probe, HF speed, destroy.
3. Rent ONE box with image <IMAGE:TAG>, disk <GB>. Write `state.tmp/instance.json`.
4. Download weights (`box/download.sh`), verify sha256 (`box/verify_weights.py`).
5. Translate the recipe into `box/serve_base.sh`; copy to `scripts/bench/baseline_serve.sh` and `champion/serve.sh`.
6. First start + `box/smoke.py`. Fix engine blockers with code fallbacks, not security workarounds.
7. Baseline with `-Record`, then >= 3 A/A runs; `python scripts/bench/aa.py runs/A runs/B ... tool=runs/..`.
8. Write `state.tmp/champion.json` + `champion.md`; rename `state.tmp/` -> `state/` LAST.

## PASS (one idea)
1. Pop the `pending` row with the highest success probability (`p=NN%` in its notes; keep the file sorted by it, re-sort after every pass). Grep `results.tsv` + `ruled_out.tsv` first. **Check that the
   flag/env exists and its default in the installed engine** (`runs/*recon*/serve_help.txt`, envs.py).
2. `candidate/serve.sh` = champion + ONE change. Write `state/pass.json` STARTED with what must move and why.
3. `.\scripts\launch.ps1 -Run NNNN -Serve candidate\serve.sh`; background `.\scripts\wait.ps1 -Run NNNN`.
4. `python scripts/bench/verdict.py runs/NNNN`. Never override it.
5. `python scripts/record.py --run runs/NNNN --pass N --idea ... --category ... --work CONTENT --minutes M --desc "..."`
   (what changed; hypothesis + evidence; what happened; conclusion and what it rules out).
6. KEEP -> confirmation re-run. Promote only if confirmed: champion/, checkpoints/pass-N/, state/champion.json,
   champion/<recipe>.yaml with comments on what each change needs.
7. Remove the idea from `ideas.tsv`; recurring failure -> `ruled_out.tsv` with a reopen condition.
8. One sentence to `insights.md`; `python check_state.py`; `python plot_progress.py`; rewrite `PROGRESS.md`
   (<= 60 lines; one table: champion vs the owner's home setup); `state/pass.json` FINISHED. Keep >= 3 pending ideas (research round if short).

## Rules that decide (numbers live in project.json and evaluator.lock)
- Keep floor 5 %. Single-probe rule: one probe >= +10 % and every other >= -5 % is a KEEP.
- Every KEEP needs a confirmation run. Judge borderline cases on the median of 2-3 runs. Noise bands are large.
- Profile before you optimize. Measure the real memory-bandwidth ceiling before you say "at the limit".
- Never stack two overlay loaders (sitecustomize.py); merge them into one directory first.
- Stop line, decisions, research rounds, sub-agent rules: skill `references/loop.md`.

## Invariants (violation = VOID)
<weights/revision, quantization, KV dtype, max_model_len, max_num_seqs, served name, sampling defaults,
thinking, memory budget (GMU), MemAvailable floor during start, evaluator files == evaluator.lock>

## Docs: which source wins
1. The engine installed on the box (serve --help=all, envs.py, config/). 2. Context7 / upstream docs.
3. Web research for forum results and PRs.

## Never
- Touch the owner's own machines beyond read-only facts they allowed.
- Quantize further, cut precision, use a lossy sampler, or game a probe (`docs/03_ANTI_GAMING.md`).
- Rent a second instance, destroy the instance (owner only), weaken container security, print a secret.
- Edit a bash script while it runs; hand-type numbers into TSVs.

## Finish
When `scripts/status.py` shows the instance gone: write `REPORT.md` (every pass in plain English, champion vs the
owner's current setup, final recipe + diff, failures and why, next ideas), then print `python scripts/status.py`.
