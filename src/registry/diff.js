'use strict';

/**
 * diff.js — normalized semantic diff between two attributed host registries,
 * with a safe/review classification. Description-only changes and safe
 * additions are classified safe; path, removal, global, detection, platform,
 * and alias changes are classified review (authority-sensitive).
 */

import { validateHost } from './validate.js';

const REVIEW_FIELDS = new Set([
  'project',
  'global',
  'removal',
  'detection',
  'platforms',
  'aliases',
]);

/** Compare two hosts that share the same id. Returns { fields, authority }. */
export function diffHost(prev, curr) {
  const fields = [];

  if (prev.displayName !== curr.displayName) fields.push('displayName');
  if (JSON.stringify(prev.destinations.project) !== JSON.stringify(curr.destinations.project)) {
    fields.push('project');
  }
  if (JSON.stringify(prev.destinations.global) !== JSON.stringify(curr.destinations.global)) {
    fields.push('global');
  }
  if (JSON.stringify(prev.detection && prev.detection.envVars) !==
      JSON.stringify(curr.detection && curr.detection.envVars)) {
    fields.push('detection');
  }
  if (JSON.stringify(prev.platforms) !== JSON.stringify(curr.platforms)) fields.push('platforms');
  if (JSON.stringify(prev.aliases) !== JSON.stringify(curr.aliases)) fields.push('aliases');

  const authority = fields.some((f) => REVIEW_FIELDS.has(f)) ? 'review' : 'safe';
  return { fields, authority };
}

/** Is a host safe to add? Safe-add = the host passes validation. */
export function isSafeAddition(host) {
  return validateHost(host) === null;
}

/**
 * Compute the normalized diff between previous and current snapshots.
 * Returns { summary, changes }.
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
      const { fields, authority } = diffHost(prev, curr);
      if (fields.length > 0) {
        changes.push({
          id,
          kind: 'change',
          authority,
          fields,
          previous: prev,
          current: curr,
        });
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

  changes.sort((a, b) => a.id.localeCompare(b.id));

  const summary = {
    added: changes.filter((c) => c.kind === 'addition').length,
    removed: changes.filter((c) => c.kind === 'removal').length,
    changed: changes.filter((c) => c.kind === 'change').length,
    safe: changes.filter((c) => c.authority === 'safe').length,
    review: changes.filter((c) => c.authority === 'review').length,
  };

  return { summary, changes };
}
