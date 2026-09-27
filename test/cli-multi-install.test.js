import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { findPackageRoot, getCatalog } from '../src/catalog.js';
import { saveProjectState } from '../src/state.js';
import { executeProjectInstallBatch } from '../src/transaction.js';

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

function tempProject(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-multi-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

test('cli: unknown skill ids fail with unknown skill before planning, for every command', async (t) => {
  const projectRoot = tempProject(t);
  const commands = [
    ['install', 'sigmawrite', 'nope', '--yes'],
    ['add', 'nope'],
    ['install', '--skill', 'nope', '--dry-run'],
    ['update', '--skill', 'nope', '--yes'],
    ['restore', '--skill', 'nope', '--yes'],
    ['uninstall', '--skill', 'nope', '--yes'],
    ['uninstall', 'nope', '--dry-run'],
  ];
  for (const args of commands) {
    const io = createMockIo();
    const code = await runCli([...args, '--project', projectRoot], io);
    assert.equal(code, 1, args.join(' '));
    assert.match(io.getStderr(), /sigmaskills error: unknown skill 'nope'/, args.join(' '));
    assert.doesNotMatch(io.getStderr(), /stale-state/);
    assert.equal(io.getStdout(), '', args.join(' '));
    assert.deepEqual(fs.readdirSync(projectRoot), [], args.join(' '));
  }
});

test('cli: uninstall still accepts a retired skill id', async (t) => {
  const projectRoot = tempProject(t);
  const io = createMockIo();
  await runCli(['uninstall', '--skill', 'sigmaperformance', '--dry-run', '--project', projectRoot], io);
  assert.doesNotMatch(io.getStderr(), /unknown skill/);
});

function countLockWrites(t) {
  const original = fs.writeFileSync;
  let count = 0;
  fs.writeFileSync = function patched(file, ...rest) {
    if (path.basename(String(file)).startsWith('skills-lock.json')) count += 1;
    return original.call(this, file, ...rest);
  };
  t.after(() => { fs.writeFileSync = original; });
  return () => count;
}

function readLock(projectRoot) {
  return JSON.parse(fs.readFileSync(path.join(projectRoot, 'skills-lock.json'), 'utf8'));
}

test('cli: install a b c installs every skill and writes the lock once', async (t) => {
  const projectRoot = tempProject(t);
  const lockWrites = countLockWrites(t);
  const io = createMockIo();
  const code = await runCli(['install', 'sigmawrite', 'sigmareview', 'sigmabrief', '--project', projectRoot], io);

  assert.equal(code, 0, io.getStderr());
  assert.equal(lockWrites(), 1);
  assert.deepEqual(Object.keys(readLock(projectRoot).skills), ['sigmabrief', 'sigmareview', 'sigmawrite']);
  for (const id of ['sigmawrite', 'sigmareview', 'sigmabrief']) {
    assert.ok(fs.existsSync(path.join(projectRoot, '.agents', 'skills', id, 'SKILL.md')), id);
    assert.match(io.getStdout(), new RegExp(`Installed .* \\(${id}\\)`));
  }
});

test('cli: install --all installs every shipped skill and writes the lock once', async (t) => {
  const projectRoot = tempProject(t);
  const catalogIo = createMockIo();
  await runCli(['list', '--json'], catalogIo);
  const allIds = JSON.parse(catalogIo.getStdout()).skills.map((skill) => skill.id).sort();
  const lockWrites = countLockWrites(t);

  const io = createMockIo();
  const code = await runCli(['install', '--all', '--project', projectRoot], io);

  assert.equal(code, 0, io.getStderr());
  assert.equal(lockWrites(), 1);
  assert.deepEqual(Object.keys(readLock(projectRoot).skills), allIds);
});

test('cli: install --all cannot be combined with skill ids', async (t) => {
  const projectRoot = tempProject(t);
  const io = createMockIo();
  const code = await runCli(['install', '--all', 'sigmawrite', '--project', projectRoot], io);
  assert.equal(code, 1);
  assert.match(io.getStderr(), /install --all cannot be combined with skill ids/);
  assert.deepEqual(fs.readdirSync(projectRoot), []);
});

test('cli: multi-skill dry run is read-only; JSON lists one plan per skill', async (t) => {
  const projectRoot = tempProject(t);
  const io = createMockIo();
  const code = await runCli(['install', 'sigmawrite', 'sigmabrief', '--dry-run', '--project', projectRoot], io);
  assert.equal(code, 0, io.getStderr());
  assert.match(io.getStdout(), /Plan: SigmaWrite/);
  assert.match(io.getStdout(), /Plan: SigmaBrief/);

  const jsonIo = createMockIo();
  assert.equal(await runCli(['install', 'sigmawrite', 'sigmabrief', '--dry-run', '--json', '--project', projectRoot], jsonIo), 0);
  const parsed = JSON.parse(jsonIo.getStdout());
  assert.equal(parsed.schemaVersion, 1);
  assert.deepEqual(parsed.plans.map((plan) => plan.skill), ['sigmawrite', 'sigmabrief']);
  assert.ok(parsed.plans.every((plan) => plan.dryRun === true));
  assert.deepEqual(fs.readdirSync(projectRoot), []);
});

test('cli: a blocked skill stops a multi-skill install before any write', async (t) => {
  const projectRoot = tempProject(t);
  const stranger = path.join(projectRoot, '.agents', 'skills', 'sigmabrief');
  fs.mkdirSync(stranger, { recursive: true });
  fs.writeFileSync(path.join(stranger, 'notes.txt'), 'not sigma', 'utf8');

  const io = createMockIo();
  const code = await runCli(['install', 'sigmawrite', 'sigmabrief', '--project', projectRoot], io);

  assert.equal(code, 1);
  assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite')));
  assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
  assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', '.sigmaskills')));
});

function snapshotTree(root) {
  const out = {};
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else out[path.relative(root, full)] = fs.readFileSync(full, 'utf8');
    }
  };
  walk(root);
  return out;
}

