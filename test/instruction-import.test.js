// #1538: the shared agent text lives once, in AGENTS.md; CLAUDE.md opens with the import line.
// An import, not a symlink: a symlink breaks on Windows clones.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lstatSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

test('CLAUDE.md is a real file that opens with @AGENTS.md', () => {
  const file = join(root, 'CLAUDE.md');
  assert.equal(lstatSync(file).isSymbolicLink(), false);
  assert.equal(readFileSync(file, 'utf8').split(/\r?\n/)[0].trim(), '@AGENTS.md');
});

test('AGENTS.md holds the shared text', () => {
  const text = readFileSync(join(root, 'AGENTS.md'), 'utf8');
  assert.match(text, /^# AGENTS\.md/);
  assert.doesNotMatch(text, /^@AGENTS\.md/m);
});
