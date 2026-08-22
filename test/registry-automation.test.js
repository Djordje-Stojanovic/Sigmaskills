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
  calculateRegistryPatchVersion,
  classifySemanticAuthority,
  evaluateAutoAuthorization,
  executeRegistryAutomation,
  formatRegistryPrBody,
  inspectRegistrySyncWorkflow,
  planGeneratedBranchCleanup,
  planGeneratedBranchPush,
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

function eligibleAuthorization(patch = {}) {
  return {
    origin: 'same-repo',
    headRef: `${GENERATED_BRANCH_PREFIX}deadbeef`,
    headSha: SHA_B,
    expectedGeneratedSha: SHA_B,
    expectedHeadSha: SHA_A,
    currentDefaultSha: SHA_A,
    files: [...REGISTRY_ALLOWLIST],
    checkConclusion: 'success',
    concurrentRun: false,
    fromTrustedWorkflow: true,
    defaultBranchProtected: true,
    classification: { autoEligible: true, blockedReasons: [] },
    ...patch,
  };
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
  const ok = evaluateAutoAuthorization(eligibleAuthorization({ files: REGISTRY_ALLOWLIST }));
  assert.equal(ok.autoAuthorized, true);

  const extra = evaluateAutoAuthorization(eligibleAuthorization({
    files: [...REGISTRY_ALLOWLIST, 'src/cli.js'],
  }));
  assert.equal(extra.autoAuthorized, false);
  assert.ok(extra.deniedReasons.some((reason) => /allowlist/i.test(reason)));
});

test('registry automation: forks, human branches, stale heads, moved main, failed checks, and concurrent runs cannot be auto-authorized', () => {
  const eligible = eligibleAuthorization();
  assert.equal(evaluateAutoAuthorization(eligible).autoAuthorized, true);

  const denials = [
    [{ origin: 'fork' }, /fork/i],
    [{ headRef: 'feature/human-work' }, /human|generated/i],
    [{ headSha: SHA_C }, /stale/i],
    [{ currentDefaultSha: SHA_C }, /moved|default branch/i],
    [{ checkConclusion: 'failure' }, /check/i],
    [{ concurrentRun: true }, /concurrent/i],
    [{ fromTrustedWorkflow: false }, /trusted.*workflow/i],
    [{ defaultBranchProtected: false }, /protected/i],
  ];
  for (const [patch, pattern] of denials) {
    const result = evaluateAutoAuthorization({ ...eligible, ...patch });
    assert.equal(result.autoAuthorized, false, JSON.stringify(patch));
    assert.ok(result.deniedReasons.some((reason) => pattern.test(reason)), result.deniedReasons.join('; '));
  }
});

test('registry automation: auto-authorized plans may merge and patch-publish, but cannot close unrelated work or delete unrelated branches', () => {
  const result = evaluateAutoAuthorization(eligibleAuthorization());
  assert.equal(result.autoAuthorized, true);
  assert.equal(result.actions.merge, true);
  assert.equal(result.actions.publishNpm, true);
  assert.equal(result.actions.closeUnrelatedIssues, false);
  assert.equal(result.actions.closeUnrelatedPullRequests, false);
  assert.equal(result.actions.deleteUnrelatedBranches, false);
});

