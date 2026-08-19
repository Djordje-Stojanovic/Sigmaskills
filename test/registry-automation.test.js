import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { diffSnapshots } from '../src/registry/diff.js';
import { CHECKOUT_ACTION_PIN, SETUP_NODE_ACTION_PIN } from '../src/release.js';
import {
  GENERATED_BRANCH_PREFIX,
  REGISTRY_ALLOWLIST,
  REGISTRY_SYNC_WORKFLOW_FILE,
  classifySemanticAuthority,
  evaluateAutoAuthorization,
  executeRegistryAutomation,
  formatRegistryPrBody,
  inspectRegistrySyncWorkflow,
  planGeneratedBranchCleanup,
  planRegistrySync,
} from '../src/registry/automation.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FIXTURE = path.join(ROOT, 'test/fixtures/vercel-skills/src/agents.ts');
const SHA_A = 'a'.repeat(40);
const SHA_B = 'b'.repeat(40);
const SHA_C = 'c'.repeat(40);
const UPSTREAM = 'd'.repeat(40);

function host(id, extra = {}) {
  return {
    id,
    name: extra.name ?? id,
    displayName: extra.displayName ?? id,
    universal: extra.universal ?? true,
    universalPrompt: extra.universalPrompt ?? true,
    destinations: extra.destinations ?? {
      project: { kind: 'literal', path: `.${id}/skills` },
      global: { kind: 'none' },
    },
    aliases: extra.aliases ?? [],
    platforms: extra.platforms ?? [],
    detection: extra.detection ?? { envVars: [] },
    attribution: extra.attribution ?? { upstreamFile: 'src/agents.ts', upstreamLine: 1 },
  };
}

function snap(hosts, revision = SHA_A) {
  return {
    schemaVersion: 1,
    generatedFrom: {
      repository: 'vercel-labs/skills',
      pinnedRevision: revision,
      upstreamFile: 'src/agents.ts',
    },
    hosts,
  };
}

function classifyDiff(previous, current) {
  return classifySemanticAuthority(diffSnapshots(previous, current));
}

test('registry automation: only validated new hosts and description-only changes stay auto-eligible', () => {
  const base = snap([host('amp', { displayName: 'Amp' })]);
  const description = snap([host('amp', { displayName: 'Amp CLI' })], SHA_B);
  const added = snap([
    host('amp', { displayName: 'Amp' }),
    host('newhost', { displayName: 'New' }),
  ], SHA_B);
  const unsafeAdd = snap([
    host('amp', { displayName: 'Amp' }),
    host('evil', {
      destinations: { project: { kind: 'literal', path: '../escape' }, global: { kind: 'none' } },
    }),
  ], SHA_B);

  assert.equal(classifyDiff(base, description).autoEligible, true);
  assert.equal(classifyDiff(base, added).autoEligible, true);
  assert.equal(classifyDiff(base, unsafeAdd).autoEligible, false);

  const pinOnly = snap([host('amp', { displayName: 'Amp' })], SHA_B);
  assert.equal(classifyDiff(base, pinOnly).autoEligible, true);
});

test('registry automation: paths, ids, aliases, detection, platform, membership, removals, and unknown changes stop', () => {
  const base = snap([host('amp', { displayName: 'Amp' })]);
  const cases = [
    snap([host('amp', {
      displayName: 'Amp',
      destinations: { project: { kind: 'literal', path: '.moved/skills' }, global: { kind: 'none' } },
    })]),
    snap([host('amp', { displayName: 'Amp', name: 'renamed' })]),
    snap([host('renamed', { displayName: 'Amp' })]),
    snap([host('amp', { displayName: 'Amp', aliases: ['amp-cli'] })]),
    snap([host('amp', { displayName: 'Amp', detection: { envVars: ['AMP_HOME'] } })]),
    snap([host('amp', { displayName: 'Amp', platforms: ['linux'] })]),
    snap([host('amp', { displayName: 'Amp', universal: false })]),
    snap([]),
  ];
  for (const current of cases) {
    const classified = classifyDiff(base, current);
    assert.equal(classified.autoEligible, false, classified.blockedReasons.join('; '));
    assert.ok(classified.blockedReasons.length > 0);
  }

  const unknown = classifySemanticAuthority({
    summary: { added: 0, removed: 0, changed: 1, safe: 0, review: 1 },
    changes: [{ id: 'amp', kind: 'rewrite', authority: 'review' }],
  });
  assert.equal(unknown.autoEligible, false);
  assert.ok(unknown.blockedReasons.some((reason) => /unknown/i.test(reason)));
});

