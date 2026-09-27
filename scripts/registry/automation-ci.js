import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { loadPin } from './sync.js';
import {
  GENERATED_BRANCH_PREFIX,
  REGISTRY_ALLOWLIST,
  REGISTRY_SYNC_WORKFLOW_FILE,
  classifySemanticAuthority,
  executeRegistryAutomation,
} from './automation.js';
import { diffSnapshots } from './diff.js';
import { validateSnapshot } from './validate.js';
import {
  RELEASE_DIST_TAG,
  RELEASE_ENVIRONMENT,
  RELEASE_PACKAGE_NAME,
  applyRegistryPatchIdentities,
  executeTrustedPatchRelease,
} from '../release.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

function git(args, options = {}) {
  const out = execFileSync('git', args, { cwd: ROOT, encoding: 'utf8', ...options });
  return typeof out === 'string' ? out.trim() : '';
}

function ghJson(args, env) {
  const raw = execFileSync('gh', args, { cwd: ROOT, encoding: 'utf8', env });
  return JSON.parse(raw);
}

async function fetchJson(url, token) {
  const headers = { 'user-agent': 'sigmaskills-registry-sync' };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`GET ${url} failed: HTTP ${res.status}`);
  return res.json();
}

async function fetchText(url) {
  const res = await fetch(url, { headers: { 'user-agent': 'sigmaskills-registry-sync' } });
  if (!res.ok) throw new Error(`GET ${url} failed: HTTP ${res.status}`);
  return res.text();
}

function writeAllowlisted(plan) {
  const writes = {
    'registry/source.json': `${JSON.stringify(plan.pin, null, 2)}\n`,
    'registry/agent-hosts.json': `${JSON.stringify(plan.snapshot, null, 2)}\n`,
    'test/fixtures/vercel-skills/src/agents.ts': plan.upstreamText,
  };
  for (const file of REGISTRY_ALLOWLIST) {
    const abs = path.join(ROOT, file);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, writes[file], 'utf8');
  }
}

function stagedFiles() {
  const output = git(['diff', '--cached', '--name-only', '-z']);
  return output ? output.split('\0').filter(Boolean) : [];
}

function remoteGeneratedBranchSha(branch) {
  if (!String(branch || '').startsWith(GENERATED_BRANCH_PREFIX)) return null;
  const output = git(['ls-remote', '--heads', 'origin', branch]);
  const sha = (output.split(/\s+/)[0] || '').trim();
  return /^[0-9a-f]{40}$/.test(sha) ? sha : null;
}

function remoteGeneratedBranchExists(branch) {
  return remoteGeneratedBranchSha(branch) !== null;
}

function openGeneratedPullRequestExists(branch, env) {
  if (!String(branch || '').startsWith(GENERATED_BRANCH_PREFIX)) return false;
  const prs = ghJson(['pr', 'list', '--head', branch, '--state', 'open', '--json', 'number'], env);
  return Array.isArray(prs) && prs.length > 0;
}

function npmVersions() {
  try {
    const raw = execFileSync('npm', ['view', RELEASE_PACKAGE_NAME, 'versions', '--json'], {
      encoding: 'utf8',
    });
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [parsed];
  } catch {
    return [];
  }
}

function githubVersions(env) {
  try {
    return ghJson(['release', 'list', '--limit', '20', '--json', 'tagName'], env)
      .map((item) => String(item.tagName || '').replace(/^v/, ''))
      .filter((value) => /^\d+\.\d+\.\d+$/.test(value));
  } catch {
    return [];
  }
}

function probePublication(version, env) {
  let npmPackage = { exists: false, versions: {} };
  try {
    const name = execFileSync('npm', ['view', RELEASE_PACKAGE_NAME, 'name'], { encoding: 'utf8' }).trim();
    npmPackage.exists = name === RELEASE_PACKAGE_NAME;
    if (npmPackage.exists) {
      try {
        const integrity = execFileSync(
          'npm',
          ['view', `${RELEASE_PACKAGE_NAME}@${version}`, 'dist.integrity'],
          { encoding: 'utf8' },
        ).trim();
        if (integrity) npmPackage.versions[version] = { integrity };
      } catch {
        // Unpublished version; reservation still counts.
      }
    }
  } catch {
    npmPackage = { exists: false, versions: {} };
  }

  let githubRelease = null;
  let gitTag = null;
  const tag = `v${version}`;
  try {
    const parsed = ghJson(['release', 'view', tag, '--json', 'tagName,targetCommitish'], env);
    githubRelease = { tag: parsed.tagName, targetCommit: parsed.targetCommitish };
  } catch {
    githubRelease = null;
  }
  try {
    gitTag = { name: tag, commit: git(['rev-list', '-n', '1', tag]) };
  } catch {
    gitTag = null;
  }

  let environment = null;
  try {
    const repo = env.GITHUB_REPOSITORY || 'Djordje-Stojanovic/Sigmaskills';
    const parsed = JSON.parse(execFileSync(
      'gh',
      ['api', `repos/${repo}/environments/${RELEASE_ENVIRONMENT}`],
      { encoding: 'utf8', env },
    ));
    environment = {
      name: parsed.name,
      protected: Array.isArray(parsed.protection_rules) && parsed.protection_rules.length > 0,
    };
  } catch {
    environment = null;
  }

  return { npmPackage, githubRelease, gitTag, environment, trustedPublisher: env.GITHUB_ACTIONS === 'true' };
}