test('registry automation: leftover generated branch is replaced; matching open PR is reused; human branches stay refused', () => {
  const generated = `${GENERATED_BRANCH_PREFIX}${UPSTREAM.slice(0, 12)}`;

  const replace = planGeneratedBranchPush({
    branch: generated,
    remoteExists: true,
    openPullRequest: false,
  });
  assert.equal(replace.ok, true);
  assert.equal(replace.action, 'replace');
  assert.equal(replace.forcePush, true);
  assert.equal(replace.createPr, true);

  const reuse = planGeneratedBranchPush({
    branch: generated,
    remoteExists: true,
    openPullRequest: true,
  });
  assert.equal(reuse.ok, true);
  assert.equal(reuse.action, 'reuse');
  assert.equal(reuse.forcePush, false);
  assert.equal(reuse.createPr, false);

  const create = planGeneratedBranchPush({
    branch: generated,
    remoteExists: false,
    openPullRequest: false,
  });
  assert.equal(create.ok, true);
  assert.equal(create.action, 'create');
  assert.equal(create.forcePush, false);
  assert.equal(create.createPr, true);

  const refused = planGeneratedBranchPush({
    branch: 'feature/sigma-installer',
    remoteExists: true,
    openPullRequest: false,
  });
  assert.equal(refused.ok, false);
  assert.equal(refused.action, 'refuse');
  assert.equal(refused.forcePush, false);
  assert.equal(refused.createPr, false);
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
  assert.match(body, /owner review/i);
  assert.match(body, /will not auto-merge/i);
  assert.match(body, /npm/i);

  const safeBody = formatRegistryPrBody({
    upstreamRevision: UPSTREAM,
    expectedHeadSha: SHA_A,
    diff: { changes: [{ id: 'newhost', kind: 'addition', authority: 'safe' }] },
    validation: { valid: true, errors: [], hostErrors: {} },
    classification: { autoEligible: true, blockedReasons: [] },
  });
  assert.match(safeBody, /may auto-merge/i);
  assert.match(safeBody, /patch/i);
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
  assert.equal(result.merged, false);
  assert.equal(result.published, false);
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

test('registry automation generate: leftover generated branch is force-replaced; matching open PR is reused', async () => {
  const fixture = fs.readFileSync(FIXTURE, 'utf8');
  const previousPin = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry/source.json'), 'utf8'));
  const previousSnapshot = JSON.parse(fs.readFileSync(path.join(ROOT, 'registry/agent-hosts.json'), 'utf8'));
  const calls = { wrote: 0, created: [] };
  const generateIo = (inspect) => ({
    converterSha: async () => SHA_A,
    currentDefaultSha: async () => SHA_A,
    fetchUpstreamText: async () => fixture,
    readPin: async () => previousPin,
    readSnapshot: async () => previousSnapshot,
    hasConcurrentRun: async () => false,
    inspectGeneratedBranch: async () => inspect,
    writeAllowlisted: async () => { calls.wrote += 1; },
    createPullRequest: async (payload) => { calls.created.push(payload); },
  });

  const replaced = await executeRegistryAutomation({
    mode: 'generate',
    dryRun: false,
    expectedHead: SHA_A,
    upstreamRevision: UPSTREAM,
  }, generateIo({ remoteExists: true, openPullRequest: false }));
  assert.equal(replaced.ok, true);
  assert.equal(replaced.pushPlan.action, 'replace');
  assert.equal(replaced.pushPlan.forcePush, true);
  assert.equal(calls.wrote, 1);
  assert.equal(calls.created.length, 1);
  assert.equal(calls.created[0].pushPlan.forcePush, true);
  assert.equal(calls.created[0].pushPlan.createPr, true);

  calls.wrote = 0;
  calls.created = [];
  const reused = await executeRegistryAutomation({
    mode: 'generate',
    dryRun: false,
    expectedHead: SHA_A,
    upstreamRevision: UPSTREAM,
  }, generateIo({ remoteExists: true, openPullRequest: true }));
  assert.equal(reused.ok, true);
  assert.equal(reused.pushPlan.action, 'reuse');
  assert.equal(reused.pushPlan.forcePush, false);
  assert.equal(calls.wrote, 0);
  assert.deepEqual(calls.created, []);
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
  assert.doesNotMatch(yaml, /gh issue close/);
  assert.match(yaml, /node \.\/src\/registry\/automation-ci\.js generate/);
  assert.match(yaml, /node \.\/src\/registry\/automation-ci\.js auto-merge/);
  assert.match(yaml, /EXPECTED_HEAD/);
  assert.match(yaml, /concurrency:/);
  assert.equal(inspected.autoMerge.permissions['id-token'], 'write');
  assert.equal(inspected.autoMerge.permissions.contents, 'write');
  assert.equal(inspected.autoMerge.permissions['pull-requests'], 'write');
  assert.equal(inspected.autoMerge.permissions.issues, undefined);
  assert.equal(inspected.generate.permissions['id-token'], undefined);
});

test('registry patch version: serialize against actual npm and GitHub state, always patch, never major or minor', () => {
  assert.equal(calculateRegistryPatchVersion({
    packageVersion: '0.1.0',
    npmVersions: ['0.1.0'],
    githubVersions: ['0.1.0'],
  }), '0.1.1');
  assert.equal(calculateRegistryPatchVersion({
    packageVersion: '0.1.0',
    npmVersions: ['0.2.0'],
    githubVersions: ['0.1.5'],
  }), '0.2.1');
  assert.throws(
    () => calculateRegistryPatchVersion({ packageVersion: '0.1.0', requestedBump: 'minor' }),
    /major|minor|patch/i,
  );
  assert.throws(
    () => calculateRegistryPatchVersion({ packageVersion: '0.1.0', requestedBump: 'major' }),
    /major|minor|patch/i,
  );
});

function autoMergeIo(overrides = {}) {
  const calls = {
    merged: [],
    published: [],
    deleted: [],
    closedIssues: [],
    closedPrs: [],
    skillWrites: [],
    versionLocks: 0,
  };
  return {
    calls,
    io: {
      inspectPullRequest: async () => ({
        origin: 'same-repo',
        headRef: `${GENERATED_BRANCH_PREFIX}deadbeef`,
        headSha: SHA_B,
        expectedGeneratedSha: SHA_B,
        files: [...REGISTRY_ALLOWLIST],
        checkConclusion: 'success',
        number: 99,
        ...overrides.pr,
      }),
      currentDefaultSha: async () => SHA_A,
      expectedHeadSha: async () => SHA_A,
      hasConcurrentRun: async () => false,
      fromTrustedWorkflow: async () => true,
      defaultBranchProtected: async () => true,
      classification: async () => classifyDiff(
        snap([host('amp', { displayName: 'Amp' })]),
        snap([
          host('amp', { displayName: 'Amp' }),
          host('newhost', { displayName: 'New' }),
        ], SHA_B),
      ),
      acquireVersionLock: async () => { calls.versionLocks += 1; return { release: async () => {} }; },
      reconcilePublishedState: async () => ({
        packageVersion: '0.1.0',
        npmVersions: ['0.1.0'],
        githubVersions: ['0.1.0'],
      }),
      mergePullRequest: async (pr) => { calls.merged.push(pr.number); return { sha: SHA_C, merged: true }; },
      verifyMerge: async () => ({ ok: true, sha: SHA_C }),
      commitPatchIdentities: async () => ({ commit: 'e'.repeat(40), version: '0.1.1' }),
      trustedPatchRelease: async (payload) => {
        calls.published.push(payload);
        return {
          ok: true,
          version: payload.version,
          recovery: { ok: true, publishNpm: true, createGithubRelease: true, createTag: true },
          npm: { version: payload.version, integrity: 'sha512-match' },
          github: { tag: `v${payload.version}`, targetCommit: payload.commit },
        };
      },
      verifyPublication: async () => ({ ok: true, npmMatches: true, githubMatches: true }),
      deleteBranch: async (name) => { calls.deleted.push(name); },
      closeIssue: async (n) => { calls.closedIssues.push(n); },
      closePullRequest: async (n) => { calls.closedPrs.push(n); },
      writeSkill: async (id) => { calls.skillWrites.push(id); },
      ...overrides.io,
    },
  };
}

test('registry automation: empty diffs and missing generated files cannot be auto-authorized', () => {
  const empty = evaluateAutoAuthorization(eligibleAuthorization({ files: [] }));
  assert.equal(empty.autoAuthorized, false);
  assert.ok(empty.deniedReasons.some((reason) => /empty/i.test(reason)));
});

test('end-to-end safe-addition rehearsal: merge, trusted patch Release, then delete only the generated branch', async () => {
  const { io, calls } = autoMergeIo();
  const result = await executeRegistryAutomation({
    mode: 'auto-merge',
    dryRun: false,
    expectedHead: SHA_A,
  }, io);
  assert.equal(result.ok, true);
  assert.equal(result.merged, true);
  assert.equal(result.published, true);
  assert.equal(result.version, '0.1.1');
  assert.equal(result.bump, 'patch');
  assert.deepEqual(calls.merged, [99]);
  assert.equal(calls.published.length, 1);
  assert.equal(calls.published[0].version, '0.1.1');
  assert.equal(calls.published[0].bump, 'patch');
  assert.ok(calls.published[0].usesTrustedPatchPrimitive);
  assert.deepEqual(calls.deleted, [`${GENERATED_BRANCH_PREFIX}deadbeef`]);
  assert.deepEqual(calls.closedIssues, []);
  assert.deepEqual(calls.closedPrs, []);
  assert.deepEqual(calls.skillWrites, []);
  assert.equal(calls.versionLocks, 1);
  assert.equal(result.actions.closeUnrelatedIssues, false);
  assert.equal(result.actions.deleteUnrelatedBranches, false);
});

test('end-to-end blocked path-change rehearsal: owner review, no merge, no publish, no branch delete', async () => {
  const { io, calls } = autoMergeIo({
    io: {
      classification: async () => classifyDiff(
        snap([host('amp', { displayName: 'Amp' })]),
        snap([host('amp', {
          displayName: 'Amp',
          destinations: { project: { kind: 'literal', path: '.moved/skills' }, global: { kind: 'none' } },
        })]),
      ),
    },
  });
  const result = await executeRegistryAutomation({
    mode: 'auto-merge',
    dryRun: false,
    expectedHead: SHA_A,
  }, io);
  assert.equal(result.ok, true);
  assert.equal(result.autoAuthorized, false);
  assert.equal(result.merged, false);
  assert.equal(result.published, false);
  assert.deepEqual(calls.merged, []);
  assert.deepEqual(calls.published, []);
  assert.deepEqual(calls.deleted, []);
  assert.ok(result.deniedReasons.some((reason) => /project/i.test(reason)));
});

test('auto-merge: partial trusted patch success is recoverable and never overwrites an npm version', async () => {
  const { io, calls } = autoMergeIo({
    io: {
      trustedPatchRelease: async (payload) => ({
        ok: true,
        version: payload.version,
        recovery: { ok: true, publishNpm: false, createGithubRelease: true, createTag: true },
        npm: { version: payload.version, integrity: 'sha512-existing' },
        github: { tag: `v${payload.version}`, targetCommit: payload.commit },
      }),
    },
  });
  const recovered = await executeRegistryAutomation({ mode: 'auto-merge', dryRun: false, expectedHead: SHA_A }, io);
  assert.equal(recovered.published, true);
  assert.equal(recovered.recovery.publishNpm, false);
  assert.deepEqual(calls.deleted, [`${GENERATED_BRANCH_PREFIX}deadbeef`]);

  const clashIo = autoMergeIo({
    io: {
      trustedPatchRelease: async () => ({
        ok: false,
        errors: ['npm already has sigmaskills@0.1.1 with a different digest; versions are immutable.'],
        recovery: { ok: false, publishNpm: false },
      }),
    },
  });
  const clash = await executeRegistryAutomation({
    mode: 'auto-merge',
    dryRun: false,
    expectedHead: SHA_A,
  }, clashIo.io);
  assert.equal(clash.ok, false);
  assert.equal(clash.branchDeleted, false);
  assert.deepEqual(clashIo.calls.deleted, []);
  assert.match(clash.errors.join('\n'), /different digest|immutable/i);
});

