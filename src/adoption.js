import fs from 'node:fs';
import path from 'node:path';
import { parseSkillFrontmatter, findPackageRoot } from './catalog.js';
import { inspectCustomizationBlock } from './customization.js';
import { UNIVERSAL_PROJECT_DESTINATION } from './destinations.js';
import { inspectManagedPath, pathExists, recommendedLinkMethod } from './links.js';
import { computeSkillRevisionAndHashes } from './revision.js';

export const RECOGNITION_PRECEDENCE = ['sigma-state', 'exact-revision', 'recognized-link'];
export const MIGRATABLE_KINDS = ['legacy', 'changed', 'unverified', 'malformed-custom'];
export const BASELINES_FILENAME = 'skill-baselines.json';

function hashRealDirectory(dirPath) {
  if (!pathExists(dirPath)) return null;
  const stat = fs.lstatSync(dirPath);
  if (stat.isSymbolicLink() || !stat.isDirectory()) return null;
  return computeSkillRevisionAndHashes(dirPath);
}

/**
 * Compare live file hashes with an upstream or baseline map.
 *
 * @param {Record<string, string>} liveFiles
 * @param {Record<string, string>} upstreamFiles
 * @returns {{ added: string[], replaced: string[], deleted: string[] }}
 */
export function diffSkillFiles(liveFiles = {}, upstreamFiles = {}) {
  const added = [];
  const replaced = [];
  const deleted = [];

  for (const file of Object.keys(liveFiles).sort()) {
    if (!(file in upstreamFiles)) added.push(file);
    else if (liveFiles[file] !== upstreamFiles[file]) replaced.push(file);
  }
  for (const file of Object.keys(upstreamFiles).sort()) {
    if (!(file in liveFiles)) deleted.push(file);
  }

  return { added, replaced, deleted };
}

/**
 * Load explicit historical Skill Revision baselines bundled with the package.
 *
 * @param {string} [packageRoot]
 * @returns {Record<string, { revision: string, files?: Record<string, string> }[]>}
 */
export function loadSkillBaselines(packageRoot = findPackageRoot()) {
  const baselinePath = path.join(packageRoot, 'registry', BASELINES_FILENAME);
  if (!pathExists(baselinePath)) return {};
  const parsed = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  if (!parsed || typeof parsed !== 'object' || !parsed.skills || typeof parsed.skills !== 'object') {
    throw new Error(`invalid skill baselines at ${baselinePath}`);
  }
  return parsed.skills;
}

function inspectLiveSkill(destPath, skillId) {
  const skillMdPath = path.join(destPath, 'SKILL.md');
  if (!pathExists(skillMdPath)) {
    return { sigmaLooking: false, customization: { status: 'absent' } };
  }

  let markdown;
  try {
    markdown = fs.readFileSync(skillMdPath, 'utf8');
  } catch {
    return { sigmaLooking: false, customization: { status: 'absent' } };
  }

  let name = null;
  try {
    name = parseSkillFrontmatter(markdown).name;
  } catch {
    name = null;
  }

  return {
    sigmaLooking: Boolean(skillId && name === skillId),
    customization: inspectCustomizationBlock(markdown, skillId || 'skill'),
  };
}

function findBaseline(hashed, bundledBaselines = []) {
  if (!hashed) return null;
  return bundledBaselines.find((baseline) => baseline && baseline.revision === hashed.revision) || null;
}

function sigmaLookingMigration(params) {
  const {
    hashed,
    live,
    bundledFiles,
    bundledBaselines,
    owned,
    extra = {},
  } = params;
  const vsUpstream = diffSkillFiles(hashed?.files || {}, bundledFiles);
  const baseline = findBaseline(hashed, bundledBaselines);
  const customization = live.customization;

  if ((owned || live.sigmaLooking) && customization?.status === 'malformed') {
    return classified({
      kind: 'malformed-custom',
      migratable: true,
      confidence: owned ? 'high' : 'low',
      revision: hashed?.revision,
      files: hashed?.files,
      diff: vsUpstream,
      customization,
      ...extra,
    });
  }

  if (baseline) {
    return classified({
      kind: 'legacy',
      migratable: true,
      confidence: 'high',
      revision: hashed.revision,
      files: hashed.files,
      baselineRevision: baseline.revision,
      diff: vsUpstream,
      customization,
      ...extra,
    });
  }

  if (owned) {
    return classified({
      kind: 'changed',
      migratable: true,
      confidence: 'high',
      revision: hashed?.revision,
      files: hashed?.files,
      diff: vsUpstream,
      customization,
      ...extra,
    });
  }

  if (live.sigmaLooking) {
    return classified({
      kind: 'unverified',
      migratable: true,
      confidence: 'low',
      revision: hashed?.revision,
      files: hashed?.files,
      diff: vsUpstream,
      customization,
      ...extra,
    });
  }

  return null;
}

function classified(fields) {
  return {
    adoptable: false,
    migratable: false,
    confidence: 'none',
    method: 'copy',
    ...fields,
  };
}

/**
 * Classify one on-disk skill path. Scope-neutral: callers supply ownership and
 * the bundled Skill Revision. Global Installation can reuse this without a project root.
 *
 * @param {object} params
 * @returns {object}
 */
