# Host facts and prompt skeletons

Checked 2026-10-20. Hosts change fast: when a fact matters, check the linked source. Each host file marks every fact **ran** (run by the author on Windows 11), **doc** (host documentation or its own bundled guide), or **source** (host source code); a step not run says "live run pending". A host not listed gets the plain instruction (last section).

Every prompt carries the same five things: ranked order, crew and model mix, wake rules, landing rules, stop line. The loop file holds the long form; the prompt points to it and repeats only what the host needs to hold the loop.

## Pick the mechanism

A prompt that needs a tool the host lacks stalls the run. Pick the row for the host and for how the run starts (a live session, or headless).

| Host | Loop that fits | Clock wake | Headless run | Skill folder |
|---|---|---|---|---|
| Claude Code | `/goal` (run to done, one printed command), `/loop` (clock) | `CronCreate`, `ScheduleWakeup` | `claude -p "/goal …"` loops to the end (ran). `/loop` needs a live session | `~/.claude/skills` or `.claude/skills` |
| Codex CLI and app | `/goal` | Scheduled tasks: desktop app and web only | `codex exec` does not expand `/goal` (ran). A `Stop` hook loops (ran) | `.agents/skills`, `~/.agents/skills` |
| Antigravity `agy` | `/goal`, `/schedule` | `schedule` tool: timers, max iterations | `agy -p "/goal …"` loops (ran) | `.agents/skills`, `~/.gemini/config/skills` |
| pi with lapi | Plan file with a `lapi-workflow` box fence, then `/code` | None | Not run | `~/.agents/skills` (invoke `/skill:sigmaloop`) |
| Stock pi | None: plain instruction | None | `pi -p`, RPC for a driver | same |
| T3 Code | `schedule_task` tool, or Settings, Scheduled tasks | Interval, fixed time, webhook | The thread runs on the host provider | the provider's own folder |
| Gemini CLI | None: plain instruction, `AfterAgent` hook | None | `gemini -p` | `.agents/skills`, `~/.gemini/skills` |

Invoke SigmaLoop the host's way (`/sigmaloop` in Claude Code, `$sigmaloop` in Codex, `/skill:sigmaloop` in pi). Skill folders in the table come from the installer registry, except `agy`, whose global folder is proven by a run (the installer overrides the registry) and must be a real copy, not a junction (ran). Windows: in Git Bash a leading `/word` argument is rewritten to a path (ran, Claude Code and `agy`); use PowerShell or `MSYS_NO_PATHCONV=1` (ran: it fixed `/loop`).


Per-host facts and the prompt skeleton: [Claude Code](host-claude-code.md), [Codex](host-codex.md), [Antigravity and Gemini CLI](host-antigravity.md), [pi and lapi](host-pi.md), [T3 Code](host-t3-code.md). Read only the one file for the host the user named.

## Other hosts: plain instruction

For a host with no loop command, one long instruction. The agent is the loop; "wake" means the start of each item.

```text
Work unattended until <time, zone>. You are the orchestrator. Rules and order live in <loop file path>: read it now and re-read it at the start of every item; edits apply on the next re-read.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: <mix, or solo>.
LANDING: <one line>.
AUTHORISED: <list>. Do not stop to ask; take the safer option when no rule decides, and log it.
Never end your turn while an item is workable and the clock is before the stop line. At <time, zone> do the Finish block in the loop file and send the final report as your last message.
```

Tell the user the limits: nothing restarts the agent if it ends its turn early. If the host has a way to send "continue" on a timer, or a `Stop` hook, use that as the wake.
