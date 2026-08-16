import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { parseAgents } from '../src/registry/parse.js';
import { validateSnapshot, assertSafePath, destinationKey } from '../src/registry/validate.js';
import { diffSnapshots } from '../src/registry/diff.js';
import { normalizeHost, buildSnapshot } from '../src/registry/normalize.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const FIXTURE = path.join(ROOT, 'test/fixtures/vercel-skills/src/agents.ts');
const SNAPSHOT = path.join(ROOT, 'registry/agent-hosts.json');
const SOURCE = path.join(ROOT, 'registry/source.json');

test('registry: committed snapshot reproduces fixture parse', () => {
  const fixtureText = fs.readFileSync(FIXTURE, 'utf8');
  const pin = JSON.parse(fs.readFileSync(SOURCE, 'utf8'));
  const parsed = parseAgents(fixtureText);
  const hosts = parsed.map((h) => normalizeHost(h, pin));
  const snapshot = buildSnapshot(hosts, pin);
  const committed = JSON.parse(fs.readFileSync(SNAPSHOT, 'utf8'));
  assert.deepEqual(snapshot, committed);
});

test('registry: snapshot carries primary-source attribution', () => {
  const snapshot = JSON.parse(fs.readFileSync(SNAPSHOT, 'utf8'));
  assert.equal(snapshot.schemaVersion, 1);
  assert.equal(snapshot.generatedFrom.repository, 'vercel-labs/skills');
  assert.equal(snapshot.generatedFrom.upstreamFile, 'src/agents.ts');
  assert.ok(snapshot.generatedFrom.pinnedRevision);
  for (const host of snapshot.hosts) {
    assert.equal(host.attribution.upstreamFile, 'src/agents.ts');
    assert.ok(host.attribution.upstreamLine >= 1);
  }
});

test('registry: validate rejects unsafe traversal and roots', () => {
  assert.match(assertSafePath('../escape', 'test'), /traversal/);
  assert.match(assertSafePath('/absolute', 'test'), /absolute/);
  assert.match(assertSafePath('a/../b', 'test'), /traversal/);
  assert.equal(assertSafePath('.agents/skills', 'test'), null);
  assert.equal(assertSafePath('.claude/skills', 'test'), null);
});

test('registry: validate rejects control characters and shell syntax', () => {
  assert.match(assertSafePath('a\x00b', 'test'), /control/);
  assert.match(assertSafePath('a;b', 'test'), /shell/);
  assert.match(assertSafePath('a$b', 'test'), /shell/);
  assert.match(assertSafePath('a`b`', 'test'), /shell/);
});

test('registry: validate rejects duplicate and case-colliding ids', () => {
  const base = {
    schemaVersion: 1,
    hosts: [
      { id: 'cursor', name: 'cursor', displayName: 'Cursor', destinations: { project: { kind: 'literal', path: '.cursor/skills' }, global: { kind: 'none' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
      { id: 'CURSOR', name: 'CURSOR', displayName: 'CURSOR', destinations: { project: { kind: 'literal', path: '.cursor2/skills' }, global: { kind: 'none' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 2 } },
    ],
  };
  const v = validateSnapshot(base);
  assert.equal(v.valid, false);
  assert.ok(v.errors.some((e) => e.includes('case-colliding')));
});

test('registry: validate rejects intra-host destination overlap', () => {
  const snap = {
    schemaVersion: 1,
    hosts: [
      { id: 'x', name: 'x', displayName: 'X', destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'literal', path: '.agents/skills' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const v = validateSnapshot(snap);
  assert.equal(v.valid, false);
  assert.ok(Object.values(v.hostErrors)[0].includes('overlap'));
});

test('registry: diff classifies description-only as safe and path changes as review', () => {
  const prev = {
    hosts: [
      { id: 'amp', name: 'amp', displayName: 'Amp', destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'join', base: 'configHome', segments: ['agents/skills'] } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const currDesc = {
    hosts: [
      { id: 'amp', name: 'amp', displayName: 'Amp Updated', destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'join', base: 'configHome', segments: ['agents/skills'] } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const currPath = {
    hosts: [
      { id: 'amp', name: 'amp', displayName: 'Amp', destinations: { project: { kind: 'literal', path: '.amp/skills' }, global: { kind: 'join', base: 'configHome', segments: ['agents/skills'] } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  assert.equal(diffSnapshots(prev, currDesc).changes[0].authority, 'safe');
  assert.equal(diffSnapshots(prev, currPath).changes[0].authority, 'review');
});

test('registry: diff classifies safe additions vs removals', () => {
  const prev = { hosts: [] };
  const currAdd = {
    hosts: [
      { id: 'newhost', name: 'newhost', displayName: 'New', destinations: { project: { kind: 'literal', path: '.new/skills' }, global: { kind: 'none' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const add = diffSnapshots(prev, currAdd);
  assert.equal(add.changes[0].kind, 'addition');
  assert.equal(add.changes[0].authority, 'safe');
  const rem = diffSnapshots(currAdd, prev);
  assert.equal(rem.changes[0].kind, 'removal');
  assert.equal(rem.changes[0].authority, 'review');
});

test('registry: no upstream detector code executes — snapshot is pure data', () => {
  const snapshot = JSON.parse(fs.readFileSync(SNAPSHOT, 'utf8'));
  const text = JSON.stringify(snapshot);
  assert.doesNotMatch(text, /detectInstalled/);
  assert.doesNotMatch(text, /existsSync/);
  assert.doesNotMatch(text, /=>/);
});
