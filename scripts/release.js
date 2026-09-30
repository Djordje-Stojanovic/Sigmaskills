import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { appendReleaseBaselines, hashSkillsAtRef } from './baselines.js';
import { getCatalog } from '../src/catalog.js';
import {
  applyReleaseIdentities,
  calculateReleasePlan,
  classifyChangelogBump,
  extractUnreleased,
  parseChangeSet,
} from './release-changelog.js';
import { defaultPack } from './release-pack.js';
import { defaultDispatch, defaultGit, defaultProbes, gitTagProbe } from './release-probes.js';
import {
  RELEASE_DIST_TAG,
  RELEASE_PACKAGE_NAME,
  RELEASE_SCHEMA_VERSION,
  RELEASE_WORKFLOW_FILE,
  TRUSTED_PUBLISHER_SETUP,
  evaluatePublication,
  inspectReleaseWorkflow,
} from './release-publication.js';
import { codedError, createGitTag, execNpm, persistJson, readJson, versionPattern } from './release-util.js';

// Public surface: other scripts and tests import these from release.js.
export * from './release-changelog.js';
export * from './release-pack.js';
export * from './release-publication.js';

/**
 * Patch-only trusted publication. Reuses evaluatePublication; never overwrites
 * an existing npm version.
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
  const { gate, recovery } = evaluatePublication({
    expected,
    workflow: options.workflow || { ok: true },
    npmPackage: options.npmPackage,
    githubRelease: options.githubRelease,
    gitTag: options.gitTag,
    environment: options.environment,
    trustedPublisher: options.trustedPublisher,
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

  runPublishers(options.publishers || {}, recovery, preview);
  return preview;
}

function runPublishers(publishers, recovery, preview) {
  if (recovery.createTag && publishers.createTag) publishers.createTag(preview);
  if (recovery.createGithubRelease && publishers.createGithubRelease) publishers.createGithubRelease(preview);
  if (recovery.publishNpm && publishers.publishNpm) publishers.publishNpm(preview);
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
  // A prepared candidate is not a published Release. Find the preceding tagged
  // changelog entry, and fold later fixes into the candidate instead of inventing a baseline.
  const tags = new Set(execFileSync('git', ['tag', '--list'], { cwd: rootDir, encoding: 'utf8' }).trim().split(/\r?\n/));
  const versions = [...identities.changelog.matchAll(/^## \[(\d+\.\d+\.\d+)\]/gm)].map((match) => match[1]);
  const outgoing = versions.find((version) => tags.has(`v${version}`));
  if (!outgoing) throw codedError('cannot find a tagged outgoing Release; fetch release tags first', 'missing-tag');
  const outgoingSkills = hashSkillsAtRef(rootDir, `refs/tags/v${outgoing}`);
  if (outgoing !== identities.packageJson.version) {
    const candidate = identities.packageJson.version;
    // Remove the candidate heading and link, and compare [Unreleased] from the outgoing tag again.
    identities.changelog = identities.changelog
      .replace(new RegExp(`^## \\[${versionPattern(candidate)}\\][^\\n]*\\n`, 'm'), '')
      .replace(new RegExp(`^\\[${versionPattern(candidate)}\\]: [^\\n]*\\n`, 'm'), '')
      .replace(
        new RegExp(`^(\\[Unreleased\\]: \\S+/compare/)v${versionPattern(candidate)}(\\.\\.\\.HEAD)`, 'm'),
        (_, before, after) => `${before}v${outgoing}${after}`,
      );
    plan.version = candidate;
    plan.tag = `v${candidate}`;
    plan.githubRelease = plan.tag;
    plan.npmPackage = `${RELEASE_PACKAGE_NAME}@${candidate}`;
    plan.changeSet = parseChangeSet(extractUnreleased(identities.changelog));
    plan.bump = classifyChangelogBump(extractUnreleased(identities.changelog));
  }
  appendReleaseBaselines(rootDir, outgoing, outgoingSkills);
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
  const gitTag = probes.gitTag !== undefined ? probes.gitTag : gitTagProbe(git, plan.tag);
  const { gate, recovery } = evaluatePublication({
    expected,
    workflow,
    npmPackage: probes.npmPackage,
    githubRelease: probes.githubRelease,
    gitTag,
    environment: probes.environment,
    trustedPublisher: probes.trustedPublisher,
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
    lines.push('  Next: run `npm run release -- --write-identities`, commit the identity files and `registry/skill-baselines.json`, then re-run --dry-run.');
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
  if (!new RegExp(`## \\[${versionPattern(expectedVersion)}\\]`).test(identities.changelog)) {
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
  else execNpm(['test'], { cwd: rootDir, stdio: 'inherit' });
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

// Tag, GitHub Release, then npm, each only when the recovery plan asks for it.
function publishWithTools(preview, recovery, rootDir) {
  if (recovery.createTag) {
    createGitTag(preview.tag, preview.commit, { cwd: rootDir });
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
    const publishArgs = ['publish', ...(artifact ? [artifact] : []), '--access', 'public', '--tag', RELEASE_DIST_TAG, '--provenance'];
    try {
      execNpm(publishArgs, { cwd: rootDir, encoding: 'utf8', stdio: 'pipe' });
    } catch (err) {
      const detail = `${err.message || ''}\n${err.stderr || ''}\n${err.stdout || ''}`;
      if (/ENEEDAUTH|unable to authenticate|not authorized/i.test(detail)) {
        throw codedError(TRUSTED_PUBLISHER_SETUP, 'trusted-publisher');
      }
      throw err;
    }
  }
}

export async function runTrustedPublish(env, options = {}) {
  const preview = await runTrustedValidate(env, options);
  const recovery = preview.recovery;
  if (!recovery.ok) throw codedError(recovery.errors[0], 'conflict');
  runPublishers(options.publishers || {}, recovery, preview);
  if (!options.publishers) publishWithTools(preview, recovery, options.rootDir || process.cwd());
  return { ...preview, dryRun: false, published: recovery };
}

const RELEASE_VALUE_FLAGS = {
  '--expected-commit': 'expectedCommit',
  '--expected-version': 'expectedVersion',
  '--expected-digest': 'expectedDigest',
};

/**
 * Parse the maintainer release command: `npm run release -- [flags]`.
 *
 * @param {string[]} args
 * @returns {object}
 */