function createRealIo(env, mode) {
  const token = env.GITHUB_TOKEN;
  const pin = loadPin();
  return {
    converterSha: async () => (env.GITHUB_SHA || git(['rev-parse', 'HEAD'])).trim(),
    currentDefaultSha: async () => {
      try {
        git(['fetch', 'origin', 'main'], { stdio: 'ignore' });
        return git(['rev-parse', 'origin/main']);
      } catch {
        return git(['rev-parse', 'HEAD']);
      }
    },
    resolveUpstreamRevision: async () => {
      const commits = await fetchJson(
        `https://api.github.com/repos/${pin.repository}/commits?path=${encodeURIComponent(pin.upstreamFile)}&per_page=1`,
        token,
      );
      const sha = commits[0] && commits[0].sha;
      if (!sha || !/^[0-9a-f]{40}$/.test(sha)) {
        throw new Error('unable to resolve a pinned 40-hex upstream revision');
      }
      return sha;
    },
    fetchUpstreamText: async (revision) => fetchText(
      `https://raw.githubusercontent.com/${pin.repository}/${revision}/${pin.upstreamFile}`,
    ),
    readPin: async () => loadPin(),
    readSnapshot: async () => JSON.parse(fs.readFileSync(path.join(ROOT, 'registry/agent-hosts.json'), 'utf8')),
    hasConcurrentRun: async () => {
      try {
        const prs = ghJson(['pr', 'list', '--state', 'open', '--json', 'headRefName'], env)
          .filter((pr) => String(pr.headRefName || '').startsWith(GENERATED_BRANCH_PREFIX));
        return mode === 'auto-merge' ? prs.length > 1 : prs.length > 0;
      } catch {
        return false;
      }
    },
    writeAllowlisted: async (plan) => writeAllowlisted(plan),
    inspectGeneratedBranch: async (branch) => ({
      remoteExists: remoteGeneratedBranchExists(branch),
      openPullRequest: openGeneratedPullRequestExists(branch, env),
    }),
    createPullRequest: async (result) => {
      const branch = result.branch
        || `${GENERATED_BRANCH_PREFIX}${result.upstreamRevision.slice(0, 12)}`;
      const pushPlan = result.pushPlan;
      if (!pushPlan || !pushPlan.ok) {
        throw new Error(`refusing to publish ${pushPlan && pushPlan.reason ? pushPlan.reason : 'unknown'} branch ${branch}`);
      }
      if (pushPlan.action === 'reuse') return;
      if (env.GITHUB_ACTIONS) {
        git(['config', 'user.name', 'github-actions[bot]']);
        git(['config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com']);
      }
      git(['checkout', '-B', branch]);
      git(['add', '--', ...REGISTRY_ALLOWLIST]);
      const extra = stagedFiles().filter((file) => !REGISTRY_ALLOWLIST.includes(file.replace(/\\/g, '/')));
      if (extra.length > 0) throw new Error(`refusing to commit files outside the registry allowlist: ${extra.join(', ')}`);
      git(['commit', '-m', `chore(registry): sync Agent Host snapshot from ${result.upstreamRevision}`]);
      const generatedHeadSha = git(['rev-parse', 'HEAD']);
      if (pushPlan.forcePush) {
        const expected = remoteGeneratedBranchSha(branch);
        if (expected) {
          git(['push', `--force-with-lease=refs/heads/${branch}:${expected}`, '-u', 'origin', branch]);
        } else {
          git(['push', '-u', 'origin', branch]);
        }
      } else {
        git(['push', '-u', 'origin', branch]);
      }
      if (pushPlan.createPr === false) return;
      try {
        execFileSync('gh', [
          'pr', 'create',
          '--title', `chore(registry): sync Agent Hosts from ${result.upstreamRevision.slice(0, 12)}`,
          '--body', `${result.body}\nGenerated head SHA: \`${generatedHeadSha}\`\n`,
          '--base', 'main',
        ], { cwd: ROOT, encoding: 'utf8', env });
      } catch (err) {
        const message = `${err.message || ''}\n${err.stderr || ''}`;
        if (/already exists/i.test(message)) return;
        throw err;
      }
    },
    listBranches: async () => git(['branch', '-a']).split(/\n/).map((line) => ({
      name: line.replace(/^\*?\s*/, '').replace(/^remotes\/origin\//, ''),
      generated: line.includes('registry/sync-'),
    })),
    protectedRefs: async () => ['main'],
    inspectPullRequest: async () => {
      const prs = ghJson(['pr', 'list', '--state', 'open', '--json', 'number,headRefName,headRefOid,isCrossRepository,files,body'], env)
        .filter((pr) => String(pr.headRefName || '').startsWith(GENERATED_BRANCH_PREFIX));
      if (prs.length !== 1) return null;
      const listed = prs[0];
      let checkConclusion = 'failure';
      try {
        execFileSync('gh', ['pr', 'checks', String(listed.number), '--watch', '--fail-fast'], {
          cwd: ROOT,
          encoding: 'utf8',
          env,
        });
        checkConclusion = 'success';
      } catch {
        checkConclusion = 'failure';
      }
      const pr = ghJson(['pr', 'view', String(listed.number), '--json', 'number,headRefName,headRefOid,isCrossRepository,files,body'], env);
      const files = (pr.files || []).map((file) => file.path).filter(Boolean);
      const recorded = String(pr.body || '').match(/Generated head SHA: `([0-9a-f]{40})`/i);
      return {
        origin: pr.isCrossRepository ? 'fork' : 'same-repo',
        headRef: pr.headRefName,
        headSha: pr.headRefOid,
        expectedGeneratedSha: recorded ? recorded[1] : 'missing-generated-sha',
        files,
        checkConclusion,
        number: pr.number,
      };
    },
    fromTrustedWorkflow: async () => (
      env.GITHUB_ACTIONS === 'true' && (
        String(env.GITHUB_WORKFLOW_REF || '').includes(`${REGISTRY_SYNC_WORKFLOW_FILE}`)
        || String(env.GITHUB_WORKFLOW_FILE || '') === REGISTRY_SYNC_WORKFLOW_FILE
        || /registry[\s_-]?sync/i.test(String(env.GITHUB_WORKFLOW || ''))
      )
    ),
    defaultBranchProtected: async () => {
      try {
        const repo = env.GITHUB_REPOSITORY || 'Djordje-Stojanovic/Sigmaskills';
        const parsed = JSON.parse(execFileSync(
          'gh',
          ['api', `repos/${repo}/branches/main`],
          { encoding: 'utf8', env },
        ));
        return parsed.protected === true;
      } catch {
        return false;
      }
    },
    classification: async () => {
      const repo = env.GITHUB_REPOSITORY;
      const prs = ghJson(['pr', 'list', '--state', 'open', '--json', 'number,headRefName,headRefOid'], env)
        .filter((item) => String(item.headRefName || '').startsWith(GENERATED_BRANCH_PREFIX));
      if (prs.length !== 1) return { autoEligible: false, blockedReasons: ['no generated pull request'] };
      const readSnapshot = (ref) => {
        const parsed = JSON.parse(execFileSync(
          'gh',
          ['api', `repos/${repo}/contents/registry/agent-hosts.json?ref=${ref}`],
          { encoding: 'utf8', env },
        ));
        return JSON.parse(Buffer.from(parsed.content, 'base64').toString('utf8'));
      };
      const current = readSnapshot(prs[0].headRefOid);
      const validation = validateSnapshot(current);
      if (!validation.valid) {
        return {
          autoEligible: false,
          blockedReasons: [...(validation.errors || []), ...Object.values(validation.hostErrors || {})],
        };
      }
      return classifySemanticAuthority(diffSnapshots(readSnapshot('main'), current));
    },
    acquireVersionLock: async () => {
      const runs = ghJson(['run', 'list', '--workflow', REGISTRY_SYNC_WORKFLOW_FILE, '--status', 'in_progress', '--json', 'databaseId'], env);
      if (runs.length > 1) throw new Error('concurrent registry-sync run holds the version lock');
      return { release: async () => {} };
    },
    reconcilePublishedState: async () => ({
      packageVersion: JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')).version,
      npmVersions: npmVersions(),
      githubVersions: githubVersions(env),
    }),
    mergePullRequest: async (pr) => {
      execFileSync('gh', ['pr', 'merge', String(pr.number), '--squash'], {
        cwd: ROOT,
        encoding: 'utf8',
        env,
      });
      git(['fetch', 'origin', 'main'], { stdio: 'ignore' });
      return { merged: true, sha: git(['rev-parse', 'origin/main']), number: pr.number };
    },
    verifyMerge: async (merged) => {
      const view = ghJson(['pr', 'view', String(merged.number), '--json', 'state,mergeCommit'], env);
      const sha = view.mergeCommit && (view.mergeCommit.oid || view.mergeCommit);
      return { ok: view.state === 'MERGED' && Boolean(sha), sha };
    },
    commitPatchIdentities: async ({ version }) => {
      git(['fetch', 'origin', 'main']);
      git(['checkout', 'main']);
      git(['pull', '--ff-only', 'origin', 'main']);
      if (env.GITHUB_ACTIONS) {
        git(['config', 'user.name', 'github-actions[bot]']);
        git(['config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com']);
      }
      const applied = applyRegistryPatchIdentities({
        packageJson: JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')),
        manifest: JSON.parse(fs.readFileSync(path.join(ROOT, 'manifest.json'), 'utf8')),
        changelog: fs.readFileSync(path.join(ROOT, 'CHANGELOG.md'), 'utf8'),
        version,
        date: new Date().toISOString().slice(0, 10),
        note: 'Agent Host registry patch from trusted registry-sync automation.',
      });
      fs.writeFileSync(path.join(ROOT, 'package.json'), `${JSON.stringify(applied.packageJson, null, 2)}\n`);
      fs.writeFileSync(path.join(ROOT, 'manifest.json'), `${JSON.stringify(applied.manifest, null, 2)}\n`);
      fs.writeFileSync(path.join(ROOT, 'CHANGELOG.md'), applied.changelog);
      git(['add', '--', 'package.json', 'manifest.json', 'CHANGELOG.md']);
      git(['commit', '-m', `chore(release): ${version} Agent Host registry patch`]);
      git(['push', 'origin', 'HEAD:main']);
      return { commit: git(['rev-parse', 'HEAD']), version };
    },
    trustedPatchRelease: async (payload) => {
      const probes = probePublication(payload.version, env);
      const rootDir = ROOT;
      return executeTrustedPatchRelease({
        version: payload.version,
        commit: payload.commit,
        rootDir,
        ...probes,
        publishers: {
          createTag: (preview) => {
            try {
              execFileSync('git', ['tag', preview.tag, preview.commit], { cwd: rootDir, encoding: 'utf8' });
            } catch {
              // Tag may already exist at this commit.
            }
            execFileSync('git', ['push', 'origin', preview.tag], { cwd: rootDir, encoding: 'utf8' });
          },
          createGithubRelease: (preview) => {
            execFileSync(
              'gh',
              ['release', 'create', preview.tag, '--target', preview.commit, '--title', preview.tag, '--notes', `Agent Host registry patch ${preview.version}`],
              { cwd: rootDir, encoding: 'utf8', env },
            );
          },
          publishNpm: (preview) => {
            const artifact = preview.tarball?.path;
            execFileSync(
              'npm',
              artifact
                ? ['publish', artifact, '--access', 'public', '--tag', RELEASE_DIST_TAG, '--provenance']
                : ['publish', '--access', 'public', '--tag', RELEASE_DIST_TAG, '--provenance'],
              { cwd: rootDir, encoding: 'utf8', env },
            );
          },
        },
      });
    },
    verifyPublication: async (published) => {
      const probes = probePublication(published.version, env);
      const npmOk = Boolean(probes.npmPackage.versions?.[published.version]);
      const githubOk = Boolean(probes.githubRelease);
      return { ok: npmOk && githubOk, npmMatches: npmOk, githubMatches: githubOk };
    },
    deleteBranch: async (name) => {
      if (!name.startsWith(GENERATED_BRANCH_PREFIX)) {
        throw new Error(`refusing to delete non-generated branch ${name}`);
      }
      execFileSync('git', ['push', 'origin', '--delete', name], { cwd: ROOT, encoding: 'utf8', env });
    },
  };
}

const mode = process.argv[2] || 'generate';
const env = process.env;
const dryRun = env.DRY_RUN === '1' || process.argv.includes('--dry-run');

try {
  const result = await executeRegistryAutomation({
    mode,
    dryRun,
    expectedHead: env.EXPECTED_HEAD,
    upstreamRevision: env.UPSTREAM_REVISION || undefined,
  }, createRealIo(env, mode));
  console.log(JSON.stringify({
    ok: result.ok !== false,
    dryRun: result.dryRun === true,
    autoEligible: result.classification && result.classification.autoEligible,
    autoAuthorized: result.autoAuthorized === true
      || (result.autoAuthorization && result.autoAuthorization.autoAuthorized),
    blockedReasons: result.deniedReasons
      || (result.classification && result.classification.blockedReasons)
      || [],
    wouldDelete: result.wouldDelete || [],
    files: result.files || [],
    merged: result.merged === true,
    published: result.published === true,
    version: result.version || null,
    actions: result.actions || { merge: false, publishNpm: false },
  }, null, 2));
  if (result.ok === false) process.exit(1);
} catch (err) {
  console.error(err.message || err);
  process.exit(1);
}
