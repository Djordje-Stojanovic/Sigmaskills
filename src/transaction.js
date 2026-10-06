import fs from 'node:fs';
import { acquireFileLock } from './concurrency-lock.js';
import path from 'node:path';
import { findPackageRoot, validateSkill } from './catalog.js';
import { injectRawCustomContent, replaceDescriptionEntry } from './customization.js';
import { commitSkillBackup, exportSkillTree, getBackupRoot, pruneOlderBackups } from './backup.js';
import { createInstallPlan } from './plan.js';
import { isForeignProjectLock, loadProjectLock, saveProjectLock, updateProjectLockSkill, PROJECT_LOCK_FILENAME } from './project-lock.js';
import { resolveHomeDir } from './destinations.js';
import {
  ensureStateDir,
  getGlobalStateDir,
  getGlobalStatePath,
  getProjectStateDir,
  getProjectStatePath,
  loadGlobalState,
  loadProjectState,
  saveGlobalState,
  saveProjectState,
  recordSkillInState,
  migrateStateForCommand,
} from './state.js';
import { createSkillLink, pathExists, removeManagedPath } from './links.js';

/**
 * Acquire process concurrency lock for project.
 *
 * @param {string} projectRoot
 * @param {string} [customStateDir]
 * @returns {() => void} Release lock function
 */
export function acquireConcurrencyLock(projectRoot, customStateDir, hooks) {
  const stateDir = getProjectStateDir(projectRoot, customStateDir);
  ensureStateDir(stateDir);
  return acquireFileLock(path.join(stateDir, '.sigma.lock'), hooks);
}

/**
 * Build the fail-closed error for an unowned destination.
 *
 * @param {object} plan
 * @returns {Error}
 */
export function createUnownedConflictError(plan) {
  const conflictDest = (plan.destinations || []).find((dest) => dest.unownedConflict)?.destination
    || plan.destination;
  return new Error(
    `Destination '${conflictDest}' already exists and is not owned by SigmaSkills. Safe adoption is not enabled. Installation aborted.`,
  );
}

export function createNeedsResolutionError(plan) {
  const pending = (plan.destinations || []).filter((dest) => dest.migratable && !dest.resolution);
  const details = pending.map((dest) => {
    const diff = dest.diff || { added: [], replaced: [], deleted: [] };
    return `${dest.relativeDestination} (${dest.recognition}, provenance ${dest.confidence}; +${(diff.added || []).length} ~${(diff.replaced || []).length} -${(diff.deleted || []).length})`;
  }).join('; ');
  return new Error(
    `Changed or legacy Sigma-looking trees need an explicit replace, skip, or export choice before mutation: ${details}`,
  );
}

/**
 * Read the caller's options and build the install plan.
 * The returned context is passed to every step below.
 */
function createInstallContext(params) {
  const { catalog, skillId, customStateDir, dryRun = false } = params;
  const scope = params.scope || 'project';
  const env = params.env || process.env;
  const homeDir = path.resolve(params.homeDir || resolveHomeDir(env));
  const projectRoot = path.resolve(params.projectRoot || process.cwd());
  const root = scope === 'global' ? homeDir : projectRoot;
  const packageRoot = params.packageRoot || findPackageRoot();

  const plan = createInstallPlan(catalog, {
    skillId,
    projectRoot,
    homeDir,
    scope,
    customStateDir,
    packageRoot,
    dryRun,
    selectedRoots: params.selectedRoots,
    destinationGroups: params.destinationGroups,
    registry: params.registry,
    env,
    method: params.method,
    copyRoots: params.copyRoots,
    resolutions: params.resolutions,
    adoptChanged: params.adoptChanged,
    adoptLegacy: params.adoptLegacy,
    adoptUnverified: params.adoptUnverified,
    adoptMalformed: params.adoptMalformed,
    exportDir: params.exportDir,
  });

  return { params, catalog, skillId, customStateDir, dryRun, scope, root, packageRoot, plan, batch: params.batch };
}

/**
 * Record the paths and the original bytes that rollback needs.
 * Adds staging paths, the two undo lists, and the state and lock snapshots to the context.
 */
