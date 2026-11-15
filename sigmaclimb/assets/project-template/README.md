# <Model> speed loop on Vast.ai

Made from the sigmaclimb skill. Rules: GOAL.md (re-read every turn). Spec: SPEC_DRAFT.md.
Status: python scripts/status.py. Chart: python plot_progress.py -> progress.png.
Queue: ideas.tsv (sorted by p=NN%). Results: results.tsv. Dead ends: ruled_out.tsv. Learnings: insights.md.
Per-project constants (score weights, floors, Vast filters, image label): project.json.

## Held-out check

The loop may promote a champion only with a PASS from inputs it cannot read. `verdict.py promote` refuses without one.
Once per target, the owner makes the sealed set:

    sudo adduser --system --group climbseal; sudo install -d -o climbseal /var/lib/climb-sealed   # once per machine
    sudo -u climbseal python3 scripts/bench/heldout.py init /var/lib/climb-sealed/<project>

`init` prints the rest: write `inputs/check.py` there (the contract is in `heldout.py`), set `sealed_dir` in `project.json`,
and give the loop's user one `sudo` line that runs only the check. The loop sees PASS or FAIL. The results folder must belong
to another user: a second user, or a read-only mount from another machine. Keep `scripts/bench/`, `evaluator.lock`,
`project.json` and `state/` read-only to the loop's user, and run the candidate in `check.py` as a third user or in a sandbox.
The set allows 10 looks, one per run. After that, or after any leak, make a new set and say so in `insights.md`.
