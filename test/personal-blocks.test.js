// Issue #407: personal instructions live in one file per skill outside every skill folder and reach every copy.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { findPackageRoot, getCatalog } from '../src/catalog.js';
import { computeSkillRevisionAndHashes } from '../src/revision.js';
import { runCli } from '../src/cli.js';
import { collectStatus } from '../src/status.js';
import { executeProjectInstall } from '../src/transaction.js';
import { executeUpdate } from '../src/update.js';

const ROOT = findPackageRoot();
const SKILL = 'sigmawrite';
const BOTH = ['--destination', '.agents/skills', '--destination', '.claude/skills', '--copy'];
const BLOCK = /<sigmaskills-custom>([\s\S]*)<\/sigmaskills-custom>/;

function withProject(fn) {
  return async () => {
    const base = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-personal-'));
    const project = path.join(base, 'p');
    const home = path.join(base, 'h');
    fs.mkdirSync(project);
    fs.mkdirSync(home);
    try {
      await fn({ project, home });
    } finally {
      fs.rmSync(base, { recursive: true, force: true });
    }
  };
}

async function cli(t, args) {
  let out = '';
  const io = { stdout: { write: (s) => { out += s; } }, stderr: { write: (s) => { out += s; } }, env: { ...process.env, HOME: t.home, USERPROFILE: t.home } };
  const code = await runCli([...args, '--project', t.project], io);
  return { code, out };
}

const md = (t, root, skill = SKILL) => path.join(t.project, ...root.split('/'), skill, 'SKILL.md');
const canonical = (t) => md(t, '.agents/skills');
const copy = (t) => md(t, '.claude/skills');
const personalFile = (t) => path.join(t.project, '.agents', '.sigmaskills', 'custom', `${SKILL}.md`);
const blockOf = (file) => BLOCK.exec(fs.readFileSync(file, 'utf8'))[1];
const setBlock = (file, raw) => fs.writeFileSync(file, fs.readFileSync(file, 'utf8').replace(BLOCK, () => `<sigmaskills-custom>${raw}</sigmaskills-custom>`));
const sha = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const SEVEN = '\nl1\nl2\nl3\nl4\nl5\nl6\nl7\n';

async function installBoth(t) {
  const r = await cli(t, ['install', SKILL, ...BOTH, '--yes']);
  assert.equal(r.code, 0, r.out);
}

// The installed copies look like an older Release: update then has an upstream change to apply.
function ageBoth(t) {
  for (const file of [canonical(t), copy(t)]) {
    fs.writeFileSync(file, fs.readFileSync(file, 'utf8').replace('## Personal instructions', '<!-- sigma-older -->\n\n## Personal instructions'));
  }
  const hashes = computeSkillRevisionAndHashes(path.dirname(canonical(t)));
  const statePath = path.join(t.project, '.agents', '.sigmaskills', 'state.json');
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  const entry = state.skills[SKILL];
  Object.assign(entry, { baseHashes: hashes.files, revision: hashes.revision, release: '0.0.9' });
  for (const item of entry.copies) if (item.baseHashes) item.baseHashes = hashes.files;
  fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
  const lockPath = path.join(t.project, 'skills-lock.json');
  const lock = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
  lock.skills[SKILL].revision = hashes.revision;
  lock.release = '0.0.9';
  fs.writeFileSync(lockPath, `${JSON.stringify(lock, null, 2)}\n`);
}

test('#407 (1) an existing empty copy is filled on update, and the lines move to one file outside the skill folders', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nmy rule\n');
  const r = await cli(t, ['update', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.equal(blockOf(copy(t)), '\nmy rule\n');
  assert.equal(fs.readFileSync(personalFile(t), 'utf8'), 'my rule\n');
}));

test('#407 (1) install --adopt-changed replace on an edited copy drops the edit and fills the block', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nmy rule\n');
  fs.writeFileSync(copy(t), fs.readFileSync(copy(t), 'utf8').replace('## Personal instructions', 'outside edit\n\n## Personal instructions'));
  const r = await cli(t, ['install', SKILL, ...BOTH, '--adopt-changed', 'replace', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.equal(fs.readFileSync(copy(t), 'utf8').includes('outside edit'), false);
  assert.equal(blockOf(copy(t)), '\nmy rule\n');
  assert.equal(blockOf(canonical(t)), '\nmy rule\n');
}));

