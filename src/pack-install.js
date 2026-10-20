import fs from 'node:fs';
import path from 'node:path';
import { acquireConcurrencyLock } from './transaction.js';
import { createSkillLink, pathExists, removeManagedPath } from './links.js';
import { UNIVERSAL_PROJECT_DESTINATION, resolveGlobalSkillPath, resolveSkillPath } from './destinations.js';
import { findSkillDirs, hashDirectory } from './pack-source.js';
import { assertSafeSkillId } from './paths.js';
import { ensureStateDir, getGlobalStateDir, getProjectStateDir } from './state.js';

/**
 * Install, update, remove and report skills that come from packs (Matt Pocock, Three.js,
 * HyperFrames, ...). The bundled Sigma skills keep their own engine in transaction.js.
 *
 * One skill is one copy in `.agents/skills/<id>`. Every other selected host folder links to
 * that copy (or holds its own copy with method `copy`). A private record in
 * `<state dir>/packs.json` says what this installer owns, so it never touches anything else.
 */

const STATE_FILE = 'packs.json';
const SCHEMA_VERSION = 1;

function context(params) {
  const scope = params.scope === 'global' ? 'global' : 'project';
  const base = path.resolve(scope === 'global' ? params.homeDir : (params.projectRoot || process.cwd()));
  const stateDir = scope === 'global'
    ? getGlobalStateDir(base, params.customStateDir)
    : getProjectStateDir(base, params.customStateDir);
  const resolve = (root, id) => (scope === 'global'
    ? resolveGlobalSkillPath(base, root, id)
    : resolveSkillPath(base, root, id));
  return { scope, base, stateDir, resolve, statePath: path.join(stateDir, STATE_FILE) };
}

export function loadPackState(params) {
  const { statePath } = context(params);
  let raw;
  try {
    raw = fs.readFileSync(statePath, 'utf8');
  } catch (err) {
    if (err.code === 'ENOENT') return { schemaVersion: SCHEMA_VERSION, skills: {} };
    throw err;
  }
  let state;
  try {
    state = JSON.parse(raw);
  } catch (err) {
    throw new Error(`failed to read pack state at ${statePath}: ${err.message}`);
  }
  if (state.schemaVersion > SCHEMA_VERSION) {
    throw new Error(`unsupported pack state schemaVersion ${state.schemaVersion}; this installer supports ${SCHEMA_VERSION}`);
  }
  return { schemaVersion: SCHEMA_VERSION, skills: state.skills || {} };
}

