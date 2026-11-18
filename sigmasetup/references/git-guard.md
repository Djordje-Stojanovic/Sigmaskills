# Git guard

A Claude Code hook for one repo. It stops the agent from running git commands that destroy work nobody can get back, and it is gone again with one command.

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

- On: `node <sigmasetup>/scripts/git-guard.mjs install .` copies the hook to `.claude/hooks/sigma-git-guard.mjs` and adds one `PreToolUse` entry (Bash and PowerShell) to `.claude/settings.json`. Other settings stay as they are; running it twice adds nothing.
- Off: `node .claude/hooks/sigma-git-guard.mjs remove .` takes the entry and the file out again. When `.claude/settings.json` held only the guard, the file goes too.
- Check: `node .claude/hooks/sigma-git-guard.mjs status .`

Claude Code treats a hook that crashes (no Node, a moved file) as "allow", so check with `status` after moving the repo or changing machines. `install` refuses the home folder, so the guard can never end up in `~/.claude/settings.json`. Commit `.claude/settings.json` and the hook file when the whole team should have the guard; leave them uncommitted for one machine.

## Matt Pocock's version

The Matt Pocock pack ships `git-guardrails-claude-code`. It offers a global install, blocks every `git push` and `git branch -D`, needs `jq` and lets every command through without it, and misses `git -C <dir> push`. Its own repo lists it as frozen and unmaintained. Offer this guard in its place; when the owner wants Matt's version anyway, install it for this project only.
