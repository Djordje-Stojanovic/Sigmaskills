import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { stageSkills } from '../src/pack-source.js';
import { commitAll, createRemote, createSandbox, headSha, writeSkills } from './pack-fixtures.js';

const script = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'scripts', 'packs-update.js');

function pack(id, repo, ref, ids, extra = {}) {
  return {
    id, title: id, blurb: 'Test.', aliases: [],
    sources: [{ type: 'git', repo, path: 'skills', ...(ref ? { ref } : {}), skills: ids.map((name) => ({ id: name, description: `${name} skill.` })), ...extra }],
  };
}

function setup(box, packs) {
  const file = path.join(box.root, 'packs.json');
  fs.writeFileSync(file, `${JSON.stringify({ schemaVersion: 1, packs }, null, 2)}\n`);
  return file;
}

function runScript(box, file, ...args) {
  const run = spawnSync(process.execPath, [script, '--file', file, ...args], { env: box.env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  const lines = run.stdout.trimEnd().split('\n');
  lines.status = run.status;
  return lines;
}

const read = (file) => JSON.parse(fs.readFileSync(file, 'utf8')).packs;

test('packs-update: a passing pack moves its pin and skill list; a failing pack keeps its pin; no install happens', () => {
  const box = createSandbox();
  try {
    const good = createRemote(box.remotes, 'acme/good', { alpha: 'Alpha.' });
    const bad = createRemote(box.remotes, 'acme/bad', { beta: 'Beta.' });
    createRemote(box.remotes, 'acme/head', { gamma: 'Gamma.' });
    const goodOld = headSha(good);
    const badOld = headSha(bad);
    writeSkills(good, { delta: 'Delta.' });
    commitAll(good, 'add delta');
    fs.writeFileSync(path.join(bad, 'skills', 'beta', 'SKILL.md'), '---\nname: beta\n---\n');
    commitAll(bad, 'break beta');
    const file = setup(box, [
      { id: 'sigma', title: 'Sigma', blurb: 'x', aliases: [], bundled: true },
      pack('good', 'acme/good', goodOld, ['alpha']),
      pack('bad', 'acme/bad', badOld, ['beta']),
      pack('head', 'acme/head', null, ['gamma']),
    ]);

    const lines = runScript(box, file);
    assert.equal(lines.length, 3, 'one line per pack that has a git source (bundled packs have none)');
    assert.equal(lines.status, 1, 'a failing pack gives exit code 1');
    const goodNew = headSha(good);
    assert.match(lines.find((line) => line.startsWith('good')), new RegExp(`${goodOld.slice(0, 7)} -> ${goodNew.slice(0, 7)}\\s+PASS`));
    assert.match(lines.find((line) => line.startsWith('bad')), new RegExp(`${badOld.slice(0, 7)} kept\\s+FAIL.*beta.*must include description`));
    assert.match(lines.find((line) => line.startsWith('head')), /unpinned/);

    const after = read(file);
    const goodSource = after.find((entry) => entry.id === 'good').sources[0];
    assert.equal(goodSource.ref, goodNew);
    assert.deepEqual(goodSource.skills.map((skill) => skill.id), ['alpha', 'delta']);
    assert.equal(after.find((entry) => entry.id === 'bad').sources[0].ref, badOld, 'a failing pack keeps its old pin');
    assert.equal(after.find((entry) => entry.id === 'head').sources[0].ref, undefined);
    assert.ok(!fs.existsSync(path.join(box.home, '.sigmaskills', 'cache')), 'nothing is cached or installed');
  } finally {
    box.cleanup();
  }
});

test('packs-update: a new upstream skill whose name an earlier pack or a Sigma skill owns is not listed', () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/first', { shared: 'Shared.' });
    const later = createRemote(box.remotes, 'acme/later', { own: 'Own.' });
    const old = headSha(later);
    writeSkills(later, { shared: 'Shared again.', sigmaship: 'A copy.', fresh: 'Fresh.' });
    commitAll(later, 'add three');
    const file = setup(box, [pack('first', 'acme/first', null, ['shared']), pack('later', 'acme/later', old, ['own'])]);

    runScript(box, file);
    assert.deepEqual(read(file).find((entry) => entry.id === 'later').sources[0].skills.map((skill) => skill.id), ['fresh', 'own']);
  } finally {
    box.cleanup();
  }
});

test('packs-update: a router that names a skill its pack does not install fails; a rename makes the route resolve', () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/first', { shared: 'Shared.' });
    const later = createRemote(box.remotes, 'acme/later', { own: 'Own.' });
    const old = headSha(later);
    writeSkills(later, { shared: 'Game version.', router: 'Routes. For low FPS load `shared`.' });
    fs.writeFileSync(path.join(later, 'LICENSE'), 'Apache-2.0\n');
    commitAll(later, 'router and licence');
    const packs = (extra) => [pack('first', 'acme/first', null, ['shared']), pack('later', 'acme/later', old, ['own'], extra)];

    const plain = setup(box, packs());
    const lines = runScript(box, plain);
    assert.match(lines.find((line) => line.startsWith('later')), /FAIL: .*router routes to shared, which this pack does not install/);
    assert.equal(lines.status, 1);

    const renamed = setup(box, packs({ licenses: ['LICENSE'], rename: { shared: 'game-shared' } }));
    assert.match(runScript(box, renamed).find((line) => line.startsWith('later')), /PASS/);
    assert.deepEqual(read(renamed).find((entry) => entry.id === 'later').sources[0].skills.map((skill) => skill.id), ['game-shared', 'own', 'router']);
  } finally {
    box.cleanup();
  }
});

