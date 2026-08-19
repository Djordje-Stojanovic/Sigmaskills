import assert from 'node:assert/strict';
import { execFileSync, execSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { pathToFileURL } from 'node:url';
import { findPackageRoot } from '../src/catalog.js';
import { inspectManagedPath, recommendedLinkMethod } from '../src/links.js';
import { computeSkillRevision } from '../src/revision.js';

const ROOT = findPackageRoot();
const LINK_METHOD = recommendedLinkMethod();
const SKILL_IDS = JSON.parse(fs.readFileSync(path.join(ROOT, 'manifest.json'), 'utf8')).skills.map((skill) => skill.id);
const FORBIDDEN_PREFIXES = [
  'package/test/',
  'package/docs/',
  'package/.github/',
  'package/.agents/',
  'package/.cursor/',
  'package/.git/',
  'package/.scratch/',
];
const SECRET_PATTERN = /(^|\/)\.env($|\.)|(^|\/)\.env\.|(^|\/)id_rsa$|\.(pem|key)$|(^|\/)credentials\.json$/i;

function snapshot(root) {
  const files = {};
  const walk = (dir, prefix = '') => {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = path.join(dir, entry.name);
      if (entry.isSymbolicLink()) files[rel] = `link:${fs.readlinkSync(full)}`;
      else if (entry.isDirectory()) walk(full, rel);
      else if (entry.isFile()) files[rel] = fs.readFileSync(full);
    }
  };
  walk(root);
  return files;
}

function walkFiles(dir, prefix = '') {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkFiles(full, rel));
    else if (entry.isFile()) out.push(rel.replace(/\\/g, '/'));
  }
  return out;
}

function offlineEnv(extra = {}) {
  return {
    ...process.env,
    ...extra,
    http_proxy: 'http://127.0.0.1:9',
    https_proxy: 'http://127.0.0.1:9',
    HTTP_PROXY: 'http://127.0.0.1:9',
    HTTPS_PROXY: 'http://127.0.0.1:9',
    NO_PROXY: '*',
  };
}

function runCli(bin, args, options = {}) {
  return execFileSync(process.execPath, [bin, ...args], {
    cwd: options.cwd,
    encoding: 'utf8',
    env: options.env || process.env,
    input: options.input,
    timeout: options.timeout || 60_000,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
}

function runCliFail(bin, args, options = {}) {
  try {
    runCli(bin, args, options);
    assert.fail(`expected packed CLI to fail: ${args.join(' ')}`);
  } catch (err) {
    if (err.code === 'ERR_ASSERTION') throw err;
    return `${err.stderr || ''}${err.stdout || ''}${err.message || ''}`;
  }
}

function listTarball(tmpDir, tarballFileName) {
  return execFileSync('tar', ['-tf', tarballFileName], { cwd: tmpDir, encoding: 'utf8' })
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/\\/g, '/'))
    .filter(Boolean);
}

