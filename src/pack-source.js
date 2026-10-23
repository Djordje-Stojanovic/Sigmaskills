import { execFile, execFileSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildTransform } from './pack-transform.js';

const SKIP_DIRS = new Set(['node_modules', '.git']);
const FULL_SHA = /^[0-9a-f]{40}$/;
const GIT_ENV = { ...process.env, GIT_TERMINAL_PROMPT: '0' };

function isDirectory(target) {
  try {
    return fs.statSync(target).isDirectory();
  } catch {
    return false;
  }
}

/**
 * Find every skill folder under a root: a folder that holds a SKILL.md. The folder name is the
 * skill id. Dot folders are skipped (they hold copies of the same skills), and the scan does not
 * descend into a skill folder.
 *
 * @param {string} root
 * @returns {Map<string, string>} skill id to absolute folder
 */
export function findSkillDirs(root) {
  const found = new Map();
  const walk = (dir, depth) => {
    if (depth > 4) return;
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    if (depth > 0 && entries.some((entry) => entry.isFile() && entry.name === 'SKILL.md')) {
      const id = path.basename(dir);
      if (!found.has(id)) found.set(id, dir);
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith('.') || SKIP_DIRS.has(entry.name)) continue;
      const full = path.join(dir, entry.name);
      if (!entry.isDirectory() && !(entry.isSymbolicLink() && isDirectory(full))) continue;
      walk(full, depth + 1);
    }
  };
  walk(path.resolve(root), 0);
  return found;
}

/**
 * Hash a folder by relative path and bytes, so two folders with the same files hash the same.
 *
 * @param {string} dir
 * @returns {string} hex sha256
 */
export function hashDirectory(dir) {
  const hash = createHash('sha256');
  const walk = (current, prefix) => {
    const entries = fs.readdirSync(current, { withFileTypes: true })
      .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    for (const entry of entries) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        hash.update(`d:${rel}\n`);
        walk(full, rel);
      } else if (entry.isFile() || (entry.isSymbolicLink() && !isDirectory(full))) {
        hash.update(`f:${rel}\n`);
        hash.update(fs.readFileSync(full));
        hash.update('\n');
      }
    }
  };
  walk(dir, '');
  return hash.digest('hex');
}

function gitUrl(source, env) {
  if (source.url) return source.url;
  const base = env.SIGMA_GIT_BASE || 'https://github.com/';
  return `${base}${source.repo}${base.startsWith('http') ? '.git' : ''}`;
}

function describeSource(source) {
  if (source.type === 'dir') return source.env || source.path || 'local folder';
  return source.repo || source.url;
}

/**
 * The git steps that fetch one source into `dest`: a shallow fetch of exactly one commit (the
 * `ref` tag or commit, else the head), with only `source.path` checked out and blobs fetched on
 * demand. Small, fast, and safe on Windows (no deep fixture paths from the rest of the repo).
 */
function planFetch(url, dest, source) {
  const ref = source.ref || 'HEAD';
  const steps = [
    { args: ['init', '-q', dest] },
    { args: ['-C', dest, 'remote', 'add', 'origin', url] },
  ];
  if (source.path) steps.push({ args: ['-C', dest, 'sparse-checkout', 'set', '--cone', source.path] });
  steps.push({
    args: ['-C', dest, 'fetch', '-q', '--depth', '1', '--filter=blob:none', 'origin', ref],
    fallback: ['-C', dest, 'fetch', '-q', '--depth', '1', 'origin', ref],
  });
  steps.push({ args: ['-c', 'advice.detachedHead=false', '-C', dest, 'checkout', '-q', '--detach', 'FETCH_HEAD'] });
  steps.push({ args: ['-C', dest, 'rev-parse', 'HEAD'], capture: true });
  return steps;
}

