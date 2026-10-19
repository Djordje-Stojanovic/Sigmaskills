# SigmaTaste plan: Snake Lite terminal game (19-10-2026)

Target: Snake Lite, `src/game.js`, seen by reading the draw loop; no live render in this run.
Medium and mode: terminal UI · Experience
Brand sources: none found (README.md describes rules only)
Lenses: first glance, only this one, type, colour, interface words
Answers: Ruling: expect a sharper look, same game — no brief given. Ruling: scope is the board, the status line and the end screen — the whole UI.

## Direction

A tiny arcade cabinet in the terminal. The board gets a frame, the snake gets a head, and the score becomes the one bold place. Everything else stays plain text.

## Ranked changes

| # | Change | Lenses | Where | What a stranger sees after | Effort | Verify |
|---|---|---|---|---|---|---|
| 1 | Frame the board and give head, body and food distinct glyphs | first glance, only this one | `src/game.js` draw | A game board, not a grid of dots | S | Before and after screenshot of one frame |
| 2 | One status line above the board: score, best, controls; score in the one accent colour | first glance, colour, type | `src/game.js` draw | The score is the first thing seen | S | Squint at the screenshot: one mass leads |
| 3 | A game-over screen with score, best and "Press R to play again" | interface words | `src/game.js` game over | The end says what happened and what to do | M | Play to game over and read only the screen |

## Findings by lens

### First glance

- `src/game.js` draw: every cell is the same dot, so nothing leads → frame and glyphs (feeds change #1).

### Only this one

- The grid of dots could be any grid → a cabinet frame from the arcade world (feeds change #1).

### Type

- `Score:` sits under the board in body text → move it up as a status line (feeds change #2).

### Colour

- No colour at all; one accent for the score is enough (feeds change #2).

### Interface words

- "Game over" alone, then exit → say the score and the next action (feeds change #3).

## Wait-what fixes

glossary in sync · README.md "best" · the README says "best" for the high score, the game says "hi" → use one word in both · two words for one thing
glossary current · no glossary → nothing to check
DESIGN.md · none found → skipped

## Keep

The 10 x 10 board and the plain W, A, S, D controls.

## Not judged

The live render and motion: this run read the code only.

## Later

- Respect `NO_COLOR` when it is set.

## Next step

/sigmaship to ship this plan as one ticket. The builder reads this file first.
