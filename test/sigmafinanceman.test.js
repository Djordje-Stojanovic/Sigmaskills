import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const script = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'sigmafinanceman', 'scripts', 'finman.py');
const python = ['python3', 'python'].find((cmd) => spawnSync(cmd, ['-c', 'import openpyxl, pptx']).status === 0);

test('sigmafinanceman: offline selftest of every model, the reverse DCF, the scenarios and the page', { skip: !python && 'python with openpyxl and python-pptx not found' }, () => {
  const r = spawnSync(python, [script, 'selftest'], { encoding: 'utf8', env: { ...process.env, FINMAN_NO_SOFFICE: '1' } });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /PASS {2}Reverse DCF: the implied growth gives back the price/);
});