for (const [label, copyBlock] of [['an empty block', '\n'], ['its own valid block', '\nown rule\n']]) {
  test(`#407 (2) the upgrade does not stop on copy-disagreement when a recorded copy has ${label}`, withProject(async (t) => {
    await installBoth(t);
    ageBoth(t);
    setBlock(canonical(t), '\nmy rule\n');
    setBlock(copy(t), copyBlock);
    const r = await cli(t, ['update', '--yes']);
    assert.equal(r.code, 0, r.out);
    for (const file of [canonical(t), copy(t)]) {
      assert.equal(fs.readFileSync(file, 'utf8').includes('<!-- sigma-older -->'), false, file);
      assert.equal(blockOf(file), '\nmy rule\n', file);
    }
    const saved = fs.readdirSync(path.dirname(personalFile(t))).filter((name) => name.startsWith(`${SKILL}.saved-`));
    if (copyBlock === '\n') assert.deepEqual(saved, []);
    // A copy's own different lines are never lost: they are kept byte for byte beside the file.
    else assert.equal(fs.readFileSync(path.join(path.dirname(personalFile(t)), saved[0]), 'utf8'), '\nown rule\n');
  }));
}

test('#407 (3) skip choices write nothing into a copy that has no install record', withProject(async (t) => {
  assert.equal((await cli(t, ['install', SKILL, '--yes'])).code, 0);
  setBlock(canonical(t), '\nmy rule\n');
  const stranger = path.dirname(copy(t));
  fs.cpSync(path.dirname(canonical(t)), stranger, { recursive: true });
  setBlock(copy(t), '\n');
  const before = sha(copy(t));
  const r = await cli(t, ['install', SKILL, ...BOTH, '--adopt-changed', 'skip', '--adopt-unverified', 'skip', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.equal(sha(copy(t)), before);
}));

test('#407 (4) a failed run restores every file it wrote, adopted copies and the personal file too', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nmy rule\n');
  const before = { canonical: sha(canonical(t)), copy: sha(copy(t)) };
  assert.throws(() => executeProjectInstall({
    catalog: getCatalog(ROOT),
    skillId: SKILL,
    projectRoot: t.project,
    homeDir: t.home,
    packageRoot: ROOT,
    selectedRoots: ['.agents/skills', '.claude/skills', '.cursor/skills'],
    method: 'copy',
    adoptChanged: 'skip',
    saveState: () => { throw new Error('injected saveState failure'); },
  }), /injected saveState failure/);
  assert.deepEqual({ canonical: sha(canonical(t)), copy: sha(copy(t)) }, before);
  assert.equal(fs.existsSync(md(t, '.cursor/skills')), false);
  assert.equal(fs.existsSync(personalFile(t)), false);
}));

test('#407 (5) a copy with CRLF line endings is no outside change and gets the block in CRLF', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nmy rule\n');
  fs.writeFileSync(copy(t), fs.readFileSync(copy(t), 'utf8').replace(/\r?\n/g, '\r\n'));
  const r = await cli(t, ['update', '--yes']);
  assert.equal(r.code, 0, r.out);
  const text = fs.readFileSync(copy(t), 'utf8');
  assert.equal(blockOf(copy(t)), '\r\nmy rule\r\n');
  assert.equal(/[^\r]\n/.test(text), false, 'the copy stays CRLF');
  const report = collectStatus({ catalog: getCatalog(ROOT), projectRoot: t.project, packageRoot: ROOT, scope: 'project' });
  const kinds = report.skills[0].destinations.flatMap((dest) => dest.classifications);
  assert.equal(kinds.includes('outside-change'), false, kinds.join());
  assert.equal(kinds.includes('copy-disagreement'), false, kinds.join());
}));

test('#407 (6) after a second update a personal block is no drift', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nmy rule\n');
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  const report = collectStatus({ catalog: getCatalog(ROOT), projectRoot: t.project, packageRoot: ROOT, scope: 'project' });
  for (const dest of report.skills[0].destinations) assert.deepEqual(dest.classifications, ['valid-customization']);
  assert.equal(report.drift, false);
}));

test('#407 a replace run never empties a block, and the backup it reports holds the old tree', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), SEVEN);
  const replaceInstall = ['install', SKILL, ...BOTH, '--adopt-legacy', 'replace', '--adopt-changed', 'replace', '--adopt-unverified', 'replace', '--outside-edit', 'replace', '--malformed-markers', 'replace', '--yes'];
  const replaceUpdate = ['update', '--yes', '--outside-edit', 'replace', '--malformed-markers', 'replace'];
  for (let round = 0; round < 2; round += 1) {
    assert.equal((await cli(t, replaceInstall)).code, 0);
    assert.equal((await cli(t, replaceUpdate)).code, 0);
    for (const file of [canonical(t), copy(t)]) assert.equal(blockOf(file), SEVEN, `round ${round} ${file}`);
  }
  // Broken markers make the update replace the file with the bundled one; the lines come back from the personal file.
  fs.writeFileSync(canonical(t), fs.readFileSync(canonical(t), 'utf8').replace('<sigmaskills-custom>', '<sigmaskills-custom>\n<sigmaskills-custom>'));
  const result = executeUpdate({ catalog: getCatalog(ROOT), projectRoot: t.project, packageRoot: ROOT, malformedMarkers: 'replace' });
  for (const file of [canonical(t), copy(t)]) assert.equal(blockOf(file), SEVEN, file);
  const backup = result.results.find((item) => item.id === SKILL)?.backupIntegrity?.path;
  assert.ok(backup && fs.existsSync(path.join(backup, 'SKILL.md')), 'the reported backup exists');
  assert.ok(fs.readFileSync(path.join(backup, 'SKILL.md'), 'utf8').includes('l7'));
}));

