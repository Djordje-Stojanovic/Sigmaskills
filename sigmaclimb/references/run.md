# Unattended run

Overnight climbs hang at 4 AM for four reasons: a test runs for hours, the agent forgets the goal, it drifts into side quests, or it ends a turn while a remote job still runs. These seven rules block all four.

## Seven anti-hang rules

1. **No command without a cap.** Every test, scorer, and eval runs through `python climb.py run runs/NNNN <change-file> [--full]`. Each `steps` command runs under `budget.step_seconds` and the pass under `budget.pass_seconds`; `run` refuses to start while either is not a number. Over a cap, `climb.py` kills the process tree and marks `CRASH`: revert, record one `results.tsv` row, take the next idea. An idea killed twice is dead.
2. **One pass is atomic.** Champion plus one change, measured, then `KEEP` (`python climb.py promote`, commit) or revert. Every pass ends with one new `results.tsv` row and the target equal to the champion.
3. **State lives in files, not memory.** Re-read `climb.md` at the start of every turn. Keep state in `results.tsv`, `ideas.tsv`, and `state/`. A fresh session resumes from disk with no chat history.
4. **Scope anchor.** The top lines of `climb.md` fix Target, Score, Guards, and Out of scope. Turn any side quest into one row in `ideas.tsv`, never work in this pass.
5. **Wake on completion, never poll.** End a turn while a command runs only if the harness will wake you: start a harness background job that sends a completion notice, or keep a local waiter with its own timeout on a remote job. No sleep loops, no polling.
6. **Use the harness watchdog.** On every wake, run `python climb.py status`. `LOOP STALLED` (pass exceeded `budget.pass_seconds`) means kill the pass, record `CRASH`, revert, and take the next idea.
7. **End every turn with `python climb.py status`.** Prints `LOOP RUNNING`, `LOOP STALLED`, or `LOOP FINISHED` (`REPORT.md` exists and either `STOP` exists or `budget.run_hours` elapsed).

## Harness loop modes

Full host details live in `sigmaloop/references/hosts.md`. Pick your harness:

| Harness | Loop & stop check | Background & workers | Watchdog |
|---|---|---|---|
| **Claude Code** | `/goal` (small model reads transcript; 4,000-char max; `/goal clear`); `claude -p "/goal …"` headless; `/loop` (`ScheduleWakeup` `stop: true`) | `Bash` (`run_in_background: true`), `Agent` (`isolation: "worktree"`); completion wakes next turn, defers `/goal` check | `/goal` check-in at 30 min (`CLAUDE_CODE_GOAL_CHECKIN_MINUTES=15`; `0` off; backs off to 4x; max 3 idle interactive, turn-end only in `-p`) |
| **Codex** | `/goal` in CLI, app, IDE (4,000-char max; `/goal pause`, `resume`, `clear`); `codex exec` skips `/goal` (headless: `.codex/hooks.json` `Stop` hook returning `{"decision":"block","reason":"…"}` or `codex exec resume --last`) | `spawn_agent`, `send_input` (`/subagents` in CLI) | None in CLI (scheduled tasks in desktop app and web only) |
| **Antigravity** | `/goal` (no turn cap; stop hook checks evidence, waits for helpers; tell it to stop or start a new `/goal`); `agy -p "/goal …"` (`--print-timeout`) | `invoke_subagent` (`TypeName: "self"`, `Workspace: "branch"` or `"share"`, `send_message`, depth 10); `/swarm` (below) | `schedule` (`DurationSeconds` + `TimerCondition: "any"`, or 5-field `CronExpression` + `MaxIterations`; `/tasks`) |
| **T3 Code** | Provider's `/goal` in a thread (Codex, Claude, Antigravity 1.5+, OpenCode 2.2.5+); Full access | `delegate_task` (`isolation:'worktree'`, `mode:'async'`); `t3_thread_send` steers; `task_cancel` stops | Antigravity thread: `schedule`; else `schedule_task` + `t3_queue` + `delete_scheduled_task` |
| **pi** | Stock `pi` has no loop or scheduler (`pi -p` runs once); drive via `--mode rpc` (`prompt`/`follow_up`) or extension `agent_before_settle` (`continue: true`) | None built in | None built in |
| **No loop mode** | Owner sends "continue" | Shell waiter with timeout | Owner runs `python climb.py status` |

