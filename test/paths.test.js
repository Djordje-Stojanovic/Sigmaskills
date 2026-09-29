import assert from 'node:assert/strict';
import path from 'node:path';
import test from 'node:test';
import { assertPathInside, isPathInside } from '../src/paths.js';
import { resolveSkillPath } from '../src/destinations.js';

const BASE = path.resolve('base-dir');

test('isPathInside: the base, children, and names that start with two dots are inside', () => {
  assert.equal(isPathInside(BASE, BASE), true);
  assert.equal(isPathInside(BASE, path.join(BASE, 'a', 'b')), true);
  assert.equal(isPathInside(BASE, path.join(BASE, '..cache', 'skills')), true);
});

test('isPathInside: parent, sibling, and other-root paths are outside', () => {
  assert.equal(isPathInside(BASE, path.dirname(BASE)), false);
  assert.equal(isPathInside(BASE, path.join(BASE, '..', 'x')), false);
  assert.equal(isPathInside(BASE, path.join(path.parse(BASE).root, 'elsewhere')), false);
});

test('assertPathInside: rejects .., ../x, and absolute escapes; accepts ..cache/skills', () => {
  assert.throws(() => assertPathInside(BASE, '..', 'entry'), /entry '\.\.' escapes/);
  assert.throws(() => assertPathInside(BASE, '../x', 'entry'), /escapes/);
  assert.throws(() => assertPathInside(BASE, path.join(path.parse(BASE).root, 'elsewhere'), 'entry'), /escapes/);
  assert.doesNotThrow(() => assertPathInside(BASE, '..cache/skills', 'entry'));
});

test('resolveSkillPath: a destination named ..cache/skills resolves; .. and ../x stay rejected (#67)', () => {
  assert.equal(resolveSkillPath(BASE, '..cache/skills', 's').relativeDestination, '..cache/skills/s');
  assert.throws(() => resolveSkillPath(BASE, '..', 's'), /invalid destination/);
  assert.throws(() => resolveSkillPath(BASE, '../x', 's'), /invalid destination/);
});
