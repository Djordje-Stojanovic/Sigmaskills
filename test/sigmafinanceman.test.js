import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const helper = join(root, 'sigmafinanceman', 'scripts', 'finman.py');

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['-c', 'import openpyxl, pptx, sys; print(sys.version_info >= (3, 10))'], { encoding: 'utf8' });
    if (r.status === 0 && r.stdout.trim() === 'True') return cmd;
  }
  return null;
}

// The offline self-test: a fictional company through every model and writer; with LibreOffice it also recalculates each workbook.
test('sigmafinanceman selftest passes (every model, every writer, no network)', { timeout: 300000 }, (t) => {
  const python = findPython();
  if (!python) {
    t.skip('python 3.10+ with openpyxl and python-pptx not found');
    return;
  }
  const r = spawnSync(python, [helper, 'selftest'], { cwd: root, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
  assert.doesNotMatch(r.stdout, /^FAIL/m);
  assert.match(r.stdout, /^PASS \(files in /m);
});
