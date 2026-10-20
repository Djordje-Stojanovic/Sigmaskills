# Antigravity (`agy`): `/goal`, `/schedule`

Marks: **ran** (run by the author, Windows 11), **doc**, **source**. See [hosts.md](hosts.md) for the table and the plain instruction.

Gemini CLI was replaced by Antigravity CLI on 2026-06-18 for unpaid and Google One users ([README](https://github.com/google-gemini/gemini-cli)). Facts from the CLI's own `agy changelog` and bundled guides (`~/.gemini/antigravity-cli/builtin/skills`), version 1.4.2:

- `/goal` runs a long task until done or cancelled; the turn limit was removed in 1.0.14 (doc). `agy -p "/goal …"` ran two turns, created both files, and exited 0 in 85 s (ran).
- `/schedule` sets a recurring cron-style run or a one-time timer (doc). The agent's `schedule` tool takes `DurationSeconds`, `MaxIterations`, and a wake-up condition (doc, changelog). `-p` waits for scheduled timers up to `--print-timeout`, then exits (doc, changelog). The timer ran 2026-10-20: `agy -p` with a 20 s `DurationSeconds` and `MaxIterations` 2 got `tick 1`, `tick 2`, `done`, exit 0 in 183 s, without the skip-permissions flag (ran).
- A `Stop` hook in `hooks.json` prints `{"decision":"continue","reason":"…"}` to re-enter the loop; after a set number of consecutive continuations it can no longer block (doc, changelog). Cron automations are `sidecar.json` files the owner enables in the Automations dashboard; each run is a fresh conversation (doc).
- Skills load from `<project>/.agents/skills` and `~/.gemini/config/skills` (doc). Probe skills in `~/.gemini/antigravity-cli/skills` and `~/.gemini/skills` were not listed; one in `~/.gemini/config/skills` was (ran, `agy` 1.4.2). The upstream registry names the first folder, so the installer overrides it. A folder that is a Windows junction shows no skills; the same folder as a real copy does (ran). `sigmaskills install sigmaloop --global --agent agy --yes` writes the copy.
- Unattended: `--dangerously-skip-permissions` (used in the run above), or `--mode auto` where the OS supports it; at 1.3.5 Windows support for auto mode was "coming later" (changelog). In `-p`, subagent questions are skipped (changelog).

Prompt skeleton: the `/goal` skeleton in [host-codex.md](host-codex.md), then one clock line: `If the work must wait on a clock, use your schedule tool (DurationSeconds, MaxIterations) and re-read <loop file path> when it fires.`

Gemini CLI (not installed here, not run): no loop command and no scheduler. Its `AfterAgent` hook with `decision: "deny"` rejects the answer and forces a retry (doc: `docs/hooks/reference.md`). Use the plain instruction, or that hook.
