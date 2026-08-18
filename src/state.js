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
function validateManagedState(state, expectedScope) {
  const label = expectedScope === 'global' ? 'global state' : 'project state';
  if (!state || typeof state !== 'object') {
    throw new Error(`invalid ${label}: expected JSON object`);
  }
  if (typeof state.schemaVersion !== 'number' || state.schemaVersion < 1) {
    throw new Error(`invalid ${label}: missing or invalid schemaVersion`);
  }
  if (state.scope !== expectedScope) {
    throw new Error(`invalid ${label}: expected scope '${expectedScope}', got '${state.scope}'`);
  }
  if (!state.skills || typeof state.skills !== 'object' || Array.isArray(state.skills)) {
    throw new Error(`invalid ${label}: skills must be an object`);
  }

  for (const [skillId, skillState] of Object.entries(state.skills)) {
    if (!skillState || typeof skillState !== 'object') {
      throw new Error(`invalid ${label} entry for '${skillId}'`);
    }
    if (!skillState.revision || typeof skillState.revision !== 'string') {
      throw new Error(`invalid ${label} for '${skillId}': missing revision`);
    }
    if (!skillState.method || typeof skillState.method !== 'string') {
      throw new Error(`invalid ${label} for '${skillId}': missing method`);
    }
    if (!skillState.destination || typeof skillState.destination !== 'string') {
      throw new Error(`invalid ${label} for '${skillId}': missing destination`);
    }
    if (!Array.isArray(skillState.ownedPaths)) {
      throw new Error(`invalid ${label} for '${skillId}': missing ownedPaths array`);
    }
    if (!skillState.baseHashes || typeof skillState.baseHashes !== 'object') {
      throw new Error(`invalid ${label} for '${skillId}': missing baseHashes map`);
    }
    if (skillState.lastBackup !== undefined && skillState.lastBackup !== null && typeof skillState.lastBackup !== 'string') {
      throw new Error(`invalid ${label} for '${skillId}': lastBackup must be a string or null`);
    }
    if (skillState.cleanupDebt !== undefined) {
      if (!Array.isArray(skillState.cleanupDebt) || skillState.cleanupDebt.some((item) => typeof item !== 'string')) {
        throw new Error(`invalid ${label} for '${skillId}': cleanupDebt must be an array of strings`);
      }
    }
    if (skillState.copies !== undefined) {
      if (!Array.isArray(skillState.copies)) {
        throw new Error(`invalid ${label} for '${skillId}': copies must be an array`);
      }
      for (const copy of skillState.copies) {
        if (!copy || typeof copy !== 'object') {
          throw new Error(`invalid ${label} for '${skillId}': copy entry is not an object`);
        }
        if (copy.kind !== 'canonical' && copy.kind !== 'host') {
          throw new Error(`invalid ${label} for '${skillId}': copy kind must be canonical or host`);
        }
        if (!copy.destination || typeof copy.destination !== 'string') {
          throw new Error(`invalid ${label} for '${skillId}': copy is missing destination`);
        }
        if (!Array.isArray(copy.hostIds)) {
          throw new Error(`invalid ${label} for '${skillId}': copy is missing hostIds`);
        }
        if (!Array.isArray(copy.ownedPaths)) {
          throw new Error(`invalid ${label} for '${skillId}': copy is missing ownedPaths`);
        }
        if (copy.method !== undefined && copy.method !== 'copy' && copy.method !== 'symlink' && copy.method !== 'junction') {
          throw new Error(`invalid ${label} for '${skillId}': copy method must be copy, symlink, or junction`);
        }
        if (copy.dependsOn !== undefined && copy.dependsOn !== null && typeof copy.dependsOn !== 'string') {
          throw new Error(`invalid ${label} for '${skillId}': copy dependsOn must be a string or null`);
        }
        if (copy.baseHashes !== undefined && (typeof copy.baseHashes !== 'object' || Array.isArray(copy.baseHashes) || copy.baseHashes === null)) {
          throw new Error(`invalid ${label} for '${skillId}': copy baseHashes must be an object`);
        }
      }
    }
  }
}

/**
 * Validate that a project state structure is valid.
 *
 * @param {object} state
 */
export function validateProjectState(state) {
  validateManagedState(state, 'project');
}

/**
 * Validate that a global state structure is valid.
 *
 * @param {object} state
 */
export function validateGlobalState(state) {
  validateManagedState(state, 'global');
}

/**
 * Serialize and atomically write project state.json file.
 *
 * @param {string} projectRoot
 * @param {object} state
 * @param {string} [customStateDir]
 */
