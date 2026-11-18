import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const file = path.join(path.dirname(fileURLToPath(import.meta.url)), 'sigmaresearch_dry.py');
const python = ['python3', 'python'].find((cmd) => spawnSync(cmd, ['--version']).status === 0);

test('sigmaresearch: the X, arXiv and SEC parsers read fixed answers offline', { skip: !python && 'python not found' }, () => {
  const r = spawnSync(python, [file], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
});
