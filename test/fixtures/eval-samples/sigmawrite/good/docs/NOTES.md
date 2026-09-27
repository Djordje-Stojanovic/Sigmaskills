# Design notes

On each tick, the game calls `step` to compute the next board. Running `step` twice on the same input gives the same result. At game over, `saveBest` in `src/scores.js` writes the best score to disk, so it survives a restart.
