import fs from 'node:fs';
import { UNIVERSAL_PROJECT_DESTINATION } from './destinations.js';
import { inspectManagedPath, pathExists, recommendedLinkMethod } from './links.js';
import { computeSkillRevisionAndHashes } from './revision.js';

export const RECOGNITION_PRECEDENCE = ['sigma-state', 'exact-revision', 'recognized-link'];

function hashRealDirectory(dirPath) {
  if (!pathExists(dirPath)) return null;
  const stat = fs.lstatSync(dirPath);
  if (stat.isSymbolicLink() || !stat.isDirectory()) return null;
  return computeSkillRevisionAndHashes(dirPath);
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
    bundledRevision,
    expectedCanonicalPath,
    sigmaOwned = false,
    sigmaRevision = null,
  } = params;

  if (!pathExists(destPath)) {
    return { kind: 'missing', adoptable: false, method: null };
  }

  const inspected = inspectManagedPath(destPath, expectedCanonicalPath);
  if (inspected.broken) {
    return { kind: 'broken-link', adoptable: false, method: inspected.method };
  }

  const isLink = fs.lstatSync(destPath).isSymbolicLink();

  if (sigmaOwned) {
    const hashed = isLink ? null : hashRealDirectory(destPath);
    return {
      kind: 'sigma-state',
      adoptable: true,
      method: inspected.method || 'copy',
      revision: sigmaRevision || hashed?.revision || null,
      files: hashed?.files,
      resolvedTarget: inspected.target || destPath,
    };
  }

  if (!isLink) {
    try {
      const hashed = hashRealDirectory(destPath);
      if (hashed && bundledRevision && hashed.revision === bundledRevision) {
        return {
          kind: 'exact-revision',
          adoptable: true,
          method: 'copy',
          revision: hashed.revision,
          files: hashed.files,
        };
      }
    } catch {
      return { kind: 'foreign', adoptable: false, method: 'copy' };
    }
    return { kind: 'foreign', adoptable: false, method: 'copy' };
  }

  let realPath;
  try {
    realPath = fs.realpathSync(destPath);
  } catch {
    return { kind: 'broken-link', adoptable: false, method: recommendedLinkMethod() };
  }

  let hashedTarget = null;
  try {
    hashedTarget = hashRealDirectory(realPath);
  } catch {
    hashedTarget = null;
  }
  const targetExact = Boolean(hashedTarget && bundledRevision && hashedTarget.revision === bundledRevision);
  if (!targetExact) {
    return {
      kind: inspected.wrongTarget ? 'wrong-target' : 'foreign',
      adoptable: false,
      method: recommendedLinkMethod(),
      resolvedTarget: realPath,
    };
  }

  return {
    kind: 'recognized-link',
    adoptable: true,
    method: recommendedLinkMethod(),
    revision: hashedTarget.revision,
    resolvedTarget: realPath,
    dependsOn: expectedCanonicalPath || realPath,
  };
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

  const fateFor = (candidate) => {
    const kind = candidate.classification?.kind;
    if (!kind || kind === 'missing') return 'create';
    return 'keep';
  };

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
