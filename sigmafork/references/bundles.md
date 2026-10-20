# Skill bundles

Install into the copy (project scope), from inside `<dest>`. The `skills` CLI writes to each Agent Host's project skill folder (`.agents/skills/`, `.claude/skills/` and others); `--copy` writes real files instead of links, so the copy stays independent of any shared folder.

| Bundle | What it brings | Install |
|---|---|---|
| The source's own skills | The skills the repo ships (for example its `storgestudio-*` set), nothing else | They came with the copy. Remove the others: list the skill folders (`.agents/skills`, `.claude/skills`) and delete the folders not in the kept set. If the repo has a `skills-lock.json`, `npx skills experimental_install` restores the locked ones |
| All Sigma | Review, improve, ship, brief, research, taste, loop, and the rest | `npx @djordje-stojanovic/sigmaskills install --all --project .` |
| All Matt Pocock | Grilling, TDD, domain modeling, codebase design, prototype, PR, code review | `npx skills add mattpocock/skills --all --copy` |
| All Three.js | Fundamentals, geometry, materials, lighting, shaders, loaders, animation, performance | `npx skills add CloudAI-X/threejs-skills --all --copy` |
| HyperFrames | The HyperFrames video skills (core, CLI, animation, captions, registry) | `npx skills add heygen-com/hyperframes --all --copy` |
| HyperFrames + Sigma | Both rows above | Both commands |
| None | No skills | Delete the copied skill folders, or keep them: ask in the grill |

Any other GitHub skill repo works the same way: `npx skills add <owner>/<repo> --list` shows its skills, `--skill <name>` picks some, `--all` takes every one.

## After the install

- List what is installed (`npx skills list`, or the skill folders) and put the list in the guide's cheat sheet.
- Skills copied with the source can carry hardcoded paths too: they are inside `<dest>`, so `scan` and `fix` already covered them. Run `verify` again after the install.
- When the copy's agent instructions (`AGENTS.md`, `CLAUDE.md`) name skills that are now gone, mark those lines for the owner in the guide's "Where things are"; do not rewrite his instructions unasked.
