import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const SKIP_DIRS = new Set(['node_modules', '.git']);

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
 * One fetcher per command. It fetches each source once, however many skills come from it, and
 * removes every temporary clone in close().
 *
 * A source is `{ type: 'git', repo, path, ref? }` or `{ type: 'dir', path | env, prefix }`. A git
 * source with a `ref` (a release tag) is fetched at that tag, so a moved head cannot change it.
 * `fetch(source)` returns `{ root, revision, label }`, where `root` holds the skill folders.
 *
 * @param {object} [options]
 * @param {NodeJS.ProcessEnv} [options.env]
 * @param {(url: string, dest: string, ref?: string) => string} [options.clone] swap the git adapter in tests
 * @returns {{ fetch: Function, close: Function }}
 */
export function createSourceFetcher({ env = process.env, clone = defaultClone } = {}) {
  const cache = new Map();
  const temps = [];
  return {
    fetch(source) {
      const key = JSON.stringify(source);
      if (cache.has(key)) return cache.get(key);
      let result;
      if (source.type === 'dir') {
        const dir = source.path || (source.env ? env[source.env] : '');
        if (!dir || !fs.existsSync(dir)) {
          throw new Error(`source folder not found (${describeSource(source)}${source.env ? `; set ${source.env}` : ''})`);
        }
        result = { root: path.resolve(dir), revision: 'local', label: path.resolve(dir) };
      } else {
        const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'sigmaskills-src-'));
        temps.push(temp);
        let revision;
        try {
          revision = clone(gitUrl(source, env), temp, source.ref);
        } catch (err) {
          throw new Error(`could not fetch ${describeSource(source)}: ${String(err.message || err).split('\n')[0]}`);
        }
        result = { root: path.join(temp, source.path || ''), revision, label: source.repo || source.url };
      }
      cache.set(key, result);
      return result;
    },
    close() {
      for (const temp of temps.splice(0)) fs.rmSync(temp, { recursive: true, force: true });
    },
  };
}

function defaultClone(url, dest, ref) {
  const opts = { stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', windowsHide: true };
  const branch = ref ? ['--branch', ref] : [];
  execFileSync('git', ['-c', 'advice.detachedHead=false', 'clone', '--depth', '1', '--quiet', ...branch, url, dest], opts);
  return execFileSync('git', ['-C', dest, 'rev-parse', 'HEAD'], opts).trim();
}
