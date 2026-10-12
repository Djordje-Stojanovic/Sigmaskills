import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
    if (r.status === 0 && /Python 3\.(\d+)/.test(r.stdout + r.stderr)) return cmd;
  }
  return null;
}

// The sigmaresearch readers are Python stdlib scripts. Their unit tests run on recorded fixtures, no network.
test('sigmaresearch reader unit tests pass (python unittest, offline)', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'test/sigmaresearch', '-v'], {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, SIGMARESEARCH_LIVE: '', PYTHONDONTWRITEBYTECODE: '1' },
  });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
});