function snapshotInstallState(tx) {
  const { params, skillId, scope, root, customStateDir } = tx;
  const stateDir = scope === 'global' ? getGlobalStateDir(root, customStateDir) : getProjectStateDir(root, customStateDir);
  tx.stagingParent = path.join(stateDir, '.sigma-staging');
  tx.stagingDir = path.join(
    tx.stagingParent,
    `${skillId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  );

  tx.committed = [];
  tx.privateBackups = [];

  tx.lockLeftAlone = scope !== 'global' && isForeignProjectLock(root);
  tx.useProjectLock = scope !== 'global' && !tx.lockLeftAlone;
  tx.lockPath = path.join(root, PROJECT_LOCK_FILENAME);
  tx.lockExisted = tx.useProjectLock && fs.existsSync(tx.lockPath);
  tx.originalLockBytes = tx.lockExisted ? fs.readFileSync(tx.lockPath) : null;
  tx.originalLock = tx.useProjectLock ? loadProjectLock(root) : { skills: {} };

  tx.statePath = scope === 'global'
    ? getGlobalStatePath(root, customStateDir)
    : getProjectStatePath(root, customStateDir);
  tx.stateExisted = fs.existsSync(tx.statePath);
  tx.originalStateBytes = tx.stateExisted ? fs.readFileSync(tx.statePath) : null;
  tx.originalState = scope === 'global'
    ? loadGlobalState(root, customStateDir)
    : loadProjectState(root, customStateDir);
  tx.persistState = params.saveState || (scope === 'global' ? saveGlobalState : saveProjectState);
  tx.stateDirForBackups = stateDir;
}

function cleanupStaging(tx) {
  const { stagingDir, stagingParent } = tx;
  try {
    if (fs.existsSync(stagingDir)) {
      fs.rmSync(stagingDir, { recursive: true, force: true });
    }
    if (fs.existsSync(stagingParent) && fs.readdirSync(stagingParent).length === 0) {
      fs.rmSync(stagingParent, { recursive: true, force: true });
    }
  } catch {
    // Staging cleanup is best-effort
  }
}

/** Undo every commit, private backup, and state or lock write. Always releases the lock at the end. */
function rollbackInstall(tx) {
  try {
    for (const entry of tx.committed.splice(0).reverse()) {
      if (entry.adopted) continue;
      try {
        if (entry.backupDir && pathExists(entry.backupDir)) {
          if (pathExists(entry.destDir)) {
            removeManagedPath(entry.destDir);
          }
          fs.renameSync(entry.backupDir, entry.destDir);
        } else if (pathExists(entry.destDir)) {
          removeManagedPath(entry.destDir);
        }
      } catch {
        // Per-destination rollback is best-effort
      }
    }
    for (const backupPath of tx.privateBackups.splice(0)) {
      try {
        if (pathExists(backupPath)) removeManagedPath(backupPath);
      } catch {
        // Private backup cleanup is best-effort
      }
    }
    // Restore state and lock or remove if they didn't exist before
    if (tx.stateExisted && tx.originalStateBytes) {
      fs.writeFileSync(tx.statePath, tx.originalStateBytes);
    } else if (fs.existsSync(tx.statePath)) {
      fs.unlinkSync(tx.statePath);
    }

    if (tx.useProjectLock && tx.lockExisted && tx.originalLockBytes) {
      fs.writeFileSync(tx.lockPath, tx.originalLockBytes);
    } else if (tx.useProjectLock && fs.existsSync(tx.lockPath)) {
      fs.unlinkSync(tx.lockPath);
    }
  } catch {
    // Rollback is best-effort
  } finally {
    cleanupStaging(tx);
    tx.releaseLock();
  }
}

/** True when every destination is already adopted and state and lock already match this revision. */
function isAlreadyInstalled(tx) {
  const { plan, skillId, scope, originalState, originalLock } = tx;
  const allAdopted = plan.destinations.every((dest) => dest.adoption);
  const existingEntry = originalState.skills?.[skillId];
  const existingDests = new Set(
    (existingEntry?.copies || []).map((copy) => String(copy.destination || '').replace(/\\/g, '/')),
  );
  const plannedDests = plan.destinations.map((dest) => dest.relativeDestination);
  const sameManagedLayout = existingEntry
    && existingEntry.revision === plan.sourceRevision
    && plannedDests.every((dest) => existingDests.has(dest))
    && existingDests.size === plannedDests.length
    && (scope === 'global' || originalLock.skills?.[skillId]?.revision === plan.sourceRevision);
  return Boolean(allAdopted && sameManagedLayout);
}

/** Result for an install that changed nothing. */
function unchangedResult(tx) {
  return {
    success: true,
    dryRun: false,
    plan: tx.plan,
    lock: tx.originalLock,
    state: tx.originalState,
  };
}

/** A destination is written unless it is adopted in place, skipped, or exported. */
function willWrite(dest) {
  return !dest.adoption
    && dest.resolution !== 'skip'
    && dest.resolution !== 'export';
}

/**
 * Copy the skill into the staging directory, check its revision, and add preserved customization.
 *
 * @returns {object} File hashes for the staged skill
 */
function stageSkill(tx) {
  const { params, catalog, skillId, packageRoot, plan, stagingDir } = tx;
  const catalogSkill = catalog.skills.find((item) => item.id === skillId);
  let fileHashes = catalogSkill?.files || {};

  if (plan.destinations.some(willWrite)) {
    fs.mkdirSync(stagingDir, { recursive: true });
    const sourceSkillDir = path.join(packageRoot, skillId);
    if (!fs.existsSync(sourceSkillDir)) {
      throw new Error(`source skill directory missing at ${sourceSkillDir}`);
    }

    fs.cpSync(sourceSkillDir, stagingDir, { recursive: true });

    const manifestMetadata = catalog.manifest.skills.find((s) => s.id === skillId);
    const validatedStaged = validateSkill(stagingDir, manifestMetadata);
    if (validatedStaged.revision !== plan.sourceRevision) {
      throw new Error(
        `staged skill revision '${validatedStaged.revision}' does not match catalog revision '${plan.sourceRevision}'`,
      );
    }
    fileHashes = validatedStaged.files;
    if (params.preservedCustomRaw !== undefined || params.preservedDescription !== undefined) {
      const stagedSkillMd = path.join(stagingDir, 'SKILL.md');
      if (pathExists(stagedSkillMd)) {
        let stagedMarkdown = fs.readFileSync(stagedSkillMd, 'utf8');
        if (params.preservedCustomRaw !== undefined) {
          stagedMarkdown = injectRawCustomContent(stagedMarkdown, params.preservedCustomRaw, skillId);
        }
        fs.writeFileSync(
          stagedSkillMd,
          replaceDescriptionEntry(stagedMarkdown, params.preservedDescription),
          'utf8',
        );
      }
    }
  }
  return fileHashes;
}

function restoreBackup(destDir, backupDir) {
  if (backupDir && pathExists(backupDir)) {
    if (pathExists(destDir)) removeManagedPath(destDir);
    fs.renameSync(backupDir, destDir);
  } else if (pathExists(destDir)) {
    removeManagedPath(destDir);
  }
}

/** Create the parent directory and move any existing destination aside. Returns the backup path or null. */
function prepareDestination(tx, destDir) {
  const destParent = path.dirname(destDir);
  if (!fs.existsSync(destParent)) {
    fs.mkdirSync(destParent, { recursive: true });
  }
  let backupDir = null;
  if (pathExists(destDir)) {
    backupDir = path.join(
      destParent,
      `.${tx.skillId}-backup-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    );
    fs.renameSync(destDir, backupDir);
  }
  return backupDir;
}

