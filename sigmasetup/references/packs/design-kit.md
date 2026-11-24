# Design Kit pack setup

Sources: [kaankiziltug/logo-design-skill](https://github.com/kaankiziltug/logo-design-skill) (`skills/`) and [larashero3-dotcom/lieflat-charts](https://github.com/larashero3-dotcom/lieflat-charts) (the repo root is the skill), each pinned to one commit.

## Logo Design

- **Python 3.** On Windows use `python` or `py -3`; `python3` is often the Store stub. Pillow for the PNG sheets and exports.
- PNG renders use the first of cairosvg, `rsvg-convert`, Inkscape or a headless Chrome, Edge, Chromium or Brave found on the machine.
- Keys, MCP servers and repo files: none. Works offline; the 1,400-logo library ships inside the skill.

## Lieflat Charts

- Written in Chinese; it answers in the user's language.
- **Node** for `scripts/validate.mjs`. `scripts/smoke-new-charts.mjs` also needs a global `playwright`: that is a machine-wide install, ask first.
- Its pages load ECharts or Chart.js from cdn.jsdelivr.net and fonts from Google Fonts unless they are inlined; pure-SVG charts run offline.
- Keys and MCP servers: none.
