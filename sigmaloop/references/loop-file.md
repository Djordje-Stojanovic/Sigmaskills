# The loop file

One Markdown file the loop agent re-reads at every wake (or, on hosts with no timer, at the start of every item). Edits apply on the next re-read. The host prompt stays short; everything long lives here.

Save to the place the user chose (default `.scratch/loops/<yyyy-mm-dd>-<slug>.md`). Keep it under about 1,400 words. Replace each `<...>`; delete a section only when the answers made it empty.

## Template

```markdown
# Loop: <title>

Host: <host>. Stop line: <date, time, zone>. Re-read this file at every <wake | item>: edits apply on the next one.

## Stance
Fill free slots from Priority. <Host wake rule, one line, from the host file.>
The user pre-authorises for this whole loop: <list from question 8>. Do not stop to ask; when no rule decides, take the safer option and log it as `Ruling: <what> - <why> - <cost if wrong>`.

## Goal
At the stop line every open item in <ticket or tracker> is ticked with dated evidence, or carries a dated log line: what was done, what is left, why, next step. <Overview or index file> is current.

## Crew
Shape: <solo | small crew: N workers, N reviewers, 1 clerk | large crew>, from question 1. Solo: this session builds, checks, self-reviews and lands each ticket; omit agent rules and model probes. Crew: each role keeps one job; apply the rules below.
1. **The orchestrator plans, starts agents and merges.** Workers own implementation tool calls; the orchestrator alone starts agents, keeping the crew visible in one thread.
2. **One whole ticket per worker** (Theo's tstack flow): finish, prove with the ticket's acceptance tests, review, PR, CI, merge. The orchestrator saves a full spec by path (`to-spec` if the repo has it) and sends the path. The worker reports once.
3. **`sol-loop` review: one reviewer per ticket, from another model family, at most 3 rounds, stop on nits.** The reviewer fixes small findings itself on the PR branch; only a large finding goes back to the writer (same agent, by follow-up message, so its context stays).
4. **First turn: one "say ok" task per model target** (from `orchestrator_capabilities`, never from memory). A target that fails moves to its fallback before any ticket starts.
5. Models: <cheap model> for bulk, research and harvests; <mid model> for workers; <top model> for planning and review only. Effort per role comes from the repo's rule. When a worker ends, its slot takes the most valuable eligible ticket in the same turn. Running agents count toward the cap. <Repo rules: banned models, background-shell limits.>
6. Headless calls (`claude -p`, `codex exec`) get closed input (`< /dev/null`, `ssh -n`, `stdin=DEVNULL`). A judge or persona called again and again keeps one session (`--resume <id>`).
7. Only the thread that owns a PR watches it. Children never watch.

## Cost rules
- Batch shell work in one script.
- **Never poll.** Wait for the completion notice (a finished agent or background job wakes you). A worker that commits nothing for 30 minutes is stopped, its work saved, and restarted. A stuck ticket is logged with its reason and skipped.
- Claude: 1-hour prompt cache (`ENABLE_PROMPT_CACHING_1H=1`); compact window the owner sets (for example 400k); batch many short chats into one session so the cache is reused; one-shot headless calls use `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` and `--disable-slash-commands`.
- CLIProxyAPI pools: fill-first (burn the account that resets first); session affinity keeps a thread on one account, so its cache stays. The quota card is the usage floor: skip a model whose weekly limit is low.
- Host facts: Claude Desktop ignores the hub address (host-managed) and cannot start T3 models (Muse Wonder, DeepSeek); run the orchestrator as a T3 thread.
- A cheap clerk does bookkeeping (ticks, handoff, status); merge ownership stays with the orchestrator.

## Each wake
1. Read the clock (<zone>). At or after the stop line: Finish.
2. Read the handoff and run <the repo's overview or status command>. Re-read this file at every wake or item; read changed tracker notes.
3. For each finished agent: give its slot the most valuable eligible ticket first. Send a finished ticket to a reviewer (another family). The orchestrator merges; the clerk ticks with dated evidence.
4. Fill every other free slot from Priority. Skip items that share files with a running agent.
5. Update the handoff (<path>): time, running agents and items, done since the last wake, queue. Rewrite it in full before each long wait and before the context fills.
6. <Host wake call and delay rule, from the host file.>

## Dated items
<Each one: date, time, zone, what happens. Claude Code: one `CronCreate` task each, created in the first turn. Delete the section when there are none.>

## Priority
<The ranked list, or the section of the tracker that holds it, with who owns what. Items that need the user live: wait; write their facts, never decide them. No-touch list: files, items, agents, systems.>

## Landing (every item, checked before its tick; a missing home = not done)
- Code or default first, with tests. <Repo test, lint, build commands.>
- Where the change must also land: <docs, skills, changelog, tracker, catalog, other repos>.
- Merge: <worktree off origin/base, never check out or reset in a shared checkout; PR; own diff check; squash merge; delete branch and worktree; fast-forward the local base>. Merge the newest main into the branch first, then run the checks on the merged tree. Never skip hooks.
- PR body: every check the repo's PR template names (for example Red test, Review, Skills lines) from the first push: <the template's lines>.
- Deploy: <the repo's deploy step and the live proof>, or "none".
- Commits say what, why, and how it was verified; end with <trailer the repo asks for>. PR bodies end with <line the repo asks for>.
- Secrets: never print a value; name the file by path.

## Worker prompt (every one carries)
- The path of its full spec, the user's words verbatim, and a checkable done line. "Build the whole ticket, check it against the acceptance tests, report once. Start no helper agents."
- Every input by path, never pasted. "Read each input whole, write each output in one Write. Code first, docs support it. Run the checks at the end of each acceptance step. Long commands run in the background; no sleep or poll loops. Commit each finished file on your branch."
- The skills or notes to load first, the Landing list, and the no-touch list.
- "New problem found: one file under <issues folder> and one pointer line in the tracker."
- "End: tick with dated evidence (numbers, paths, PRs), run <status command>, report short and plain."

## Only work that moves us forward
<The goal in the user's terms: better product, faster, a real bug fixed.> Keep one test that proves the change. A change that adds a step must remove a bigger one.

## When fewer than 3 items are workable
Search <repos and machines in scope> for the next improvement that moves us forward: a bug, a speed gain, a quality gain, a reliability fix. Write it as a new item (one file, one tracker line) and start it. Repeat until the stop line.

## Never
<Off-limits from question 6, one line each.>

## Finish (at the stop line)
Start nothing new. Let running agents finish and write their state into their item. Close helper servers. Prove sync, and print the proof: no open PR; no remote feature branch; one worktree; every machine on the same main commit (<machines>); docs and help pages updated; temp files deleted. Write the final handoff: done (with evidence), open (reason, next step), owner-only steps. Report in short plain English. <Host stop call, from the host file.>
```

## Rules for the file

- Every number comes from an answer or from the repo. Never invent a limit.
- Crew rules 1-7, every Cost rules line and the Finish sync proof are defaults: copy each one whole. Drop a line only when an answer contradicts it. The PR line names the repo's real template checks, or "none" when it has no template.
- Write rules as steps the agent can check, not as wishes. "Fill every free slot" can be checked; "be efficient" cannot.
- Name each authority once. A pre-authorised action is listed; an unlisted one means ask (or take the safer option and log it, when the loop must not wait).
- Point to the ranked order in the tracker; copy it only when no file holds it.
- Keep lab-specific words out unless they are the user's own tracker words.
