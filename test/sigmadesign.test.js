import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
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

// sigmadesign.py makes, builds, checks, scans and integrates in temp folders only: no network, no real repo.
test('sigmadesign helper unit tests pass (python unittest, offline)', (t) => {
  const python = findPython();
  if (!python) return t.skip('python 3 not found');
  const r = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'test/sigmadesign', '-v'], {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
});

test('the card names every helper command and its three references', () => {
  const card = readFileSync(join(root, 'sigmadesign', 'SKILL.md'), 'utf8');
  for (const cmd of ['new', 'pack', 'build', 'check', 'scan', 'integrate']) {
    assert.ok(card.includes(`sigmadesign.py ${cmd}`) || card.includes(`\`${cmd} `) || card.includes(` ${cmd} `), `card does not name the ${cmd} command`);
  }
  for (const ref of ['format.md', 'integrate.md', 'quality.md']) assert.ok(card.includes(`references/${ref}`), `card does not link ${ref}`);
});