function writeStateFile(stateDir, state, scope) {
  if (!fs.existsSync(stateDir)) {
    fs.mkdirSync(stateDir, { recursive: true });
  }

  const sortedSkills = {};
  for (const key of Object.keys(state.skills || {}).sort()) {
    sortedSkills[key] = state.skills[key];
  }

  const cleanState = {
    schemaVersion: state.schemaVersion || STATE_SCHEMA_VERSION,
    scope,
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

/**
 * Serialize and atomically write project state.json file.
 *
 * @param {string} projectRoot
 * @param {object} state
 * @param {string} [customStateDir]
 */
export function saveProjectState(projectRoot, state, customStateDir) {
  validateProjectState(state);
  writeStateFile(getProjectStateDir(projectRoot, customStateDir), state, 'project');
}

/**
 * Resolve directory path where private Global Installation state is stored.
 *
 * @param {string} homeDir
 * @param {string} [customStateDir]
 * @returns {string}
 */
export function getGlobalStateDir(homeDir, customStateDir) {
  if (customStateDir) {
    return path.resolve(customStateDir);
  }
  if (process.env.SIGMA_STATE_DIR) {
    return path.resolve(process.env.SIGMA_STATE_DIR);
  }
  return path.join(path.resolve(homeDir), '.agents');
}

/**
 * Resolve full path to global state.json file.
 *
 * @param {string} homeDir
 * @param {string} [customStateDir]
 * @returns {string}
 */
export function getGlobalStatePath(homeDir, customStateDir) {
  return path.join(getGlobalStateDir(homeDir, customStateDir), STATE_FILENAME);
}

function emptyGlobalState() {
  return {
    schemaVersion: STATE_SCHEMA_VERSION,
    scope: 'global',
    skills: {},
  };
}

function migrateGlobalState(parsed) {
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('invalid global state: expected JSON object');
  }
  if (typeof parsed.schemaVersion === 'number' && parsed.schemaVersion > STATE_SCHEMA_VERSION) {
    throw new Error(
      `unsupported global state schemaVersion ${parsed.schemaVersion}; this installer supports ${STATE_SCHEMA_VERSION}`,
    );
  }

  const skills = {};
  for (const [skillId, entry] of Object.entries(parsed.skills || {})) {
    if (!entry || typeof entry !== 'object') {
      throw new Error(`invalid global state entry for '${skillId}'`);
    }
    skills[skillId] = {
      ...entry,
      lastBackup: entry.lastBackup || entry.backup || null,
    };
  }

  const migrated = {
    schemaVersion: STATE_SCHEMA_VERSION,
    scope: 'global',
    skills,
  };
  validateGlobalState(migrated);
  return migrated;
}

/**
 * Load and parse the private global state file.
 * Unknown newer schemas fail without writing. Older schemas migrate in memory.
 *
 * @param {string} homeDir
 * @param {string} [customStateDir]
 * @returns {object}
 */
export function loadGlobalState(homeDir, customStateDir) {
  const statePath = getGlobalStatePath(homeDir, customStateDir);
  if (!fs.existsSync(statePath)) {
    return emptyGlobalState();
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    if (typeof parsed?.schemaVersion === 'number' && parsed.schemaVersion > STATE_SCHEMA_VERSION) {
      throw new Error(
        `unsupported global state schemaVersion ${parsed.schemaVersion}; this installer supports ${STATE_SCHEMA_VERSION}`,
      );
    }
    if (parsed?.schemaVersion === STATE_SCHEMA_VERSION && parsed.scope === 'global') {
      validateGlobalState(parsed);
      return parsed;
    }
    if (parsed?.schemaVersion === STATE_SCHEMA_VERSION) {
      throw new Error(`invalid global state: expected scope 'global', got '${parsed.scope}'`);
    }
    return migrateGlobalState(parsed);
  } catch (err) {
    if (/unsupported global state schemaVersion/.test(err.message) || /expected scope 'global'/.test(err.message)) {
      throw err;
    }
    throw new Error(`failed to read global state at ${statePath}: ${err.message}`);
  }
}

/**
 * Serialize and atomically write global state.json file.
 *
 * @param {string} homeDir
 * @param {object} state
 * @param {string} [customStateDir]
 */
export function saveGlobalState(homeDir, state, customStateDir) {
  if (typeof state?.schemaVersion === 'number' && state.schemaVersion > STATE_SCHEMA_VERSION) {
    throw new Error(
      `unsupported global state schemaVersion ${state.schemaVersion}; this installer supports ${STATE_SCHEMA_VERSION}`,
    );
  }
  validateGlobalState(state);
  writeStateFile(getGlobalStateDir(homeDir, customStateDir), state, 'global');
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
export function isDestinationOwned(projectRoot, skillId, destinationPath, customStateDir, options = {}) {
  const scope = options.scope || 'project';
  const state = scope === 'global'
    ? loadGlobalState(projectRoot, customStateDir)
    : loadProjectState(projectRoot, customStateDir);
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
    lastBackup,
    cleanupDebt,
    scope,
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
    lastBackup: lastBackup === undefined
      ? (existing?.lastBackup || null)
      : (lastBackup == null ? null : toRelative(lastBackup)),
  };
  if (cleanupDebt !== undefined) {
    if (Array.isArray(cleanupDebt) && cleanupDebt.length > 0) {
      updatedSkills[skillId].cleanupDebt = cleanupDebt.map((item) => toRelative(item));
    }
  } else if (Array.isArray(existing?.cleanupDebt) && existing.cleanupDebt.length > 0) {
    updatedSkills[skillId].cleanupDebt = existing.cleanupDebt;
  }

  return {
    schemaVersion: state.schemaVersion || STATE_SCHEMA_VERSION,
    scope: scope || state.scope || 'project',
    skills: updatedSkills,
  };
}
