import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  loadHostRegistry,
  listProjectDestinationGroups,
} from '../src/destinations.js';
import { recommendedLinkMethod } from '../src/links.js';
import { createInstallPlan, formatPlanHuman } from '../src/plan.js';
import { loadProjectLock, PROJECT_LOCK_FILENAME } from '../src/project-lock.js';
import { loadProjectState, saveProjectState, recordSkillInState, STATE_FILENAME } from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';

const ROOT = findPackageRoot();
const LINK_METHOD = recommendedLinkMethod();

function hostGroups(projectRoot) {
  return listProjectDestinationGroups({
    registry: loadHostRegistry(ROOT),
    projectRoot,
    env: {},
  });
}

function plantSkill(destDir, skillId = 'sigmawrite') {
  fs.mkdirSync(path.dirname(destDir), { recursive: true });
  fs.cpSync(path.join(ROOT, skillId), destDir, { recursive: true });
}

function skillBytes(destDir) {
  const files = {};
  const walk = (dir, prefix = '') => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === '.sigma-backup.json') continue;
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full, rel);
      else files[rel] = fs.readFileSync(full);
    }
  };
  walk(destDir);
  return files;
}

test('install: exact manual copy is adopted without rewriting skill bytes', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-manual-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    const before = skillBytes(dest);
    const mtime = fs.statSync(path.join(dest, 'SKILL.md')).mtimeMs;

    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
    });

    assert.equal(result.success, true);
    assert.equal(result.plan.destinations[0].adoption, 'exact-revision');
    assert.deepEqual(skillBytes(dest), before);
    assert.equal(fs.statSync(path.join(dest, 'SKILL.md')).mtimeMs, mtime);

    const state = loadProjectState(projectRoot);
    assert.equal(state.skills.sigmawrite.revision, result.plan.sourceRevision);
    assert.equal(state.skills.sigmawrite.destination, '.agents/skills/sigmawrite');
    const lock = loadProjectLock(projectRoot);
    assert.equal(lock.skills.sigmawrite.revision, result.plan.sourceRevision);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: generic-CLI link to an exact copy is adopted by resolved target', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-generic-link-'));
  try {
    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    plantSkill(canonical);
    fs.mkdirSync(path.dirname(host), { recursive: true });
    fs.symlinkSync(
      process.platform === 'win32' ? canonical : path.relative(path.dirname(host), canonical),
      host,
      process.platform === 'win32' ? 'junction' : 'dir',
    );
    fs.writeFileSync(path.join(projectRoot, PROJECT_LOCK_FILENAME), `${JSON.stringify({
      skills: {
        sigmawrite: { source: 'npx', sourceUrl: 'https://example.invalid/skills' },
      },
    }, null, 2)}\n`);
    const beforeCanonical = skillBytes(canonical);
    const beforeHostMtime = fs.lstatSync(host).mtimeMs;

    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      destinationGroups: hostGroups(projectRoot),
      method: 'link',
    });

    const canonicalPlan = result.plan.destinations.find((dest) => dest.kind === 'canonical');
    const hostPlan = result.plan.destinations.find((dest) => dest.kind === 'host');
    assert.equal(canonicalPlan.adoption, 'exact-revision');
    assert.equal(hostPlan.adoption, 'recognized-link');
    assert.equal(hostPlan.method, LINK_METHOD);
    assert.deepEqual(skillBytes(canonical), beforeCanonical);
    assert.equal(fs.lstatSync(host).mtimeMs, beforeHostMtime);
    assert.equal(fs.realpathSync(host), fs.realpathSync(canonical));

    const lock = loadProjectLock(projectRoot);
    assert.equal(lock.skills.sigmawrite.revision, result.plan.sourceRevision);
    assert.ok(!('source' in lock.skills.sigmawrite));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: existing Sigma state is a no-op rerun that leaves files and lock bytes unchanged', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-sigma-state-'));
  try {
    const catalog = getCatalog(ROOT);
    executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
    });

    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const before = skillBytes(dest);
    const lockPath = path.join(projectRoot, PROJECT_LOCK_FILENAME);
    const lockBytes = fs.readFileSync(lockPath);
    const statePath = path.join(projectRoot, '.agents', STATE_FILENAME);
    const stateBytes = fs.readFileSync(statePath);
    const skillMtime = fs.statSync(path.join(dest, 'SKILL.md')).mtimeMs;

    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
    });

    assert.equal(result.plan.destinations[0].adoption, 'sigma-state');
    assert.deepEqual(skillBytes(dest), before);
    assert.equal(fs.statSync(path.join(dest, 'SKILL.md')).mtimeMs, skillMtime);
    assert.deepEqual(fs.readFileSync(lockPath), lockBytes);
    assert.deepEqual(fs.readFileSync(statePath), stateBytes);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: duplicate exact copies keep every tree and record one canonical choice', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-dups-'));
  try {
    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    plantSkill(canonical);
    plantSkill(host);
    const beforeCanonical = skillBytes(canonical);
    const beforeHost = skillBytes(host);

    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      destinationGroups: hostGroups(projectRoot),
      method: 'copy',
    });

    assert.equal(result.plan.adoption.canonical, '.agents/skills/sigmawrite');
    const hostFate = result.plan.adoption.copies.find((copy) => copy.destination === '.claude/skills/sigmawrite');
    assert.equal(hostFate.fate, 'keep');
    assert.deepEqual(skillBytes(canonical), beforeCanonical);
    assert.deepEqual(skillBytes(host), beforeHost);

    const human = formatPlanHuman(result.plan);
    assert.match(human, /Canonical:\s+\.agents\/skills\/sigmawrite/);
    assert.match(human, /\.claude\/skills\/sigmawrite.*keep/i);

    const state = loadProjectState(projectRoot);
    const copies = state.skills.sigmawrite.copies;
    assert.equal(copies.find((copy) => copy.kind === 'canonical').method, 'copy');
    assert.equal(copies.find((copy) => copy.kind === 'host').method, 'copy');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: failed state creation leaves the original exact copy and prior state unchanged', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-fail-state-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    const before = skillBytes(dest);
    const catalog = getCatalog(ROOT);

    const originalState = recordSkillInState(loadProjectState(projectRoot), {
      skillId: 'sigmabrief',
      release: '0.1.0',
      revision: 'prior-brief',
      method: 'copy',
      destination: '.agents/skills/sigmabrief',
      projectRoot,
      ownedPaths: ['.agents/skills/sigmabrief/SKILL.md'],
      baseHashes: { 'SKILL.md': 'abc' },
    });
    saveProjectState(projectRoot, originalState);
    const priorState = fs.readFileSync(path.join(projectRoot, '.agents', STATE_FILENAME));

    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
          saveState: () => {
            throw new Error('state write failed');
          },
        });
      },
      /state write failed/,
    );

    assert.deepEqual(skillBytes(dest), before);
    assert.deepEqual(fs.readFileSync(path.join(projectRoot, '.agents', STATE_FILENAME)), priorState);
    assert.ok(!fs.existsSync(path.join(projectRoot, PROJECT_LOCK_FILENAME)));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('plan: foreign content still fails closed and generic lock entries do not grant ownership', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-adopt-foreign-plan-'));
  try {
    const dest = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    fs.mkdirSync(dest, { recursive: true });
    fs.writeFileSync(path.join(dest, 'SKILL.md'), 'foreign content', 'utf8');
    fs.writeFileSync(path.join(projectRoot, PROJECT_LOCK_FILENAME), `${JSON.stringify({
      skills: {
        sigmawrite: { source: 'npx' },
      },
    }, null, 2)}\n`);

    const catalog = getCatalog(ROOT);
    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
        });
      },
      /already exists and is not owned by SigmaSkills/,
    );
    assert.equal(fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8'), 'foreign content');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI adopts manual copies, generic-CLI links, Sigma state, duplicates, and no-op reruns', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-adopt-'));
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
    const packedRoot = path.join(appDir, 'node_modules', '@djordje-stojanovic', 'sigmaskills');

    const plantPacked = (destDir, skillId = 'sigmawrite') => {
      fs.mkdirSync(path.dirname(destDir), { recursive: true });
      fs.cpSync(path.join(packedRoot, skillId), destDir, { recursive: true });
    };

    const manualProject = path.join(tmpDir, 'manual');
    const manualDest = path.join(manualProject, '.agents', 'skills', 'sigmawrite');
    plantPacked(manualDest);
    const manualBefore = fs.readFileSync(path.join(manualDest, 'SKILL.md'));
    const manualMtime = fs.statSync(path.join(manualDest, 'SKILL.md')).mtimeMs;
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', manualProject], {
      cwd: appDir,
      encoding: 'utf8',
    });
    assert.deepEqual(fs.readFileSync(path.join(manualDest, 'SKILL.md')), manualBefore);
    assert.equal(fs.statSync(path.join(manualDest, 'SKILL.md')).mtimeMs, manualMtime);
    assert.ok(fs.existsSync(path.join(manualProject, 'skills-lock.json')));

    const linkProject = path.join(tmpDir, 'generic-link');
    const linkCanonical = path.join(linkProject, '.agents', 'skills', 'sigmawrite');
    const linkHost = path.join(linkProject, '.claude', 'skills', 'sigmawrite');
    plantPacked(linkCanonical);
    fs.mkdirSync(path.dirname(linkHost), { recursive: true });
    fs.symlinkSync(
      process.platform === 'win32' ? linkCanonical : path.relative(path.dirname(linkHost), linkCanonical),
      linkHost,
      process.platform === 'win32' ? 'junction' : 'dir',
    );
    fs.writeFileSync(path.join(linkProject, 'skills-lock.json'), `${JSON.stringify({
      skills: { sigmawrite: { source: 'npx' } },
    }, null, 2)}\n`);
    const linkOut = execFileSync(
      'node',
      [
        installedBin, 'install', 'sigmawrite',
        '--project', linkProject,
        '--destination', '.claude/skills',
        '--json',
      ],
      { cwd: appDir, encoding: 'utf8' },
    );
    const linkPlan = JSON.parse(linkOut);
    const hostPlan = linkPlan.destinations.find((dest) => dest.relativeRoot === '.claude/skills');
    assert.equal(hostPlan.adoption, 'recognized-link');
    assert.ok(fs.lstatSync(linkHost).isSymbolicLink());
    assert.equal(fs.realpathSync(linkHost), fs.realpathSync(linkCanonical));

    const sigmaProject = path.join(tmpDir, 'sigma-state');
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', sigmaProject], {
      cwd: appDir,
      encoding: 'utf8',
    });
    const sigmaLock = fs.readFileSync(path.join(sigmaProject, 'skills-lock.json'));
    const sigmaSkill = path.join(sigmaProject, '.agents', 'skills', 'sigmawrite', 'SKILL.md');
    const sigmaMtime = fs.statSync(sigmaSkill).mtimeMs;
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', sigmaProject], {
      cwd: appDir,
      encoding: 'utf8',
    });
    assert.deepEqual(fs.readFileSync(path.join(sigmaProject, 'skills-lock.json')), sigmaLock);
    assert.equal(fs.statSync(sigmaSkill).mtimeMs, sigmaMtime);

    const dupProject = path.join(tmpDir, 'dups');
    plantPacked(path.join(dupProject, '.agents', 'skills', 'sigmawrite'));
    plantPacked(path.join(dupProject, '.claude', 'skills', 'sigmawrite'));
    const dupOut = execFileSync(
      'node',
      [
        installedBin, 'install', 'sigmawrite',
        '--project', dupProject,
        '--destination', '.agents/skills',
        '--destination', '.claude/skills',
        '--copy',
        '--json',
      ],
      { cwd: appDir, encoding: 'utf8' },
    );
    const dupPlan = JSON.parse(dupOut);
    assert.equal(dupPlan.adoption.canonical, '.agents/skills/sigmawrite');
    assert.equal(
      dupPlan.adoption.copies.find((copy) => copy.destination === '.claude/skills/sigmawrite').fate,
      'keep',
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
