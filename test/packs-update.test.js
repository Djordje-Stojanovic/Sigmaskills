import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
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
