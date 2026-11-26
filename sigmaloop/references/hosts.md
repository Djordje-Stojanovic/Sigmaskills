# Host facts and prompt skeletons

Checked 2026-11-26. Hosts change fast: when a fact matters, check the linked source. Each fact is marked **ran** (run by the author on Windows 11), **doc** (host documentation or its bundled guide), or **source** (host source code); a step not run says "live run pending".

## Pick the mechanism

Pick the row for the host and for how the run starts (a live session, or headless).

| Host | Loop that fits | Clock wake | Headless run | Skill folder |
|---|---|---|---|---|
| Claude Code | `/goal` (run to done, one printed command), `/loop` (clock) | `CronCreate`, `ScheduleWakeup` | `claude -p "/goal …"` loops to the end (ran). `/loop` needs a live session | `~/.claude/skills` or `.claude/skills` |
| Codex CLI and app | `/goal` | Scheduled tasks: desktop app and web only | `codex exec` does not expand `/goal` (ran). A `Stop` hook loops (ran) | `.agents/skills`, `~/.agents/skills` |
| Antigravity `agy` | `/goal`, `/schedule` | `schedule` tool: `DurationSeconds` + `TimerCondition`, or `CronExpression` + `MaxIterations` | `agy -p "/goal …"` loops (ran) | `.agents/skills`, `~/.gemini/config/skills`, `~/.agents/skills` (1.5.16+) |
| pi with lapi | Plan file with a `lapi-workflow` box fence, then `/code` | None | Not run | `~/.agents/skills` (invoke `/skill:sigmaloop`) |
| Stock pi | None: plain instruction | None | `pi -p`, RPC for a driver | same |
| T3 Code | `/goal` in a Claude, Codex, Antigravity (CLI 1.5+) or OpenCode (2.2.5+) thread (doc + source); `schedule_task` on other providers | `schedule_task` | Start in a T3 thread (Full access). Outside agents cannot bind `schedule_task` (ran) | the provider's own folder |
| Gemini CLI | None: plain instruction, `AfterAgent` hook | None | `gemini -p` | `.agents/skills`, `~/.gemini/skills` |

Invoke SigmaLoop the host's way (`/sigmaloop` in Claude Code and Antigravity, `$sigmaloop` in Codex, `/skill:sigmaloop` in pi). On Windows, Git Bash rewrites a leading `/word` argument to a path (ran, Claude Code and `agy`); use PowerShell or `MSYS_NO_PATHCONV=1` (ran).

## The `/goal` prompt

One skeleton for every host with a native `/goal` (Claude Code, Codex, Antigravity, and their T3 Code threads). The loop file holds the rest: order, crew, failure and speed rules, landing.

```text
/goal <Title> is done: `<one command>` prints <exact text>. Every turn: read <loop file path> first and follow it exactly; refill a slot in the same turn its job ends; never sleep or poll; print the command's output at the end of each turn. Limits: <the 2-3 rules that must hold>.
```

- Keep it under 4,000 characters (the Claude Code and Codex limit).
- A clock stop line: add `Read the clock each turn; at <time, zone> do Finish in the loop file.` No `/goal` reads the clock by itself.
- Watchdog on: add `Keep the loop file's watchdog timer set.`
- A goal changes how the agent stops, not what it may do. Tell the user to set the permission mode first, or the run stalls on a prompt.

## Workers, warm messages, watchdog

| Host | Start a worker | Message a warm worker | Watchdog |
|---|---|---|---|
| Claude Code | An `Agent` call with `isolation: "worktree"`, in the background; its completion notice starts the next turn (doc) | `SendMessage` to its id or name (doc) | Built into `/goal`: a check-in after 30 minutes of running background work. `CLAUDE_CODE_GOAL_CHECKIN_MINUTES=15` sets it; later check-ins back off (doc). No timer of your own |
| Codex | `spawn_agent` (doc) | `send_input` (doc) | None: the CLI has no timer (doc). The Stuck rule runs when any worker reports |
| Antigravity | `invoke_subagent` (`TypeName: "self"`, `Workspace: "branch"` for a worktree) (doc) | `send_message` wakes an idle sub-agent with its context (doc) | `schedule` with `DurationSeconds: 900`, `TimerCondition: "any"`: any incoming message cancels it and wakes the agent itself, so nothing piles up (doc) |
| T3 Code | `delegate_task` (`isolation:'worktree'`, `mode:'async'`); completion wakes the parent (ran) | `t3_thread_send` to the child's thread (ran: `mode:'steer'`) | Antigravity thread: its native `schedule` (ran). Other providers: the wake task of the scheduler skeleton below |
| pi, Gemini CLI | None | None | None |

## Claude Code

