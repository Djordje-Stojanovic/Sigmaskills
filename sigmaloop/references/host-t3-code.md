# T3 Code: `schedule_task`, `/goal`, and a crew of threads

Marks: **ran** (run by the author), **doc** (T3 user docs), **source** (T3 source). See `hosts.md` for the table and the plain instruction. A step not run says "live run pending".

Checked 2026-11-25 against T3 Code 0.1.12 (`docs/user/` + live runs). Verified live (ran): native `/goal` on Claude and Antigravity threads, async `delegate_task` for lane managers and workers (a finished child wakes its parent), `t3_thread_send` with `mode:'steer'`, one status file per lane. The clock and run-to-done scheduler skeletons: live run pending.

T3 Code starts other agents (Codex, Claude Code, Antigravity, OpenCode, Cursor, Pi, Muse) and has no loop of its own. It gives the agent three things to build one: native `/goal`, a scheduler, and tools that start more threads. **Default: native `/goal` with one printed done command, and no repeat timer.** A completion notice wakes the orchestrator, so a timer only piles up wake messages. Use the scheduler only when the stop line is a clock time or the provider has no native `/goal`.

| Mode | Use it when | Wake |
|---|---|---|
| **Native `/goal`** (default) | The thread runs Claude, Codex, Antigravity (CLI 1.5+), or OpenCode (2.2.5+) and one printed command proves the end | The provider keeps going turn after turn; no timer |
| **Run to done** | Same, on a provider without native `/goal` (e.g. Pi, Muse, Cursor, local ACP) | Scheduled task re-wakes the thread until the command prints the done text, then disables itself |
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
| Other machines | `t3_environment_links`, `t3_environment_link`; `delegate_task` takes `target.environmentId`: set it to run a worker on another machine |
| Projects | `t3_project_list`, `t3_project_create`, `t3_project_clone` |

**Antigravity threads** (T3 Code 0.1.12 + managed Antigravity CLI 1.5.14+, doc + ran):
- Native `/goal`, `invoke_subagent`, `schedule` (including `TimerCondition` watchdogs), and T3 MCP tools (`mcp_t3-code_*`) work directly in Antigravity threads; T3 tools can load lazily, so try the tool name once before treating it as absent.
- **ACP fallback** (only if a T3 tool is absent from the tool list): on Windows PowerShell pipe JSON to stdin via `$env:T3_ACP_MCP_CALL` (`'{}' | & $env:T3_ACP_MCP_CALL orchestrator_capabilities -`, non-ASCII as `\uXXXX`); on POSIX follow the `acp-mcp-call` line injected in the thread's T3 instructions.
- Async `delegate_task` completion wakes the Antigravity parent, and `t3_thread_send` (`mode:'steer'`) reaches a running turn (ran). In `agy acp` 1.5.15+, `session/prompt` stays open across non-daemon background subagents/tasks (doc). In **Full access**, Antigravity can still send fixed-choice questions (`ask_question`) or occasional native approval requests (doc).

A child may not run at wider permission modes than its parent (source). Start the orchestrator thread at Full access and the crew inherits it.

**Native `/goal`.** On Claude, Codex, Antigravity (CLI 1.5+), and OpenCode (2.2.5+), a message starting with `/goal <condition>` sets a goal and keeps working across turns until met (doc: `composer.md`, `providers-antigravity.md`). T3 parses the command on the message path, so the first message, a queued message, and `t3_thread_send` all work (source).
- Claude: `/goal` shows it, `/goal clear` removes it; Stop ends the turn and keeps the goal for the next message.
- Codex and OpenCode: `/goal`, `/goal clear`, `/goal pause`, `/goal resume`; Stop pauses the goal.
- Antigravity: Stop interrupts a running goal, then tell Antigravity to stop pursuing it before starting new work; T3 offers no `/goal` status, pause, resume, or clear commands for Antigravity (doc).
- Claude's `/loop` (`ScheduleWakeup`, `CronCreate`) has no T3 adapter handling (source); for clock wakes in T3 use `schedule_task` (or Antigravity's native `schedule` tool for within-session watchdogs).

For clock or scheduled run-to-done mode, read `host-t3-scheduler.md` before filling the scheduler skeleton: it covers schedule fields, overlap, permissions, restart and cleanup.

## The crew

The orchestrator thread runs the loop. Workers do the items.

**Per builder:** build, prove, review, PR, CI, merge. Roles, tiers and failure rules: `loop-file.md`, Crew and Failure rules.