export function classifySkillPath(params) {
  const {
    destPath,
    skillId = null,
    bundledRevision,
    bundledFiles = {},
    bundledBaselines = [],
    expectedCanonicalPath,
    sigmaOwned = false,
    sigmaRevision = null,
    baseHashes = null,
  } = params;

  if (!pathExists(destPath)) {
    return classified({ kind: 'missing', method: null });
  }

  const inspected = inspectManagedPath(destPath, expectedCanonicalPath);
  if (inspected.broken) {
    return classified({ kind: 'broken-link', method: inspected.method });
  }

  const isLink = fs.lstatSync(destPath).isSymbolicLink();
  const live = isLink ? inspectLiveSkill(inspected.target || destPath, skillId) : inspectLiveSkill(destPath, skillId);

  if (sigmaOwned && isLink) {
    return classified({
      kind: 'sigma-state',
      adoptable: true,
      confidence: 'high',
      method: inspected.method || recommendedLinkMethod(),
      revision: sigmaRevision || null,
      resolvedTarget: inspected.target || destPath,
      customization: live.customization,
    });
  }

  if (sigmaOwned && !isLink) {
    const hashed = hashRealDirectory(destPath);
    if (hashed && bundledRevision && hashed.revision === bundledRevision) {
      return classified({
        kind: 'sigma-state',
        adoptable: true,
        confidence: 'high',
        method: 'copy',
        revision: hashed.revision,
        files: hashed.files,
        resolvedTarget: destPath,
        customization: live.customization,
      });
    }

    const migrated = sigmaLookingMigration({
      hashed,
      live,
      bundledFiles,
      bundledBaselines,
      owned: true,
      extra: { revision: hashed?.revision || sigmaRevision },
    });
    return migrated || classified({
      kind: 'changed',
      migratable: true,
      confidence: 'high',
      revision: hashed?.revision || sigmaRevision,
      files: hashed?.files,
      diff: diffSkillFiles(hashed?.files || {}, bundledFiles),
      customization: live.customization,
    });
  }

  if (!isLink) {
    let hashed = null;
    try {
      hashed = hashRealDirectory(destPath);
    } catch {
      return classified({ kind: 'foreign', customization: live.customization });
    }

    if (hashed && bundledRevision && hashed.revision === bundledRevision) {
      return classified({
        kind: 'exact-revision',
        adoptable: true,
        confidence: 'high',
        revision: hashed.revision,
        files: hashed.files,
        customization: live.customization,
      });
    }

    const migrated = sigmaLookingMigration({
      hashed,
      live,
      bundledFiles,
      bundledBaselines,
      owned: false,
    });
    if (migrated) return migrated;
    return classified({
      kind: 'foreign',
      customization: live.customization,
      diff: diffSkillFiles(hashed?.files || {}, bundledFiles),
    });
  }

  let realPath;
  try {
    realPath = fs.realpathSync(destPath);
  } catch {
    return classified({ kind: 'broken-link', method: recommendedLinkMethod() });
  }

  let hashedTarget = null;
  try {
    hashedTarget = hashRealDirectory(realPath);
  } catch {
    hashedTarget = null;
  }
  const targetExact = Boolean(hashedTarget && bundledRevision && hashedTarget.revision === bundledRevision);
  if (targetExact) {
    return classified({
      kind: 'recognized-link',
      adoptable: true,
      confidence: 'high',
      method: recommendedLinkMethod(),
      revision: hashedTarget.revision,
      resolvedTarget: realPath,
      dependsOn: expectedCanonicalPath || realPath,
      customization: live.customization,
    });
  }

  const targetLive = inspectLiveSkill(realPath, skillId);
  const migrated = sigmaLookingMigration({
    hashed: hashedTarget,
    live: targetLive,
    bundledFiles,
    bundledBaselines,
    owned: false,
    extra: {
      method: recommendedLinkMethod(),
      resolvedTarget: realPath,
    },
  });
  if (migrated) return migrated;

  return classified({
    kind: inspected.wrongTarget ? 'wrong-target' : 'foreign',
    method: recommendedLinkMethod(),
    resolvedTarget: realPath,
    customization: targetLive.customization,
  });
}

function fateFor(candidate) {
  const kind = candidate.classification?.kind;
  if (!kind || kind === 'missing') return 'create';
  if (candidate.resolution) return candidate.resolution;
  if (candidate.classification?.adoptable) return 'keep';
  if (candidate.classification?.migratable) return 'needs-resolution';
  return 'keep';
}

/**
 * Choose one canonical copy among recognized destinations and name the fate of every other copy.
 *
 * @param {object[]} candidates
 * @param {object} [options]
 * @returns {{ canonical: object, others: object[] }}
 */
export function chooseCanonical(candidates, options = {}) {
  const universalRoot = options.universalRelativeRoot || UNIVERSAL_PROJECT_DESTINATION;
  if (!Array.isArray(candidates) || candidates.length === 0) {
    throw new Error('chooseCanonical requires at least one destination candidate');
  }

  const preferred = candidates.find((candidate) => candidate.relativeRoot === universalRoot)
    || candidates[0];

  const canonical = {
    ...preferred,
    fate: fateFor(preferred),
    role: 'canonical',
  };

  const others = candidates
    .filter((candidate) => candidate.relativeDestination !== canonical.relativeDestination)
    .map((candidate) => ({
      ...candidate,
      fate: fateFor(candidate),
      role: candidate.relativeRoot === universalRoot ? 'canonical' : 'host',
    }));

  return { canonical, others };
}