test('packed Release candidate covers lifecycle, platforms, terminals, schemas, allowlist, identities, and offline use', async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rc-'));
  try {
    const packOutput = execSync(`npm pack --pack-destination "${tmpDir}"`, {
      cwd: ROOT,
      encoding: 'utf8',
    }).trim();
    const tarballFileName = packOutput.split(/\r?\n/).pop()?.trim();
    assert.ok(tarballFileName, 'expected tarball filename from npm pack');
    const tarballPath = path.join(tmpDir, tarballFileName);
    const packedFiles = listTarball(tmpDir, tarballFileName);

    const pkgAllowlist = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')).files;
    const expectedSrc = walkFiles(path.join(ROOT, 'src')).map((rel) => `package/src/${rel}`);
    const expectedSkills = SKILL_IDS.flatMap((id) => (
      walkFiles(path.join(ROOT, id)).map((rel) => `package/${id}/${rel}`)
    ));
    for (const req of [
      'package/package.json',
      'package/manifest.json',
      'package/bin/sigmaskills.js',
      'package/registry/agent-hosts.json',
      'package/registry/source.json',
      'package/registry/schema.json',
      'package/registry/skill-baselines.json',
      ...expectedSrc,
      ...expectedSkills,
    ]) {
      assert.ok(packedFiles.includes(req), `tarball missing required resource: ${req}`);
    }
    for (const file of packedFiles) {
      if (file === 'package/package.json') continue;
      const rel = file.slice('package/'.length);
      const allowed = pkgAllowlist.some((entry) => rel === entry || rel.startsWith(`${entry}/`));
      assert.ok(allowed, `tarball contains file outside package.json files allowlist: ${file}`);
      for (const prefix of FORBIDDEN_PREFIXES) {
        assert.ok(!file.startsWith(prefix), `tarball contains development path ${file}`);
      }
      assert.ok(!SECRET_PATTERN.test(rel), `tarball contains secret or local file ${file}`);
    }

    const appDir = path.join(tmpDir, 'app');
    fs.mkdirSync(appDir, { recursive: true });
    execSync('npm init -y', { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    execSync(`npm install "${tarballPath}"`, { cwd: appDir, encoding: 'utf8', stdio: 'pipe' });
    const packedRoot = path.join(appDir, 'node_modules', 'sigmaskills');
    const bin = path.join(packedRoot, 'bin', 'sigmaskills.js');
    const offline = offlineEnv({ HOME: path.join(tmpDir, 'offline-home'), USERPROFILE: path.join(tmpDir, 'offline-home') });

    const packedPkg = JSON.parse(fs.readFileSync(path.join(packedRoot, 'package.json'), 'utf8'));
    const packedManifest = JSON.parse(fs.readFileSync(path.join(packedRoot, 'manifest.json'), 'utf8'));
    assert.equal(packedPkg.version, packedManifest.version);
    const listed = JSON.parse(runCli(bin, ['list', '--json'], { cwd: appDir, env: offline }));
    assert.equal(listed.version, packedPkg.version);
    assert.equal(listed.name, packedManifest.name);
    for (const skill of listed.skills) {
      assert.equal(skill.revision, computeSkillRevision(path.join(packedRoot, skill.id)));
    }

    const { executeRelease } = await import(pathToFileURL(path.join(packedRoot, 'src', 'release.js')).href);
    const preview = executeRelease({
      rootDir: packedRoot,
      dryRun: true,
      git: {
        revParse: () => 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        show() { throw new Error('use working tree identities'); },
        statusPorcelain: () => '',
      },
      pack: () => ({
        filename: tarballFileName,
        digest: 'ab'.repeat(32),
        integrity: 'sha512-packed',
        contents: packedFiles,
      }),
      workflow: { ok: true },
      probes: {
        npmPackage: { exists: true, versions: {} },
        githubRelease: null,
        gitTag: null,
        environment: { name: 'release', protected: true },
        trustedPublisher: true,
      },
    });
    assert.equal(preview.command, 'release');
    assert.equal(preview.dryRun, true);
    assert.match(String(preview.npmPackage), new RegExp(`^${packedPkg.name}(?:@|$)`));
    assert.equal(preview.skills.length, listed.skills.length);
    for (const skill of preview.skills) {
      const fromList = listed.skills.find((item) => item.id === skill.id);
      assert.equal(skill.revision, fromList.revision);
    }
    assert.equal(preview.tarball.digest, 'ab'.repeat(32));
    assert.equal(preview.gate.ok, true);
    assert.equal(packedPkg.version, packedManifest.version);
    assert.ok(preview.version === packedPkg.version || Boolean(preview.bump));

    const noFetch = /fetch\(|https?:\/\/|undici|\bdns\b/;
    for (const rel of ['src/cli.js', 'src/transaction.js', 'src/adoption.js', 'src/status.js', 'src/uninstall.js', 'src/restore.js']) {
      assert.doesNotMatch(fs.readFileSync(path.join(packedRoot, rel), 'utf8'), noFetch);
    }

    const project = path.join(tmpDir, 'proj');
    const adoptDest = path.join(project, '.agents', 'skills', 'sigmawrite');
    fs.cpSync(path.join(packedRoot, 'sigmawrite'), adoptDest, { recursive: true });
    const adoptBefore = fs.readFileSync(path.join(adoptDest, 'SKILL.md'));
    runCli(bin, ['install', 'sigmawrite', '--project', project, '--json'], { cwd: appDir, env: offline });
    assert.deepEqual(fs.readFileSync(path.join(adoptDest, 'SKILL.md')), adoptBefore);

    const linkOut = runCli(bin, [
      'install', 'sigmabrief',
      '--project', project,
      '--destination', '.claude/skills',
    ], { cwd: appDir, env: offline });
    assert.match(linkOut, new RegExp(LINK_METHOD));
    const hostLink = path.join(project, '.claude', 'skills', 'sigmabrief');
    const linkInfo = inspectManagedPath(hostLink, path.join(project, '.agents', 'skills', 'sigmabrief'));
    assert.equal(linkInfo.method, LINK_METHOD);
    assert.equal(linkInfo.broken, false);
    assert.equal(linkInfo.wrongTarget, false);

    const copyProject = path.join(tmpDir, 'copy-proj');
    runCli(bin, [
      'install', 'sigmawrite',
      '--project', copyProject,
      '--destination', '.claude/skills',
      '--copy',
    ], { cwd: appDir, env: offline });
    const copyHost = path.join(copyProject, '.claude', 'skills', 'sigmawrite');
    assert.equal(fs.lstatSync(copyHost).isSymbolicLink(), false);

    const dry = JSON.parse(runCli(bin, [
      'install', 'sigmabrief', '--dry-run', '--json', '--project', path.join(tmpDir, 'dry-proj'),
    ], { cwd: appDir, env: offline }));
    assert.equal(dry.dryRun, true);
    assert.ok(!fs.existsSync(path.join(tmpDir, 'dry-proj', '.agents')));

    const statusBefore = snapshot(project);
    const statusJson = JSON.parse(runCli(bin, ['status', '--json', '--project', project], { cwd: appDir, env: offline }));
    assert.equal(statusJson.command, 'status');
    assert.equal(statusJson.readOnly, true);
    assert.deepEqual(snapshot(project), statusBefore);

    fs.writeFileSync(path.join(adoptDest, 'outside-edit.md'), 'unsafe local', 'utf8');
    const unsafeBefore = snapshot(project);
    const unsafeOut = runCliFail(bin, ['update', '--yes', '--project', project], { cwd: appDir, env: offline });
    assert.match(unsafeOut, /outside edits|--outside-edit|unsafe/i);
    assert.deepEqual(snapshot(project), unsafeBefore);

    runCli(bin, ['update', '--yes', '--outside-edit', 'replace', '--project', project], { cwd: appDir, env: offline });
    assert.ok(!fs.existsSync(path.join(adoptDest, 'outside-edit.md')));

    const restoreDry = JSON.parse(runCli(bin, [
      'restore', '--skill', 'sigmawrite', '--dry-run', '--json', '--project', project,
    ], { cwd: appDir, env: offline }));
    assert.equal(restoreDry.dryRun, true);
    runCli(bin, ['restore', '--skill', 'sigmawrite', '--yes', '--project', project], { cwd: appDir, env: offline });
    assert.ok(fs.existsSync(path.join(adoptDest, 'outside-edit.md')));

    runCli(bin, ['uninstall', '--skill', 'sigmabrief', '--yes', '--project', project], { cwd: appDir, env: offline });
    assert.ok(!fs.existsSync(path.join(project, '.agents', 'skills', 'sigmabrief')));

    runCli(bin, ['install', 'sigmabrief', '--project', project], { cwd: appDir, env: offline });
    runCli(bin, ['uninstall', '--all', '--yes', '--project', project], { cwd: appDir, env: offline });
    const afterAll = JSON.parse(fs.readFileSync(path.join(project, '.agents', 'state.json'), 'utf8'));
    assert.deepEqual(afterAll.skills, {});

    runCli(bin, ['install', 'sigmawrite', '--project', project], { cwd: appDir, env: offline });
    runCli(bin, [
      'purge', '--confirm-purge', 'purge SigmaSkills', '--project', project,
    ], { cwd: appDir, env: offline });
    assert.ok(!fs.existsSync(path.join(project, '.agents', 'skills', 'sigmawrite')));

    const schemaProject = path.join(tmpDir, 'schema-proj');
    runCli(bin, ['install', 'sigmawrite', '--project', schemaProject], { cwd: appDir, env: offline });
    const schemaPath = path.join(schemaProject, '.agents', 'state.json');
    const schemaState = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
    schemaState.schemaVersion = 99;
    fs.writeFileSync(schemaPath, `${JSON.stringify(schemaState, null, 2)}\n`);
    const schemaBefore = snapshot(schemaProject);
    const schemaFail = runCliFail(bin, ['install', 'sigmabrief', '--project', schemaProject], { cwd: appDir, env: offline });
    assert.match(schemaFail, /schemaVersion 99|unsupported/i);
    assert.deepEqual(snapshot(schemaProject), schemaBefore);
    const statusFail = runCliFail(bin, ['status', '--project', schemaProject], { cwd: appDir, env: offline });
    assert.match(statusFail, /schemaVersion 99|unsupported/i);
    assert.deepEqual(snapshot(schemaProject), schemaBefore);
    const updateFail = runCliFail(bin, ['update', '--yes', '--project', schemaProject], { cwd: appDir, env: offline });
    assert.match(updateFail, /schemaVersion 99|unsupported/i);
    assert.deepEqual(snapshot(schemaProject), schemaBefore);

    const homeDir = path.join(tmpDir, 'home');
    fs.mkdirSync(homeDir, { recursive: true });
    const globalEnv = offlineEnv({ HOME: homeDir, USERPROFILE: homeDir });
    runCli(bin, ['install', 'sigmawrite', '--global', '--yes'], { cwd: appDir, env: globalEnv });
    const globalStatePath = path.join(homeDir, '.agents', 'state.json');
    const globalState = JSON.parse(fs.readFileSync(globalStatePath, 'utf8'));
    globalState.skills.sigmawrite.lastBackup = 'backups/sigmawrite/kept-ref';
    const migrated = {
      schemaVersion: 0,
      skills: {
        sigmawrite: {
          ...globalState.skills.sigmawrite,
          backup: globalState.skills.sigmawrite.lastBackup,
        },
      },
    };
    delete migrated.skills.sigmawrite.lastBackup;
    fs.writeFileSync(globalStatePath, `${JSON.stringify(migrated, null, 2)}\n`);
    const globalStatus = JSON.parse(runCli(bin, ['status', '--json', '--global'], { cwd: appDir, env: globalEnv }));
    assert.equal(globalStatus.scope, 'global');
    runCli(bin, ['install', 'sigmabrief', '--global', '--yes'], { cwd: appDir, env: globalEnv });
    const afterMigrate = JSON.parse(fs.readFileSync(globalStatePath, 'utf8'));
    assert.equal(afterMigrate.schemaVersion, 1);
    assert.equal(afterMigrate.skills.sigmawrite.lastBackup, 'backups/sigmawrite/kept-ref');
    assert.deepEqual(afterMigrate.skills.sigmawrite.ownedPaths, globalState.skills.sigmawrite.ownedPaths);
    assert.ok(afterMigrate.skills.sigmabrief);

    const interactiveProject = path.join(tmpDir, 'interactive');
    fs.mkdirSync(interactiveProject, { recursive: true });
    const cancelOut = runCli(bin, [
      '--static', '--no-color', '--narrow', '--project', interactiveProject,
    ], { cwd: appDir, env: { ...offline, CI: '', NO_COLOR: '', REDUCED_MOTION: '1' }, input: '\x1b' });
    assert.match(cancelOut, /narrow/i);
    assert.match(cancelOut, /cancelled/i);
    assert.doesNotMatch(cancelOut, /\x1b\[/);
    assert.ok(!fs.existsSync(path.join(interactiveProject, '.agents', 'skills')));

    const reducedOut = runCli(bin, ['--static', '--project', path.join(tmpDir, 'reduced')], {
      cwd: appDir,
      env: { ...offline, CI: '', REDUCED_MOTION: '1', PREFERS_REDUCED_MOTION: 'reduce' },
      input: '\x1b',
    });
    assert.doesNotMatch(reducedOut, /\x1b\[\?25l/);

    const interruptProject = path.join(tmpDir, 'interrupt');
    fs.mkdirSync(interruptProject, { recursive: true });
    const interruptCode = await new Promise((resolve, reject) => {
      const child = spawn(process.execPath, [bin, '--static', '--project', interruptProject], {
        cwd: appDir,
        env: { ...offline, CI: '' },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      const timer = setTimeout(() => {
        child.kill('SIGKILL');
        reject(new Error('packed interrupt timed out'));
      }, 15_000);
      child.stdin.write('\x03');
      child.stdin.end();
      child.on('error', (err) => {
        clearTimeout(timer);
        reject(err);
      });
      child.on('exit', (code, signal) => {
        clearTimeout(timer);
        resolve(signal || code);
      });
    });
    assert.ok(interruptCode === 130 || interruptCode === 'SIGINT' || interruptCode === 1);
    assert.ok(!fs.existsSync(path.join(interruptProject, '.agents', 'skills')));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
