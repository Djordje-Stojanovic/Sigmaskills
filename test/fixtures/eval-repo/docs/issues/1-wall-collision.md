# #1 The snake survives one cell past the right and bottom walls

The README says the snake dies when it leaves the board. In `src/logic.js`, `step` uses `>` instead of `>=`, so the snake can move to x = 10 or y = 10.

## Acceptance criteria

- [ ] Moving to x = 10 or y = 10 ends the game.
- [ ] A test in `test/logic.test.js` covers both walls.
