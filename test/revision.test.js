import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { computeSkillRevision, computeFileHashes, computeSkillRevisionAndHashes } from '../src/revision.js';

test('revision: computes deterministic SHA-256 for a fixed test vector matching hardcoded literal', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rev-test-'));
  try {
    // File 1: SKILL.md
    fs.writeFileSync(
      path.join(tmpDir, 'SKILL.md'),
      '---\nname: demo\ndescription: Demo skill\n---\n# Demo\n',
      'utf8',
    );
    // File 2: agents/openai.yaml
    fs.mkdirSync(path.join(tmpDir, 'agents'), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, 'agents', 'openai.yaml'),
      'display_name: Demo\n',
      'utf8',
    );

    // Exact hardcoded SHA-256 literal for this vector:
    const expectedLiteral = '3c3605a5886b05c72ada9f7b5bd3fba7d543324dd978a5f24caf29fe0756ad1e';

    const actualRevision = computeSkillRevision(tmpDir);
    assert.equal(actualRevision, expectedLiteral);
    assert.match(actualRevision, /^[a-f0-9]{64}$/);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('revision: fixed synthetic vector matches exact hardcoded hash literal', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rev-vector-'));
  try {
    fs.writeFileSync(path.join(tmpDir, 'a.txt'), 'hello', 'utf8');
    fs.mkdirSync(path.join(tmpDir, 'sub'), { recursive: true });
    fs.writeFileSync(path.join(tmpDir, 'sub', 'b.txt'), 'world', 'utf8');

    // Expected hardcoded SHA-256 string literal:
    const expectedLiteral = '59dc8d3beabc0065656012374ea708854468cceebe7bb493f1b2bec7c2ed4f6d';

    const actual = computeSkillRevision(tmpDir);
    assert.equal(actual, expectedLiteral);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('revision: order of file creation does not change revision (path sorting)', () => {
  const dirA = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rev-order-a-'));
  const dirB = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rev-order-b-'));
  try {
    // In dirA, create z.txt then a.txt
    fs.writeFileSync(path.join(dirA, 'z.txt'), 'content z', 'utf8');
    fs.writeFileSync(path.join(dirA, 'a.txt'), 'content a', 'utf8');

    // In dirB, create a.txt then z.txt
    fs.writeFileSync(path.join(dirB, 'a.txt'), 'content a', 'utf8');
    fs.writeFileSync(path.join(dirB, 'z.txt'), 'content z', 'utf8');

    const revA = computeSkillRevision(dirA);
    const revB = computeSkillRevision(dirB);
    assert.equal(revA, revB);
  } finally {
    fs.rmSync(dirA, { recursive: true, force: true });
    fs.rmSync(dirB, { recursive: true, force: true });
  }
});

test('revision: byte modification changes the revision', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rev-mod-'));
  try {
    fs.writeFileSync(path.join(tmpDir, 'a.txt'), 'hello', 'utf8');
    const rev1 = computeSkillRevision(tmpDir);
    fs.writeFileSync(path.join(tmpDir, 'a.txt'), 'hello!', 'utf8');
    const rev2 = computeSkillRevision(tmpDir);
    assert.notEqual(rev1, rev2);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('revision: computeSkillRevisionAndHashes returns both revision and file map in single pass', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rev-combined-'));
  try {
    fs.writeFileSync(path.join(tmpDir, 'a.txt'), 'hello', 'utf8');
    fs.mkdirSync(path.join(tmpDir, 'nested'), { recursive: true });
    fs.writeFileSync(path.join(tmpDir, 'nested', 'b.txt'), 'world', 'utf8');

    const result = computeSkillRevisionAndHashes(tmpDir);
    const expectedA = crypto.createHash('sha256').update('hello').digest('hex');
    const expectedB = crypto.createHash('sha256').update('world').digest('hex');

    assert.equal(result.revision, '8b1619c01f5fdd8a650671a9ab455e0f11f74ef3c061d8fbae442b32c3b847b1');
    assert.deepEqual(result.files, {
      'a.txt': expectedA,
      'nested/b.txt': expectedB,
    });
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
