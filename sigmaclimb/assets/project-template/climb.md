# <Project> climb

- Target: <the thing to improve and its starting version>
- Score: <what counts as better under real use>
- Guards: <quality checks and protected measures>
- Out of scope: <changes to put in the queue for another project>
- Stop line: <when to write STOP or let run_hours expire and report>
- Crew: <who runs passes and who picks blind pairs, if used>
- Compute: <where both sides are measured>
- Budgets: <step seconds, pass seconds, total hours or owner stop>

## Each turn

Read this file first. Read the current pass, champion, and last results. Recover a stalled pass first. Identify its process tree, stop it, run cleanup and record the CRASH. While a command runs, stay with it or arrange for the harness to wake you. End every turn with `python climb.py status`.

## Setup once

1. Fill `project.json` from the signed spec. Set the caps and target commands. Bring up the target and smoke-test the owner's recipe.
2. Run the baseline with `python climb.py run runs/0001 <change-file> --full`. Use the same inputs and warmup for the remaining unchanged runs. Count the baseline toward `repeats`. Check raw scores and quality. Record BASELINE and AA rows.
3. Run `python climb.py lock runs/0001 runs/0002 runs/0003` with the actual unchanged runs. For a held-out check in advisory or required mode, run `python climb.py heldout selftest` and fix a failed self-test before using its answers.

## Profile

Measure where the time or errors go. Update the table below. Rank pending ideas by the measured share of the part they affect times their chance of working (`p=NN%` in notes).

## The pass

1. Take the top idea. Read past results and dead rows, then mark it trying. Start from the champion and make ONE change. Write the invariant check for this run.
2. Run `python climb.py run runs/NNNN <change-file>`, then `python climb.py verdict runs/NNNN`. Only STAGE1-WIN earns a quality check during a normal pass.
3. Append exactly one results row per pass with `python climb.py record --run runs/NNNN --idea ID --category C --work CODE --part P --desc "..."`. Select CODE, SETTING or TEXT. Describe the change, evidence and outcome.
4. On KEEP, obtain any confirmation or held-out answer, run `python climb.py promote runs/NNNN` with the confirmation run if needed, then commit the promoted recipe. Otherwise restore the target to the current champion. Record a dead idea's failure and reopening condition in its notes. Capture a side quest as an ideas row.
5. Run `python climb.py check`. At each promotion, refresh the progress section, draw `python progress.py` and profile again.

## Rules that decide

Use the locked noise bands and the thresholds in `project.json`. Take trades to the owner and preserve their words with `promote --owner`. Keep three pending ideas. Change category after the configured streak. Fix an UNDER warning before the next idea.

## Invariants

<What must match the champion and how to check it.>

## Progress

| Part | Share | How measured |
|---|---:|---|
| <part> | <share> | <evidence> |

Best against the start: <champion, score, guard results and run>.

## Rulings

<One line per decision: `Ruling: <what> - <why> - <cost if wrong>`. The owner's own words go here with their date.>

## Finish

At the stop line, write `REPORT.md` with the best recipe, gain, guards, failures and next ideas. Run `python climb.py status`.
