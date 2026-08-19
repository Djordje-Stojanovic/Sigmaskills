import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getBackupRoot } from '../src/backup.js';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import { injectRawCustomContent } from '../src/customization.js';
import { UNIVERSAL_PROJECT_DESTINATION, listProjectDestinationGroups, loadHostRegistry } from '../src/destinations.js';
import { pathExists, recommendedLinkMethod } from '../src/links.js';
import { getProjectStateDir } from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';
import { executeUpdate } from '../src/update.js';
import { createUninstallPlan, executeUninstall } from '../src/uninstall.js';

const ROOT = findPackageRoot();
const LINK_METHOD = recommendedLinkMethod();

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

function skillDir(root, skillId, relativeRoot = UNIVERSAL_PROJECT_DESTINATION) {
  return path.join(root, ...relativeRoot.split('/'), skillId);
}

function readState(root) {
  return JSON.parse(fs.readFileSync(path.join(root, '.agents', 'state.json'), 'utf8'));
}

function readLock(root) {
  return JSON.parse(fs.readFileSync(path.join(root, 'skills-lock.json'), 'utf8'));
}

function backupAbs(root, skillId) {
  const rel = readState(root).skills[skillId]?.lastBackup;
  if (!rel) return null;
  return path.join(getProjectStateDir(root), rel);
}

test('uninstall: dry-run names every path, method, scope, and canonical dependency and writes nothing', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-preview-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    const before = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8');
    const plan = createUninstallPlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      dryRun: true,
    });
    const skill = plan.skills[0];
    assert.equal(plan.command, 'uninstall');
    assert.equal(plan.scope, 'project');
    assert.equal(skill.id, 'sigmawrite');
    assert.equal(skill.reviewKind, 'clean');
    assert.deepEqual(skill.choices.sort(), ['keep', 'remove'].sort());
    const dests = skill.destinations.map((dest) => dest.relativeDestination).sort();
    assert.deepEqual(dests, ['.agents/skills/sigmawrite', '.claude/skills/sigmawrite'].sort());
    const host = skill.destinations.find((dest) => dest.relativeDestination === '.claude/skills/sigmawrite');
    const canonical = skill.destinations.find((dest) => dest.kind === 'canonical');
    assert.equal(host.method, LINK_METHOD);
    assert.equal(host.dependsOn, '.agents/skills/sigmawrite');
    assert.equal(canonical.method, 'copy');
    assert.ok(skill.remainingCanonicalDependencies.includes('.claude/skills/sigmawrite'));
    assert.equal(skill.scope, 'project');

    const io = createMockIo();
    const code = await runCli(['uninstall', '--dry-run', '--skill', 'sigmawrite', '--project', projectRoot], io);
    assert.equal(code, 0);
    assert.match(io.getStdout(), /uninstall/i);
    assert.match(io.getStdout(), /sigmawrite/);
    assert.match(io.getStdout(), /\.claude\/skills\/sigmawrite/);
    assert.match(io.getStdout(), /copy|junction|symlink/i);
    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8'), before);
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite', '.claude/skills')), true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('uninstall: clean remove deletes owned paths and lock/state; keep leaves them', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-clean-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    const keepPlan = executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmabrief'],
      clean: 'keep',
    });
    assert.equal(keepPlan.skills[0].action, 'keep');
    assert.equal(pathExists(path.join(skillDir(projectRoot, 'sigmabrief'), 'SKILL.md')), true);
    assert.ok(readState(projectRoot).skills.sigmabrief);

    const result = executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      clean: 'remove',
    });
    assert.equal(result.skills[0].action, 'remove');
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite')), false);
    assert.equal(readState(projectRoot).skills.sigmawrite, undefined);
    assert.equal(readLock(projectRoot).skills.sigmawrite, undefined);
    assert.ok(readState(projectRoot).skills.sigmabrief);
    assert.ok(readLock(projectRoot).skills.sigmabrief);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('uninstall: changed and customized skills need an explicit backup, keep, export, or delete choice', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-changed-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    const skillMd = path.join(dest, 'SKILL.md');
    fs.writeFileSync(skillMd, injectRawCustomContent(fs.readFileSync(skillMd, 'utf8'), '\nkeep these notes\n', 'sigmawrite'), 'utf8');
    const plan = createUninstallPlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
    });
    assert.equal(plan.skills[0].reviewKind, 'customized');
    assert.deepEqual(plan.skills[0].choices.sort(), ['backup', 'delete', 'export', 'keep'].sort());
    assert.throws(
      () => executeUninstall({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
      }),
      /--changed/,
    );
    assert.equal(pathExists(skillMd), true);

    fs.writeFileSync(path.join(dest, 'local-keep.txt'), 'outside', 'utf8');
    const changed = createUninstallPlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
    });
    assert.equal(changed.skills[0].reviewKind, 'changed');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('uninstall: backup-and-remove keeps a restorable snapshot; permanent delete leaves the older backup', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-backup-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    fs.writeFileSync(path.join(dest, 'local-keep.txt'), 'first-edit', 'utf8');
    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      outsideEdit: 'replace',
    });
    const older = backupAbs(projectRoot, 'sigmawrite');
    assert.equal(fs.readFileSync(path.join(older, 'local-keep.txt'), 'utf8'), 'first-edit');

    fs.writeFileSync(path.join(dest, 'second.txt'), 'live-now', 'utf8');
    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      changed: 'backup',
    });
    assert.equal(pathExists(dest), false);
    assert.equal(pathExists(older), false);
    const retained = fs.readdirSync(path.join(getBackupRoot(getProjectStateDir(projectRoot)), 'sigmawrite'));
    assert.equal(retained.length, 1);
    const newest = path.join(getBackupRoot(getProjectStateDir(projectRoot)), 'sigmawrite', retained[0]);
    assert.equal(fs.readFileSync(path.join(newest, 'second.txt'), 'utf8'), 'live-now');
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }

  const deleteRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-delete-'));
  try {
    installWrite(deleteRoot, 'sigmawrite');
    const dest = skillDir(deleteRoot, 'sigmawrite');
    fs.writeFileSync(path.join(dest, 'local-keep.txt'), 'preserve-backup', 'utf8');
    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot: deleteRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      outsideEdit: 'replace',
    });
    const older = backupAbs(deleteRoot, 'sigmawrite');
    fs.writeFileSync(path.join(dest, 'gone.txt'), 'current', 'utf8');
    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot: deleteRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      changed: 'delete',
    });
    assert.equal(pathExists(dest), false);
    assert.equal(pathExists(older), true);
    assert.equal(fs.readFileSync(path.join(older, 'local-keep.txt'), 'utf8'), 'preserve-backup');
    assert.equal(pathExists(path.join(older, 'gone.txt')), false);
  } finally {
    fs.rmSync(deleteRoot, { recursive: true, force: true });
  }
});

