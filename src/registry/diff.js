'use strict';

/**
 * diff.js — normalized semantic diff between two attributed host registries,
 * with a safe/review classification. Description-only changes and safe
 * additions are classified safe; path, removal, global, detection, platform,
 * alias, universal, and source changes are classified review
 * (authority-sensitive).
 */

import { validateHost } from './validate.js';
import { compareIds } from './normalize.js';

/** Canonical destination shape used for comparison (drops raw text noise). */
function canonicalDestination(dest) {
  if (!dest) return dest;
  switch (dest.kind) {
    case 'literal':
      return { kind: 'literal', path: dest.path };
    case 'join':
      return { kind: 'join', base: dest.base, segments: dest.segments };
    case 'conditional':
      return {
        kind: 'conditional',
        base: dest.base,
        cases: dest.cases.map((c) => ({ probe: c.probe, formula: canonicalDestination(c.formula) })),
      };
    default:
      return { kind: dest.kind };
  }
}

const REVIEW_FIELDS = new Set([
  'name',
  'universal',
  'universalPrompt',
  'project',
  'global',
  'detection',
  'platforms',
  'aliases',
]);

/**
 * Compare two hosts that share the same id.
 * Returns { kind, authority, fields } where kind is one of
 * 'description-change' | 'change', and fields lists each changed dimension.
 */
export function diffHost(prev, curr) {
  const fields = [];

  if (prev.name !== curr.name) fields.push('name');
  if (prev.displayName !== curr.displayName) fields.push('displayName');
  if (prev.universal !== curr.universal) fields.push('universal');
  if (prev.universalPrompt !== curr.universalPrompt) fields.push('universalPrompt');
  if (JSON.stringify(canonicalDestination(prev.destinations.project)) !==
      JSON.stringify(canonicalDestination(curr.destinations.project))) {
    fields.push('project');
  }
  if (JSON.stringify(canonicalDestination(prev.destinations.global)) !==
      JSON.stringify(canonicalDestination(curr.destinations.global))) {
    fields.push('global');
  }
  if (JSON.stringify(prev.detection && prev.detection.envVars) !==
      JSON.stringify(curr.detection && curr.detection.envVars)) {
    fields.push('detection');
  }
  if (JSON.stringify(prev.platforms) !== JSON.stringify(curr.platforms)) fields.push('platforms');
  if (JSON.stringify(prev.aliases) !== JSON.stringify(curr.aliases)) fields.push('aliases');

  const onlyDescription =
    fields.length > 0 && fields.every((f) => f === 'displayName');
  const authority = fields.some((f) => REVIEW_FIELDS.has(f)) ? 'review' : 'safe';
  const kind = onlyDescription ? 'description-change' : 'change';
  return { kind, authority, fields };
}

/** Is a host safe to add? Safe-add = the host passes validation. */
export function isSafeAddition(host) {
  return validateHost(host) === null;
}

/**
 * Compute the normalized diff between previous and current snapshots.
 * Returns { summary, changes } with changes sorted bytewise by id.
 */
export function diffSnapshots(previous, current) {
  const prevById = new Map((previous.hosts || []).map((h) => [h.id, h]));
  const currById = new Map((current.hosts || []).map((h) => [h.id, h]));
  const changes = [];

  for (const [id, curr] of currById) {
    const prev = prevById.get(id);
    if (!prev) {
      changes.push({
        id,
        kind: 'addition',
        authority: isSafeAddition(curr) ? 'safe' : 'review',
        previous: null,
        current: curr,
      });
    } else {
      const { kind, authority, fields } = diffHost(prev, curr);
      if (fields.length > 0) {
        changes.push({ id, kind, authority, fields, previous: prev, current: curr });
      }
    }
  }

  for (const [id, prev] of prevById) {
    if (!currById.has(id)) {
      changes.push({
        id,
        kind: 'removal',
        authority: 'review',
        previous: prev,
        current: null,
      });
    }
  }

  // Source pin / schema metadata drift is authority-sensitive.
  const sourceDrift = JSON.stringify(previous.generatedFrom) !== JSON.stringify(current.generatedFrom);
  if (sourceDrift) {
    changes.push({
      id: '<source>',
      kind: 'source-change',
      authority: 'review',
      fields: ['generatedFrom'],
      previous: previous.generatedFrom,
      current: current.generatedFrom,
    });
  }

  changes.sort((a, b) => {
    const byId = compareIds(a.id, b.id);
    return byId !== 0 ? byId : a.kind < b.kind ? -1 : a.kind > b.kind ? 1 : 0;
  });

  const summary = {
    added: changes.filter((c) => c.kind === 'addition').length,
    removed: changes.filter((c) => c.kind === 'removal').length,
    changed: changes.filter((c) => c.kind !== 'addition' && c.kind !== 'removal' && c.kind !== 'source-change').length,
    safe: changes.filter((c) => c.authority === 'safe').length,
    review: changes.filter((c) => c.authority === 'review').length,
  };

  return { summary, changes };
}
