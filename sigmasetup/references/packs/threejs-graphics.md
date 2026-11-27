# Three.js Graphics pack setup

Source: [scottstts/Threejs-Awesome-Graphics-Agent-Skills](https://github.com/scottstts/Threejs-Awesome-Graphics-Agent-Skills) (`skills/`), pinned to one commit. 28 skills plus `threejs-skill-router`, which picks the smallest set a request needs. License: MIT; each skill folder gets the repo's `LICENSE`.

- It teaches advanced graphics (lighting and GI, shadows, water, clouds, terrain, procedural worlds, post-processing), not the three.js API. Pair it with the `threejs` pack for API basics.
- Many skills ship runnable examples in their own `examples/` and `assets/` folders and point to a sibling skill's examples by relative path; the pack installs every skill side by side, so those paths resolve.
- **Node** runs the example scripts; **Python 3** runs `threejs-procedural-materials` and `threejs-visual-validation` helpers. Add `three` to the project only on a yes.
- Keys, MCP servers and repo files: none stated. Start with `threejs-skill-router`.
