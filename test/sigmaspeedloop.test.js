import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const skill = join(root, 'sigmaspeedloop');
const template = join(skill, 'assets', 'project-template');

function filesUnder(dir) {
  return fs.readdirSync(dir, { recursive: true }).map((rel) => join(dir, rel)).filter((p) => fs.statSync(p).isFile());
}

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['-c', 'import sys; print(sys.version_info >= (3, 8))'], { encoding: 'utf8' });
    if (r.status === 0 && r.stdout.trim() === 'True') return cmd;
  }
  return null;
}

// The skill is shared, so it must carry no keys, no tokens and no one person's machine paths.
test('sigmaspeedloop holds no keys, tokens or personal paths', () => {
  const secret = [/\bhf_[A-Za-z0-9]{30,}\b/, /\b[a-f0-9]{64}\b/, /\bsk-[A-Za-z0-9]{20,}\b/, /BEGIN [A-Z ]*PRIVATE KEY/];
  const personal = [/C:\\Users\\[^\\<\s]+\\/i, /\/home\/[a-z0-9_-]+\//, /%APPDATA%\\Python\\Python3\d+/i];
  for (const p of filesUnder(skill)) {
    const text = fs.readFileSync(p, 'utf8');
    const rel = relative(root, p);
    for (const re of secret) assert.doesNotMatch(text, re, `${rel} looks like it holds a secret (${re})`);
    for (const re of personal) assert.doesNotMatch(text, re, `${rel} holds a personal path (${re})`);
  }
});

// Every helper the template copies into a new project must at least parse.
test('sigmaspeedloop template Python files compile', (t) => {
  const python = findPython();
  if (!python) {
    t.skip('python 3.8+ not found');
    return;
  }
  const scripts = filesUnder(template).filter((p) => p.endsWith('.py'));
  assert.ok(scripts.length >= 10, 'expected the template scripts');
  const code = 'import ast, sys\nfor p in sys.argv[1:]:\n    ast.parse(open(p, encoding="utf-8").read(), p)\n';
  const r = spawnSync(python, ['-c', code, ...scripts], { encoding: 'utf8' });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
});

// The template's score weights are the ones the verdict reads; they must add up to 1.
test('sigmaspeedloop template weights add up to 1 and match the verdict components', () => {
  const project = JSON.parse(fs.readFileSync(join(template, 'project.json'), 'utf8'));
  const sum = Object.values(project.weights).reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(sum - 1) < 1e-9, `weights add up to ${sum}`);
  const verdict = fs.readFileSync(join(template, 'scripts', 'bench', 'verdict.py'), 'utf8');
  for (const name of Object.keys(project.weights)) assert.match(verdict, new RegExp(`"${name}"`), `verdict.py has no "${name}" component`);
});
