# Superpowers pack setup

Source: [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent, pinned to one commit. License: MIT (the `LICENSE` file in that repo).

- **Session start.** Upstream installs as a plugin whose `SessionStart` hook injects the `using-superpowers` bootstrap. This installer copies the skills only: no hook is written. Tell the owner, and call the skills by name (`brainstorming`, `writing-plans`, `executing-plans`).
- **Sub-agents.** `dispatching-parallel-agents` and `subagent-driven-development` need a host that can start sub-agents.
- **Worktrees.** `using-git-worktrees` and `finishing-a-development-branch` use `git worktree`. Check that the repo is a git repository.
- Keys, MCP servers and other repo files: none stated.
