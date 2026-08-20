import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { getCatalog } from './catalog.js';

export const RELEASE_SCHEMA_VERSION = 1;
export const RELEASE_WORKFLOW_FILE = 'release.yml';
export const RELEASE_ENVIRONMENT = 'release';
export const RELEASE_DIST_TAG = 'latest';
export const RELEASE_PACKAGE_NAME = '@djordje-stojanovic/sigmaskills';
export const CHECKOUT_ACTION_PIN = '11bd71901bbe5b1630ceea73d27597364c9af683';
export const SETUP_NODE_ACTION_PIN = '49933ea5288caeca8642d1e84afbd3f7d6820020';

function codedError(message, code) {
  const err = new Error(message);
  err.code = code;
  return err;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function persistJson(file, payload) {
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  fs.renameSync(tmp, file);
}

export function bumpSemver(version, kind) {
  const match = String(version || '').match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!match) throw codedError(`invalid semantic version '${version}'`, 'invalid-version');
  let major = Number(match[1]);
  let minor = Number(match[2]);
  let patch = Number(match[3]);
  if (kind === 'major') {
    major += 1;
    minor = 0;
    patch = 0;
  } else if (kind === 'minor') {
    minor += 1;
    patch = 0;
  } else {
    patch += 1;
  }
  return `${major}.${minor}.${patch}`;
}

function sectionBody(changelog, headingTest) {
  const lines = String(changelog || '').split(/\r?\n/);
  const start = lines.findIndex((line) => headingTest.test(line));
  if (start < 0) return '';
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i += 1) {
    if (/^## \[/.test(lines[i])) {
      end = i;
      break;
    }
  }
  return lines.slice(start + 1, end).join('\n');
}