test('packs-update: a router that still names a skill upstream deleted fails', () => {
  const box = createSandbox();
  try {
    const repo = createRemote(box.remotes, 'acme/gone', { router: 'Routes. For speed load `some-skill`.', 'some-skill': 'Some.' });
    const old = headSha(repo);
    fs.rmSync(path.join(repo, 'skills', 'some-skill'), { recursive: true, force: true });
    commitAll(repo, 'delete some-skill');
    const file = setup(box, [pack('gone', 'acme/gone', old, ['router', 'some-skill'])]);
    const lines = runScript(box, file);
    assert.match(lines.find((line) => line.startsWith('gone')), /FAIL: .*router routes to some-skill, which this pack does not install/);
    assert.equal(lines.status, 1);
    assert.equal(read(file)[0].sources[0].ref, old, 'the pack keeps its old pin');
  } finally {
    box.cleanup();
  }
});

test('a fetched pack source holds the pinned bytes even when the machine sets core.autocrlf=true', () => {
  const box = createSandbox();
  try {
    const repo = createRemote(box.remotes, 'acme/eol', { alpha: 'Alpha.' });
    fs.writeFileSync(path.join(repo, 'LICENSE'), 'line one\nline two\n');
    commitAll(repo, 'licence');
    const system = path.join(box.root, 'system.gitconfig');
    fs.writeFileSync(system, '[core]\n\tautocrlf = true\n'); // what Git for Windows ships
    const source = { type: 'git', repo: 'acme/eol', path: 'skills', ref: headSha(repo) };
    const code = `import { createSourceFetcher } from ${JSON.stringify(pathToFileURL(path.join(path.dirname(script), '..', 'src', 'pack-source.js')).href)};
      import fs from 'node:fs'; import path from 'node:path';
      const f = createSourceFetcher(); const r = f.fetch(${JSON.stringify(source)});
      process.stdout.write(JSON.stringify([fs.readFileSync(path.join(r.repoRoot, 'LICENSE'), 'utf8'), fs.readFileSync(path.join(r.root, 'alpha', 'SKILL.md'), 'utf8')]));`;
    const run = spawnSync(process.execPath, ['--input-type=module', '-e', code], { env: { ...box.env, GIT_CONFIG_SYSTEM: system }, encoding: 'utf8' });
    assert.equal(run.status, 0, run.stderr);
    const [licence, skill] = JSON.parse(run.stdout);
    assert.equal(licence, 'line one\nline two\n');
    assert.ok(!skill.includes('\r'), 'no CRLF in a fetched skill file');
  } finally {
    box.cleanup();
  }
});

test('stageSkills: licence files go into every skill folder, and a renamed skill is renamed in every Markdown file', () => {
  const box = createSandbox();
  try {
    const repo = path.join(box.root, 'repo');
    fs.mkdirSync(path.join(repo, 'skills', 'perf'), { recursive: true });
    fs.mkdirSync(path.join(repo, 'skills', 'router', 'references'), { recursive: true });
    fs.writeFileSync(path.join(repo, 'LICENSE'), 'L');
    // A licence below the root (cursor/plugins keeps pstack's at harness/pstack/claude-code/LICENSE) lands by its file name.
    fs.mkdirSync(path.join(repo, 'legal'));
    fs.writeFileSync(path.join(repo, 'legal', 'NOTICE'), 'N');
    fs.writeFileSync(path.join(repo, 'skills', 'perf', 'SKILL.md'), '---\nname: perf\ndescription: P.\n---\n');
    fs.writeFileSync(path.join(repo, 'skills', 'router', 'SKILL.md'), '---\nname: router\ndescription: R.\n---\nLoad perf, not perf-tools.\n');
    fs.writeFileSync(path.join(repo, 'skills', 'router', 'references', 'table.md'), '| slow | `perf` |\n');
    const out = path.join(box.root, 'out');
    stageSkills({ licenses: ['LICENSE', 'legal/NOTICE', 'MISSING'], rename: { perf: 'game-perf' } }, path.join(repo, 'skills'), repo, out);
    assert.deepEqual(fs.readdirSync(out).sort(), ['game-perf', 'router']);
    assert.deepEqual(fs.readdirSync(path.join(out, 'router')).sort(), ['LICENSE', 'NOTICE', 'SKILL.md', 'references']);
    assert.match(fs.readFileSync(path.join(out, 'game-perf', 'SKILL.md'), 'utf8'), /name: game-perf/);
    assert.match(fs.readFileSync(path.join(out, 'router', 'SKILL.md'), 'utf8'), /Load game-perf, not perf-tools\./);
    assert.match(fs.readFileSync(path.join(out, 'router', 'references', 'table.md'), 'utf8'), /`game-perf`/);
  } finally {
    box.cleanup();
  }
});

test('packs-update: --dry-run reports the move and writes nothing; an unchanged pack says so', () => {
  const box = createSandbox();
  try {
    const repo = createRemote(box.remotes, 'acme/same', { alpha: 'Alpha.' });
    const moved = createRemote(box.remotes, 'acme/moved', { beta: 'Beta.' });
    const movedOld = headSha(moved);
    writeSkills(moved, { beta: 'Beta two.' });
    commitAll(moved, 'edit beta');
    const file = setup(box, [pack('same', 'acme/same', headSha(repo), ['alpha']), pack('moved', 'acme/moved', movedOld, ['beta'])]);
    const before = fs.readFileSync(file, 'utf8');

    const lines = runScript(box, file, '--dry-run');
    assert.match(lines.find((line) => line.startsWith('same')), /unchanged\s+PASS/);
    assert.match(lines.find((line) => line.startsWith('moved')), /->.*PASS/);
    assert.equal(fs.readFileSync(file, 'utf8'), before);
    assert.equal(lines.status, 0);
  } finally {
    box.cleanup();
  }
});
