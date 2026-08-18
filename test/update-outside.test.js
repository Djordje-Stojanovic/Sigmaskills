import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import { UNIVERSAL_PROJECT_DESTINATION, listProjectDestinationGroups, loadHostRegistry } from '../src/destinations.js';
import { pathExists } from '../src/links.js';
import { getProjectStateDir } from '../src/state.js';
import { computeSkillRevisionAndHashes } from '../src/revision.js';
import { executeProjectInstall } from '../src/transaction.js';
import { exportSkillTree, inventorySkillTree } from '../src/backup.js';
import { createUpdatePlan, executeUpdate } from '../src/update.js';

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
  return path.join(root, '.agents', 'skills', skillId);
}

function readState(root) {
  return JSON.parse(fs.readFileSync(path.join(root, '.agents', 'state.json'), 'utf8'));
}

function plantPriorBackup(root, skillId, marker) {
  const stateDir = getProjectStateDir(root);
  const stamp = '2020-01-01T00-00-00-000Z';
  const backupDir = path.join(stateDir, 'backups', skillId, stamp);
  fs.mkdirSync(backupDir, { recursive: true });
  fs.writeFileSync(path.join(backupDir, 'prior.txt'), marker, 'utf8');
  const state = readState(root);
  state.skills[skillId].lastBackup = `backups/${skillId}/${stamp}`;
  fs.writeFileSync(path.join(root, '.agents', 'state.json'), `${JSON.stringify(state, null, 2)}\n`);
  return backupDir;
}

function applyOutsideEdits(dest) {
  fs.writeFileSync(path.join(dest, 'notes.txt'), 'local text\n', 'utf8');
  fs.writeFileSync(path.join(dest, 'blob.bin'), Buffer.from([0, 1, 2, 255]));
  fs.writeFileSync(path.join(dest, '.hidden'), 'secret', 'utf8');
  const skillMd = path.join(dest, 'SKILL.md');
  fs.writeFileSync(
    skillMd,
    fs.readFileSync(skillMd, 'utf8').replace(
      '## Personal instructions',
      'outside-body\n\n## Personal instructions',
    ),
    'utf8',
  );
  const yamlPath = path.join(dest, 'agents', 'openai.yaml');
  fs.copyFileSync(yamlPath, path.join(dest, 'agents', 'renamed.yaml'));
  fs.unlinkSync(yamlPath);
  fs.mkdirSync(yamlPath);
  fs.writeFileSync(path.join(yamlPath, 'nested.yaml'), 'now-a-dir\n', 'utf8');
  const escapeTarget = path.join(path.dirname(dest), '..', 'escape-target');
  fs.mkdirSync(escapeTarget, { recursive: true });
  fs.writeFileSync(path.join(escapeTarget, 'secret.txt'), 'should-not-follow', 'utf8');
  const linkPath = path.join(dest, 'escape-link');
  fs.symlinkSync(escapeTarget, linkPath, process.platform === 'win32' ? 'junction' : 'dir');
}

