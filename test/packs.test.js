import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { describeRoots, resolveAgentRoots, suggestAgents } from '../src/agents.js';
import { findPackageRoot, getCatalog } from '../src/catalog.js';
import {
  listGlobalDestinationGroups,
  listProjectDestinationGroups,
  loadHostRegistry,
} from '../src/destinations.js';
import { findPack, loadPackCatalog, resolveSelection } from '../src/packs.js';
import { ACME_PACK, createSandbox, writeSkills, writeUserConfig } from './pack-fixtures.js';

const packageRoot = findPackageRoot();
const catalog = getCatalog(packageRoot);

function load(box, extra) {
  if (extra) writeUserConfig(box.home, extra);
  return loadPackCatalog({ catalog, packageRoot, homeDir: box.home, env: box.env });
}

test('packs: the registry lists the bundled Sigma pack and the five outside packs', () => {
  const box = createSandbox();
  try {
    const packs = load(box);
    assert.deepEqual(packs.packs.map((pack) => pack.id), ['sigma', 'mattpocock', 'threejs', 'hyperframes', 'minimax-h3', 'storgestudio']);
    const sigma = findPack(packs, 'sigma');
    assert.equal(sigma.skills.length, catalog.skills.length);
    assert.ok(sigma.skills.every((skill) => skill.kind === 'bundled'));
    assert.equal(findPack(packs, 'matt').id, 'mattpocock');
    assert.equal(findPack(packs, 'THREE').id, 'threejs');
    assert.ok(findPack(packs, 'mattpocock').skills.some((skill) => skill.id === 'tdd'));
    assert.equal(findPack(packs, 'threejs').skills.length, 13);
    assert.ok(findPack(packs, 'hyperframes').skills.some((skill) => skill.id === 'hyperframes-core'));
    assert.ok(findPack(packs, 'hyperframes').skills.some((skill) => skill.id === 'cut-silences'), 'the student kit is part of the HyperFrames pack');
    assert.equal(findPack(packs, 'nope'), null);
  } finally {
    box.cleanup();
  }
});

test('packs: StorgeStudio is unavailable until a folder is set, then lists the prefixed skills', () => {
  const box = createSandbox();
  try {
    let packs = load(box);
    const storge = findPack(packs, 'storge');
    assert.equal(storge.available, false);
    assert.match(storge.note, /SIGMA_STORGESTUDIO_DIR/);

    const folder = path.join(box.root, 'skills-folder');
    writeSkills(folder, { 'storgestudio-film': 'Make films.', 'storgestudio-audio': 'Make audio.', 'unrelated-skill': 'Skip me.' }, '.');
    packs = load(box, { dirs: { storgestudio: folder } });
    const found = findPack(packs, 'storgestudio');
    assert.equal(found.available, true);
    assert.deepEqual(found.skills.map((skill) => skill.id), ['storgestudio-audio', 'storgestudio-film']);
    assert.equal(found.skills[0].description, 'Make audio.');

    const viaEnv = loadPackCatalog({ catalog, packageRoot, homeDir: path.join(box.root, 'other-home'), env: { ...box.env, SIGMA_STORGESTUDIO_DIR: folder } });
    assert.equal(findPack(viaEnv, 'storgestudio').skills.length, 2);
  } finally {
    box.cleanup();
  }
});

test('packs: the owner config can add a whole pack', () => {
  const box = createSandbox();
  try {
    const packs = load(box, { packs: [ACME_PACK] });
    assert.deepEqual(findPack(packs, 'ac').skills.map((skill) => skill.id), ['alpha', 'beta']);
    assert.equal(packs.skills.get('alpha').pack, 'acme');
  } finally {
    box.cleanup();
  }
});

test('packs: a broken owner config stops with the file name', () => {
  const box = createSandbox();
  try {
    fs.mkdirSync(path.join(box.home, '.sigmaskills'));
    fs.writeFileSync(path.join(box.home, '.sigmaskills', 'packs.json'), '{ not json');
    assert.throws(() => load(box), /packs\.json/);
  } finally {
    box.cleanup();
  }
});

test('packs: resolveSelection joins presets and skill ids and reports what it cannot use', () => {
  const box = createSandbox();
  try {
    const packs = load(box, { packs: [ACME_PACK] });
    const picked = resolveSelection(packs, { presets: ['sigma,ac', 'nope'], skillIds: ['tdd', 'alpha', 'missing'] });
    assert.equal(picked.skills.length, catalog.skills.length + 2 + 1, 'sigma + acme(2) + tdd; alpha is not repeated');
    assert.deepEqual(picked.unknownPresets, ['nope']);
    assert.deepEqual(picked.unknownSkills, ['missing']);

    const storge = resolveSelection(packs, { presets: ['storgestudio'] });
    assert.equal(storge.skills.length, 0);
    assert.deepEqual(storge.unavailable.map((pack) => pack.id), ['storgestudio']);

    const all = resolveSelection(packs, { presets: ['all'] });
    assert.ok(all.skills.length > 80);
    assert.deepEqual(all.unavailable, [], 'all skips unavailable packs without complaint');
  } finally {
    box.cleanup();
  }
});

test('agents: friendly names resolve to destination roots and the universal root is always kept', () => {
  const box = createSandbox();
  try {
    const registry = loadHostRegistry(packageRoot);
    const groups = listProjectDestinationGroups({ registry, projectRoot: box.project, env: box.env });
    const claude = resolveAgentRoots(['claude'], groups);
    assert.deepEqual(claude.roots.sort(), ['.agents/skills', '.claude/skills']);
    assert.deepEqual(claude.unknown, []);

    const many = resolveAgentRoots(['codex,gemini', 'agy', 'pi', 'cursor', 'opencode'], groups);
    assert.deepEqual(many.roots, ['.agents/skills'], 'these hosts all read .agents/skills');
    assert.deepEqual(many.hosts.map((host) => host.id).sort(), ['antigravity-cli', 'codex', 'cursor', 'gemini-cli', 'opencode', 'pi']);

    const bad = resolveAgentRoots(['claud', 'claude'], groups);
    assert.deepEqual(bad.unknown, ['claud']);
    assert.ok(suggestAgents('claud', groups).includes('claude-code'));

    const every = resolveAgentRoots(['*'], groups);
    assert.ok(every.roots.length > 20);
  } finally {
    box.cleanup();
  }
});

test('agents: global groups resolve the same friendly names', () => {
  const box = createSandbox();
  try {
    const registry = loadHostRegistry(packageRoot);
    const groups = listGlobalDestinationGroups({ registry, homeDir: box.home, env: box.env });
    const claude = resolveAgentRoots(['claude'], groups);
    assert.ok(claude.roots.includes('.claude/skills'));
    const names = describeRoots(groups);
    assert.match(names.get('.agents/skills'), /Codex/);
    assert.equal(names.get('.claude/skills'), 'Claude Code');
  } finally {
    box.cleanup();
  }
});