**Model chain by usage.** Write the chain into the loop file's Crew section from `orchestrator_capabilities` (never guess a model id). Apply the provider and tier rules in loop-file.md, Failure rules. A worker takes the first step with usage left; a step is out when a child ends on a usage or rate-limit error. If a step shares a pool with the orchestrator, give it a floor (a percent of weekly and 5-hour limit left). Set the target on `delegate_task` (`target.providerInstanceId`, `target.model`, `target.options`) or `modelSelection` on `t3_thread_launch`; `t3_thread_configure` changes a live thread.

**Wake hygiene** (scheduler modes only). `t3_queue` `list` this thread at the start of each wake and `cancel` piled-up wake messages. A closed queue (after Stop or a restart) waits for **Resume**.

**Failure and speed rules**: `loop-file.md`. More than one lane: `lanes.md`.

**Waiting.** Read a child's status file or result, not its thread: `t3_thread_read` starts at the first message and costs a lot (ran).

1. First turn: `orchestrator_capabilities` once. Write the provider, model and options you will use per role into the loop file's Crew section.
2. Ticket the worker builds, parent only needs the result: `delegate_task` with `isolation:'worktree'`, `mode:'async'`, a `target` model for the role, and a task that is the path of its full spec plus the done line (the child sees no parent history). End the turn; completion wakes the orchestrator (source). A delegate review or re-check is a fresh `delegate_task` carrying the findings and objections; apply small fixes on the PR branch.
3. Only when the owner asks for a new top-level thread: `t3_thread_launch` with its own worktree and `modelSelection`, then `t3_thread_wait` or the next wake. Mention it by its `link`.
4. At most as many live workers as the Crew section allows. Write each worker's id and item into the handoff file before the turn ends.
5. Landing: the worker opens the pull request; only the thread that owns a PR watches it (`watch_pull_request`), children never; call `unwatch_pull_request` before stopping. Write the merge permission in the loop file, since some models will not merge without it. A question to the owner goes through the harness's question tool, or the thread looks finished. The sidebar is the inbox: settle a thread when its item is done.

## Prompt skeleton: native `/goal` (default)

Send it as the first message of the thread (Claude, Codex, Antigravity, or OpenCode 2.2.5+). No `schedule_task`.

```text
/goal <Title> is done: `<one command>` prints <exact text>. Follow the selected solo or crew roles in the loop file. Every turn: read <loop file path> first and follow it exactly; print the command's output at the end of each turn. Limits: <the 2-3 rules that must hold>.
```

Put the selected roles, tstack flow and landing in the loop file. In crew mode, each worker is `delegate_task` (`isolation:'worktree'`, `mode:'async'`) on one whole ticket, and its completion wakes the orchestrator (same-provider Antigravity workers can also use native `invoke_subagent`). Keep the goal under 4,000 characters (the Claude/Codex limit; T3 sets none). Stop behavior: Claude re-checks at the next message; Codex/OpenCode need `/goal resume`; Antigravity stops the turn and needs a follow-up asking it to cancel the goal. No schedule runs, so a closed server ends the run: add the clock skeleton only if the run must survive a restart.

## Prompt skeleton: clock (stop line is a time)

```text
Work unattended until <time, zone>. You are the orchestrator in this thread. Rules and order live in <loop file path>: re-read it at every wake.
FIRST TURN: call schedule_task {schedule:{type:'interval', everyMs:<900000>}, bindToCurrentThread:true, title:"<slug> wake", prompt:"WAKE. Read <loop file path> and <handoff path>. t3_queue list this thread and cancel any extra WAKE message. Read the clock (<zone>). Before <time, zone>: do 'Each turn'. At or after it: do 'Finish', then delete_scheduled_task with the id on the 'Wake task' line of the handoff."} Write the returned scheduledTaskId on a 'Wake task:' line in <handoff path>. Then start item 1.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: <shape from the loop file>. One whole unit per builder (build, prove, review, PR, CI, merge); delegate_task with isolation 'worktree' and the spec path; completion wakes you. Re-read the loop file at every wake. Never start an item the handoff marks running.
LANDING: <one line>.
AUTHORISED: <list>. Do not stop to ask; when no rule decides, take the option that keeps work moving and can be undone; log it.
```

## Prompt skeleton: run to done (providers without `/goal`)

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
- Not run: the scheduler skeletons. The claims under Overlap and Restart hold only after a live run.
