import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { runCli } from '../src/cli.js';

function makeDirs() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-safety-'));
  const project = path.join(base, 'project');
  const home = path.join(base, 'home');
  fs.mkdirSync(project);
  fs.mkdirSync(home);
  return { base, project, home };
}

async function run(dirs, args) {
  let stdout = '';
  let stderr = '';
  const env = { ...process.env, HOME: dirs.home, USERPROFILE: dirs.home };
  const code = await runCli([...args, '--project', dirs.project], {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    env,
  });
  return { code, stdout, stderr };
}

function withDirs(fn) {
  return async () => {
    const dirs = makeDirs();
    try {
      await fn(dirs);
    } finally {
      fs.rmSync(dirs.base, { recursive: true, force: true });
    }
  };
}

const GENERIC_LOCK = JSON.stringify({
  version: 1,
  skills: { 'acme-skill': { source: 'acme/repo', sourceType: 'github', computedHash: 'abc123' } },
}, null, 2) + '\n';

test('A1: generic skills-lock.json stays byte-identical through install, restore, and uninstall', withDirs(async (dirs) => {
  const lockPath = path.join(dirs.project, 'skills-lock.json');
  fs.writeFileSync(lockPath, GENERIC_LOCK);

  let r = await run(dirs, ['install', 'sigmawrite', '--destination', '.agents/skills', '--destination', '.claude/skills', '--copy']);
  assert.equal(r.code, 0, r.stderr);
  assert.match(r.stdout, /skills-lock\.json left alone because another tool owns it/);
  assert.equal(fs.readFileSync(lockPath, 'utf8'), GENERIC_LOCK);

  r = await run(dirs, ['install', 'sigmabrief', 'sigmareview']);
  assert.equal(r.code, 0, r.stderr);
  assert.equal(fs.readFileSync(lockPath, 'utf8'), GENERIC_LOCK);

  fs.writeFileSync(path.join(dirs.project, '.agents', 'skills', 'sigmawrite', 'EDIT.txt'), 'x');
  r = await run(dirs, ['uninstall', '--skill', 'sigmawrite', '--changed', 'backup', '--yes']);
  assert.equal(r.code, 0, r.stderr);
  assert.equal(fs.readFileSync(lockPath, 'utf8'), GENERIC_LOCK);

  r = await run(dirs, ['restore', '--skill', 'sigmawrite', '--yes']);
  assert.equal(r.code, 0, r.stderr);
  assert.equal(fs.readFileSync(lockPath, 'utf8'), GENERIC_LOCK);

  r = await run(dirs, ['uninstall', '--all', '--yes']);
  assert.equal(r.code, 0, r.stderr);
  assert.equal(fs.readFileSync(lockPath, 'utf8'), GENERIC_LOCK);
}));

function readStateFile(project) {
  const statePath = path.join(project, '.agents', '.sigmaskills', 'state.json');
  return { statePath, state: JSON.parse(fs.readFileSync(statePath, 'utf8')) };
}

test('A2: a crafted ../victim destination in state is rejected and never removed', withDirs(async (dirs) => {
  const victim = path.join(dirs.base, 'victim');
  fs.mkdirSync(victim);
  fs.writeFileSync(path.join(victim, 'precious.txt'), 'keep me');

  let r = await run(dirs, ['install', 'sigmawrite']);
  assert.equal(r.code, 0, r.stderr);
  const { statePath, state } = readStateFile(dirs.project);
  const entry = state.skills.sigmawrite;
  entry.destination = '../victim';
  entry.copies = [{ kind: 'canonical', destination: '../victim', method: 'copy', hostIds: [], ownedPaths: [] }];
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2));

  r = await run(dirs, ['uninstall', '--all', '--yes']);
  assert.notEqual(r.code, 0);
  assert.match(r.stderr, /escapes/);
  assert.equal(fs.readFileSync(path.join(victim, 'precious.txt'), 'utf8'), 'keep me');
}));

test('A2: a crafted purge journal path outside the project is rejected and never removed', withDirs(async (dirs) => {
  const victim = path.join(dirs.base, 'victim');
  fs.mkdirSync(victim);
  fs.writeFileSync(path.join(victim, 'precious.txt'), 'keep me');

  let r = await run(dirs, ['install', 'sigmawrite']);
  assert.equal(r.code, 0, r.stderr);
  const stateDir = path.join(dirs.project, '.agents', '.sigmaskills');
  fs.writeFileSync(path.join(stateDir, 'purge-journal.json'), JSON.stringify({
    schemaVersion: 1,
    command: 'purge',
    scope: 'project',
    status: 'quarantined',
    quarantineDir: '../victim',
    items: [{ kind: 'manifest', relative: 'x', absolutePath: victim, status: 'pending' }],
    skills: [],
  }));

  r = await run(dirs, ['purge', '--confirm-purge', 'purge SigmaSkills']);
  assert.notEqual(r.code, 0);
  assert.match(r.stderr, /escapes/);
  assert.equal(fs.readFileSync(path.join(victim, 'precious.txt'), 'utf8'), 'keep me');
}));
