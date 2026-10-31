import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { PassThrough } from 'node:stream';
import { runCli } from '../src/cli.js';
import { findPackageRoot, getCatalog } from '../src/catalog.js';
import { findPack, loadPackCatalog } from '../src/packs.js';
import {
  ACME_PACK, createMockIo, createRemote, createSandbox, removeSkillFromRemote, tagRemote, writeSkills, writeUserConfig,
} from './pack-fixtures.js';

const packageRoot = findPackageRoot();
const catalog = getCatalog(packageRoot);
const packsJson = JSON.parse(fs.readFileSync(path.join(packageRoot, 'registry', 'packs.json'), 'utf8'));
const ENTER = '\r';
const DOWN = '\x1b[B';

async function run(box, args) {
  const io = createMockIo(box.env);
  const code = await runCli([...args, '--project', box.project, '--no-color'], io);
  return { code, out: io.getStdout(), err: io.getStderr() };
}

/** A folder of the owner's own skills that also holds copies of two Sigma skills. */
function ownerFolder(box) {
  const folder = path.join(box.root, 'owner-skills');
  writeSkills(folder, { sigmahuman: 'Local copy.', sigmawrite: 'Local copy.', 'studio-film': 'Make films.' }, '.');
  box.env.SIGMA_LOCAL_SKILLS_DIR = folder;
  return folder;
}

test('hyperframes pack: the source is pinned to a release tag and lists only skills upstream still has', () => {
  const pack = packsJson.packs.find((entry) => entry.id === 'hyperframes');
  const heygen = pack.sources.find((source) => source.repo === 'heygen-com/hyperframes');
  assert.match(heygen.ref, /^v\d+\.\d+\.\d+$/, 'a release tag, never the head');
  const ids = heygen.skills.map((skill) => skill.id).sort();
  assert.deepEqual(ids, ['figma', 'hyperframes', 'hyperframes-cli', 'hyperframes-registry', 'media-use', 'remotion-to-hyperframes', 'slideshow']);
});

test('pack install: a source with a ref installs from that tag even after upstream moved a skill', async () => {
  const box = createSandbox();
  try {
    const remote = createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    tagRemote(remote, 'v1.0.0');
    removeSkillFromRemote(remote, 'beta');
    const pinned = { ...ACME_PACK, sources: [{ ...ACME_PACK.sources[0], ref: 'v1.0.0' }] };
    writeUserConfig(box.home, { packs: [pinned] });
    const { code, out, err } = await run(box, ['install', '--preset', 'acme']);
    assert.equal(code, 0, err);
    assert.match(out, /2 skills installed/);
    assert.ok(!/failed/.test(out), out);
    assert.ok(fs.existsSync(path.join(box.project, '.agents', 'skills', 'beta', 'SKILL.md')));
  } finally {
    box.cleanup();
  }
});

test('packs: one owner per skill name; a later pack does not list a name an earlier pack owns', () => {
  const box = createSandbox();
  try {
    ownerFolder(box);
    const other = { id: 'other', title: 'Other', sources: [{ type: 'dir', path: path.join(box.root, 'owner-skills') }] };
    writeUserConfig(box.home, { packs: [other] });
    const packs = loadPackCatalog({ catalog, packageRoot, homeDir: box.home, env: box.env });
    assert.deepEqual(findPack(packs, 'local').skills.map((skill) => skill.id), ['studio-film']);
    assert.deepEqual(findPack(packs, 'other').skills.map((skill) => skill.id), []);
    assert.equal(packs.skills.get('sigmahuman').kind, 'bundled', 'the Sigma set wins');
    assert.equal(findPack(packs, 'sigma').skills.length, catalog.skills.length);
    const listed = packs.packs.flatMap((pack) => pack.skills.map((skill) => skill.id));
    assert.equal(new Set(listed).size, listed.length, 'no name twice across packs');
  } finally {
    box.cleanup();
  }
});

test('install: Sigma plus Local in a fresh folder keeps nothing and counts every set N of N', async () => {
  const box = createSandbox();
  try {
    ownerFolder(box);
    const total = catalog.skills.length;
    const { code, out, err } = await run(box, ['install', '--preset', 'sigma,local']);
    assert.equal(code, 0, err);
    assert.match(out, new RegExp(`${total + 1} skills installed`));
    assert.match(out, new RegExp(`Sigma[ ]+${total} of ${total}`));
    assert.match(out, /Local[ ]+1 of 1/);
    assert.ok(!/kept|failed|folder in the way/.test(out), out);
    const copy = fs.readFileSync(path.join(box.project, '.agents', 'skills', 'sigmahuman', 'SKILL.md'), 'utf8');
    assert.ok(!copy.includes('Local copy.'), 'the Sigma copy is the one written');
  } finally {
    box.cleanup();
  }
});

test('wizard: Sigma plus Local in a fresh folder installs each name once', async () => {
  const box = createSandbox();
  try {
    ownerFolder(box);
    const stdin = new PassThrough();
    stdin.isTTY = true;
    stdin.setRawMode = () => {};
    const stdout = new PassThrough();
    stdout.isTTY = true;
    stdout.columns = 110;
    stdout.rows = 30;
    stdout.getColorDepth = () => 24;
    const stderr = new PassThrough();
    let out = '';
    stdout.setEncoding('utf8');
    stdout.on('data', (chunk) => { out += chunk; });
    // Sigma is key 1. Local is the 11th row (number keys stop at ten): move down ten rows, then Space picks it.
    // Keys arrive one at a time.
    const keys = ['1', ...Array(10).fill(DOWN), ' ', ENTER, ENTER, ENTER];
    keys.forEach((chunk, index) => {
      setTimeout(() => (index === keys.length - 1 ? stdin.end(chunk) : stdin.write(chunk)), 200 * (index + 1));
    });
    const code = await runCli(['--project', box.project], { stdin, stdout, stderr, env: { ...box.env, TERM: 'xterm-256color' } });
    assert.equal(code, 0);
    const text = out.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '');
    const total = catalog.skills.length;
    assert.match(text, new RegExp(`${total + 1} skills installed`));
    assert.match(text, /Local[ ]+1 of 1/);
    assert.ok(!/kept|failed|folder in the way/.test(text), text);
  } finally {
    box.cleanup();
  }
});
