# Host facts

The one home for what each harness can do. Checked 2026-10-20 to 2026-11-12; hosts change fast, so when a fact matters, check the linked source. Marks: **ran** (run by the author), **doc** (the host's docs or bundled guide), **source** (its source code). For a harness not listed, read its docs and use the plain instruction at the end.

Every prompt carries the done command or stop line, the run file path to re-read each turn, and the 2-3 limits that must hold. Default on every host that has it: its own `/goal`, driven by completion notices, with no wake task and no cron.

| Host | Run to done | Clock wake | Headless | Skill folder |
|---|---|---|---|---|
| Claude Code | `/goal` | `/loop` with `ScheduleWakeup`, `CronCreate` | `claude -p "/goal …"` loops to the end (ran); `/loop` needs a live session (ran) | `~/.claude/skills`, `.claude/skills` |
| Codex CLI and app | `/goal` | Scheduled tasks: desktop app and web only (doc) | `codex exec` does not expand `/goal` (ran); a `Stop` hook loops (ran) | `~/.agents/skills`, `.agents/skills` |
| Antigravity `agy` | `/goal` | `/schedule`, the `schedule` tool (ran) | `agy -p "/goal …"` loops (ran) | `~/.gemini/config/skills` (a real copy, not a junction: ran), `.agents/skills` |
| T3 Code | `/goal` in a Claude or Codex thread (doc, source) | `schedule_task` | Start inside a T3 thread at Full access; outside a thread a task cannot bind (ran) | the provider's own folder |
| pi with lapi | plan file with a `lapi-workflow` fence, then `/code` (source) | none | not run | `~/.agents/skills` (`/skill:sigmaloop`) |
| Stock pi, Gemini CLI | none: plain instruction | none | `pi -p`, `gemini -p` | `~/.agents/skills`, `~/.gemini/skills` |

Invoke the skill the host's way: `/sigmaloop` in Claude Code, `$sigmaloop` in Codex (it is typed-only there: `allow_implicit_invocation: false`), `/skill:sigmaloop` in pi. In Git Bash on Windows a leading `/word` argument is rewritten to a path (ran): use PowerShell or `MSYS_NO_PATHCONV=1`.

## The default prompt

```text
/goal <Title> is done: `<one command>` prints <exact text>. Every turn: read <run file path> first and follow it and its flow exactly; refill a builder slot in the same turn its job ends; never schedule a wake or poll; print the command's output at the end of each turn. Limits: <the 2-3 rules that must hold>.
```

Keep it under 4,000 characters (Claude Code and Codex cap the condition there). Add `or stop after N turns` to bound it.

## Claude Code

- `/goal` ([docs](https://code.claude.com/docs/en/goal)) starts another turn after each turn until a small model judges the condition met; that model reads only the conversation, so each turn prints the done command's output (doc). Several turns in a row with no tool use stop it with the goal still set (doc), so a turn that waits on jobs ends with them running and their completion notices start the next turn.
- At most 3 idle check-ins follow when agents still run, the first after 30 minutes (`CLAUDE_CODE_GOAL_CHECKIN_MINUTES`, `0` turns them off) (doc). A usage limit pauses the goal; an auth failure or a context overflow clears it (doc). `--resume` brings the goal back, but background shells never come back (doc): restart each job from its last commit.
- Permissions are inherited: set auto mode or an allowlist first, or the run stalls on a prompt (doc).
- Crew: Agent calls with `isolation: "worktree"`, in the background.
- `/loop` only for work that waits on a clock: end each turn with `ScheduleWakeup` (1800-3600 s, a fallback; notices wake sooner), `stop: true` at the stop line. A turn with neither gets one fallback wake about 20 minutes later, then the loop ends; a recurring task expires after 7 days (doc).

## Codex

- `/goal [<objective>|clear|edit|pause|resume]` persists across turns until complete, paused or limited (doc). The `goals` feature is stable and on (ran, `codex features list`). Each continuation turn asks the model to prove every requirement from files and command output before it calls `update_goal` (source). No timer: a clock stop line works only if the objective says to read the clock each turn.
- Headless: `codex exec "/goal …"` ran one plain turn (ran). Use a `Stop` hook in `.codex/hooks.json` that prints `{"decision":"block","reason":"…"}` (doc; ran under `--dangerously-bypass-hook-trust`), or re-run `codex exec resume --last` from a shell loop.
- A large finding goes back to the same agent by `send_input`. `/goal pause` and `/goal clear` stop it; it stops at a plan limit.

## Antigravity and Gemini CLI

- `agy` `/goal` runs until done or cancelled (doc); `agy -p "/goal …"` ran two turns and exited 0 (ran). Its `schedule` tool takes `DurationSeconds` and `MaxIterations` (ran). A `Stop` hook printing `{"decision":"continue","reason":"…"}` re-enters the loop (doc). Unattended: `--dangerously-skip-permissions` (ran).
- Prompt: the default prompt, plus for a clock: `If the work must wait on a clock, use your schedule tool (DurationSeconds, MaxIterations) and re-read <run file path> when it fires.`
- Gemini CLI has no loop and no scheduler; its `AfterAgent` hook with `decision: "deny"` forces a retry (doc). Use the plain instruction or that hook.

## T3 Code

- T3 starts other agents and has no loop of its own: native `/goal` on a Claude or Codex thread (doc: `composer.md`). T3 reads `/goal` in the message path, so the first message, a queued message and `t3_thread_send` all work (source). Stop on a Claude thread keeps the goal; on Codex it pauses (doc). T3's Claude adapter does not handle `ScheduleWakeup` or `CronCreate` (source): the schedule is the wake.
- Crew: `orchestrator_capabilities` once, then each worker is `delegate_task` with `isolation: 'worktree'`, `mode: 'async'` and a `target` model; a finished child wakes its parent (ran). A review or re-check is a fresh `delegate_task`. Read a child's status file or result, not its thread: `t3_thread_read` starts at the first message and costs a lot (ran). A child may not run at wider permissions than its parent (source): start the planner at **Full access**.
- Only the thread that owns a PR watches it (`watch_pull_request`), children never; `unwatch_pull_request` before stopping.
- `schedule_task` (clock, or run to done on a thread that is neither Claude nor Codex): the schedule is `{type:'interval', everyMs}` (minimum 60000), `{type:'fixed_time', timeOfDay, weekdays}` or `{type:'webhook'}`; `bindToCurrentThread` defaults to true (source). There is no update tool: call `schedule_task` again with `scheduledTaskId` (`enabled=false` pauses); `delete_scheduled_task` ends it (ran). Each run is queued behind an active turn and the next one is due `everyMs` after the send, so set `everyMs` above the longest turn and `t3_queue` `cancel` extra wake messages at each wake (source). The task id goes on a `Wake task:` line in the handoff, since the prompt cannot name a task that does not exist yet.
- A restart or Stop holds queued messages until **Resume** in the composer (doc). The scheduler lives in the T3 server: keep it running (`t3 service install` on Linux and macOS; the app open on Windows) (doc).

## pi

- Stock pi has no loop and no scheduler (doc). lapi adds one: in Code mode, open `- [ ]` boxes inside `<!-- lapi-workflow -->` … `<!-- /lapi-workflow -->` in the dated plan file under `.pi/plans/` start the next turn each time the agent goes idle; it stops when every box is ticked or the agent writes `[LAPI_PLAN_DONE]` (source). The loop needs the interactive session: `pi -p "/code"` only switches mode (ran).
- Prompt: Plan mode writes the plan (mission, boundaries, order, landing, authorised) and the fence, one box per ranked item, and a last box that reads the clock and, before the stop line, adds the next items above itself. The owner starts it with `/code`; `Esc` pauses.

## Other hosts: plain instruction

```text
Work unattended until <time, zone>. You are the planner. Rules and order live in <run file path>: read it now and re-read it at the start of every item.
Never end your turn while an item is workable and the clock is before the stop line. At <time, zone> do Finish and send the final report as your last message.
```

Tell the user that nothing restarts the agent if it ends its turn early; a host's timer that sends "continue", or a `Stop` hook, is the wake.
