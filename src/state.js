import fs from 'node:fs';
import { acquireFileLock } from './concurrency-lock.js';
import path from 'node:path';
import { resolveHomeDir, UNIVERSAL_PROJECT_DESTINATION } from './destinations.js';
import { assertPathInside, assertSafeSkillId } from './paths.js';

export const STATE_FILENAME = 'state.json';
export const STATE_SCHEMA_VERSION = 1;
export const PRIVATE_STATE_DIRNAME = '.sigmaskills';
export const LEGACY_MIGRATION_MARKER = 'legacy-migration.json';
const IGNORE_ALL = '*\n';

// Private entries that 0.3.0 and older kept straight in .agents/, next to the committed skills.
const LEGACY_ENTRIES = [
  STATE_FILENAME,
  '.sigma.lock',
  'backups',
  '.sigma-staging',
  '.sigma-uninstall-staging',
  '.sigma-restore-staging',
];

// state.json and backups are generic names. They count as ours only beside a Sigma-shaped state.json;
// the other entries carry a Sigma name. Another tool's files in .agents/ are never moved or removed.
function isSigmaStateFile(file) {
  try {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    return typeof parsed?.schemaVersion === 'number' && parsed.skills !== null && typeof parsed.skills === 'object';
  } catch {
    return false;
  }
}

function presentLegacyEntries(legacyDir) {
  const generic = new Set([STATE_FILENAME, 'backups']);
  const sigmaState = isSigmaStateFile(path.join(legacyDir, STATE_FILENAME));
  return LEGACY_ENTRIES.filter((name) => fs.existsSync(path.join(legacyDir, name)) && (sigmaState || !generic.has(name)));
}

// Journals store absolute paths, so an interrupted run must finish where it started.
const LEGACY_JOURNALS = ['uninstall-journal.json', 'purge-journal.json', '.sigma-purge-quarantine'];

/**
 * Create a private state folder that ignores itself in Git.
 * The ignore file is written only into a folder this call creates, or into the
 * default .agents/.sigmaskills folder when a crash left it without one,
 * so a user's own --state-dir folder is never hidden.
 *
 * @param {string} stateDir
 */
export function ensureStateDir(stateDir) {
  const ignorePath = path.join(stateDir, '.gitignore');
  if (fs.existsSync(stateDir)) {
    const isDefault = path.basename(stateDir) === PRIVATE_STATE_DIRNAME
      && path.basename(path.dirname(stateDir)) === '.agents';
    if (isDefault && !fs.existsSync(ignorePath)) fs.writeFileSync(ignorePath, IGNORE_ALL, 'utf8');
    return;
  }
  fs.mkdirSync(stateDir, { recursive: true });
  fs.writeFileSync(ignorePath, IGNORE_ALL, 'utf8');
}

/**
 * Remove the self-ignore file and the folder when nothing else is left in it.
 *
 * @param {string} stateDir
 */
export function removeEmptyStateDir(stateDir) {
  const ignorePath = path.join(stateDir, '.gitignore');
  try {
    const names = fs.readdirSync(stateDir);
    // Only a folder this installer created (it holds our own ignore file) is removed.
    if (names.length !== 1 || names[0] !== '.gitignore') return;
    if (fs.readFileSync(ignorePath, 'utf8') !== IGNORE_ALL) return;
    fs.rmSync(ignorePath, { force: true });
    fs.rmdirSync(stateDir);
  } catch {
    // Best-effort: an empty private folder is harmless.
  }
}

// fs.cpSync turns a Windows junction into a plain folder with the target's files,
// so copy links as links, the same way backups create them.
function copyNoFollow(from, to) {
  const stat = fs.lstatSync(from);
  if (stat.isSymbolicLink()) {
    fs.symlinkSync(fs.readlinkSync(from), to, process.platform === 'win32' ? 'junction' : 'dir');
  } else if (stat.isDirectory()) {
    fs.mkdirSync(to, { recursive: true });
    for (const name of fs.readdirSync(from)) copyNoFollow(path.join(from, name), path.join(to, name));
  } else {
    fs.copyFileSync(from, to);
  }
}

