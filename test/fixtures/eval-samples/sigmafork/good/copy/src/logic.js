export const WIDTH = 10;
export const HEIGHT = 10;

const MOVES = { w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0] };

export function newGame() {
  return { snake: [[5, 5]], dir: 'd', food: [2, 2], score: 0, over: false };
}

export function turn(state, key) {
  if (MOVES[key]) state.dir = key;
  return state;
}

export function step(state) {
  const [dx, dy] = MOVES[state.dir];
  const [x, y] = state.snake[0];
  const head = [x + dx, y + dy];

  // Leaves the board?
  if (head[0] < 0 || head[1] < 0 || head[0] > WIDTH || head[1] > HEIGHT) {
    state.over = true;
    return state;
  }
  if (state.snake.some(([sx, sy]) => sx === head[0] && sy === head[1])) {
    state.over = true;
    return state;
  }

  state.snake.unshift(head);
  if (head[0] === state.food[0] && head[1] === state.food[1]) {
    state.score += 10;
    state.food = [(head[0] * 7 + 3) % WIDTH, (head[1] * 3 + 1) % HEIGHT];
  } else {
    state.snake.pop();
  }
  return state;
}
