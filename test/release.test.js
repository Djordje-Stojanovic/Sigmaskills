import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { findPackageRoot } from '../src/catalog.js';
import { runCli, parseCliArgs } from '../src/cli.js';
import {
  RELEASE_DIST_TAG,
  RELEASE_ENVIRONMENT,
  RELEASE_SCHEMA_VERSION,
  RELEASE_WORKFLOW_FILE,
  applyReleaseIdentities,
  calculateReleasePlan,
  evaluatePublicationGate,
  executeRelease,
  formatReleaseHuman,
  formatReleaseJson,
  inspectReleaseWorkflow,
  planIdempotentPublish,
} from '../src/release.js';

const ROOT = findPackageRoot();

function changelogWith(unreleased, released = '0.1.0') {
  return `# Changelog

## [Unreleased]

${unreleased}

## [${released}] — 2026-08-11

First public release.
`;
}

function tmpTree(files) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-release-'));
  for (const [rel, contents] of Object.entries(files)) {
    const abs = path.join(dir, rel);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, contents, 'utf8');
  }
  return dir;
}

function mockIo(release) {
  let stdout = '';
  let stderr = '';
  return {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    env: { CI: '1' },
    release,
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

const catalog = {
  manifest: { name: 'sigmaskills', version: '0.1.0', schemaVersion: 1 },
  skills: [{ id: 'sigmawrite', title: 'SigmaWrite', revision: 'aa'.repeat(32) }],
};

const inspectedWorkflow = inspectReleaseWorkflow(
  fs.readFileSync(path.join(ROOT, '.github', 'workflows', RELEASE_WORKFLOW_FILE), 'utf8'),
);

const readyIdentities = {
  'package.json': JSON.stringify({ name: 'sigmaskills', version: '0.2.0' }, null, 2),
  'manifest.json': JSON.stringify({ schemaVersion: 1, name: 'sigmaskills', version: '0.2.0', skills: [] }, null, 2),
  'CHANGELOG.md': `# Changelog

## [Unreleased]

## [0.2.0] — 2026-08-19

### Added

- Owner-triggered publication.

## [0.1.0] — 2026-08-11

First public release.
`,
};

test('release plan: Added notes on the last published version calculate the next minor', () => {
  const plan = calculateReleasePlan({
    packageVersion: '0.1.0',
    manifestVersion: '0.1.0',
    changelog: changelogWith('### Added\n\n- Installer purge command.\n'),
    sourceCommit: 'abc123',
  });
  assert.equal(plan.version, '0.2.0');
  assert.equal(plan.bump, 'minor');
  assert.equal(plan.identitiesCommitted, false);
  assert.equal(plan.sourceCommit, 'abc123');
  assert.deepEqual(plan.changeSet, [{ heading: 'Added', items: ['Installer purge command.'] }]);
  assert.equal(plan.tag, 'v0.2.0');
  assert.equal(plan.githubRelease, 'v0.2.0');
  assert.equal(plan.npmPackage, 'sigmaskills@0.2.0');
  assert.equal(plan.distTag, RELEASE_DIST_TAG);
  assert.equal(plan.tests.command, 'npm test');
});

test('release plan: Fixed-only notes calculate a patch, Removed notes calculate a major', () => {
  const patch = calculateReleasePlan({
    packageVersion: '1.2.0',
    manifestVersion: '1.2.0',
    changelog: changelogWith('### Fixed\n\n- Restore fallback on Windows.\n', '1.2.0'),
    sourceCommit: 'def',
  });
  assert.equal(patch.version, '1.2.1');
  assert.equal(patch.bump, 'patch');

  const major = calculateReleasePlan({
    packageVersion: '1.2.0',
    manifestVersion: '1.2.0',
    changelog: changelogWith('### Removed\n\n- Legacy flag.\n', '1.2.0'),
    sourceCommit: 'def',
  });
  assert.equal(major.version, '2.0.0');
  assert.equal(major.bump, 'major');
});

test('release plan: committed identities reuse that version and its change set', () => {
  const plan = calculateReleasePlan({
    packageVersion: '0.2.0',
    manifestVersion: '0.2.0',
    changelog: readyIdentities['CHANGELOG.md'],
    sourceCommit: 'cafebabe',
  });
  assert.equal(plan.version, '0.2.0');
  assert.equal(plan.identitiesCommitted, true);
  assert.deepEqual(plan.changeSet, [{ heading: 'Added', items: ['Owner-triggered publication.'] }]);
});

test('release plan: package and manifest disagreement fails closed', () => {
  assert.throws(
    () => calculateReleasePlan({
      packageVersion: '0.2.0',
      manifestVersion: '0.1.0',
      changelog: changelogWith('### Added\n\n- x\n'),
      sourceCommit: 'a',
    }),
    /package\.json and manifest\.json versions disagree/,
  );
});

test('release identities: Unreleased notes move under the calculated version heading', () => {
  const applied = applyReleaseIdentities({
    packageJson: { name: 'sigmaskills', version: '0.1.0' },
    manifest: { schemaVersion: 1, name: 'sigmaskills', version: '0.1.0' },
    changelog: changelogWith('### Added\n\n- Purge command.\n'),
    version: '0.2.0',
    date: '2026-08-19',
  });
  assert.equal(applied.packageJson.version, '0.2.0');
  assert.equal(applied.manifest.version, '0.2.0');
  assert.match(applied.changelog, /## \[Unreleased\]\s*\n\s*\n## \[0\.2\.0\] — 2026-08-19/);
  assert.match(applied.changelog, /### Added\s*\n\s*\n- Purge command\./);
  assert.match(applied.changelog, /## \[0\.1\.0\]/);
});

test('release dry-run preview names commit, version, tests, tarball, revisions, tag, GitHub Release, npm, and dist-tag', () => {
  const dir = tmpTree(readyIdentities);
  try {
    const result = executeRelease({
      rootDir: dir,
      catalog: { ...catalog, manifest: { ...catalog.manifest, version: '0.2.0' } },
      dryRun: true,
      git: { revParse: () => 'deadbeef', statusPorcelain: () => '', tagCommit: () => null },
      pack: () => ({
        digest: 'ff'.repeat(32),
        integrity: 'sha512-abc',
        contents: ['package/package.json', 'package/manifest.json', 'package/LICENSE'],
        filename: 'sigmaskills-0.2.0.tgz',
      }),
      probes: {
        npmPackage: { exists: true, versions: {} },
        githubRelease: null,
        environment: { name: RELEASE_ENVIRONMENT, protected: true },
        trustedPublisher: true,
      },
    });
    assert.equal(result.schemaVersion, RELEASE_SCHEMA_VERSION);
    assert.equal(result.dryRun, true);
    assert.equal(result.commit, 'deadbeef');
    assert.equal(result.version, '0.2.0');
    assert.equal(result.tests.command, 'npm test');
    assert.equal(result.tarball.digest, 'ff'.repeat(32));
    assert.ok(result.tarball.contents.includes('package/LICENSE'));
    assert.equal(result.skills[0].revision, 'aa'.repeat(32));
    assert.equal(result.tag, 'v0.2.0');
    assert.equal(result.githubRelease, 'v0.2.0');
    assert.equal(result.npmPackage, 'sigmaskills@0.2.0');
    assert.equal(result.distTag, 'latest');
    const human = formatReleaseHuman(result);
    assert.match(human, /deadbeef/);
    assert.match(human, /0\.2\.0/);
    assert.match(human, /npm test/);
    assert.match(human, /sha256:/);
    assert.match(human, /sigmawrite/);
    assert.match(human, /v0\.2\.0/);
    assert.match(human, /GitHub Release/);
    assert.match(human, /sigmaskills@0\.2\.0/);
    assert.match(human, /latest/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('release confirmation: --yes, CI, and informal text cannot dispatch', () => {
  const dir = tmpTree(readyIdentities);
  try {
    const adapters = {
      rootDir: dir,
      catalog: { ...catalog, manifest: { ...catalog.manifest, version: '0.2.0' } },
      git: { revParse: () => 'deadbeef', statusPorcelain: () => '', tagCommit: () => null },
      pack: () => ({ digest: 'aa'.repeat(32), integrity: 'sha512-x', contents: ['package/package.json'], filename: 'sigmaskills-0.2.0.tgz' }),
      probes: {
        npmPackage: { exists: true, versions: {} },
        githubRelease: null,
        environment: { name: RELEASE_ENVIRONMENT, protected: true },
        trustedPublisher: true,
      },
      dispatch: () => {
        throw new Error('dispatch must not run');
      },
    };
    for (const extra of [{ yes: true }, { confirmText: 'publish' }, { confirmText: 'yes' }]) {
      assert.throws(
        () => executeRelease({ ...adapters, ...extra }),
        /immutable expected commit, version, and digest/,
      );
    }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('release confirmation: matching expected commit, version, and digest dispatch the trusted workflow', () => {
  const dir = tmpTree(readyIdentities);
  try {
    const dispatched = [];
    const result = executeRelease({
      rootDir: dir,
      catalog: { ...catalog, manifest: { ...catalog.manifest, version: '0.2.0' } },
      expectedCommit: 'deadbeef',
      expectedVersion: '0.2.0',
      expectedDigest: 'aa'.repeat(32),
      git: { revParse: () => 'deadbeef', statusPorcelain: () => '', tagCommit: () => null },
      pack: () => ({ digest: 'aa'.repeat(32), integrity: 'sha512-x', contents: ['package/package.json'], filename: 'sigmaskills-0.2.0.tgz' }),
      workflow: inspectedWorkflow,
      probes: {
        npmPackage: { exists: true, versions: {} },
        githubRelease: null,
        environment: { name: RELEASE_ENVIRONMENT, protected: true },
        trustedPublisher: true,
      },
      dispatch: (payload) => {
        dispatched.push(payload);
        return { ok: true };
      },
    });
    assert.equal(result.dispatched, true);
    assert.equal(dispatched.length, 1);
    assert.deepEqual(dispatched[0], {
      workflow: RELEASE_WORKFLOW_FILE,
      expectedCommit: 'deadbeef',
      expectedVersion: '0.2.0',
      expectedDigest: 'aa'.repeat(32),
    });
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('release confirmation: a mismatched expected digest does not dispatch', () => {
  const dir = tmpTree(readyIdentities);
  try {
    assert.throws(
      () => executeRelease({
        rootDir: dir,
        catalog: { ...catalog, manifest: { ...catalog.manifest, version: '0.2.0' } },
        expectedCommit: 'deadbeef',
        expectedVersion: '0.2.0',
        expectedDigest: 'bb'.repeat(32),
        git: { revParse: () => 'deadbeef', statusPorcelain: () => '', tagCommit: () => null },
        pack: () => ({ digest: 'aa'.repeat(32), integrity: 'sha512-x', contents: ['package/package.json'], filename: 'x.tgz' }),
        probes: {
          npmPackage: { exists: true, versions: {} },
          githubRelease: null,
          environment: { name: RELEASE_ENVIRONMENT, protected: true },
          trustedPublisher: true,
        },
        dispatch: () => {
          throw new Error('dispatch must not run');
        },
      }),
      /does not match/,
    );
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('publication gate: missing reservation, publisher, environment, protection, or conflicts fail closed with setup guidance', () => {
  const expected = { version: '0.2.0', commit: 'deadbeef', digest: 'aa'.repeat(32), integrity: 'sha512-local' };
  const workflow = inspectReleaseWorkflow(fs.readFileSync(path.join(ROOT, '.github', 'workflows', RELEASE_WORKFLOW_FILE), 'utf8'));

  const reservation = evaluatePublicationGate({
    expected,
    workflow,
    npmPackage: { exists: false, versions: {} },
    githubRelease: null,
    gitTag: null,
    environment: { name: RELEASE_ENVIRONMENT, protected: true },
    trustedPublisher: true,
  });
  assert.equal(reservation.ok, false);
  assert.match(reservation.errors.join('\n'), /Reserve the npm name `sigmaskills`/);

  const publisher = evaluatePublicationGate({
    expected,
    workflow,
    npmPackage: { exists: true, versions: {} },
    githubRelease: null,
    gitTag: null,
    environment: { name: RELEASE_ENVIRONMENT, protected: true },
    trustedPublisher: false,
  });
  assert.match(publisher.errors.join('\n'), /trusted publisher/);
  assert.match(publisher.errors.join('\n'), /release\.yml/);

  const environment = evaluatePublicationGate({
    expected,
    workflow,
    npmPackage: { exists: true, versions: {} },
    githubRelease: null,
    gitTag: null,
    environment: null,
    trustedPublisher: true,
  });
  assert.match(environment.errors.join('\n'), /GitHub Environment named `release`/);

  const protection = evaluatePublicationGate({
    expected,
    workflow,
    npmPackage: { exists: true, versions: {} },
    githubRelease: null,
    gitTag: null,
    environment: { name: RELEASE_ENVIRONMENT, protected: false },
    trustedPublisher: true,
  });
  assert.match(protection.errors.join('\n'), /protection/);

  const tag = evaluatePublicationGate({
    expected,
    workflow,
    npmPackage: { exists: true, versions: {} },
    githubRelease: null,
    gitTag: { name: 'v0.2.0', commit: 'other' },
    environment: { name: RELEASE_ENVIRONMENT, protected: true },
    trustedPublisher: true,
  });
  assert.match(tag.errors.join('\n'), /tag/);

  const release = evaluatePublicationGate({
    expected,
    workflow,
    npmPackage: { exists: true, versions: {} },
    githubRelease: { tag: 'v0.2.0', targetCommit: 'other' },
    gitTag: null,
    environment: { name: RELEASE_ENVIRONMENT, protected: true },
    trustedPublisher: true,
  });
  assert.match(release.errors.join('\n'), /GitHub Release/);
});

test('idempotent recovery: matching npm digest or GitHub Release is skipped; mismatches are refused', () => {
  const expected = { version: '0.2.0', commit: 'deadbeef', digest: 'aa'.repeat(32), integrity: 'sha512-local' };
  const skipNpm = planIdempotentPublish({
    expected,
    npmPackage: { exists: true, versions: { '0.2.0': { integrity: 'sha512-local' } } },
    githubRelease: null,
    gitTag: null,
  });
  assert.equal(skipNpm.ok, true);
  assert.equal(skipNpm.publishNpm, false);
  assert.equal(skipNpm.createGithubRelease, true);
  assert.equal(skipNpm.createTag, true);

  const skipAll = planIdempotentPublish({
    expected,
    npmPackage: { exists: true, versions: { '0.2.0': { integrity: 'sha512-local' } } },
    githubRelease: { tag: 'v0.2.0', targetCommit: 'deadbeef' },
    gitTag: { name: 'v0.2.0', commit: 'deadbeef' },
  });
  assert.equal(skipAll.publishNpm, false);
  assert.equal(skipAll.createGithubRelease, false);
  assert.equal(skipAll.createTag, false);

  const branchTarget = planIdempotentPublish({
    expected,
    npmPackage: { exists: true, versions: {} },
    githubRelease: { tag: 'v0.2.0', targetCommit: 'main' },
    gitTag: { name: 'v0.2.0', commit: 'deadbeef' },
  });
  assert.equal(branchTarget.ok, true);
  assert.equal(branchTarget.createGithubRelease, false);

  const clash = planIdempotentPublish({
    expected,
    npmPackage: { exists: true, versions: { '0.2.0': { integrity: 'sha512-other' } } },
    githubRelease: null,
    gitTag: null,
  });
  assert.equal(clash.ok, false);
  assert.match(clash.errors.join('\n'), /different digest/);
});

test('trusted workflow: validation is read-only, publish is the only privileged job, actions are pinned, merges do not publish', () => {
  const releaseYaml = fs.readFileSync(path.join(ROOT, '.github', 'workflows', RELEASE_WORKFLOW_FILE), 'utf8');
  const ciYaml = fs.readFileSync(path.join(ROOT, '.github', 'workflows', 'ci.yml'), 'utf8');
  const inspected = inspectReleaseWorkflow(releaseYaml);
  assert.equal(inspected.ok, true);
  assert.deepEqual(inspected.triggers, ['workflow_dispatch']);
  assert.equal(inspected.validate.permissions.contents, 'read');
  assert.equal(inspected.validate.permissions['id-token'], undefined);
  assert.equal(inspected.publish.permissions['id-token'], 'write');
  assert.equal(inspected.publish.permissions.contents, 'write');
  assert.equal(inspected.publish.environment, RELEASE_ENVIRONMENT);
  assert.match(inspected.checkoutPin, /^[a-f0-9]{40}$/);
  assert.match(inspected.setupNodePin, /^[a-f0-9]{40}$/);
  assert.equal(inspected.usesFloatingTags, false);
  assert.doesNotMatch(ciYaml, /npm publish/);
  assert.doesNotMatch(ciYaml, /id-token:/);
  assert.doesNotMatch(releaseYaml, /\non:\s*\n(?:[^\n]*\n)*?\s+push:/);
});

test('cli: release --dry-run --json prints the versioned preview; --yes is not enough to dispatch', async () => {
  const dir = tmpTree(readyIdentities);
  try {
    const release = {
      rootDir: dir,
      catalog: { ...catalog, manifest: { ...catalog.manifest, version: '0.2.0' } },
      git: { revParse: () => 'deadbeef', statusPorcelain: () => '', tagCommit: () => null },
      pack: () => ({ digest: 'aa'.repeat(32), integrity: 'sha512-x', contents: ['package/LICENSE'], filename: 'sigmaskills-0.2.0.tgz' }),
      probes: {
        npmPackage: { exists: true, versions: {} },
        githubRelease: null,
        environment: { name: RELEASE_ENVIRONMENT, protected: true },
        trustedPublisher: true,
      },
      dispatch: () => {
        throw new Error('dispatch must not run');
      },
    };
    const io = mockIo(release);
    const code = await runCli(['release', '--dry-run', '--json'], io);
    assert.equal(code, 0);
    const parsed = JSON.parse(io.getStdout());
    assert.equal(parsed.schemaVersion, RELEASE_SCHEMA_VERSION);
    assert.equal(parsed.command, 'release');
    assert.equal(parsed.version, '0.2.0');
    assert.equal(parsed.tarball.digest, 'aa'.repeat(32));

    const yesIo = mockIo(release);
    const yesCode = await runCli(['release', '--yes'], yesIo);
    assert.equal(yesCode, 1);
    assert.match(yesIo.getStderr(), /immutable expected commit, version, and digest/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('cli: parseCliArgs captures immutable release confirmation flags', () => {
  const parsed = parseCliArgs([
    'release',
    '--expected-commit', 'deadbeef',
    '--expected-version', '0.2.0',
    '--expected-digest', 'aa'.repeat(32),
  ]);
  assert.equal(parsed.command, 'release');
  assert.equal(parsed.expectedCommit, 'deadbeef');
  assert.equal(parsed.expectedVersion, '0.2.0');
  assert.equal(parsed.expectedDigest, 'aa'.repeat(32));
});

test('formatReleaseJson is a stable versioned envelope', () => {
  const json = JSON.parse(formatReleaseJson({
    schemaVersion: RELEASE_SCHEMA_VERSION,
    command: 'release',
    commit: 'deadbeef',
    version: '0.2.0',
    dryRun: true,
    tests: { command: 'npm test', required: true },
    tarball: { digest: 'aa'.repeat(32), contents: ['package/LICENSE'] },
    skills: [{ id: 'sigmawrite', revision: 'bb'.repeat(32) }],
    tag: 'v0.2.0',
    githubRelease: 'v0.2.0',
    npmPackage: 'sigmaskills@0.2.0',
    distTag: 'latest',
  }));
  assert.equal(json.schemaVersion, 1);
  assert.equal(json.command, 'release');
});
