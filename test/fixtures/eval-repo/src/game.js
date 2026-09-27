import readline from 'node:readline';
import { HEIGHT, WIDTH, newGame, step, turn } from './logic.js';
import { loadBest, saveBest } from './scores.js';

function draw(state) {
  const rows = [];
  for (let y = 0; y < HEIGHT; y++) {
    let row = '';
    for (let x = 0; x < WIDTH; x++) {
      if (state.snake.some(([sx, sy]) => sx === x && sy === y)) row += 'O';
      else if (state.food[0] === x && state.food[1] === y) row += '*';
      else row += '.';
    }
    rows.push(row);
  }
  console.clear();
  console.log(rows.join('\n'));
  console.log(`Score: ${state.score}`);
}

const state = newGame();
console.log(`Best: ${loadBest()}`);
readline.emitKeypressEvents(process.stdin);
if (process.stdin.isTTY) process.stdin.setRawMode(true);
process.stdin.on('keypress', (_, key) => {
  if (key.ctrl && key.name === 'c') process.exit(0);
  turn(state, key.name);
});

const timer = setInterval(() => {
  step(state);
  draw(state);
  if (state.over) {
    clearInterval(timer);
    saveBest(state.score);
    console.log('Game over');
    process.exit(0);
  }
}, 200);