export function parseReleaseArgs(args) {
  const parsed = { dryRun: false, json: false, yes: false, writeIdentities: false, unknown: [] };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const [flag, inline] = arg.split(/=(.*)/s);
    if (arg === '--dry-run') parsed.dryRun = true;
    else if (arg === '--json') parsed.json = true;
    else if (arg === '-y' || arg === '--yes') parsed.yes = true;
    else if (arg === '--write-identities') parsed.writeIdentities = true;
    else if (RELEASE_VALUE_FLAGS[flag]) parsed[RELEASE_VALUE_FLAGS[flag]] = inline ?? args[++i];
    else parsed.unknown.push(arg);
  }
  return parsed;
}

/**
 * Run the maintainer release command from a repository checkout.
 *
 * @param {string[]} args
 * @param {object} [io] stdout/stderr handles; `io.release` injects test adapters
 * @returns {Promise<number>} exit code
 */
export async function runReleaseCli(args = process.argv.slice(2), io = { stdout: process.stdout, stderr: process.stderr }) {
  try {
    const opts = parseReleaseArgs(args);
    if (opts.unknown.length > 0) throw new Error(`unknown option: ${opts.unknown[0]}`);
    const adapters = io.release || {};
    const result = executeRelease({
      rootDir: adapters.rootDir || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'),
      catalog: adapters.catalog,
      dryRun: opts.dryRun,
      yes: opts.yes,
      writeIdentities: opts.writeIdentities,
      expectedCommit: opts.expectedCommit,
      expectedVersion: opts.expectedVersion,
      expectedDigest: opts.expectedDigest,
      git: adapters.git,
      pack: adapters.pack,
      probes: adapters.probes,
      dispatch: adapters.dispatch,
      workflow: adapters.workflow,
      now: adapters.now,
    });
    const out = opts.json ? formatReleaseJson(result) : formatReleaseHuman(result);
    io.stdout.write(out.endsWith('\n') ? out : `${out}\n`);
    return 0;
  } catch (err) {
    io.stderr.write(`release error: ${err.message}\n`);
    return 1;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await runReleaseCli();
}
