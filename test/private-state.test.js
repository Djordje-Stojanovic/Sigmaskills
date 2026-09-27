import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  listProjectDestinationGroups,
  loadHostRegistry,
} from '../src/destinations.js';
import { verifyBackupIntegrity } from '../src/backup.js';
import { pathExists } from '../src/links.js';
import { executePurge, PURGE_CONFIRMATION_PHRASE } from '../src/purge.js';
import { executeRestore } from '../src/restore.js';
import {
  collectStatus,
} from '../src/status.js';
import {
  getGlobalStateDir,
  getProjectStateDir,
  LEGACY_MIGRATION_MARKER,
  migrateLegacyState,
  migrateStateForCommand,
  PRIVATE_STATE_DIRNAME,
} from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';
import { executeUninstall } from '../src/uninstall.js';
import { executeUpdate } from '../src/update.js';

const ROOT = findPackageRoot();

function installWrite(projectRoot, skillId) {
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
    selectedRoots: [UNIVERSAL_PROJECT_DESTINATION],
  });
}

function skillDir(root, skillId) {
  return path.join(root, ...UNIVERSAL_PROJECT_DESTINATION.split('/'), skillId);
}

function forceBackup(projectRoot, skillId, text) {
  fs.writeFileSync(path.join(skillDir(projectRoot, skillId), 'local-keep.txt'), text, 'utf8');
  executeUpdate({
    catalog: getCatalog(ROOT),
    projectRoot,
    packageRoot: ROOT,
    skillIds: [skillId],
    outsideEdit: 'replace',
  });
}

function stagedPaths(projectRoot) {
  execFileSync('git', ['init', '-q'], { cwd: projectRoot });
  execFileSync('git', ['add', '-A'], { cwd: projectRoot });
  return execFileSync('git', ['diff', '--cached', '--name-only'], { cwd: projectRoot, encoding: 'utf8' })
    .split(/\r?\n/)
    .filter(Boolean);
}

// Turn a current-layout project back into the 0.3.0/0.4.0 layout: private files straight in .agents/.
function toLegacyLayout(base) {
  const legacyDir = path.join(base, '.agents');
  const stateDir = path.join(legacyDir, PRIVATE_STATE_DIRNAME);
  for (const name of fs.readdirSync(stateDir)) {
    if (name === '.gitignore') continue;
    fs.renameSync(path.join(stateDir, name), path.join(legacyDir, name));
  }
  fs.rmSync(stateDir, { recursive: true, force: true });
}

function ownership(projectRoot) {
  const report = collectStatus({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT, env: {} });
  return JSON.stringify(report.skills ?? report);
}