test('registry automation: generated files must stay on the registry allowlist', () => {
  assert.deepEqual(REGISTRY_ALLOWLIST, [
    'registry/agent-hosts.json',
    'registry/source.json',
    'test/fixtures/vercel-skills/src/agents.ts',
  ]);
  const ok = evaluateAutoAuthorization({
    origin: 'same-repo',
    headRef: `${GENERATED_BRANCH_PREFIX}deadbeef`,
    headSha: SHA_B,
    expectedGeneratedSha: SHA_B,
    expectedHeadSha: SHA_A,
    currentDefaultSha: SHA_A,
    files: REGISTRY_ALLOWLIST,
    checkConclusion: 'success',
    concurrentRun: false,
    classification: { autoEligible: true, blockedReasons: [] },
  });
  assert.equal(ok.autoAuthorized, true);

  const extra = evaluateAutoAuthorization({
    ...ok,
    origin: 'same-repo',
    headRef: `${GENERATED_BRANCH_PREFIX}deadbeef`,
    headSha: SHA_B,
    expectedGeneratedSha: SHA_B,
    expectedHeadSha: SHA_A,
    currentDefaultSha: SHA_A,
    files: [...REGISTRY_ALLOWLIST, 'src/cli.js'],
    checkConclusion: 'success',
    concurrentRun: false,
    classification: { autoEligible: true, blockedReasons: [] },
  });
  assert.equal(extra.autoAuthorized, false);
  assert.ok(extra.deniedReasons.some((reason) => /allowlist/i.test(reason)));
});

test('registry automation: forks, human branches, stale heads, moved main, failed checks, and concurrent runs cannot be auto-authorized', () => {
  const eligible = {
    origin: 'same-repo',
    headRef: `${GENERATED_BRANCH_PREFIX}deadbeef`,
    headSha: SHA_B,
    expectedGeneratedSha: SHA_B,
    expectedHeadSha: SHA_A,
    currentDefaultSha: SHA_A,
    files: [...REGISTRY_ALLOWLIST],
    checkConclusion: 'success',
    concurrentRun: false,
    classification: { autoEligible: true, blockedReasons: [] },
  };
  assert.equal(evaluateAutoAuthorization(eligible).autoAuthorized, true);

  const denials = [
    [{ origin: 'fork' }, /fork/i],
    [{ headRef: 'feature/human-work' }, /human|generated/i],
    [{ headSha: SHA_C }, /stale/i],
    [{ currentDefaultSha: SHA_C }, /moved|default branch/i],
    [{ checkConclusion: 'failure' }, /check/i],
    [{ concurrentRun: true }, /concurrent/i],
  ];
  for (const [patch, pattern] of denials) {
    const result = evaluateAutoAuthorization({ ...eligible, ...patch });
    assert.equal(result.autoAuthorized, false, JSON.stringify(patch));
    assert.ok(result.deniedReasons.some((reason) => pattern.test(reason)), result.deniedReasons.join('; '));
  }
});

test('registry automation: even auto-authorized plans cannot merge, publish, close unrelated work, or delete unrelated branches', () => {
  const result = evaluateAutoAuthorization({
    origin: 'same-repo',
    headRef: `${GENERATED_BRANCH_PREFIX}deadbeef`,
    headSha: SHA_B,
    expectedGeneratedSha: SHA_B,
    expectedHeadSha: SHA_A,
    currentDefaultSha: SHA_A,
    files: [...REGISTRY_ALLOWLIST],
    checkConclusion: 'success',
    concurrentRun: false,
    classification: { autoEligible: true, blockedReasons: [] },
  });
  assert.equal(result.autoAuthorized, true);
  assert.equal(result.actions.merge, false);
  assert.equal(result.actions.publishNpm, false);
  assert.equal(result.actions.closeUnrelatedIssues, false);
  assert.equal(result.actions.closeUnrelatedPullRequests, false);
  assert.equal(result.actions.deleteUnrelatedBranches, false);
});

test('registry automation: generated-branch cleanup dry-run refuses human, protected, and unrelated refs', () => {
  const plan = planGeneratedBranchCleanup({
    dryRun: true,
    branches: [
      { name: `${GENERATED_BRANCH_PREFIX}${UPSTREAM.slice(0, 12)}`, generated: true },
      { name: 'feature/sigma-installer', generated: false },
      { name: 'main', generated: false },
      { name: 'registry/please-delete-me', generated: false },
    ],
    protectedRefs: ['main'],
  });
  assert.equal(plan.dryRun, true);
  assert.deepEqual(plan.wouldDelete, [`${GENERATED_BRANCH_PREFIX}${UPSTREAM.slice(0, 12)}`]);
  assert.ok(plan.refused.some((item) => item.name === 'feature/sigma-installer'));
  assert.ok(plan.refused.some((item) => item.name === 'main'));
  assert.ok(plan.refused.some((item) => item.name === 'registry/please-delete-me'));
  assert.equal(plan.deleteUnrelatedBranches, false);
});

test('registry automation: trusted converter plans allowlisted files from a pinned upstream revision', () => {
  const fixture = fs.readFileSync(FIXTURE, 'utf8');
  const previousPin = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry/source.json'), 'utf8'));
  const previousSnapshot = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry/agent-hosts.json'), 'utf8'));
  const plan = planRegistrySync({
    expectedHeadSha: SHA_A,
    currentHeadSha: SHA_A,
    converterRevision: SHA_A,
    upstreamRevision: UPSTREAM,
    upstreamText: fixture,
    previousSnapshot,
    previousPin,
  });
  assert.equal(plan.ok, true);
  assert.equal(plan.validation.valid, true);
  assert.deepEqual(plan.files.sort(), [...REGISTRY_ALLOWLIST].sort());
  assert.equal(plan.pin.pinnedRevision, UPSTREAM);
  assert.notEqual(plan.pin.pinnedRevision, previousPin.pinnedRevision);

  const driftedConverter = planRegistrySync({
    expectedHeadSha: SHA_A,
    currentHeadSha: SHA_A,
    converterRevision: SHA_B,
    upstreamRevision: UPSTREAM,
    upstreamText: fixture,
    previousSnapshot,
    previousPin,
  });
  assert.equal(driftedConverter.ok, false);
  assert.match(driftedConverter.errors.join('\n'), /trusted|expected head/i);
});

