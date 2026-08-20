import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  loadHostRegistry,
  listProjectDestinationGroups,
} from '../src/destinations.js';
import { inspectManagedPath, pathExists, recommendedLinkMethod } from '../src/links.js';
import { createInstallPlan, formatPlanHuman } from '../src/plan.js';
import { loadProjectState } from '../src/state.js';
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

test('plan: recommended link method records copy for canonical and a platform link for each host destination', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-plan-link-'));
  try {
    const catalog = getCatalog(ROOT);
    const plan = createInstallPlan(catalog, {
      skillId: 'sigmawrite',
      projectRoot,
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      destinationGroups: hostGroups(projectRoot),
      method: 'link',
      dryRun: true,
    });

    assert.equal(plan.method, 'link');
    const canonical = plan.destinations.find((dest) => dest.kind === 'canonical');
    const host = plan.destinations.find((dest) => dest.kind === 'host');
    assert.equal(canonical.method, 'copy');
    assert.equal(canonical.dependsOn, null);
    assert.equal(host.method, LINK_METHOD);
    assert.equal(host.dependsOn, '.agents/skills/sigmawrite');
    assert.ok(plan.writes.includes('.claude/skills/sigmawrite'));
    assert.ok(!plan.writes.some((write) => write.startsWith('.claude/skills/sigmawrite/')));

    const human = formatPlanHuman(plan);
    assert.match(human, /Method:\s+link/);
    assert.match(human, new RegExp(`Method:\\s+${LINK_METHOD}`));
    assert.match(human, /Method:\s+copy/);
    assert.match(human, /Depends on:\s+\.agents\/skills\/sigmawrite/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('plan: explicit copy method records an independent copy at every destination', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-plan-copy-'));
  try {
    const catalog = getCatalog(ROOT);
    const plan = createInstallPlan(catalog, {
      skillId: 'sigmawrite',
      projectRoot,
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      destinationGroups: hostGroups(projectRoot),
      method: 'copy',
      dryRun: true,
    });

    assert.equal(plan.method, 'copy');
    for (const dest of plan.destinations) {
      assert.equal(dest.method, 'copy');
      assert.equal(dest.dependsOn, null);
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: recommended link creates a real Windows junction or POSIX symlink', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-install-link-'));
  try {
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

    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    assert.equal(fs.lstatSync(canonical).isSymbolicLink(), false);
    assert.ok(fs.lstatSync(host).isSymbolicLink());
    assert.equal(fs.realpathSync(host), fs.realpathSync(canonical));
    assert.equal(
      fs.readFileSync(path.join(host, 'SKILL.md'), 'utf8'),
      fs.readFileSync(path.join(canonical, 'SKILL.md'), 'utf8'),
    );

    const hostPlan = result.plan.destinations.find((dest) => dest.kind === 'host');
    assert.equal(hostPlan.method, LINK_METHOD);

    const state = loadProjectState(projectRoot);
    const copies = state.skills.sigmawrite.copies;
    const hostCopy = copies.find((copy) => copy.kind === 'host');
    assert.equal(hostCopy.method, LINK_METHOD);
    assert.equal(hostCopy.dependsOn, '.agents/skills/sigmawrite');
    assert.equal(hostCopy.baseHashes, undefined);
    const canonicalCopy = copies.find((copy) => copy.kind === 'canonical');
    assert.equal(canonicalCopy.method, 'copy');
    assert.ok(canonicalCopy.baseHashes['SKILL.md']);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: copy fallback records an independent managed copy with its own hashes', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-install-copy-indep-'));
  try {
    const catalog = getCatalog(ROOT);
    executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      destinationGroups: hostGroups(projectRoot),
      method: 'copy',
    });

    const canonicalFile = path.join(projectRoot, '.agents', 'skills', 'sigmawrite', 'SKILL.md');
    const hostFile = path.join(projectRoot, '.claude', 'skills', 'sigmawrite', 'SKILL.md');
    assert.equal(fs.lstatSync(path.dirname(hostFile)).isSymbolicLink(), false);
    const original = fs.readFileSync(hostFile, 'utf8');
    fs.writeFileSync(hostFile, `${original}\nlocal-only\n`, 'utf8');
    assert.equal(fs.readFileSync(canonicalFile, 'utf8'), original);

    const state = loadProjectState(projectRoot);
    const hostCopy = state.skills.sigmawrite.copies.find((copy) => copy.kind === 'host');
    assert.equal(hostCopy.method, 'copy');
    assert.equal(hostCopy.dependsOn, null);
    assert.ok(hostCopy.baseHashes['SKILL.md']);
    assert.equal(hostCopy.baseHashes['SKILL.md'], state.skills.sigmawrite.copies.find((copy) => copy.kind === 'canonical').baseHashes['SKILL.md']);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: existing wrong-target and broken links fail before any write', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-install-bad-link-'));
  try {
    const catalog = getCatalog(ROOT);
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    const other = path.join(projectRoot, '.other', 'sigmawrite');
    fs.mkdirSync(other, { recursive: true });
    fs.writeFileSync(path.join(other, 'SKILL.md'), 'other', 'utf8');
    fs.mkdirSync(path.dirname(host), { recursive: true });
    fs.symlinkSync(other, host, process.platform === 'win32' ? 'junction' : 'dir');

    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
          selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
          method: 'link',
        });
      },
      /wrong-target/i,
    );
    assert.ok(!pathExists(path.join(projectRoot, '.agents', 'skills', 'sigmawrite')));
    assert.equal(inspectManagedPath(host, path.join(projectRoot, '.agents', 'skills', 'sigmawrite')).wrongTarget, true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: declining copy fallback leaves destination and ownership unchanged', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-install-decline-'));
  try {
    const catalog = getCatalog(ROOT);
    const cause = Object.assign(new Error('EPERM: operation not permitted, symlink'), { code: 'EPERM' });
    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
          selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
          method: 'link',
          createLink: () => {
            throw cause;
          },
          onLinkFailure: (failure) => {
            assert.match(failure.cause, /EPERM/);
            assert.match(failure.destination, /claude/i);
            return 'abort';
          },
        });
      },
      /EPERM/,
    );

    assert.ok(!pathExists(path.join(projectRoot, '.agents', 'skills', 'sigmawrite')));
    assert.ok(!pathExists(path.join(projectRoot, '.claude', 'skills', 'sigmawrite')));
    assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
    const statePath = path.join(projectRoot, '.agents', 'state.json');
    assert.ok(!fs.existsSync(statePath));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: accepting copy fallback writes an independent copy and does not switch silently', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-install-fallback-'));
  try {
    const catalog = getCatalog(ROOT);
    const cause = Object.assign(new Error('ENAMETOOLONG: name too long'), { code: 'ENAMETOOLONG' });
    const decisions = [];
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
      createLink: () => {
        throw cause;
      },
      onLinkFailure: (failure) => {
        decisions.push(failure);
        return 'copy';
      },
    });

    assert.equal(decisions.length, 1);
    assert.match(decisions[0].cause, /ENAMETOOLONG/);
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    assert.equal(fs.lstatSync(host).isSymbolicLink(), false);
    assert.ok(fs.existsSync(path.join(host, 'SKILL.md')));
    const hostPlan = result.plan.destinations.find((dest) => dest.kind === 'host');
    assert.equal(hostPlan.method, 'copy');
    assert.equal(hostPlan.fallbackFrom, LINK_METHOD);
    const state = loadProjectState(projectRoot);
    const hostCopy = state.skills.sigmawrite.copies.find((copy) => copy.kind === 'host');
    assert.equal(hostCopy.method, 'copy');
    assert.equal(hostCopy.dependsOn, null);
    assert.ok(hostCopy.baseHashes['SKILL.md']);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('cli: --destination with default link method plans a platform link', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cli-dest-link-'));
  try {
    const io = createMockIo();
    const code = await runCli([
      'install', 'sigmawrite',
      '--dry-run', '--json',
      '--project', projectRoot,
      '--destination', '.claude/skills',
    ], io);
    assert.equal(code, 0);
    const plan = JSON.parse(io.getStdout());
    assert.equal(plan.method, 'link');
    const host = plan.destinations.find((dest) => dest.relativeRoot === '.claude/skills');
    assert.equal(host.method, LINK_METHOD);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('cli: --copy writes independent copies to selected destinations', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cli-copy-'));
  try {
    const io = createMockIo();
    const code = await runCli([
      'install', 'sigmawrite',
      '--project', projectRoot,
      '--destination', '.claude/skills',
      '--copy',
    ], io);
    assert.equal(code, 0);
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    assert.equal(fs.lstatSync(host).isSymbolicLink(), false);
    assert.ok(fs.existsSync(path.join(host, 'SKILL.md')));
    assert.match(io.getStdout(), /Method:\s+copy/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI creates a real platform link for an explicit host destination', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-link-'));
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
    const projectRoot = path.join(tmpDir, 'proj');
    fs.mkdirSync(projectRoot, { recursive: true });

    const installOut = execFileSync(
      'node',
      [
        installedBin, 'install', 'sigmawrite',
        '--project', projectRoot,
        '--destination', '.claude/skills',
      ],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.match(installOut, new RegExp(LINK_METHOD));

    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite');
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    assert.ok(fs.lstatSync(host).isSymbolicLink());
    assert.equal(fs.realpathSync(host), fs.realpathSync(canonical));
    const state = JSON.parse(fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8'));
    const hostCopy = state.skills.sigmawrite.copies.find((copy) => copy.kind === 'host');
    assert.equal(hostCopy.method, LINK_METHOD);
    assert.equal(hostCopy.dependsOn, '.agents/skills/sigmawrite');
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
