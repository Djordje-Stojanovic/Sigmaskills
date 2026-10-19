# Example: a filled loop file

Adapted from a real overnight run on a repo with one big ticket and many sub-tasks. Paths and names are generalised. Host: Claude Code `/loop`. It shows how the template reads once filled: the crew mix, the landing list, the sub-agent prompt, and the finish block did the work.

The host prompt that went with it was one line plus the wake rule:

```text
/loop Overnight ticket T-12 until 11:00 Vienna. You are the orchestrator. Re-read .scratch/loops/overnight-T-12.md at every wake: edits apply on the next wake. Always end every turn with ScheduleWakeup (60-120 s after an agent ends or a merge needs a check, else 900-1200 s); a turn without it ends the loop. At 11:00 do the Finish block, then ScheduleWakeup with stop: true.
```

The loop file:

```markdown
# Loop: Overnight ticket T-12

Host: Claude Code /loop. Stop line: 2026-10-19 11:00 Vienna. Re-read this file at every wake: edits apply on the next wake.

## Stance
Be optimistic and aggressive. Plan to finish EVERY open item by 11:00, not just log it. Never idle: if no agent slot is free, do the next small item yourself. A free slot or an idle wake is a bug. Always reschedule before a turn ends (a turn without ScheduleWakeup ends the loop).
The owner pre-authorises for this whole loop: commit, push, PR, squash merge, deploy (the repo's four deploy commands), and deleting merged worktrees and feature branches. Do not stop to ask; take the safer option when no rule decides, and log it.

## Goal
At 11:00 every open item in .scratch/T-12/issues/T-12-main.md is done with dated evidence, or has a dated log line: what was done, what is left, why, next step. The overview file is current.

## Crew
Max 4 sub-agents at once: 2 Haiku (xhigh), 1 Sonnet (high), 1 Opus (medium). Never max effort. Opus = hardest items. Sonnet = big kit or skill items. Haiku = measurement, backfills, doc landings, installs, verification, cleanup. When one ends, start the next item in the same turn. Running agents count toward the 4.

## Each wake
1. `date` (Vienna). At or after 11:00: Finish.
2. Re-read the ticket's "How to work", the Handoff, and every open line; run the overview script.
3. For each finished agent: one quick check (its key test or output). Fix wrong ticks, add dated evidence, merge or deploy what it left.
4. Fill every free slot from Priority. Skip items that share files with a running agent.
5. Update the Handoff: time, running agents and items, done since the last wake, queue.
6. ScheduleWakeup: 60-120 s right after an agent ends or a merge/deploy needs a check; else 900-1200 s (agent notifications wake you sooner).

## Priority
The ticket section "Overnight order" is the order; follow it top down. A second agent (the pi agent) works in the same ticket in parallel: its rows (T1-T12, the publishing rows) and the publishing files are NOT ours. Re-read the ticket right before every write. Rows marked "needs the owner live" wait for him: write their facts, never decide them.
Never: items marked owner-only, screenshots of the hypervisor UI, restarting the container that holds a running terminal session.

## Landing (every item, checked before its tick; a missing home = not done)
- Code or default first, with tests. A live shared kit: copy, test, one atomic write, keep line endings. Never edit finished work folders. Back up a file before a risky edit.
- Also lands in: docs, the local skills, the glossary, the user guide, the catalog, one dated learning line per lesson.
- Second repo: worktree from origin/main outside the main checkout (never check out or reset the main checkout), docs and tests, PR, own check, squash merge, delete branch and worktree, then fast-forward the main checkout when it is clean and run the sync command.
- Website docs: run the sync script, the site tests, push, and check the health endpoint shows the new commit. If another session's pre-push hook blocks, log it and move on (never --no-verify).
- Checks: the full test suite in the kit (~90 s, safe in parallel), the repo check script, the doc coverage script; name failures that are not yours. A live proof after every deploy.
- Commits say what, why, and how verified; end with the trailer. PR bodies end with the generated-with line.

## Sub-agent prompt (every one carries)
- The item file or line, the owner's words verbatim, and a checkable "done when".
- "Read what the item touches, then do the work. No plan documents, no scaffolding, no menus. Code first, docs support it. Never cut corners. Hill-climb to completion; a loss still gets its numbers written."
- The skills to load first. The Landing list. The no-touch list (files running agents own).
- "New problem found: one file in .scratch/T-12/issues/ + one pointer line in the ticket."
- "End: tick with dated evidence (numbers, paths, PRs, deploy versions), run the overview script, report short and plain."

## Only work that moves us forward
Better films, faster films, more views, or a real bug fixed. No new scaffolding, no extra checks or gates, no double-checking, no over-testing (one test that proves the change is enough), no over-engineering, no reports for their own sake. If a change adds a step to the film process, it must remove a bigger one.

## When fewer than 3 items are workable
Search all three repos and the live machines for the next improvement that moves us forward: a bug, a speed gain, a quality gain the viewer sees or hears, a UI that can look better, a reliability fix. Write it as a new item (one file + one ticket line) and start it. Repeat until 11:00.

## Finish (11:00)
Start nothing new. Let running agents finish the current step and write their state into their item. Close helper servers. Delete merged worktrees and branches. Final Handoff: done since the start with evidence, open with reason and next step, owner steps. Short plain-English report to the owner. ScheduleWakeup with stop: true.
```
