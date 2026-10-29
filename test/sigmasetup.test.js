import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { blockReason, install, remove, status } from '../sigmasetup/scripts/git-guard.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const guide = join(root, 'sigmasetup', 'references', 'packs');

test('git guard blocks commands that destroy work, also behind git global options', () => {
  for (const cmd of [
    'git push --force origin main',
    'git push -f',
    'git push origin +main',
    'git push --force-with-lease',
    'git -C ../other push --force',
    'git -c core.x=1 reset --hard HEAD~1',
    'git clean -fd',
    'git checkout -- .',
    'git restore .',
    'cd repo && git reset --hard',
    'git.exe push -uf origin x',
  ]) assert.ok(blockReason(cmd), `should block: ${cmd}`);
});

test('git guard allows normal work and branch cleanup after a squash merge', () => {
  for (const cmd of [
    'git push origin feat/x',
    'git push -u origin feat/x',
    'git push origin --delete feat/x',
    'git branch -D feat/x',
    'git branch -d feat/x',
    'git reset --soft HEAD~1',
    'git restore --staged .',
    'git checkout main',
    'git worktree remove ../wt',
    'git commit -m "docs; git reset --hard is blocked"',
  ]) assert.equal(blockReason(cmd), null, `should allow: ${cmd}`);
});

test('git guard install and remove touch only their own entry and refuse the home folder', () => {
  const dir = fs.mkdtempSync(join(os.tmpdir(), 'sigmasetup-'));
  const settings = join(dir, '.claude', 'settings.json');
  fs.mkdirSync(join(dir, '.claude'));
  const before = { model: 'opus', hooks: { PreToolUse: [{ matcher: 'Bash', hooks: [{ type: 'command', command: 'other' }] }] } };
  fs.writeFileSync(settings, JSON.stringify(before));

  install(dir);
  install(dir);
  const on = JSON.parse(fs.readFileSync(settings, 'utf8'));
  assert.equal(on.hooks.PreToolUse.length, 2, 'install twice adds one entry');
  assert.equal(status(dir), 'git guard on');

  const hook = join(dir, '.claude', 'hooks', 'sigma-git-guard.mjs');
  const blocked = spawnSync(process.execPath, [hook], { input: JSON.stringify({ tool_input: { command: 'git push --force' } }), encoding: 'utf8' });
  assert.equal(blocked.status, 2);
  assert.match(blocked.stderr, /BLOCKED/);
  const allowed = spawnSync(process.execPath, [hook], { input: JSON.stringify({ tool_input: { command: 'git branch -D x' } }), encoding: 'utf8' });
  assert.equal(allowed.status, 0);

  remove(dir);
  assert.deepEqual(JSON.parse(fs.readFileSync(settings, 'utf8')), before);
  assert.equal(fs.existsSync(hook), false);
  assert.equal(status(dir), 'git guard off');

  assert.throws(() => install(os.homedir()), /never global/);
  if (process.platform === 'win32') assert.throws(() => install(os.homedir().toLowerCase()), /never global/);

  const typo = spawnSync(process.execPath, [hook, 'uninstall', dir], { encoding: 'utf8', timeout: 5000 });
  assert.equal(typo.status, 1, 'an unknown mode fails fast instead of waiting on stdin');

  const bare = fs.mkdtempSync(join(os.tmpdir(), 'sigmasetup-'));
  install(bare);
  remove(bare);
  assert.deepEqual(fs.readdirSync(bare), [], 'remove leaves no empty .claude folder behind');
  fs.rmSync(bare, { recursive: true, force: true });
  fs.rmSync(dir, { recursive: true, force: true });
});

// The pre-merge rule: every pack the installer offers has a setup guide, and the Sigma guide covers every Sigma skill.
test('sigmasetup has a setup guide for every installer pack and every Sigma skill', () => {
  const packs = JSON.parse(fs.readFileSync(join(root, 'registry', 'packs.json'), 'utf8')).packs.map((p) => p.id);
  for (const id of packs) {
    assert.ok(fs.existsSync(join(guide, `${id}.md`)), `sigmasetup/references/packs/${id}.md is missing: add a setup guide for the "${id}" pack`);
  }
  const extra = fs.readdirSync(guide).map((f) => f.replace(/\.md$/, '')).filter((id) => !packs.includes(id));
  assert.deepEqual(extra, [], 'a guide names a pack the installer does not offer');
  const sigma = fs.readFileSync(join(guide, 'sigma.md'), 'utf8');
  const manifest = JSON.parse(fs.readFileSync(join(root, 'manifest.json'), 'utf8'));
  for (const { id } of manifest.skills) {
    assert.match(sigma, new RegExp(`^### ${id}$`, 'm'), `sigmasetup/references/packs/sigma.md has no "### ${id}" section`);
  }
});
