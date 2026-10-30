# Hosts

SigmaCourse works the same on every agent host. Three things change: how a skill is called, how agents run in parallel, and how the unattended run starts. SigmaLoop owns the run prompt; its `references/hosts.md` names the host file to read.

| Host | Call the skill | Unattended run (SigmaLoop host file) |
|---|---|---|
| Claude Code | `/sigmacourse` | `/goal` (multi-day, comes back after a restart) or `/loop` |
| Codex | `$sigmacourse` | `/goal` |
| Antigravity | skills load from `<project>/.agents/skills` | its unattended mode, per `host-antigravity.md` |
| pi | `/skill:sigmacourse` | the pi prompt, per `host-pi.md` |
| T3 Code | the call of the agent it drives (Codex, Claude Code and others) | a scheduled task, per `host-t3-code.md` |
| Any other host | read `SKILL.md` | the plain instruction SigmaLoop writes |

Parallel agents: use the host's own way (Claude Code subagents, Codex spawned agents); where none exists, run one job at a time. Every writing agent gets its own git worktree.

## Personas on any host

A persona runs as a headless session from a folder outside the course repo, with no tools, no extra servers, and the persona file as its system prompt or instructions. Exclude every global rule file the account loads (`CLAUDE.md`, `AGENTS.md`): a global writing rule flattens the persona's voice. One launcher script per persona.

## Media on any host

Media jobs call the user's own tools: video, voice, image and 3D generators, local or hosted. The spec names each tool, its machine and its limits. When a Sigma or other installed skill covers a tool (HyperFrames for programmatic video, an image or voice skill), the run file names that skill; otherwise it names the command.
