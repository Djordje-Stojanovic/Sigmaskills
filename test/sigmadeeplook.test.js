import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
    if (r.status === 0 && /Python 3\.(\d+)/.test(r.stdout + r.stderr) && Number(RegExp.$1) >= 10) return cmd;
  }
  return null;
}

// look.py is a Python stdlib script. The offline tests run it on the committed fixtures in the bare tier
// (--no-tools), so they pass on any machine with Python 3.10+ and nothing else installed.
test('sigmadeeplook: unit tests and the bare-tier selftest pass (python unittest, offline)', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3.10+ not found');
  const r = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'test/sigmadeeplook', '-v'], {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
});
