import fs from 'node:fs';
import path from 'node:path';

export const PROJECT_LOCK_FILENAME = 'skills-lock.json';
export const PROJECT_LOCK_SCHEMA_VERSION = 1;

/**
 * Load and parse the project lockfile (skills-lock.json).
 * Returns a default empty lock structure if the file does not exist.
 *
 * @param {string} projectRoot
 * @returns {object}
 */
export function loadProjectLock(projectRoot) {
  const lockPath = path.join(projectRoot, PROJECT_LOCK_FILENAME);
  if (!fs.existsSync(lockPath)) {
    return {
      schemaVersion: PROJECT_LOCK_SCHEMA_VERSION,
      release: null,
      skills: {},
    };
  }

  try {
    const raw = fs.readFileSync(lockPath, 'utf8');
    const parsed = JSON.parse(raw);
    validateProjectLock(parsed);
    return parsed;
  } catch (err) {
    throw new Error(`failed to read project lockfile at ${lockPath}: ${err.message}`);
  }
}

/**
 * Validate that a project lock structure complies with repo contracts:
 * - schemaVersion is a positive integer
 * - skills is an object
 * - each skill entry contains only revision (no machine paths, no timestamps)
 *
 * @param {object} lock
 */
export function validateProjectLock(lock) {
  if (!lock || typeof lock !== 'object') {
    throw new Error('invalid project lock: expected JSON object');
  }
  if (typeof lock.schemaVersion !== 'number' || lock.schemaVersion < 1) {
    throw new Error('invalid project lock: missing or invalid schemaVersion');
  }
  if (lock.release !== null && typeof lock.release !== 'string') {
    throw new Error('invalid project lock: release must be string or null');
  }
  if (!lock.skills || typeof lock.skills !== 'object' || Array.isArray(lock.skills)) {
    throw new Error('invalid project lock: skills must be an object');
  }

  for (const [skillId, skillData] of Object.entries(lock.skills)) {
    if (!skillData || typeof skillData !== 'object') {
      throw new Error(`invalid project lock skill entry for '${skillId}'`);
    }
    if (!skillData.revision || typeof skillData.revision !== 'string') {
      throw new Error(`invalid project lock skill '${skillId}': missing revision string`);
    }
    // Prohibit machine paths or timestamps in lockfile
    if ('path' in skillData || 'installedAt' in skillData || 'updatedAt' in skillData || 'destination' in skillData) {
      throw new Error(`invalid project lock skill '${skillId}': lock must not contain paths or timestamps`);
    }
  }
}

/**
 * Serialize and atomically write project lockfile (skills-lock.json) with sorted keys.
 *
 * @param {string} projectRoot
 * @param {object} lock
 */
export function saveProjectLock(projectRoot, lock) {
  validateProjectLock(lock);

  // Sort skill keys alphabetically for deterministic git-merge friendly format
  const sortedSkills = {};
  const skillKeys = Object.keys(lock.skills || {}).sort();
  for (const key of skillKeys) {
    sortedSkills[key] = {
      revision: lock.skills[key].revision,
    };
  }

  const cleanLock = {
    schemaVersion: lock.schemaVersion || PROJECT_LOCK_SCHEMA_VERSION,
    release: lock.release || null,
    skills: sortedSkills,
  };

  const content = JSON.stringify(cleanLock, null, 2) + '\n';
  const lockPath = path.join(projectRoot, PROJECT_LOCK_FILENAME);
  const tempPath = path.join(projectRoot, `${PROJECT_LOCK_FILENAME}.tmp.${process.pid}.${Date.now()}`);

  fs.writeFileSync(tempPath, content, 'utf8');
  try {
    fs.renameSync(tempPath, lockPath);
  } catch (err) {
    try {
      fs.copyFileSync(tempPath, lockPath);
      fs.unlinkSync(tempPath);
    } catch {
      throw err;
    }
  }
}

/**
 * Update or add a skill in the project lock.
 *
 * @param {object} currentLock
 * @param {string} skillId
 * @param {string} revision
 * @param {string} release
 * @returns {object} Updated lock object
 */
export function updateProjectLockSkill(currentLock, skillId, revision, release) {
  const nextSkills = { ...(currentLock.skills || {}) };
  nextSkills[skillId] = { revision };

  return {
    schemaVersion: currentLock.schemaVersion || PROJECT_LOCK_SCHEMA_VERSION,
    release: release || currentLock.release,
    skills: nextSkills,
  };
}
