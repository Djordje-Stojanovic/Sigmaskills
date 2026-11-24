# Motion Kit pack setup

Sources: [nolangz/pixel2motion](https://github.com/nolangz/pixel2motion) and [JDhruv14/line-art-animation](https://github.com/JDhruv14/line-art-animation). Each repo root is the skill; each is pinned to one commit.

## Pixel2Motion

- **Python 3** with Pillow and NumPy for the trace, fit and overlay scripts.
- Frame capture and the motion probe need Playwright for Python and its Chromium (`pip install playwright`, then `python -m playwright install chromium`).
- `scripts/export_claude_videos.mjs` exports the maker's own demo page; it expects Chrome at the macOS path and FFmpeg.
- Keys and MCP servers: none. Everything runs on the machine.

## Line-art animation

- **Node 22.18 or later** (the scripts run `.ts` files directly). A scene is a Vite and TypeScript project: copy `lib/` into it and `npm install` there.
- Video export: Chrome, Chromium or Playwright's headless shell (`CHROME=/path` to pick one), then FFmpeg. `scripts/clip.ts` and `scripts/frames.sh` also need FFmpeg.
- Keys and MCP servers: none.