function finishLegacyCleanup(legacyDir, newDir) {
  const markerPath = path.join(newDir, LEGACY_MIGRATION_MARKER);
  if (!fs.existsSync(markerPath)) return;
  const { entries = [] } = JSON.parse(fs.readFileSync(markerPath, 'utf8'));
  for (const name of entries) {
    if (LEGACY_ENTRIES.includes(name) && name !== '.sigma.lock') {
      fs.rmSync(path.join(legacyDir, name), { recursive: true, force: true });
    }
  }
  fs.rmSync(markerPath, { force: true });
}

/**
 * Move 0.3.0-layout private state from legacyDir into newDir.
 * One directory rename is the commit point: a crash before it leaves the old layout,
 * a crash after it leaves the new layout plus a marker that finishes the cleanup next run.
 *
 * @param {string} legacyDir
 * @param {string} newDir
 * @param {{ beforeCommit?: () => void, afterCommit?: () => void }} [hooks] test-only crash points
 */
export function migrateLegacyState(legacyDir, newDir, hooks = {}) {
  const tempDir = path.join(legacyDir, `${PRIVATE_STATE_DIRNAME}.migrating`);
  if (fs.existsSync(newDir)) {
    if (!fs.existsSync(path.join(newDir, LEGACY_MIGRATION_MARKER))
      && !fs.existsSync(path.join(legacyDir, '.sigma.lock'))) return;
    const release = acquireFileLock(path.join(legacyDir, '.sigma.lock'));
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
      finishLegacyCleanup(legacyDir, newDir);
    } finally { release(); }
    return;
  }
  const present = presentLegacyEntries(legacyDir);
  if (present.length === 0) {
    fs.rmSync(tempDir, { recursive: true, force: true });
    return;
  }
  const journal = LEGACY_JOURNALS.find((name) => fs.existsSync(path.join(legacyDir, name)));
  if (journal) {
    throw new Error(
      `an interrupted SigmaSkills run left ${path.join(legacyDir, journal)}. `
      + 'Finish it with the version that started it, then run this command again: '
      + 'npx @djordje-stojanovic/sigmaskills@0.3.0 uninstall --all --yes, or purge --confirm-purge "purge SigmaSkills".',
    );
  }
  // Hold the old-layout lock so no other run (this version or 0.3.0) touches the files mid-copy.
  const lockPath = path.join(legacyDir, '.sigma.lock');
  let release;
  try { release = acquireFileLock(lockPath); }
  catch (err) {
    throw new Error(`another SigmaSkills run holds ${lockPath}. ${err.message}`);
  }
  try {
    if (fs.existsSync(newDir)) {
      finishLegacyCleanup(legacyDir, newDir);
      return;
    }
    const entries = presentLegacyEntries(legacyDir);
    fs.rmSync(tempDir, { recursive: true, force: true });
    fs.mkdirSync(tempDir, { recursive: true });
    fs.writeFileSync(path.join(tempDir, '.gitignore'), IGNORE_ALL, 'utf8');
    for (const name of entries) {
      if (name === '.sigma.lock') continue;
      copyNoFollow(path.join(legacyDir, name), path.join(tempDir, name));
    }
    fs.writeFileSync(path.join(tempDir, LEGACY_MIGRATION_MARKER), `${JSON.stringify({ entries })}\n`, 'utf8');
    hooks.beforeCommit?.();
    fs.renameSync(tempDir, newDir);
    hooks.afterCommit?.();
    finishLegacyCleanup(legacyDir, newDir);
  } finally {
    release();
  }
}

// Read-only: an unmigrated project keeps working from the old layout until a write command migrates it.
function defaultStateDir(base) {
  const legacyDir = path.join(path.resolve(base), '.agents');
  const stateDir = path.join(legacyDir, PRIVATE_STATE_DIRNAME);
  if (fs.existsSync(stateDir)) return stateDir;
  const legacy = presentLegacyEntries(legacyDir).length > 0
    || LEGACY_JOURNALS.some((name) => fs.existsSync(path.join(legacyDir, name)));
  return legacy ? legacyDir : stateDir;
}

/**
 * Migrate the default private state folder before a write command plans anything.
 * Dry runs, --state-dir, and SIGMA_STATE_DIR never migrate.
 *
 * @param {{ scope?: string, projectRoot?: string, homeDir?: string, env?: object, customStateDir?: string, dryRun?: boolean }} options
 */
