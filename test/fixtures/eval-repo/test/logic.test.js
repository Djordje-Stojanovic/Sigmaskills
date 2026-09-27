import assert from 'node:assert/strict';
import test from 'node:test';
import { newGame, step } from '../src/logic.js';

test('the snake moves right', () => {
  const state = step(newGame());
  assert.deepEqual(state.snake[0], [6, 5]);
});
