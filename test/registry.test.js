import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { parseAgents, extractEnvVars } from '../src/registry/parse.js';
import { validateSnapshot, assertSafePath, SUPPORTED_PLATFORMS } from '../src/registry/validate.js';
import { diffSnapshots } from '../src/registry/diff.js';
import { normalizeHost, buildSnapshot, compareIds } from '../src/registry/normalize.js';
import { loadPin, syncRegistry, runSync, fetchPinnedSource, canonicalSourceText } from '../src/registry/sync.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const FIXTURE = path.join(ROOT, 'test/fixtures/vercel-skills/src/agents.ts');
const SNAPSHOT = path.join(ROOT, 'registry/agent-hosts.json');
const SOURCE = path.join(ROOT, 'registry/source.json');
const REGISTRY_DIR = path.join(ROOT, 'registry');

function loadSnapshot() {
  return JSON.parse(fs.readFileSync(SNAPSHOT, 'utf8'));
}

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

test('registry: committed snapshot reproduces fixture parse', () => {
  const fixtureText = fs.readFileSync(FIXTURE, 'utf8');
  const pin = loadPin();
  const parsed = parseAgents(fixtureText);
  const hosts = parsed.map((h) => normalizeHost(h, pin));
  const snapshot = buildSnapshot(hosts, pin);
  assert.deepEqual(snapshot, loadSnapshot());
});

test('registry: snapshot carries primary-source attribution from a real pin', () => {
  const snapshot = loadSnapshot();
  const pin = loadPin();
  assert.equal(snapshot.schemaVersion, 1);
  assert.equal(snapshot.generatedFrom.repository, 'vercel-labs/skills');
  assert.equal(snapshot.generatedFrom.upstreamFile, 'src/agents.ts');
  assert.match(snapshot.generatedFrom.pinnedRevision, /^[0-9a-f]{40}$/);
  assert.equal(pin.contentSha256, sha256(canonicalSourceText(fs.readFileSync(FIXTURE, 'utf8'))));
  for (const host of snapshot.hosts) {
    assert.equal(host.attribution.upstreamFile, 'src/agents.ts');
    assert.ok(host.attribution.upstreamLine >= 1);
  }
});

