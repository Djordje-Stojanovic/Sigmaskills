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
    'git checkout -f main',
    'git switch --discard-changes main',
    'git stash clear',
    'git stash drop',
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
    'git checkout -b feat/x',
    'git switch -c feat/x',
    'git stash',
    'git stash pop',
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

  // Antigravity: .agents/hooks.json gets one named hook; the decision comes back as JSON on stdout.
  const agyHooks = JSON.parse(fs.readFileSync(join(dir, '.agents', 'hooks.json'), 'utf8'));
  assert.equal(agyHooks['sigma-git-guard'].PreToolUse[0].matcher, 'run_command');
  const agyHook = join(dir, '.agents', 'hooks', 'sigma-git-guard.mjs');
  const agyCall = (CommandLine) => JSON.parse(spawnSync(process.execPath, [agyHook], { input: JSON.stringify({ toolCall: { name: 'run_command', args: { CommandLine } } }), encoding: 'utf8' }).stdout);
  assert.equal(agyCall('git -C x reset --hard').decision, 'deny');
  assert.match(agyCall('git -C x reset --hard').reason, /\.agents\/hooks/);
  assert.equal(agyCall('git status').decision, 'allow');
  fs.writeFileSync(join(dir, '.agents', 'hooks.json'), JSON.stringify({ lint: { Stop: [] }, ...agyHooks }));

  remove(dir);
  assert.deepEqual(JSON.parse(fs.readFileSync(join(dir, '.agents', 'hooks.json'), 'utf8')), { lint: { Stop: [] } });
  assert.equal(fs.existsSync(agyHook), false);
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

test('house files: check finds drift, apply syncs copies and sections in one go, undo puts everything back', async () => {
  const { personalLines, readConfig, plan, apply, undo } = await import('../sigmasetup/scripts/house.mjs');
  const tmp = fs.mkdtempSync(join(os.tmpdir(), 'sigmasetup-house-'));
  const masters = join(tmp, 'masters');
  const repo = join(tmp, 'repo');
  fs.mkdirSync(join(masters, 'docs'), { recursive: true });
  fs.mkdirSync(repo);
  fs.writeFileSync(join(masters, 'ENGINEERING.md'), '# Engineering\n\nQuestion, delete, simplify.\n');
  fs.writeFileSync(join(masters, 'docs', 'HOW.md'), 'how\n');
  fs.writeFileSync(join(masters, 'AGENTS.md'), '# Master\n\n## How we work\n\n- Rule one.\n- Rule two.\n\n## Other\n\nmaster only\n');
  fs.writeFileSync(join(repo, 'ENGINEERING.md'), '# Engineering\n\nold\n');
  const agents = '# Repo\r\n\r\nOwn intro.\r\n\r\n## How we work\r\n\r\n- Rule one.\r\n- Repo rule.\r\n\r\n## Build\r\n\r\nnpm test\r\n';
  fs.writeFileSync(join(repo, 'AGENTS.md'), agents);

  const block = '## Personal instructions\n\n<sigmaskills-custom>\n- house: x\ncopy: ENGINEERING.md\ncopy: docs/HOW.md -> docs/HOW_WE_WORK.md\nsection: AGENTS.md#How we work\nseed: T.md -> CLAUDE.md\n</sigmaskills-custom>\n';
  const config = readConfig(personalLines(block));
  assert.equal(config.source, 'x');
  assert.deepEqual(config.map.map((r) => `${r.kind} ${r.to}`), ['copy ENGINEERING.md', 'copy docs/HOW_WE_WORK.md', 'section AGENTS.md', 'seed CLAUDE.md']);
  assert.equal(readConfig([]).map.length, 3, 'no map lines: the default map runs');

  const rows = plan(repo, masters, config.map);
  assert.deepEqual(rows.map((r) => r.state), ['drift', 'missing', 'drift', 'no master']);
  assert.deepEqual(rows[2].kept, ['- Repo rule.'], 'a repo-only line in the section is kept and reported');

  apply(repo, rows, ['docs/HOW_WE_WORK.md']);
  assert.equal(fs.readFileSync(join(repo, 'ENGINEERING.md'), 'utf8'), fs.readFileSync(join(masters, 'ENGINEERING.md'), 'utf8'));
  assert.equal(fs.readFileSync(join(repo, 'docs', 'HOW_WE_WORK.md'), 'utf8'), 'how\n');
  const merged = fs.readFileSync(join(repo, 'AGENTS.md'), 'utf8');
  assert.equal(merged, '# Repo\r\n\r\nOwn intro.\r\n\r\n## How we work\r\n\r\n- Rule one.\r\n- Rule two.\r\n\r\n- Repo rule.\r\n\r\n## Build\r\n\r\nnpm test\r\n', 'only the section changes, in the repo file\'s line endings');
  assert.ok(plan(repo, masters, config.map).slice(0, 3).every((r) => r.state === 'current'), 'a second check is clean');
  assert.equal(plan(repo, masters, config.map, true)[2].state, 'drift', '--exact drops the repo-only line');

  const done = undo(repo);
  assert.deepEqual(done, { changed: ['ENGINEERING.md', 'AGENTS.md'], created: ['docs/HOW_WE_WORK.md'] });
  assert.equal(fs.readFileSync(join(repo, 'AGENTS.md'), 'utf8'), agents);
  assert.equal(fs.readFileSync(join(repo, 'ENGINEERING.md'), 'utf8'), '# Engineering\n\nold\n');
  assert.equal(fs.existsSync(join(repo, 'docs', 'HOW_WE_WORK.md')), false);
  assert.equal(undo(repo), null, 'nothing left to undo');

  // A repo with only CLAUDE.md gets the section there, not a new AGENTS.md.
  const solo = join(tmp, 'solo');
  fs.mkdirSync(solo);
  fs.writeFileSync(join(solo, 'CLAUDE.md'), '# Solo\n');
  const [row] = plan(solo, masters, readConfig(['section: AGENTS.md#How we work']).map);
  assert.equal(row.file, 'CLAUDE.md');
  assert.equal(row.state, 'missing');
  fs.rmSync(tmp, { recursive: true, force: true });
});