test('update: outside-edit inventory covers add/replace/delete/rename/hidden/type-change/symlink', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-detect-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    applyOutsideEdits(skillDir(projectRoot, 'sigmawrite'));
    const inventory = inventorySkillTree(skillDir(projectRoot, 'sigmawrite'));
    assert.equal(inventory.entries['notes.txt'].kind, 'file');
    assert.equal(inventory.entries['blob.bin'].binary, true);
    assert.equal(inventory.entries['.hidden'].kind, 'file');
    assert.equal(inventory.entries['agents/renamed.yaml'].kind, 'file');
    assert.equal(inventory.entries['agents/openai.yaml'].kind, 'directory');
    assert.equal(inventory.entries['escape-link'].kind, 'symlink');
    assert.equal(inventory.entries['escape-link'].escaped, true);
    assert.equal(
      Object.values(inventory.entries).some((entry) => entry.hash && entry.kind === 'file' && entry.hash.includes('should-not-follow')),
      false,
    );

    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    const skill = plan.skills.find((item) => item.id === 'sigmawrite');
    assert.equal(skill.changeKind, 'local-only');
    assert.ok(skill.effects.added.includes('notes.txt'));
    assert.ok(skill.effects.added.includes('blob.bin'));
    assert.ok(skill.effects.added.includes('.hidden'));
    assert.ok(skill.effects.replaced.includes('SKILL.md'));
    assert.ok(skill.effects.renames.some((rename) => rename.from === 'agents/openai.yaml' && rename.to === 'agents/renamed.yaml'));
    assert.ok(skill.effects.typeChanges.some((change) => change.path === 'agents/openai.yaml'));
    assert.ok(skill.effects.symlinks.some((link) => link.path === 'escape-link' && link.escaped));
    assert.match(plan.prompt, /local-only/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: prompts distinguish local-only, upstream-only, and concurrent changes', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-kinds-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    installWrite(projectRoot, 'sigmareview');

    applyOutsideEdits(skillDir(projectRoot, 'sigmawrite'));

    const briefMd = path.join(skillDir(projectRoot, 'sigmabrief'), 'SKILL.md');
    fs.writeFileSync(
      briefMd,
      fs.readFileSync(briefMd, 'utf8').replace('## Personal instructions', '<!-- sigma-older -->\n\n## Personal instructions'),
      'utf8',
    );
    const hashes = JSON.parse(fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8'));
    const briefLive = computeSkillRevisionAndHashes(skillDir(projectRoot, 'sigmabrief'));
    hashes.skills.sigmabrief.baseHashes = briefLive.files;
    hashes.skills.sigmabrief.revision = briefLive.revision;
    hashes.skills.sigmabrief.release = '0.0.9';

    const reviewMd = path.join(skillDir(projectRoot, 'sigmareview'), 'SKILL.md');
    fs.writeFileSync(
      reviewMd,
      fs.readFileSync(reviewMd, 'utf8').replace(
        '## Personal instructions',
        '<!-- sigma-older -->\n\n## Personal instructions',
      ),
      'utf8',
    );
    const reviewBase = computeSkillRevisionAndHashes(skillDir(projectRoot, 'sigmareview'));
    hashes.skills.sigmareview.baseHashes = reviewBase.files;
    hashes.skills.sigmareview.revision = reviewBase.revision;
    hashes.skills.sigmareview.release = '0.0.9';
    fs.writeFileSync(path.join(projectRoot, '.agents', 'state.json'), `${JSON.stringify(hashes, null, 2)}\n`);
    applyOutsideEdits(skillDir(projectRoot, 'sigmareview'));

    const io = createMockIo();
    const code = await runCli(['update', '--dry-run', '--project', projectRoot], io);
    assert.equal(code, 0);
    assert.match(io.getStdout(), /local-only/);
    assert.match(io.getStdout(), /upstream-only/);
    assert.match(io.getStdout(), /concurrent/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: replace shows overwrite effects, verifies backup integrity, and keeps only the new backup after commit', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-replace-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    applyOutsideEdits(dest);
    const prior = plantPriorBackup(projectRoot, 'sigmawrite', 'keep-until-commit');
    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    const skill = plan.skills.find((item) => item.id === 'sigmawrite');
    assert.ok(skill.effects.overwrite.length + skill.effects.delete.length > 0);
    assert.equal(skill.backup.required, true);

    const result = executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      outsideEdit: 'replace',
    });
    assert.ok(result.results[0].backupIntegrity.ok);
    assert.equal(pathExists(prior), false);
    const state = readState(projectRoot);
    const backupRel = state.skills.sigmawrite.lastBackup;
    assert.ok(backupRel);
    const backupAbs = path.join(getProjectStateDir(projectRoot), backupRel);
    assert.equal(pathExists(backupAbs), true);
    const backupInventory = inventorySkillTree(backupAbs);
    assert.equal(backupInventory.entries['notes.txt'].kind, 'file');
    assert.equal(pathExists(path.join(dest, 'notes.txt')), false);
    assert.equal(state.skills.sigmawrite.cleanupDebt, undefined);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: skip leaves that skill unchanged while another skill still updates', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-skip-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    applyOutsideEdits(skillDir(projectRoot, 'sigmawrite'));
    const briefMd = path.join(skillDir(projectRoot, 'sigmabrief'), 'SKILL.md');
    const originalBrief = fs.readFileSync(briefMd, 'utf8');
    fs.writeFileSync(
      briefMd,
      originalBrief.replace('## Personal instructions', '<!-- sigma-older -->\n\n## Personal instructions'),
      'utf8',
    );
    const briefLive = computeSkillRevisionAndHashes(skillDir(projectRoot, 'sigmabrief'));
    const state = readState(projectRoot);
    state.skills.sigmabrief.baseHashes = briefLive.files;
    state.skills.sigmabrief.revision = briefLive.revision;
    fs.writeFileSync(path.join(projectRoot, '.agents', 'state.json'), `${JSON.stringify(state, null, 2)}\n`);
    const writeNotes = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'notes.txt'), 'utf8');
    const writeStateBefore = JSON.stringify(readState(projectRoot).skills.sigmawrite);

    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      outsideEdit: 'skip',
      yes: true,
    });

    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'notes.txt'), 'utf8'), writeNotes);
    assert.equal(JSON.stringify(readState(projectRoot).skills.sigmawrite), writeStateBefore);
    assert.equal(fs.readFileSync(briefMd, 'utf8').includes('<!-- sigma-older -->'), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: export uses a planned path, refuses collisions, supports dry-run JSON, and cleans partial output', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-export-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    applyOutsideEdits(skillDir(projectRoot, 'sigmawrite'));
    const exportRoot = path.join(projectRoot, 'exports');
    const planned = path.join(exportRoot, 'sigmawrite');
    const dry = createUpdatePlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      exportDir: exportRoot,
    });
    const skill = dry.skills.find((item) => item.id === 'sigmawrite');
    assert.equal(path.resolve(skill.exportPath), path.resolve(planned));
    assert.equal(skill.exportCollision, false);

    const io = createMockIo();
    const dryCode = await runCli(
      ['update', '--dry-run', '--json', '--outside-edit', 'export', '--export-dir', exportRoot, '--project', projectRoot],
      io,
    );
    assert.equal(dryCode, 0);
    const payload = JSON.parse(io.getStdout());
    assert.equal(pathExists(planned), false);
    assert.ok(payload.skills.some((item) => item.id === 'sigmawrite' && item.exportPath));

    fs.mkdirSync(planned, { recursive: true });
    fs.writeFileSync(path.join(planned, 'keep.txt'), 'existing', 'utf8');
    assert.throws(
      () => exportSkillTree({
        sourceDir: skillDir(projectRoot, 'sigmawrite'),
        exportRoot,
        skillId: 'sigmawrite',
        dest: planned,
        refuseCollision: true,
      }),
      /collision/,
    );
    assert.equal(fs.readFileSync(path.join(planned, 'keep.txt'), 'utf8'), 'existing');

    assert.throws(
      () => exportSkillTree({
        sourceDir: skillDir(projectRoot, 'sigmawrite'),
        exportRoot,
        skillId: 'sigmawrite',
        dest: path.join(exportRoot, 'partial'),
        copyFn: (from, to) => {
          fs.mkdirSync(to, { recursive: true });
          fs.writeFileSync(path.join(to, 'half.txt'), 'x', 'utf8');
          throw new Error('copy exploded');
        },
      }),
      /copy exploded/,
    );
    assert.equal(pathExists(path.join(exportRoot, 'partial')), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: cleanup failure keeps two backups and records cleanup debt', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-debt-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    applyOutsideEdits(skillDir(projectRoot, 'sigmawrite'));
    const prior = plantPriorBackup(projectRoot, 'sigmawrite', 'old-backup');
    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      outsideEdit: 'replace',
      pruneBackups: () => {
        throw new Error('cannot prune');
      },
    });
    assert.equal(pathExists(prior), true);
    const state = readState(projectRoot);
    assert.ok(state.skills.sigmawrite.lastBackup);
    assert.ok(Array.isArray(state.skills.sigmawrite.cleanupDebt));
    assert.ok(state.skills.sigmawrite.cleanupDebt.length >= 1);
    const newest = path.join(getProjectStateDir(projectRoot), state.skills.sigmawrite.lastBackup);
    assert.equal(pathExists(newest), true);
    assert.notEqual(path.resolve(newest), path.resolve(prior));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: failure injection keeps the live tree, prior backup, and ownership state', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-fail-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    applyOutsideEdits(dest);
    const prior = plantPriorBackup(projectRoot, 'sigmawrite', 'owned-prior');
    const beforeNotes = fs.readFileSync(path.join(dest, 'notes.txt'));
    const beforeState = fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'));

    assert.throws(
      () => executeUpdate({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        outsideEdit: 'replace',
        afterBackup: () => {
          throw new Error('fail after backup');
        },
      }),
      /fail after backup/,
    );
    assert.deepEqual(fs.readFileSync(path.join(dest, 'notes.txt')), beforeNotes);
    assert.equal(fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8'), beforeState.toString('utf8'));
    assert.equal(pathExists(prior), true);

    assert.throws(
      () => executeUpdate({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        outsideEdit: 'replace',
        saveState: () => {
          throw new Error('fail after state');
        },
      }),
      /fail after state/,
    );
    assert.deepEqual(fs.readFileSync(path.join(dest, 'notes.txt')), beforeNotes);
    assert.equal(fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8'), beforeState.toString('utf8'));
    assert.equal(pathExists(prior), true);
    assert.equal(fs.readFileSync(path.join(prior, 'prior.txt'), 'utf8'), 'owned-prior');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('cli: --yes without --outside-edit does not mutate local-only edits', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-outside-yes-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    applyOutsideEdits(skillDir(projectRoot, 'sigmawrite'));
    const before = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'notes.txt'), 'utf8');
    const io = createMockIo();
    const code = await runCli(['update', '--yes', '--project', projectRoot], io);
    assert.equal(code, 1);
    assert.match(io.getStderr(), /outside edit|--outside-edit/);
    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'notes.txt'), 'utf8'), before);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI exports an outside-edited skill without mutating the live tree', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-outside-'));
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
    const project = path.join(tmpDir, 'proj');
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', project], {
      cwd: appDir,
      encoding: 'utf8',
    });
    applyOutsideEdits(skillDir(project, 'sigmawrite'));
    const notes = fs.readFileSync(path.join(skillDir(project, 'sigmawrite'), 'notes.txt'), 'utf8');
    const exportRoot = path.join(project, 'keep');
    execFileSync(
      'node',
      [installedBin, 'update', '--skill', 'sigmawrite', '--outside-edit', 'export', '--export-dir', exportRoot, '--project', project],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(fs.readFileSync(path.join(skillDir(project, 'sigmawrite'), 'notes.txt'), 'utf8'), notes);
    assert.equal(fs.readFileSync(path.join(exportRoot, 'sigmawrite', 'notes.txt'), 'utf8'), notes);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
