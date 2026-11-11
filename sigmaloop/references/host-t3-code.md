# T3 Code: `schedule_task`, `/goal`, and a crew of threads

Marks: **ran** (run by the author), **doc** (T3 user docs), **source** (T3 source). See [hosts.md](hosts.md) for the table and the plain instruction. A step not run says "live run pending".

Checked 2026-10-31 against T3 `0.1.6-nightly.20261030.3904`, source commit `36dac688a1` of [pingdotgg/t3code](https://github.com/pingdotgg/t3code) (`apps/server/src/mcp/toolkits/`, `apps/server/src/scheduledTasks/`, `packages/contracts/src/scheduledTask.ts`, `orchestratorMcp.ts`), and `docs/user/`. `main` is 315 commits later; in those files it changed the scheduler only by refactors and webhook logging, and no tool name or description (source: diff). The run flow below is **not run end to end**: live run pending.

T3 Code starts other agents (Codex, Claude Code, Cursor, Grok, OpenCode, Antigravity, Pi) and has no loop of its own. It gives the agent three things to build one: a native `/goal`, a scheduler, and tools that start more threads. **Default: native `/goal` with one printed done command, and no repeat timer.** A completion notice wakes the orchestrator, so a timer only piles up wake messages. Use the scheduler only when the stop line is a clock time or the orchestrator is not Claude or Codex.

| Mode | Use it when | Wake |
|---|---|---|
| **Native `/goal`** (default) | The thread runs Claude or Codex and one printed command proves the end | The provider keeps going turn after turn; no timer |
| **Run to done** | Same, but the thread is neither Claude nor Codex | Scheduled task re-wakes the thread until the command prints the done text, then disables itself |
| **Clock** | The stop line is a time | Scheduled task, then delete it at the stop line |

## What T3 gives the agent

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

For clock or scheduled run-to-done mode, read [host-t3-scheduler.md](host-t3-scheduler.md) before filling the scheduler skeleton: it covers schedule fields, overlap, permissions, restart and cleanup.

## The crew

The orchestrator thread runs the loop. Workers do the items.

**Per builder:** build, prove, one closing review, PR, CI, merge. Roles, tiers and failure rules: [loop-file.md](loop-file.md), Crew and Failure rules.

**Model chain by usage.** Write the chain into the loop file's Crew section from `orchestrator_capabilities` (never guess a model id). Apply the provider and tier rules in loop-file.md, Failure rules. A worker takes the first step with usage left; a step is out when a child ends on a usage or rate-limit error. If a step shares a pool with the orchestrator, give it a floor (a percent of weekly and 5-hour limit left). Set the target on `delegate_task` (`target.providerInstanceId`, `target.model`, `target.options`) or `modelSelection` on `t3_thread_launch`; `t3_thread_configure` changes a live thread.

**Wake hygiene** (scheduler modes only). `t3_queue` `list` this thread at the start of each wake and `cancel` piled-up wake messages. A closed queue (after Stop or a restart) waits for **Resume**.

**Failure and speed rules**: [loop-file.md](loop-file.md).

1. First turn: `orchestrator_capabilities` once. Write the provider, model and options you will use per role into the loop file's Crew section.
2. Ticket the worker builds, parent only needs the result: `delegate_task` with `isolation:'worktree'`, `mode:'async'`, a `target` model for the role, and a task that is the path of its full spec plus the done line (the child sees no parent history). End the turn; completion wakes the orchestrator (source). A delegate review or re-check is a fresh `delegate_task` carrying the findings and objections; apply small fixes on the PR branch.
3. Only when the owner asks for a new top-level thread: `t3_thread_launch` with its own worktree and `modelSelection`, then `t3_thread_wait` or the next wake. Mention it by its `link`.
5. At most as many live workers as the Crew section allows. Write each worker's id and item into the handoff file before the turn ends.
6. Landing: the worker opens the pull request; only the thread that owns a PR watches it (`watch_pull_request`), children never; call `unwatch_pull_request` before stopping. Write the merge permission in the loop file, since some models will not merge without it. A question to the owner goes through the harness's question tool, or the thread looks finished. The sidebar is the inbox: settle a thread when its item is done.

## Prompt skeleton: native `/goal` (default; Claude or Codex thread)

Send it as the first message of the thread. No `schedule_task`.

```text
/goal <Title> is done: `<one command>` prints <exact text>. Follow the selected solo or crew roles in the loop file. Every turn: read <loop file path> first and follow it exactly; print the command's output at the end of each turn. Limits: <the 2-3 rules that must hold>.
```

Put the selected roles, tstack flow and landing in the loop file. In crew mode, each worker is `delegate_task` (`isolation:'worktree'`, `mode:'async'`) on one whole ticket, and its completion wakes the orchestrator. Keep the goal under 4,000 characters (the Claude Code limit; T3 sets none). Stop on a Claude goal is checked again at the next message; a Codex goal needs `/goal resume`. No schedule runs, so a closed server ends the run: add the clock skeleton only if the run must survive a restart.

## Prompt skeleton: clock (stop line is a time)

```text
Work unattended until <time, zone>. You are the orchestrator in this thread. Rules and order live in <loop file path>: re-read it at every wake.
FIRST TURN: call schedule_task {schedule:{type:'interval', everyMs:<900000>}, bindToCurrentThread:true, title:"<slug> wake", prompt:"WAKE. Read <loop file path> and <handoff path>. t3_queue list this thread and cancel any extra WAKE message. Read the clock (<zone>). Before <time, zone>: do 'Each turn'. At or after it: do 'Finish', then delete_scheduled_task with the id on the 'Wake task' line of the handoff."} Write the returned scheduledTaskId on a 'Wake task:' line in <handoff path>. Then start item 1.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: <shape from the loop file>. One whole unit per builder (build, prove, one closing review, PR, CI, merge); delegate_task with isolation 'worktree' and the spec path; completion wakes you. Re-read the loop file at every wake. Never start an item the handoff marks running.
LANDING: <one line>.
AUTHORISED: <list>. Do not stop to ask; take the safer option and log it.
```

## Prompt skeleton: run to done (thread is not Claude or Codex)

The check command is the stop line. The wake task re-wakes the thread until it prints the done text.

```text
Run until `<one command>` prints <exact text>, or <N> wakes pass. You are the orchestrator in this thread. Rules and order live in <loop file path>: re-read it at every wake.
FIRST TURN: call schedule_task {schedule:{type:'interval', everyMs:<900000>}, bindToCurrentThread:true, title:"<slug> wake", prompt:"WAKE. Read <loop file path> and <handoff path>. t3_queue list this thread and cancel any extra WAKE message. Run `<one command>` and print its output. If it printed <exact text>, or the wake count in the handoff reached <N>: write 'State: DONE' in the handoff, call schedule_task with the id on the 'Wake task' line and enabled=false, then send the final report. Otherwise add 1 to the wake count and do the next item in Priority."} Write the returned scheduledTaskId on a 'Wake task:' line in <handoff path>, with 'Wakes: 0'. Then start item 1.
ORDER, CREW (roles, tiers, clerk), LANDING, AUTHORISED: as in the clock skeleton.
```

Put the scheduled prompt under 120,000 characters (it is far shorter). The id sits in the handoff file because the prompt cannot name a task that does not exist yet (and `list_scheduled_tasks` is not for finding your own task in a scheduled run, source).

## Tell the user

- Start a new thread in the project. Pick the orchestrator's provider and model, **Full access**, and **New worktree** if the loop writes files. Paste the prompt. Do not start it from a terminal agent outside T3.
- Keep the machine on and the T3 server running (`t3 service install` on Linux or macOS; the app open on Windows).
- A restart or Stop holds queued wakes. Press **Resume** in the composer to continue.
- Stop: delete the task in Settings, Scheduled tasks, or ask the thread to. A finished run-to-done loop leaves a disabled task behind; delete it. Also stop or settle the worker threads.
- Not run: the full loop. The tools and fields come from source, the tool list and one failed call came from a live server; the first real run will show if the claims under Overlap and Restart hold.
