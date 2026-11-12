# The loop file

One Markdown file the loop agent re-reads at the start of every turn. Edits apply on the next turn. The host prompt stays short; everything long lives here.

Save to the place the user chose (default `.scratch/loops/<yyyy-mm-dd>-<slug>.md`). Keep its rules under about 1,200 words and the whole run file under <60> KB: rewrite the state section, never append to it; old notes go to <log file>. Replace each `<...>`; delete a section only when the answers made it empty.

## Template

```markdown
# Loop: <title>

Host: <host>. Stop line: <done command and its text, and/or date, time, zone>. Re-read this file at the start of every turn.

## Stance
The user pre-authorises for this whole run: <list>. Do not stop to ask; when no rule decides, take the safer option and log `Ruling: <what> - <why> - <cost if wrong>`.
Speed metric: <accepted output per hour and per token, in the user's unit>. Drafted output that is not accepted counts as zero.
Owner's words: <path>. First turn: copy his messages from this chat into it verbatim, one per numbered line. Every turn, copy each new one before anything else. Cite a line as `W<n>`.
Owner page: <path or url>. Questions first: one card each, with A, B, C, your pick first and what happens with no answer; he answers in one reply block. A ticket that needs him is skipped, never waited on.

## Budgets
No meter, no budget. One block each; the quote is the owner's sentence and its date.
- <name>: <what>, limit <n> per <period>, split <family share, ...>. Meter: `<command>` prints used against the limit (and `next=<family>`). At the limit: <action>. "<his sentence>" (<date>)
- Spend with no usage store (rentals, games, books): the meter is a ledger file, one line per spend, written before the spend.
A share is a rule of thumb: job difficulty picks the model, the share breaks ties. Never stop a running job for it.

## Goal
At the stop line every item in <tracker> is accepted with dated evidence, or carries a dated line: done, left, why, next step.

## Crew
Shape: <solo | crew of N slots | N lanes: read lanes.md>. Solo: this session plans, builds, self-reviews and lands each unit; drop the table and rules 1-4. Crew: roles and tiers (ids and effort only from the user or <repo model file>):
| Role | Tier | Model ids, in fallback order |
|---|---|---|
| Planner (orchestrator) | top | <ids> |
| Builder | <cheap or mid> | <ids> |
| Reviewer (another family than the builder) | <mid or top> | <ids> |
| Clerk (ticks, handoff, status) | cheap | <ids> |
1. The planner plans, starts jobs and merges. It does no builder's tool calls.
2. One whole unit per builder: build, prove with the unit's acceptance tests, commit. The brief is a spec path and a done line.
3. One review per pull request. The builder first re-reads its own diff in a fresh context. Then one gate before the merge, by another model family when one is free; the reviewer runs the change, not only reads it, and ends with MERGE or a finding list. The builder fixes each finding or dismisses it in writing; style nits are dropped. At most 3 rounds, 5 for security, data loss or publishing; a round with nothing new ends it. No human review.
4. When a job ends, its slot takes the most valuable eligible unit in the same turn. Slots: <N>, capped by CPU (below), not by habit.
5. Lanes only: workers end after one ticket, lane managers go on ticket after ticket, the top never ends before the stop line. Priority is one ranked list for all lanes, never one list per lane.
Guides (workers are briefed by the guide of their model): <links>

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
2. Read the handoff and any new owner message (copy it to the words file first). Run <status command>.
3. For each finished job: send it to review, or accept it; refill its slot at once.
4. Fill every free slot from Priority. Skip units that share files with a running job.
5. Rewrite the handoff (<path>), never append; the run file stays under <60> KB and old notes go to <log file>: running jobs with process ids and worktrees, accepted since last turn, queue.

## Priority
<The ranked list, or the tracker section that holds it. Items that need the user live: write their facts, never decide them.>

## Landing
- Code first, with the unit's tests. <Changed-unit check command.>
- Also lands in: <docs, changelog, tracker>.
- Merge: <worktree off origin/base; PR; squash merge; delete branch and worktree>. Never skip hooks.
- Commits end with <trailer>. PR bodies end with <line>.

## Do not
- Run another review round when the last one found nothing new.
- Re-check the whole tree when one unit changed.
- Put a short time cap on a check that acceptance depends on.
- Cap the crew below what CPU and the queue allow.
- Keep a gate that never passes: fix it or cut it in the first hour.
- Write briefs, old reports or logs no machine reads.
- Schedule wake tasks that make empty turns.
- Count drafted lines as progress: watch accepted output per hour, and when it falls while drafting rises, stop drafting and land.
<Off-limits from the answers, one line each, with the owner's sentence and its date in quotes. A limit with no quote starts with `model:` and may be dropped if it blocks the run.>

## Finish (at the stop line)
Start nothing new. Let running jobs finish and write their state. Run the full gate once and print it. Prove sync: no open PR of this run, one worktree, no stray process. Write the final handoff: accepted (with evidence), open (reason, next step), owner steps.

## On stop (only when the owner asks)
Run sigmamusk, then `sigmamusk cut`, then sigmareview on the loop's own scaffolding. Target: half the scaffolding bytes and checks about 10x faster. Measure both before and after, and print the numbers.
```

## Rules for the file

- Every number comes from an answer or the repo; a `<30>` style default is a recommendation the question round confirms.
- Failure rules, Speed rules, Do not and Finish are defaults: copy each whole. Drop a line only when an answer contradicts it.
- Write rules as checks the agent can run, not as wishes.
- Fill the Guides line with the maker's guide for each model in the table (Anthropic first, OpenAI second, the rest third; links, never copies; checked 2026-11-12): Claude [best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices), the model page `.../prompt-engineering/prompting-claude-<model>`, [skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [subagents](https://code.claude.com/docs/en/sub-agents); OpenAI [latest model](https://developers.openai.com/api/docs/guides/latest-model), [AGENTS.md](https://developers.openai.com/codex/guides/agents-md); Google [prompt design](https://ai.google.dev/gemini-api/docs/prompting-strategies); DeepSeek [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode); Kimi [prompt practice](https://platform.kimi.com/docs/guide/prompt-best-practice); Meta [reasoning](https://dev.meta.ai/docs/reasoning). A model with no guide: say so in the file, do not guess.
- Model ids appear only in the Crew table. Everywhere else, name the role or tier.
- Host-only facts (wake tools, cache flags, proxies) belong in the host file, not here.
