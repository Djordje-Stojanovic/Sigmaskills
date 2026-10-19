# Sources

Baseline: [abubakarsiddik31/claude-skills-collection](https://github.com/abubakarsiddik31/claude-skills-collection) (1,103 stars, no licence file, 252 skills in 13 categories, read 2026-10-19). Every skill in it that touches taste, design, visuals or writing quality was listed, and each one's `SKILL.md` was read. The lenses are written fresh: ideas are credited, no source text is copied. Stars are the GitHub count on 2026-10-19.

## Used

| Skill | Repository | Stars | Licence | Feeds |
|---|---|---|---|---|
| frontend-design | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 182,002 | Apache-2.0 (skill folder) | first glance, only this one, spent defaults, type, colour, one bold place, motion, interface words |
| canvas-design | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/canvas-design) | 182,002 | Apache-2.0 (skill folder) | only this one, one bold place |
| writing-shape | [mattpocock/skills](https://github.com/mattpocock/skills/tree/main/skills/in-progress/writing-shape) | 296,231 | MIT | rhythm |
| humanizer | [blader/humanizer](https://github.com/blader/humanizer) | 58,113 | MIT | prose |
| copywriting, copy-editing, cro, marketing-psychology | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | 55,384 | MIT | first glance, only this one, one bold place, interface words, the pitch |
| emil-design-eng | [emilkowalski/skills](https://github.com/emilkowalski/skills/tree/main/skills/emil-design-eng) | 47,388 | MIT | motion, feel |
| web-design-guidelines | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines) and its fetched rules file | 32,608 | MIT | type, motion, feel, interface words, everyone |
| frontend-slides | [zarazhangrui/frontend-slides](https://github.com/zarazhangrui/frontend-slides) | 30,856 | MIT | spent defaults, rhythm |
| no-ai-slop | [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop) | 12,534 | MIT | only this one, prose |
| avoid-ai-writing | [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) | 5,087 | MIT | prose |
| skill.color-expert | [meodai/skill.color-expert](https://github.com/meodai/skill.color-expert) | 615 | CC-BY-4.0 (credit: meodai) | colour, charts |
| revealjs-skill | [ryanbbrown/revealjs-skill](https://github.com/ryanbbrown/revealjs-skill) | 416 | MIT | spent defaults, rhythm |
| claude-d3js-skill | [chrisvoncsefalvay/claude-d3js-skill](https://github.com/chrisvoncsefalvay/claude-d3js-skill) | 242 | none stated | charts |
| accessibility-skills | [mgifford/accessibility-skills](https://github.com/mgifford/accessibility-skills) | 55 | AGPL-3.0 (ideas only) | everyone, charts |
| claude-a11y-skill | [airowe/claude-a11y-skill](https://github.com/airowe/claude-a11y-skill) | 17 | none stated | everyone |

Outside the collection, kept from an earlier taste review: Leonxlnx `taste-skill` (the one-second and squint passes, first glance).

Adoption is uneven on purpose: low-star sources feed only lenses where a high-star source agrees (Vercel for access, Anthropic for colour roles), or where no larger source covers the topic (colour science).

## Read and not used

| Skill | Why not |
|---|---|
| algorithmic-art (Anthropic) | A p5.js art workflow; its one taste idea (name a movement first) already comes from canvas-design. |
| brand-guidelines (Anthropic) | Anthropic's own palette and fonts. The general rule it implies, "the brand wins", is in the operating contract. |
| theme-factory (Anthropic) | Ten preset themes: picking a preset is the default this skill exists to avoid. |
| design-mobile-apps (designed-by-ai, 19 stars) | A client for a paid design API, not a way of seeing. |
| web-asset-generator (alonw0, 519 stars) | Generates favicons and social images; its contrast check is covered by colour and everyone. |
| writing-skills (obra/superpowers) | About writing agent skills, not about the taste of a target. |
| writing-fragments, writing-beats (mattpocock) | Idea-mining sessions; writing-shape carries the one lens idea. |
| edit-article (mattpocock) | Listed in the collection; the path no longer exists in the repository. |
| Content Research Writer, claude-blog, claude-email, academic writing skills | Content production pipelines, not taste lenses; their quality rules repeat the prose sources. |
| expo-app-design (expo/skills) | Platform build guidance for one framework. |

## Contradictions and how the lenses settle them

- frontend-slides bans Inter, Roboto and system fonts outright; frontend-design says every look is legitimate when the brief asks. The lenses treat them as defaults the brand can earn, never bans.
- emil-design-eng gives fixed motion numbers (under 300 ms, ease-out only); the motion lens keeps them as defaults for UI and lets the brand's own motion win.
- Vercel's copy rules ask for Title Case and curly quotes; frontend-design asks for sentence case. The interface words lens says sentence case unless the brand's style says otherwise.
- revealjs-skill asks for icons to add interest; frontend-design lists icon rows as a generic tell. The rhythm and spent defaults lenses keep icons only where they carry information.
