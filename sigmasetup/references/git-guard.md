# Git guard

A hook for one repo, for Claude Code and Antigravity. It stops the agent from running git commands that destroy work nobody can get back, and it is gone again with one command.

| Blocked | Why |
|---|---|
| `git push --force`, `-f`, `--force-with-lease`, `--mirror`, `+<ref>` | rewrites history on the remote |
| `git reset --hard` | throws away uncommitted work |
| `git clean -f` | deletes untracked files for good |
| `git checkout .`, `git restore .` (not `restore --staged .`), `checkout -f`, `switch --discard-changes` | throws away every uncommitted change |
| `git stash clear`, `git stash drop` | deletes stashed work for good |

Allowed on purpose: a normal push, `git push origin --delete <branch>`, `git branch -D`. After a squash merge, Git sees the branch as not merged, so `-D` is normal cleanup once the PR shows merged. The guard also reads past git's global options, so `git -C <dir> push --force` is blocked too.

## On, off, check

Run from the repo root. `<sigmasetup>` is the folder this skill is installed in.

- On: `node <sigmasetup>/scripts/git-guard.mjs install .` does both agents in one go. Claude Code: it copies the hook to `.claude/hooks/sigma-git-guard.mjs` and adds one `PreToolUse` entry (Bash and PowerShell) to `.claude/settings.json`. Antigravity (app, `agy`, IDE, and T3 Code's Antigravity): it copies the hook to `.agents/hooks/sigma-git-guard.mjs` and adds one `sigma-git-guard` hook on `run_command` to `.agents/hooks.json`. Other settings and hooks stay as they are; running it twice adds nothing.
- Off: `node .claude/hooks/sigma-git-guard.mjs remove .` takes both entries and both files out again. A settings file that held only the guard goes too.
- Check: `node .claude/hooks/sigma-git-guard.mjs status .` says on, off, or which half is missing.

Claude Code treats a hook that crashes (no Node, a moved file) as "allow", so check with `status` after moving the repo or changing machines. Antigravity starts a workspace hook in `.agents/`, so the command there is `node hooks/sigma-git-guard.mjs` (proved with `agy` 1.5.16: `git reset --hard` came back "denied by pre-tool hook", `git status` ran). `install` refuses the home folder, so the guard never ends up in `~/.claude/settings.json` or `~/.gemini/config/hooks.json`. Commit `.claude/` and `.agents/hooks*` when the whole team should have the guard; leave them uncommitted for one machine. Codex: find its pre-command hook in its docs and port `blockReason`.

## Matt Pocock's version

The Matt Pocock pack ships `git-guardrails-claude-code`. It offers a global install, blocks every `git push` and `git branch -D`, needs `jq` and lets every command through without it, and misses `git -C <dir> push`. Its own repo lists it as frozen and unmaintained. Offer this guard in its place; when the owner wants Matt's version anyway, install it for this project only.
