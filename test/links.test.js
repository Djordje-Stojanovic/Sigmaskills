import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {
  createSkillLink,
  inspectManagedPath,
  pathExists,
  recommendedLinkMethod,
  removeManagedPath,
} from '../src/links.js';

function makeTree() {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-link-'));
  const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
  const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
  fs.mkdirSync(canonical, { recursive: true });
  fs.writeFileSync(path.join(canonical, 'SKILL.md'), 'canonical-body', 'utf8');
  fs.mkdirSync(path.dirname(host), { recursive: true });
  return { projectRoot, canonical, host };
}

test('recommended link method is a Windows junction or a POSIX symbolic link', () => {
  const expected = process.platform === 'win32' ? 'junction' : 'symlink';
  assert.equal(recommendedLinkMethod(), expected);
});

test('createSkillLink installs a real platform link that reads the canonical copy', () => {
  const { projectRoot, canonical, host } = makeTree();
  try {
    const result = createSkillLink(host, canonical, projectRoot);
    assert.equal(result.method, recommendedLinkMethod());
    assert.ok(fs.lstatSync(host).isSymbolicLink());
    assert.equal(fs.realpathSync(host), fs.realpathSync(canonical));
    assert.equal(fs.readFileSync(path.join(host, 'SKILL.md'), 'utf8'), 'canonical-body');

    fs.writeFileSync(path.join(canonical, 'SKILL.md'), 'shared-edit', 'utf8');
    assert.equal(fs.readFileSync(path.join(host, 'SKILL.md'), 'utf8'), 'shared-edit');

    const inspected = inspectManagedPath(host);
    assert.equal(inspected.method, recommendedLinkMethod());
    assert.equal(inspected.broken, false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('removing a managed link leaves the canonical copy intact', () => {
  const { projectRoot, canonical, host } = makeTree();
  try {
    createSkillLink(host, canonical, projectRoot);
    removeManagedPath(host);
    assert.ok(!pathExists(host));
    assert.equal(fs.readFileSync(path.join(canonical, 'SKILL.md'), 'utf8'), 'canonical-body');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('createSkillLink refuses a destination that already occupies the path', () => {
  const { projectRoot, canonical, host } = makeTree();
  try {
    fs.mkdirSync(host, { recursive: true });
    fs.writeFileSync(path.join(host, 'SKILL.md'), 'occupied', 'utf8');
    assert.throws(
      () => createSkillLink(host, canonical, projectRoot),
      /already exists/,
    );
    assert.equal(fs.readFileSync(path.join(host, 'SKILL.md'), 'utf8'), 'occupied');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('inspectManagedPath reports a broken link and a wrong-target link', () => {
  const { projectRoot, canonical, host } = makeTree();
  const other = path.join(projectRoot, '.other', 'skills', 'sigmawrite');
  try {
    fs.mkdirSync(other, { recursive: true });
    fs.writeFileSync(path.join(other, 'SKILL.md'), 'other', 'utf8');
    createSkillLink(host, other, projectRoot);
    const wrong = inspectManagedPath(host, canonical);
    assert.equal(wrong.wrongTarget, true);
    assert.equal(wrong.broken, false);

    removeManagedPath(host);
    const missingTarget = path.join(projectRoot, '.missing', 'skills', 'sigmawrite');
    fs.mkdirSync(missingTarget, { recursive: true });
    createSkillLink(host, missingTarget, projectRoot);
    fs.rmSync(missingTarget, { recursive: true, force: true });
    const broken = inspectManagedPath(host, canonical);
    assert.equal(broken.broken, true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('createSkillLink refuses a target that escapes the project', () => {
  const { projectRoot, host } = makeTree();
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-'));
  try {
    fs.writeFileSync(path.join(outside, 'SKILL.md'), 'escaped', 'utf8');
    assert.throws(
      () => createSkillLink(host, outside, projectRoot),
      /escapes the project/,
    );
    assert.ok(!pathExists(host));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(outside, { recursive: true, force: true });
  }
});
