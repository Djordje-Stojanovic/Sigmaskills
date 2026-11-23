# Project files, the long run, steering, research, hand-off

## 1. File map of `assets/project-template/`

**Generic core** (any target; keep it as it is):

| Path | Role |
|---|---|
| `project.json` | every setting of the loop with its default and reason: measurer, weights, noise runs, smallest gain, confirmation rule, quality share, category switch, bold slot, held-out mode |
| `GOAL.md` | run file, re-read every turn; fill every `<...>` |
| `scripts/bench/run_experiment.sh` | one pass in two stages: score, stage-1 verdict, quality check only on a win; times every stage |
| `scripts/bench/verdict.py` | the only judge: VOID, CRASH, REJECT, ARCHIVE, STAGE1-WIN, KEEP; `promote` is the only writer of `state/champion.json` |
| `scripts/bench/aa.py` | noise bands from the unchanged runs, file hashes -> `evaluator.lock` |
| `scripts/bench/heldout.py` | the optional held-out check (`held-out.md`) |
| `scripts/record.py` | one `results.tsv` row from the raw files |
| `scripts/status.py` | the status line and the loop's own speed |
| `check_state.py`, `plot_progress.py` | TSV validator; `progress.png` with the champion chain back to the start |

**The serving example** (replace these for another target):

| Path | Role |
|---|---|
| `scripts/bench/target.sh` | the target's steps: start, warmup, score, quality, stop |
| `scripts/bench/speed.py`, `common.py` | score probes; writes `raw/score.json` |
| `scripts/bench/gate.py`, `quality.py` | quality check; `quality.py` writes `raw/quality.json` from A/A bands |
| `scripts/bench/invariants.py`, `bw.py`, `build_replay.py` | locked flags, bandwidth probe, agent replay traces |
| `scripts/box.ps1`, `launch.ps1`, `wait.ps1`, `box/*` | the rented box: run, push, wait, pull; download and smoke test |
| `docs/03_ANTI_GAMING.md` | the serving shortcuts and their blocks |

A run folder: `runs/<id>/raw/` holds `change`, `score.json`, `quality.json` (stage 2 only), `meta.json` (status and
seconds per stage) and the target's own files. `runs/<id>/verdict.json` is the verdict.

## 2. TSV headers

`ideas.tsv`: `id	status	idea	category	work_type	part	share	expected_effect	evidence	notes` (`part` = the profile
row it attacks, `share` = that row's share; `p=NN%` last in notes; sort by share x p)
`ruled_out.tsv`: `id	direction	why_it_failed	evidence	rules_out	reopen_condition`
`results.tsv`: `pass	utc	parent	idea_id	category	work_type	part	who	machine	verdict	vs_champion	vs_start	probes	quality	minutes	score_share	cost_usd	description`

Verdicts in `results.tsv`: BASELINE, AA, KEEP, ARCHIVE, REJECT, VOID, CRASH, RECON. Tabs only. Run
`python check_state.py` after every write.

## 3. The long-run prompt

The stop condition is the one line `scripts/status.py` prints: "LOOP FINISHED: ..." when the stop rule holds (the
owner destroyed the rented box, or wrote a `STOP` file, and `REPORT.md` exists), "LOOP RUNNING: ..." in every other
case. Paste the prompt after the setup files exist. Replace the first word with the loop command of the user's
harness. The table holds the harnesses met so far. For any other, find it (the user's words, your own tools), ask
once when unclear, and read its docs (context7, a web search, a fast sigmaresearch pass) for a run-to-done mode;
`sigmaloop` step 2 does the same.

```text
<host loop command> <Project> climb is done: `python scripts/status.py` prints "LOOP FINISHED". Every turn: read <project>/GOAL.md first and follow it exactly, then print the output of `python scripts/status.py` at the end of the turn. Never end a turn without a live background job that waits on the running pass. Limits: never touch the owner's own machines; never cut what the owner protects (quality, precision, the invariants); ideas.tsv keeps at least 3 pending ideas, sorted by share x odds; one change per pass, and only scripts/bench/verdict.py decides; start no sub-agent; never print a secret.
```

| Host | Loop command and stop check | Notes |
|---|---|---|
| Claude Code | `/goal`: a judge reads the transcript for the printed status line | The owner ends it with `/goal clear`. See `sigmaloop/references/hosts.md`. |
| Codex | `/goal`, with the status line as the done check | `sigmaloop/references/hosts.md` |
| pi, T3 Code, Antigravity | their own loop or goal mode | `sigmaloop/references/hosts.md` |
| No loop mode | the owner re-sends "continue" | Every turn still starts by reading `GOAL.md` and ends with the status line. |

- **"Every turn read GOAL.md":** an edit to that file steers the next turn. Put rulings there.
- **The limits in the prompt** are the ones a long session must not forget after its context is compacted.
- When the owner says stop, stop starting runs, even while the stop check still says RUNNING. Say what keeps billing.

## 4. How the owner steers

- The agent decides what a rule decides and logs `Ruling: <what> - <why> - <cost if wrong>` in `insights.md`. A
  real choice comes as **one table**: option, effect on each probe, risk, recommended answer. Keep the target busy
  with the next idea meanwhile.
- The owner may say "sort by chance", "run X first", "drop low-value ideas". Log each as `Owner <time>: ...`.
- **Never idle.** Each turn starts, measures, records, profiles or researches; the background waiter wakes you.
- A trade (ARCHIVE) comes as a table; the owner's word promotes it (`promote ... --owner "<his words>"`).
- Status answers, in plain words (`plain-words.md`): time, current pass and stage, last verdicts,
  the best setup against the start and the owner's setup, money left, the loop's own speed, and the chart.

## 5. Research rounds

Start one when fewer than 3 ideas are pending, when the profile changed, after `category_switch_after` passes without
a KEEP, or when asked. The agent that runs the loop does the research itself; it starts no sub-agent.

- Read `ideas.tsv` and `ruled_out.tsv` first; report only new ideas.
- Read the target's own source and docs first, then upstream issues and pull requests, then forums with raw data.
- Each idea: the part it attacks and its share, the exact change, the expected effect, the risk to the guards, and
  the evidence URL. Keep only ideas with a concrete code path or setting. At least one in three is a code or
  design change.
- Write the round to `docs/NN_RESEARCH_<topic>.md` and log the ordering ruling in `insights.md`.

## 6. Hand-off when usage runs out

Before the limit hits (or when asked), leave the project resumable by a fresh session:
1. `PROGRESS.md` current: the profile, the champion table against the start, the queue top, what runs now.
2. `state/pass.json` correct; any waiter job named in `PROGRESS.md` with its run id.
3. `insights.md` has every ruling and owner decision up to now.
4. `GOAL.md` still says what to do first on resume: recover the pass, then continue.
5. One line to the owner: what is running, when it ends, what the next session does first.