test('registry: pinned content hash ignores CRLF from Windows checkout', () => {
  const pin = loadPin();
  const lf = canonicalSourceText(fs.readFileSync(FIXTURE, 'utf8'));
  const crlf = lf.replace(/\n/g, '\r\n');
  assert.equal(sha256(canonicalSourceText(crlf)), pin.contentSha256);
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-registry-crlf-'));
  try {
    const source = path.join(tmpDir, 'agents.ts');
    fs.writeFileSync(source, crlf, 'utf8');
    const result = syncRegistry({ source, allowReview: true, dryRun: true }, { pin, previous: loadSnapshot() });
    assert.equal(result.ok, true, (result.errors || []).join('\n'));
    assert.equal(result.diff.summary.review, 0);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('registry: universal membership is preserved from upstream flags', () => {
  const hosts = parseAgents(fs.readFileSync(FIXTURE, 'utf8'));
  const byId = new Map(hosts.map((h) => [h.id, h]));
  assert.equal(byId.get('amp').universal, true);
  assert.equal(byId.get('replit').universal, false);
  assert.equal(byId.get('universal').universal, false);
  assert.equal(byId.get('dexto').universalPrompt, false);
  assert.equal(byId.get('amp').universalPrompt, true);
});

test('registry: snapshot ordering is bytewise and locale-independent', () => {
  const snapshot = loadSnapshot();
  const ids = snapshot.hosts.map((h) => h.id);
  const sorted = [...ids].sort(compareIds);
  assert.deepEqual(ids, sorted);
  // Bytewise: uppercase letters sort before lowercase, independent of locale.
  assert.deepEqual(['A', 'a', 'b', 'B'].sort(compareIds), ['A', 'B', 'a', 'b']);
  assert.deepEqual(['b', 'A', 'a'].sort(compareIds), ['A', 'a', 'b']);
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
      { id: 'cursor', name: 'cursor', displayName: 'Cursor', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.cursor/skills' }, global: { kind: 'none' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
      { id: 'CURSOR', name: 'CURSOR', displayName: 'CURSOR', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.cursor2/skills' }, global: { kind: 'none' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 2 } },
    ],
  };
  const v = validateSnapshot(base);
  assert.equal(v.valid, false);
  assert.ok(v.errors.some((e) => e.includes('case-colliding')));
});

test('registry: validate fails closed on malformed host entries', () => {
  const bad = { schemaVersion: 1, hosts: [null, { id: 42 }] };
  const v = validateSnapshot(bad);
  assert.equal(v.valid, false);
  assert.ok(Object.values(v.hostErrors).some((e) => /missing or not an object/.test(e)));
  assert.ok(Object.values(v.hostErrors).some((e) => /host id is missing/.test(e)));
});

test('registry: validate rejects invalid platform and detection data', () => {
  const mk = (patch) => ({
    schemaVersion: 1,
    hosts: [{
      id: 'x', name: 'x', displayName: 'X', universal: true, universalPrompt: true,
      destinations: { project: { kind: 'literal', path: '.x/skills' }, global: { kind: 'none' } },
      aliases: [], platforms: [], detection: { envVars: [] },
      attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 },
      ...patch,
    }],
  });
  const badPlatform = validateSnapshot(mk({ platforms: ['os/2'] }));
  assert.equal(badPlatform.valid, false);
  assert.ok(Object.values(badPlatform.hostErrors)[0].includes('unsupported platform'));
  const badEnv = validateSnapshot(mk({ detection: { envVars: ['lowercase'] } }));
  assert.equal(badEnv.valid, false);
  assert.ok(Object.values(badEnv.hostErrors)[0].includes('invalid detection env var'));
  assert.ok(validateSnapshot(mk({ platforms: SUPPORTED_PLATFORMS })).valid);
});

test('registry: validate rejects intra-host destination overlap', () => {
  const snap = {
    schemaVersion: 1,
    hosts: [
      { id: 'x', name: 'x', displayName: 'X', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'literal', path: '.agents/skills' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const v = validateSnapshot(snap);
  assert.equal(v.valid, false);
  assert.ok(Object.values(v.hostErrors)[0].includes('overlap'));
});

test('registry: diff classifies description-only as safe and path changes as review', () => {
  const prev = {
    hosts: [
      { id: 'amp', name: 'amp', displayName: 'Amp', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'join', base: 'configHome', segments: ['agents/skills'] } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const currDesc = {
    hosts: [
      { id: 'amp', name: 'amp', displayName: 'Amp Updated', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'join', base: 'configHome', segments: ['agents/skills'] } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const currPath = {
    hosts: [
      { id: 'amp', name: 'amp', displayName: 'Amp', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.amp/skills' }, global: { kind: 'join', base: 'configHome', segments: ['agents/skills'] } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const descDiff = diffSnapshots(prev, currDesc).changes[0];
  assert.equal(descDiff.authority, 'safe');
  assert.equal(descDiff.kind, 'description-change');
  const pathDiff = diffSnapshots(prev, currPath).changes[0];
  assert.equal(pathDiff.authority, 'review');
  assert.deepEqual(pathDiff.fields, ['project']);
});

test('registry: diff ignores raw formula text and flags universal changes as review', () => {
  const prev = {
    hosts: [
      { id: 'amp', name: 'amp', displayName: 'Amp', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.agents/skills', raw: "'.agents/skills'" }, global: { kind: 'join', base: 'configHome', segments: ['agents/skills'], raw: "join(configHome, 'agents/skills')" } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const curr = JSON.parse(JSON.stringify(prev));
  curr.hosts[0].destinations.project.raw = 'different raw text but same path';
  curr.hosts[0].universal = false;
  const changes = diffSnapshots(prev, curr).changes;
  assert.deepEqual(changes[0].fields, ['universal']);
  assert.equal(changes[0].authority, 'review');
});

test('registry: diff classifies safe additions vs removals', () => {
  const prev = { hosts: [] };
  const currAdd = {
    hosts: [
      { id: 'newhost', name: 'newhost', displayName: 'New', universal: true, universalPrompt: true, destinations: { project: { kind: 'literal', path: '.new/skills' }, global: { kind: 'none' } }, aliases: [], platforms: [], detection: { envVars: [] }, attribution: { upstreamFile: 'src/agents.ts', upstreamLine: 1 } },
    ],
  };
  const add = diffSnapshots(prev, currAdd);
  assert.equal(add.changes[0].kind, 'addition');
  assert.equal(add.changes[0].authority, 'safe');
  const rem = diffSnapshots(currAdd, prev);
  assert.equal(rem.changes[0].kind, 'removal');
  assert.equal(rem.changes[0].authority, 'review');
});

test('registry: diff flags source pin drift as review', () => {
  const prev = { generatedFrom: { repository: 'vercel-labs/skills', pinnedRevision: 'a'.repeat(40), upstreamFile: 'src/agents.ts' }, hosts: [] };
  const curr = { generatedFrom: { repository: 'vercel-labs/skills', pinnedRevision: 'b'.repeat(40), upstreamFile: 'src/agents.ts' }, hosts: [] };
  const changes = diffSnapshots(prev, curr).changes;
  assert.ok(changes.some((c) => c.kind === 'source-change' && c.authority === 'review'));
});

test('registry: sync rejects tampered source against the pinned hash', () => {
  const pin = loadPin();
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-registry-sync-'));
  const tampered = path.join(tmpDir, 'agents.ts');
  fs.writeFileSync(tampered, fs.readFileSync(FIXTURE, 'utf8') + '\n// tampered\n', 'utf8');
  const result = syncRegistry({ source: tampered }, { pin });
  assert.equal(result.ok, false);
  assert.match(result.errors[0], /does not match pinned contentSha256/);
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

test('registry: sync writes snapshot only when diff is safe', () => {
  const pin = loadPin();
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-registry-write-'));
  try {
    const prev = loadSnapshot();
    // same source, no drift -> should write
    const ok = syncRegistry({ source: FIXTURE, allowReview: true }, { pin, previous: prev });
    assert.equal(ok.ok, true);
    assert.equal(ok.diff.summary.review, 0);
    assert.equal(ok.shouldWrite, true);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('registry: no upstream detector code executes — snapshot is pure data', () => {
  const snapshot = loadSnapshot();
  const text = JSON.stringify(snapshot);
  assert.doesNotMatch(text, /detectInstalled/);
  assert.doesNotMatch(text, /existsSync/);
  assert.doesNotMatch(text, /=>/);
});
