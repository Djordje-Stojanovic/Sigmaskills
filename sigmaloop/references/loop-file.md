# The loop file

One Markdown file the loop agent re-reads at the start of every turn. Edits apply on the next turn. The host prompt stays short; everything long lives here.

Save to the place the user chose (default `.scratch/loops/<yyyy-mm-dd>-<slug>.md`). Keep it under about 1,200 words. Replace each `<...>`; delete a section only when the answers made it empty.

## Template

```markdown
# Loop: <title>

Host: <host>. Stop line: <done command and its text, and/or date, time, zone>. Re-read this file at the start of every turn.

## Stance
The user pre-authorises for this whole run: <list>. Do not stop to ask; when no rule decides, take the safer option and log `Ruling: <what> - <why> - <cost if wrong>`.
Speed metric: <accepted output per hour and per token, in the user's unit>. Drafted output that is not accepted counts as zero.

## Goal
At the stop line every item in <tracker> is accepted with dated evidence, or carries a dated line: done, left, why, next step.

## Crew
Shape: <solo | crew of N slots>. Solo: this session plans, builds, self-reviews and lands each unit; drop the table and rules 1-4. Crew: roles and tiers (ids and effort only from the user or <repo model file>):
| Role | Tier | Model ids, in fallback order |
|---|---|---|
| Planner (orchestrator) | top | <ids> |
| Builder | <cheap or mid> | <ids> |
| Reviewer (another family than the builder) | <mid or top> | <ids> |
| Clerk (ticks, handoff, status) | cheap | <ids> |
1. The planner plans, starts jobs and merges. It does no builder's tool calls.
2. One whole unit per builder: build, prove with the unit's acceptance tests, commit. The brief is a spec path and a done line.
3. One review per job, and it closes the job: the reviewer fixes findings in place, writes the acceptance record, writes the verdict. No confirm review, no re-review. Only a finding too large to fix in place goes back to the same builder by follow-up message.
4. When a job ends, its slot takes the most valuable eligible unit in the same turn. Slots: <N>, capped by CPU (below), not by habit.

## Failure rules
- **Stuck:** a job with no new commit and no new output for <30> minutes is stuck. Read the time from its last commit or log line, never by polling: check it when any notice wakes you.
- **Restart:** a stuck job gets a WIP commit, is stopped, and restarts from that WIP commit with the same brief. A job stuck <3> times is parked: write why in the handoff, take the next unit, never restart it again.
- **Provider:** a provider that fails twice (429, rate limit, or a cut-off run) drops to last place in every fallback list.
- **Tier:** a job that fails twice moves one tier up.
- **Cleanup:** remove a finished job's worktree; stop a stray process only by a process id this run wrote into the handoff, never by name and never an id it did not start.
- **No polling.** No sleep loops, no "still waiting" turns. Wait for completion notices.

## Speed rules
- **Accepted is final.** Never re-check a unit already accepted. Check only what changed since the last acceptance.
- **One full gate, at the end.** During the run, checks cover changed units only. The full gate runs once, at Finish.
- **Bulk compute.** Many small computations of the same kind run as one bulk job, not one run per unit.
- **CPU safety by parallel cap.** At most <N> heavy processes at once. Do not cap a single process at a few seconds; give it the time the work needs.
- **Records a machine reads.** Write a record only when a script or the next turn reads it: the handoff, acceptance records, the tracker. No briefs or reports kept for their own sake.

## Each turn
1. Read the clock (<zone>). At or after the stop line: Finish.
2. Read the handoff. Run <status command>.
3. For each finished job: send it to its one review, or accept it; refill its slot at once.
4. Fill every free slot from Priority. Skip units that share files with a running job.
5. Rewrite the handoff (<path>): running jobs with process ids and worktrees, accepted since last turn, queue.

## Priority
<The ranked list, or the tracker section that holds it. Items that need the user live: write their facts, never decide them.>

## Landing
- Code first, with the unit's tests. <Changed-unit check command.>
- Also lands in: <docs, changelog, tracker>.
- Merge: <worktree off origin/base; PR; squash merge; delete branch and worktree>. Never skip hooks.
- Commits end with <trailer>. PR bodies end with <line>.

## Do not
- Run more than one review per landing.
- Re-check the whole tree when one unit changed.
- Put a short time cap on a check that acceptance depends on.
- Cap the crew below what CPU and the queue allow.
- Keep a gate that never passes: fix it or cut it in the first hour.
- Write briefs, old reports or logs no machine reads.
- Schedule wake tasks that make empty turns.
- Count drafted lines as progress: watch accepted output per hour, and when it falls while drafting rises, stop drafting and land.
<Off-limits from the answers, one line each.>

## Finish (at the stop line)
Start nothing new. Let running jobs finish and write their state. Run the full gate once and print it. Prove sync: no open PR of this run, one worktree, no stray process. Write the final handoff: accepted (with evidence), open (reason, next step), owner steps.

## On stop (only when the owner asks)
Run sigmamusk, then `sigmamusk cut`, then sigmareview on the loop's own scaffolding. Target: half the scaffolding bytes and checks about 10x faster. Measure both before and after, and print the numbers.
```

## Rules for the file

- Every number comes from an answer or the repo; a `<30>` style default is a recommendation the question round confirms.
- Failure rules, Speed rules, Do not and Finish are defaults: copy each whole. Drop a line only when an answer contradicts it.
- Write rules as checks the agent can run, not as wishes.
- Model ids appear only in the Crew table. Everywhere else, name the role or tier.
- Host-only facts (wake tools, cache flags, proxies) belong in the host file, not here.
