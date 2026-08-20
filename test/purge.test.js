import assert from 'node:assert/strict';
import { execFileSync, execSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { commitSkillBackup, getBackupRoot } from '../src/backup.js';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  listGlobalDestinationGroups,
  listProjectDestinationGroups,
  loadHostRegistry,
} from '../src/destinations.js';
import { pathExists, recommendedLinkMethod } from '../src/links.js';
import {
  PURGE_CONFIRMATION_PHRASE,
  PURGE_JOURNAL_FILENAME,
  PURGE_QUARANTINE_DIRNAME,
  createPurgePlan,
  executePurge,
} from '../src/purge.js';
import { getProjectStateDir } from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';
import { UNINSTALL_JOURNAL_FILENAME } from '../src/uninstall.js';

const ROOT = findPackageRoot();
const LINK_METHOD = recommendedLinkMethod();

function createMockIo(env, extra = {}) {
  let stdout = '';
  let stderr = '';
  return {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    stdin: extra.stdin,
    env,
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

function ttyStdin(line) {
  const stdin = new PassThrough();
  stdin.isTTY = true;
  setImmediate(() => stdin.end(`${line}\n`));
  return stdin;
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

function seedBackup(projectRoot, skillId) {
  return commitSkillBackup({
    stateDir: getProjectStateDir(projectRoot),
    skillId,
    sourceDir: skillDir(projectRoot, skillId),
    ownership: { scope: 'project', canonicalTarget: `.agents/skills/${skillId}` },
  });
}

test('purge: dry-run enumerates the ownership plan and writes nothing', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-preview-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    installWrite(projectRoot, 'sigmabrief');
    const backupDir = seedBackup(projectRoot, 'sigmawrite');
    const lookalike = path.join(projectRoot, '.agents', 'skills', 'not-recorded');
    fs.mkdirSync(lookalike, { recursive: true });
    fs.writeFileSync(path.join(lookalike, 'keep.txt'), 'folder-name is not ownership', 'utf8');
    const beforeWrite = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8');

    const plan = createPurgePlan({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      dryRun: true,
    });
    assert.equal(plan.command, 'purge');
    assert.equal(plan.scope, 'project');
    assert.equal(plan.confirmationPhrase, PURGE_CONFIRMATION_PHRASE);
    const rels = plan.items.map((item) => item.relative).sort();
    assert.ok(rels.includes('.agents/skills/sigmawrite'));
    assert.ok(rels.includes('.claude/skills/sigmawrite'));
    assert.ok(rels.includes('.agents/skills/sigmabrief'));
    assert.ok(rels.includes('skills-lock.json'));
    assert.ok(rels.includes('state.json') || plan.items.some((item) => item.kind === 'manifest'));
    assert.ok(plan.items.some((item) => item.kind === 'backups'));
    assert.equal(rels.includes('.agents/skills/not-recorded'), false);

    const io = createMockIo();
    const code = await runCli(['purge', '--dry-run', '--project', projectRoot, '--json'], io);
    assert.equal(code, 0);
    const json = JSON.parse(io.getStdout());
    assert.equal(json.command, 'purge');
    assert.equal(json.dryRun, true);
    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8'), beforeWrite);
    assert.equal(pathExists(backupDir), true);
    assert.equal(fs.readFileSync(path.join(lookalike, 'keep.txt'), 'utf8'), 'folder-name is not ownership');
    assert.ok(readState(projectRoot).skills.sigmawrite);
    assert.ok(readLock(projectRoot).skills.sigmawrite);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('purge: --yes, CI, non-TTY, and JSON are not confirmation', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-auth-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');

    const yesIo = createMockIo();
    assert.equal(await runCli(['purge', '--yes', '--project', projectRoot], yesIo), 1);
    assert.match(yesIo.getStderr(), /confirm-purge|confirmation phrase/i);

    const jsonIo = createMockIo();
    assert.equal(await runCli(['purge', '--json', '--project', projectRoot], jsonIo), 1);
    assert.match(jsonIo.getStderr(), /confirm-purge|confirmation phrase/i);

    const ciIo = createMockIo({ ...process.env, CI: 'true' });
    assert.equal(await runCli(['purge', '--project', projectRoot], ciIo), 1);
    assert.match(ciIo.getStderr(), /confirm-purge|confirmation phrase/i);

    assert.equal(pathExists(dest), true);
    assert.ok(readState(projectRoot).skills.sigmawrite);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('purge: cancellation and the wrong phrase write nothing', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-phrase-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    const dest = skillDir(projectRoot, 'sigmawrite');

    const cancelIo = createMockIo({ ...process.env, CI: '' }, { stdin: ttyStdin('') });
    assert.equal(await runCli(['purge', '--project', projectRoot], cancelIo), 1);
    assert.match(cancelIo.getStderr(), /cancel/i);
    assert.equal(pathExists(dest), true);

    const wrongIo = createMockIo({ ...process.env, CI: '' }, { stdin: ttyStdin('purge please') });
    assert.equal(await runCli(['purge', '--project', projectRoot], wrongIo), 1);
    assert.match(wrongIo.getStderr(), /phrase|confirm/i);
    assert.equal(pathExists(dest), true);

    const flagIo = createMockIo();
    assert.equal(
      await runCli(['purge', '--confirm-purge', 'nope', '--project', projectRoot], flagIo),
      1,
    );
    assert.match(flagIo.getStderr(), /phrase|confirm/i);
    assert.equal(pathExists(dest), true);
    assert.ok(readState(projectRoot).skills.sigmawrite);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('purge: unowned occupants stop and remain; lookalikes are not owned', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-unowned-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    const host = skillDir(projectRoot, 'sigmawrite', '.claude/skills');
    fs.rmSync(host, { recursive: true, force: true });
    fs.mkdirSync(host, { recursive: true });
    fs.writeFileSync(path.join(host, 'mine.txt'), 'not yours', 'utf8');
    const lookalike = path.join(projectRoot, '.agents', 'skills', 'sigmawrite-extra');
    fs.mkdirSync(lookalike, { recursive: true });
    fs.writeFileSync(path.join(lookalike, 'stay.txt'), 'stay', 'utf8');

    assert.throws(
      () => executePurge({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        confirmPurge: PURGE_CONFIRMATION_PHRASE,
      }),
      /unowned|wrong-target/i,
    );
    assert.equal(fs.readFileSync(path.join(host, 'mine.txt'), 'utf8'), 'not yours');
    assert.equal(fs.readFileSync(path.join(lookalike, 'stay.txt'), 'utf8'), 'stay');
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite')), true);
    assert.ok(readState(projectRoot).skills.sigmawrite);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('purge: project scope never touches Global Installation', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-project-'));
  const homeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-home-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    executeProjectInstall({
      catalog: getCatalog(ROOT),
      skillId: 'sigmawrite',
      projectRoot,
      homeDir,
      scope: 'global',
      packageRoot: ROOT,
      env: { HOME: homeDir, USERPROFILE: homeDir, CI: '' },
      destinationGroups: listGlobalDestinationGroups({
        registry: loadHostRegistry(ROOT),
        homeDir,
        env: {},
      }),
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION],
    });
    const globalDest = path.join(homeDir, '.agents', 'skills', 'sigmawrite', 'SKILL.md');
    const globalBytes = fs.readFileSync(globalDest, 'utf8');

    executePurge({
      catalog: getCatalog(ROOT),
      projectRoot,
      homeDir,
      packageRoot: ROOT,
      confirmPurge: PURGE_CONFIRMATION_PHRASE,
    });
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite')), false);
    assert.equal(fs.readFileSync(globalDest, 'utf8'), globalBytes);

    executePurge({
      catalog: getCatalog(ROOT),
      projectRoot,
      homeDir,
      scope: 'global',
      packageRoot: ROOT,
      confirmPurge: PURGE_CONFIRMATION_PHRASE,
    });
    assert.equal(pathExists(globalDest), false);
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite')), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('purge: complete purge removes owned trees, backups, journals, staging, and Sigma lock', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-ok-'));
  try {
    installWrite(projectRoot, 'sigmawrite', {
      selectedRoots: [UNIVERSAL_PROJECT_DESTINATION, '.claude/skills'],
      method: 'link',
    });
    installWrite(projectRoot, 'sigmabrief');
    seedBackup(projectRoot, 'sigmabrief');
    const stateDir = getProjectStateDir(projectRoot);
    fs.writeFileSync(path.join(stateDir, UNINSTALL_JOURNAL_FILENAME), '{}\n', 'utf8');
    fs.mkdirSync(path.join(stateDir, '.sigma-uninstall-staging', 'leftover'), { recursive: true });
    fs.writeFileSync(
      path.join(projectRoot, 'skills-lock.json.generic-keep'),
      'ignore',
      'utf8',
    );
    const result = executePurge({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      confirmPurge: PURGE_CONFIRMATION_PHRASE,
    });
    assert.equal(result.dryRun, false);
    assert.equal(result.command, 'purge');
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite')), false);
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite', '.claude/skills')), false);
    assert.equal(pathExists(skillDir(projectRoot, 'sigmabrief')), false);
    assert.equal(pathExists(getBackupRoot(stateDir)), false);
    assert.equal(pathExists(path.join(stateDir, UNINSTALL_JOURNAL_FILENAME)), false);
    assert.equal(pathExists(path.join(stateDir, PURGE_JOURNAL_FILENAME)), false);
    assert.equal(pathExists(path.join(stateDir, PURGE_QUARANTINE_DIRNAME)), false);
    assert.equal(pathExists(path.join(stateDir, 'state.json')), false);
    assert.equal(pathExists(path.join(projectRoot, 'skills-lock.json')), false);
    assert.equal(pathExists(path.join(projectRoot, 'skills-lock.json.generic-keep')), true);
    assert.ok(result.items.some((item) => item.method === LINK_METHOD || item.kind === 'link'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('purge: crash during quarantine restores live trees; crash after quarantine is retryable', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-purge-crash-'));
  try {
    installWrite(projectRoot, 'sigmawrite');
    installWrite(projectRoot, 'sigmabrief');
    const writeBefore = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8');
    const briefBefore = fs.readFileSync(path.join(skillDir(projectRoot, 'sigmabrief'), 'SKILL.md'), 'utf8');

    assert.throws(
      () => executePurge({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        confirmPurge: PURGE_CONFIRMATION_PHRASE,
        afterQuarantineItem: (item) => {
          if (item.skillId === 'sigmawrite') throw new Error('injected purge quarantine crash');
        },
      }),
      /injected purge quarantine crash/,
    );
    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmawrite'), 'SKILL.md'), 'utf8'), writeBefore);
    assert.equal(fs.readFileSync(path.join(skillDir(projectRoot, 'sigmabrief'), 'SKILL.md'), 'utf8'), briefBefore);
    assert.ok(readState(projectRoot).skills.sigmawrite);
    assert.ok(readLock(projectRoot).skills.sigmawrite);

    assert.throws(
      () => executePurge({
        catalog: getCatalog(ROOT),
        projectRoot,
        packageRoot: ROOT,
        confirmPurge: PURGE_CONFIRMATION_PHRASE,
        afterQuarantine: () => {
          throw new Error('injected purge cleanup crash');
        },
      }),
      /injected purge cleanup crash/,
    );
    const stateDir = getProjectStateDir(projectRoot);
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite')), false);
    assert.equal(pathExists(path.join(stateDir, 'state.json')), true);
    assert.ok(
      pathExists(path.join(stateDir, PURGE_JOURNAL_FILENAME))
      || pathExists(path.join(stateDir, PURGE_QUARANTINE_DIRNAME, PURGE_JOURNAL_FILENAME)),
    );
    assert.equal(pathExists(path.join(stateDir, PURGE_QUARANTINE_DIRNAME)), true);

    const retried = executePurge({
      catalog: getCatalog(ROOT),
      projectRoot,
      packageRoot: ROOT,
      confirmPurge: PURGE_CONFIRMATION_PHRASE,
    });
    assert.equal(retried.resumed, true);
    assert.equal(pathExists(skillDir(projectRoot, 'sigmawrite')), false);
    assert.equal(pathExists(skillDir(projectRoot, 'sigmabrief')), false);
    assert.equal(pathExists(path.join(stateDir, PURGE_QUARANTINE_DIRNAME)), false);
    assert.equal(pathExists(path.join(stateDir, 'state.json')), false);
    assert.equal(pathExists(path.join(projectRoot, 'skills-lock.json')), false);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('packed CLI covers cancellation, wrong phrase, crash retry, and complete purge', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-pack-purge-'));
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
    const listed = execFileSync('tar', ['-tf', tarballFileName], { cwd: tmpDir, encoding: 'utf8' });
    assert.match(listed, /package\/src\/purge\.js/);

    const project = path.join(tmpDir, 'proj');
    execFileSync('node', [installedBin, 'install', 'sigmawrite', '--project', project], {
      cwd: appDir,
      encoding: 'utf8',
    });
    const dest = path.join(project, '.agents', 'skills', 'sigmawrite');
    const stranger = path.join(project, '.claude', 'skills', 'sigmawrite');
    fs.mkdirSync(stranger, { recursive: true });
    fs.writeFileSync(path.join(stranger, 'leave-me.txt'), 'unrelated', 'utf8');

    try {
      execFileSync('node', [installedBin, 'purge', '--confirm-purge=', '--project', project], {
        cwd: appDir,
        encoding: 'utf8',
      });
      assert.fail('expected packed cancellation');
    } catch (err) {
      assert.match(String(err.stderr || err.message), /cancel/i);
    }
    assert.equal(pathExists(dest), true);

    try {
      execFileSync(
        'node',
        [installedBin, 'purge', '--confirm-purge', 'wrong phrase', '--project', project],
        { cwd: appDir, encoding: 'utf8' },
      );
      assert.fail('expected packed wrong phrase');
    } catch (err) {
      assert.match(String(err.stderr || err.message), /phrase|confirm/i);
    }
    assert.equal(pathExists(dest), true);

    const packedPurge = pathToFileURLSafe(path.join(packedRoot, 'src', 'purge.js'));
    const packedCatalog = pathToFileURLSafe(path.join(packedRoot, 'src', 'catalog.js'));
    execFileSync(process.execPath, ['--input-type=module', '-e', `
      import { getCatalog } from ${JSON.stringify(packedCatalog)};
      import { executePurge, PURGE_CONFIRMATION_PHRASE } from ${JSON.stringify(packedPurge)};
      const packageRoot = ${JSON.stringify(packedRoot)};
      try {
        executePurge({
          catalog: getCatalog(packageRoot),
          projectRoot: ${JSON.stringify(project)},
          packageRoot,
          confirmPurge: PURGE_CONFIRMATION_PHRASE,
          afterQuarantine: () => { throw new Error('packed crash point'); },
        });
      } catch (err) {
        if (!String(err.message).includes('packed crash point')) throw err;
      }
    `], { cwd: appDir, encoding: 'utf8' });
    assert.equal(pathExists(path.join(project, '.agents', PURGE_QUARANTINE_DIRNAME)), true);

    execFileSync(
      'node',
      [installedBin, 'purge', '--confirm-purge', PURGE_CONFIRMATION_PHRASE, '--project', project],
      { cwd: appDir, encoding: 'utf8' },
    );
    assert.equal(pathExists(dest), false);
    assert.equal(fs.readFileSync(path.join(stranger, 'leave-me.txt'), 'utf8'), 'unrelated');
    assert.equal(pathExists(path.join(project, '.agents', 'state.json')), false);
    assert.equal(pathExists(path.join(project, 'skills-lock.json')), false);
    assert.ok(fs.existsSync(path.join(packedRoot, 'src', 'purge.js')));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

function pathToFileURLSafe(filePath) {
  const abs = path.resolve(filePath);
  const posixPath = abs.replace(/\\/g, '/');
  return posixPath.startsWith('/') ? `file://${posixPath}` : `file:///${posixPath}`;
}