function commitCopy(tx, destDir) {
  const backupDir = prepareDestination(tx, destDir);
  try {
    fs.cpSync(tx.stagingDir, destDir, { recursive: true });
    tx.committed.push({ destDir, backupDir });
  } catch (copyErr) {
    restoreBackup(destDir, backupDir);
    throw new Error(`failed to write destination '${destDir}': ${copyErr.message}`);
  }
}

function commitLink(tx, dest, canonicalDest) {
  const { params, root } = tx;
  const createLink = params.createLink || ((linkPath, targetPath) => (
    createSkillLink(linkPath, targetPath, root)
  ));
  const destDir = dest.destination;
  const backupDir = prepareDestination(tx, destDir);
  try {
    createLink(destDir, canonicalDest.destination, root);
    tx.committed.push({ destDir, backupDir });
  } catch (linkErr) {
    restoreBackup(destDir, backupDir);
    const failure = {
      destination: dest.destination,
      relativeDestination: dest.relativeDestination,
      relativeRoot: dest.relativeRoot,
      method: dest.method,
      cause: linkErr.message,
      code: linkErr.code,
    };
    const decision = typeof params.onLinkFailure === 'function'
      ? params.onLinkFailure(failure)
      : 'abort';
    if (decision !== 'copy') {
      const wrapped = new Error(linkErr.message);
      wrapped.cause = linkErr;
      wrapped.code = linkErr.code;
      wrapped.linkFailure = failure;
      throw wrapped;
    }
    dest.fallbackFrom = dest.method;
    dest.method = 'copy';
    dest.dependsOn = null;
    commitCopy(tx, destDir);
  }
}

