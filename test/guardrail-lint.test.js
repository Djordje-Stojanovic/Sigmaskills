import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

// guardrail_lint (plan 2026-10-17 D8, owner 2026-10-19): no new model-authored prohibition lands in an agent-facing doc,
// and the lint itself is proven by its own negative test. The script is Python because every workbench on this machine
// runs it from a Python gate; `npm test` runs it too, so a doc edit cannot land a ban unnoticed.
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SCRIPT = path.join(ROOT, 'scripts', 'guardrail_lint.py');
const ALLOW = path.join(ROOT, 'scripts', 'guardrail_allowlist.txt');

function run(args) {
  return spawnSync(process.env.PYTHON || 'python', [SCRIPT, ...args], { cwd: ROOT, encoding: 'utf8' });
}

function pythonMissing(r) {
  return r.error && (r.error.code === 'ENOENT' || r.error.code === 'EACCES');
}

test('the guardrail lint and its allowlist ship with the repo', () => {
  assert.ok(fs.existsSync(SCRIPT), 'scripts/guardrail_lint.py exists');
  assert.ok(fs.existsSync(ALLOW), 'scripts/guardrail_allowlist.txt exists');
});

test('guardrail_lint --selftest passes: a ban fails, a mechanical guard and an allowlisted keep pass', (t) => {
  const r = run(['--selftest']);
  if (pythonMissing(r)) return t.skip('python is not on PATH');
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /selftest PASS/);
});

test('this repo carries no un-allowlisted prohibition in its agent-facing docs', (t) => {
  const r = run([]);
  if (pythonMissing(r)) return t.skip('python is not on PATH');
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /no new prohibition/);
});
