import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { CORE_PACKS } from '../src/packs.js';
import { createMockIo, createRemote, createSandbox, writeSkills, writeUserConfig } from './pack-fixtures.js';

const GIT = ['-c', 'user.email=test@example.com', '-c', 'user.name=Test', '-c', 'commit.gpgsign=false'];
const git = (cwd, ...args) => execFileSync('git', [...GIT, ...args], { cwd, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8' });

const pack = (id, skills) => ({
  id, title: id, blurb: 'Test pack.',
  sources: [{ type: 'git', repo: `t/${id}`, path: 'skills', skills: skills.map((s) => ({ id: s, description: `${s} skill.` })) }],
});

/** Every path under `dir` with its bytes (a link: its target), so two snapshots compare byte for byte. */
function snapshot(dir) {
  const out = {};
  const walk = (rel) => {
    const abs = path.join(dir, rel);
    const st = fs.lstatSync(abs);
    if (st.isSymbolicLink()) out[rel] = `link:${fs.readlinkSync(abs)}`;
    else if (st.isDirectory()) for (const name of fs.readdirSync(abs).sort()) walk(path.join(rel, name));
    else out[rel] = fs.readFileSync(abs).toString('base64');
  };
  if (fs.existsSync(dir)) walk('');
  return out;
}

/** Repo A (the target), repo B with its own committed skill, and a global skills folder the owner filled by hand. */
function setup() {
  const box = createSandbox();
  const repoB = path.join(box.root, 'B');
  writeSkills(path.join(repoB, '.claude'), { 'b-own': 'B keeps this.' }, 'skills');
  git(repoB, 'init', '-q');
  git(repoB, 'add', '-A');
  git(repoB, 'commit', '-q', '-m', 'b');
  writeSkills(path.join(box.home, '.claude'), { 'owner-global': 'Mine.' }, 'skills');
  writeSkills(path.join(box.home, '.agents'), { 'owner-agents': 'Mine too.' }, 'skills');
  const packs = [pack('acme', ['alpha', 'beta']), pack('bravo', ['bravo1']), pack('charlie', ['charlie1'])];
  for (const p of packs) createRemote(box.remotes, `t/${p.id}`, Object.fromEntries(p.sources[0].skills.map((s) => [s.id, s.description])));
  writeUserConfig(box.home, { packs });
  const run = async (args) => {
    const io = createMockIo(box.env);
    const code = await runCli([...args, '--project', box.project, '--no-color'], io);
    return { code, out: io.getStdout(), err: io.getStderr() };
  };
  const others = () => ({
    B: snapshot(repoB),
    globalClaude: snapshot(path.join(box.home, '.claude')),
    globalAgents: snapshot(path.join(box.home, '.agents')),
  });
  return { box, run, others };
}

test('per repo: one command adds three packs to repo A; repo B and the global skills folders stay byte for byte', async () => {
  const { box, run, others } = setup();
  try {
    const before = others();
    const r = await run(['install', '--pack', 'acme', '--pack', 'bravo', '--pack', 'charlie', '--agent', 'claude', '--yes']);
    assert.equal(r.code, 0, r.err + r.out);
    assert.deepEqual(fs.readdirSync(path.join(box.project, '.claude', 'skills')).sort(), ['alpha', 'beta', 'bravo1', 'charlie1']);
    assert.deepEqual(others(), before);
  } finally {
    box.cleanup();
  }
});

test('per repo: uninstall keeps a skill folder the repo commits (the 18 Nov course deletion)', async () => {
  const { box, run, others } = setup();
  try {
    git(box.project, 'init', '-q');
    assert.equal((await run(['install', 'sigmawrite', '--agent', 'claude', '--yes'])).code, 0);
    assert.equal((await run(['install', '--pack', 'acme', '--agent', 'claude', '--yes'])).code, 0);
    git(box.project, 'add', '-A', '.agents/skills/sigmawrite', '.agents/skills/alpha');
    git(box.project, 'commit', '-q', '-m', 'the repo keeps two of its skills');
    const before = others();
    const committed = [snapshot(path.join(box.project, '.agents', 'skills', 'sigmawrite')), snapshot(path.join(box.project, '.agents', 'skills', 'alpha'))];

    const sigma = await run(['uninstall', '--skill', 'sigmawrite', '--changed', 'backup', '--yes']);
    const packed = await run(['uninstall', '--skill', 'alpha', '--force', '--yes']);
    assert.match(sigma.out + sigma.err, /git-tracked/);
    assert.match(packed.out + packed.err, /git/);
    assert.deepEqual([snapshot(path.join(box.project, '.agents', 'skills', 'sigmawrite')), snapshot(path.join(box.project, '.agents', 'skills', 'alpha'))], committed);
    assert.equal(git(box.project, 'status', '--porcelain', '--', '.agents/skills/sigmawrite', '.agents/skills/alpha'), '');
    assert.deepEqual(others(), before);

    // A skill the repo does not commit is still the installer's to remove.
    assert.equal((await run(['uninstall', '--skill', 'beta', '--yes'])).code, 0);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents', 'skills', 'beta')));
  } finally {
    box.cleanup();
  }
});

test('global set: CORE_PACKS is the one line; --non-core keeps Sigma while it is listed and removes it once it is not', async () => {
  const { box, others } = setup();
  const runGlobal = async (args) => {
    const io = createMockIo(box.env);
    const code = await runCli([...args, '--global', '--no-color'], io);
    return { code, out: io.getStdout(), err: io.getStderr() };
  };
  const sigmawrite = path.join(box.home, '.agents', 'skills', 'sigmawrite');
  try {
    assert.equal((await runGlobal(['install', 'sigmawrite', '--agent', 'claude', '--yes'])).code, 0);
    const owner = others();
    assert.equal((await runGlobal(['uninstall', '--non-core', '--yes'])).code, 0);
    assert.ok(fs.existsSync(sigmawrite), 'sigma is in CORE_PACKS, so it stays');
    CORE_PACKS.splice(CORE_PACKS.indexOf('sigma'), 1);
    const r = await runGlobal(['uninstall', '--non-core', '--yes']);
    assert.equal(r.code, 0, r.err + r.out);
    assert.ok(!fs.existsSync(sigmawrite), 'sigma left the line, so --non-core removes it');
    assert.deepEqual(others().B, owner.B);
    assert.ok(fs.existsSync(path.join(box.home, '.claude', 'skills', 'owner-global', 'SKILL.md')), 'a folder the installer did not make stays');
  } finally {
    if (!CORE_PACKS.includes('sigma')) CORE_PACKS.unshift('sigma');
    box.cleanup();
  }
});
