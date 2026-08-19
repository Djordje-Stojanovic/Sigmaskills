import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { BACKUP_METADATA_NAME, inventorySkillTree } from '../src/backup.js';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import { UNIVERSAL_PROJECT_DESTINATION, listProjectDestinationGroups, loadHostRegistry } from '../src/destinations.js';
import { pathExists } from '../src/links.js';
import { createRestorePlan, executeRestore } from '../src/restore.js';
import { getProjectStateDir } from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';
import { executeUpdate } from '../src/update.js';

const ROOT = findPackageRoot();

function createMockIo(env) {
  let stdout = '';
  let stderr = '';
  return {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    env,
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

function installWrite(projectRoot, skillId, extra = {}) {
  return executeProjectInstall({
    catalog: getCatalog(ROOT),
    skillId,
    projectRoot,
    packageRoot: ROOT,
    destinationGroups: listProjectDestinationGroups({
      registry: loadHostRegistry(ROOT),
      projectRoot,
      env: {},
    }),
    selectedRoots: extra.selectedRoots || [UNIVERSAL_PROJECT_DESTINATION],
    method: extra.method,
  });
}

function skillDir(root, skillId) {
  return path.join(root, '.agents', 'skills', skillId);
}

function readState(root) {
  return JSON.parse(fs.readFileSync(path.join(root, '.agents', 'state.json'), 'utf8'));
}

function backupAbs(root, skillId) {
  const rel = readState(root).skills[skillId].lastBackup;
  return path.join(getProjectStateDir(root), rel);
}

function replaceWithOutsideEdit(projectRoot, skillId, marker) {
  installWrite(projectRoot, skillId);
  const dest = skillDir(projectRoot, skillId);
  fs.writeFileSync(path.join(dest, 'local-keep.txt'), marker, 'utf8');
  executeUpdate({
    catalog: getCatalog(ROOT),
    projectRoot,
    packageRoot: ROOT,
    skillIds: [skillId],
    outsideEdit: 'replace',
  });
  return dest;
}

test('restore: dry-run preview names release, revision, date, size, scope, target, and links', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-preview-'));
  try {
    replaceWithOutsideEdit(projectRoot, 'sigmawrite', 'preview-bytes');
    const plan = createRestorePlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      dryRun: true,
    });
    const skill = plan.skills[0];
    assert.equal(skill.id, 'sigmawrite');
    assert.equal(plan.scope, 'project');
    assert.equal(skill.preview.scope, 'project');
    assert.ok(skill.preview.release);
    assert.match(skill.preview.revision, /^[a-f0-9]{64}$/);
    assert.ok(skill.preview.createdAt);
    assert.ok(skill.preview.sizeBytes > 0);
    assert.equal(skill.preview.canonicalTarget, '.agents/skills/sigmawrite');
    assert.ok(Array.isArray(skill.preview.links));
    assert.ok(Array.isArray(skill.preview.copies));

    const io = createMockIo();
    const code = await runCli(['restore', '--dry-run', '--skill', 'sigmawrite', '--project', projectRoot], io);
    assert.equal(code, 0);
    assert.match(io.getStdout(), /release/i);
    assert.match(io.getStdout(), /revision/i);
    assert.match(io.getStdout(), /sigmawrite/);
    assert.equal(pathExists(path.join(skillDir(projectRoot, 'sigmawrite'), 'local-keep.txt')), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('restore: success puts the prior live tree in the latest backup so restore can undo once', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-ok-'));
  try {
    const dest = replaceWithOutsideEdit(projectRoot, 'sigmawrite', 'from-backup');
    assert.equal(pathExists(path.join(dest, 'local-keep.txt')), false);
    const firstBackup = backupAbs(projectRoot, 'sigmawrite');
    assert.equal(fs.readFileSync(path.join(firstBackup, 'local-keep.txt'), 'utf8'), 'from-backup');

    const result = executeRestore({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      yes: true,
    });
    assert.equal(result.skills[0].action, 'restored');
    assert.equal(fs.readFileSync(path.join(dest, 'local-keep.txt'), 'utf8'), 'from-backup');
    assert.equal(pathExists(firstBackup), false);
    const undo = backupAbs(projectRoot, 'sigmawrite');
    assert.equal(pathExists(undo), true);
    assert.equal(pathExists(path.join(undo, 'local-keep.txt')), false);
    assert.equal(pathExists(path.join(undo, BACKUP_METADATA_NAME)), true);
    assert.equal(pathExists(path.join(dest, BACKUP_METADATA_NAME)), false);

    executeRestore({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      yes: true,
    });
    assert.equal(pathExists(path.join(dest, 'local-keep.txt')), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('restore: identical content is a no-op and does not rotate backups', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-noop-'));
  try {
    const dest = replaceWithOutsideEdit(projectRoot, 'sigmawrite', 'same-later');
    fs.writeFileSync(path.join(dest, 'local-keep.txt'), 'same-later', 'utf8');
    const lastBackup = readState(projectRoot).skills.sigmawrite.lastBackup;
    const kept = inventorySkillTree(backupAbs(projectRoot, 'sigmawrite'));

    const result = executeRestore({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      yes: true,
    });
    assert.equal(result.skills[0].action, 'no-op');
    assert.equal(readState(projectRoot).skills.sigmawrite.lastBackup, lastBackup);
    assert.deepEqual(inventorySkillTree(backupAbs(projectRoot, 'sigmawrite')).entries, kept.entries);
    assert.equal(fs.readFileSync(path.join(dest, 'local-keep.txt'), 'utf8'), 'same-later');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('restore: failure after staging leaves the live tree and retained backup intact', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-fail-'));
  try {
    const dest = replaceWithOutsideEdit(projectRoot, 'sigmawrite', 'keep-backup');
    const beforeLive = inventorySkillTree(dest);
    const beforeBackup = backupAbs(projectRoot, 'sigmawrite');
    const beforeBackupBytes = fs.readFileSync(path.join(beforeBackup, 'local-keep.txt'), 'utf8');
    const beforeState = fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8');

    assert.throws(
      () => executeRestore({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        yes: true,
        afterStage: () => {
          throw new Error('stage exploded');
        },
      }),
      /stage exploded/,
    );
    assert.deepEqual(inventorySkillTree(dest).entries, beforeLive.entries);
    assert.equal(fs.readFileSync(path.join(beforeBackup, 'local-keep.txt'), 'utf8'), beforeBackupBytes);
    assert.equal(fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8'), beforeState);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('restore: missing, truncated, tampered, schema-incompatible, insufficient-space, stale-ownership, occupied-unowned, and Windows-fallback stop safely', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-stop-'));
  try {
    const dest = replaceWithOutsideEdit(projectRoot, 'sigmawrite', 'guarded');
    const backup = backupAbs(projectRoot, 'sigmawrite');
    const liveBefore = fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8');
    const backupBefore = fs.readFileSync(path.join(backup, 'local-keep.txt'), 'utf8');

    const missingRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-missing-'));
    try {
      installWrite(missingRoot, 'sigmawrite');
      assert.throws(
        () => executeRestore({
          catalog: getCatalog(ROOT),
          projectRoot: missingRoot,
          packageRoot: ROOT,
          skillIds: ['sigmawrite'],
          yes: true,
        }),
        /missing/,
      );
    } finally {
      fs.rmSync(missingRoot, { recursive: true, force: true });
    }

    const metaPath = path.join(backup, BACKUP_METADATA_NAME);
    const originalMeta = fs.readFileSync(metaPath, 'utf8');

    fs.unlinkSync(path.join(backup, 'local-keep.txt'));
    assert.throws(
      () => executeRestore({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        yes: true,
      }),
      /truncated/,
    );
    fs.writeFileSync(path.join(backup, 'local-keep.txt'), backupBefore, 'utf8');

    fs.writeFileSync(path.join(backup, 'local-keep.txt'), 'tampered', 'utf8');
    assert.throws(
      () => executeRestore({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        yes: true,
      }),
      /tampered/,
    );
    fs.writeFileSync(path.join(backup, 'local-keep.txt'), backupBefore, 'utf8');

    const parsed = JSON.parse(originalMeta);
    fs.writeFileSync(metaPath, `${JSON.stringify({ ...parsed, schemaVersion: 99 }, null, 2)}\n`);
    assert.throws(
      () => executeRestore({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        yes: true,
      }),
      /schema/,
    );
    fs.writeFileSync(metaPath, originalMeta);

    assert.throws(
      () => executeRestore({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        yes: true,
        statfs: () => ({ bavail: 0, bsize: 4096 }),
      }),
      /insufficient space|space/,
    );

    const staleMeta = JSON.parse(originalMeta);
    staleMeta.ownedPaths = ['.agents/skills/sigmabrief'];
    staleMeta.copies = [{ kind: 'canonical', destination: '.agents/skills/sigmabrief', hostIds: [], ownedPaths: ['.agents/skills/sigmabrief'] }];
    fs.writeFileSync(metaPath, `${JSON.stringify(staleMeta, null, 2)}\n`);
    installWrite(projectRoot, 'sigmabrief');
    assert.throws(
      () => executeRestore({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        yes: true,
      }),
      /stale ownership|stale-ownership/,
    );
    fs.writeFileSync(metaPath, originalMeta);

    const occupiedRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-occ-'));
    try {
      replaceWithOutsideEdit(occupiedRoot, 'sigmawrite', 'occupied');
      const occupiedDest = skillDir(occupiedRoot, 'sigmawrite');
      const occupiedBackup = backupAbs(occupiedRoot, 'sigmawrite');
      fs.rmSync(occupiedDest, { recursive: true, force: true });
      const state = readState(occupiedRoot);
      delete state.skills.sigmawrite;
      fs.writeFileSync(path.join(occupiedRoot, '.agents', 'state.json'), `${JSON.stringify(state, null, 2)}\n`);
      fs.mkdirSync(occupiedDest, { recursive: true });
      fs.writeFileSync(path.join(occupiedDest, 'stranger.txt'), 'not yours', 'utf8');
      assert.throws(
        () => executeRestore({
          catalog: getCatalog(ROOT),
          projectRoot: occupiedRoot,
          packageRoot: ROOT,
          skillIds: ['sigmawrite'],
          yes: true,
        }),
        /unowned|occupied/,
      );
      assert.equal(fs.readFileSync(path.join(occupiedDest, 'stranger.txt'), 'utf8'), 'not yours');
      assert.equal(pathExists(occupiedBackup), true);
    } finally {
      fs.rmSync(occupiedRoot, { recursive: true, force: true });
    }

    assert.throws(
      () => executeRestore({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        yes: true,
        renameDirectory: () => {
          const err = new Error('EPERM: rename blocked');
          err.code = 'EPERM';
          throw err;
        },
        copyDirectory: () => {
          const err = new Error('Windows fallback failed');
          err.code = 'EPERM';
          throw err;
        },
      }),
      /Windows fallback|EPERM|fallback/,
    );

    assert.equal(fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8'), liveBefore);
    assert.equal(fs.readFileSync(path.join(backup, 'local-keep.txt'), 'utf8'), backupBefore);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('restore: a removed skill returns from portable ownership metadata without claiming unrelated paths', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-restore-removed-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    const dest = skillDir(projectRoot, 'sigmawrite');
    fs.writeFileSync(path.join(dest, 'local-keep.txt'), 'removed-skill', 'utf8');
    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      outsideEdit: 'replace',
    });
    const backup = backupAbs(projectRoot, 'sigmawrite');
    fs.rmSync(dest, { recursive: true, force: true });
    const state = readState(projectRoot);
    delete state.skills.sigmawrite;
    fs.writeFileSync(path.join(projectRoot, '.agents', 'state.json'), `${JSON.stringify(state, null, 2)}\n`);

    const stranger = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    fs.mkdirSync(stranger, { recursive: true });
    fs.writeFileSync(path.join(stranger, 'leave-me.txt'), 'unrelated', 'utf8');

    executeRestore({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      yes: true,
    });
    assert.equal(fs.readFileSync(path.join(dest, 'local-keep.txt'), 'utf8'), 'removed-skill');
    assert.equal(fs.readFileSync(path.join(stranger, 'leave-me.txt'), 'utf8'), 'unrelated');
    assert.equal(readState(projectRoot).skills.sigmabrief.destination, '.agents/skills/sigmabrief');
    assert.equal(pathExists(backup), true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI restores adoption and update backups', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-restore-'));
  try {
    const packOutput = execSync(`npm pack --pack-destination "${tmpDir}"`, {
      cwd: ROOT,
      encoding: 'utf8',
    }).trim();
    const tarballFileName = packOutput.split(/\r?\n/).pop()?.trim();
    const tarballPath = path.join(tmpDir, tarballFileName);
    const appDir = path.join(tmpDir, 'test-app');
    fs.mkdirSync(appDir, { recursive: true });
    execSync('npm init -y', { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    execSync(`npm install "${tarballPath}"`, { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    const installedBin = path.join(appDir, 'node_modules', 'sigmaskills', 'bin', 'sigmaskills.js');
    const packedRoot = path.join(appDir, 'node_modules', 'sigmaskills');

    const adoptProject = path.join(tmpDir, 'adopt');
    const adoptDest = path.join(adoptProject, '.agents', 'skills', 'sigmawrite');
    fs.mkdirSync(path.dirname(adoptDest), { recursive: true });
    fs.cpSync(path.join(packedRoot, 'sigmawrite'), adoptDest, { recursive: true });
    fs.writeFileSync(path.join(adoptDest, 'extra.md'), 'packed extra', 'utf8');
    execFileSync(
      'node',
      [installedBin, 'install', 'sigmawrite', '--project', adoptProject, '--adopt-unverified', 'replace'],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(pathExists(path.join(adoptDest, 'extra.md')), false);
    execFileSync(
      'node',
      [installedBin, 'restore', '--skill', 'sigmawrite', '--yes', '--project', adoptProject],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(fs.readFileSync(path.join(adoptDest, 'extra.md'), 'utf8'), 'packed extra');

    const updateProject = path.join(tmpDir, 'update');
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', updateProject], {
      cwd: appDir,
      encoding: 'utf8',
    });
    const updateDest = path.join(updateProject, '.agents', 'skills', 'sigmawrite');
    fs.writeFileSync(path.join(updateDest, 'notes.txt'), 'from-update-backup', 'utf8');
    execFileSync(
      'node',
      [installedBin, 'update', '--skill', 'sigmawrite', '--outside-edit', 'replace', '--project', updateProject],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(pathExists(path.join(updateDest, 'notes.txt')), false);
    execFileSync(
      'node',
      [installedBin, 'restore', '--skill', 'sigmawrite', '--yes', '--project', updateProject],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(fs.readFileSync(path.join(updateDest, 'notes.txt'), 'utf8'), 'from-update-backup');
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
