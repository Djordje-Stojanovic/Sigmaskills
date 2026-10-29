# The loop file

One Markdown file the loop agent re-reads at every wake (or, on hosts with no timer, at the start of every item). Edits apply on the next re-read. The host prompt stays short; everything long lives here.

Save to the place the user chose (default `.scratch/loops/<yyyy-mm-dd>-<slug>.md`). Keep it under about 1,200 words. Replace each `<...>`; delete a section only when the answers made it empty.

## Template

```markdown
# Loop: <title>

Host: <host>. Stop line: <date, time, zone>. Re-read this file at every <wake | item>: edits apply on the next one.

## Stance
Be optimistic and aggressive: plan to finish every open item by the stop line, not just log it. Never idle: if no agent slot is free, do the next small item yourself. A free slot or an idle wake is a bug. <Host wake rule, one line, from the host file.>
The user pre-authorises for this whole loop: <list from question 7>. Do not stop to ask; when no rule decides, take the safer option and log it as `Ruling: <what> - <why> - <cost if wrong>`.

## Goal
At the stop line every open item in <ticket or tracker> is ticked with dated evidence, or carries a dated log line: what was done, what is left, why, next step. <Overview or index file> is current.

## Crew
Max <N> sub-agents at once: <mix by model and effort>. Model by difficulty: <small model> for research, sources, harvests and transcripts; <mid model> for code and drafts; <top model> for reviews and the hardest items. A review runs one model up; at most 2 review rounds per item. Jobs are given out dynamically: when an agent ends, its slot takes the most valuable eligible item for its model in the same turn; no slot owns a fixed lane. A fix round goes to the same agent at once by a follow-up message (Claude Code `SendMessage`, Codex `send_input`), so its context stays. Running agents count toward the cap. A headless agent called again and again (a persona, a judge) keeps one session (`claude -p --resume <id>`, `codex exec resume <id>`, or the repo's wrapper), so later calls read the prompt cache. Every headless call (`claude -p`, `codex exec`) gets closed input (`< /dev/null`, `ssh -n`, `stdin=DEVNULL`); with an open, empty stdin `claude -p` waits 3 s. <Rules from the repo: effort limits, banned models, background-shell limits.>

## Each wake
1. Read the clock (<zone>). At or after the stop line: Finish.
2. Re-read the tracker's how-to-work notes, the handoff, and every open line; run <the repo's overview or status command>.
3. For each finished agent: give its slot the most valuable eligible item first, then one quick check of its result (its key test or output). Fix wrong ticks, add dated evidence, merge or deploy what it left.
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
- Merge: <worktree off origin/base, never check out or reset in a shared checkout; PR; own diff check; squash merge; delete branch and worktree; fast-forward the local base>. Never skip hooks.
- Deploy: <the repo's deploy step and the live proof>, or "none".
- Commits say what, why, and how it was verified; end with <trailer the repo asks for>. PR bodies end with <line the repo asks for>.
- Secrets: never print a value; name the file by path.

## Sub-agent prompt (every one carries)
- The item file or line, the user's words verbatim, and a checkable "done when".
- Every input by path, never pasted. "Do the whole job in 10-20 tool calls: read each input whole, write each output file in one Write, split a huge input into parts by script first. No plan documents, no scaffolding. Code first, docs support it. Run the checks once, at the end. Long commands run in the background; no sleep or poll loops. Commit each finished file on your branch, so a usage limit loses nothing. Hill-climb to completion; a loss still gets its numbers written."
- The skills or notes to load first.
- The Landing list above and the no-touch list (files running agents own).
- "New problem found: write one file under <issues folder> and one pointer line in the tracker."
- "End: tick with dated evidence (numbers, paths, PRs), run <status command>, report short and plain."

## Only work that moves us forward
<The goal in the user's terms, for example: better product, faster, a real bug fixed.> No new scaffolding, no extra gates, no double-checking, no over-testing (one test that proves the change), no reports for their own sake. A check that never caught anything is cut. A change that adds a step must remove a bigger one.

## When fewer than 3 items are workable
Search <repos and machines in scope> for the next improvement that moves us forward: a bug, a speed gain, a quality gain, a reliability fix. Write it as a new item (one file, one tracker line) and start it. Repeat until the stop line.

## Never
<Off-limits from question 6, one line each.>

## Finish (at the stop line)
Start nothing new. Let running agents finish the current step and write their state into their item. Close helper servers. Delete merged worktrees and branches. Write the final handoff: done since the start (with evidence), open (reason, next step), steps only the user can do. Report in short plain English. <Host stop call, from the host file.>
```

## Rules for the file

- Every number comes from an answer or from the repo. Never invent a limit.
- Write rules as steps the agent can check, not as wishes. "Fill every free slot" can be checked; "be efficient" cannot.
- Name each authority once. A pre-authorised action is listed; an unlisted one means ask (or take the safer option and log it, when the loop must not wait).
- The ranked order is a pointer when the tracker already holds it (a section name, a file). Copy it only when no file holds it.
- Keep lab-specific words out unless they are the user's own tracker words.