function exportDestination(tx, dest) {
  const { params, plan, root, skillId } = tx;
  const exportRoot = plan.exportDir || path.join(root, '.sigma-export');
  const exporter = params.exportSkill || exportSkillTree;
  dest.exportPath = exporter({
    sourceDir: dest.destination,
    exportRoot,
    skillId,
    dest: dest.exportPath,
  });
}

/** Save a private backup of the tree that a replace choice is about to overwrite. */
function backupBeforeReplace(tx, dest) {
  const { params, plan, skillId, scope } = tx;
  const backupFn = params.backupSkill || commitSkillBackup;
  const existing = tx.originalState.skills?.[skillId];
  const privateBackup = backupFn({
    stateDir: tx.stateDirForBackups,
    skillId,
    sourceDir: dest.destination,
    ownership: {
      scope,
      release: existing?.release || plan.release || null,
      revision: existing?.revision || null,
      method: existing?.method || dest.method,
      canonicalTarget: existing?.destination || dest.relativeDestination,
      copies: existing?.copies || [],
      ownedPaths: existing?.ownedPaths || [dest.relativeDestination],
    },
  });
  tx.privateBackups.push(privateBackup);
  dest.privateBackup = privateBackup;
  if (typeof params.afterBackup === 'function') {
    params.afterBackup(privateBackup);
  }
}

/** Put the user's customization back into a replaced SKILL.md. */
function reapplyCustomization(tx, dest) {
  const customStatus = dest.customization?.status;
  if (
    tx.params.preservedCustomRaw === undefined
    && dest.resolution === 'replace'
    && (customStatus === 'valid' || customStatus === 'empty')
  ) {
    const skillMd = path.join(dest.destination, 'SKILL.md');
    if (pathExists(skillMd)) {
      const current = fs.readFileSync(skillMd, 'utf8');
      fs.writeFileSync(
        skillMd,
        injectRawCustomContent(current, dest.customization.rawCustomContent ?? '\n', tx.skillId),
        'utf8',
      );
    }
  }
}

/** Write, link, adopt, skip, or export each destination. The canonical destination goes first. */
function commitDestinations(tx) {
  const { plan } = tx;
  const canonicalDest = plan.destinations.find((dest) => dest.kind === 'canonical')
    || plan.destinations[0];

  const ordered = [...plan.destinations].sort((a, b) => {
    if (a.kind === 'canonical' && b.kind !== 'canonical') return -1;
    if (b.kind === 'canonical' && a.kind !== 'canonical') return 1;
    return 0;
  });

  for (const dest of ordered) {
    if (dest.adoption) {
      tx.committed.push({ destDir: dest.destination, backupDir: null, adopted: true });
      continue;
    }
    if (dest.resolution === 'skip') {
      dest.exportPath = null;
      continue;
    }
    if (dest.resolution === 'export') {
      exportDestination(tx, dest);
      continue;
    }
    if (dest.resolution === 'replace' && pathExists(dest.destination)) {
      backupBeforeReplace(tx, dest);
    }
    if (dest.method === 'copy') commitCopy(tx, dest.destination);
    else commitLink(tx, dest, canonicalDest);
    reapplyCustomization(tx, dest);
  }
}