test('uninstall: export copies the current tree then removes managed paths without touching a retained backup', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-export-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    fs.writeFileSync(path.join(dest, 'local-keep.txt'), 'export-me', 'utf8');
    executeUpdate({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      outsideEdit: 'replace',
    });
    const older = backupAbs(projectRoot, 'sigmawrite');
    fs.writeFileSync(path.join(dest, 'newer.txt'), 'live', 'utf8');
    const exportDir = path.join(projectRoot, 'exported');
    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      changed: 'export',
      exportDir,
    });
    assert.equal(pathExists(dest), false);
    assert.equal(fs.readFileSync(path.join(exportDir, 'sigmawrite', 'newer.txt'), 'utf8'), 'live');
    assert.equal(pathExists(older), true);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('uninstall: deletes a link itself and keeps canonical until dependents are gone', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-link-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    const canonical = skillDir(projectRoot, 'sigmawrite');
    const linkPath = skillDir(projectRoot, 'sigmawrite', '.claude/skills');
    const canonicalBytes = fs.readFileSync(path.join(canonical, 'SKILL.md'), 'utf8');
    assert.equal(fs.lstatSync(linkPath).isSymbolicLink(), true);

    executeUninstall({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      skillIds: ['sigmawrite'],
      clean: 'remove',
      afterUnlink: () => {
        assert.equal(pathExists(linkPath), false);
        assert.equal(pathExists(canonical), true);
        assert.equal(fs.readFileSync(path.join(canonical, 'SKILL.md'), 'utf8'), canonicalBytes);
      },
    });
    assert.equal(pathExists(linkPath), false);
    assert.equal(pathExists(canonical), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('uninstall: missing, unowned, divergent copies, and wrong-target links stop without writes', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-stop-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    const dest = skillDir(projectRoot, 'sigmawrite');
    const liveBefore = fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8');
    const linkPath = skillDir(projectRoot, 'sigmawrite', '.claude/skills');

    fs.rmSync(dest, { recursive: true, force: true });
    assert.throws(
      () => executeUninstall({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        clean: 'remove',
      }),
      /missing/,
    );
    assert.equal(pathExists(linkPath), true);
    if (pathExists(linkPath)) fs.unlinkSync(linkPath);
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });

    const foreign = path.join(projectRoot, 'foreign-target');
    fs.mkdirSync(foreign, { recursive: true });
    fs.writeFileSync(path.join(foreign, 'SKILL.md'), liveBefore, 'utf8');
    fs.unlinkSync(linkPath);
    fs.symlinkSync(foreign, linkPath, process.platform === 'win32' ? 'junction' : 'dir');
    assert.throws(
      () => executeUninstall({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        clean: 'remove',
      }),
      /wrong-target|wrong target/,
    );
    assert.equal(pathExists(linkPath), true);
    assert.equal(fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8'), liveBefore);
    fs.unlinkSync(linkPath);
    fs.mkdirSync(linkPath, { recursive: true });
    fs.writeFileSync(path.join(linkPath, 'stranger.txt'), 'not a link', 'utf8');
    assert.throws(
      () => executeUninstall({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        changed: 'delete',
      }),
      /unowned/,
    );
    assert.equal(fs.readFileSync(path.join(linkPath, 'stranger.txt'), 'utf8'), 'not a link');
    fs.rmSync(linkPath, { recursive: true, force: true });
    fs.rmSync(foreign, { recursive: true, force: true });
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });

    const unownedRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-unowned-'));
    try {
      installWrite(unownedRoot, 'sigmawrite');
      const unownedDest = skillDir(unownedRoot, 'sigmawrite');
      const state = readState(unownedRoot);
      delete state.skills.sigmawrite;
      fs.writeFileSync(path.join(unownedRoot, '.agents', 'state.json'), `${JSON.stringify(state, null, 2)}\n`);
      assert.throws(
        () => executeUninstall({
          catalog: getCatalog(ROOT),
          projectRoot: unownedRoot,
          packageRoot: ROOT,
          skillIds: ['sigmawrite'],
          clean: 'remove',
        }),
        /unowned|stale/,
      );
      assert.equal(pathExists(path.join(unownedDest, 'SKILL.md')), true);
    } finally {
      fs.rmSync(unownedRoot, { recursive: true, force: true });
    }

    const copyRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-divergent-'));
    try {
      installWrite(copyRoot, 'sigmawrite', {
        selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
        method: 'copy',
      });
      fs.writeFileSync(path.join(skillDir(copyRoot, 'sigmawrite', '.claude/skills'), 'only-host.txt'), 'divergent', 'utf8');
      assert.throws(
        () => executeUninstall({
          catalog: getCatalog(ROOT),
          projectRoot: copyRoot,
          packageRoot: ROOT,
          skillIds: ['sigmawrite'],
        }),
        /copy-disagreement|--changed|divergent/,
      );
      assert.equal(pathExists(skillDir(copyRoot, 'sigmawrite')), true);
      assert.equal(pathExists(path.join(skillDir(copyRoot, 'sigmawrite', '.claude/skills'), 'only-host.txt')), true);
    } finally {
      fs.rmSync(copyRoot, { recursive: true, force: true });
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('uninstall: failure after staging leaves the prior live tree and ownership', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-fail-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');
    const before = fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8');
    assert.throws(
      () => executeUninstall({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        skillIds: ['sigmawrite'],
        clean: 'remove',
        afterStage: () => {
          throw new Error('injected uninstall failure');
        },
      }),
      /injected uninstall failure/,
    );
    assert.equal(fs.readFileSync(path.join(dest, 'SKILL.md'), 'utf8'), before);
    assert.ok(readState(projectRoot).skills.sigmawrite);
    assert.ok(readLock(projectRoot).skills.sigmawrite);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('cli: uninstall requires --skill and --yes or --dry-run; global writes need --global and --yes', async () => {
  const io = createMockIo();
  assert.equal(await runCli(['uninstall'], io), 1);
  assert.match(io.getStderr(), /--skill/);

  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-cli-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const needYes = createMockIo();
    assert.equal(await runCli(['uninstall', '--skill', 'sigmawrite', '--project', projectRoot], needYes), 1);
    assert.match(needYes.getStderr(), /--yes|--dry-run/);

    const homeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-uninstall-home-'));
    try {
      const env = { ...process.env, HOME: homeDir, USERPROFILE: homeDir, CI: '' };
      const globalIo = createMockIo(env);
      assert.equal(
        await runCli(['uninstall', '--skill', 'sigmawrite', '--global', '--project', projectRoot], globalIo),
        1,
      );
      assert.match(globalIo.getStderr(), /--global and --yes/);
    } finally {
      fs.rmSync(homeDir, { recursive: true, force: true });
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI uninstalls a selected skill and leaves an unowned stranger path', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-uninstall-'));
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
    const listed = execFileSync('tar', ['-tf', tarballFileName], { cwd: tmpDir, encoding: 'utf8' });
    assert.match(listed, /package\/src\/uninstall\.js/);

    const project = path.join(tmpDir, 'proj');
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', project], {
      cwd: appDir,
      encoding: 'utf8',
    });
    const dest = path.join(project, '.agents', 'skills', 'sigmawrite');
    const stranger = path.join(project, '.claude', 'skills', 'sigmawrite');
    fs.mkdirSync(stranger, { recursive: true });
    fs.writeFileSync(path.join(stranger, 'leave-me.txt'), 'unrelated', 'utf8');
    execFileSync(
      'node',
      [installedBin, 'uninstall', '--skill', 'sigmawrite', '--yes', '--project', project],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(pathExists(dest), false);
    assert.equal(fs.readFileSync(path.join(stranger, 'leave-me.txt'), 'utf8'), 'unrelated');
    assert.equal(JSON.parse(fs.readFileSync(path.join(project, '.agents', 'state.json'), 'utf8')).skills.sigmawrite, undefined);
    assert.ok(fs.existsSync(path.join(packedRoot, 'src', 'uninstall.js')));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