test('#407 an empty canonical block invents nothing and writes nothing', withProject(async (t) => {
  await installBoth(t);
  const before = { canonical: sha(canonical(t)), copy: sha(copy(t)) };
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  assert.deepEqual({ canonical: sha(canonical(t)), copy: sha(copy(t)) }, before);
  assert.equal(fs.existsSync(personalFile(t)), false);
}));

test('#407 marker-like text round-trips, and a real marker in the personal file is refused, not rendered', withProject(async (t) => {
  await installBoth(t);
  const lines = '\nWrap with <sigmaskills-customization> tags.\nKeep </sigmaskills-custom-x> literal.\n';
  setBlock(canonical(t), lines);
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  assert.equal(blockOf(copy(t)), lines);

  fs.writeFileSync(personalFile(t), 'broken </sigmaskills-custom> line\n');
  const before = { canonical: sha(canonical(t)), copy: sha(copy(t)) };
  const r = await cli(t, ['update', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, /marker/i);
  assert.deepEqual({ canonical: sha(canonical(t)), copy: sha(copy(t)) }, before);
}));

test('#407 an edit to the personal file reaches every copy; an edit in a block reaches the file', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nfirst\n');
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  fs.writeFileSync(personalFile(t), 'second\n');
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  for (const file of [canonical(t), copy(t)]) assert.equal(blockOf(file), '\nsecond\n');
  setBlock(copy(t), '\nthird\n');
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  assert.equal(fs.readFileSync(personalFile(t), 'utf8'), 'third\n');
  assert.equal(blockOf(canonical(t)), '\nthird\n');
}));

test('#407 one replace run over two folders of a skill keeps both backups (the empty backup folder on Windows)', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), SEVEN);
  for (const file of [canonical(t), copy(t)]) {
    fs.writeFileSync(file, fs.readFileSync(file, 'utf8').replace('## Personal instructions', 'outside edit\n\n## Personal instructions'));
  }
  const r = await cli(t, ['install', SKILL, ...BOTH, '--adopt-changed', 'replace', '--yes']);
  assert.equal(r.code, 0, r.out);
  const dir = path.join(t.project, '.agents', '.sigmaskills', 'backups', SKILL);
  const kept = fs.readdirSync(dir).filter((name) => fs.existsSync(path.join(dir, name, 'SKILL.md')));
  assert.equal(kept.length, 2, `backups: ${fs.readdirSync(dir).join(', ')}`);
  for (const name of kept) assert.ok(fs.readFileSync(path.join(dir, name, 'SKILL.md'), 'utf8').includes('outside edit'));
  for (const file of [canonical(t), copy(t)]) assert.equal(blockOf(file), SEVEN, file);
}));

// Review round 1 of PR #416.
const stderrOf = (r) => r.out;

test('#407 r1-1 purge as the first command keeps the lines in the personal file', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), SEVEN);
  const r = await cli(t, ['purge', '--confirm-purge', 'purge SigmaSkills']);
  assert.equal(r.code, 0, r.out);
  assert.equal(fs.existsSync(canonical(t)), false);
  assert.equal(fs.readFileSync(personalFile(t), 'utf8'), 'l1\nl2\nl3\nl4\nl5\nl6\nl7\n');
}));

test('#407 r1-1 uninstall with delete keeps the lines in the personal file', withProject(async (t) => {
  await installBoth(t);
  setBlock(copy(t), '\nonly in the copy\n');
  const r = await cli(t, ['uninstall', '--skill', SKILL, '--yes', '--clean', 'remove', '--changed', 'delete']);
  assert.equal(r.code, 0, r.out);
  assert.equal(fs.existsSync(copy(t)), false);
  assert.equal(fs.readFileSync(personalFile(t), 'utf8'), 'only in the copy\n');
}));

test('#407 r1-4 a reinstall for one host keeps the other recorded copies and writes them', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nfirst\n');
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  fs.writeFileSync(personalFile(t), 'second\n');
  const r = await cli(t, ['install', SKILL, '--destination', '.agents/skills', '--adopt-changed', 'replace', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.equal(blockOf(copy(t)), '\nsecond\n');
  const report = collectStatus({ catalog: getCatalog(ROOT), projectRoot: t.project, packageRoot: ROOT, scope: 'project' });
  assert.ok(report.skills[0].destinations.some((dest) => dest.relativeDestination === '.claude/skills/sigmawrite'));
}));