/** The state entries for the destinations this run owns. */
function buildCopies(tx, fileHashes) {
  const { plan } = tx;
  return plan.destinations
    .filter((dest) => dest.adoption || dest.resolution === 'replace' || (!dest.migratable && dest.resolution !== 'skip' && dest.resolution !== 'export'))
    .map((dest) => {
      const independent = dest.method === 'copy';
      return {
        kind: dest.kind,
        destination: dest.relativeDestination,
        method: dest.method,
        dependsOn: dest.dependsOn || null,
        hostIds: (dest.hosts || []).map((host) => host.id),
        ownedPaths: independent
          ? plan.files.map((file) => `${dest.relativeDestination}/${file}`)
          : [dest.relativeDestination],
        ...(independent ? { baseHashes: dest.baseHashes && dest.resolution !== 'replace' ? dest.baseHashes : fileHashes } : {}),
      };
    });
}

/** Add this skill to a state object. `record` holds copies, primary, fileHashes, and lastBackup. */
function recordInstalledSkill(tx, baseState, record, cleanupDebt) {
  const { plan, skillId, scope, root } = tx;
  return recordSkillInState(baseState, {
    skillId,
    release: plan.release,
    revision: plan.sourceRevision,
    method: plan.method,
    destination: record.primary.destination,
    projectRoot: root,
    ownedPaths: record.primary.ownedPaths,
    baseHashes: record.primary.baseHashes || record.fileHashes,
    copies: record.copies,
    scope,
    lastBackup: record.lastBackup,
    cleanupDebt,
  });
}

/** Write the project lock now, or queue it for the batch. Returns the lock to report. */
function writeProjectLock(tx) {
  const { plan, skillId, root, batch } = tx;
  if (tx.useProjectLock && batch) {
    batch.lockSkills.push([skillId, plan.sourceRevision, plan.release]);
  } else if (tx.useProjectLock) {
    const updatedLock = updateProjectLockSkill(
      tx.originalLock,
      skillId,
      plan.sourceRevision,
      plan.release,
    );
    saveProjectLock(root, updatedLock);
    return updatedLock;
  }
  return tx.originalLock;
}

/** Drop the swap backups after a successful install, prune older private backups, and record any debt. */
function finalizeInstall(tx, updatedState, record) {
  const { params, skillId, scope, root, customStateDir, batch, stateDirForBackups } = tx;
  for (const entry of tx.committed) {
    if (entry.backupDir && pathExists(entry.backupDir)) {
      removeManagedPath(entry.backupDir);
      entry.backupDir = null;
    }
  }
  for (const backupPath of tx.privateBackups) {
    let debt = [];
    try {
      const pruneFn = params.pruneBackups || pruneOlderBackups;
      const result = pruneFn({
        stateDir: stateDirForBackups,
        skillId,
        keepPath: backupPath,
      });
      if (result && Array.isArray(result.debt)) debt = result.debt;
    } catch {
      const dir = path.join(getBackupRoot(stateDirForBackups), skillId);
      if (pathExists(dir)) {
        const keep = path.resolve(backupPath);
        for (const name of fs.readdirSync(dir)) {
          const full = path.resolve(dir, name);
          if (full !== keep) {
            debt.push(path.relative(stateDirForBackups, full).replace(/\\/g, '/'));
          }
        }
      }
    }
    if (debt.length > 0) {
      try {
        const debtBase = batch
          ? (scope === 'global' ? loadGlobalState(root, customStateDir) : loadProjectState(root, customStateDir))
          : updatedState;
        tx.persistState(root, recordInstalledSkill(tx, debtBase, record, debt), customStateDir);
      } catch {
        // Two backups remain; recording debt is best-effort.
      }
    }
  }
}

/**
 * Run the install steps. Returns the summary, or throws so the caller can roll back.
 */