export function migrateStateForCommand(options = {}) {
  if (options.dryRun || options.customStateDir || process.env.SIGMA_STATE_DIR) return;
  const base = options.scope === 'global'
    ? (options.homeDir || resolveHomeDir(options.env || process.env))
    : (options.projectRoot || process.cwd());
  const legacyDir = path.join(path.resolve(base), '.agents');
  migrateLegacyState(legacyDir, path.join(legacyDir, PRIVATE_STATE_DIRNAME));
}

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
  return defaultStateDir(projectRoot);
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
    validateProjectState(parsed, { root: projectRoot, stateDir: getProjectStateDir(projectRoot, customStateDir) });
    return parsed;
  } catch (err) {
    throw new Error(`failed to read project state at ${statePath}: ${err.message}`);
  }
}

function assertStateInside(skillId, skillState, bounds) {
  const inside = (recorded, what) => assertPathInside(bounds.root, recorded, `state entry '${skillId}' ${what}`);
  inside(skillState.destination, 'destination');
  for (const owned of skillState.ownedPaths) if (typeof owned === 'string') inside(owned, 'owned path');
  for (const copy of skillState.copies || []) {
    inside(copy.destination, 'destination');
    for (const owned of copy.ownedPaths) if (typeof owned === 'string') inside(owned, 'owned path');
    if (typeof copy.dependsOn === 'string') inside(copy.dependsOn, 'dependency path');
  }
  if (typeof skillState.lastBackup === 'string') {
    assertPathInside(bounds.stateDir, skillState.lastBackup, `state entry '${skillId}' backup`);
  }
}

/**
 * Validate that a managed state structure is valid. With bounds, recorded paths must stay inside them.
 *
 * @param {object} state
 * @param {'project'|'global'} expectedScope
 * @param {{ root: string, stateDir: string }} [bounds]
 */
function validateManagedState(state, expectedScope, bounds) {
  const label = expectedScope === 'global' ? 'global state' : 'project state';
  if (!state || typeof state !== 'object') {
    throw new Error(`invalid ${label}: expected JSON object`);
  }
  if (typeof state.schemaVersion !== 'number' || state.schemaVersion < 1) {
    throw new Error(`invalid ${label}: missing or invalid schemaVersion`);
  }
  if (state.schemaVersion > STATE_SCHEMA_VERSION) {
    throw new Error(
      `unsupported ${label} schemaVersion ${state.schemaVersion}; this installer supports ${STATE_SCHEMA_VERSION}`,
    );
  }
  if (state.scope !== expectedScope) {
    throw new Error(`invalid ${label}: expected scope '${expectedScope}', got '${state.scope}'`);
  }
  if (!state.skills || typeof state.skills !== 'object' || Array.isArray(state.skills)) {
    throw new Error(`invalid ${label}: skills must be an object`);
  }

  for (const [skillId, skillState] of Object.entries(state.skills)) {
    assertSafeSkillId(skillId, `invalid ${label}`);
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
    if (bounds) assertStateInside(skillId, skillState, bounds);
  }
}

/**
 * Validate that a project state structure is valid.
 *
 * @param {object} state
 */
export function validateProjectState(state, bounds) {
  validateManagedState(state, 'project', bounds);
}

/**
 * Validate that a global state structure is valid.
 *
 * @param {object} state
 */
export function validateGlobalState(state, bounds) {
  validateManagedState(state, 'global', bounds);
}

/**
 * Serialize and atomically write project state.json file.
 *
 * @param {string} projectRoot
 * @param {object} state
 * @param {string} [customStateDir]
 */
function writeStateFile(stateDir, state, scope) {
  ensureStateDir(stateDir);

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
  return defaultStateDir(homeDir);
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
      validateGlobalState(parsed, { root: homeDir, stateDir: getGlobalStateDir(homeDir, customStateDir) });
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

/**
 * Drop a skill from managed state after a successful uninstall.
 *
 * @param {object} state
 * @param {string} skillId
 * @returns {object}
 */
export function removeSkillFromState(state, skillId) {
  const skills = { ...(state.skills || {}) };
  delete skills[skillId];
  return {
    schemaVersion: state.schemaVersion || STATE_SCHEMA_VERSION,
    scope: state.scope || 'project',
    skills,
  };
}
