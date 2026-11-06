# Claude Code: `/goal` (default), `/loop` (option)

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See [hosts.md](hosts.md) for the table and the plain instruction.

Facts ([/goal](https://code.claude.com/docs/en/goal), [scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks)):

- `/goal <condition>` starts a turn at once and starts another after each turn until a small model judges the condition met (doc). That model reads only the conversation, so the condition names a command whose output each turn prints. Up to 4,000 characters; add `or stop after N turns` to bound it. `claude -p "/goal …"` ran two working turns and exited 0 (ran).
- Agents still running at turn end skip the check, and at most 3 idle check-ins follow (doc). So a turn that waits on jobs ends with the jobs running; their completion notices start the next turn. A usage limit pauses the goal; an auth failure or a context overflow clears it (doc).
- `--resume` brings back the goal. Background shells never come back (doc): restart their jobs from the last pushed commit.
- Permissions are inherited. Set auto mode or an allowlist first, or the run stalls on a prompt (doc).
- `/loop <prompt>` is the option for work that waits on a clock. The next wake is `ScheduleWakeup`; `stop: true` ends it; a turn with neither gets one fallback wake about 20 minutes later, then the loop ends (doc). `/loop` needs a live session: `claude -p "/loop …"` ran once and exited (ran). A recurring task expires after 7 days (doc).

## Default: one `/goal` run, no wake task, no cron

```text
/goal <Title> is done: `<one command>` prints <exact text>. Every turn: read <loop file path> first and follow it exactly; refill a slot in the same turn its job ends; never schedule a wake or poll; print the command's output at the end of each turn. Limits: <the 2-3 rules that must hold>.
```

Crew: builders and reviewers are Agent calls with `isolation: "worktree"`, run in the background; a completion notice starts the next turn. Put order, crew, landing and the handoff path in the loop file.

## Option: `/loop` (only when the work waits on a clock)

```text
/loop <Title> until <time, zone>. Re-read <loop file path> at every wake. WAKE: end every turn with ScheduleWakeup <1800-3600> s, a fallback only: completion notices wake you sooner. STOP: at <time, zone> do Finish in the loop file, then ScheduleWakeup with stop: true.
```

Tell the user: set the permission mode; keep the machine on; `Esc` stops it.