function runInstallTransaction(tx) {
  const { plan, batch } = tx;

  if (isAlreadyInstalled(tx)) {
    cleanupStaging(tx);
    tx.releaseLock();
    return unchangedResult(tx);
  }

  const fileHashes = stageSkill(tx);
  commitDestinations(tx);

  const copies = buildCopies(tx, fileHashes);
  if (copies.length === 0) {
    cleanupStaging(tx);
    tx.releaseLock();
    return unchangedResult(tx);
  }
  const primary = copies.find((copy) => copy.kind === 'canonical') || copies[0];

  const lastBackup = tx.privateBackups.length > 0
    ? path.relative(tx.stateDirForBackups, tx.privateBackups[tx.privateBackups.length - 1]).replace(/\\/g, '/')
    : undefined;
  const record = { copies, primary, fileHashes, lastBackup };
  const updatedState = recordInstalledSkill(tx, tx.originalState, record, []);
  tx.persistState(tx.root, updatedState, tx.customStateDir);

  const updatedLock = writeProjectLock(tx);

  // Cleanup backups after state and lock write succeed (a batch runs this after its lock write)
  const finalize = () => finalizeInstall(tx, updatedState, record);
  if (batch) batch.finalizers.push(finalize);
  else finalize();

  cleanupStaging(tx);
  tx.releaseLock();

  return {
    success: true,
    dryRun: false,
    plan,
    lock: updatedLock,
    lockLeftAlone: tx.lockLeftAlone,
    state: updatedState,
  };
}

/**
 * Execute transactional single-skill project installation.
 *
 * @param {object} params
 * @param {object} params.catalog
 * @param {string} params.skillId
 * @param {string} [params.projectRoot]
 * @param {string} [params.customStateDir]
 * @param {string} [params.packageRoot]
 * @param {boolean} [params.dryRun]
 * @returns {object} Execution summary with plan
 */
export function executeProjectInstall(params) {
  migrateStateForCommand(params);
  const tx = createInstallContext(params);
  const { plan, batch } = tx;

  if (plan.unownedConflict) throw createUnownedConflictError(plan);

  if (tx.dryRun) {
    return {
      success: true,
      dryRun: true,
      plan,
    };
  }

  if (plan.requiresApproval) throw createNeedsResolutionError(plan);

  // Inside a batch, the batch holds the concurrency lock and owns rollback, the lock file, and cleanup.
  tx.releaseLock = batch ? () => {} : acquireConcurrencyLock(tx.root, tx.customStateDir);
  // The outer finally frees the lock even when setup code below throws before the transaction starts.
  try {
    snapshotInstallState(tx);
    if (batch) batch.rollbacks.push(() => rollbackInstall(tx));

    try {
      return runInstallTransaction(tx);
    } catch (err) {
      rollbackInstall(tx);
      throw err;
    } finally {
      cleanupStaging(tx);
      tx.releaseLock();
    }
  } finally {
    tx.releaseLock();
  }
}

/**
 * Install several skills as one transaction.
 *
 * Every skill is planned first, so a conflict or a pending choice stops before any write.
 * Then each skill commits under one concurrency lock. If any skill fails, every skill in
 * the batch rolls back and the state and project lock return to their earlier bytes.
 * The project lock is written once, after every skill has committed.
 *
 * @param {object} params Same as executeProjectInstall, with `skillIds` instead of `skillId`
 * @returns {object[]} One execution summary per skill, in order
 */
export function executeProjectInstallBatch(params) {
  const { skillIds, dryRun = false, ...rest } = params;
  const plans = skillIds.map((skillId) => executeProjectInstall({ ...rest, skillId, dryRun: true }).plan);
  if (dryRun) return plans.map((plan) => ({ success: true, dryRun: true, plan }));
  const pending = plans.find((plan) => plan.requiresApproval);
  if (pending) throw createNeedsResolutionError(pending);

  migrateStateForCommand(params);
  const scope = rest.scope || 'project';
  const root = path.resolve(scope === 'global'
    ? rest.homeDir || resolveHomeDir(rest.env || process.env)
    : rest.projectRoot || process.cwd());
  const batch = { rollbacks: [], finalizers: [], lockSkills: [] };
  const releaseLock = acquireConcurrencyLock(root, rest.customStateDir);
  const rollbackAll = () => {
    for (const rollback of batch.rollbacks.splice(0).reverse()) rollback();
  };

  try {
    let results;
    try {
      results = skillIds.map((skillId) => executeProjectInstall({ ...rest, skillId, batch }));
      if (batch.lockSkills.length > 0) {
        let lock = loadProjectLock(root);
        for (const [skillId, revision, release] of batch.lockSkills) {
          lock = updateProjectLockSkill(lock, skillId, revision, release);
        }
        saveProjectLock(root, lock);
      }
    } catch (err) {
      rollbackAll();
      throw err;
    }
    for (const finalize of batch.finalizers) finalize();
    return results;
  } finally {
    releaseLock();
  }
}
