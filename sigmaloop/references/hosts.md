# Host facts and prompt skeletons

Checked 2026-11-25. Hosts change fast: when a fact matters, check the linked source. Each host file marks every fact **ran** (run by the author on Windows 11), **doc** (host documentation or its own bundled guide), or **source** (host source code); a step not run says "live run pending". These are the harnesses met so far, not the whole world. For any other, read its docs (SKILL.md step 2) and write the prompt from what it can do; a harness with no loop of its own gets the plain instruction (last section).

Every prompt carries the done command or stop line, the loop file path to re-read each turn, and the 2-3 limits that must hold. The loop file holds the rest (order, roles, failure and speed rules, landing). Default on every host that has it: native `/goal`, driven by completion notices, with no wake task and no cron.

## Pick the mechanism

A prompt that needs a tool the host lacks stalls the run. Pick the row for the host and for how the run starts (a live session, or headless).

| Host | Loop that fits | Clock wake | Headless run | Skill folder |
|---|---|---|---|---|
| Claude Code | `/goal` (run to done, one printed command), `/loop` (clock) | `CronCreate`, `ScheduleWakeup` | `claude -p "/goal …"` loops to the end (ran). `/loop` needs a live session | `~/.claude/skills` or `.claude/skills` |
| Codex CLI and app | `/goal` | Scheduled tasks: desktop app and web only | `codex exec` does not expand `/goal` (ran). A `Stop` hook loops (ran) | `.agents/skills`, `~/.agents/skills` |
| Antigravity `agy` | `/goal` (native run to done), `/schedule`, `/swarm` (explicit), `/run-workflow` | `schedule` tool: `DurationSeconds` + `TimerCondition` watchdog, or `CronExpression` + `MaxIterations` | `agy -p "/goal …"` loops (ran); `--input-format stream-json` for warm multi-turn | `.agents/skills`, `~/.gemini/config/skills`, `~/.agents/skills` (1.5.16+) |
| pi with lapi | Plan file with a `lapi-workflow` box fence, then `/code` | None | Not run | `~/.agents/skills` (invoke `/skill:sigmaloop`) |
| Stock pi | None: plain instruction | None | `pi -p`, RPC for a driver | same |
| T3 Code | `/goal` in a Claude, Codex, Antigravity (CLI 1.5+), or OpenCode (2.2.5+) thread (doc + source); `schedule_task` (clock, or run to done on other providers) | `schedule_task`: interval, fixed time, webhook. Crew: `delegate_task`, `t3_thread_launch` | Start in a T3 thread (Full access) or `t3 thread start` on host. Outside agents cannot bind `schedule_task` (ran) | the provider's own folder |
| Gemini CLI | None: plain instruction, `AfterAgent` hook | None | `gemini -p` | `.agents/skills`, `~/.gemini/skills` |

Invoke SigmaLoop the host's way (`/sigmaloop` in Claude Code and Antigravity, `$sigmaloop` in Codex, `/skill:sigmaloop` in pi). On Windows, Antigravity's global skill folder must be a real copy, not a junction (ran), and Git Bash rewrites a leading `/word` argument to a path (ran, Claude Code and `agy`); use PowerShell or `MSYS_NO_PATHCONV=1` (ran).


Per-host facts and the prompt skeleton: [Claude Code](host-claude-code.md), [Codex](host-codex.md), [Antigravity and Gemini CLI](host-antigravity.md), [pi and lapi](host-pi.md), [T3 Code](host-t3-code.md) and its [scheduler](host-t3-scheduler.md). Read only the file for the user's harness.

## Other hosts: plain instruction

For a harness whose docs show no loop command, one long instruction. The agent is the loop; "wake" means the start of each item.

```text
Work unattended until <time, zone>. You are the orchestrator. Rules and order live in <loop file path>: read it now and re-read it at the start of every item; edits apply on the next re-read.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: <mix, or solo>. One whole ticket per worker (an item too big goes through to-spec and to-tickets first), one report, a review by a different model; no helper agents.
LANDING: <one line>.
AUTHORISED: <list>. Do not stop to ask; when no rule decides, take the option that keeps work moving and can be undone; log it.
Never end your turn while an item is workable and the clock is before the stop line. At <time, zone> do the Finish block in the loop file and send the final report as your last message.
```

Tell the user the limits: nothing restarts the agent if it ends its turn early. If the host has a way to send "continue" on a timer, or a `Stop` hook, use that as the wake.