Facts ([/goal](https://code.claude.com/docs/en/goal), [scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks)):

- `/goal <condition>` starts a turn at once and another after each turn, until a small model judges the condition met (doc). That model reads only the conversation, so the condition names a command whose output each turn prints. Add `or stop after N turns` to bound it. `claude -p "/goal …"` ran two working turns and exited 0 (ran).
- A turn that ends with agents still running skips the check; their completion notices start the next turn. Check-ins come when a turn ends or, in a live session, on their own while it is idle: at most 3 idle ones between the user's prompts, none in `-p` (doc). `CLAUDE_CODE_GOAL_CHECKIN_MINUTES=0` turns check-ins and retries off (doc). Several turns in a row with no tool use stop the loop with the goal still set, so every turn does real work (doc). A usage limit pauses the goal; an auth failure or a context overflow clears it (doc).
- `--resume` brings back the goal. Background shells never come back (doc): restart each job from its own last commit, pushed or WIP.
- `/loop <prompt>` is the option for work that waits on a clock. The next wake is `ScheduleWakeup`; `stop: true` ends it; a turn with neither gets one fallback wake about 20 minutes later, then the loop ends (doc). `/loop` needs a live session: `claude -p "/loop …"` ran once and exited (ran). A recurring task expires after 30 days (doc).

```text
/loop <Title> until <time, zone>. Re-read <loop file path> at every wake. WAKE: end every turn with ScheduleWakeup <1800-3600> s, a fallback only: completion notices wake you sooner. STOP: at <time, zone> do Finish in the loop file, then ScheduleWakeup with stop: true.
```

Tell the user: keep the machine on; `Esc` stops a turn, `/goal clear` ends the goal.

## Codex

Facts ([slash commands](https://learn.chatgpt.com/codex/reference/slash-commands.md), [hooks](https://learn.chatgpt.com/docs/hooks), [scheduled tasks](https://learn.chatgpt.com/docs/automations), source of [openai/codex](https://github.com/openai/codex)):

- `/goal [<objective>|clear|edit|pause|resume]`. The goal persists across turns until complete, paused or limited (doc); `usage_limited` means a plan limit stopped it (source). Codex 0.163.0 lists `goals` as stable and on (ran: `codex features list`). An objective over 4,000 characters is stored as a file (source).
- Each continuation turn tells the model to judge progress from files and command output and to call `update_goal` only when every requirement is proved (source). A token budget is optional.
- `codex exec "/goal …"` sent the text as a plain prompt: one turn, no continuation (ran). For a headless loop use a `Stop` hook: in `.codex/hooks.json` it prints `{"decision":"block","reason":"…"}` and Codex starts a new turn with the reason as its prompt (doc; a two-iteration hook ran under `codex exec --dangerously-bypass-hook-trust`). Else re-run `codex exec resume --last` from a shell loop.
- SigmaLoop sets `allow_implicit_invocation: false`, so Codex leaves it out of the skill list it shows the model. Type `$sigmaloop` (ran, `codex-cli` 0.163.0).
- Scheduled tasks exist in the desktop app and on the web, not in the CLI (doc).

Tell the user: `/goal pause` and `/goal clear` stop it; the goal stops at a plan limit.

## Antigravity

Checked against CLI 1.5.14-1.5.16 and App 2.35.1 ([`/goal`](https://antigravity.google/docs/commands/goal), [`/schedule`](https://antigravity.google/docs/commands/schedule), [subagents](https://antigravity.google/docs/subagents), [headless](https://antigravity.google/docs/cli/headless), [hooks](https://antigravity.google/docs/hooks)):

- **`/goal`**: no turn cap. A stop hook blocks an early stop and asks for evidence against real output; it waits for sub-agents and background tasks first. Starting a new `/goal`, or telling it to stop, cancels it (doc). `--input-format stream-json --output-format stream-json` runs many turns in one warm process (doc).
- **`schedule`**: a one-shot timer (`DurationSeconds`, `Prompt`, `TimerCondition`: `never`, `any`, or a sub-agent or task id) or a five-field `CronExpression` (`MaxIterations`, `IsDaemon`). Timers belong to the conversation; `manage_task` or `/tasks` lists and kills them (doc). `-p` waits for timers up to `--print-timeout` (ran).
- **Sub-agents**: `invoke_subagent` with `TypeName` `self`, `research`, `browser` or a custom agent (`.agents/agents/<name>.md`), `Workspace` `inherit`, `branch` (its own worktree) or `share`, and `Model` `inherit`, `flash_lite`, `flash` or `pro`. A sub-agent starts with no parent history; `manage_subagents` kills one and cleans its worktree; nesting stops at depth 10 (doc). A custom agent's `commandExecutionPolicy` defaults to `sandbox` (doc). `/swarm`, `/run-workflow`, `/teamwork` and `/boost` are the built-in crews; use one only when the user names it.
- **Permissions and resume**: `--mode auto` is the default since 1.5.7 where an OS sandbox exists. Headless `-p` soft-denies unapproved calls unless `--dangerously-skip-permissions` or `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` covers them (doc). Resume with `agy -c`, or `agy -r <id>` (1.5.16+).
- **Skills**: Windows needs a real copy in the global folder, not a junction (ran); `sigmaskills install sigmaloop --global --agent agy --yes` writes it.

Gemini CLI (legacy, not run): the plain instruction, or an `AfterAgent` hook returning `decision: "deny"`.

## pi

Facts for lapi, a pi setup with Plan and Code modes (source: its Plan and Code prompts; [pi docs](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent/docs)). `pi -p "/skill:sigmaloop …"` loads the skill (ran, Windows and Linux). The plan loop needs the interactive session: `pi -p "/code"` only switches the mode and exits (ran). Live run of the TUI loop pending.

- Stock pi has no loop and no scheduler (doc). In lapi's Code mode, while the dated plan file under `.pi/plans/` has open `- [ ]` boxes inside `<!-- lapi-workflow -->` … `<!-- /lapi-workflow -->`, lapi starts the next turn each time the agent goes idle. Boxes outside the fence are not a loop (source).
- The loop starts from Plan mode, which is read-only except `.pi/plans/`. In chat the plan is one `[LAPI_PLAN]` … `[/LAPI_PLAN]` block with nothing after it; the dated file holds the same block, then the fence. `/code`, or `/code-fresh` for a new session, starts Code mode (source).
- It stops when every box is ticked or the agent writes `[LAPI_PLAN_DONE]`. A turn with no write, edit or bash waits for the owner. `Esc` pauses; `/plan pause`, `/plan resume`, `/plan clear` (source).
- No clock: for a clock stop line, end with a box that reads the clock and, before the stop line, adds new boxes above itself.

```text
Plan mode. Use the answers in <loop file path>; ask nothing new. Write the plan: Mission (outcome, stop line <time, zone>), Boundaries, Invariants, Order (<loop file> "Priority"), Landing (<one line>), Authorised (<list>). Give it in chat as one [LAPI_PLAN] … [/LAPI_PLAN] block. Write the same block to the dated file under .pi/plans/, then the loop below it:
<!-- lapi-workflow -->
- [ ] Read <loop file path>. Do item <1> to its Landing as one full spec; tick it in the tracker with evidence.
- [ ] (one box per ranked item, the first <N>)
- [ ] Read the clock. Before <time, zone>: add the next items as new boxes above this one. At or after it: do the Finish block, then write [LAPI_PLAN_DONE].
<!-- /lapi-workflow -->
Then stop and wait: the owner starts the run with /code.
```

Stock pi: the plain instruction. An extension can ask for one more turn with `agent_before_settle` and `continue: true`, and a driver can send `follow_up` over RPC (doc).

## T3 Code

Checked against T3 Code 0.1.12 (`docs/user/` and live runs). T3 Code starts other agents (Codex, Claude Code, Antigravity, OpenCode, Cursor, pi, Muse) and has no loop of its own. **Default: the provider's native `/goal`, sent as the thread's first message, with no repeat timer.** T3 reads the command on the message path, so a queued message and `t3_thread_send` work too (source). Use the scheduler skeleton only when the stop line is a clock time or the provider has no `/goal`.

The crew:

1. First turn: `orchestrator_capabilities` once. Write the provider, model and options into the loop file's Models line; never guess a model id.
2. **Every worker that runs commands is a `delegate_task` child**, on every provider: `isolation:'worktree'`, `mode:'async'`, a `target` (`providerInstanceId`, `model`, `options`; `environmentId` for another machine), and a `task` that is the spec path, the done line and the loop file's worker rule (Crew, Bootstrap), since the child sees no parent history. End the turn; completion wakes the orchestrator (ran). A child cannot run wider than its parent (source): start the orchestrator at **Full access** and leave `runtimeMode` out.
3. In one Antigravity run (ran, 2026-11-26, 5 workers) native `invoke_subagent` workers stalled 60 s on shell commands and failed reads outside the worktree; the same work as `delegate_task` children ran clean. `agy` has stalled 60 s on sub-agent approvals under `agy acp` before (doc: changelog), and the T3 user can read a native sub-agent's work but cannot message or stop it (doc). Keep `invoke_subagent` for short read-only lookups.
4. A fix goes to the warm child with `t3_thread_send`: a send to a finished child starts a new task on its thread and returns the task id (ran: live tool list). A review is a fresh `delegate_task`. `task_status` and `task_cancel` take the task id. A child that ends on a usage or rate-limit error is the Provider rule's signal.
5. Wait on a child's result or status file, not its thread: `t3_thread_read` starts at the first message and costs a lot (ran).
6. `t3_thread_launch` makes a new top-level thread: only when the owner asks for one.
7. Landing: the worker opens the pull request. Only the thread that owns a PR watches it (`watch_pull_request`), then `unwatch_pull_request` before it stops. Write the merge permission in the loop file: some models will not merge without it. A question to the owner goes through the harness's question tool, or the thread looks finished.

Antigravity threads (managed CLI 1.5.14+): native `/goal`, `schedule` and the T3 tools (`mcp_t3-code_*`) work (ran). T3 tools can load late: try the name once before you call it absent. If one is still absent, on Windows pipe JSON to `$env:T3_ACP_MCP_CALL` (`'{}' | & $env:T3_ACP_MCP_CALL orchestrator_capabilities -`); on POSIX follow the `acp-mcp-call` line in the thread's T3 instructions. In Full access Antigravity can still ask a fixed-choice question (doc).

Stopping a goal: Claude keeps the goal after Stop and re-checks at the next message (`/goal clear` removes it). Codex and OpenCode pause on Stop (`/goal resume`). Antigravity stops the turn; then tell it to stop pursuing the goal, since T3 has no goal status, pause or clear for it (doc). Claude's `/loop` has no T3 handling (source): clock wakes use `schedule_task`.

### Scheduler skeleton (clock stop line, or a provider without `/goal`)

Live run pending.

```text
Work unattended until <time, zone | `<one command>` prints <exact text> or <N> wakes pass>. You are the orchestrator in this thread. Rules and order live in <loop file path>: re-read it at every wake.
FIRST TURN: call schedule_task {schedule:{type:'interval', everyMs:<900000>}, bindToCurrentThread:true, title:"<slug> wake", prompt:"WAKE. Read <loop file path> and <handoff path>. t3_queue list this thread and cancel any extra WAKE message. <Read the clock (<zone>). | Run `<one command>`, print its output and add 1 to 'Wakes' in the handoff.> Not done: do 'Each turn'. Done: do 'Finish', then delete_scheduled_task with the id on the 'Wake task' line of the handoff."} Write the returned scheduledTaskId on a 'Wake task:' line in <handoff path>. Then start item 1.
AUTHORISED: <list>. Do not stop to ask; when no rule decides, take the option that keeps work moving and can be undone; log it.
```

- **The schedule is an object:** `{type:'interval', everyMs}` (minimum 60000), `{type:'fixed_time', timeOfDay, weekdays}`, `{type:'once', runAt}` or `{type:'webhook'}` (ran: live tool list). `bindToCurrentThread` defaults to true inside a thread. There is no update tool: call `schedule_task` again with `scheduledTaskId` (`enabled=false` pauses). `delete_scheduled_task` ends it; the id sits in the handoff because the prompt cannot name a task that does not exist yet (source).
- **Overlap:** a run queues its prompt behind an active turn and counts as done when sent, so a turn longer than `everyMs` piles up wake prompts (source). Set `everyMs` at or above the longest normal turn and cancel extra wakes at every wake.
- **Server:** the scheduler lives in the T3 server. `t3 service install` keeps it up on Linux and macOS; on Windows keep the desktop app open (doc). A run caught by a restart is marked failed and the next is set from the restart time (source). A queue held by Stop or a restart waits for **Resume** in the composer (doc).
- **Stop:** the Stop button and `t3_thread_interrupt` leave the schedule alive, so a later run still queues: delete the task. Deleting the bound thread deletes its tasks (doc).
- **Outside agents:** an agent in a terminal can drive T3 through its MCP URL, but outside a thread `schedule_task` cannot bind (ran). Run the loop from an agent inside a T3 thread.

Tell the user: start a new thread in the project, pick the orchestrator's provider and model, **Full access**, and **New worktree** if the loop writes files; paste the prompt. Keep the machine on and the T3 server running. A usage limit holds the thread: **Resume at reset** (doc). At the end, settle the worker threads and delete any wake task left.

## Other hosts: plain instruction

For a harness whose docs show no loop command, one long instruction. The agent is the loop; "wake" means the start of each item.

```text
Work unattended until <time, zone>. You are the orchestrator. Rules and order live in <loop file path>: read it now and re-read it at the start of every item; edits apply on the next re-read.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
LANDING: <one line>.
AUTHORISED: <list>. Do not stop to ask; when no rule decides, take the option that keeps work moving and can be undone; log it.
Never end your turn while an item is workable and the clock is before the stop line. At <time, zone> do the Finish block in the loop file and send the final report as your last message.
```

Tell the user the limits: nothing restarts the agent if it ends its turn early. If the host has a way to send "continue" on a timer, or a `Stop` hook, use that as the wake.
