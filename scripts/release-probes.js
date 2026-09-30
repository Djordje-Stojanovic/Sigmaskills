import { execFileSync } from 'node:child_process';
import { RELEASE_ENVIRONMENT, RELEASE_PACKAGE_NAME, RELEASE_WORKFLOW_FILE } from './release-publication.js';
import { absentOn404, execNpm } from './release-util.js';

const DEFAULT_TOOLS = { execFileSync, execNpm };
// Capture stderr: an expected not-found (E404, missing tag) would otherwise print to the terminal.
// Node still puts it on a thrown error, so absentOn404 can read it.
const QUIET = ['ignore', 'pipe', 'pipe'];

export function defaultGit(rootDir) {
  const run = (args) => execFileSync('git', args, { cwd: rootDir, encoding: 'utf8', stdio: QUIET }).trim();
  return {
    revParse: (ref = 'HEAD') => run(['rev-parse', ref]),
    show: (spec) => run(['show', spec]),
    statusPorcelain: () => run(['status', '--porcelain']),
    // Only a missing tag is null. Any other git error stops the release.
    tagCommit: (tag) => absentOn404(() => run(['rev-list', '-n', '1', tag]), null),
  };
}

// The npm package name and, when the name is taken, the digest of the expected version.
// Only a 404 means "absent"; any other error stops the release.
function probeNpm(version, tools) {
  const name = absentOn404(
    () => tools.execNpm(['view', RELEASE_PACKAGE_NAME, 'name'], { encoding: 'utf8', stdio: QUIET }).trim(),
    '',
  );
  const npmPackage = { exists: name === RELEASE_PACKAGE_NAME, versions: {} };
  if (npmPackage.exists) {
    // A version that is not published still counts as a reservation.
    const integrity = absentOn404(
      () => tools.execNpm(['view', `${RELEASE_PACKAGE_NAME}@${version}`, 'dist.integrity'], { encoding: 'utf8', stdio: QUIET }).trim(),
      '',
    );
    if (integrity) npmPackage.versions[version] = { integrity };
  }
  return npmPackage;
}

function probeGithubRelease(tag, git, rootDir, tools) {
  const raw = absentOn404(
    () => tools.execFileSync('gh', ['release', 'view', tag, '--json', 'tagName,targetCommitish'], {
      cwd: rootDir,
      encoding: 'utf8',
      stdio: QUIET,
    }),
    null,
  );
  if (raw === null) return null;
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
  return { tag: parsed.tagName, targetCommit };
}

function probeEnvironment(tools) {
  const repo = process.env.GITHUB_REPOSITORY || 'Djordje-Stojanovic/Sigmaskills';
  const raw = absentOn404(
    () => tools.execFileSync('gh', ['api', `repos/${repo}/environments/${RELEASE_ENVIRONMENT}`], { encoding: 'utf8', stdio: QUIET }),
    null,
  );
  if (raw === null) return null;
  const parsed = JSON.parse(raw);
  return {
    name: parsed.name,
    protected: Array.isArray(parsed.protection_rules) && parsed.protection_rules.length > 0,
  };
}

export function gitTagProbe(git, tag) {
  const commit = git.tagCommit?.(tag);
  return commit ? { name: tag, commit } : null;
}

export function defaultProbes({ git, expected, rootDir, tools = DEFAULT_TOOLS }) {
  return {
    npmPackage: probeNpm(expected.version, tools),
    githubRelease: probeGithubRelease(expected.tag, git, rootDir, tools),
    environment: probeEnvironment(tools),
    gitTag: git.tagCommit ? gitTagProbe(git, expected.tag) : null,
  };
}

export function defaultDispatch({ expectedCommit, expectedVersion, expectedDigest, rootDir }) {
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
