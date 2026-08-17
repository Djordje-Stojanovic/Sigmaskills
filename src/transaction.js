import fs from 'node:fs';
import path from 'node:path';
import { findPackageRoot, validateSkill } from './catalog.js';
import { createInstallPlan } from './plan.js';
import { loadProjectLock, saveProjectLock, updateProjectLockSkill, PROJECT_LOCK_FILENAME } from './project-lock.js';
import {
  getProjectStateDir,
  getProjectStatePath,
  loadProjectState,
  saveProjectState,
  recordSkillInState,
} from './state.js';

/**
 * Acquire process concurrency lock for project.
 *
 * @param {string} projectRoot
 * @param {string} [customStateDir]
 * @returns {() => void} Release lock function
 */
export function acquireConcurrencyLock(projectRoot, customStateDir) {
  const stateDir = getProjectStateDir(projectRoot, customStateDir);
  if (!fs.existsSync(stateDir)) {
    fs.mkdirSync(stateDir, { recursive: true });
  }

  const lockPath = path.join(stateDir, '.sigma.lock');

  function tryCreateLock() {
    try {
      const fd = fs.openSync(lockPath, 'wx');
      const payload = JSON.stringify({
        pid: process.pid,
        createdAt: new Date().toISOString(),
      });
      fs.writeFileSync(fd, payload, 'utf8');
      fs.closeSync(fd);
      return true;
    } catch (err) {
      if (err.code === 'EEXIST') {
        return false;
      }
      throw err;
    }
  }

  if (!tryCreateLock()) {
    // Check if existing lock is stale
    try {
      const existing = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
      const isAlive = isProcessAlive(existing.pid);
      if (isAlive) {
        throw new Error(
          `Concurrent SigmaSkills operation in progress (PID ${existing.pid}). Aborting to prevent corruption.`,
        );
      }
      // Stale lock from dead process: remove and retry
      fs.unlinkSync(lockPath);
      if (!tryCreateLock()) {
        throw new Error('Failed to acquire lock after clearing stale lock file.');
      }
    } catch (readErr) {
      if (readErr.message.includes('Concurrent SigmaSkills operation')) {
        throw readErr;
      }
      // If reading/parsing failed, attempt unlink and recreate
      try {
        fs.unlinkSync(lockPath);
        if (!tryCreateLock()) {
          throw new Error('Failed to acquire lock.');
        }
      } catch {
        throw new Error(`Failed to acquire project lock at ${lockPath}: ${readErr.message}`);
      }
    }
  }

  let released = false;
  return function releaseLock() {
    if (released) return;
    released = true;
    try {
      if (fs.existsSync(lockPath)) {
        const existing = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
        if (existing.pid === process.pid) {
          fs.unlinkSync(lockPath);
        }
      }
    } catch {
      // Best-effort cleanup
    }
  };
}

/**
 * Check if a process ID is currently running.
 *
 * @param {number} pid
 * @returns {boolean}
 */
