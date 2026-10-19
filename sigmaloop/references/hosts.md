# Host facts and prompt skeletons

Checked 2026-10-19. Hosts change fast: when a fact here matters to the user's setup, check the linked source before relying on it. A host not listed gets the plain instruction (last section).

Every prompt carries the same five things: ranked order, crew and model mix, wake rules, landing rules, stop line. The loop file holds the long form; the prompt points to it and repeats only what the host needs to hold the loop.

## Claude Code: `/loop`

Facts ([scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks), [/goal](https://code.claude.com/docs/en/goal)):

- `/loop <prompt>` with no interval is self-paced. After each iteration Claude picks a delay between one minute and one hour, and prints the delay and the reason.
- The next wake is the `ScheduleWakeup` tool. Calling it with `stop: true` cancels the pending wake and ends the loop.
- If an iteration ends with neither a reschedule nor a stop, Claude Code schedules one fallback wake about 20 minutes later; if that iteration does not reschedule either, the loop ends. So the prompt must say: always reschedule before a turn ends.
- A scheduled prompt runs between turns, not mid-response. `Esc` clears the pending wake.
- Session-scoped: the session must stay open and the machine on. A self-paced loop is not restored by `--resume` or `--continue`: run `/loop` again. A recurring task expires after 7 days. A session holds up to 50 scheduled tasks.
- Permissions are inherited from the session. For an unattended run the user sets auto mode or an allowlist first, or the loop stalls on a prompt.
- A bare `/loop` reads `.claude/loop.md` (or `~/.claude/loop.md`), but only when no prompt is given. With a prompt, the file is ignored, so the prompt itself must say to re-read the loop file.
- Other option: `/goal <condition>` keeps turns going back-to-back until a model judges the condition met (condition up to 4,000 characters; a turn or time clause bounds it). Pick `/goal` when the work never waits for a clock; pick `/loop` when it waits on CI, renders, deploys, or the stop line is a clock time.

Prompt skeleton:

```text
/loop <Title> until <time, zone>. You are the orchestrator. Re-read <loop file path> at every wake: edits apply on the next wake.
ORDER: <loop file> "Priority", top down. First: <items 1-3>.
CREW: max <N> sub-agents: <mix>.
LANDING: <one line: code + tests, docs, tracker tick with evidence, PR merged, branch + worktree gone, deploy proof>.
AUTHORISED: <list>. Take the safer option when no rule decides; log it.
WAKE: always end every turn with ScheduleWakeup (<60-120> s right after an agent ends or a merge needs a check, else <900-1200> s). A turn without ScheduleWakeup ends the loop.
STOP: at <time, zone> do the Finish block in the loop file, then call ScheduleWakeup with stop: true.
```

Tell the user: leave the session open and the machine on; set the permission mode; `Esc` stops it; a resumed session needs `/loop` again.

## Codex: `/goal`

Facts (source code of [openai/codex](https://github.com/openai/codex): `codex-rs/tui/src/goal_display.rs`, `codex-rs/protocol/src/protocol.rs`, `codex-rs/ext/goal/templates/goals/continuation.md`; [Codex slash commands](https://learn.chatgpt.com/codex/reference/slash-commands.md)):

- Syntax: `/goal [<objective>|clear|edit|pause|resume]`. A goal persists across turns until it is complete, paused, or limited. `/plan` first, then `/goal`, is the documented way to shape an objective.
- The objective is capped at 4,000 characters. A longer one is stored as a file and the model is told to read it. So keep the objective a short end-state statement and put the long rules in the loop file.
- Status values: active, paused, stalled (blocked), usage limited, limited by budget, complete. A token budget is optional. At a budget limit the agent wraps up and reports.
- Each continuation turn tells the model to keep the full objective, to judge progress from the current files and command output rather than the chat, to prove every requirement before it calls the goal complete, and to call `update_goal` only when the goal is complete (or the user asks for a pause). So write the objective as a checkable end state, not a task list.
- There is no timer. "Waking" is the next turn. A clock stop line works only if the objective tells the agent to read the clock each turn.
- If `/goal` is missing in the CLI, a third-party write-up says to enable the goals feature (`[features] goals = true` in `~/.codex/config.toml`, or `codex --enable goals`); check the current Codex docs.
- Sub-agents: use them only if the user's Codex build has them; otherwise the crew is solo.

Prompt skeleton (keep under 4,000 characters):

```text
/goal By <time, zone>, every open item in <tracker or ticket> is ticked with dated evidence, or has a dated log line (done, left, why, next step); <status file> is current. Rules and order live in <loop file path>: read it first and at the start of every turn; edits apply on the next turn.
Order: <loop file> "Priority", top down. First: <items 1-3>.
Crew: <solo, or the sub-agent mix>.
Landing per item: <code + tests, docs, tracker tick with evidence, PR merged, branch + worktree gone, deploy proof>.
Authorised: <list>. Take the safer option when no rule decides; log it.
Each turn: read the clock; do the next item; update the handoff. Never end a turn idle while an item is workable. At <time, zone> do the Finish block in the loop file, then mark the goal complete.
```

Tell the user: start it in a session with the right permission mode (a goal does not change it); `/goal pause` and `/goal clear` stop it; consider a token budget.

## pi: plan mode

Facts ([pi.dev](https://pi.dev), [pi-mono](https://github.com/badlogic/pi-mono), a plan-mode package such as [@narumitw/pi-plan-mode](https://pi.dev/packages/@narumitw/pi-plan-mode)):

- pi has no built-in plan mode and no built-in sub-agents. Plan mode comes from an extension or package the user installed (`pi install npm:<package>`); different packages use different commands (a read-only `/plan`, an approval step such as `/build`, a plan file). Ask which one the user runs, and use its words.
- pi loads context files (such as `AGENTS.md`) at start, supports skills, and has print mode (`pi -p "..."`), JSON mode, and RPC mode for scripts.
- pi has no scheduler. The session is the loop. "Wake" means the start of each item: the prompt tells the agent to re-read the loop file then.
- Plan-mode restrictions are extension-level, not an OS sandbox.

The prompt asks for a plan, then the run. Skeleton:

```text
Plan mode. Write the plan to your plan file, then wait for approval. Do not edit the work items yet.
Plan sections: Mission (why, outcome, stop line <time, zone>); Boundaries (in scope, non-goals, no-touch list); Invariants (rules that never bend); Order (<loop file> "Priority", with who owns what); Landing (per item: <code + tests, docs, tracker tick, PR merged, cleanup, deploy proof>); Authorised actions (<list>).
After approval, run the plan as one long session. Rules and order live in <loop file path>: re-read it at the start of every item; edits apply on the next re-read. Crew: solo, one item at a time<, or the user's extra sessions, each in its own worktree>. Never end a turn idle while an item is workable. At <time, zone> do the Finish block in the loop file and stop.
```

Tell the user: approve with the extension's own command; keep the terminal open or use a multiplexer (tmux, screen) so the session survives.

## T3 Code: plain instruction

Facts ([t3.codes](https://t3.codes), [T3 Code docs: permission modes](https://github.com/pingdotgg/t3code/blob/main/docs/user/permission-modes.md), [Pi provider](https://github.com/pingdotgg/t3code/blob/main/docs/user/providers-pi.md)):

- T3 Code is a control surface over other agent harnesses (Claude Code, Codex CLI, Cursor, Grok, OpenCode, Antigravity, and pi). It does not run its own loop, and its docs show no scheduler or loop feature.
- Each thread writes to its own branch. A thread's permission mode (Supervised, Auto-accept edits, Auto, Full access) is set in the composer and applies to that thread; the default for new threads is Full access.
- Whether a provider's own slash command (`/loop`, `/goal`) works inside the T3 Code composer is not documented. Do not assume it. Write a plain instruction.
- Outside agents can start and message threads through T3 Code's MCP server, if the user enables it. Mention it only if the crew needs several threads.

Prompt skeleton: the plain instruction below, plus one line for the permission mode.

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

Tell the user the limits: nothing restarts the agent if it ends its turn early. If the host has a way to send "continue" on a timer, use that as the wake.