test('#407 r1-5 a missing personal file is rebuilt from the blocks; an empty one empties the copies', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nkeep me\n');
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  fs.rmSync(personalFile(t));
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  assert.equal(fs.readFileSync(personalFile(t), 'utf8'), 'keep me\n');
  const r = await cli(t, ['install', SKILL, '--destination', '.agents/skills', '--destination', '.claude/skills', '--destination', '.cursor/skills', '--copy', '--adopt-changed', 'skip', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.equal(blockOf(md(t, '.cursor/skills')), '\nkeep me\n');
  fs.writeFileSync(personalFile(t), '');
  assert.equal((await cli(t, ['update', '--yes'])).code, 0);
  for (const file of [canonical(t), copy(t), md(t, '.cursor/skills')]) assert.equal(blockOf(file), '\n', file);
}));

test('#407 r1-6 a replace that saves a block, and a refused render, both print the path', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nmine\n');
  setBlock(copy(t), '\nother\n');
  let r = await cli(t, ['install', SKILL, ...BOTH, '--adopt-changed', 'replace', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.match(stderrOf(r), /saved byte for byte to .*sigmawrite\.saved-/);
  fs.writeFileSync(personalFile(t), 'x </sigmaskills-custom> y\n');
  r = await cli(t, ['install', SKILL, ...BOTH, '--adopt-changed', 'skip', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.match(stderrOf(r), /marker; its lines were not written/);
  assert.ok(stderrOf(r).includes(personalFile(t)));
}));

test('#407 r1-2 r1-7 a saved block keeps its exact bytes and is written once, also on a retry', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nmine\n');
  setBlock(copy(t), '\n\n  spaced  \n\n');
  const { syncPersonalBlocks } = await import('../src/personal.js');
  const stateDir = path.join(t.project, '.agents', '.sigmaskills');
  const folders = [path.dirname(canonical(t)), path.dirname(copy(t))];
  for (let run = 0; run < 2; run += 1) syncPersonalBlocks({ stateDir, skillId: SKILL, read: folders });
  const dir = path.dirname(personalFile(t));
  const saved = fs.readdirSync(dir).filter((name) => name.startsWith(`${SKILL}.saved-`));
  assert.equal(saved.length, 1, saved.join());
  assert.equal(fs.readFileSync(path.join(dir, saved[0]), 'utf8'), '\n\n  spaced  \n\n');
  assert.equal(fs.readFileSync(personalFile(t), 'utf8'), 'mine\n', 'a retry does not flip the file to the saved lines');
}));

test('#407 r1-8 the personal folder is 0700 and its files 0600', { skip: process.platform === 'win32' }, withProject(async (t) => {
  const old = process.umask(0o022);
  try {
    await installBoth(t);
    setBlock(canonical(t), '\nmine\n');
    setBlock(copy(t), '\nother\n');
    assert.equal((await cli(t, ['update', '--yes'])).code, 0);
    const dir = path.dirname(personalFile(t));
    assert.equal(fs.statSync(dir).mode & 0o777, 0o700);
    for (const name of fs.readdirSync(dir)) assert.equal(fs.statSync(path.join(dir, name)).mode & 0o777, 0o600, name);
  } finally {
    process.umask(old);
  }
}));

test('#407 r1-3 an update whose state save fails converges on the next run', withProject(async (t) => {
  await installBoth(t);
  ageBoth(t);
  setBlock(canonical(t), '\nmy rule\n');
  assert.throws(() => executeUpdate({
    catalog: getCatalog(ROOT), projectRoot: t.project, homeDir: t.home, packageRoot: ROOT,
    saveState: () => { throw new Error('injected saveState failure'); },
  }), /injected saveState failure/);
  const r = await cli(t, ['update', '--yes']);
  assert.equal(r.code, 0, r.out);
  for (const file of [canonical(t), copy(t)]) {
    assert.equal(blockOf(file), '\nmy rule\n', file);
    assert.equal(fs.readFileSync(file, 'utf8').includes('<!-- sigma-older -->'), false, file);
  }
  const report = collectStatus({ catalog: getCatalog(ROOT), projectRoot: t.project, packageRoot: ROOT, scope: 'project' });
  assert.equal(report.drift, false);
}));

test('#407 r1-10 install --json leaves the personal lines out', withProject(async (t) => {
  await installBoth(t);
  setBlock(canonical(t), '\nsecret-ish line\n');
  const r = await cli(t, ['install', SKILL, ...BOTH, '--adopt-changed', 'skip', '--json', '--yes']);
  assert.equal(r.code, 0, r.out);
  assert.equal(r.out.includes('secret-ish line'), false);
}));
