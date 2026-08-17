import fs from 'node:fs';
import path from 'node:path';
import { findPackageRoot } from './catalog.js';
import { inspectManagedPath, pathExists } from './links.js';

export const UNIVERSAL_PROJECT_DESTINATION = '.agents/skills';

/**
 * Load the bundled Agent Host registry snapshot.
 *
 * @param {string} [packageRoot]
 * @returns {object}
 */
export function loadHostRegistry(packageRoot = findPackageRoot()) {
  const snapshotPath = path.join(packageRoot, 'registry', 'agent-hosts.json');
  if (!fs.existsSync(snapshotPath)) {
    throw new Error(`missing Agent Host registry at ${snapshotPath}`);
  }
  let snapshot;
  try {
    snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf8'));
  } catch (err) {
    throw new Error(`failed to read Agent Host registry at ${snapshotPath}: ${err.message}`);
  }
  if (!snapshot || !Array.isArray(snapshot.hosts)) {
    throw new Error('registry hosts must be an array');
  }
  return snapshot;
}

/**
 * Normalize a project-relative destination root to posix form without a trailing slash.
 *
 * @param {string} relativeRoot
 * @returns {string}
 */
export function normalizeRelativeRoot(relativeRoot) {
  return String(relativeRoot || '')
    .replace(/\\/g, '/')
    .replace(/^\.\//, '')
    .replace(/\/+$/, '');
}

/**
 * Whether a host is labeled detected from environment metadata.
 * Detection never selects destinations.
 *
 * @param {object} host
 * @param {NodeJS.ProcessEnv} [env]
 * @returns {boolean}
 */
export function detectHost(host, env = process.env) {
  const envVars = host?.detection?.envVars;
  if (!Array.isArray(envVars) || envVars.length === 0) return false;
  return envVars.some((name) => {
    const value = env[name];
    return value !== undefined && value !== '';
  });
}

function expandProjectRelativeRoot(formula) {
  if (!formula || formula.kind === 'none') return null;
  if (formula.kind !== 'literal' || typeof formula.path !== 'string') return null;
  const relativeRoot = normalizeRelativeRoot(formula.path);
  if (!relativeRoot) return null;
  return relativeRoot;
}

function compareIds(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

function compareRoots(a, b) {
  if (a === UNIVERSAL_PROJECT_DESTINATION && b !== UNIVERSAL_PROJECT_DESTINATION) return -1;
  if (b === UNIVERSAL_PROJECT_DESTINATION && a !== UNIVERSAL_PROJECT_DESTINATION) return 1;
  return compareIds(a, b);
}

/**
 * Group every Agent Host by its Project Installation destination.
 * Hosts without a project destination still appear under a non-selectable group.
 *
 * @param {object} params
 * @param {object} params.registry
 * @param {string} params.projectRoot
 * @param {NodeJS.ProcessEnv} [params.env]
 * @returns {object[]}
 */
export function listProjectDestinationGroups({ registry, projectRoot, env = process.env }) {
  const resolvedProjectRoot = path.resolve(projectRoot);
  const grouped = new Map();

  for (const host of registry.hosts || []) {
    const relativeRoot = expandProjectRelativeRoot(host.destinations?.project);
    const key = relativeRoot || `__none__:${host.id}`;
    if (!grouped.has(key)) {
      const universal = relativeRoot === UNIVERSAL_PROJECT_DESTINATION;
      grouped.set(key, {
        key,
        relativeRoot: relativeRoot || '',
        absoluteRoot: relativeRoot ? path.resolve(resolvedProjectRoot, ...relativeRoot.split('/')) : '',
        universal,
        selectedByDefault: universal,
        selectable: Boolean(relativeRoot),
        hosts: [],
      });
    }
    grouped.get(key).hosts.push({
      id: host.id,
      name: host.name,
      displayName: host.displayName,
      aliases: [...(host.aliases || [])],
      detected: detectHost(host, env),
      relativeRoot: relativeRoot || '',
    });
  }

  const groups = [...grouped.values()].sort((a, b) => compareRoots(a.relativeRoot || a.key, b.relativeRoot || b.key));
  for (const group of groups) {
    group.hosts.sort((a, b) => compareIds(a.id, b.id));
  }
  return groups;
}

/**
 * Default selected destination roots: only the universal `.agents/skills` path.
 *
 * @param {object[]} groups
 * @returns {string[]}
 */
export function defaultSelectedRoots(groups) {
  return groups.filter((group) => group.selectedByDefault).map((group) => group.relativeRoot);
}

/**
 * Search all hosts by id, display name, name, or alias. Detection does not hide hosts.
 *
 * @param {object[]} groups
 * @param {string} query
 * @returns {object[]}
 */
export function searchHosts(groups, query) {
  const needle = String(query || '').trim().toLowerCase();
  const hosts = groups.flatMap((group) => group.hosts.map((host) => ({ ...host, group })));
  if (!needle) return hosts;
  return hosts.filter((host) => {
    const haystacks = [host.id, host.name, host.displayName, ...(host.aliases || [])];
    return haystacks.some((value) => String(value || '').toLowerCase().includes(needle));
  });
}

function isInsideProject(projectRoot, absolutePath) {
  const relative = path.relative(path.resolve(projectRoot), path.resolve(absolutePath));
  return relative === '' || (relative && !relative.startsWith('..') && !path.isAbsolute(relative));
}

/**
 * Resolve one skill folder under a project destination root.
 *
 * @param {string} projectRoot
 * @param {string} relativeRoot
 * @param {string} skillId
 * @returns {{ destination: string, relativeDestination: string, relativeRoot: string }}
 */
export function resolveSkillPath(projectRoot, relativeRoot, skillId) {
  const normalizedRoot = normalizeRelativeRoot(relativeRoot);
  if (!normalizedRoot || normalizedRoot.split('/').some((segment) => segment === '..')) {
    throw new Error(`invalid destination '${relativeRoot}'`);
  }

  const destination = path.resolve(projectRoot, ...normalizedRoot.split('/'), skillId);
  if (!isInsideProject(projectRoot, destination)) {
    throw new Error(`invalid destination '${relativeRoot}': resolved path escapes the project`);
  }

  const relativeDestination = path.relative(path.resolve(projectRoot), destination).replace(/\\/g, '/');
  if (!relativeDestination || relativeDestination.startsWith('../')) {
    throw new Error(`invalid destination '${relativeRoot}'`);
  }

  return {
    destination,
    relativeDestination,
    relativeRoot: normalizedRoot,
  };
}

function normalizeAbs(absolutePath) {
  const resolved = path.resolve(absolutePath);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

function classifyPathPair(a, b) {
  const left = normalizeAbs(a);
  const right = normalizeAbs(b);
  if (left === right) return 'duplicate';
  const sep = path.sep;
  if (left.startsWith(right + sep) || right.startsWith(left + sep)) return 'overlap';
  return null;
}

/**
 * Fail-closed checks for selected Project Installation destinations.
 * Returns human-readable error strings; an empty array means the set is safe.
 *
 * @param {object} params
 * @returns {string[]}
 */
export function findDestinationConflicts({ projectRoot, skillIds, selectedRoots, isOwned }) {
  const errors = [];
  const normalizedRoots = selectedRoots.map((root) => normalizeRelativeRoot(root));
  const seenRoots = new Set();

  for (const root of normalizedRoots) {
    if (seenRoots.has(root)) {
      errors.push(`duplicate resolved destination '${root}'`);
    }
    seenRoots.add(root);
  }

  const resolved = [];
  for (const root of [...seenRoots]) {
    for (const skillId of skillIds) {
      let skillPath;
      try {
        skillPath = resolveSkillPath(projectRoot, root, skillId);
      } catch (err) {
        errors.push(err.message);
        continue;
      }
      resolved.push({ root, skillId, ...skillPath });
    }
  }

  for (let i = 0; i < resolved.length; i++) {
    for (let j = i + 1; j < resolved.length; j++) {
      const kind = classifyPathPair(resolved[i].destination, resolved[j].destination);
      if (kind === 'duplicate') {
        errors.push(
          `duplicate resolved destination '${resolved[i].relativeDestination}'`,
        );
      } else if (kind === 'overlap') {
        errors.push(
          `overlapping destinations '${resolved[i].relativeDestination}' and '${resolved[j].relativeDestination}'`,
        );
      }
    }
  }

  for (const item of resolved) {
    if (process.platform === 'win32' && item.destination.length >= 260) {
      errors.push(
        `Destination '${item.destination}' exceeds the Windows path length limit. Installation aborted.`,
      );
      continue;
    }
    if (!pathExists(item.destination)) continue;
    const expectedCanonical = resolveSkillPath(projectRoot, UNIVERSAL_PROJECT_DESTINATION, item.skillId);
    const inspected = inspectManagedPath(item.destination, expectedCanonical.destination);
    const owned = typeof isOwned === 'function'
      ? isOwned(item.skillId, item.destination)
      : false;
    if (inspected.broken) {
      errors.push(
        `Destination '${item.destination}' is a broken link. Installation aborted.`,
      );
      continue;
    }
    if (inspected.wrongTarget) {
      errors.push(
        `Destination '${item.destination}' is a wrong-target link. Installation aborted.`,
      );
      continue;
    }
    if (!owned) {
      errors.push(
        `Destination '${item.destination}' already exists and is not owned by SigmaSkills. Safe adoption is not enabled. Installation aborted.`,
      );
    }
  }

  return errors;
}
