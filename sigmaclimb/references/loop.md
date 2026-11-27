# The loop: files, the pass, verdicts, cheats, steering, hand-off

## 1. The project folder

Copied from `assets/project-template/`. Every command runs from it.

| Path | Role |
|---|---|
| `climb.md` | the run file, re-read every turn: scope anchor, budgets, the pass, rules, the profile table, every ruling |
| `project.json` | every setting with its reason; `steps` holds the target's shell commands |
| `climb.py` | the one tool: `run`, `verdict`, `promote`, `lock`, `record`, `status`, `check`, `heldout` |
| `results.tsv` | one row per pass; only `climb.py record` writes it |
| `ideas.tsv` | the queue and the dead ends: `pending`, `trying`, `dead` |
| `progress.py`, `progress.json` | the chart `progress.png` and its config |
| `evaluator.lock` | noise bands and scorer hashes, from `climb.py lock` |
| `state/champion.json` | the champion; only `climb.py promote` writes it |
| `runs/NNNN/` | `raw/change`, `raw/score.json`, `raw/quality.json` (stage 2 only), `raw/meta.json`; `verdict.json` |
| `STOP`, `REPORT.md` | the owner's stop; the final report |

## 2. One pass

1. **Wake.** Read `climb.md`, then `python climb.py status`. `LOOP STALLED` (a pass ran past `pass_seconds`): kill its process tree, record a CRASH, restore the champion.
2. **Pick** the `pending` idea with the highest share x odds and mark it `trying`. First search `results.tsv` and the `dead` rows (a repeat costs a whole pass), and check that the setting exists in the installed target and its default today. Every third pass (`bold_every`) is a code or design change: the big gains live there.
3. **Cheap test first.** A live switch: an ABAB test of minutes on the running target. A bold idea: build its first hour with a dry test that needs no target; its effort estimate is a guess.
4. **One change.** The change file is the champion plus one change: a patch, a settings file, the new text. With `invariants` on, write `runs/NNNN/invariants.json` (`ok`, `problems`) before measuring; without it the pass is VOID.
5. **Measure.** `python climb.py run runs/NNNN <change-file>`. Every pass takes a new run id: `run` refuses one that already finished.
6. **Verdict.** `python climb.py verdict runs/NNNN`. Act on it as printed.
7. **Record.** `python climb.py record --run runs/NNNN --idea <id> --category <c> --work CODE|SETTING|TEXT --part <p> --desc "..."`. The description is the next session's memory: what changed, why, what happened, what it rules out. A failed idea turns `dead` with what would reopen it.
8. **Keep or revert.** KEEP: `python climb.py promote runs/NNNN`; when it asks for a confirmation, run the same change once more as `runs/MMMM` and promote with both; commit. ARCHIVE: one table to the owner, the next idea meanwhile; on his yes, run the change once more with `--full` (a trade has no quality check yet) and promote that run with `--owner`. Any other verdict: revert. Two changes that score the same: keep the one that deletes.
9. **Close.** `python climb.py check` prints `STATE: CLEAN`. At a KEEP: `python progress.py`, and profile again. Keep 3 or more `pending` ideas. End the turn with `python climb.py status`.

## 3. The verdicts

The right column is what the owner hears.

| Verdict | When | Say this |
|---|---|---|
| VOID | a scorer file changed (hash), or an invariant broke | the run does not count |
| CRASH | a step was killed at its cap or failed; no score | the run failed before it measured anything |
| REJECT | the quality check failed, or the gain is under the smallest gain | the change is not better; it is undone |
| STAGE1-WIN | the score wins; the quality check has not run | the change scored better; the quality check runs next |
| KEEP | the gain reaches the smallest gain, quality held, no probe dropped past its band | the change is better and stays |
| ARCHIVE | a trade: the score wins but a probe dropped, or one probe is clearly up and the total is short | better in one part, worse in another; you decide |

`promote` asks for a confirmation run when the gain is small (`confirm_below`). `--owner "<his words>"` promotes any scored verdict on his word, an ARCHIVE or a REJECT too; never a VOID, a CRASH, or a run without a passed quality check.

