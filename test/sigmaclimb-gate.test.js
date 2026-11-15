import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const file = path.join(path.dirname(fileURLToPath(import.meta.url)), 'sigmaclimb_gate.py');
const python = spawnSync('python3', ['--version']).status === 0;

test('sigmaclimb template: promotion needs a held-out PASS for this exact change', { skip: !python && 'python3 not found' }, () => {
  const r = spawnSync('python3', [file, '-v'], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
});
