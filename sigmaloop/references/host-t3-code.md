# T3 Code: `schedule_task`, `/goal`, and a crew of threads

Marks: **ran** (run by the author), **doc** (T3 user docs), **source** (T3 source). See [hosts.md](hosts.md) for the table and the plain instruction. A step not run says "live run pending".

Checked 2026-10-31 against T3 `0.1.6-nightly.20261030.3904`, source commit `36dac688a1` of [pingdotgg/t3code](https://github.com/pingdotgg/t3code) (`apps/server/src/mcp/toolkits/`, `apps/server/src/scheduledTasks/`, `packages/contracts/src/scheduledTask.ts`, `orchestratorMcp.ts`), and `docs/user/`. `main` is 315 commits later; in those files it changed the scheduler only by refactors and webhook logging, and no tool name or description (source: diff). The run flow below is **not run end to end**: live run pending.

T3 Code starts other agents (Codex, Claude Code, Cursor, Grok, OpenCode, Antigravity, Pi) and has no loop of its own. It gives the agent three things to build one: a scheduler, a native `/goal`, and tools that start more threads. Pick the mode, then read the sections you need.

| Mode | Use it when | Wake |
|---|---|---|
| **Clock** | The stop line is a time, or work waits on CI or a deploy | Scheduled task, then delete it at the stop line |
| **Run to done** | One printed command proves the end state (like Claude Code `/goal`) | Scheduled task re-wakes the thread until the command prints the done text, then disables itself |
| **Native `/goal`** | The thread runs Claude or Codex | The provider keeps going turn after turn |

## What T3 gives the agent

**Scheduler.** `schedule_task` makes work that runs when no turn is active (source). The schedule is an object, not text: `{type:'interval', everyMs}` (minimum 60000), `{type:'fixed_time', timeOfDay:'09:00', weekdays:[0-6]}` or `{type:'webhook'}`. `bindToCurrentThread` defaults to true inside a thread: each run posts the prompt into that thread. False starts a new thread per run, in a fresh worktree of `main` (source). Prompt limit 120,000 characters (source). There is **no** `update_scheduled_task` tool. To change or pause a task, call `schedule_task` again with `scheduledTaskId` (only the given fields change; `enabled=false` pauses). `delete_scheduled_task` stops it at once. `list_scheduled_tasks` lists. `run_scheduled_task_now` fires one run (source). The tool list of a live T3 server shows exactly these, and no update tool (ran: devbox `0.1.6-nightly.20261031.9003956`, 2026-10-31). The owner can also manage tasks in Settings, Scheduled tasks (doc).

**Orchestrator tools** (source, `mcp/toolkits/`; names as the server lists them):

| Job | Tool |
|---|---|
| Which providers, models and options exist | `orchestrator_capabilities` |
| One worker as a child; completion wakes the parent | `delegate_task` (`task`, `target:{providerInstanceId, model, options}`, `role`, `isolation:'worktree'`, `mode:'async'`) then `task_status`, `task_cancel` |
| One worker as a separate top-level thread | `t3_thread_launch` (`title`, `message`, `modelSelection`, `workspaceStrategy:{type:'worktree', baseRef, branch?, startFromOrigin?}`) |
| Up to 20 threads at once, same checkout | `create_threads` |
| Talk to a thread | `t3_thread_send` (`mode`: `auto`, `queue`, `steer`, `restart`), `t3_thread_wait`, `t3_thread_read`, `t3_thread_interrupt` (`stop:true` also holds its queue and stops its delegates) |
| Change a thread's model | `t3_thread_configure` |
| Move this thread into its own worktree | `t3_worktree_handoff` (call last in the turn), `t3_worktree_status`, `t3_worktree_list` |
| Fork or merge context between threads | `t3_thread_transfer` |
| Queue and questions | `t3_queue` (`list`, `cancel`, `reorder`, `edit`, `promote_to_steer`), `t3_pending_request` |
| Thread housekeeping | `t3_thread_list`, `t3_thread_search`, `t3_thread_update`, `t3_thread_organize` (settle, archive, pin, snooze) |
| Pull requests | `link_pull_request`, `watch_pull_request`, `unwatch_pull_request`, `list_thread_pull_requests` |
| Other machines | `t3_environment_links`, `t3_environment_link`; `delegate_task` takes `target.environmentId` |
| Projects | `t3_project_list`, `t3_project_create`, `t3_project_clone` |

A child may not run at wider permission modes than its parent (source). Start the orchestrator thread at Full access and the crew inherits it.

**Native `/goal`.** With Codex and Claude, a message that starts with `/goal <condition>` sets a goal, and the agent keeps working across turns until it judges it met (doc: `composer.md`, Goals). T3 reads the command in the message path, so the first message, a queued message and a `t3_thread_send` all work (source: `parseGoalCommand`, `Orchestrator.ts`). `/goal` alone shows it, `/goal clear` removes it. Codex also takes `/goal pause` and `/goal resume`; Claude does not (T3 rejects them for Claude). Stop on a Claude thread ends the turn and keeps the goal; Claude checks it again at the end of the next message. Stop on a Codex thread pauses it (doc). A goal command never joins a running turn: it stops the run or waits in the queue (source). Whether the provider's own `/loop` works in a T3 thread is **not documented**, and T3's Claude adapter has no handling for `ScheduleWakeup` or `CronCreate` (source: no match). Do not assume it. The schedule is the wake.

## Overlap: a run that fires while a turn is active

- Each scheduled run sends its prompt with mode `queue` (source). Thread idle: a turn starts. Turn active: the prompt waits behind it. One thread runs one turn at a time.
- The task counts a run as done when the prompt is sent, not when the turn ends. The next run is due `everyMs` after that send (source). A turn longer than `everyMs` leaves wake prompts piling up in the queue, and each one repeats the same work.
- A task that is still being sent is not started again (source: "Schedule task is already running" for manual runs; a scheduled run is skipped).
- After a missed interval (server down) the task fires once when the server is back. A missed `fixed_time` run is skipped if it is over 10 minutes late (source).
- A queue that Stop or a restart held does **not** restart on a scheduled message. A message the owner sends from the app resumes it, or **Resume** in the composer (source; doc). Queued scheduled runs wait until then. A later fix (t3code #27221) releases held agent and scheduled messages once the thread completes a run, so expect a stall, not a loss.
- Rule for the prompt: set `everyMs` at or above the longest normal turn, claim an item in the handoff file before starting it, and at the start of every wake run `t3_queue` `list` for this thread and `cancel` extra wake messages. Check a started worker with `task_status` or `t3_thread_read`, never start the same item again.

## Permissions, server, restart, stop

- **Full access.** Only Full access runs without prompts. Any other mode waits for the owner, and a question to the owner pauses the run (doc: `permission-modes.md`). New threads default to Full access (doc). The task keeps the creator's modes, and the bound thread's current modes apply too (source).
- **Server up.** The scheduler lives in the T3 server. On Linux and macOS `t3 service install` keeps it running after logout and at boot; on Linux lingering must be on (`t3 service status` shows it). Windows has no background service: keep the desktop app open (doc: `background-service.md`). A phone or browser only shows the thread; the host machine runs it (doc).
- **Restart.** A run caught by a restart is marked failed ("interrupted by a server restart") and the next run is set from the restart time (source). Settings, Maintenance, **Continue threads after restarts** (on by default) resumes supported active threads after an update, crash or reboot, but not one waiting for approval, an answer, archived, snoozed or settled, and after three automatic resumes in a row it waits for your next message (doc). T3 must start again by itself; this setting does not do that. Queued messages are held after a restart (doc). A usage limit holds the thread: use **Resume at reset** (doc).
- **Stop.** Pause: `schedule_task` with `scheduledTaskId` and `enabled=false`. End: `delete_scheduled_task`. Deleting the bound thread deletes its tasks too (doc). Stop the work: `t3_thread_interrupt` with `stop:true`, or the thread's Stop button; this does not delete the schedule (no code path ends the task on Stop), so a later run still queues. Clean up: delete the task, settle or archive the worker threads (`t3_thread_organize`), remove their worktrees, unwatch pull requests (`unwatch_pull_request`).
- **Outside agents.** An agent in a terminal can drive T3 through its MCP URL (doc: `outside-agents.md`), but outside a thread `schedule_task` cannot bind: it needs a `projectId`, and a project with no default model fails with `invalid_request` ("has no default model") (ran, 2026-10-31). Run the loop from an agent inside a T3 thread.

## The crew

The orchestrator thread runs the loop. Workers do the items.

1. First turn: `orchestrator_capabilities` once. Write the provider, model and options you will use per role into the loop file's Crew section.
2. Small, checkable item, parent only needs the result: `delegate_task` with `isolation:'worktree'`, `mode:'async'`, a `target` model for the role, and a task that carries the full brief (the child sees no parent history). End the turn; completion wakes the orchestrator (source). A fix round goes by `t3_thread_send` to the child thread; a send to a finished child starts a fresh task (source).
3. Item the owner may want to watch, steer or keep: `t3_thread_launch` with its own worktree and `modelSelection`, then `t3_thread_wait` or the next wake. Mention it by its `link`.
4. Several models on one question: one `delegate_task` per model, compare, refine (the way Theo reviews; timestamps here are from the auto-captioned transcript of his video "These 3 skills changed my life", https://www.youtube.com/watch?v=5Bmp9cz1JN8, 2026-10-26: 09:36 to 11:27).
5. At most as many live workers as the Crew section allows. Write each worker's id and item into the handoff file before the turn ends.
6. Landing: the worker opens the pull request; `watch_pull_request` follows checks and reviews; call `unwatch_pull_request` before stopping (transcript 16:54 to 17:15). Write the merge permission in the loop file, since some models will not merge without it (transcript 16:01 to 16:17). A question to the owner goes through the harness's question tool, or the thread looks finished (transcript 18:12 to 18:41). The sidebar is the inbox: settle a thread when its item is done (transcript 12:37 to 13:17).

## Prompt skeleton: clock

```text
Work unattended until <time, zone>. You are the orchestrator in this thread. Rules and order live in <loop file path>: re-read it at every wake.
FIRST TURN: call schedule_task {schedule:{type:'interval', everyMs:<900000>}, bindToCurrentThread:true, title:"<slug> wake", prompt:"WAKE. Read <loop file path> and <handoff path>. t3_queue list this thread and cancel any extra WAKE message. Read the clock (<zone>). Before <time, zone>: do 'Each wake'. At or after it: do 'Finish', then delete_scheduled_task with the id on the 'Wake task' line of the handoff."} Write the returned scheduledTaskId on a 'Wake task:' line in <handoff path>. Then start item 1.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: max <N> workers: <mix by role, model>. delegate_task with isolation 'worktree'; completion wakes you. Never start an item the handoff marks running.
LANDING: <one line>.
AUTHORISED: <list>. Do not stop to ask; take the safer option and log it.
```

## Prompt skeleton: run to done

The check command is the stop line. The wake task re-wakes the thread until it prints the done text.

```text
Run until `<one command>` prints <exact text>, or <N> wakes pass. You are the orchestrator in this thread. Rules and order live in <loop file path>: re-read it at every wake.
FIRST TURN: call schedule_task {schedule:{type:'interval', everyMs:<900000>}, bindToCurrentThread:true, title:"<slug> wake", prompt:"WAKE. Read <loop file path> and <handoff path>. t3_queue list this thread and cancel any extra WAKE message. Run `<one command>` and print its output. If it printed <exact text>, or the wake count in the handoff reached <N>: write 'State: DONE' in the handoff, call schedule_task with the id on the 'Wake task' line and enabled=false, then send the final report. Otherwise add 1 to the wake count and do the next item in Priority."} Write the returned scheduledTaskId on a 'Wake task:' line in <handoff path>, with 'Wakes: 0'. Then start item 1.
ORDER, CREW, LANDING, AUTHORISED: as in the clock skeleton.
```

Put the scheduled prompt under 120,000 characters (it is far shorter). The id sits in the handoff file because the prompt cannot name a task that does not exist yet (and `list_scheduled_tasks` is not for finding your own task in a scheduled run, source).

## Prompt skeleton: native `/goal` (Claude or Codex thread)

Send it as the first message of the thread. The thread must run Claude or Codex.

```text
/goal <Title> is done: `<one command>` prints <exact text>. Every turn: read <loop file path> first and follow it exactly; print the command's output at the end of each turn. Limits: <the 2-3 rules that must hold>.
```

Keep it under 4,000 characters (the Claude Code limit; T3 sets none). Put the crew and landing rules in the loop file. If the owner presses Stop, a Claude goal is checked again at the next message; a Codex goal needs `/goal resume`. No schedule runs under this mode, so a closed server ends it: add a clock wake from the first skeleton if the run must survive a restart.

## Tell the user

- Start a new thread in the project. Pick the orchestrator's provider and model, **Full access**, and **New worktree** if the loop writes files. Paste the prompt. Do not start it from a terminal agent outside T3.
- Keep the machine on and the T3 server running (`t3 service install` on Linux or macOS; the app open on Windows).
- A restart or Stop holds queued wakes. Press **Resume** in the composer to continue.
- Stop: delete the task in Settings, Scheduled tasks, or ask the thread to. A finished run-to-done loop leaves a disabled task behind; delete it. Also stop or settle the worker threads.
- Not run: the full loop. The tools and fields come from source, the tool list and one failed call came from a live server; the first real run will show if the claims under Overlap and Restart hold.
