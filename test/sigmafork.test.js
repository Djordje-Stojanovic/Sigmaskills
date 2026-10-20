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

// sigmafork.py copies, scans, fixes and verifies in temp folders only: no network, no real repo.
test('sigmafork helper unit tests pass (python unittest, offline)', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'test/sigmafork', '-v'], {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
});

test('the onboarding template carries FILL markers and every stop the guide names', async () => {
  const { readFileSync } = await import('node:fs');
  const html = readFileSync(join(root, 'sigmafork', 'assets', 'guide-template.html'), 'utf8');
  assert.match(html, /\bFILL\b/);
  for (const stop of ['What it is', 'The map', 'Run it', 'Real example projects', 'How a change flows', 'Your first three tasks', 'Where things are', 'Keys and access', 'Part 2']) {
    assert.ok(html.includes(stop), `template is missing the stop "${stop}"`);
  }
});
