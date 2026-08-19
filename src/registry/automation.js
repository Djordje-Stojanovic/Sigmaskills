'use strict';

/**
 * Guarded Agent Host registry pull-request automation.
 *
 * Converter code always comes from an exact trusted default-branch SHA.
 * Upstream TypeScript is fetched as pinned data and never executed.
 * Generated trees are limited to the registry/attribution allowlist.
 * Classification records whether a change could later be auto-merged;
 * this ticket never merges, publishes npm, closes unrelated work, or
 * deletes unrelated branches.
 */

import crypto from 'node:crypto';
import { parseAgents } from './parse.js';
import { buildSnapshot, normalizeHost } from './normalize.js';
import { validateSnapshot } from './validate.js';
import { diffSnapshots } from './diff.js';
import { CHECKOUT_ACTION_PIN, SETUP_NODE_ACTION_PIN } from '../release.js';

export const REGISTRY_SYNC_WORKFLOW_FILE = 'registry-sync.yml';
export const GENERATED_BRANCH_PREFIX = 'registry/sync-';
export const REGISTRY_ALLOWLIST = Object.freeze([
  'registry/agent-hosts.json',
  'registry/source.json',
  'test/fixtures/vercel-skills/src/agents.ts',
]);

const REVISION_PATTERN = /^[0-9a-f]{40}$/;
const BLOCKED_ACTIONS = Object.freeze({
  merge: false,
  publishNpm: false,
  closeUnrelatedIssues: false,
  closeUnrelatedPullRequests: false,
  deleteUnrelatedBranches: false,
});

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

function posixPath(file) {
  return String(file || '').replace(/\\/g, '/');
}

export function assertAllowlistedPaths(files) {
  const denied = [];
  for (const file of files || []) {
    const normalized = posixPath(file);
    if (!REGISTRY_ALLOWLIST.includes(normalized)) denied.push(normalized);
  }
  return {
    ok: denied.length === 0,
    denied,
  };
}

export function classifySemanticAuthority(diff) {
  const blockedReasons = [];
  for (const change of diff && diff.changes ? diff.changes : []) {
    if (change.kind === 'source-change') continue;
    if (change.kind === 'description-change') continue;
    if (change.kind === 'addition') {
      if (change.authority !== 'safe') {
        blockedReasons.push(`${change.id}: new host failed destination validation`);
      }
      continue;
    }
    if (change.kind === 'removal') {
      blockedReasons.push(`${change.id}: removal`);
      continue;
    }
    if (change.kind === 'change') {
      const fields = change.fields && change.fields.length ? change.fields.join(', ') : 'identity';
      blockedReasons.push(`${change.id}: ${fields}`);
      continue;
    }
    blockedReasons.push(`${change.id}: unknown change ${change.kind}`);
  }
  return {
    autoEligible: blockedReasons.length === 0,
    blockedReasons,
  };
}

export function evaluateAutoAuthorization(input) {
  const deniedReasons = [];
  if (input.origin === 'fork') deniedReasons.push('fork pull requests cannot be auto-authorized');
  if (!String(input.headRef || '').startsWith(GENERATED_BRANCH_PREFIX)) {
    deniedReasons.push('human branches cannot be auto-authorized; ref is not a generated registry-sync branch');
  }
  if (input.headSha && input.expectedGeneratedSha && input.headSha !== input.expectedGeneratedSha) {
    deniedReasons.push('stale generated head cannot be auto-authorized');
  }
  if (input.currentDefaultSha && input.expectedHeadSha && input.currentDefaultSha !== input.expectedHeadSha) {
    deniedReasons.push('moved default branch cannot be auto-authorized');
  }
  if (input.checkConclusion && input.checkConclusion !== 'success') {
    deniedReasons.push('failed or incomplete checks cannot be auto-authorized');
  }
  if (input.concurrentRun) deniedReasons.push('concurrent registry-sync runs cannot be auto-authorized');
  const allowlist = assertAllowlistedPaths(input.files);
  if (!allowlist.ok) {
    deniedReasons.push(`generated changes escape the registry allowlist: ${allowlist.denied.join(', ')}`);
  }
  if (input.classification && input.classification.autoEligible === false) {
    deniedReasons.push(...(input.classification.blockedReasons || ['semantic classification is blocked']));
  }
  return {
    autoAuthorized: deniedReasons.length === 0,
    deniedReasons,
    actions: { ...BLOCKED_ACTIONS },
  };
}

export function planGeneratedBranchCleanup({ dryRun = true, branches = [], protectedRefs = [] }) {
  const protectedSet = new Set(protectedRefs);
  const wouldDelete = [];
  const refused = [];
  for (const branch of branches) {
    const name = branch.name;
    if (protectedSet.has(name)) {
      refused.push({ name, reason: 'protected' });
      continue;
    }
    const generated = branch.generated === true || name.startsWith(GENERATED_BRANCH_PREFIX);
    if (!generated || !name.startsWith(GENERATED_BRANCH_PREFIX)) {
      refused.push({ name, reason: 'not-generated' });
      continue;
    }
    wouldDelete.push(name);
  }
  return {
    dryRun: dryRun !== false,
    wouldDelete,
    refused,
    deleteUnrelatedBranches: false,
  };
}

