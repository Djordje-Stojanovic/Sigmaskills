import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { isCiEnv } from '../src/interactive.js';

function makeDirs() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-small-'));
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

const NEWER_LOCK = `${JSON.stringify({
  schemaVersion: 2,
  release: '9.9.9',
  skills: { sigmareview: { revision: 'abc' } },
  futureField: { a: 1 },
}, null, 2)}\n`;

test('A9: a project lock with a newer schemaVersion fails the install without a write', withDirs(async (dirs) => {
  const lockPath = path.join(dirs.project, 'skills-lock.json');
  fs.writeFileSync(lockPath, NEWER_LOCK);

  const failed = await run(dirs, ['install', 'sigmawrite']);
  assert.notEqual(failed.code, 0);
  assert.match(failed.stderr, /schemaVersion 2.*newer|newer.*schemaVersion 2/i);
  assert.equal(fs.readFileSync(lockPath, 'utf8'), NEWER_LOCK);
  assert.equal(fs.existsSync(path.join(dirs.project, '.agents', 'skills', 'sigmawrite')), false);
}));

test('A10: replacing a changed skill keeps a CRLF customization block byte for byte', withDirs(async (dirs) => {
  assert.equal((await run(dirs, ['install', 'sigmawrite'])).code, 0);
  const skillDir = path.join(dirs.project, '.agents', 'skills', 'sigmawrite');
  const skillMd = path.join(skillDir, 'SKILL.md');
  const raw = '\r\nmy rule\r\nsecond\r\n';
  const block = /<sigmaskills-custom>[\s\S]*<\/sigmaskills-custom>/;
  fs.writeFileSync(skillMd, fs.readFileSync(skillMd, 'utf8').replace(block, () => `<sigmaskills-custom>${raw}</sigmaskills-custom>`));
  fs.writeFileSync(path.join(skillDir, 'EXTRA.txt'), 'x');

  const replaced = await run(dirs, ['install', 'sigmawrite', '--adopt-changed', 'replace']);
  assert.equal(replaced.code, 0, replaced.stderr);
  assert.equal(fs.existsSync(path.join(skillDir, 'EXTRA.txt')), false);
  const after = /<sigmaskills-custom>([\s\S]*)<\/sigmaskills-custom>/.exec(fs.readFileSync(skillMd, 'utf8'));
  assert.equal(after[1], raw);
}));

test('A12: CI counts only when set and not empty, 0, or false in any case', () => {
  for (const value of ['1', 'true', 'TRUE', 'yes', 'github']) assert.equal(isCiEnv({ CI: value }), true, value);
  for (const value of [undefined, '', '0', 'false', 'False', 'FALSE']) assert.equal(isCiEnv({ CI: value }), false, String(value));
  assert.equal(isCiEnv({}), false);
});
