'use strict';

/**
 * validate.js — validate an attributed host registry against the schema
 * contracts and safety rules. Rejects unsafe traversal, roots, control
 * characters, shell syntax, duplicate/case-colliding ids, invalid platform
 * data, and intra-host destination overlap (a host whose project and global
 * destinations resolve to the same path). Cross-host sharing of a skills
 * directory is legitimate and is not rejected. Returns { valid, errors }.
 */

const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;
const SHELL_SYNTAX = /[`$;|&<>()"'\\]/;
const TRAVERSAL_SEGMENT = /^(\.\.|\.\.\.)$/;
const ABSOLUTE_PREFIX = /^([/\\~%]|[A-Za-z]:)/;

/**
 * Assert a relative path fragment is safe. Fragments may contain '/' path
 * separators (they join onto a base home dir), but must not be absolute,
 * must not escape via traversal segments, and must not contain control
 * characters or shell syntax.
 */
export function assertSafePath(path, where) {
  if (typeof path !== 'string' || path.length === 0) {
    return `${where}: empty destination path`;
  }
  if (CONTROL_CHARS.test(path)) {
    return `${where}: control character in destination path ${JSON.stringify(path)}`;
  }
  if (SHELL_SYNTAX.test(path)) {
    return `${where}: shell syntax in destination path ${JSON.stringify(path)}`;
  }
  if (ABSOLUTE_PREFIX.test(path)) {
    return `${where}: absolute/root destination path ${JSON.stringify(path)}`;
  }
  for (const segment of path.split('/')) {
    if (TRAVERSAL_SEGMENT.test(segment)) {
      return `${where}: traversal segment in destination path ${JSON.stringify(path)}`;
    }
  }
  return null;
}

const BASE_IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

/** Validate one host record. Returns an error string or null. */
export function validateHost(host) {
  if (typeof host.id !== 'string' || host.id.length === 0) {
    return 'host id is missing or empty';
  }
  if (CONTROL_CHARS.test(host.id)) {
    return `host id contains control characters (${JSON.stringify(host.id)})`;
  }
  if (typeof host.displayName !== 'string' || host.displayName.length === 0) {
    return `${host.id}: displayName is missing or empty`;
  }
  if (CONTROL_CHARS.test(host.displayName)) {
    return `${host.id}: displayName contains control characters`;
  }
  const d = host.destinations;
  if (!d || typeof d !== 'object') {
    return `${host.id}: destinations are missing`;
  }
  const projectErr = validateDestination(d.project, `${host.id}.destinations.project`, true);
  if (projectErr) return projectErr;
  const globalErr = validateDestination(d.global, `${host.id}.destinations.global`, false);
  if (globalErr) return globalErr;
  const projectKey = destinationKey(d.project);
  const globalKey = destinationKey(d.global);
  if (projectKey && projectKey === globalKey) {
    return `${host.id}: project and global destinations overlap (both resolve to ${projectKey})`;
  }
  if (!Array.isArray(host.aliases)) return `${host.id}: aliases must be an array`;
  if (!Array.isArray(host.platforms)) return `${host.id}: platforms must be an array`;
  for (const platform of host.platforms) {
    if (typeof platform !== 'string' || platform.length === 0 || CONTROL_CHARS.test(platform)) {
      return `${host.id}: invalid platform declaration ${JSON.stringify(platform)}`;
    }
  }
  const envVars = host.detection && host.detection.envVars;
  if (!Array.isArray(envVars)) return `${host.id}: detection.envVars must be an array`;
  return null;
}

/** Validate one destination formula record. */
export function validateDestination(dest, where, requirePresent) {
  if (!dest) {
    return requirePresent ? `${where}: destination is missing` : null;
  }
  switch (dest.kind) {
    case 'none':
      return null;
    case 'literal':
      return assertSafePath(dest.path, where);
    case 'join':
      if (typeof dest.base !== 'string' || !BASE_IDENTIFIER.test(dest.base)) {
        return `${where}: join base is not an env-var identifier (${JSON.stringify(dest.base)})`;
      }
      if (!Array.isArray(dest.segments) || dest.segments.length === 0) {
        return `${where}: join has no path segments`;
      }
      for (const segment of dest.segments) {
        const err = assertSafePath(segment, where);
        if (err) return err;
      }
      return null;
    case 'conditional':
      if (!Array.isArray(dest.cases) || dest.cases.length === 0) {
        return `${where}: conditional has no cases`;
      }
      for (const entry of dest.cases) {
        const err = validateDestination(entry.formula, `${where}.case(${JSON.stringify(entry.probe)})`, true);
        if (err) return err;
      }
      return null;
    case 'function':
      return `${where}: destination requires evaluation (function ${JSON.stringify(dest.name)})`;
    case 'unknown':
      return `${where}: destination formula is not parseable (${JSON.stringify(dest.raw)})`;
    default:
      return `${where}: unknown destination kind ${JSON.stringify(dest.kind)}`;
  }
}

/** Resolve a destination to a canonical path key for overlap checks. */
export function destinationKey(dest) {
  if (!dest) return '';
  switch (dest.kind) {
    case 'literal':
      return 'project:' + dest.path;
    case 'join':
      return 'global:' + dest.base + ':' + dest.segments.join('/');
    case 'conditional':
      return 'conditional:' + JSON.stringify(dest.cases);
    case 'none':
      return '';
    default:
      return `${dest.kind}:${JSON.stringify(dest)}`;
  }
}

/**
 * Validate a full snapshot. Returns { valid, errors } where errors are
 * schema-level and cross-host problems; host-level errors are collected
 * under hostErrors.
 */
export function validateSnapshot(snapshot) {
  const errors = [];
  const hostErrors = {};
  if (!snapshot || typeof snapshot !== 'object') {
    return { valid: false, errors: ['snapshot is missing'] };
  }
  if (snapshot.schemaVersion !== 1) {
    errors.push(`unsupported schemaVersion ${JSON.stringify(snapshot.schemaVersion)}`);
  }
  if (!Array.isArray(snapshot.hosts)) {
    errors.push('snapshot.hosts must be an array');
    return { valid: errors.length === 0, errors, hostErrors };
  }

  const byId = new Map();
  const byLower = new Map();

  for (const host of snapshot.hosts) {
    const err = validateHost(host);
    if (err) {
      hostErrors[host.id] = err;
      continue;
    }
    if (byId.has(host.id)) {
      errors.push(`duplicate host id ${JSON.stringify(host.id)}`);
      continue;
    }
    const lower = host.id.toLowerCase();
    if (byLower.has(lower) && byLower.get(lower) !== host.id) {
      errors.push(`case-colliding host ids ${JSON.stringify(byLower.get(lower))} and ${JSON.stringify(host.id)}`);
    }
    byId.set(host.id, host);
    byLower.set(lower, host.id);
  }

  const valid = errors.length === 0 && Object.keys(hostErrors).length === 0;
  return { valid, errors, hostErrors };
}
