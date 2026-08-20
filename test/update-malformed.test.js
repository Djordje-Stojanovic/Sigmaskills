import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import {
  CUSTOM_BLOCK_END,
  CUSTOM_BLOCK_START,
  applyProposedRepair,
  diagnoseCustomizationMarkers,
} from '../src/customization.js';
import { UNIVERSAL_PROJECT_DESTINATION, listProjectDestinationGroups, loadHostRegistry } from '../src/destinations.js';
import { pathExists } from '../src/links.js';
import { computeSkillRevisionAndHashes } from '../src/revision.js';
import { getProjectStateDir } from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';
import { createUpdatePlan, executeUpdate } from '../src/update.js';

const ROOT = findPackageRoot();

function createMockIo() {
  let stdout = '';
  let stderr = '';
  return {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
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

function snapshot(root) {
  const files = {};
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const rel = path.relative(root, full).replace(/\\/g, '/');
      if (entry.isDirectory() && !entry.isSymbolicLink()) walk(full);
      else if (entry.isSymbolicLink()) files[rel] = `link:${fs.readlinkSync(full)}`;
      else files[rel] = fs.readFileSync(full);
    }
  };
  walk(root);
  return files;
}

function breakMarkers(skillMd, kind) {
  const original = fs.readFileSync(skillMd, 'utf8');
  if (kind === 'missing') {
    fs.writeFileSync(skillMd, original.replace(CUSTOM_BLOCK_START, '').replace(CUSTOM_BLOCK_END, ''), 'utf8');
    return;
  }
  if (kind === 'duplicate') {
    fs.writeFileSync(skillMd, original.replace(CUSTOM_BLOCK_START, `${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_START}`), 'utf8');
    return;
  }
  if (kind === 'reversed') {
    fs.writeFileSync(
      skillMd,
      original.replace(`${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}`, `${CUSTOM_BLOCK_END}\n${CUSTOM_BLOCK_START}`),
      'utf8',
    );
  }
}

function ageOfficial(root, skillId) {
  const dest = skillDir(root, skillId);
  const skillMd = path.join(dest, 'SKILL.md');
  fs.writeFileSync(
    skillMd,
    fs.readFileSync(skillMd, 'utf8').replace('## Personal instructions', '<!-- sigma-older -->\n\n## Personal instructions'),
    'utf8',
  );
  const hashes = computeSkillRevisionAndHashes(dest);
  const state = readState(root);
  state.skills[skillId].baseHashes = hashes.files;
  state.skills[skillId].revision = hashes.revision;
  fs.writeFileSync(path.join(root, '.agents', 'state.json'), `${JSON.stringify(state, null, 2)}\n`);
}

