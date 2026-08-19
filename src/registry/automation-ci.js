import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { loadPin } from './sync.js';
import {
  REGISTRY_ALLOWLIST,
  executeRegistryAutomation,
} from './automation.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

function git(args, options = {}) {
  const out = execFileSync('git', args, { cwd: ROOT, encoding: 'utf8', ...options });
  return typeof out === 'string' ? out.trim() : '';
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

function createRealIo(env) {
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
        const raw = execFileSync('gh', ['pr', 'list', '--state', 'open', '--json', 'headRefName'], {
          cwd: ROOT,
          encoding: 'utf8',
          env,
        });
        return JSON.parse(raw).some((pr) => String(pr.headRefName || '').startsWith('registry/sync-'));
      } catch {
        return false;
      }
    },
    writeAllowlisted: async (plan) => writeAllowlisted(plan),
    createPullRequest: async (result) => {
      const branch = `registry/sync-${result.upstreamRevision.slice(0, 12)}`;
      if (env.GITHUB_ACTIONS) {
        git(['config', 'user.name', 'github-actions[bot]']);
        git(['config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com']);
      }
      git(['checkout', '-B', branch]);
      git(['add', '--', ...REGISTRY_ALLOWLIST]);
      const extra = stagedFiles().filter((file) => !REGISTRY_ALLOWLIST.includes(file.replace(/\\/g, '/')));
      if (extra.length > 0) throw new Error(`refusing to commit files outside the registry allowlist: ${extra.join(', ')}`);
      git(['commit', '-m', `chore(registry): sync Agent Host snapshot from ${result.upstreamRevision}`]);
      git(['push', '-u', 'origin', branch]);
      execFileSync('gh', [
        'pr', 'create',
        '--title', `chore(registry): sync Agent Hosts from ${result.upstreamRevision.slice(0, 12)}`,
        '--body', result.body,
        '--base', 'main',
      ], { cwd: ROOT, encoding: 'utf8', env });
    },
    listBranches: async () => git(['branch', '-a']).split(/\n/).map((line) => ({
      name: line.replace(/^\*?\s*/, '').replace(/^remotes\/origin\//, ''),
      generated: line.includes('registry/sync-'),
    })),
    protectedRefs: async () => ['main'],
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
  }, createRealIo(env));
  console.log(JSON.stringify({
    ok: result.ok !== false,
    dryRun: result.dryRun === true,
    autoEligible: result.classification && result.classification.autoEligible,
    autoAuthorized: result.autoAuthorization && result.autoAuthorization.autoAuthorized,
    blockedReasons: (result.classification && result.classification.blockedReasons) || [],
    wouldDelete: result.wouldDelete || [],
    files: result.files || [],
    actions: result.actions || { merge: false, publishNpm: false },
  }, null, 2));
  if (result.ok === false) process.exit(1);
} catch (err) {
  console.error(err.message || err);
  process.exit(1);
}
