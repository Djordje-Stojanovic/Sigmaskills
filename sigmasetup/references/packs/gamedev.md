# Game Dev pack setup

Source: [gamedev-skills/awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills) pinned to one commit. 79 skills for 12 engines plus `router`, which picks the 2 or 3 skills a request needs. License: Apache-2.0; each skill folder gets the repo's `LICENSE` and `NOTICE`. Its `performance-optimization` skill installs as `game-performance-optimization` (the `agent-skills` pack owns the first name), and every route to it is renamed with it.

- **The engine you build in.** Each skill names its engine (Godot, Unity, Unreal, Ebitengine, Bevy, Phaser, PixiJS, three.js, Defold, LÖVE, pygame, Roblox); the engine itself is your install. The engine versions it was checked against: its `docs/VERSION-SUPPORT.md`.
- The router reads a chosen skill at `skills/<category>/<name>/SKILL.md`, the repo's layout. Installed there is no category level: the skill is `<skills folder>/<name>/SKILL.md`, the folder the agent already loads it from by name.
- Keys, MCP servers and repo files: none stated. Start with `router` when you do not know which skill fits.
