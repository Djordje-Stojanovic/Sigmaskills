# Refactor scan

Counting method: `laloc` is not installed, so I used the Node.js fallback from `scan.md`.

| Rank | File | Lines |
|---:|---|---:|
| 1 | src/game.js | 41 |
| 2 | src/logic.js | 38 |
| 3 | src/scores.js | 13 |

## Choices

| File | Choice | Line change | Risk | Verification |
|---|---|---|---|---|
| src/game.js | extract `draw` | -0 / +0 moved | low | `npm test` plus a manual run |
