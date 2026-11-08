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
import { pathExists } from '../src/links.js';
import { executePurge, PURGE_CONFIRMATION_PHRASE } from '../src/purge.js';
import {
} from '../src/status.js';
import {
  getGlobalStateDir,
  getProjectStateDir,
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
