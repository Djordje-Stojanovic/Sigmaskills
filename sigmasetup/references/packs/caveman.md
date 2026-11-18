# Caveman pack setup

Source: [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman), pinned to one commit. License: Apache-2.0.

- The installer puts the skills in as plain files: no hooks, no settings changes. Setup: none for the answer style and the build, review and verify skills.
- `caveman-compress` calls a model API to shrink files. It reads `CAVEMAN_COMPRESS_API_KEY`, else `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, from the environment.
- `caveman-setup` wires a project to the hosted Caveman gateway, with `CAVE_API_KEY` in the repo's ignored env file. Offer it only when the owner has a gateway account.
