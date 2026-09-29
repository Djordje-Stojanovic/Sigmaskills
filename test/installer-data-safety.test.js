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

test('A3: restore stops on an unowned host destination and keeps the user files there', withDirs(async (dirs) => {
  let r = await run(dirs, ['install', 'sigmawrite', '--destination', '.agents/skills', '--destination', '.claude/skills', '--copy']);
  assert.equal(r.code, 0, r.stderr);
  for (const root of ['.agents', '.claude']) {
    fs.writeFileSync(path.join(dirs.project, root, 'skills', 'sigmawrite', 'EDIT.txt'), 'x');
  }
  r = await run(dirs, ['uninstall', '--all', '--yes']);
  assert.equal(r.code, 0, r.stderr);

  const host = path.join(dirs.project, '.claude', 'skills', 'sigmawrite');
  fs.mkdirSync(host, { recursive: true });
  fs.writeFileSync(path.join(host, 'MINE.md'), 'unrelated user skill content');

  r = await run(dirs, ['restore', '--skill', 'sigmawrite', '--yes']);
  assert.notEqual(r.code, 0);
  assert.match(r.stderr, /occupied-unowned/);
  assert.deepEqual(fs.readdirSync(host), ['MINE.md']);
  assert.equal(fs.readFileSync(path.join(host, 'MINE.md'), 'utf8'), 'unrelated user skill content');
}));

test('A4: a foreign .agents/state.json and .agents/backups are left alone and install succeeds', withDirs(async (dirs) => {
  const agents = path.join(dirs.project, '.agents');
  fs.mkdirSync(path.join(agents, 'backups'), { recursive: true });
  const foreignState = JSON.stringify({ other: 'tool', data: [1, 2, 3] });
  fs.writeFileSync(path.join(agents, 'state.json'), foreignState);
  fs.writeFileSync(path.join(agents, 'backups', 'mine.txt'), 'other tool backup');

  const r = await run(dirs, ['install', 'sigmawrite']);
  assert.equal(r.code, 0, r.stderr);
  assert.equal(fs.readFileSync(path.join(agents, 'state.json'), 'utf8'), foreignState);
  assert.equal(fs.readFileSync(path.join(agents, 'backups', 'mine.txt'), 'utf8'), 'other tool backup');
  assert.ok(fs.existsSync(path.join(agents, '.sigmaskills', 'state.json')));
  assert.ok(!fs.existsSync(path.join(agents, '.sigmaskills', 'backups', 'mine.txt')));
}));

test('A6: reinstalling over an owned link with the wrong target never reports Installed with exit 0', withDirs(async (dirs) => {
  let r = await run(dirs, ['install', 'sigmawrite', '--destination', '.claude/skills']);
  assert.equal(r.code, 0, r.stderr);

  const link = path.join(dirs.project, '.claude', 'skills', 'sigmawrite');
  const other = path.join(dirs.project, 'other');
  fs.mkdirSync(other);
  fs.writeFileSync(path.join(other, 'x'), 'x');
  fs.unlinkSync(link);
  fs.symlinkSync(other, link, 'junction');

  r = await run(dirs, ['install', 'sigmawrite', '--destination', '.claude/skills']);
  const repaired = fs.realpathSync(link) === fs.realpathSync(path.join(dirs.project, '.agents', 'skills', 'sigmawrite'));
  if (r.code === 0) {
    assert.ok(repaired, 'exit 0 needs a repaired link');
  } else {
    assert.match(r.stderr, /wrong-target/);
    assert.ok(!/Installed/.test(r.stdout));
  }
  assert.ok(fs.existsSync(path.join(other, 'x')));
}));

test('A7: status, update, and uninstall agree on a link a user added inside a skill', withDirs(async (dirs) => {
  let r = await run(dirs, ['install', 'sigmawrite']);
  assert.equal(r.code, 0, r.stderr);
  const skill = path.join(dirs.project, '.agents', 'skills', 'sigmawrite');
  const external = path.join(dirs.project, 'external-data');
  fs.mkdirSync(external);
  fs.writeFileSync(path.join(external, 'keep.txt'), 'external');
  fs.symlinkSync(external, path.join(skill, 'extlink'), 'junction');

  r = await run(dirs, ['status']);
  assert.match(r.stdout, /Drift:\s+Yes/);
  assert.match(r.stdout, /Classification:\s+outside-addition/);

  r = await run(dirs, ['update', '--dry-run']);
  assert.match(r.stdout, /\[local-only\]/);

  r = await run(dirs, ['uninstall', '--all', '--yes']);
  assert.doesNotMatch(r.stdout, /Review: clean/);
  assert.ok(fs.existsSync(path.join(external, 'keep.txt')));
}));