test('update: malformed markers block automatic update and dry-run shows exact repair bytes', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-malformed-block-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const skillMd = path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md');
    breakMarkers(skillMd, 'missing');
    const before = snapshot(projectRoot);
    const diagnosis = diagnoseCustomizationMarkers(fs.readFileSync(skillMd, 'utf8'), 'sigmawrite');

    const plan = createUpdatePlan({ catalog: getCatalog(ROOT), projectRoot, packageRoot: ROOT });
    const skill = plan.skills.find((item) => item.id === 'sigmawrite');
    assert.equal(skill.comparison, 'malformed-markers');
    assert.equal(skill.needsMarkerResolution, true);
    assert.equal(skill.repairable, true);
    assert.equal(skill.proposedRepair, diagnosis.proposedRepair);
    assert.deepEqual(skill.repairEffects, { added: [], replaced: ['SKILL.md'], deleted: [] });
    assert.match(plan.prompt, /malformed/);

    const io = createMockIo();
    const dryCode = await runCli(['update', '--dry-run', '--json', '--project', projectRoot], io);
    assert.equal(dryCode, 0);
    const payload = JSON.parse(io.getStdout());
    const drySkill = payload.skills.find((item) => item.id === 'sigmawrite');
    assert.equal(drySkill.proposedRepair, diagnosis.proposedRepair);
    assert.deepEqual(snapshot(projectRoot), before);

    const yesIo = createMockIo();
    const yesCode = await runCli(['update', '--yes', '--project', projectRoot], yesIo);
    assert.equal(yesCode, 1);
    assert.match(yesIo.getStderr(), /malformed|--malformed-markers/);
    assert.deepEqual(snapshot(projectRoot), before);
    assert.equal(fs.readFileSync(skillMd, 'utf8').includes(CUSTOM_BLOCK_START), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: skip leaves malformed skill unchanged while another skill updates', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-malformed-skip-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    breakMarkers(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'duplicate');
    ageOfficial(projectRoot, 'sigmabrief');
    const writeBefore = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8');
    const writeStateBefore = JSON.stringify(readState(projectRoot).skills.sigmawrite);

    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      malformedMarkers: 'skip',
    });

    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8'), writeBefore);
    assert.equal(JSON.stringify(readState(projectRoot).skills.sigmawrite), writeStateBefore);
    assert.equal(
      fs.readFileSync(path.join(skillDir(projectRoot, 'sigmabrief'), 'SKILL.md'), 'utf8').includes('<!-- sigma-older -->'),
      false,
    );
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: approved repair writes exact proposed bytes and keeps extra files', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-malformed-repair-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    const skillMd = path.join(dest, 'SKILL.md');
    breakMarkers(skillMd, 'missing');
    fs.writeFileSync(path.join(dest, 'notes.txt'), 'keep me\n', 'utf8');
    const broken = fs.readFileSync(skillMd, 'utf8');
    const expected = applyProposedRepair(broken, 'sigmawrite');

    assert.throws(
      () => executeUpdate({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        malformedMarkers: 'repair',
        skillIds: ['sigmawrite'],
      }),
      /outside-edit|outside edit/i,
    );
    assert.equal(fs.readFileSync(skillMd, 'utf8'), broken);
    assert.equal(fs.readFileSync(path.join(dest, 'notes.txt'), 'utf8'), 'keep me\n');

    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      malformedMarkers: 'repair',
      outsideEdit: 'skip',
      skillIds: ['sigmawrite'],
    });
    assert.equal(fs.readFileSync(skillMd, 'utf8'), expected);
    assert.equal(fs.readFileSync(path.join(dest, 'notes.txt'), 'utf8'), 'keep me\n');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: backup plus clean install replaces a malformed skill after a private backup', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-malformed-replace-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    const skillMd = path.join(dest, 'SKILL.md');
    breakMarkers(skillMd, 'duplicate');
    fs.writeFileSync(path.join(dest, 'notes.txt'), 'local\n', 'utf8');
    const broken = fs.readFileSync(skillMd, 'utf8');

    const result = executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      malformedMarkers: 'replace',
      outsideEdit: 'replace',
      skillIds: ['sigmawrite'],
    });
    assert.equal(result.results[0].action, 'replace');
    assert.equal(fs.readFileSync(skillMd, 'utf8').includes(`${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_START}`), false);
    assert.equal(pathExists(path.join(dest, 'notes.txt')), false);
    const backupRoot = path.join(getProjectStateDir(projectRoot), 'backups', 'sigmawrite');
    const stamps = fs.readdirSync(backupRoot);
    assert.equal(stamps.length > 0, true);
    const backupMd = fs.readFileSync(path.join(backupRoot, stamps[0], 'SKILL.md'), 'utf8');
    assert.equal(backupMd, broken);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('update: invalid repair, editor failure, backup failure, and cancel write nothing', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-malformed-fail-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    const skillMd = path.join(dest, 'SKILL.md');
    breakMarkers(skillMd, 'duplicate');
    const duplicateBefore = fs.readFileSync(skillMd, 'utf8');

    assert.throws(
      () => executeUpdate({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        malformedMarkers: 'repair',
        skillIds: ['sigmawrite'],
      }),
      /invalid repair/i,
    );
    assert.equal(fs.readFileSync(skillMd, 'utf8'), duplicateBefore);

    fs.writeFileSync(skillMd, fs.readFileSync(path.join(ROOT, 'sigmawrite', 'SKILL.md'), 'utf8'), 'utf8');
    breakMarkers(skillMd, 'missing');
    const missingBefore = fs.readFileSync(skillMd, 'utf8');
    assert.throws(
      () => executeUpdate({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        malformedMarkers: 'repair',
        skillIds: ['sigmawrite'],
        repairEditor: () => { throw new Error('editor failed'); },
      }),
      /editor failed/,
    );
    assert.equal(fs.readFileSync(skillMd, 'utf8'), missingBefore);

    assert.throws(
      () => executeUpdate({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        malformedMarkers: 'replace',
        skillIds: ['sigmawrite'],
        afterBackup: () => { throw new Error('backup exploded'); },
      }),
      /backup exploded/,
    );
    assert.equal(fs.readFileSync(skillMd, 'utf8'), missingBefore);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI skips a malformed skill and updates a sibling Project Installation', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-malformed-'));
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
    const installedBin = path.join(appDir, 'node_modules', '@djordje-stojanovic', 'sigmaskills', 'bin', 'sigmaskills.js');
    const project = path.join(tmpDir, 'proj');
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', project], {
      cwd: appDir,
      encoding: 'utf8',
    });
    execFileSync('node', [installedBin, 'install', 'sigmabrief', '--project', project], {
      cwd: appDir,
      encoding: 'utf8',
    });
    const writeMd = path.join(skillDir(project, 'sigmawrite'), 'SKILL.md');
    breakMarkers(writeMd, 'missing');
    const broken = fs.readFileSync(writeMd, 'utf8');
    const briefMd = path.join(skillDir(project, 'sigmabrief'), 'SKILL.md');
    fs.writeFileSync(
      briefMd,
      fs.readFileSync(briefMd, 'utf8').replace('## Personal instructions', '<!-- sigma-older -->\n\n## Personal instructions'),
      'utf8',
    );
    const briefLive = computeSkillRevisionAndHashes(skillDir(project, 'sigmabrief'));
    const statePath = path.join(project, '.agents', 'state.json');
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    state.skills.sigmabrief.baseHashes = briefLive.files;
    state.skills.sigmabrief.revision = briefLive.revision;
    fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);

    execFileSync(
      'node',
      [installedBin, 'update', '--yes', '--malformed-markers', 'skip', '--project', project],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(fs.readFileSync(writeMd, 'utf8'), broken);
    assert.equal(fs.readFileSync(briefMd, 'utf8').includes('<!-- sigma-older -->'), false);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
