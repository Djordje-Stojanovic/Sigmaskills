# pstack pack setup

Source: Lauren Tan's (poteto) pstack in [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack), installed from its generated Claude Code tree `harness/pstack/claude-code/skills`, pinned to one commit. 59 skills: `poteto-mode` with its playbooks, 23 `principle-*` skills, review, verification and investigation skills. License: MIT; each skill folder gets `harness/pstack/claude-code/LICENSE`.

- Matt Pocock's pack owns `tdd` and `teach`, so pstack's install as `pstack-tdd` and `pstack-teach`, and every call to them in the pack is renamed with them. The plain verb "teach" in prose stays.
- **Subagents.** The playbooks of `poteto-mode` spawn the `poteto-agent` subagent, and `no-comments` uses `comment-sicko`. Both are agent files in `harness/pstack/claude-code/agents/`, not skills, so this pack does not install them. In Claude Code they come with the upstream plugin: `/plugin marketplace add cursor/plugins`, then `/plugin install pstack@cursor-plugins` (its skills are prefixed `pstack:`, so they do not clash with this pack's).
- Run `setup-pstack` first: it picks a reasoning budget and a model per role. Then use `poteto-mode` for any task that needs rigor; `poteto-help` says which skill fits.
- The skills are written for Cursor. The adapter that maps Cursor names to Claude Code (`docs/harness/claude-code.md`) and the guide (`docs/guide/`) sit outside the skill folders, so their relative links do not resolve after install: read them on GitHub. A step that needs a Cursor-only feature (Bugbot, automations) is skipped.
- **`gh`** for the PR and review steps. Keys and MCP servers: none stated.
