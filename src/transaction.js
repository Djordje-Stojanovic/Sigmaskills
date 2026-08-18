import fs from 'node:fs';
import path from 'node:path';
import { findPackageRoot, validateSkill } from './catalog.js';
import { injectCustomContent, injectRawCustomContent } from './customization.js';
import { commitSkillBackup, exportSkillTree, pruneOlderBackups } from './backup.js';
import { createInstallPlan } from './plan.js';
import { loadProjectLock, saveProjectLock, updateProjectLockSkill, PROJECT_LOCK_FILENAME } from './project-lock.js';
import { resolveHomeDir } from './destinations.js';
import {
  getGlobalStateDir,
  getGlobalStatePath,
  getProjectStateDir,
  getProjectStatePath,
  loadGlobalState,
  loadProjectState,
  saveGlobalState,
  saveProjectState,
  recordSkillInState,
} from './state.js';
import { createSkillLink, pathExists, removeManagedPath } from './links.js';

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

  if (plan.unownedConflict) throw createUnownedConflictError(plan);

  if (dryRun) {
    return {
      success: true,
      dryRun: true,
      plan,
    };
  }

  if (plan.requiresApproval) throw createNeedsResolutionError(plan);

  const releaseLock = acquireConcurrencyLock(root, customStateDir);

  const stagingParent = path.join(root, '.agents', '.sigma-staging');
  const stagingDir = path.join(
    stagingParent,
    `${skillId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  );

  const committed = [];
  const privateBackups = [];

  const useProjectLock = scope !== 'global';
  const lockPath = path.join(root, PROJECT_LOCK_FILENAME);
  const lockExisted = useProjectLock && fs.existsSync(lockPath);
  const originalLockBytes = lockExisted ? fs.readFileSync(lockPath) : null;
  const originalLock = useProjectLock ? loadProjectLock(root) : { skills: {} };

  const statePath = scope === 'global'
    ? getGlobalStatePath(root, customStateDir)
    : getProjectStatePath(root, customStateDir);
  const stateExisted = fs.existsSync(statePath);
  const originalStateBytes = stateExisted ? fs.readFileSync(statePath) : null;
  const originalState = scope === 'global'
    ? loadGlobalState(root, customStateDir)
    : loadProjectState(root, customStateDir);
  const persistState = params.saveState || (scope === 'global' ? saveGlobalState : saveProjectState);
  const stateDirForBackups = scope === 'global'
    ? getGlobalStateDir(root, customStateDir)
    : getProjectStateDir(root, customStateDir);

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
      for (const backupPath of privateBackups.splice(0)) {
        try {
          if (pathExists(backupPath)) removeManagedPath(backupPath);
        } catch {
          // Private backup cleanup is best-effort
        }
      }
      // Restore state and lock or remove if they didn't exist before
      if (stateExisted && originalStateBytes) {
        fs.writeFileSync(statePath, originalStateBytes);
      } else if (fs.existsSync(statePath)) {
        fs.unlinkSync(statePath);
      }

      if (useProjectLock && lockExisted && originalLockBytes) {
        fs.writeFileSync(lockPath, originalLockBytes);
      } else if (useProjectLock && fs.existsSync(lockPath)) {
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
    const willWrite = (dest) => (
      !dest.adoption
      && dest.resolution !== 'skip'
      && dest.resolution !== 'export'
    );
    const allAdopted = plan.destinations.every((dest) => dest.adoption);
    const needsSkillWrite = plan.destinations.some(willWrite);
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
    if (allAdopted && sameManagedLayout) {
      cleanupStaging();
      releaseLock();
      return {
        success: true,
        dryRun: false,
        plan,
        lock: originalLock,
        state: originalState,
      };
    }

    const catalogSkill = catalog.skills.find((item) => item.id === skillId);
    let fileHashes = catalogSkill?.files || {};

    if (needsSkillWrite) {
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
      if (params.preservedCustomRaw !== undefined) {
        const stagedSkillMd = path.join(stagingDir, 'SKILL.md');
        if (pathExists(stagedSkillMd)) {
          const stagedMarkdown = fs.readFileSync(stagedSkillMd, 'utf8');
          fs.writeFileSync(
            stagedSkillMd,
            injectRawCustomContent(stagedMarkdown, params.preservedCustomRaw, skillId),
            'utf8',
          );
        }
      }
    }

    const createLink = params.createLink || ((linkPath, targetPath) => (
      createSkillLink(linkPath, targetPath, root)
    ));
    const canonicalDest = plan.destinations.find((dest) => dest.kind === 'canonical')
      || plan.destinations[0];

    const restoreBackup = (destDir, backupDir) => {
      if (backupDir && pathExists(backupDir)) {
        if (pathExists(destDir)) removeManagedPath(destDir);
        fs.renameSync(backupDir, destDir);
      } else if (pathExists(destDir)) {
        removeManagedPath(destDir);
      }
    };

    const prepareDestination = (destDir) => {
      const destParent = path.dirname(destDir);
      if (!fs.existsSync(destParent)) {
        fs.mkdirSync(destParent, { recursive: true });
      }
      let backupDir = null;
      if (pathExists(destDir)) {
        backupDir = path.join(
          destParent,
          `.${skillId}-backup-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        );
        fs.renameSync(destDir, backupDir);
      }
      return backupDir;
    };

    const commitCopy = (destDir) => {
      const backupDir = prepareDestination(destDir);
      try {
        fs.cpSync(stagingDir, destDir, { recursive: true });
        committed.push({ destDir, backupDir });
      } catch (copyErr) {
        restoreBackup(destDir, backupDir);
        throw new Error(`failed to write destination '${destDir}': ${copyErr.message}`);
      }
    };

    const commitLink = (dest) => {
      const destDir = dest.destination;
      const backupDir = prepareDestination(destDir);
      try {
        createLink(destDir, canonicalDest.destination, root);
        committed.push({ destDir, backupDir });
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
        commitCopy(destDir);
      }
    };

    const ordered = [...plan.destinations].sort((a, b) => {
      if (a.kind === 'canonical' && b.kind !== 'canonical') return -1;
      if (b.kind === 'canonical' && a.kind !== 'canonical') return 1;
      return 0;
    });

    for (const dest of ordered) {
      if (dest.adoption) {
        committed.push({ destDir: dest.destination, backupDir: null, adopted: true });
        continue;
      }
      if (dest.resolution === 'skip') {
        dest.exportPath = null;
        continue;
      }
      if (dest.resolution === 'export') {
        const exportRoot = plan.exportDir || path.join(root, '.sigma-export');
        const exporter = params.exportSkill || exportSkillTree;
        dest.exportPath = exporter({
          sourceDir: dest.destination,
          exportRoot,
          skillId,
          dest: dest.exportPath,
        });
        continue;
      }
      if (dest.resolution === 'replace' && pathExists(dest.destination)) {
        const backupFn = params.backupSkill || commitSkillBackup;
        const privateBackup = backupFn({
          stateDir: stateDirForBackups,
          skillId,
          sourceDir: dest.destination,
        });
        privateBackups.push(privateBackup);
        dest.privateBackup = privateBackup;
        if (typeof params.afterBackup === 'function') {
          params.afterBackup(privateBackup);
        }
      }
      if (dest.method === 'copy') commitCopy(dest.destination);
      else commitLink(dest);
      const customStatus = dest.customization?.status;
      if (
        params.preservedCustomRaw === undefined
        && dest.resolution === 'replace'
        && (customStatus === 'valid' || customStatus === 'empty')
      ) {
        const skillMd = path.join(dest.destination, 'SKILL.md');
        if (pathExists(skillMd)) {
          const current = fs.readFileSync(skillMd, 'utf8');
          fs.writeFileSync(
            skillMd,
            injectCustomContent(current, dest.customization.customContent || '', skillId),
            'utf8',
          );
        }
      }
    }

    const copies = plan.destinations
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
    if (copies.length === 0) {
      cleanupStaging();
      releaseLock();
      return {
        success: true,
        dryRun: false,
        plan,
        lock: originalLock,
        state: originalState,
      };
    }
    const primary = copies.find((copy) => copy.kind === 'canonical') || copies[0];

    const lastBackup = privateBackups.length > 0
      ? path.relative(stateDirForBackups, privateBackups[privateBackups.length - 1]).replace(/\\/g, '/')
      : undefined;
    const updatedState = recordSkillInState(originalState, {
      skillId,
      release: plan.release,
      revision: plan.sourceRevision,
      method: plan.method,
      destination: primary.destination,
      projectRoot: root,
      ownedPaths: primary.ownedPaths,
      baseHashes: primary.baseHashes || fileHashes,
      copies,
      scope,
      lastBackup,
    });
    persistState(root, updatedState, customStateDir);

    let updatedLock = originalLock;
    if (useProjectLock) {
      updatedLock = updateProjectLockSkill(
        originalLock,
        skillId,
        plan.sourceRevision,
        plan.release,
      );
      saveProjectLock(root, updatedLock);
    }

    // 5. Cleanup backups after state & lock write succeed
    for (const entry of committed) {
      if (entry.backupDir && pathExists(entry.backupDir)) {
        removeManagedPath(entry.backupDir);
        entry.backupDir = null;
      }
    }
    for (const backupPath of privateBackups) {
      pruneOlderBackups({
        stateDir: stateDirForBackups,
        skillId,
        keepPath: backupPath,
      });
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
