import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { findPackageRoot } from '../src/catalog.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  defaultSelectedRoots,
  detectHost,
  findDestinationConflicts,
  listProjectDestinationGroups,
  loadHostRegistry,
  resolveSkillPath,
  searchHosts,
} from '../src/destinations.js';

const ROOT = findPackageRoot();

function fixtureHost(overrides) {
  return {
    id: 'fixture',
    name: 'fixture',
    displayName: 'Fixture Host',
    universal: false,
    universalPrompt: false,
    destinations: {
      project: { kind: 'literal', path: '.fixture/skills' },
      global: { kind: 'none' },
    },
    aliases: ['fix'],
    platforms: [],
    detection: { envVars: [] },
    ...overrides,
  };
}

test('bundled registry keeps every Agent Host searchable, including undetected hosts', () => {
  const registry = loadHostRegistry(ROOT);
  const groups = listProjectDestinationGroups({
    registry,
    projectRoot: path.join(os.tmpdir(), 'sigma-dest-search'),
    env: {},
  });

  const hostIds = groups.flatMap((group) => group.hosts.map((host) => host.id));
  assert.ok(hostIds.includes('pi'));
  assert.ok(hostIds.includes('claude-code'));
  assert.ok(hostIds.includes('cursor'));
  assert.ok(hostIds.includes('codex'));
  assert.equal(hostIds.length, registry.hosts.length);

  const piMatches = searchHosts(groups, 'pi');
  assert.ok(piMatches.some((host) => host.id === 'pi'));
  const claudeMatches = searchHosts(groups, 'Claude Code');
  assert.ok(claudeMatches.some((host) => host.id === 'claude-code'));
  const aliasMatches = searchHosts(groups, 'fix');
  assert.equal(aliasMatches.length, 0);
});

test('only .agents/skills is selected by default and lists every affected Agent Host', () => {
  const registry = loadHostRegistry(ROOT);
  const projectRoot = 'C:\\proj';
  const groups = listProjectDestinationGroups({ registry, projectRoot, env: {} });
  const selected = defaultSelectedRoots(groups);

  assert.deepEqual(selected, [UNIVERSAL_PROJECT_DESTINATION]);
  assert.equal(UNIVERSAL_PROJECT_DESTINATION, '.agents/skills');

  const universal = groups.find((group) => group.universal);
  assert.ok(universal);
  assert.equal(universal.relativeRoot, '.agents/skills');
  assert.equal(universal.selectedByDefault, true);
  assert.ok(universal.hosts.some((host) => host.id === 'codex'));
  assert.ok(universal.hosts.some((host) => host.id === 'cursor'));
  assert.ok(!universal.hosts.some((host) => host.id === 'pi'));
  assert.ok(!universal.hosts.some((host) => host.id === 'claude-code'));
  assert.ok(universal.hosts.length >= 2);
  assert.equal(path.basename(path.dirname(universal.absoluteRoot)), '.agents');
});

test('host-specific destinations start unselected and detection never selects them', () => {
  const registry = {
    schemaVersion: 1,
    hosts: [
      fixtureHost({
        id: 'claude-code',
        displayName: 'Claude Code',
        destinations: { project: { kind: 'literal', path: '.claude/skills' }, global: { kind: 'none' } },
        detection: { envVars: ['CLAUDE_CODE'] },
      }),
      fixtureHost({
        id: 'amp',
        displayName: 'Amp',
        destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'none' } },
      }),
    ],
  };
  const groups = listProjectDestinationGroups({
    registry,
    projectRoot: path.join(os.tmpdir(), 'sigma-dest-detect'),
    env: { CLAUDE_CODE: '1' },
  });

  const claude = groups.find((group) => group.relativeRoot === '.claude/skills');
  assert.equal(claude.selectedByDefault, false);
  assert.equal(claude.hosts[0].detected, true);
  assert.ok(!defaultSelectedRoots(groups).includes('.claude/skills'));
  assert.equal(detectHost(registry.hosts[0], { CLAUDE_CODE: '1' }), true);
  assert.equal(detectHost(registry.hosts[0], {}), false);
});

test('resolved skill paths stay inside the project and reject traversal', () => {
  const projectRoot = path.resolve('/tmp/sigma-project');
  const resolved = resolveSkillPath(projectRoot, '.claude/skills', 'sigmawrite');
  assert.equal(resolved.relativeDestination.replace(/\\/g, '/'), '.claude/skills/sigmawrite');
  assert.equal(path.resolve(resolved.destination), path.resolve(projectRoot, '.claude', 'skills', 'sigmawrite'));

  assert.throws(
    () => resolveSkillPath(projectRoot, '../outside', 'sigmawrite'),
    /invalid destination/,
  );
});

test('colliding, overlapping, duplicate, invalid, and occupied-unowned destinations fail before any write', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-dest-conflict-'));
  try {
    const occupied = path.join(projectRoot, '.claude', 'skills', 'sigmawrite');
    fs.mkdirSync(occupied, { recursive: true });
    fs.writeFileSync(path.join(occupied, 'SKILL.md'), 'foreign', 'utf8');

    const duplicate = findDestinationConflicts({
      projectRoot,
      skillIds: ['sigmawrite'],
      selectedRoots: ['.agents/skills', '.agents/skills'],
      isOwned: () => false,
    });
    assert.match(duplicate[0], /duplicate/i);

    const overlap = findDestinationConflicts({
      projectRoot,
      skillIds: ['sigmawrite'],
      selectedRoots: ['.agents/skills', '.agents/skills/sigmawrite'],
      isOwned: () => false,
    });
    assert.match(overlap[0], /overlap/i);

    const invalid = findDestinationConflicts({
      projectRoot,
      skillIds: ['sigmawrite'],
      selectedRoots: ['../outside'],
      isOwned: () => false,
    });
    assert.match(invalid[0], /invalid/i);

    const occupiedUnowned = findDestinationConflicts({
      projectRoot,
      skillIds: ['sigmawrite'],
      selectedRoots: ['.claude/skills'],
      isOwned: () => false,
    });
    assert.match(occupiedUnowned[0], /not owned/i);

    const ownedOk = findDestinationConflicts({
      projectRoot,
      skillIds: ['sigmawrite'],
      selectedRoots: ['.claude/skills'],
      isOwned: () => true,
    });
    assert.deepEqual(ownedOk, []);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