test('house files: a line the master dropped leaves the copy; a repo-only line stays', async () => {
  const { plan } = await import('../sigmasetup/scripts/house.mjs');
  const tmp = fs.mkdtempSync(join(os.tmpdir(), 'sigmasetup-dropped-'));
  const masters = join(tmp, 'masters');
  const repo = join(tmp, 'repo');
  fs.mkdirSync(masters);
  fs.mkdirSync(repo);
  const git = (...args) => assert.equal(spawnSync('git', ['-C', masters, '-c', 'user.name=t', '-c', 'user.email=t@t', ...args], { encoding: 'utf8' }).status, 0, args.join(' '));
  git('init', '-q');
  fs.writeFileSync(join(masters, 'AGENTS.md'), '## How we work\n\n- Rule one.\n- Plan content on the planner.\n');
  git('add', 'AGENTS.md');
  git('commit', '-q', '-m', 'one');
  fs.writeFileSync(join(masters, 'AGENTS.md'), '## How we work\n\n- Rule one.\n');
  git('commit', '-q', '-am', 'two');
  fs.writeFileSync(join(repo, 'AGENTS.md'), '## How we work\n\n- Rule one.\n- Plan content on the planner.\n- Repo rule.\n');
  const [row] = plan(repo, masters, [{ kind: 'section', from: 'AGENTS.md', heading: 'How we work', to: 'AGENTS.md' }]);
  assert.deepEqual(row.kept, ['- Repo rule.'], 'the dropped master line is not repo-only');
  assert.equal(row.next, '## How we work\n\n- Rule one.\n\n- Repo rule.\n');
  fs.rmSync(tmp, { recursive: true, force: true });
});

test('house files: a repo with no map gets no missing house file unasked, DESIGN.md least of all', async () => {
  const { readConfig, plan, apply } = await import('../sigmasetup/scripts/house.mjs');
  const tmp = fs.mkdtempSync(join(os.tmpdir(), 'sigmasetup-empty-'));
  const masters = join(tmp, 'masters');
  const repo = join(tmp, 'repo');
  fs.mkdirSync(masters);
  fs.mkdirSync(repo);
  fs.writeFileSync(join(masters, 'DESIGN.md'), '# Another project\n');
  fs.writeFileSync(join(masters, 'ENGINEERING.md'), '# Engineering\n');
  fs.writeFileSync(join(masters, 'AGENTS.md'), '# M\n\n## How we work\n\n- Rule.\n');
  const rows = plan(repo, masters, readConfig([]).map);
  assert.deepEqual(rows.map((r) => r.state), ['missing', 'missing', 'missing']);
  assert.equal(apply(repo, rows), null, 'nothing written without a yes');
  assert.deepEqual(fs.readdirSync(repo), []);
  apply(repo, rows, ['ENGINEERING.md']);
  assert.deepEqual(fs.readdirSync(repo).filter((f) => !f.startsWith('.')), ['ENGINEERING.md'], 'only the file he said yes to');
  fs.rmSync(tmp, { recursive: true, force: true });
});

test('house.mjs runs when its folder is reached through a symlink or junction', (t) => {
  const tmp = fs.mkdtempSync(join(os.tmpdir(), 'sigmasetup-link-'));
  const link = join(tmp, 'scripts');
  try {
    fs.symlinkSync(join(root, 'sigmasetup', 'scripts'), link, process.platform === 'win32' ? 'junction' : 'dir');
  } catch (err) {
    fs.rmSync(tmp, { recursive: true, force: true });
    t.skip(`skipped: no symlink right (${err.code})`);
    return;
  }
  const masters = join(tmp, 'masters');
  fs.mkdirSync(masters);
  fs.writeFileSync(join(masters, 'ENGINEERING.md'), '# E\n');
  const run = spawnSync(process.execPath, [join(link, 'house.mjs'), 'check', tmp, '--source', masters], { encoding: 'utf8' });
  fs.unlinkSync(link); // the link only, never what it points at
  fs.rmSync(tmp, { recursive: true, force: true });
  assert.match(run.stdout, /House source:/, `ran silently: ${run.stderr}`);
});
