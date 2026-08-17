import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  loadHostRegistry,
  listProjectDestinationGroups,
} from '../src/destinations.js';
import { createInstallPlan, formatPlanHuman } from '../src/plan.js';
import { loadProjectState } from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';

const ROOT = findPackageRoot();

function hostGroups(projectRoot, env = {}) {
  return listProjectDestinationGroups({
    registry: loadHostRegistry(ROOT),
    projectRoot,
    env,
  });
}

test('plan: default Project Installation resolves only the universal destination with full paths', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-plan-universal-'));
  try {
    const catalog = getCatalog(ROOT);
    const plan = createInstallPlan(catalog, {
      skillId: 'sigmawrite',
      projectRoot,
      destinationGroups: hostGroups(projectRoot),
      dryRun: true,
    });

    assert.equal(plan.destinations.length, 1);
    assert.equal(plan.destinations[0].relativeRoot, UNIVERSAL_PROJECT_DESTINATION);
    assert.equal(plan.destinations[0].kind, 'canonical');
    assert.equal(plan.destinations[0].destination, path.resolve(projectRoot, '.agents', 'skills', 'sigmawrite'));
    assert.ok(plan.destinations[0].hosts.some((host) => host.id === 'codex'));
    assert.ok(plan.destinations[0].hosts.some((host) => host.id === 'cursor'));
    assert.ok(!plan.destinations[0].hosts.some((host) => host.id === 'pi'));

    const human = formatPlanHuman(plan);
    assert.match(human, /Resolved destinations:/);
    assert.ok(human.includes(plan.destinations[0].destination));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: writes managed copies only at selected destinations and records each copy', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-host-copies-'));
  try {
    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      projectRoot,
      packageRoot: ROOT,
      selectedRoots: ['.agents/skills', '.claude/skills'],
      destinationGroups: hostGroups(projectRoot),
    });

    const canonical = path.join(projectRoot, '.agents', 'skills', 'sigmawrite', 'SKILL.md');
    const claude = path.join(projectRoot, '.claude', 'skills', 'sigmawrite', 'SKILL.md');
    const pi = path.join(projectRoot, '.pi', 'skills', 'sigmawrite', 'SKILL.md');
    const piGlobalStyle = path.join(projectRoot, '.pi', 'agent', 'skills', 'sigmawrite', 'SKILL.md');

    assert.ok(fs.existsSync(canonical));
    assert.ok(fs.existsSync(claude));
    assert.ok(!fs.existsSync(pi));
    assert.ok(!fs.existsSync(piGlobalStyle));

    const state = loadProjectState(projectRoot);
    const copies = state.skills.sigmawrite.copies;
    assert.ok(Array.isArray(copies));
    assert.equal(copies.length, 2);
    assert.equal(copies[0].kind, 'canonical');
    assert.equal(copies[0].destination, '.agents/skills/sigmawrite');
    assert.ok(copies[0].hostIds.includes('codex'));
    assert.equal(copies[1].kind, 'host');
    assert.equal(copies[1].destination, '.claude/skills/sigmawrite');
    assert.deepEqual(copies[1].hostIds, ['claude-code']);
    assert.equal(state.skills.sigmawrite.destination, '.agents/skills/sigmawrite');
    assert.ok(result.plan.destinations.some((dest) => dest.relativeRoot === '.claude/skills'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: unselected Pi and Claude Code directories stay untouched on default install', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-host-default-'));
  try {
    const catalog = getCatalog(ROOT);
    executeProjectInstall({
      catalog,
      skillId: 'sigmabrief',
      projectRoot,
      packageRoot: ROOT,
    });

    assert.ok(fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmabrief', 'SKILL.md')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.claude')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.pi')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: occupied host destination fails before any write, including the universal copy', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-host-preflight-'));
  try {
    const catalog = getCatalog(ROOT);
    const occupied = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    fs.mkdirSync(occupied, { recursive: true });
    fs.writeFileSync(path.join(occupied, 'SKILL.md'), 'foreign', 'utf8');

    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
          selectedRoots: ['.agents/skills', '.claude/skills'],
        });
      },
      /already exists and is not owned/,
    );

    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite')));
    assert.equal(fs.readFileSync(path.join(occupied, 'SKILL.md'), 'utf8'), 'foreign');
    assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('install: overlapping selected destinations fail before any write', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-host-overlap-'));
  try {
    const catalog = getCatalog(ROOT);
    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          projectRoot,
          packageRoot: ROOT,
          selectedRoots: ['.agents/skills', '.agents/skills/sigmawrite'],
        });
      },
      /overlap/i,
    );
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