test('private state: git add -A after install and backup stages only skills and skills-lock.json', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-git-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    forceBackup(projectRoot, 'sigmawrite', 'first-edit');
    fs.writeFileSync(path.join(skillDir(projectRoot, 'sigmabrief'), 'mine.txt'), 'edit', 'utf8');
    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmabrief'],
      changed: 'backup',
    });

    const stateDir = getProjectStateDir(projectRoot);
    assert.equal(stateDir, path.join(projectRoot, '.agents', PRIVATE_STATE_DIRNAME));
    assert.ok(pathExists(path.join(stateDir, 'state.json')));
    assert.ok(fs.readdirSync(path.join(stateDir, 'backups')).includes('sigmabrief'));

    const staged = stagedPaths(projectRoot);
    assert.ok(staged.length > 0);
    for (const file of staged) {
      assert.ok(
        file === 'skills-lock.json' || file.startsWith('.agents/skills/'),
        `unexpected staged file ${file}`,
      );
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: global state lives in its own ignored folder too', () => {
  const homeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-home-'));
  try {
    assert.equal(getGlobalStateDir(homeDir), path.join(homeDir, '.agents', PRIVATE_STATE_DIRNAME));
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('private state: old-layout project migrates on the next command with ownership and backups intact', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-migrate-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    forceBackup(projectRoot, 'sigmawrite', 'old-backup');
    const before = ownership(projectRoot);
    toLegacyLayout(projectRoot);
    assert.ok(pathExists(path.join(projectRoot, '.agents', 'state.json')));

    // status is read-only: it reads the old layout in place and moves nothing.
    assert.equal(ownership(projectRoot), before);
    assert.ok(pathExists(path.join(projectRoot, '.agents', 'state.json')));
    assert.equal(pathExists(path.join(projectRoot, '.agents', PRIVATE_STATE_DIRNAME)), false);

    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      clean: 'remove',
    });
    const stateDir = getProjectStateDir(projectRoot);
    assert.equal(stateDir, path.join(projectRoot, '.agents', PRIVATE_STATE_DIRNAME));
    assert.ok(pathExists(path.join(stateDir, 'state.json')));
    assert.ok(pathExists(path.join(stateDir, '.gitignore')));
    assert.equal(pathExists(path.join(stateDir, LEGACY_MIGRATION_MARKER)), false);
    for (const name of ['state.json', 'backups', '.sigma.lock']) {
      assert.equal(pathExists(path.join(projectRoot, '.agents', name)), false, `${name} left behind`);
    }
    const restored = executeRestore({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
    });
    assert.equal(restored.skills[0].action, 'restored');
    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'local-keep.txt'), 'utf8'), 'old-backup');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: a crash before the commit rename leaves the old layout; the next run migrates', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-crash-before-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const before = ownership(projectRoot);
    toLegacyLayout(projectRoot);
    const legacyDir = path.join(projectRoot, '.agents');
    const newDir = path.join(legacyDir, PRIVATE_STATE_DIRNAME);
    const legacyState = fs.readFileSync(path.join(legacyDir, 'state.json'), 'utf8');

    assert.throws(
      () => migrateLegacyState(legacyDir, newDir, { beforeCommit: () => { throw new Error('crash'); } }),
      /crash/,
    );
    assert.equal(pathExists(newDir), false);
    assert.equal(fs.readFileSync(path.join(legacyDir, 'state.json'), 'utf8'), legacyState);

    assert.equal(ownership(projectRoot), before);
    migrateStateForCommand({ projectRoot });
    assert.equal(ownership(projectRoot), before);
    assert.equal(pathExists(path.join(legacyDir, 'state.json')), false);
    assert.equal(fs.readdirSync(legacyDir).filter((name) => name !== 'skills' && name !== PRIVATE_STATE_DIRNAME).length, 0);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: a crash after the commit rename uses the new layout and finishes cleanup', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-crash-after-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const before = ownership(projectRoot);
    toLegacyLayout(projectRoot);
    const legacyDir = path.join(projectRoot, '.agents');
    const newDir = path.join(legacyDir, PRIVATE_STATE_DIRNAME);

    assert.throws(
      () => migrateLegacyState(legacyDir, newDir, { afterCommit: () => { throw new Error('crash'); } }),
      /crash/,
    );
    assert.ok(pathExists(path.join(newDir, 'state.json')));
    assert.ok(pathExists(path.join(newDir, LEGACY_MIGRATION_MARKER)));

    assert.equal(ownership(projectRoot), before);
    migrateStateForCommand({ projectRoot });
    assert.equal(pathExists(path.join(legacyDir, 'state.json')), false);
    assert.equal(pathExists(path.join(newDir, LEGACY_MIGRATION_MARKER)), false);
    assert.equal(ownership(projectRoot), before);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: an interrupted old-layout uninstall journal stops migration with a clear next step', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-journal-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    toLegacyLayout(projectRoot);
    const legacyDir = path.join(projectRoot, '.agents');
    fs.writeFileSync(path.join(legacyDir, 'uninstall-journal.json'), '{"status":"in-progress"}', 'utf8');
    assert.equal(getProjectStateDir(projectRoot), legacyDir);
    assert.throws(() => migrateStateForCommand({ projectRoot }), /uninstall-journal\.json.*0\.4\.0/s);
    assert.ok(pathExists(path.join(legacyDir, 'state.json')));
    assert.equal(pathExists(path.join(legacyDir, PRIVATE_STATE_DIRNAME)), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: purge removes the private folder; uninstall-all leaves only kept backups and state', () => {
  const purgeRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-purge-'));
  try {
    installWrite(purgeRoot, 'sigmawrite');
    forceBackup(purgeRoot, 'sigmawrite', 'x');
    executePurge({
      catalog: getCatalog(ROOT),
      projectRoot: purgeRoot,
      packageRoot: ROOT,
      confirmPurge: PURGE_CONFIRMATION_PHRASE,
    });
    assert.equal(pathExists(path.join(purgeRoot, '.agents', PRIVATE_STATE_DIRNAME)), false);
  } finally {
    fs.rmSync(purgeRoot, { recursive: true, force: true });
  }

  const allRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-all-'));
  try {
    installWrite(allRoot, 'sigmawrite');
    installWrite(allRoot, 'sigmabrief');
    fs.writeFileSync(path.join(skillDir(allRoot, 'sigmawrite'), 'mine.txt'), 'keep', 'utf8');
    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot: allRoot,
      packageRoot: ROOT,
      all: true,
      yes: true,
      clean: 'remove',
      changed: 'backup',
    });
    const stateDir = getProjectStateDir(allRoot);
    assert.deepEqual(fs.readdirSync(stateDir).sort(), ['.gitignore', 'backups', 'state.json']);
    assert.deepEqual(fs.readdirSync(path.join(allRoot, '.agents')).filter((name) => name !== 'skills'), [PRIVATE_STATE_DIRNAME]);
  } finally {
    fs.rmSync(allRoot, { recursive: true, force: true });
  }
});

