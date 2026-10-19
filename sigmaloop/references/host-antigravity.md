# Antigravity (`agy`): `/goal`, `/schedule`

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See [hosts.md](hosts.md) for the table and the plain instruction.

Gemini CLI was replaced by Antigravity CLI on 2026-06-18 for unpaid and Google One users ([README](https://github.com/google-gemini/gemini-cli)). Facts from the CLI's own `agy changelog` and bundled guides (`~/.gemini/antigravity-cli/builtin/skills`), version 1.4.2:

- `/goal` runs a long task until done or cancelled; the turn limit was removed in 1.0.14 (doc). `agy -p "/goal …"` ran two turns, created both files, and exited 0 in 85 s (ran).
- `/schedule` sets a recurring cron-style run or a one-time timer (doc). The agent's `schedule` tool takes `DurationSeconds`, `MaxIterations`, and a wake-up condition (doc, changelog). `-p` waits for scheduled timers up to `--print-timeout`, then exits (doc, changelog). I did not run the timer: live run pending.
- A `Stop` hook in `hooks.json` prints `{"decision":"continue","reason":"…"}` to re-enter the loop; after a set number of consecutive continuations it can no longer block (doc, changelog). Cron automations are `sidecar.json` files the owner enables in the Automations dashboard; each run is a fresh conversation (doc).
- Skills load from `<project>/.agents/skills` and `~/.gemini/config/skills` (doc). The installer registry lists a different global folder, `~/.gemini/antigravity-cli/skills`, which the bundled guides do not name; `agy -p "/skills"` did not list skills from `~/.agents/skills` (ran). Install into one of the two documented folders.
- Unattended: `--dangerously-skip-permissions` (used in the run above), or `--mode auto` where the OS supports it; at 1.3.5 Windows support for auto mode was "coming later" (changelog). In `-p`, subagent questions are skipped (changelog).

Prompt skeleton: the `/goal` skeleton in [host-codex.md](host-codex.md), then one clock line: `If the work must wait on a clock, use your schedule tool (DurationSeconds, MaxIterations) and re-read <loop file path> when it fires.`

Gemini CLI (not installed here, not run): no loop command and no scheduler. Its `AfterAgent` hook with `decision: "deny"` rejects the answer and forces a retry (doc: `docs/hooks/reference.md`). Use the plain instruction, or that hook.
