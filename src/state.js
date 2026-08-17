import fs from 'node:fs';
import path from 'node:path';
import { UNIVERSAL_PROJECT_DESTINATION } from './destinations.js';

export const STATE_FILENAME = 'state.json';
export const STATE_SCHEMA_VERSION = 1;

/**
 * Resolve directory path where private project machine state is stored.
 *
 * @param {string} projectRoot
 * @param {string} [customStateDir]
 * @returns {string}
 */
export function getProjectStateDir(projectRoot, customStateDir) {
  if (customStateDir) {
    return path.resolve(customStateDir);
  }
  if (process.env.SIGMA_STATE_DIR) {
    return path.resolve(process.env.SIGMA_STATE_DIR);
  }
  return path.join(projectRoot, '.agents');
}

/**
 * Resolve full path to project state.json file.
 *
 * @param {string} projectRoot
 * @param {string} [customStateDir]
 * @returns {string}
 */
export function getProjectStatePath(projectRoot, customStateDir) {
  return path.join(getProjectStateDir(projectRoot, customStateDir), STATE_FILENAME);
}

/**
 * Load and parse the private project state file.
 * Returns default initial state if file does not exist.
 *
 * @param {string} projectRoot
 * @param {string} [customStateDir]
 * @returns {object}
 */
export function loadProjectState(projectRoot, customStateDir) {
  const statePath = getProjectStatePath(projectRoot, customStateDir);
  if (!fs.existsSync(statePath)) {
    return {
      schemaVersion: STATE_SCHEMA_VERSION,
      scope: 'project',
      skills: {},
    };
  }

  try {
    const raw = fs.readFileSync(statePath, 'utf8');
    const parsed = JSON.parse(raw);
    validateProjectState(parsed);
    return parsed;
  } catch (err) {
    throw new Error(`failed to read project state at ${statePath}: ${err.message}`);
  }
}

/**
 * Validate that a project state structure is valid.
 *
 * @param {object} state
 */
export function validateProjectState(state) {
  if (!state || typeof state !== 'object') {
    throw new Error('invalid project state: expected JSON object');
  }
  if (typeof state.schemaVersion !== 'number' || state.schemaVersion < 1) {
    throw new Error('invalid project state: missing or invalid schemaVersion');
  }
  if (state.scope !== 'project') {
    throw new Error(`invalid project state: expected scope 'project', got '${state.scope}'`);
  }
  if (!state.skills || typeof state.skills !== 'object' || Array.isArray(state.skills)) {
    throw new Error('invalid project state: skills must be an object');
  }

  for (const [skillId, skillState] of Object.entries(state.skills)) {
    if (!skillState || typeof skillState !== 'object') {
      throw new Error(`invalid project state entry for '${skillId}'`);
    }
    if (!skillState.revision || typeof skillState.revision !== 'string') {
      throw new Error(`invalid project state for '${skillId}': missing revision`);
    }
    if (!skillState.method || typeof skillState.method !== 'string') {
      throw new Error(`invalid project state for '${skillId}': missing method`);
    }
    if (!skillState.destination || typeof skillState.destination !== 'string') {
      throw new Error(`invalid project state for '${skillId}': missing destination`);
    }
    if (!Array.isArray(skillState.ownedPaths)) {
      throw new Error(`invalid project state for '${skillId}': missing ownedPaths array`);
    }
    if (!skillState.baseHashes || typeof skillState.baseHashes !== 'object') {
      throw new Error(`invalid project state for '${skillId}': missing baseHashes map`);
    }
    if (skillState.copies !== undefined) {
      if (!Array.isArray(skillState.copies)) {
        throw new Error(`invalid project state for '${skillId}': copies must be an array`);
      }
      for (const copy of skillState.copies) {
        if (!copy || typeof copy !== 'object') {
          throw new Error(`invalid project state for '${skillId}': copy entry is not an object`);
        }
        if (copy.kind !== 'canonical' && copy.kind !== 'host') {
          throw new Error(`invalid project state for '${skillId}': copy kind must be canonical or host`);
        }
        if (!copy.destination || typeof copy.destination !== 'string') {
          throw new Error(`invalid project state for '${skillId}': copy is missing destination`);
        }
        if (!Array.isArray(copy.hostIds)) {
          throw new Error(`invalid project state for '${skillId}': copy is missing hostIds`);
        }
        if (!Array.isArray(copy.ownedPaths)) {
          throw new Error(`invalid project state for '${skillId}': copy is missing ownedPaths`);
        }
        if (copy.method !== undefined && copy.method !== 'copy' && copy.method !== 'symlink' && copy.method !== 'junction') {
          throw new Error(`invalid project state for '${skillId}': copy method must be copy, symlink, or junction`);
        }
        if (copy.dependsOn !== undefined && copy.dependsOn !== null && typeof copy.dependsOn !== 'string') {
          throw new Error(`invalid project state for '${skillId}': copy dependsOn must be a string or null`);
        }
        if (copy.baseHashes !== undefined && (typeof copy.baseHashes !== 'object' || Array.isArray(copy.baseHashes) || copy.baseHashes === null)) {
          throw new Error(`invalid project state for '${skillId}': copy baseHashes must be an object`);
        }
      }
    }
  }
}