export function planRegistrySync({
  expectedHeadSha,
  currentHeadSha,
  converterRevision,
  upstreamRevision,
  upstreamText,
  previousSnapshot,
  previousPin,
}) {
  const errors = [];
  if (!REVISION_PATTERN.test(String(expectedHeadSha || ''))) {
    errors.push('expected head SHA must be an immutable 40-hex revision');
  }
  if (!REVISION_PATTERN.test(String(upstreamRevision || ''))) {
    errors.push('upstream revision must be an immutable 40-hex pin');
  }
  if (converterRevision !== expectedHeadSha) {
    errors.push('converter is not the trusted expected head; generated and upstream branch code must not run');
  }
  if (errors.length > 0) return { ok: false, errors, files: [], hasChanges: false };

  const pin = {
    repository: previousPin.repository,
    pinnedRevision: upstreamRevision,
    upstreamFile: previousPin.upstreamFile,
    contentSha256: sha256(upstreamText),
  };
  const parsed = parseAgents(upstreamText);
  const hosts = parsed.map((host) => normalizeHost(host, pin));
  const snapshot = buildSnapshot(hosts, pin);
  const validation = validateSnapshot(snapshot);
  if (!validation.valid) {
    return {
      ok: false,
      errors: [...(validation.errors || []), ...Object.values(validation.hostErrors || {})],
      validation,
      pin,
      snapshot,
      files: [],
      hasChanges: false,
    };
  }

  const diff = previousSnapshot ? diffSnapshots(previousSnapshot, snapshot) : { summary: {}, changes: [] };
  const classification = classifySemanticAuthority(diff);
  const files = [...REGISTRY_ALLOWLIST];
  const hasChanges = JSON.stringify(previousSnapshot) !== JSON.stringify(snapshot)
    || JSON.stringify(previousPin) !== JSON.stringify(pin);

  return {
    ok: true,
    errors: [],
    expectedHeadSha,
    currentHeadSha,
    converterRevision,
    upstreamRevision,
    pin,
    snapshot,
    upstreamText,
    validation,
    diff,
    classification,
    files,
    hasChanges,
    movedDefaultBranch: currentHeadSha !== expectedHeadSha,
  };
}

export function formatRegistryPrBody(plan) {
  const changes = (plan.diff && plan.diff.changes) || [];
  const diffLines = changes.length === 0
    ? ['- (no host semantic changes)']
    : changes.map((change) => {
      const fields = change.fields && change.fields.length ? ` [${change.fields.join(', ')}]` : '';
      return `- ${change.authority || 'n/a'} ${change.id} ${change.kind}${fields}`;
    });
  const validation = plan.validation || {};
  const hostErrors = Object.entries(validation.hostErrors || {}).map(([id, err]) => `- ${id}: ${err}`);
  const blocked = (plan.classification && plan.classification.blockedReasons) || [];
  return [
    '## Agent Host registry sync',
    '',
    `Upstream commit: \`${plan.upstreamRevision}\``,
    `Expected default-branch head: \`${plan.expectedHeadSha || ''}\``,
    '',
    '### Semantic diff',
    '',
    ...diffLines,
    '',
    '### Validation evidence',
    '',
    `- valid: ${validation.valid === true}`,
    ...(validation.errors || []).map((err) => `- ${err}`),
    ...hostErrors,
    '',
    '### Blocked reasons',
    '',
    ...(blocked.length ? blocked.map((reason) => `- ${reason}`) : ['- none; classified as later-auto-mergeable']),
    '',
    'This pull request does not auto-merge, publish npm, close unrelated issues or pull requests, or delete unrelated branches.',
    '',
  ].join('\n');
}

