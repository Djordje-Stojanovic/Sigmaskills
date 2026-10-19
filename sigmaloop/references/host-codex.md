# Codex: `/goal`

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See [hosts.md](hosts.md) for the table and the plain instruction.

Facts ([slash commands](https://learn.chatgpt.com/codex/reference/slash-commands.md), [hooks](https://learn.chatgpt.com/docs/hooks), [scheduled tasks](https://learn.chatgpt.com/docs/automations), source of [openai/codex](https://github.com/openai/codex): `codex-rs/tui/src/goal_display.rs`, `codex-rs/ext/goal/templates/goals/continuation.md`):

- Syntax: `/goal [<objective>|clear|edit|pause|resume]`. The goal persists across turns until complete, paused, or limited (doc). Use `/plan` first to shape it (doc). Codex 0.163.0 lists the `goals` feature as stable and on (ran: `codex features list`), so no flag is needed. The status `usage_limited` means a plan limit stopped the goal (source).
- The objective is capped at 4,000 characters; a longer one is stored as a file (source). Keep it a short checkable end state; put long rules in the loop file.
- Each continuation turn tells the model to judge progress from files and command output, to prove every requirement before it calls the goal complete, and to call `update_goal` only then (source). Status values: active, paused, stalled, usage limited, limited by budget, complete (source). A token budget is optional.
- There is no timer. "Waking" is the next turn, so a clock stop line works only if the objective says to read the clock each turn.
- `codex exec "/goal …"` sent the text to the model as a plain prompt: one turn, exit 0, no continuation (ran). For a headless loop use a `Stop` hook: in `.codex/hooks.json` it prints `{"decision":"block","reason":"…"}` and Codex starts a new turn with the reason as its prompt (doc). A two-iteration hook ran under `codex exec --dangerously-bypass-hook-trust` (ran). Otherwise re-run `codex exec resume --last` from a shell loop.
- Scheduled tasks exist in the desktop app and on the web, not in the CLI (doc). A task scheduled inside a chat returns to that chat (doc).

Prompt skeleton (under 4,000 characters):

```text
/goal By <time, zone>, every open item in <tracker or ticket> is ticked with dated evidence, or has a dated log line (done, left, why, next step); <status file> is current. Rules and order live in <loop file path>: read it first and at the start of every turn; edits apply on the next turn.
Order: <loop file> "Priority", top down. First: <items 1-3>.
Crew: <solo, or the sub-agent mix>.
Landing per item: <code + tests, docs, tracker tick with evidence, PR merged, branch + worktree gone, deploy proof>.
Authorised: <list>. Take the safer option when no rule decides; log it.
Each turn: read the clock; do the next item; update the handoff; print the check that proves it. Never end a turn idle while an item is workable. At <time, zone> do the Finish block in the loop file, then mark the goal complete.
```

Tell the user: start it in a session with the right permission mode (a goal does not change it); `/goal pause` and `/goal clear` stop it; consider a token budget; the goal stops at a plan limit.
