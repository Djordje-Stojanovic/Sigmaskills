# <Project> climb

Made from the sigmaclimb skill. Rules: GOAL.md (re-read every turn). Spec: SPEC_DRAFT.md. Settings: project.json.
Status: python scripts/status.py. Chart: python plot_progress.py -> progress.png.
Queue: ideas.tsv (sorted by share x p=NN%). Results: results.tsv. Dead ends: ruled_out.tsv. Learnings: insights.md.

## Generic core: keep these for any target

| File | Does |
|---|---|
| `project.json` | every setting of the loop, with its default and reason |
| `scripts/bench/run_experiment.sh` | one pass: score first, the quality check only on a stage-1 win |
| `scripts/bench/verdict.py` | decides, and `promote` makes the champion |
| `scripts/bench/aa.py` | noise bands and the hash lock |
| `scripts/bench/heldout.py` | the optional held-out check |
| `scripts/record.py`, `scripts/status.py`, `check_state.py`, `plot_progress.py` | results rows, status line, checks, chart |
| `GOAL.md`, `PROGRESS.md`, the TSV files | run file, owner page, queue and results |

## The worked example: a served model on a rented box

`scripts/bench/target.sh`, `speed.py`, `common.py`, `gate.py`, `quality.py`, `invariants.py`, `bw.py`,
`build_replay.py`, `scripts/box.ps1`, `launch.ps1`, `wait.ps1`, `box/*`, `docs/03_ANTI_GAMING.md`.

For another target, replace these:
1. `scripts/bench/target.sh`: the five steps of your target (start, warmup, score, quality, stop).
2. Its score step writes `raw/score.json`: `{"probes": {"name": value}}`, or `{"pairs": {"champion": {"won", "lost",
   "tied"}, "start": {...}}}` for blind pairs.
3. Its quality step writes `raw/quality.json`: `{"ok": true, "fails": []}`.
4. `project.json`: the probe weights, `lower_is_better`, the measurer, and the rest from the interview.
5. Your invariants check writes `runs/<id>/invariants.json` (`{"ok": true, "problems": []}`) before a pass; set
   `"invariants": false` in `project.json` only when nothing is locked.
6. The launch and wait scripts, if the target does not run on a rented box. Local: `bash scripts/bench/run_experiment.sh runs/0005 candidate/change.patch`.

## Held-out check

Off by default. To use it, set `heldout.mode` and `heldout.dir` in `project.json`, put the owner's `check.py` in that
folder, and run `python scripts/bench/heldout.py selftest .` once. The skill's `references/held-out.md` has the rest.