export function inspectRegistrySyncWorkflow(yaml) {
  const text = String(yaml || '');
  const errors = [];
  if (/^\s{2}pull_request:/m.test(text) || /\npull_request:/m.test(text)) {
    errors.push('registry-sync must not run converter code from pull_request heads');
  }
  if (/github\.event\.pull_request\.head\.sha/.test(text)) {
    errors.push('registry-sync must not check out pull_request.head.sha');
  }
  if (/npm publish/.test(text)) errors.push('registry-sync must not publish npm');
  if (/gh pr merge/.test(text)) errors.push('registry-sync must not merge pull requests');
  if (/gh issue close/.test(text)) errors.push('registry-sync must not close issues');
  if (/uses:\s+actions\/(?:checkout|setup-node)@v\d+/.test(text)) {
    errors.push('registry-sync must pin actions by commit SHA');
  }
  const checkoutPin = (text.match(/uses:\s+actions\/checkout@([a-f0-9]{40})/) || [])[1] || null;
  const setupNodePin = (text.match(/uses:\s+actions\/setup-node@([a-f0-9]{40})/) || [])[1] || null;
  if (checkoutPin !== CHECKOUT_ACTION_PIN) errors.push('actions/checkout pin is missing or drifted');
  if (setupNodePin !== SETUP_NODE_ACTION_PIN) errors.push('actions/setup-node pin is missing or drifted');
  if (!/node \.\/src\/registry\/automation-ci\.js generate/.test(text)) {
    errors.push('generate job must run automation-ci.js generate');
  }
  if (!/EXPECTED_HEAD/.test(text)) errors.push('workflow must pass EXPECTED_HEAD');
  if (!/concurrency:/.test(text)) errors.push('workflow must serialize concurrent runs');
  if (!/permissions:\s*\n\s*\{\}/.test(text) && !/permissions:\s*\{\}/.test(text)) {
    errors.push('workflow default permissions must be empty');
  }

  const parsePerms = (block) => {
    const perms = {};
    for (const line of String(block || '').split(/\n/)) {
      const match = line.match(/^\s+([a-z-]+):\s+(\w+)\s*$/);
      if (match) perms[match[1]] = match[2];
    }
    return perms;
  };
  const generateMatch = text.match(/generate:[\s\S]*?permissions:\s*\n((?:\s{6,}[^\n]+\n)+)/);
  const generate = { permissions: parsePerms(generateMatch ? generateMatch[1] : '') };
  if (generate.permissions.contents !== 'write') errors.push('generate job must use contents: write');
  if (generate.permissions['pull-requests'] !== 'write') errors.push('generate job must use pull-requests: write');
  if (generate.permissions.issues) errors.push('generate job must not receive issues write');
  if (generate.permissions['id-token']) errors.push('generate job must not receive id-token');

  const topPerms = {};
  const top = text.match(/^permissions:\s*\n((?:\s{2}[^\n]+\n)+)/m);
  if (top) Object.assign(topPerms, parsePerms(top[1]));

  return {
    ok: errors.length === 0,
    errors,
    checkoutPin,
    setupNodePin,
    usesFloatingTags: /uses:\s+actions\/(?:checkout|setup-node)@v\d+/.test(text),
    permissions: topPerms,
    generate,
  };
}

export async function executeRegistryAutomation(args, io = {}) {
  if (args.mode === 'cleanup') {
    const branches = io.listBranches ? await io.listBranches() : [];
    const protectedRefs = io.protectedRefs ? await io.protectedRefs() : ['main'];
    const plan = planGeneratedBranchCleanup({ dryRun: args.dryRun !== false, branches, protectedRefs });
    if (args.dryRun !== false) return plan;
    if (io.deleteBranch) {
      for (const name of plan.wouldDelete) await io.deleteBranch(name);
    }
    return plan;
  }

  const expectedHead = args.expectedHead;
  const converterRevision = io.converterSha ? await io.converterSha() : expectedHead;
  const currentHeadSha = io.currentDefaultSha ? await io.currentDefaultSha() : expectedHead;
  const upstreamRevision = args.upstreamRevision
    || (io.resolveUpstreamRevision ? await io.resolveUpstreamRevision() : null);
  const upstreamText = await io.fetchUpstreamText(upstreamRevision);
  const previousPin = await io.readPin();
  const previousSnapshot = await io.readSnapshot();
  const concurrentRun = io.hasConcurrentRun ? await io.hasConcurrentRun() : false;

  const plan = planRegistrySync({
    expectedHeadSha: expectedHead,
    currentHeadSha,
    converterRevision,
    upstreamRevision,
    upstreamText,
    previousSnapshot,
    previousPin,
  });

  const authorization = evaluateAutoAuthorization({
    origin: 'same-repo',
    headRef: `${GENERATED_BRANCH_PREFIX}${(upstreamRevision || '').slice(0, 12)}`,
    headSha: args.dryRun ? expectedHead : null,
    expectedGeneratedSha: args.dryRun ? expectedHead : null,
    expectedHeadSha: expectedHead,
    currentDefaultSha: currentHeadSha,
    files: plan.files || [],
    checkConclusion: args.dryRun ? 'success' : 'pending',
    concurrentRun,
    classification: plan.classification || { autoEligible: false, blockedReasons: plan.errors || [] },
  });

  const body = formatRegistryPrBody({
    ...plan,
    upstreamRevision,
    expectedHeadSha: expectedHead,
  });

  const result = {
    ...plan,
    dryRun: args.dryRun !== false,
    body,
    autoAuthorization: authorization,
    actions: { ...BLOCKED_ACTIONS },
    merged: false,
    published: false,
  };

  if (args.dryRun !== false) return result;
  if (!plan.ok || !plan.hasChanges || concurrentRun) return result;
  if (io.writeAllowlisted) await io.writeAllowlisted(plan);
  if (io.createPullRequest) await io.createPullRequest({ ...result, body });
  return result;
}
