# Claude Code: `/loop`, `/goal`

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See [hosts.md](hosts.md) for the table and the plain instruction.

Facts ([scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks), [/goal](https://code.claude.com/docs/en/goal)):

- `/loop <prompt>` with no interval is self-paced: after each iteration Claude picks a delay of one minute to one hour and prints it (doc). The next wake is the `ScheduleWakeup` tool; `stop: true` cancels the wake and ends the loop (doc).
- An iteration that ends with neither a reschedule nor a stop gets one fallback wake about 20 minutes later; if that iteration does not reschedule either, the loop ends (doc). So the prompt says: always reschedule before a turn ends.
- A scheduled prompt runs between turns. `Esc` clears the wake. The session must stay open and the machine on; a self-paced loop is not restored by `--resume` (run `/loop` again); a recurring task expires after 7 days (doc).
- Permissions are inherited. For an unattended run set auto mode or an allowlist first, or the loop stalls on a prompt (doc).
- A bare `/loop` reads `.claude/loop.md`; with a prompt the file is ignored, so the prompt must say to re-read the loop file (doc).
- `/goal <condition>` starts a turn at once and starts another after each turn until a small model judges the condition met (doc). That model reads only the conversation, so the condition must name a check Claude prints (a test result, `git status` clean). Up to 4,000 characters; add `or stop after N turns` to bound it. It works with `-p`: `claude -p "/goal …"` ran two working turns and exited 0 (ran). `claude -p "/loop …"` ran the prompt once and exited, with no wake (ran): `/loop` needs a live session.
- Pick `/goal` when the work never waits for a clock; pick `/loop` when it waits on CI, renders, or deploys, or the stop line is a clock time.

Prompt skeleton:

```text
/loop <Title> until <time, zone>. You are the orchestrator. Re-read <loop file path> at every wake: edits apply on the next wake.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: max <N> sub-agents: <mix>. When one ends, its slot takes the most valuable eligible item for its model in the same turn; a fix round goes to the same agent by SendMessage.
LANDING: <one line: code + tests, docs, tracker tick with evidence, PR merged, branch + worktree gone, deploy proof>.
AUTHORISED: <list>. Take the safer option when no rule decides; log it.
WAKE: end every turn with ScheduleWakeup <1800-3600> s, a fallback only: agent and background-shell notifications wake you sooner, so never wake to poll. A turn without ScheduleWakeup ends the loop.
STOP: at <time, zone> do the Finish block in the loop file, then call ScheduleWakeup with stop: true.
```

Tell the user: leave the session open and the machine on; set the permission mode; `Esc` stops it; a resumed session needs `/loop` again.

## Run mode: one `/goal` session (a run to done, hours or days)

Use it for a ticket with one checkable end state. Claude Code runs the work in turns; the judge model sees only what the turns printed (doc).

- **One printed command.** The goal line names one command whose output proves the end state, and every turn prints its result. The line stays under 4,000 characters.
- **Run file.** The loop file holds the rules. The goal line says "every turn: read it first", so an edit applies on the next turn. A change to the goal line itself needs a new `/goal`.
- **Dated items.** One `CronCreate` task each (a report at 12:00, a job on a date), created in the first turn. A recurring task expires after 7 days: create it again on day 7.
- **Handoff file.** Rewrite it before each long wait and when the context passes about two-thirds. After a compaction or a restart, the next turn reads the run file and the handoff.
- **Keep it running.** Every turn does real work (a tool call, a check, a started lane): turns without tools stop the loop. Agents still running at turn end skip the check, and at most 3 idle check-ins follow (doc). A usage limit pauses the goal; an auth failure or a context overflow clears it (doc).
- **After a restart.** `--resume` brings back the goal and the cron tasks, except recurring ones past 7 days and one-shots already past. Run `CronList`, re-create only the missing ones, and restart the lanes. Background shells never come back (doc).

```text
/goal <Title> is done: `<one command>` prints <exact text>. Every turn: read <loop file path> first and follow it exactly; print the command's output at the end of each turn. Limits: <the 2-3 rules that must hold>.
```

Write the rest of the host prompt into the loop file: ranked order, crew, landing, the cron list, the handoff path. Source: [/goal](https://code.claude.com/docs/en/goal), [scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks).