test('registry automation: pull request body carries upstream commit, semantic diff, validation, and blocked reasons', () => {
  const previous = snap([host('amp', { displayName: 'Amp' })]);
  const current = snap([
    host('amp', {
      displayName: 'Amp',
      destinations: { project: { kind: 'literal', path: '.moved/skills' }, global: { kind: 'none' } },
    }),
  ], SHA_B);
  const diff = diffSnapshots(previous, current);
  const classification = classifySemanticAuthority(diff);
  const body = formatRegistryPrBody({
    upstreamRevision: UPSTREAM,
    expectedHeadSha: SHA_A,
    diff,
    validation: { valid: true, errors: [], hostErrors: {} },
    classification,
  });
  assert.match(body, new RegExp(UPSTREAM));
  assert.match(body, /semantic diff/i);
  assert.match(body, /amp/);
  assert.match(body, /validation/i);
  assert.match(body, /blocked/i);
  assert.match(body, /does not auto-merge/i);
  assert.match(body, /npm/i);
});

test('registry automation dry-run: execute classifies authority and cleanup without merging or publishing', async () => {
  const fixture = fs.readFileSync(FIXTURE, 'utf8');
  const previousPin = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry/source.json'), 'utf8'));
  const previousSnapshot = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry/agent-hosts.json'), 'utf8'));
  let wrote = false;
  let merged = false;
  let published = false;
  const result = await executeRegistryAutomation({
    mode: 'generate',
    dryRun: true,
    expectedHead: SHA_A,
    upstreamRevision: UPSTREAM,
  }, {
    converterSha: async () => SHA_A,
    currentDefaultSha: async () => SHA_A,
    fetchUpstreamText: async () => fixture,
    readPin: async () => previousPin,
    readSnapshot: async () => previousSnapshot,
    hasConcurrentRun: async () => false,
    writeAllowlisted: async () => { wrote = true; },
    mergePullRequest: async () => { merged = true; },
    publishNpm: async () => { published = true; },
  });
  assert.equal(result.dryRun, true);
  assert.equal(result.ok, true);
  assert.equal(wrote, false);
  assert.equal(merged, false);
  assert.equal(published, false);
  assert.equal(result.actions.merge, false);
  assert.equal(result.actions.publishNpm, false);
  assert.match(result.body, new RegExp(UPSTREAM));

  const cleanup = await executeRegistryAutomation({
    mode: 'cleanup',
    dryRun: true,
  }, {
    listBranches: async () => [
      { name: `${GENERATED_BRANCH_PREFIX}abcd`, generated: true },
      { name: 'feature/sigma-installer', generated: false },
    ],
    protectedRefs: async () => ['main'],
    deleteBranch: async () => { throw new Error('delete must not run in dry-run'); },
  });
  assert.equal(cleanup.dryRun, true);
  assert.deepEqual(cleanup.wouldDelete, [`${GENERATED_BRANCH_PREFIX}abcd`]);
  assert.equal(cleanup.deleteUnrelatedBranches, false);
});

test('trusted registry-sync workflow: pinned actions, expected-head checkout, no untrusted execution, no publish or unrelated mutation', () => {
  const yaml = fs.readFileSync(path.join(ROOT, '.github', 'workflows', REGISTRY_SYNC_WORKFLOW_FILE), 'utf8');
  const inspected = inspectRegistrySyncWorkflow(yaml);
  assert.equal(inspected.ok, true, inspected.errors.join('\n'));
  assert.equal(inspected.checkoutPin, CHECKOUT_ACTION_PIN);
  assert.equal(inspected.setupNodePin, SETUP_NODE_ACTION_PIN);
  assert.equal(inspected.usesFloatingTags, false);
  assert.equal(inspected.permissions['id-token'], undefined);
  assert.equal(inspected.generate.permissions.contents, 'write');
  assert.equal(inspected.generate.permissions['pull-requests'], 'write');
  assert.equal(inspected.generate.permissions.issues, undefined);
  assert.doesNotMatch(yaml, /pull_request:/);
  assert.doesNotMatch(yaml, /github\.event\.pull_request\.head\.sha/);
  assert.doesNotMatch(yaml, /npm publish/);
  assert.doesNotMatch(yaml, /gh pr merge/);
  assert.doesNotMatch(yaml, /gh issue close/);
  assert.match(yaml, /node \.\/src\/registry\/automation-ci\.js generate/);
  assert.match(yaml, /EXPECTED_HEAD/);
  assert.match(yaml, /concurrency:/);
});
