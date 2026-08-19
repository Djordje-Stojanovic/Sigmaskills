'use strict';

/**
 * normalize.js — turn parsed upstream host records into the canonical,
 * versioned, attributed registry snapshot consumed by the installer.
 *
 * Only declarative data survives normalization. Detection function bodies
 * are reduced to env-var metadata; destination formulas are kept as safe
 * declarative records (kind: literal | join | conditional | none). Nothing
 * is evaluated. Hosts are sorted bytewise by id so the emitted JSON is
 * reproducible regardless of host locale or ICU settings.
 */

/**
 * Bytewise (code-point) id comparator, locale-independent. Guarantees the
 * snapshot ordering is identical on every machine and Node build.
 */
export function compareIds(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Normalize a parsed host record into a canonical registry entry.
 * Adds attribution (upstream file + line) and a stable normalized shape.
 */
export function normalizeHost(host, source) {
  return {
    id: host.id,
    name: host.name,
    displayName: host.displayName,
    universal: host.universal,
    universalPrompt: host.universalPrompt,
    destinations: {
      project: host.project ?? { kind: 'none', raw: undefined },
      global: host.global ?? { kind: 'none', raw: undefined },
    },
    aliases: host.aliases ?? [],
    platforms: host.platforms ?? [],
    detection: {
      envVars: host.envVars ?? [],
    },
    attribution: {
      upstreamFile: source.upstreamFile ?? source.file,
      upstreamLine: host.line,
    },
  };
}

/**
 * Build the canonical snapshot container.
 * @param {Array} hosts  normalized host records
 * @param {object} source pin record { repository, pinnedRevision, upstreamFile, fetchedAt? }
 */
export function buildSnapshot(hosts, source) {
  const sorted = [...hosts].sort((a, b) => compareIds(a.id, b.id));
  const generatedFrom = {
    repository: source.repository,
    pinnedRevision: source.pinnedRevision ?? source.revision,
    upstreamFile: source.upstreamFile ?? source.file,
  };
  if (source.fetchedAt) generatedFrom.fetchedAt = source.fetchedAt;
  return {
    schemaVersion: 1,
    generatedFrom,
    hosts: sorted,
  };
}