const GIT_OPTS = { stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', windowsHide: true, env: GIT_ENV };

function gitFailure(err) {
  const lines = String(err.stderr || err.message || err).split('\n').map((line) => line.trim()).filter(Boolean);
  return new Error(lines[lines.length - 1] || 'git failed');
}

function verifyRevision(source, revision) {
  if (FULL_SHA.test(source.ref || '') && revision !== source.ref) {
    throw new Error(`fetched ${revision.slice(0, 8)}, not the pinned commit ${source.ref.slice(0, 8)}`);
  }
  return revision;
}

function fetchGitSync(url, dest, source) {
  let revision = '';
  for (const step of planFetch(url, dest, source)) {
    let out;
    try {
      out = execFileSync('git', step.args, GIT_OPTS);
    } catch (err) {
      if (!step.fallback) throw gitFailure(err);
      try {
        out = execFileSync('git', step.fallback, GIT_OPTS);
      } catch (second) {
        throw gitFailure(second);
      }
    }
    if (step.capture) revision = String(out).trim();
  }
  return verifyRevision(source, revision);
}

function execGit(args) {
  return new Promise((resolve, reject) => {
    execFile('git', args, GIT_OPTS, (err, stdout) => (err ? reject(gitFailure(err)) : resolve(String(stdout))));
  });
}

async function fetchGitAsync(url, dest, source) {
  let revision = '';
  for (const step of planFetch(url, dest, source)) {
    let out;
    try {
      out = await execGit(step.args);
    } catch (err) {
      if (!step.fallback) throw err;
      out = await execGit(step.fallback);
    }
    if (step.capture) revision = out.trim();
  }
  return verifyRevision(source, revision);
}

function cacheRoot(env) {
  if (env.SIGMA_CACHE_DIR) return path.resolve(env.SIGMA_CACHE_DIR);
  return path.join(path.resolve(env.HOME || env.USERPROFILE || os.homedir()), '.sigmaskills', 'cache', 'git');
}

function cacheKey(source) {
  const name = String(source.repo || source.url).replace(/[^A-Za-z0-9._-]+/g, '_');
  const part = String(source.path || '').replace(/[^A-Za-z0-9._-]+/g, '_');
  return `${name}@${source.ref}${part ? `#${part}` : ''}`;
}

function headOf(dir) {
  return execFileSync('git', ['-C', dir, 'rev-parse', 'HEAD'], GIT_OPTS).trim();
}

/**
 * One fetcher per command. It fetches each source once, however many skills come from it.
 *
 * A source is `{ type: 'git', repo, path, ref?, transform? }` or `{ type: 'dir', path | env, prefix }`.
 * A git source with a `ref` (a release tag or a full commit) is pinned: it is fetched at that
 * ref, checked, and kept in the cache folder (`~/.sigmaskills/cache/git`, or SIGMA_CACHE_DIR), so
 * a later run makes no network call. A source without a `ref` follows the head and is never cached.
 * A source with a `transform` is turned into skill folders after the fetch (see pack-transform.js).
 *
 * `await warm(sources)` fetches every distinct git source at once. `fetch(source)` returns
 * `{ root, revision, label }`, where `root` holds the skill folders; it fetches on the spot when
 * the source was not warmed. `close()` removes the temporary folders.
 *
 * @param {object} [options]
 * @param {NodeJS.ProcessEnv} [options.env]
 * @returns {{ fetch: Function, warm: Function, close: Function }}
 */
export function createSourceFetcher({ env = process.env } = {}) {
  const done = new Map();
  const temps = [];

  const tempDir = (parent, prefix) => {
    fs.mkdirSync(parent, { recursive: true });
    return path.join(parent, `${prefix}${process.pid}-${randomBytes(4).toString('hex')}`);
  };

  /** Where a git source is fetched: the cache for a pinned source, a temporary folder otherwise. */
  function gitTarget(source) {
    if (!source.ref) {
      const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'sigmaskills-src-'));
      temps.push(temp);
      return { temp, final: null };
    }
    const root = cacheRoot(env);
    const final = path.join(root, cacheKey(source));
    if (fs.existsSync(path.join(final, '.git'))) return { final, hit: true };
    return { temp: tempDir(root, '.tmp-'), final };
  }

  function settle(source, checkout, revision) {
    const label = source.repo || source.url;
    let result = { root: path.join(checkout, source.path || ''), repoRoot: checkout, revision, label };
    if (source.transform) {
      const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigmaskills-gen-'));
      temps.push(outDir);
      buildTransform(source.transform, {
        repoRoot: checkout, sourcePath: source.path || '', outDir, revision, repo: source.repo, skills: source.skills || [],
      });
      result = { ...result, root: outDir };
    }
    return result;
  }

  /** Move a finished temporary fetch into the cache. Another process may have won the race. */
  function keep(target) {
    if (!target.final || !target.temp) return target.temp || target.final;
    try {
      fs.renameSync(target.temp, target.final);
    } catch {
      fs.rmSync(target.temp, { recursive: true, force: true });
    }
    return target.final;
  }

  function discard(target) {
    if (target.temp && target.final) fs.rmSync(target.temp, { recursive: true, force: true });
  }

  function failure(source, err) {
    return new Error(`could not fetch ${describeSource(source)}: ${String(err.message || err).split('\n')[0]}`);
  }

  function fetchDir(source) {
    const dir = source.path || (source.env ? env[source.env] : '');
    if (!dir || !fs.existsSync(dir)) {
      throw new Error(`source folder not found (${describeSource(source)}${source.env ? `; set ${source.env}` : ''})`);
    }
    return { root: path.resolve(dir), revision: 'local', label: path.resolve(dir) };
  }

  return {
    fetch(source) {
      const key = JSON.stringify(source);
      if (!done.has(key)) {
        try {
          done.set(key, { value: source.type === 'dir' ? fetchDir(source) : fetchNow(source) });
        } catch (err) {
          done.set(key, { error: err });
        }
      }
      const entry = done.get(key);
      if (entry.error) throw entry.error;
      return entry.value;
    },

    async warm(sources) {
      const queue = [];
      const seen = new Set();
      for (const source of sources) {
        const key = JSON.stringify(source);
        if (source.type === 'dir' || done.has(key) || seen.has(key)) continue;
        seen.add(key);
        queue.push([key, source]);
      }
      const worker = async () => {
        while (queue.length > 0) {
          const [key, source] = queue.shift();
          const target = gitTarget(source);
          try {
            const revision = target.hit ? headOf(target.final) : await fetchGitAsync(gitUrl(source, env), target.temp, source);
            const checkout = target.hit ? target.final : keep(target);
            done.set(key, { value: settle(source, checkout, revision) });
          } catch (err) {
            discard(target);
            done.set(key, { error: failure(source, err) });
          }
        }
      };
      await Promise.all(Array.from({ length: Math.min(4, queue.length) }, worker));
    },

    close() {
      for (const temp of temps.splice(0)) fs.rmSync(temp, { recursive: true, force: true });
    },
  };

  function fetchNow(source) {
    const target = gitTarget(source);
    let revision;
    try {
      revision = target.hit ? headOf(target.final) : fetchGitSync(gitUrl(source, env), target.temp, source);
    } catch (err) {
      discard(target);
      throw failure(source, err);
    }
    return settle(source, target.hit ? target.final : keep(target), revision);
  }
}
