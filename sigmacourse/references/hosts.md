# Hosts

SigmaCourse works the same on every agent harness. Three things change: how a skill is called, how agents run in parallel, and how the unattended run starts. Find the harness the user runs (the one they name, else your own tools and slash commands, else ask once). When you do not know it well, read its docs: the context7 MCP, a web search, or a fast research subagent. SigmaLoop owns the unattended-run prompt and does the same for its host file.

Harnesses met so far, as examples:

| Harness | Call the skill | Unattended run |
|---|---|---|
| Claude Code | `/sigmacourse` | `/goal` (multi-day, comes back after a restart) or `/loop` |
| Codex | `$sigmacourse` | `/goal` |
| pi | `/skill:sigmacourse` | the pi prompt SigmaLoop writes |
| T3 Code | the call of the agent it drives | a scheduled task or `/goal` in a thread |

Parallel agents: use the harness's own way (subagents, spawned agents, child threads); where none exists, run one job at a time. Every writing agent gets its own git worktree.

## Personas on any host

A persona runs as a headless session from a folder outside the course repo, with no tools, no extra servers, and the persona file as its system prompt or instructions. Exclude every global rule file the account loads (`CLAUDE.md`, `AGENTS.md`): a global writing rule flattens the persona's voice. One launcher script per persona.