function isProcessAlive(pid) {
  if (!pid || typeof pid !== 'number') return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err.code === 'EPERM'; // Process exists but no permission
  }
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
  const {
    catalog,
    skillId,
    customStateDir,
    dryRun = false,
  } = params;

  const projectRoot = path.resolve(params.projectRoot || process.cwd());
  const packageRoot = params.packageRoot || findPackageRoot();

  const plan = createInstallPlan(catalog, {
    skillId,
    projectRoot,
    customStateDir,
    packageRoot,
    dryRun,
    selectedRoots: params.selectedRoots,
    destinationGroups: params.destinationGroups,
    registry: params.registry,
    env: params.env,
  });

  if (plan.unownedConflict) throw createUnownedConflictError(plan);

  if (dryRun) {
    return {
      success: true,
      dryRun: true,
      plan,
    };
  }

  const releaseLock = acquireConcurrencyLock(projectRoot, customStateDir);

  const stagingParent = path.join(projectRoot, '.agents', '.sigma-staging');
  const stagingDir = path.join(
    stagingParent,
    `${skillId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  );

  const committed = [];

  const lockPath = path.join(projectRoot, PROJECT_LOCK_FILENAME);
  const lockExisted = fs.existsSync(lockPath);
  const originalLock = loadProjectLock(projectRoot);

  const statePath = getProjectStatePath(projectRoot, customStateDir);
  const stateExisted = fs.existsSync(statePath);
  const originalState = loadProjectState(projectRoot, customStateDir);

  const cleanupStaging = () => {
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
  };

  const rollback = () => {
    try {
      for (const entry of committed.splice(0).reverse()) {
        try {
          if (entry.backupDir && fs.existsSync(entry.backupDir)) {
            if (fs.existsSync(entry.destDir)) {
              fs.rmSync(entry.destDir, { recursive: true, force: true });
            }
            fs.renameSync(entry.backupDir, entry.destDir);
          } else if (fs.existsSync(entry.destDir)) {
            fs.rmSync(entry.destDir, { recursive: true, force: true });
          }
        } catch {
          // Per-destination rollback is best-effort
        }
      }
      // Restore state and lock or remove if they didn't exist before
      if (stateExisted) {
        saveProjectState(projectRoot, originalState, customStateDir);
      } else if (fs.existsSync(statePath)) {
        fs.unlinkSync(statePath);
      }

      if (lockExisted) {
        saveProjectLock(projectRoot, originalLock);
      } else if (fs.existsSync(lockPath)) {
        fs.unlinkSync(lockPath);
      }
    } catch {
      // Rollback is best-effort
    } finally {
      cleanupStaging();
      releaseLock();
    }
  };

  // Register signal listeners during transaction
  const signalHandler = () => {
    rollback();
    process.exit(130);
  };
  process.once('SIGINT', signalHandler);
  process.once('SIGTERM', signalHandler);

  try {
    // 1. Stage skill files on destination volume
    fs.mkdirSync(stagingDir, { recursive: true });
    const sourceSkillDir = path.join(packageRoot, skillId);
    if (!fs.existsSync(sourceSkillDir)) {
      throw new Error(`source skill directory missing at ${sourceSkillDir}`);
    }

    fs.cpSync(sourceSkillDir, stagingDir, { recursive: true });

    // 2. Validate staged tree before touching live destination
    const manifestMetadata = catalog.manifest.skills.find((s) => s.id === skillId);
    const validatedStaged = validateSkill(stagingDir, manifestMetadata);
    if (validatedStaged.revision !== plan.sourceRevision) {
      throw new Error(
        `staged skill revision '${validatedStaged.revision}' does not match catalog revision '${plan.sourceRevision}'`,
      );
    }

    // 3. Copy the staged tree into every selected destination
    const commitDestination = (destDir) => {
      const destParent = path.dirname(destDir);
      if (!fs.existsSync(destParent)) {
        fs.mkdirSync(destParent, { recursive: true });
      }

      let backupDir = null;
      if (fs.existsSync(destDir)) {
        backupDir = path.join(
          destParent,
          `.${skillId}-backup-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        );
        fs.renameSync(destDir, backupDir);
      }

      try {
        fs.cpSync(stagingDir, destDir, { recursive: true });
        committed.push({ destDir, backupDir });
      } catch (copyErr) {
        if (backupDir && fs.existsSync(backupDir)) {
          if (fs.existsSync(destDir)) {
            fs.rmSync(destDir, { recursive: true, force: true });
          }
          fs.renameSync(backupDir, destDir);
        } else if (fs.existsSync(destDir)) {
          fs.rmSync(destDir, { recursive: true, force: true });
        }
        throw new Error(`failed to write destination '${destDir}': ${copyErr.message}`);
      }
    };

    for (const dest of plan.destinations) {
      commitDestination(dest.destination);
    }

    const copies = plan.destinations.map((dest) => ({
      kind: dest.kind,
      destination: dest.relativeDestination,
      hostIds: (dest.hosts || []).map((host) => host.id),
      ownedPaths: plan.files.map((file) => `${dest.relativeDestination}/${file}`),
    }));
    const primary = copies.find((copy) => copy.kind === 'canonical') || copies[0];

    // 4. Update private state and project lock
    const updatedState = recordSkillInState(originalState, {
      skillId,
      release: plan.release,
      revision: plan.sourceRevision,
      method: plan.method,
      destination: primary.destination,
      projectRoot,
      ownedPaths: primary.ownedPaths,
      baseHashes: validatedStaged.files,
      copies,
    });
    saveProjectState(projectRoot, updatedState, customStateDir);

    const updatedLock = updateProjectLockSkill(
      originalLock,
      skillId,
      plan.sourceRevision,
      plan.release,
    );
    saveProjectLock(projectRoot, updatedLock);

    // 5. Cleanup backups after state & lock write succeed
    for (const entry of committed) {
      if (entry.backupDir && fs.existsSync(entry.backupDir)) {
        fs.rmSync(entry.backupDir, { recursive: true, force: true });
        entry.backupDir = null;
      }
    }

    cleanupStaging();
    releaseLock();

    return {
      success: true,
      dryRun: false,
      plan,
      lock: updatedLock,
      state: updatedState,
    };
  } catch (err) {
    rollback();
    throw err;
  } finally {
    process.removeListener('SIGINT', signalHandler);
    process.removeListener('SIGTERM', signalHandler);
    cleanupStaging();
    releaseLock();
  }
}