test('private state: migration keeps links inside old backups as links', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-link-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const outside = path.join(projectRoot, 'outside');
    fs.mkdirSync(outside);
    fs.writeFileSync(path.join(outside, 'big.txt'), 'not part of the backup', 'utf8');
    fs.symlinkSync(outside, path.join(skillDir(projectRoot, 'sigmawrite'), 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
    forceBackup(projectRoot, 'sigmawrite', 'old-backup');
    toLegacyLayout(projectRoot);

    migrateStateForCommand({ projectRoot });

    const backupRoot = path.join(getProjectStateDir(projectRoot), 'backups', 'sigmawrite');
    const [stamp] = fs.readdirSync(backupRoot);
    assert.ok(fs.lstatSync(path.join(backupRoot, stamp, 'linked')).isSymbolicLink(), 'link became a plain folder');
    verifyBackupIntegrity({ backupDir: path.join(backupRoot, stamp), skillId: 'sigmawrite' });
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: a second process cannot migrate while the first one is mid-migration', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-race-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    forceBackup(projectRoot, 'sigmawrite', 'old-backup');
    const before = ownership(projectRoot);
    toLegacyLayout(projectRoot);
    const legacyDir = path.join(projectRoot, '.agents');
    const newDir = path.join(legacyDir, PRIVATE_STATE_DIRNAME);
    const stateModule = new URL('../src/state.js', import.meta.url).href;
    const script = `import { migrateLegacyState } from ${JSON.stringify(stateModule)};
      migrateLegacyState(${JSON.stringify(legacyDir)}, ${JSON.stringify(newDir)});`;

    let second;
    migrateLegacyState(legacyDir, newDir, {
      beforeCommit: () => {
        try {
          execFileSync(process.execPath, ['--input-type=module', '-e', script], { stdio: 'pipe' });
          second = 'migrated';
        } catch (err) {
          second = String(err.stderr);
        }
      },
    });

    assert.match(second, /another SigmaSkills run holds/);
    assert.equal(ownership(projectRoot), before);
    assert.equal(pathExists(path.join(legacyDir, '.sigma.lock')), false);
    assert.equal(pathExists(path.join(newDir, LEGACY_MIGRATION_MARKER)), false);
    assert.ok(fs.readdirSync(path.join(newDir, 'backups')).includes('sigmawrite'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: uninstall-all with no kept backups removes the private folder', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-all-clean-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      all: true,
      yes: true,
      clean: 'remove',
    });
    assert.equal(pathExists(path.join(projectRoot, '.agents', PRIVATE_STATE_DIRNAME)), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: purge keeps a --state-dir folder the user made', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-custom-'));
  const customStateDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-custom-state-'));
  try {
    executePurge({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      customStateDir,
      confirmPurge: PURGE_CONFIRMATION_PHRASE,
    });
    assert.ok(pathExists(customStateDir));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(customStateDir, { recursive: true, force: true });
  }
});

test('private state: a cancelled or unconfirmed purge does not migrate an old-layout project', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-purge-cancel-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    toLegacyLayout(projectRoot);
    const legacyDir = path.join(projectRoot, '.agents');
    for (const confirmPurge of [undefined, '', 'wrong phrase']) {
      assert.throws(() => executePurge({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        confirmPurge,
      }));
      assert.ok(pathExists(path.join(legacyDir, 'state.json')));
      assert.equal(pathExists(path.join(legacyDir, PRIVATE_STATE_DIRNAME)), false);
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: a private folder left without its ignore file by a crash is ignored again', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-no-ignore-'));
  try {
    // A crash between creating the folder and writing its .gitignore leaves an empty folder.
    fs.mkdirSync(path.join(projectRoot, '.agents', PRIVATE_STATE_DIRNAME), { recursive: true });
    installWrite(projectRoot, 'sigmawrite');
    for (const file of stagedPaths(projectRoot)) {
      assert.ok(
        file === 'skills-lock.json' || file.startsWith('.agents/skills/'),
        `unexpected staged file ${file}`,
      );
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: purge removes state.json temp files left by a crashed save', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-private-tmp-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    fs.writeFileSync(path.join(getProjectStateDir(projectRoot), 'state.json.tmp.123.456'), '{}', 'utf8');
    executePurge({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      confirmPurge: PURGE_CONFIRMATION_PHRASE,
    });
    assert.equal(pathExists(path.join(projectRoot, '.agents', PRIVATE_STATE_DIRNAME)), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('private state: recovery after process exit at migration commit removes the legacy lock', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-migration-exit-'));
  try {
    installWrite(root, 'sigmawrite');
    toLegacyLayout(root);
    const legacy = path.join(root, '.agents');
    const next = path.join(legacy, PRIVATE_STATE_DIRNAME);
    const script = `import { migrateLegacyState } from ${JSON.stringify(new URL('../src/state.js', import.meta.url).href)};
      migrateLegacyState(${JSON.stringify(legacy)}, ${JSON.stringify(next)}, { afterCommit: () => process.exit(0) });`;
    execFileSync(process.execPath, ['--input-type=module', '-e', script]);
    assert.ok(fs.existsSync(path.join(legacy, '.sigma.lock')));
    migrateStateForCommand({ projectRoot: root });
    assert.equal(fs.existsSync(path.join(legacy, '.sigma.lock')), false);
    assert.equal(fs.existsSync(path.join(next, LEGACY_MIGRATION_MARKER)), false);
    assert.ok(fs.existsSync(path.join(next, 'state.json')));
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
