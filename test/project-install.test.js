import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { createInstallPlan, formatPlanHuman, formatPlanJson } from '../src/plan.js';
import {
  loadProjectLock,
  saveProjectLock,
  updateProjectLockSkill,
  validateProjectLock,
  PROJECT_LOCK_FILENAME,
} from '../src/project-lock.js';
import {
  loadProjectState,
  saveProjectState,
  recordSkillInState,
  isDestinationOwned,
  STATE_FILENAME,
} from '../src/state.js';
import {
  acquireConcurrencyLock,
  executeProjectInstall,
} from '../src/transaction.js';

const ROOT = findPackageRoot();

test('project-lock: load, update, save, and validate timestamp-free sorted lock', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-lock-test-'));
  try {
    // 1. Loading non-existent lock returns empty template
    const initial = loadProjectLock(tmpDir);
    assert.equal(initial.schemaVersion, 1);
    assert.equal(initial.release, null);
    assert.deepEqual(initial.skills, {});

    // 2. Update skills in reverse alphabetical order
    let lock = updateProjectLockSkill(initial, 'sigmawrite', 'hash_w', '0.1.0');
    lock = updateProjectLockSkill(lock, 'sigmabrief', 'hash_b', '0.1.0');
    lock = updateProjectLockSkill(lock, 'sigmareview', 'hash_r', '0.1.0');

    // 3. Save lock
    saveProjectLock(tmpDir, lock);

    // 4. Verify on-disk file content is sorted alphabetically and has no timestamps or machine paths
    const lockPath = path.join(tmpDir, PROJECT_LOCK_FILENAME);
    assert.ok(fs.existsSync(lockPath));
    const raw = fs.readFileSync(lockPath, 'utf8');

    // Ensure no timestamps or machine paths exist in raw JSON
    assert.ok(!raw.includes('installedAt'));
    assert.ok(!raw.includes('updatedAt'));
    assert.ok(!raw.includes('destination'));
    assert.ok(!raw.includes('/'));
    assert.ok(!raw.includes('\\'));

    const parsed = JSON.parse(raw);
    const keys = Object.keys(parsed.skills);
    assert.deepEqual(keys, ['sigmabrief', 'sigmareview', 'sigmawrite']);
    assert.equal(parsed.release, '0.1.0');
    assert.equal(parsed.skills.sigmabrief.revision, 'hash_b');

    // 5. Validation rejects lock with machine paths or timestamps
    assert.throws(
      () => {
        validateProjectLock({
          schemaVersion: 1,
          release: '0.1.0',
          skills: {
            sigmabrief: {
              revision: 'hash_b',
              installedAt: '2026-08-16T00:00:00Z',
            },
          },
        });
      },
      /lock must not contain paths or timestamps/,
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('state: record, save, load, and check destination ownership', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-state-test-'));
  try {
    const initial = loadProjectState(tmpDir);
    assert.equal(initial.schemaVersion, 1);
    assert.equal(initial.scope, 'project');
    assert.deepEqual(initial.skills, {});

    const updated = recordSkillInState(initial, {
      skillId: 'sigmabrief',
      release: '0.1.0',
      revision: 'revision123',
      method: 'copy',
      destination: '.agents/skills/sigmabrief',
      projectRoot: tmpDir,
      ownedPaths: ['.agents/skills/sigmabrief/SKILL.md', '.agents/skills/sigmabrief/agents/openai.yaml'],
      baseHashes: {
        'SKILL.md': 'hash1',
        'agents/openai.yaml': 'hash2',
      },
    });

    saveProjectState(tmpDir, updated);

    const statePath = path.join(tmpDir, '.agents', STATE_FILENAME);
    assert.ok(fs.existsSync(statePath));

    const loaded = loadProjectState(tmpDir);
    assert.equal(loaded.skills.sigmabrief.revision, 'revision123');
    assert.equal(loaded.skills.sigmabrief.method, 'copy');
    assert.equal(loaded.skills.sigmabrief.ownedPaths.length, 2);
    assert.ok(loaded.skills.sigmabrief.installedAt);
    assert.ok(loaded.skills.sigmabrief.updatedAt);

    // Ownership check
    const destPath = path.join(tmpDir, '.agents', 'skills', 'sigmabrief');
    assert.ok(isDestinationOwned(tmpDir, 'sigmabrief', destPath));
    assert.ok(!isDestinationOwned(tmpDir, 'sigmawrite', path.join(tmpDir, '.agents', 'skills', 'sigmawrite')));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('plan: dry run produces accurate preview without mutating files', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-plan-test-'));
  try {
    const catalog = getCatalog(ROOT);
    const plan = createInstallPlan(catalog, {
      skillId: 'sigmawrite',
      projectRoot: tmpDir,
      dryRun: true,
    });

    assert.equal(plan.skill, 'sigmawrite');
    assert.equal(plan.scope, 'project');
    assert.equal(plan.method, 'copy');
    assert.equal(plan.unownedConflict, false);
    assert.equal(plan.writes.length, 2); // SKILL.md, agents/openai.yaml
    assert.equal(plan.replacements.length, 0);
    assert.equal(plan.lockChanges.action, 'add');

    const human = formatPlanHuman(plan);
    assert.match(human, /SigmaSkills Project Installation Plan: SigmaWrite/);
    assert.match(human, /Dry run complete/);

    const json = formatPlanJson(plan);
    const parsed = JSON.parse(json);
    assert.equal(parsed.skill, 'sigmawrite');

    // Verify no files were created during dry run
    assert.ok(!fs.existsSync(path.join(tmpDir, '.agents')));
    assert.ok(!fs.existsSync(path.join(tmpDir, PROJECT_LOCK_FILENAME)));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('install: installs skill transactionally into universal destination', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-install-test-'));
  try {
    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmabrief',
      projectRoot: tmpDir,
      packageRoot: ROOT,
    });

    assert.equal(result.success, true);
    assert.equal(result.dryRun, false);

    // Verify installed files at universal project destination
    const destDir = path.join(tmpDir, '.agents', 'skills', 'sigmabrief');
    assert.ok(fs.existsSync(destDir));
    assert.ok(fs.existsSync(path.join(destDir, 'SKILL.md')));
    assert.ok(fs.existsSync(path.join(destDir, 'agents', 'openai.yaml')));
    assert.ok(fs.existsSync(path.join(destDir, 'references', 'brief-method.md')));

    // Verify project lockfile
    const lock = loadProjectLock(tmpDir);
    assert.equal(lock.release, catalog.manifest.version);
    assert.equal(lock.skills.sigmabrief.revision, result.plan.sourceRevision);

    // Verify private state
    const state = loadProjectState(tmpDir);
    assert.equal(state.skills.sigmabrief.revision, result.plan.sourceRevision);
    assert.equal(state.skills.sigmabrief.method, 'copy');
    assert.equal(state.skills.sigmabrief.destination, '.agents/skills/sigmabrief');
    assert.ok(state.skills.sigmabrief.ownedPaths.length > 0);
    assert.ok(state.skills.sigmabrief.baseHashes['SKILL.md']);

    // Staging directory must be cleaned up
    const stagingDir = path.join(tmpDir, '.agents', '.sigma-staging');
    assert.ok(!fs.existsSync(stagingDir));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('install: fails closed on unowned existing destination', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-unowned-test-'));
  try {
    const catalog = getCatalog(ROOT);
    const foreignDir = path.join(tmpDir, '.agents', 'skills', 'sigmawrite');
    fs.mkdirSync(foreignDir, { recursive: true });
    fs.writeFileSync(path.join(foreignDir, 'SKILL.md'), 'foreign content', 'utf8');

    // Attempting install without ownership must fail closed
    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot: tmpDir,
          packageRoot: ROOT,
        });
      },
      /already exists and is not owned by SigmaSkills/,
    );

    // Verify foreign content remains untouched
    assert.equal(fs.readFileSync(path.join(foreignDir, 'SKILL.md'), 'utf8'), 'foreign content');
    // Verify no lockfile or state was written
    assert.ok(!fs.existsSync(path.join(tmpDir, PROJECT_LOCK_FILENAME)));
    assert.ok(!fs.existsSync(path.join(tmpDir, '.agents', STATE_FILENAME)));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('install: concurrency lock blocks parallel runs and cleans stale lock', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-lock-concurrency-'));
  try {
    // Acquire lock
    const release = acquireConcurrencyLock(tmpDir);

    // Second acquire in same process should fail because PID is alive
    assert.throws(
      () => {
        acquireConcurrencyLock(tmpDir);
      },
      /Concurrent SigmaSkills operation in progress/,
    );

    // Release lock
    release();

    // Now acquiring should succeed
    const release2 = acquireConcurrencyLock(tmpDir);
    release2();

    // Create a fake dead PID lock (PID 99999999)
    const lockPath = path.join(tmpDir, '.agents', '.sigma.lock');
    fs.writeFileSync(lockPath, JSON.stringify({ pid: 99999999, createdAt: new Date().toISOString() }), 'utf8');

    // Acquiring should detect dead PID, clear stale lock, and succeed
    const release3 = acquireConcurrencyLock(tmpDir);
    assert.ok(fs.existsSync(lockPath));
    release3();
    assert.ok(!fs.existsSync(lockPath));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('install: reinstalling owned skill updates files and lock smoothly', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-reinstall-test-'));
  try {
    const catalog = getCatalog(ROOT);

    // 1. Initial install
    executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot: tmpDir,
      packageRoot: ROOT,
    });

    const destDir = path.join(tmpDir, '.agents', 'skills', 'sigmawrite');
    assert.ok(fs.existsSync(path.join(destDir, 'SKILL.md')));

    // 2. Reinstall
    const result2 = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot: tmpDir,
      packageRoot: ROOT,
    });

    assert.equal(result2.success, true);
    assert.equal(result2.plan.replacements.length, 2);

    const lock = loadProjectLock(tmpDir);
    assert.ok(lock.skills.sigmawrite);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