function savePackState(ctx, state) {
  ensureStateDir(ctx.stateDir);
  const temp = `${ctx.statePath}.${process.pid}.tmp`;
  fs.writeFileSync(temp, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
  fs.renameSync(temp, ctx.statePath);
}

function copySkill(from, to) {
  fs.cpSync(from, to, {
    recursive: true,
    dereference: true,
    filter: (src) => path.basename(src) !== '.git',
  });
}

function backupAway(ctx, id, target) {
  const dir = path.join(ctx.stateDir, 'pack-backups');
  fs.mkdirSync(dir, { recursive: true });
  const dest = path.join(dir, `${id}-${new Date().toISOString().replace(/[:.]/g, '-')}`);
  fs.cpSync(target, dest, { recursive: true, dereference: true });
  removeManagedPath(target);
  return dest;
}

function safeHash(dir) {
  try {
    return hashDirectory(dir);
  } catch {
    return null;
  }
}

/**
 * Install or refresh skills from packs.
 *
 * Result status per skill: `installed`, `updated`, `current` (nothing changed), `edited`
 * (the installed copy has local edits; kept), `conflict` (a folder this installer does not own
 * is in the way; kept), `failed`. `--force` replaces an edited or conflicting folder after a
 * private backup. With `dryRun`, the statuses are what would happen and nothing is written.
 *
 * @param {object} params
 * @param {object[]} params.skills pack skills from resolveSelection()
 * @param {string[]} [params.roots] destination roots; the universal root is always included
 * @param {'link'|'copy'} [params.method]
 * @param {object} params.fetcher from createSourceFetcher()
 * @returns {{ results: object[] }}
 */
export function installPackSkills(params) {
  const ctx = context(params);
  const { skills, fetcher, dryRun = false, force = false, version = '', onProgress } = params;
  const method = params.method === 'copy' ? 'copy' : 'link';
  const roots = [...new Set([UNIVERSAL_PROJECT_DESTINATION, ...(params.roots || [])])];
  const hostRoots = roots.filter((root) => root !== UNIVERSAL_PROJECT_DESTINATION);

  for (const skill of skills) assertSafeSkillId(skill.id, 'pack skill');
  const release = dryRun ? () => {} : acquireConcurrencyLock(ctx.base, params.customStateDir);
  try {
    const state = loadPackState(params);
    const results = [];
    const indexes = new Map();
    for (const skill of skills) {
      const result = { id: skill.id, pack: skill.pack, status: 'failed', note: '', destinations: [] };
      results.push(result);
      onProgress?.({ phase: 'start', id: skill.id });
      try {
        let index = indexes.get(skill.source);
        if (!index) {
          const fetched = fetcher.fetch(skill.source);
          index = { ...fetched, dirs: findSkillDirs(fetched.root) };
          indexes.set(skill.source, index);
        }
        const sourceDir = index.dirs.get(skill.id);
        if (!sourceDir) throw new Error(`not found in ${index.label}`);
        applySkill({ ctx, state, skill, sourceDir, index, result, hostRoots, method, dryRun, force, version });
      } catch (err) {
        result.status = 'failed';
        result.note = err.message;
      }
      onProgress?.({ phase: 'done', id: skill.id, result });
    }
    return { results };
  } finally {
    release();
  }
}

function applySkill({ ctx, state, skill, sourceDir, index, result, hostRoots, method, dryRun, force, version }) {
  const record = state.skills[skill.id];
  const canonical = ctx.resolve(UNIVERSAL_PROJECT_DESTINATION, skill.id);
  const newHash = hashDirectory(sourceDir);
  const present = pathExists(canonical.destination);
  const currentHash = present ? safeHash(canonical.destination) : null;
  result.revision = index.revision;
  result.destinations.push({ root: UNIVERSAL_PROJECT_DESTINATION, relativeDestination: canonical.relativeDestination, destination: canonical.destination, method: 'copy' });

  let kind;
  if (!present) kind = 'installed';
  else if (record && record.hash === currentHash) kind = record.hash === newHash ? 'current' : 'updated';
  else if (record) kind = 'edited';
  else kind = currentHash === newHash ? 'adopt' : 'conflict';

  if ((kind === 'edited' || kind === 'conflict') && !force) {
    result.status = kind;
    result.note = kind === 'edited'
      ? 'local edits found; kept (use --force to replace after a backup)'
      : 'a folder Sigma does not manage is in the way; kept (use --force to replace after a backup)';
    return;
  }

  const wantRoots = hostRoots.map((root) => ({ root, ...ctx.resolve(root, skill.id) }));
  for (const host of wantRoots) {
    result.destinations.push({ root: host.root, relativeDestination: host.relativeDestination, destination: host.destination, method });
  }

  const recordedRoots = new Set((record?.roots || []));
  const hostBlocked = wantRoots.filter((host) => pathExists(host.destination) && !recordedRoots.has(host.root) && !isCurrentLink(host.destination, canonical.destination));
  if (hostBlocked.length > 0 && !force) {
    result.status = 'conflict';
    result.note = `${hostBlocked[0].relativeDestination} exists and is not managed by Sigma; kept (use --force to replace after a backup)`;
    return;
  }

  const hostsOk = wantRoots.every((host) => hostInPlace(host.destination, canonical.destination, method));
  if (kind === 'current' && hostsOk && sameRoots(record, wantRoots)) {
    result.status = 'current';
    return;
  }
  result.status = kind === 'adopt' ? 'installed' : ['conflict', 'edited', 'current'].includes(kind) ? 'updated' : kind;
  if (dryRun) return;

  const staging = `${canonical.destination}.sigma-new-${process.pid}`;
  removeManagedPath(staging);
  fs.mkdirSync(path.dirname(canonical.destination), { recursive: true });
  try {
    copySkill(sourceDir, staging);
    if (present) {
      if (kind === 'edited' || kind === 'conflict') result.backup = backupAway(ctx, skill.id, canonical.destination);
      else removeManagedPath(canonical.destination);
    }
    fs.renameSync(staging, canonical.destination);
  } catch (err) {
    removeManagedPath(staging);
    throw err;
  }

  // Roots a past run recorded but this run no longer wants are removed with the old links.
  for (const old of recordedRoots) {
    if (old === UNIVERSAL_PROJECT_DESTINATION || wantRoots.some((host) => host.root === old)) continue;
    removeManagedPath(ctx.resolve(old, skill.id).destination);
  }
  for (const host of wantRoots) {
    if (pathExists(host.destination)) {
      if (!recordedRoots.has(host.root) && !isCurrentLink(host.destination, canonical.destination)) {
        result.backup = backupAway(ctx, `${skill.id}-${host.root.replace(/[\\/.]/g, '_')}`, host.destination);
      } else {
        removeManagedPath(host.destination);
      }
    }
    if (method === 'link') {
      try {
        createSkillLink(host.destination, canonical.destination, ctx.base);
      } catch (err) {
        err.message = `${err.message}. The method did not change; re-run with --copy for a full copy there.`;
        throw err;
      }
    } else {
      copySkill(canonical.destination, host.destination);
    }
  }

  state.skills[skill.id] = {
    pack: skill.pack,
    source: index.label,
    revision: index.revision,
    hash: newHash,
    method,
    roots: wantRoots.map((host) => host.root),
    installedAt: record?.installedAt || new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    installer: version,
  };
  savePackState(ctx, state);
}

function isCurrentLink(destination, canonical) {
  try {
    return fs.lstatSync(destination).isSymbolicLink() && fs.realpathSync(destination) === fs.realpathSync(canonical);
  } catch {
    return false;
  }
}

function hostInPlace(destination, canonical, method) {
  if (!pathExists(destination)) return false;
  return method === 'link' ? isCurrentLink(destination, canonical) : !fs.lstatSync(destination).isSymbolicLink();
}

function sameRoots(record, wantRoots) {
  const have = [...(record?.roots || [])].sort().join('|');
  return have === wantRoots.map((host) => host.root).sort().join('|');
}

/**
 * Bring recorded pack skills to the newest source. Same rules as install: edited copies stay
 * unless `force`. A skill whose pack no longer lists it is reported as `retired` and kept.
 */
export function updatePackSkills(params) {
  const state = loadPackState(params);
  const ids = (params.skillIds?.length ? params.skillIds : Object.keys(state.skills)).filter((id) => state.skills[id]);
  const results = [];
  const groups = new Map();
  for (const id of ids) {
    const skill = params.packCatalog.skills.get(id);
    if (!skill || skill.kind !== 'external') {
      results.push({ id, pack: state.skills[id].pack, status: 'retired', note: 'no longer in any pack; kept', destinations: [] });
      continue;
    }
    const record = state.skills[id];
    const key = `${record.method}|${(record.roots || []).join(',')}`;
    if (!groups.has(key)) groups.set(key, { method: record.method, roots: record.roots || [], skills: [] });
    groups.get(key).skills.push(skill);
  }
  for (const group of groups.values()) {
    results.push(...installPackSkills({ ...params, skills: group.skills, roots: group.roots, method: group.method }).results);
  }
  return { results };
}

/**
 * Remove recorded pack skills and every destination this installer made for them. A copy with
 * local edits stays unless `force`, which saves it to the private backup folder first.
 */
export function uninstallPackSkills(params) {
  const ctx = context(params);
  const { dryRun = false, force = false } = params;
  const release = dryRun ? () => {} : acquireConcurrencyLock(ctx.base, params.customStateDir);
  try {
    const state = loadPackState(params);
    const ids = params.all ? Object.keys(state.skills) : (params.skillIds || []);
    const results = [];
    for (const id of ids) {
      const record = state.skills[id];
      if (!record) {
        results.push({ id, pack: '', status: 'not-installed', note: '', destinations: [] });
        continue;
      }
      const canonical = ctx.resolve(UNIVERSAL_PROJECT_DESTINATION, id);
      const edited = pathExists(canonical.destination) && safeHash(canonical.destination) !== record.hash;
      const destinations = [canonical, ...(record.roots || []).map((root) => ctx.resolve(root, id))]
        .map((dest) => ({ relativeDestination: dest.relativeDestination, destination: dest.destination }));
      if (edited && !force) {
        results.push({ id, pack: record.pack, status: 'edited', note: 'local edits found; kept (use --force to back up and remove)', destinations });
        continue;
      }
      const result = { id, pack: record.pack, status: 'removed', note: '', destinations };
      if (!dryRun) {
        if (edited) result.backup = backupAway(ctx, id, canonical.destination);
        for (const root of [...(record.roots || []), UNIVERSAL_PROJECT_DESTINATION]) {
          const target = ctx.resolve(root, id).destination;
          if (root === UNIVERSAL_PROJECT_DESTINATION || pathExists(target)) removeManagedPath(target);
        }
        delete state.skills[id];
        savePackState(ctx, state);
      }
      results.push(result);
    }
    return { results };
  } finally {
    release();
  }
}

/** Read-only report of recorded pack skills: present, edited or missing. */
export function packStatus(params) {
  const ctx = context(params);
  const state = loadPackState(params);
  return Object.entries(state.skills).map(([id, record]) => {
    const canonical = ctx.resolve(UNIVERSAL_PROJECT_DESTINATION, id);
    const exists = pathExists(canonical.destination);
    const edited = exists && safeHash(canonical.destination) !== record.hash;
    return {
      id,
      pack: record.pack,
      source: record.source,
      revision: record.revision,
      method: record.method,
      roots: record.roots || [],
      path: canonical.destination,
      state: !exists ? 'missing' : edited ? 'edited' : 'clean',
    };
  });
}
