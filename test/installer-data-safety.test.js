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
