// Rehearse the owner Release path on the checked-out commit, in a throwaway worktree:
// write and commit identities, preview (--dry-run), dispatch, then trusted validate and publish.
// git and npm pack run for real. npm and GitHub lookups, dispatch, publish, and the test
// re-run (CI's test job covers it) are stubbed, so no secrets or network are needed.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { RELEASE_ENVIRONMENT, runReleaseCli, runTrustedPublish, writeReleaseIdentities } from './release.js';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dir = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-rehearsal-')), 'repo');
const git = (...args) => execFileSync('git', args, { cwd: dir, encoding: 'utf8' }).trim();
const probes = {
  npmPackage: { exists: true, versions: {} },
  githubRelease: null,
  gitTag: null,
  environment: { name: RELEASE_ENVIRONMENT, protected: true },
  trustedPublisher: true,
};

async function release(args, adapters = {}) {
  let stdout = '';
  let stderr = '';
  const io = {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    release: { rootDir: dir, probes, ...adapters },
  };
  if (await runReleaseCli(args, io) !== 0) throw new Error(stderr.trim());
  return stdout;
}

execFileSync('git', ['worktree', 'add', '--detach', dir, 'HEAD'], { cwd: repo, stdio: 'ignore' });
try {
  writeReleaseIdentities(dir);
  git('add', '-A');
  if (git('status', '--porcelain')) {
    git('-c', 'user.name=Release rehearsal', '-c', 'user.email=rehearsal@example.invalid', 'commit', '-q', '-m', 'Release identities (rehearsal)');
  }
  const preview = JSON.parse(await release(['--dry-run', '--json']));
  let dispatched;
  await release(
    ['--expected-commit', preview.commit, '--expected-version', preview.version, '--expected-digest', preview.tarball.digest],
    { dispatch: (payload) => { dispatched = payload; } },
  );
  const published = [];
  const stub = (step) => () => published.push(step);
  await runTrustedPublish(
    {
      EXPECTED_COMMIT: dispatched.expectedCommit,
      EXPECTED_VERSION: dispatched.expectedVersion,
      EXPECTED_DIGEST: dispatched.expectedDigest,
    },
    {
      rootDir: dir,
      probes,
      runTests: () => {},
      publishers: { createTag: stub('tag'), createGithubRelease: stub('GitHub Release'), publishNpm: stub('npm') },
    },
  );
  console.log(`Release rehearsal passed: ${preview.version} at ${preview.commit}, sha256:${preview.tarball.digest}; stubbed ${published.join(', ')}`);
} finally {
  execFileSync('git', ['worktree', 'remove', '--force', dir], { cwd: repo, stdio: 'ignore' });
}
