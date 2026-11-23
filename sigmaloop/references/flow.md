# The flow of a run

Every run follows this file; the run file holds only its variables. Re-read both at the start of every turn.

## Four states

1. **Ready:** in the order list, not started.
2. **Working:** a builder has it.
3. **Reviewing:** a reviewer runs it. Findings send it back to Working.
4. **Landed:** merged (a PR per ticket) or on the feature branch (one PR).

## Roles

- **Planner.** Hands out work, starts reviewers, merges, runs the stop command. It does no builder's tool calls. When a job ends, its slot takes the next Ready ticket in the same turn.
- **Builder.** One fresh agent per ticket, in its own worktree, on a branch that carries the ticket id. It builds test-first, commits and pushes each finished part, and ticks that part off itself, where the to-do is: the spec issue's checkbox, the PR's checklist or the issue (a body on GitHub, never a file in the repo, so parallel builders never collide). Before `READY` it merges the newest base or feature branch into its branch and runs its checks, so the planner's merge is clean. It ends with `READY <PR or branch>`. It never waits for its own review: its slot is free.
- **Reviewer.** A role with no count and no queue: on each `READY` the planner starts one fresh reviewer at once, from another model family when one is free. It runs the change, changes nothing, and ends with `PASS` or a numbered finding list: facts and breakage, no style. A finding names the spec line it breaks or the command that shows the failure; anything else is a note and holds nothing up.
- Builders and reviewers start no agents and no multi-agent skill of their own: only the planner does.
- **The builder fixes each finding, and the planner merges.** Findings go back to the builder's thread, or a fresh builder with the old branch and the findings; it fixes each or dismisses it in writing. At most 2 rounds; a round with nothing new ends it.

## Landing

- **One feature branch, one PR (default).** The planner opens the feature branch and one draft PR whose body lists every ticket as a checkbox. Builders branch from the feature branch. On `PASS` the planner merges the ticket branch into it, ticks the box if the builder did not, and deletes the ticket branch and worktree. At the stop line the full gate runs once on the feature branch; green, the PR merges; red, it stays a draft and the handoff lists the failures.
- **A PR per ticket.** Each builder opens its own PR (`Closes #N`). On `PASS` the planner squash-merges it and deletes the branch and worktree.

## Each turn

1. Read the clock, the run file and the handoff. At the stop line: Finish.
2. Copy each new owner message into the owner's words file first.
3. For each finished job: `READY` starts a reviewer, `PASS` lands, findings go back. Refill every free builder slot from the order, skipping tickets that share files with a running job.
4. Rewrite the handoff, never append: running jobs with worktrees, landed since last turn, the queue. Print the stop command's output.

## When it goes wrong

- **Stuck:** a job with no new commit or output for 30 minutes gets one message; stuck twice, it is replaced by a fresh worker that gets the old branch. Read the time from its last commit, never by polling.
- **Provider:** one that fails twice (rate limit, a cut-off run) drops to last place in every fallback list. A job that fails twice moves one tier up.
- **No polling.** No sleep loops, no wake tasks, no "still waiting" turns: completion notices start the next turn.
- **The owner.** A ticket that needs him gets one card on his page (A, B, C, your pick first, what happens with no answer) and is skipped, never waited on. A call that can be undone: make it and log `Ruling:`. One that cannot: skip it and put it on the card.
- **Cleanup:** stop a process only by an id this run wrote into the handoff, never by name.

## Speed

- Accepted is final: never re-check a landed ticket. During the run, checks cover the changed units; the full gate runs once, at Finish.
- Keep only records a machine or the next turn reads: the handoff, the tracker, the run file.
- Several repos: each builder slot names its repo. Two jobs that meet in one file: the later one rebases, never overwrites.

## Finish

Start nothing new. Let running jobs end and write their state. Run the full gate once and print it. Prove: no open PR of this run except the one waiting for its gate, no worktree left, no stray process. Write the final handoff: landed (with evidence), open (reason, next step), owner steps, each checked once by running it.
