# Hallmark pack setup

Source: [Nutlope/hallmark](https://github.com/Nutlope/hallmark) pinned to one commit. License: MIT.

- **Node 18 or later.** Check with `node --version`.
- **Browser checks** (`sloplint --render`, screenshots) also need `npm i -g puppeteer-core` and Chrome. That is a machine-wide install: ask first. Without them the static checks still run.
- Optional `TOGETHER_API_KEY`: `scripts/imagegen.mjs` sends prompts to api.together.xyz for generated stills (the comp step). An Inspo MCP server is used when one is connected. Library photos come from Wikimedia Commons.