## 4. How a run cheats, and the block

| Shortcut | Block |
|---|---|
| Edit the scorer, its inputs, its parser or a step command | the hash lock in `evaluator.lock`: any edit makes the pass VOID |
| Do less work (shorter output, fewer steps, lower precision) | fixed work per probe; the quality check; the invariants |
| Reuse results left by an earlier run | a fresh seed or salt per request; the new-input probe |
| Best of N runs, or re-run until it wins | one verdict per pass; at most one confirmation; every run saved |
| Win by luck on a noisy machine | the noise bands; champion and candidate in the same state |
| Buy the win with more memory, clock or cores | the invariants; peak use recorded |
| Claim a result it did not run | the verdict reads `runs/NNNN/raw/` |
| Tune to the visible inputs | the new-input probe; the held-out check where the owner wants it |

## 5. The held-out check

The same score and quality check on inputs the loop never tuned to, on the candidates' machine. When the owner runs the target on his own machine, his run there is the held-out check.

| `heldout` mode | What `promote` does | When |
|---|---|---|
| `off` | nothing | the default |
| `advisory` | prints the answer, promotes anyway | he wants to see whether a gain transfers |
| `required` | refuses without a PASS for this exact change | only when he opts in, in his own words |

- The check is `check.py` in the folder `heldout.dir` names, written by the owner or with his inputs. It is called as `python check.py <project folder> <run folder>` under `budget.step_seconds`, and its last printed line is JSON: `{"quality_ok": true, "gain": 0.04}`. The gain is in the score's own unit: the ratio minus 1, or the share of pairs won minus 0.5.
- `python climb.py heldout selftest` runs the check on the unchanged champion before first use. A check that fails the champion is broken, not strict: tell the owner and leave it off until it passes.
- `python climb.py heldout check runs/NNNN` answers `PASS`, `FAIL quality` or `FAIL gain` (the gain did not transfer), with no numbers.
- `FAIL quality` on a change that cannot alter the output: repeat the self-test before you believe it. `FAIL gain`: the idea turns `dead`. The loop goes on either way.
- A held-out input the agent saw (a log, an error message) is spent: make a new set and say so.

## 6. How the owner steers

- **He steers through `climb.md`**: an edit applies on the next turn. His rulings go there in his words, with the date and the runs they re-judge; old rows keep the rule they were judged by.
- The agent logs each ruling it takes there: `Ruling: <what> - <why> - <cost if wrong>`. A choice for him is one table (option, effect on each probe, risk, recommended answer); the next idea runs meanwhile.
- When he says stop, start no new pass, and say what keeps billing.

## 7. Research rounds

Start one when fewer than 3 ideas are `pending`, when the profile changed, after `category_switch_after` passes without a KEEP, or when asked. In a crew a worker can take it; the orchestrator writes the rows.

- Read `ideas.tsv` and `results.tsv` first; add only new ideas.
- Sources in this order: the target's own source and docs, upstream issues and pull requests, forums that show raw data.
- Each row: the part it attacks and its share, the exact change, the risk to the guards, the evidence URL, the odds. One in three is a code or design change.
- A gain someone else measured is worth a test, not an expected gain; such gains do not add up.

## 8. Hand-off

Three checks: `python climb.py check` prints `STATE: CLEAN`; `climb.md` holds the profile, every ruling and what to do first; one line tells the owner what runs, when it ends and what the next session does first.

## 9. Plain words for the owner

A label appears only in a code span, after its phrase.

| Label | Say this |
|---|---|
| champion | the best setup so far |
| start | your setup as it was before the loop |
| promote | make the change the new best setup |
| guard | a measurement that may not get worse |
| smallest gain | the gain needed to be sure it is not luck |
| lock | the fingerprint that shows nobody edited the measuring scripts |
| profile | where the time (or size, or flaw) goes, part by part |

A report or status answer starts with what changed for him, then one table (the best setup against the start and against his current setup), then what runs now, what comes next and the money left.

Bad: "P9 KEEP, gate ok, ARCHIVE on c3."
Good: "Pass 9: the change is better and stays (6 % faster than the best setup before). The quality test passed."
