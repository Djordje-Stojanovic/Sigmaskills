# Antigravity (`agy`): `/goal` (default), `/schedule` (watchdog/clock)

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See `hosts.md` for the table and plain instruction.

Checked 2026-11-25 against Antigravity CLI 1.5.14–1.5.16 and App 2.35.1 docs ([`/goal`](https://antigravity.google/docs/commands/goal), [`/schedule`](https://antigravity.google/docs/commands/schedule), [subagents](https://antigravity.google/docs/subagents), [`/swarm`](https://antigravity.google/docs/swarm), [headless](https://antigravity.google/docs/cli/headless), [hooks](https://antigravity.google/docs/hooks)):

- **`/goal <objective>`**: autonomous run-to-done with no turn cap across App, CLI, IDE, and T3 Code threads (doc). A goal stop hook blocks premature stops and prompts an evidence audit against real output; it waits for subagents and background tasks (`fullyIdle`) before checking; cancel by telling it to stop or starting a new `/goal` (doc). Headless: `agy -p "/goal …"` loops to completion (ran); `--input-format stream-json --output-format stream-json` runs multi-turn in one warm process (doc).
- **`/schedule` & `schedule` tool**: non-blocking timers (`DurationSeconds`, `Prompt`, `TimerCondition`: `never` | `any` | subagent/task ID for early-cancel watchdogs without polling) or 5-field `CronExpression` (`MaxIterations`, `IsDaemon`, `ExactTiming`); manage via `manage_task` or `/tasks` (doc). `-p` waits for timers up to `--print-timeout` (ran: 20 s timer, `MaxIterations` 2, exit 0). Persistent App crons: `/automation` (`~/.gemini/config/sidecars/<id>/sidecar.json`, `CRON_TZ=<IANA>`). `Stop` hook in `.agents/hooks.json` or `~/.gemini/config/hooks.json` prints `{"decision":"continue","reason":"…"}` (`fullyIdle` reports background work) (doc).
- **Crew**: native `invoke_subagent` (`TypeName`: `self`, `research`, `browser`, or `.agents/agents/<name>.md` / `~/.gemini/config/agents/<name>.md`; `Workspace`: `inherit`, `branch` isolated Git worktree, or `share`; `Model`: `inherit`/`flash_lite`/`flash`/`pro`; `send_message` wakes idle subagents with context; `manage_subagents` `kill` cleans worktrees; depth 10) (doc). Multi-agent modes: `/swarm` (named workers + `@verifier` + `@monitor` on shared board, all plans, explicit `/swarm` only), `/run-workflow` (bundled Python `parallel()`/`pipeline()`, JSON Schema outputs, all plans), `/teamwork` and `/boost` (paid). In T3 Code: `invoke_subagent` for same-provider workers; `delegate_task` for cross-provider models, custom options, or other machines (`host-t3-code.md`).
- **Permissions & resume**: `--mode auto` is default since 1.5.7 where OS sandbox exists (macOS/Linux 1.3.5+, Windows 11 24H2+ 1.4.4+, personal accounts; 1.5.14+ auto-reads outside workspace; 1.5.16+ auto-edits inside VCS repos); headless `-p` soft-denies unapproved calls unless `--dangerously-skip-permissions` (`always-proceed`) or `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` covers them (doc). Resume: `agy -c` / `--continue`, `agy -r <id>` / `--resume <id>` (`--conversation`, 1.5.16+), `/resume`; unlimited local history (1.5.15+); App 2.35.1 auto-resumes interrupted conversations after restart (doc).
- **Skills**: `.agents/skills` (`.gemini/skills`, `.agent/skills`); global `~/.gemini/config/skills` and `~/.agents/skills` (1.5.16+; `~/.gemini` wins on collision). Windows: global folder must be a real copy, not a junction (ran); `sigmaskills install sigmaloop --global --agent agy --yes` writes the copy.

## Default: one `/goal` run, no cron

```text
/goal <Title> is done: `<one command>` prints <exact text>. Every turn: read <loop file path> first and follow it exactly; refill a slot in the same turn a subagent ends; never sleep or poll; print the command's output before concluding. Limits: <the 2-3 rules that must hold>.
```

Crew: `invoke_subagent` (`TypeName: "self"`, `Workspace: "branch"` for parallel writers); completion wakes the parent. Watchdog or clock option: `If work must wait on a timer or watchdog, call schedule (DurationSeconds + TimerCondition: "any" or "<task-id>", or CronExpression + MaxIterations) and re-read <loop file path> when it fires.`

Tell the user: run in `--mode auto` or `--dangerously-skip-permissions` (or `permissions.allow`); stop `/goal` by telling it to cancel; `agy -c` or `agy -r <id>` resumes.

Gemini CLI (legacy, replaced 2026-06-18 for personal/Google One users; not run): plain instruction, or `AfterAgent` hook returning `decision: "deny"`.
