# Three.js Games pack setup

Source: [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills) (`skills/`), pinned to one commit. 9 skills; `threejs-game-director` routes gameplay, graphics, UI, asset generation, audio, debugging and release QA. License: MIT; each skill folder gets the repo's `LICENSE`.

- **Node** for the game and `npx playwright` (browser checks in `threejs-game-director`, `threejs-gameplay-systems` and `threejs-qa-release`). **Python 3** (or `uv`) for the asset scripts.
- **Optional keys**, read from the environment or `--api-key`, only for generated assets: `TRIPO_API_KEY` (`threejs-3d-generator`), `GEMINI_API_KEY` (`threejs-image-generator`), `ELEVENLABS_API_KEY` (`threejs-audio-generator`). Each script's `probe` prints `SET` or `MISSING`. Without them the director builds the game with no generated assets.
- MCP servers and repo files: none stated. Start with `threejs-game-director` in an empty folder or an existing three.js game.
