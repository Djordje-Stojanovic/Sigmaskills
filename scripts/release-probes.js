import { execFileSync } from 'node:child_process';
import { RELEASE_ENVIRONMENT, RELEASE_PACKAGE_NAME, RELEASE_WORKFLOW_FILE } from './release-publication.js';
import { execNpm } from './release-util.js';

export function defaultGit(rootDir) {
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

// The npm package name and, when the name is taken, the digest of the expected version.
function probeNpm(version) {
  try {
    const name = execNpm(['view', RELEASE_PACKAGE_NAME, 'name'], { encoding: 'utf8' }).trim();
    const npmPackage = { exists: name === RELEASE_PACKAGE_NAME, versions: {} };
    if (npmPackage.exists) {
      try {
        const integrity = execNpm(
          ['view', `${RELEASE_PACKAGE_NAME}@${version}`, 'dist.integrity'],
          { encoding: 'utf8' },
        ).trim();
        if (integrity) npmPackage.versions[version] = { integrity };
      } catch {
        // Version is unpublished; reservation still counts.
      }
    }
    return npmPackage;
  } catch {
    return { exists: false, versions: {} };
  }
}

function probeGithubRelease(tag, git, rootDir) {
  try {
    const raw = execFileSync('gh', ['release', 'view', tag, '--json', 'tagName,targetCommitish'], {
      cwd: rootDir,
      encoding: 'utf8',
    });
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
  } catch {
    return null;
  }
}

function probeEnvironment() {
  try {
    const repo = process.env.GITHUB_REPOSITORY || 'Djordje-Stojanovic/Sigmaskills';
    const raw = execFileSync('gh', ['api', `repos/${repo}/environments/${RELEASE_ENVIRONMENT}`], { encoding: 'utf8' });
    const parsed = JSON.parse(raw);
    return {
      name: parsed.name,
      protected: Array.isArray(parsed.protection_rules) && parsed.protection_rules.length > 0,
    };
  } catch {
    return null;
  }
}

export function gitTagProbe(git, tag) {
  const commit = git.tagCommit?.(tag);
  return commit ? { name: tag, commit } : null;
}

export function defaultProbes({ git, expected, rootDir }) {
  return {
    npmPackage: probeNpm(expected.version),
    githubRelease: probeGithubRelease(expected.tag, git, rootDir),
    environment: probeEnvironment(),
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