export function extractUnreleased(changelog) {
  return sectionBody(changelog, /^## \[Unreleased\]\s*$/);
}

export function extractVersionSection(changelog, version) {
  const escaped = String(version).replace(/\./g, '\\.');
  return sectionBody(changelog, new RegExp(`^## \\[${escaped}\\](?:\\s|$)`));
}

export function lastReleasedVersion(changelog) {
  const matches = [...String(changelog || '').matchAll(/## \[(\d+\.\d+\.\d+)\]/g)];
  return matches[0] ? matches[0][1] : null;
}

export function parseChangeSet(section) {
  const changeSet = [];
  let current = null;
  for (const line of String(section || '').split(/\r?\n/)) {
    const heading = line.match(/^###\s+(.+?)\s*$/);
    if (heading) {
      current = { heading: heading[1], items: [] };
      changeSet.push(current);
      continue;
    }
    const item = line.match(/^-\s+(.+?)\s*$/);
    if (item && current) current.items.push(item[1]);
  }
  return changeSet.filter((group) => group.items.length > 0);
}

export function classifyChangelogBump(unreleased) {
  const text = String(unreleased || '');
  if (!parseChangeSet(text).length && !/###\s+/.test(text.trim())) return null;
  if (/BREAKING CHANGE/i.test(text) || /###\s+Removed/i.test(text)) return 'major';
  if (/###\s+Added/i.test(text)) return 'minor';
  if (/###\s+Fixed/i.test(text) || /###\s+Changed/i.test(text)) return 'patch';
  return parseChangeSet(text).length ? 'patch' : null;
}

export function calculateReleasePlan({ packageVersion, manifestVersion, changelog, sourceCommit }) {
  if (packageVersion !== manifestVersion) {
    throw codedError('package.json and manifest.json versions disagree', 'identity-mismatch');
  }
  const last = lastReleasedVersion(changelog);
  const unreleased = extractUnreleased(changelog);
  const bump = classifyChangelogBump(unreleased);
  const changelogHasPackage = new RegExp(`## \\[${String(packageVersion).replace(/\./g, '\\.')}\\]`).test(changelog || '');

  let version;
  let changeSet;
  let identitiesCommitted;

  if (changelogHasPackage && !(bump && last === packageVersion)) {
    version = packageVersion;
    changeSet = parseChangeSet(extractVersionSection(changelog, version));
    identitiesCommitted = true;
  } else if (bump && last === packageVersion) {
    version = bumpSemver(packageVersion, bump);
    changeSet = parseChangeSet(unreleased);
    identitiesCommitted = false;
  } else if (!bump) {
    throw codedError('CHANGELOG.md has no Unreleased change set to publish', 'nothing-to-release');
  } else {
    throw codedError(
      `Release identities are inconsistent: package ${packageVersion}, last changelog ${last || 'none'}`,
      'identity-mismatch',
    );
  }

  return {
    sourceCommit,
    version,
    bump: bump || null,
    changeSet,
    identitiesCommitted,
    tag: `v${version}`,
    githubRelease: `v${version}`,
    npmPackage: `${RELEASE_PACKAGE_NAME}@${version}`,
    distTag: RELEASE_DIST_TAG,
    tests: { command: 'npm test', required: true },
  };
}

export function applyReleaseIdentities({ packageJson, manifest, changelog, version, date }) {
  const unreleased = extractUnreleased(changelog).replace(/^\s+|\s+$/g, '');
  const nextChangelog = String(changelog).replace(
    /## \[Unreleased\]\s*\n[\s\S]*?(?=\n## \[)/,
    `## [Unreleased]\n\n## [${version}] — ${date}\n\n${unreleased}\n\n`,
  );
  return {
    packageJson: { ...packageJson, version },
    manifest: { ...manifest, version },
    changelog: nextChangelog,
  };
}

export function applyRegistryPatchIdentities({ packageJson, manifest, changelog, version, date, note }) {
  if (new RegExp(`^## \\[${String(version).replace(/\./g, '\\.')}\\]`, 'm').test(String(changelog || ''))) {
    return {
      packageJson: { ...packageJson, version },
      manifest: { ...manifest, version },
      changelog,
    };
  }
  const insertion = `## [Unreleased]\n\n## [${version}] — ${date}\n\n### Changed\n\n- ${note}\n`;
  const nextChangelog = String(changelog).replace(/## \[Unreleased\]\s*\n/, `${insertion}\n`);
  return {
    packageJson: { ...packageJson, version },
    manifest: { ...manifest, version },
    changelog: nextChangelog,
  };
}

/**
 * Patch-only trusted publication. Reuses evaluatePublicationGate and
 * planIdempotentPublish; never overwrites an existing npm version.
 */
export async function executeTrustedPatchRelease(options = {}) {
  const tarball = options.tarball || (options.rootDir ? defaultPack(options.rootDir) : null);
  const expected = {
    version: options.version,
    commit: options.commit,
    digest: tarball?.digest,
    integrity: tarball?.integrity,
    tag: `v${options.version}`,
  };
  const gate = evaluatePublicationGate({
    expected,
    workflow: options.workflow || { ok: true },
    npmPackage: options.npmPackage,
    githubRelease: options.githubRelease,
    gitTag: options.gitTag,
    environment: options.environment,
    trustedPublisher: options.trustedPublisher,
  });
  const recovery = planIdempotentPublish({
    expected,
    npmPackage: options.npmPackage,
    githubRelease: options.githubRelease,
    gitTag: options.gitTag,
  });
  const preview = {
    ok: gate.ok && recovery.ok,
    errors: [...(gate.ok ? [] : gate.errors || []), ...(recovery.ok ? [] : recovery.errors || [])],
    version: options.version,
    commit: options.commit,
    tag: expected.tag,
    bump: 'patch',
    tarball,
    gate,
    recovery,
  };
  if (!preview.ok || options.dryRun) return preview;

  const publishers = options.publishers || {};
  if (recovery.createTag && publishers.createTag) publishers.createTag(preview);
  if (recovery.createGithubRelease && publishers.createGithubRelease) publishers.createGithubRelease(preview);
  if (recovery.publishNpm && publishers.publishNpm) publishers.publishNpm(preview);
  return preview;
}

export function inspectReleaseWorkflow(yaml) {
  const text = String(yaml || '');
  const errors = [];
  const onBlock = text.match(/\non:\s*\n([\s\S]*?)(?=\n(?:permissions|concurrency|env|jobs):|\njobs:)/);
  const onText = onBlock ? onBlock[1] : '';
  const triggers = [];
  if (/^\s{2}workflow_dispatch:/m.test(onText) || /^\s+workflow_dispatch:/m.test(text)) triggers.push('workflow_dispatch');
  if (/^\s{2}push:/m.test(onText)) {
    errors.push('release workflow must not publish on push');
    triggers.push('push');
  }
  if (/^\s{2}pull_request:/m.test(onText)) {
    errors.push('release workflow must not publish on pull_request');
    triggers.push('pull_request');
  }
  if (!triggers.includes('workflow_dispatch')) errors.push('release workflow must use workflow_dispatch');

  const usesFloatingTags = /uses:\s+actions\/(?:checkout|setup-node)@v\d+/m.test(text);
  if (usesFloatingTags) errors.push('release workflow must pin actions by commit SHA');

  const checkoutPin = (text.match(/uses:\s+actions\/checkout@([a-f0-9]{40})/) || [])[1] || null;
  const setupNodePin = (text.match(/uses:\s+actions\/setup-node@([a-f0-9]{40})/) || [])[1] || null;
  if (checkoutPin !== CHECKOUT_ACTION_PIN) errors.push('actions/checkout pin is missing or drifted');
  if (setupNodePin !== SETUP_NODE_ACTION_PIN) errors.push('actions/setup-node pin is missing or drifted');

  const validateMatch = text.match(/validate:[\s\S]*?permissions:\s*\n((?:\s{6,}[^\n]+\n)+)/);
  const publishMatch = text.match(/publish:[\s\S]*?permissions:\s*\n((?:\s{6,}[^\n]+\n)+)/);
  const parsePerms = (block) => {
    const perms = {};
    for (const line of String(block || '').split(/\n/)) {
      const match = line.match(/^\s+([a-z-]+):\s+(\w+)\s*$/);
      if (match) perms[match[1]] = match[2];
    }
    return perms;
  };
  const validate = { permissions: parsePerms(validateMatch ? validateMatch[1] : '') };
  const publish = {
    permissions: parsePerms(publishMatch ? publishMatch[1] : ''),
    environment: /publish:[\s\S]*?environment:\s+(\S+)/.test(text)
      ? text.match(/publish:[\s\S]*?environment:\s+(\S+)/)[1]
      : null,
  };

  if (validate.permissions.contents !== 'read') errors.push('validate job must use contents: read');
  if (validate.permissions['id-token']) errors.push('validate job must not receive id-token');
  if (publish.permissions['id-token'] !== 'write') errors.push('publish job must use id-token: write');
  if (publish.permissions.contents !== 'write') errors.push('publish job must use contents: write');
  if (publish.environment !== RELEASE_ENVIRONMENT) errors.push(`publish job must use environment ${RELEASE_ENVIRONMENT}`);
  if (!/node \.\/src\/release-ci\.js validate/.test(text)) errors.push('validate job must rebuild through release-ci.js');
  if (!/node \.\/src\/release-ci\.js publish/.test(text)) errors.push('publish job must publish through release-ci.js');

  return {
    ok: errors.length === 0,
    errors,
    triggers: [...new Set(triggers)],
    validate,
    publish,
    checkoutPin,
    setupNodePin,
    usesFloatingTags,
    trustedPublisherShape: publish.permissions['id-token'] === 'write' && publish.environment === RELEASE_ENVIRONMENT,
  };
}

export function evaluatePublicationGate({
  expected,
  workflow,
  npmPackage,
  githubRelease,
  gitTag,
  environment,
  trustedPublisher,
}) {
  const errors = [];
  if (workflow && workflow.ok === false) errors.push(...(workflow.errors || ['release workflow failed inspection']));
  if (!npmPackage?.exists) {
    errors.push(
      'Reserve the npm name `sigmaskills` at https://www.npmjs.com/package/sigmaskills, then configure a trusted publisher for workflow `release.yml` and GitHub Environment `release`.',
    );
  }
  if (trustedPublisher === false) {
    errors.push(
      'Configure an npm trusted publisher for this GitHub repository, workflow filename `release.yml`, and environment `release`. Publication cannot start until that one-time setup exists.',
    );
  }
  if (!environment || environment.name !== RELEASE_ENVIRONMENT) {
    errors.push('Create a GitHub Environment named `release` with required reviewers, then retry publication.');
  } else if (!environment.protected) {
    errors.push('Add protection rules (required reviewers) to the GitHub Environment named `release`.');
  }
  const tagName = `v${expected.version}`;
  if (gitTag && gitTag.commit && gitTag.commit !== expected.commit) {
    errors.push(`git tag ${tagName} already points at ${gitTag.commit}; refusing to overwrite.`);
  }
  if (githubRelease && githubRelease.targetCommit && githubRelease.targetCommit !== expected.commit && !releasePointsAtCommit(githubRelease, gitTag, expected)) {
    errors.push(`GitHub Release ${tagName} already targets ${githubRelease.targetCommit}; refusing to duplicate or overwrite.`);
  }
  const published = npmPackage?.versions?.[expected.version];
  if (published && published.integrity && expected.integrity && published.integrity !== expected.integrity) {
    errors.push(`npm already has ${RELEASE_PACKAGE_NAME}@${expected.version} with a different digest; versions are immutable.`);
  }
  return { ok: errors.length === 0, errors };
}

function releasePointsAtCommit(githubRelease, gitTag, expected) {
  if (!githubRelease) return false;
  const tagged = gitTag && gitTag.commit === expected.commit;
  return githubRelease.targetCommit === expected.commit || tagged;
}

export function planIdempotentPublish({ expected, npmPackage, githubRelease, gitTag }) {
  const errors = [];
  const published = npmPackage?.versions?.[expected.version];
  if (published && published.integrity && expected.integrity && published.integrity !== expected.integrity) {
    errors.push(`npm already has ${RELEASE_PACKAGE_NAME}@${expected.version} with a different digest; versions are immutable.`);
  }
  const tagName = `v${expected.version}`;
  if (gitTag && gitTag.commit && gitTag.commit !== expected.commit) {
    errors.push(`git tag ${tagName} already points at ${gitTag.commit}; refusing to overwrite.`);
  }
  if (githubRelease && githubRelease.targetCommit && githubRelease.targetCommit !== expected.commit && !releasePointsAtCommit(githubRelease, gitTag, expected)) {
    errors.push(`GitHub Release ${tagName} already targets ${githubRelease.targetCommit}; refusing to duplicate or overwrite.`);
  }
  if (errors.length) return { ok: false, errors, publishNpm: false, createGithubRelease: false, createTag: false };
  const sameNpm = Boolean(published && (!expected.integrity || published.integrity === expected.integrity));
  const sameRelease = releasePointsAtCommit(githubRelease, gitTag, expected);
  const sameTag = Boolean(gitTag && gitTag.commit === expected.commit);
  return {
    ok: true,
    errors,
    publishNpm: !sameNpm,
    createGithubRelease: !sameRelease,
    createTag: !sameTag,
  };
}

function defaultGit(rootDir) {
  const run = (args) => execFileSync('git', args, { cwd: rootDir, encoding: 'utf8' }).trim();
  return {
    revParse: (ref = 'HEAD') => run(['rev-parse', ref]),
    show: (spec) => run(['show', spec]),
    statusPorcelain: () => run(['status', '--porcelain']),
    tagCommit: (tag) => {
      try {
        return run(['rev-list', '-n', '1', tag]);
      } catch {
        return null;
      }
    },
  };
}

function npmCommand() {
  return process.platform === 'win32' ? 'npm.cmd' : 'npm';
}

function defaultPack(rootDir) {
  const dest = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-release-pack-'));
  const output = execFileSync(npmCommand(), ['pack', '--json', `--pack-destination=${dest}`], {
    cwd: rootDir,
    encoding: 'utf8',
  });
  const parsed = JSON.parse(output);
  const info = Array.isArray(parsed) ? parsed[0] : parsed;
  const tarballPath = path.join(dest, info.filename);
  const bytes = fs.readFileSync(tarballPath);
  const digest = crypto.createHash('sha256').update(bytes).digest('hex');
  const contents = execFileSync('tar', ['-tf', tarballPath], { encoding: 'utf8' })
    .split(/\r?\n/)
    .map((line) => line.trim().replace(/\\/g, '/'))
    .filter(Boolean);
  return {
    filename: info.filename,
    digest,
    integrity: info.integrity,
    contents,
    path: tarballPath,
  };
}

function loadIdentities(rootDir, git, commit) {
  if (git?.show && commit) {
    try {
      return {
        packageJson: JSON.parse(git.show(`${commit}:package.json`)),
        manifest: JSON.parse(git.show(`${commit}:manifest.json`)),
        changelog: git.show(`${commit}:CHANGELOG.md`),
      };
    } catch {
      // Use the working tree when this commit does not contain identity files.
    }
  }
  return {
    packageJson: readJson(path.join(rootDir, 'package.json')),
    manifest: readJson(path.join(rootDir, 'manifest.json')),
    changelog: fs.readFileSync(path.join(rootDir, 'CHANGELOG.md'), 'utf8'),
  };
}

function utcDate(now) {
  const date = now ? new Date(now) : new Date();
  return date.toISOString().slice(0, 10);
}

export function writeReleaseIdentities(rootDir, { now } = {}) {
  const identities = loadIdentities(rootDir);
  const plan = calculateReleasePlan({
    packageVersion: identities.packageJson.version,
    manifestVersion: identities.manifest.version,
    changelog: identities.changelog,
    sourceCommit: null,
  });
  if (plan.identitiesCommitted) return plan;
  const applied = applyReleaseIdentities({
    ...identities,
    version: plan.version,
    date: utcDate(now),
  });
  persistJson(path.join(rootDir, 'package.json'), applied.packageJson);
  persistJson(path.join(rootDir, 'manifest.json'), applied.manifest);
  fs.writeFileSync(path.join(rootDir, 'CHANGELOG.md'), applied.changelog, 'utf8');
  return { ...plan, identitiesCommitted: true, wroteIdentities: true };
}

function defaultProbes({ git, expected, rootDir }) {
  let npmPackage = { exists: false, versions: {} };
  try {
    const name = execFileSync(npmCommand(), ['view', RELEASE_PACKAGE_NAME, 'name'], {
      encoding: 'utf8',
    }).trim();
    npmPackage.exists = name === RELEASE_PACKAGE_NAME;
    if (npmPackage.exists) {
      try {
        const integrity = execFileSync(
          npmCommand(),
          ['view', `${RELEASE_PACKAGE_NAME}@${expected.version}`, 'dist.integrity'],
          { encoding: 'utf8' },
        ).trim();
        if (integrity) npmPackage.versions[expected.version] = { integrity };
      } catch {
        // Version is unpublished; reservation still counts.
      }
    }
  } catch {
    npmPackage = { exists: false, versions: {} };
  }

  let githubRelease = null;
  try {
    const raw = execFileSync(
      'gh',
      ['release', 'view', expected.tag, '--json', 'tagName,targetCommitish'],
      { cwd: rootDir, encoding: 'utf8' },
    );
    const parsed = JSON.parse(raw);
    let targetCommit = parsed.targetCommitish;
    try {
      targetCommit = git.revParse ? git.revParse(`${parsed.targetCommitish}^{commit}`) : targetCommit;
    } catch {
      try {
        targetCommit = git.tagCommit?.(parsed.tagName) || targetCommit;
      } catch {
        targetCommit = parsed.targetCommitish;
      }
    }
    githubRelease = { tag: parsed.tagName, targetCommit };
  } catch {
    githubRelease = null;
  }

  let environment = null;
  try {
    const repo = process.env.GITHUB_REPOSITORY || 'Djordje-Stojanovic/Sigmaskills';
    const raw = execFileSync(
      'gh',
      ['api', `repos/${repo}/environments/${RELEASE_ENVIRONMENT}`],
      { encoding: 'utf8' },
    );
    const parsed = JSON.parse(raw);
    environment = {
      name: parsed.name,
      protected: Array.isArray(parsed.protection_rules) && parsed.protection_rules.length > 0,
    };
  } catch {
    environment = null;
  }

  return {
    npmPackage,
    githubRelease,
    environment,
    gitTag: git.tagCommit ? (git.tagCommit(expected.tag) ? { name: expected.tag, commit: git.tagCommit(expected.tag) } : null) : null,
  };
}

function defaultDispatch({ expectedCommit, expectedVersion, expectedDigest, rootDir }) {
  execFileSync(
    'gh',
    [
      'workflow',
      'run',
      RELEASE_WORKFLOW_FILE,
      '-f',
      `expected_commit=${expectedCommit}`,
      '-f',
      `expected_version=${expectedVersion}`,
      '-f',
      `expected_digest=${expectedDigest}`,
    ],
    { cwd: rootDir, encoding: 'utf8' },
  );
  return { ok: true };
}

function loadWorkflow(rootDir) {
  const file = path.join(rootDir, '.github', 'workflows', RELEASE_WORKFLOW_FILE);
  if (!fs.existsSync(file)) {
    return inspectReleaseWorkflow('');
  }
  return inspectReleaseWorkflow(fs.readFileSync(file, 'utf8'));
}

/**
 * Prepare or dispatch an owner-triggered Release.
 *
 * @param {object} options
 * @returns {object}
 */
export function executeRelease(options = {}) {
  const rootDir = options.rootDir;
  if (!rootDir) throw codedError('release requires a package root', 'missing-root');
  const hasExpected = Boolean(options.expectedCommit && options.expectedVersion && options.expectedDigest);
  const dryRun = Boolean(options.dryRun) || (Boolean(options.writeIdentities) && !hasExpected);
  const git = options.git || defaultGit(rootDir);
  const sourceCommit = git.revParse();
  const before = loadIdentities(rootDir);

  if (options.writeIdentities) {
    writeReleaseIdentities(rootDir, { now: options.now });
  }

  const current = options.writeIdentities
    ? loadIdentities(rootDir)
    : loadIdentities(rootDir, git, sourceCommit);
  const plan = calculateReleasePlan({
    packageVersion: current.packageJson.version,
    manifestVersion: current.manifest.version,
    changelog: current.changelog,
    sourceCommit,
  });

  const catalog = options.catalog || getCatalog(rootDir);
  const pack = options.pack || (() => defaultPack(rootDir));
  const tarball = pack();

  const preview = {
    schemaVersion: RELEASE_SCHEMA_VERSION,
    command: 'release',
    dryRun,
    commit: sourceCommit,
    version: plan.version,
    bump: plan.bump,
    changeSet: plan.changeSet,
    identitiesCommitted: plan.identitiesCommitted,
    tests: plan.tests,
    tarball,
    skills: (catalog.skills || []).map((skill) => ({
      id: skill.id,
      title: skill.title,
      revision: skill.revision,
    })),
    tag: plan.tag,
    githubRelease: plan.githubRelease,
    npmPackage: plan.npmPackage,
    distTag: plan.distTag,
    dispatched: false,
  };

  if (before.packageJson.version !== current.packageJson.version) {
    preview.wroteIdentities = true;
  }

  const expected = {
    version: plan.version,
    commit: sourceCommit,
    digest: tarball.digest,
    integrity: tarball.integrity,
    tag: plan.tag,
  };
  const workflow = options.workflow || loadWorkflow(rootDir);
  const probes = options.probes || defaultProbes({ git, expected, rootDir });
  const gitTag = probes.gitTag !== undefined
    ? probes.gitTag
    : (git.tagCommit?.(plan.tag) ? { name: plan.tag, commit: git.tagCommit(plan.tag) } : null);
  const gate = evaluatePublicationGate({
    expected,
    workflow,
    npmPackage: probes.npmPackage,
    githubRelease: probes.githubRelease,
    gitTag,
    environment: probes.environment,
    trustedPublisher: probes.trustedPublisher,
  });
  const recovery = planIdempotentPublish({
    expected,
    npmPackage: probes.npmPackage,
    githubRelease: probes.githubRelease,
    gitTag,
  });
  preview.gate = gate;
  preview.recovery = recovery;

  if (dryRun) return preview;

  if (!hasExpected) {
    throw codedError(
      'release requires immutable expected commit, version, and digest; --yes, CI, and informal text are not authority',
      'confirmation-required',
    );
  }
  if (git.statusPorcelain && git.statusPorcelain().trim()) {
    throw codedError('release dispatch requires a clean working tree at the approved commit', 'dirty-tree');
  }
  if (!plan.identitiesCommitted) {
    throw codedError(
      `commit Release identities for ${plan.version} (package.json, manifest.json, CHANGELOG.md) before dispatch`,
      'identities-pending',
    );
  }
  if (options.expectedCommit !== sourceCommit || options.expectedVersion !== plan.version || options.expectedDigest !== tarball.digest) {
    throw codedError(
      `approved commit/version/digest does not match prepared ${sourceCommit} ${plan.version} sha256:${tarball.digest}`,
      'expectation-mismatch',
    );
  }
  if (!gate.ok) {
    throw codedError(gate.errors[0], 'setup-incomplete');
  }
  if (!recovery.ok) {
    throw codedError(recovery.errors[0], 'conflict');
  }

  const dispatch = options.dispatch || ((payload) => defaultDispatch({ ...payload, rootDir }));
  dispatch({
    workflow: RELEASE_WORKFLOW_FILE,
    expectedCommit: options.expectedCommit,
    expectedVersion: options.expectedVersion,
    expectedDigest: options.expectedDigest,
  });
  preview.dispatched = true;
  preview.dryRun = false;
  return preview;
}

export function formatReleaseHuman(result) {
  const lines = [
    `SigmaSkills Release ${result.dryRun ? 'preview' : result.dispatched ? 'dispatch' : 'plan'}`,
    `  Commit:              ${result.commit}`,
    `  Version:             ${result.version}`,
    `  Tests:               ${result.tests?.command || 'npm test'} (trusted workflow re-runs before publish)`,
    `  Tarball digest:      ${result.tarball?.digest ? `sha256:${result.tarball.digest}` : 'pending identity write'}`,
    `  Tarball integrity:   ${result.tarball?.integrity || 'pending'}`,
    `  Tag:                 ${result.tag}`,
    `  GitHub Release:      ${result.githubRelease}`,
    `  npm package:         ${result.npmPackage}`,
    `  dist-tag:            ${result.distTag}`,
  ];
  if (result.tarball?.contents?.length) {
    lines.push('  Tarball contents:');
    for (const file of result.tarball.contents.slice(0, 40)) lines.push(`    - ${file}`);
    if (result.tarball.contents.length > 40) lines.push(`    - … ${result.tarball.contents.length - 40} more`);
  }
  lines.push('  Skill Revisions:');
  for (const skill of result.skills || []) {
    lines.push(`    - ${skill.id}: ${skill.revision}`);
  }
  if (result.changeSet?.length) {
    lines.push('  Change set:');
    for (const group of result.changeSet) {
      lines.push(`    ${group.heading}`);
      for (const item of group.items) lines.push(`      - ${item}`);
    }
  }
  if (result.gate?.errors?.length) {
    lines.push('  Setup blockers:');
    for (const error of result.gate.errors) lines.push(`    - ${error}`);
  }
  if (!result.identitiesCommitted) {
    lines.push('  Next: run `sigmaskills release --write-identities`, commit the identity files, then re-run --dry-run.');
  } else if (result.dryRun) {
    lines.push('  Next: dispatch with --expected-commit, --expected-version, and --expected-digest matching this preview.');
  }
  return lines.join('\n');
}

export function formatReleaseJson(result) {
  return `${JSON.stringify({
    schemaVersion: RELEASE_SCHEMA_VERSION,
    command: 'release',
    dryRun: Boolean(result.dryRun),
    dispatched: Boolean(result.dispatched),
    commit: result.commit,
    version: result.version,
    bump: result.bump || null,
    changeSet: result.changeSet || [],
    identitiesCommitted: Boolean(result.identitiesCommitted),
    tests: result.tests,
    tarball: result.tarball,
    skills: result.skills || [],
    tag: result.tag,
    githubRelease: result.githubRelease,
    npmPackage: result.npmPackage,
    distTag: result.distTag,
    gate: result.gate || null,
    recovery: result.recovery || null,
  }, null, 2)}\n`;
}

export function verifyApprovedCommit({ git, expectedCommit, expectedVersion, rootDir }) {
  const head = git.revParse();
  if (head !== expectedCommit) {
    throw codedError(`checked-out commit ${head} is not the approved commit ${expectedCommit}`, 'commit-mismatch');
  }
  const identities = loadIdentities(rootDir);
  if (identities.packageJson.version !== expectedVersion || identities.manifest.version !== expectedVersion) {
    throw codedError('package.json, manifest.json, and approved version disagree', 'identity-mismatch');
  }
  if (!new RegExp(`## \\[${String(expectedVersion).replace(/\./g, '\\.')}\\]`).test(identities.changelog)) {
    throw codedError(`CHANGELOG.md has no ${expectedVersion} heading`, 'identity-mismatch');
  }
}

export async function runTrustedValidate(env, options = {}) {
  const rootDir = options.rootDir || process.cwd();
  const expectedCommit = env.EXPECTED_COMMIT;
  const expectedVersion = env.EXPECTED_VERSION;
  const expectedDigest = env.EXPECTED_DIGEST;
  const git = options.git || defaultGit(rootDir);
  verifyApprovedCommit({ git, expectedCommit, expectedVersion, rootDir });
  if (options.runTests) await options.runTests();
  else execFileSync(npmCommand(), ['test'], { cwd: rootDir, stdio: 'inherit' });
  const tarball = options.pack ? options.pack() : defaultPack(rootDir);
  if (tarball.digest !== expectedDigest) {
    throw codedError(`rebuilt tarball sha256:${tarball.digest} does not match approved digest sha256:${expectedDigest}`, 'digest-mismatch');
  }
  const catalog = options.catalog || getCatalog(rootDir);
  const result = executeRelease({
    rootDir,
    catalog,
    dryRun: true,
    git,
    pack: () => tarball,
    probes: options.probes,
    workflow: options.workflow || loadWorkflow(rootDir),
  });
  if (result.version !== expectedVersion) {
    throw codedError(`prepared version ${result.version} is not the approved version ${expectedVersion}`, 'version-mismatch');
  }
  if (!result.gate?.ok) throw codedError(result.gate.errors[0], 'setup-incomplete');
  return result;
}

export async function runTrustedPublish(env, options = {}) {
  const preview = await runTrustedValidate(env, options);
  const recovery = preview.recovery;
  if (!recovery.ok) throw codedError(recovery.errors[0], 'conflict');
  const publishers = options.publishers || {};
  if (recovery.createTag && publishers.createTag) publishers.createTag(preview);
  if (recovery.createGithubRelease && publishers.createGithubRelease) publishers.createGithubRelease(preview);
  if (recovery.publishNpm && publishers.publishNpm) publishers.publishNpm(preview);
  if (!options.publishers) {
    const rootDir = options.rootDir || process.cwd();
    if (recovery.createTag) {
      try {
        execFileSync('git', ['tag', preview.tag, preview.commit], { cwd: rootDir, encoding: 'utf8' });
      } catch {
        // Tag may already exist at this commit.
      }
      execFileSync('git', ['push', 'origin', preview.tag], { cwd: rootDir, encoding: 'utf8' });
    }
    if (recovery.createGithubRelease) {
      execFileSync(
        'gh',
        ['release', 'create', preview.tag, '--target', preview.commit, '--title', preview.tag, '--notes', formatReleaseHuman(preview)],
        { cwd: rootDir, encoding: 'utf8' },
      );
    }
    if (recovery.publishNpm) {
      const artifact = preview.tarball?.path;
      const publishArgs = artifact
        ? ['publish', artifact, '--access', 'public', '--tag', RELEASE_DIST_TAG, '--provenance']
        : ['publish', '--access', 'public', '--tag', RELEASE_DIST_TAG, '--provenance'];
      try {
        execFileSync(npmCommand(), publishArgs, {
          cwd: rootDir,
          encoding: 'utf8',
          stdio: 'pipe',
        });
      } catch (err) {
        const detail = `${err.message || ''}\n${err.stderr || ''}\n${err.stdout || ''}`;
        if (/ENEEDAUTH|unable to authenticate|not authorized/i.test(detail)) {
          throw codedError(
            'Configure an npm trusted publisher for this GitHub repository, workflow filename `release.yml`, and environment `release`. Publication cannot start until that one-time setup exists.',
            'trusted-publisher',
          );
        }
        throw err;
      }
    }
  }
  return { ...preview, dryRun: false, published: recovery };
}
