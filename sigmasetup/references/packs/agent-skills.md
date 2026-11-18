# Agent Skills pack setup

Source: [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) by Addy Osmani, pinned to one commit. License: MIT.

- Several skills (`code-review-and-quality`, `frontend-ui-engineering`, `doubt-driven-development` and others) link to checklists in the repo's top-level `references/` folder: security, performance, accessibility, testing, definition of done. The installer copies only the skill folders, so those links are dead. Offer to copy that folder from the pinned commit into the repo as `docs/agent-skills/`, and tell the owner the links still say `../../references/`. Undo: delete `docs/agent-skills/`.
- Tools: the skills use the repo's own test, type-check and build commands. `browser-testing-with-devtools` needs Chrome DevTools or Playwright (`npx playwright install`).
- Keys and MCP servers: none required.
