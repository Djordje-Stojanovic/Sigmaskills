# GOAL.md - <PROJECT> climb (run file: re-read at the start of EVERY turn)

Host: <the agent host and its loop mode, for example Claude Code /goal or Codex /goal>. Stop line: <the stop rule
from the interview, for example: the owner destroys the rented instance, or writes STOP; then REPORT.md>.
Spec: `SPEC_DRAFT.md`. Settings: `project.json`. Fill every <...> from the signed spec; leave nothing in angle brackets.
One agent runs this loop. It starts no sub-agent.

## Mission
Make <TARGET> better on <SCORE> under the owner's real use, with no loss on <GUARDS>. One change per pass; it stays
only when `scripts/bench/verdict.py` says KEEP and `verdict.py promote` makes it the champion.

## Each turn
1. Read this file, `PROGRESS.md` (the profile and the champion table), the last 40 lines of `insights.md`, the head
   of `ideas.tsv`, `state/champion.json`.
2. Recover first: `state/pass.json` STARTED without FINISHED -> finish it from raw files or mark CRASH.
3. No `state/` -> SETUP. No profile in `PROGRESS.md` -> PROFILE. Else the next step of the current pass.
4. Never end a turn without a live background waiter on the running pass, unless the target is gone.
5. End every turn with `python scripts/status.py`. If it says UNDER HALF, fix the loop before the next idea.

## SETUP (once)
1. Bring the target up (serving example: `references/setup-vast.md` of the skill; the box files in `box/`).
2. Translate the owner's recipe into the change format (serving: `box/serve_base.sh` -> `scripts/bench/baseline_serve.sh`
   and `champion/serve.sh`). Smoke test.
3. Baseline with the quality references (`launch.ps1 -Record`), then `repeats` - 1 more runs of the unchanged target
   (`-Full`). Serving: `python scripts/bench/quality.py bands runs/0001 runs/0002 runs/0003`.
4. `python scripts/bench/aa.py runs/0001 runs/0002 runs/0003` writes `evaluator.lock`.
5. Held-out check: mode `<off | advisory | required>` from the interview. If not off: `heldout.dir` set,
   `python scripts/bench/heldout.py selftest .` says PASS before first use (`references/held-out.md`).
6. Rename `state.tmp/` -> `state/` LAST.

## PROFILE (after SETUP, after each KEEP, at every plateau)
Measure where the score goes, part by part (time per stage, bytes per stream, flaws per chapter). Write the table
(part, share, how measured) at the top of `PROGRESS.md`. Re-rank `ideas.tsv` by share x p.

## PASS (one idea)
1. Take the `pending` row with the highest share x `p=NN%`. Grep `results.tsv` + `ruled_out.tsv` first. Check that
   the setting exists and what its default is today. Every third pass (`bold_every`) is a code or design change.
2. A live switch: run a 10-minute ABAB kill test on the running target first. A bold idea: a spike of up to two
   hours with a dry test that needs no target.
3. `candidate/` = champion + ONE change. Write `state/pass.json` STARTED: the part, the hypothesis, the evidence.
4. Start the pass (serving: `.\scripts\launch.ps1 -Run NNNN -Serve candidate\serve.sh`; background
   `.\scripts\wait.ps1 -Run NNNN`). Stage 1 measures; stage 2 runs the quality check only on a STAGE1-WIN.
5. `python scripts/bench/verdict.py runs/NNNN`. Never override it.
6. `python scripts/record.py --run runs/NNNN --pass N --idea ... --category ... --work CODE|SETTING --part ... --desc "..."`
   (what changed; hypothesis + evidence; what happened; what it rules out).
7. KEEP -> `python scripts/bench/verdict.py promote runs/NNNN [runs/<confirm>]`. It asks for one confirmation run
   only when the gain is small, and for a held-out PASS only in `required` mode. ARCHIVE -> a table to the owner;
   his word promotes it (`--owner "<his words>"`).
8. Remove the idea from `ideas.tsv`; a dead idea -> `ruled_out.tsv` with what it rules out and a reopen condition.
9. One sentence to `insights.md`; `python check_state.py`. At a KEEP: commit, `python plot_progress.py`, rewrite
   `PROGRESS.md` in plain words, then PROFILE. `state/pass.json` FINISHED. Keep >= 3 pending ideas.

## Rules that decide (every number lives in project.json and evaluator.lock)
- The smallest gain, the drop bands, the confirmation rule, the quality share, the category switch and the bold slot
  are settings in `project.json`. One run and at most one confirmation per idea.
- After `category_switch_after` passes without a KEEP in one category: change category and PROFILE again.
- Same warm-up for both sides; never "fresh and empty" by default. One probe reads new input every run.

## Invariants (violation = VOID)
<what may never change: for a served model the weights, quantization, context length, served name, sampling
defaults, memory budget; the evaluator files == evaluator.lock>

## Never
- Touch the owner's own machines beyond read-only facts they allowed.
- Cut what the owner protects (quality, precision, steps) or game a probe (`docs/03_ANTI_GAMING.md`).
- Rent a second instance, destroy the instance (owner only), weaken container security, print a secret.
- Edit a bash script while it runs; hand-type numbers into TSVs.

## Finish
When the stop line holds: write `REPORT.md` (what changed for the owner first; every pass in plain words; champion
against the start and the owner's setup; final recipe + diff; failures and why; next ideas), then print
`python scripts/status.py`.