/**
 * Serialize and atomically write project state.json file.
 *
 * @param {string} projectRoot
 * @param {object} state
 * @param {string} [customStateDir]
 */
export function saveProjectState(projectRoot, state, customStateDir) {
  validateProjectState(state);

  const stateDir = getProjectStateDir(projectRoot, customStateDir);
  if (!fs.existsSync(stateDir)) {
    fs.mkdirSync(stateDir, { recursive: true });
  }

  const sortedSkills = {};
  for (const key of Object.keys(state.skills || {}).sort()) {
    sortedSkills[key] = state.skills[key];
  }

  const cleanState = {
    schemaVersion: state.schemaVersion || STATE_SCHEMA_VERSION,
    scope: 'project',
    skills: sortedSkills,
  };

  const content = JSON.stringify(cleanState, null, 2) + '\n';
  const statePath = path.join(stateDir, STATE_FILENAME);
  const tempPath = path.join(stateDir, `${STATE_FILENAME}.tmp.${process.pid}.${Date.now()}`);

  fs.writeFileSync(tempPath, content, 'utf8');
  try {
    fs.renameSync(tempPath, statePath);
  } catch (err) {
    try {
      fs.copyFileSync(tempPath, statePath);
      fs.unlinkSync(tempPath);
    } catch {
      throw err;
    }
  }
}

function recordedCopyDestinations(entry) {
  const destinations = [];
  if (entry?.destination) destinations.push(entry.destination);
  if (Array.isArray(entry?.copies)) {
    for (const copy of entry.copies) {
      if (copy?.destination) destinations.push(copy.destination);
    }
  }
  return destinations;
}

/**
 * Check whether a target skill destination is recorded as owned by Sigma in project state.
 *
 * @param {string} projectRoot
 * @param {string} skillId
 * @param {string} destinationPath
 * @param {string} [customStateDir]
 * @returns {boolean}
 */
export function isDestinationOwned(projectRoot, skillId, destinationPath, customStateDir) {
  const state = loadProjectState(projectRoot, customStateDir);
  const entry = state.skills?.[skillId];
  if (!entry) {
    return false;
  }

  const relDest = path.relative(projectRoot, destinationPath).replace(/\\/g, '/');
  return recordedCopyDestinations(entry).some((recorded) => {
    const recordedRel = recorded.replace(/\\/g, '/');
    return relDest === recordedRel || path.resolve(destinationPath) === path.resolve(projectRoot, recordedRel);
  });
}

/**
 * Record or update a skill installation in project state.
 *
 * @param {object} state
 * @param {object} details
 * @returns {object} Updated state object
 */
export function recordSkillInState(state, details) {
  const {
    skillId,
    release,
    revision,
    method = 'copy',
    destination,
    projectRoot,
    ownedPaths = [],
    baseHashes = {},
    installedAt,
    copies,
  } = details;

  const toRelative = (value) => {
    if (path.isAbsolute(value)) {
      return path.relative(projectRoot, value).replace(/\\/g, '/');
    }
    return value.replace(/\\/g, '/');
  };

  const relDest = toRelative(destination);
  const normalizedOwnedPaths = ownedPaths.map((p) => toRelative(p));
  const normalizedCopies = Array.isArray(copies)
    ? copies.map((copy) => {
      const entry = {
        kind: copy.kind,
        destination: toRelative(copy.destination),
        method: copy.method || method,
        dependsOn: copy.dependsOn == null ? null : toRelative(copy.dependsOn),
        hostIds: [...(copy.hostIds || [])],
        ownedPaths: (copy.ownedPaths || []).map((p) => toRelative(p)),
      };
      if (copy.baseHashes && typeof copy.baseHashes === 'object') {
        entry.baseHashes = copy.baseHashes;
      }
      return entry;
    })
    : [{
      kind: relDest.replace(/\\/g, '/').startsWith(`${UNIVERSAL_PROJECT_DESTINATION}/`) ? 'canonical' : 'host',
      destination: relDest,
      hostIds: [],
      ownedPaths: normalizedOwnedPaths,
    }];

  const now = new Date().toISOString();
  const existing = state.skills?.[skillId];

  const updatedSkills = { ...(state.skills || {}) };
  updatedSkills[skillId] = {
    release: release || existing?.release || null,
    revision,
    method,
    destination: relDest,
    copies: normalizedCopies,
    ownedPaths: normalizedOwnedPaths,
    baseHashes,
    installedAt: installedAt || existing?.installedAt || now,
    updatedAt: now,
  };

  return {
    schemaVersion: state.schemaVersion || STATE_SCHEMA_VERSION,
    scope: 'project',
    skills: updatedSkills,
  };
}
