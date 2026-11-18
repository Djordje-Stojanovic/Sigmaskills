# Marketing Skills pack setup

Source: [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) by Corey Haines, pinned to one commit. License: MIT.

- The skills read `.agents/product-marketing.md` (or `.claude/product-marketing.md`) before they ask questions. Offer to write it once per product with the pack's `product-marketing` skill. Undo: delete the file.
- Some skills link to tool notes in the repo's top-level `tools/` folder (Ahrefs, Semrush, Exa, Firecrawl and more). The installer copies only the skills, so those links are dead; read the notes on GitHub at the pinned commit.
- Keys are optional and per tool, in the environment: `SCRAPECREATORS_API_KEY`, `ELEVENLABS_API_KEY`, `POSTHOG_API_KEY`, `GITHUB_TOKEN`. Ask only for the tools the owner uses.
