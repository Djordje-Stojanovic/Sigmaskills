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
CREW: max <N> sub-agents: <mix>.
LANDING: <one line: code + tests, docs, tracker tick with evidence, PR merged, branch + worktree gone, deploy proof>.
AUTHORISED: <list>. Take the safer option when no rule decides; log it.
WAKE: always end every turn with ScheduleWakeup (<60-120> s right after an agent ends or a merge needs a check, else <900-1200> s). A turn without ScheduleWakeup ends the loop.
STOP: at <time, zone> do the Finish block in the loop file, then call ScheduleWakeup with stop: true.
```

Tell the user: leave the session open and the machine on; set the permission mode; `Esc` stops it; a resumed session needs `/loop` again. For `/goal`, use the skeleton in [host-codex.md](host-codex.md) with "print the check" added to the objective.