test('transaction: a failure in a later skill rolls back every skill in the batch', async (t) => {
  const projectRoot = tempProject(t);
  assert.equal(await runCli(['install', 'sigmabrief', '--project', projectRoot], createMockIo()), 0);
  const before = snapshotTree(projectRoot);
  const packageRoot = findPackageRoot();

  let saves = 0;
  assert.throws(() => executeProjectInstallBatch({
    catalog: getCatalog(packageRoot),
    packageRoot,
    projectRoot,
    skillIds: ['sigmawrite', 'sigmareview'],
    saveState: (root, state, dir) => {
      saves += 1;
      if (saves === 2) throw new Error('simulated state write failure');
      saveProjectState(root, state, dir);
    },
  }), /simulated state write failure/);

  assert.equal(saves, 2);
  assert.deepEqual(snapshotTree(projectRoot), before);
});

test('cli: install a b --global --yes installs both skills and writes no project lock', async (t) => {
  const homeDir = tempProject(t);
  const projectRoot = tempProject(t);
  const io = { ...createMockIo(), env: { ...process.env, HOME: homeDir, USERPROFILE: homeDir } };
  const code = await runCli(['install', 'sigmawrite', 'sigmabrief', '--global', '--yes', '--project', projectRoot], io);

  assert.equal(code, 0, io.getStderr());
  for (const id of ['sigmawrite', 'sigmabrief']) {
    assert.ok(fs.existsSync(path.join(homeDir, '.agents', 'skills', id, 'SKILL.md')), id);
  }
  assert.deepEqual(fs.readdirSync(projectRoot), []);
});

test('cli: install a b migrates an old-layout project once, then installs both', async (t) => {
  const projectRoot = tempProject(t);
  assert.equal(await runCli(['install', 'sigmabrief', '--project', projectRoot], createMockIo()), 0);
  const agents = path.join(projectRoot, '.agents');
  const stateDir = path.join(agents, '.sigmaskills');
  for (const name of fs.readdirSync(stateDir)) {
    if (name !== '.gitignore') fs.renameSync(path.join(stateDir, name), path.join(agents, name));
  }
  fs.rmSync(stateDir, { recursive: true, force: true });

  const io = createMockIo();
  const code = await runCli(['install', 'sigmawrite', 'sigmareview', '--project', projectRoot], io);

  assert.equal(code, 0, io.getStderr());
  assert.ok(!fs.existsSync(path.join(agents, 'state.json')));
  const state = JSON.parse(fs.readFileSync(path.join(stateDir, 'state.json'), 'utf8'));
  assert.deepEqual(Object.keys(state.skills).sort(), ['sigmabrief', 'sigmareview', 'sigmawrite']);
  assert.deepEqual(Object.keys(readLock(projectRoot).skills), ['sigmabrief', 'sigmareview', 'sigmawrite']);
});