Host notes:

- **Claude Code:** Set permission mode (e.g. auto mode) before `/goal`. In `-p`, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` caps idle waits at 10 min (`0` removes it). Background shells vanish on `--resume`; restart from the last commit.
- **Codex:** CLI lacks timers and scheduled tasks; `/goal` stops on a plan limit. Set `--sandbox workspace-write` or `/permissions` first.
- **Antigravity `/swarm`:** Preview on all plans. Turns the session into a coordinator with named workers, `@verifier`, and `@monitor` watchdog on one `@mention` board; idle members sleep with zero token spend, and workers can get separate working copies. Fits a climb crew when parallel tracks benefit from sharing dead ends on one board: keep the orchestrator as sole writer of `climb.md`/champion, restrict `@verifier` to mechanical script checks (never content scoring), and note Swarm burns quota faster and pauses on quota without auto-retrying.
- **T3 Code:** Start at Full access (children inherit at most parent permissions). Keep the server up with `t3 service install` (Linux, macOS, Windows; on Windows it runs only while the user is signed in). With `schedule_task` (`{schedule:{type:'interval', everyMs}, bindToCurrentThread:true}`), set `everyMs` >= a normal turn and clear stacked wakes via `t3_queue`.
- **pi / no loop mode:** Every turn starts by reading `climb.md` and ends with `python climb.py status`.

## Long-run prompt skeleton

Paste after setup and locking; replace `<host loop command>` (e.g. `/goal`):

```text
<host loop command> <Project> climb is done when `python climb.py status` prints "LOOP FINISHED".
Every turn: read <project>/climb.md first and follow it; run passes only via `python climb.py run`; update `results.tsv` and `ideas.tsv`; print `python climb.py status` last.
End a turn while a command runs only when a harness completion notice wakes you. No sleep loops, no polling.
Limits: protect Target invariants and Guards; one change per pass; only `python climb.py verdict` decides and `python climb.py promote` updates the champion; no model scores content; print no secret.
```

## Multi-agent crew

- **One orchestrator owns state.** Only the orchestrator writes `climb.md`, `results.tsv`, `ideas.tsv`, and the champion. Workers never edit them.
- **One candidate per worker.** Each worker returns one change file and its `runs/NNNN` folder.
- **No overlapping measurements.** Two measurements never overlap on one machine. A shared machine parallelises research and building while measurements queue one at a time.
- **Remote compute per worker.** Separate remote machines let measurements run in parallel. Compare a worker's score only with a champion run on that same machine.
- **Orchestrator promotes.** Only the orchestrator calls `python climb.py promote`, after a confirming run on the reference machine.

## Compute

Run **locally first** when the machine holds the target and quality check cleanly. Otherwise rent via `sigmacollab` in order:

1. **Google Colab**: CPU, High-RAM, GPU, or TPU in plan units (`colab`; 12 h cap, 24 h with background execution; stop by name).
2. **boat.dev**: CPU Linux sandboxes (`boat`) for runs outliving Colab or one box per worker (`--ttl` deadline; `boat delete ID --yes`).
3. **vast.ai**: a GPU (`vastai`) when Colab refuses or excludes the job (`--onstart-cmd` deadline running `vastai destroy instance $CONTAINER_ID --api-key $CONTAINER_API_KEY`).

Show estimated price before starting and prove teardown at the end: your names absent from `colab --auth adc sessions`, `boat list --all`, or `vastai show instances --raw` (filtered to id and label).
