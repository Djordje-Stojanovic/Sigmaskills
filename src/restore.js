import fs from 'node:fs';
import path from 'node:path';
import {
  BACKUP_METADATA_NAME,
  commitSkillBackup,
  copySkillTree,
  findLatestBackupDir,
  inventoriesMatch,
  inventorySkillTree,
  pruneOlderBackups,
  verifyBackupIntegrity,
} from './backup.js';
import { resolveHomeDir } from './destinations.js';
import { createSkillLink, pathExists, removeManagedPath } from './links.js';
import { loadProjectLock, saveProjectLock, updateProjectLockSkill } from './project-lock.js';
import { computeSkillRevisionAndHashes } from './revision.js';
import {
  getGlobalStateDir,
  getProjectStateDir,
  loadGlobalState,
  loadProjectState,
  recordSkillInState,
  saveGlobalState,
  saveProjectState,
} from './state.js';
import { acquireConcurrencyLock } from './transaction.js';

export const RESTORE_SCHEMA_VERSION = 1;

function codedError(message, code) {
  const err = new Error(message);
  err.code = code;
  return err;
}

function resolveRoot(options) {
  const scope = options.scope || 'project';
  if (scope === 'global') return path.resolve(options.homeDir || resolveHomeDir(options.env || process.env));
  return path.resolve(options.projectRoot || process.cwd());
}

function resolveStateDir(scope, root, customStateDir) {
  return scope === 'global'
    ? getGlobalStateDir(root, customStateDir)
    : getProjectStateDir(root, customStateDir);
}

function loadState(scope, root, customStateDir) {
  return scope === 'global'
    ? loadGlobalState(root, customStateDir)
    : loadProjectState(root, customStateDir);
}

function recordedCopyDestinations(entry) {
  const destinations = [];
  if (entry?.destination) destinations.push(String(entry.destination).replace(/\\/g, '/'));
  if (Array.isArray(entry?.copies)) {
    for (const copy of entry.copies) {
      if (copy?.destination) destinations.push(String(copy.destination).replace(/\\/g, '/'));
    }
  }
  return destinations;
}

function ownerOfPath(state, relativePath) {
  const wanted = String(relativePath || '').replace(/\\/g, '/');
  for (const [skillId, entry] of Object.entries(state.skills || {})) {
    if (recordedCopyDestinations(entry).includes(wanted)) return skillId;
  }
  return null;
}

function previewFrom(metadata, sizeBytes, backupDir) {
  const copies = Array.isArray(metadata.copies) ? metadata.copies : [];
  const links = copies
    .filter((copy) => copy.method && copy.method !== 'copy')
    .map((copy) => ({
      destination: copy.destination,
      method: copy.method,
    }));
  const managedCopies = copies
    .filter((copy) => !copy.method || copy.method === 'copy')
    .map((copy) => ({
      destination: copy.destination,
      kind: copy.kind || 'canonical',
    }));
  return {
    release: metadata.release || null,
    revision: metadata.revision || null,
    createdAt: metadata.createdAt || null,
    sizeBytes,
    scope: metadata.scope || null,
    canonicalTarget: metadata.canonicalTarget || null,
    backupDir,
    links,
    copies: managedCopies,
  };
}

function classifyRestoreSkill(options, skillId) {
  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const stateDir = resolveStateDir(scope, root, options.customStateDir);
  const state = loadState(scope, root, options.customStateDir);
  const entry = state.skills?.[skillId];
  const backupDir = findLatestBackupDir({
    stateDir,
    skillId,
    lastBackup: entry?.lastBackup,
  });
  const fallbackRel = entry?.destination || `.agents/skills/${skillId}`;

  try {
    const verified = verifyBackupIntegrity({ backupDir, skillId });
    const metadata = verified.metadata;
    const canonicalRel = metadata.canonicalTarget || fallbackRel;
    const canonicalAbs = path.resolve(root, ...canonicalRel.split('/'));
    const blockedReasons = [];

    if (metadata.scope && metadata.scope !== scope) {
      blockedReasons.push('stale-ownership');
    }

    const claimed = [
      canonicalRel,
      ...(Array.isArray(metadata.ownedPaths) ? metadata.ownedPaths : []),
      ...(Array.isArray(metadata.copies) ? metadata.copies.map((copy) => copy.destination).filter(Boolean) : []),
    ].map((item) => String(item).replace(/\\/g, '/'));

    for (const rel of claimed) {
      const owner = ownerOfPath(state, rel);
      if (owner && owner !== skillId) {
        blockedReasons.push('stale-ownership');
        break;
      }
    }

    const liveExists = pathExists(canonicalAbs);
    const weOwn = ownerOfPath(state, canonicalRel) === skillId;
    if (liveExists && !weOwn) {
      blockedReasons.push('occupied-unowned');
    }

    const needed = Math.max(verified.sizeBytes, 1) * 3;
    const statfs = options.statfs || (typeof fs.statfsSync === 'function' ? fs.statfsSync.bind(fs) : null);
    if (typeof statfs === 'function') {
      try {
        const parent = pathExists(path.dirname(canonicalAbs)) ? path.dirname(canonicalAbs) : root;
        const stat = statfs(parent);
        const available = Number(stat.bavail) * Number(stat.bsize);
        if (Number.isFinite(available) && available < needed) {
          blockedReasons.push('insufficient-space');
        }
      } catch {
        // Filesystems without statfs still attempt the restore; explicit hooks can fail closed.
      }
    }

    const liveInventory = liveExists ? inventorySkillTree(canonicalAbs) : { entries: {} };
    const identical = liveExists && inventoriesMatch(liveInventory, verified.inventory);
    const uniqueReasons = [...new Set(blockedReasons)];
    return {
      id: skillId,
      backupDir,
      metadata,
      canonicalRel,
      canonicalAbs,
      preview: previewFrom(metadata, verified.sizeBytes, backupDir),
      identical,
      blocked: uniqueReasons.length > 0,
      blockedReasons: uniqueReasons,
      action: uniqueReasons.length > 0 ? 'blocked' : (identical ? 'no-op' : 'restore'),
    };
  } catch (err) {
    const code = err.code || 'missing';
    const reason = code === 'schema' ? 'schema-incompatible' : code;
    return {
      id: skillId,
      backupDir,
      metadata: null,
      canonicalRel: fallbackRel,
      canonicalAbs: path.resolve(root, ...fallbackRel.split('/')),
      preview: {
        release: null,
        revision: null,
        createdAt: null,
        sizeBytes: 0,
        scope,
        canonicalTarget: entry?.destination || null,
        backupDir,
        links: [],
        copies: [],
      },
      identical: false,
      blocked: true,
      blockedReasons: [reason],
      action: 'blocked',
      error: err.message,
    };
  }
}

/**
 * Preview restore of the latest retained backup for selected skills.
 *
 * @param {object} options
 * @returns {object}
 */
export function createRestorePlan(options = {}) {
  const scope = options.scope || 'project';
  const skillIds = Array.isArray(options.skillIds) ? options.skillIds.filter(Boolean) : [];
  return {
    schemaVersion: RESTORE_SCHEMA_VERSION,
    command: 'restore',
    scope,
    dryRun: Boolean(options.dryRun),
    skills: skillIds.map((skillId) => classifyRestoreSkill(options, skillId)),
  };
}

function swapLiveTree(staged, live, options) {
  const rename = options.renameDirectory || ((from, to) => fs.renameSync(from, to));
  const copy = options.copyDirectory || ((from, to) => {
    fs.mkdirSync(path.dirname(to), { recursive: true });
    copySkillTree(from, to);
  });
  const displaced = `${live}.sigma-displace-${process.pid}-${Date.now()}`;
  const incoming = `${live}.sigma-incoming-${process.pid}-${Date.now()}`;
  const liveExisted = pathExists(live);

  const restoreDisplaced = () => {
    if (pathExists(displaced) && !pathExists(live)) {
      try {
        fs.renameSync(displaced, live);
      } catch {
        copySkillTree(displaced, live);
      }
    }
    if (pathExists(incoming)) {
      try {
        fs.rmSync(incoming, { recursive: true, force: true });
      } catch {
        // Incoming cleanup is best-effort.
      }
    }
  };

  try {
    if (liveExisted) {
      try {
        rename(live, displaced);
      } catch (err) {
        try {
          copy(staged, incoming);
          try {
            rename(live, displaced);
          } catch (liveErr) {
            throw codedError(
              `Windows fallback failed: ${liveErr.message}`,
              liveErr.code || err.code || 'fallback',
            );
          }
          try {
            rename(incoming, live);
          } catch {
            copy(incoming, live);
            fs.rmSync(incoming, { recursive: true, force: true });
          }
          if (pathExists(displaced)) fs.rmSync(displaced, { recursive: true, force: true });
          if (pathExists(staged)) fs.rmSync(staged, { recursive: true, force: true });
          return;
        } catch (fallbackErr) {
          restoreDisplaced();
          throw codedError(
            `Windows fallback failed: ${fallbackErr.message}`,
            fallbackErr.code || err.code || 'fallback',
          );
        }
      }
    }

    try {
      rename(staged, live);
    } catch (err) {
      try {
        copy(staged, live);
        if (pathExists(staged)) fs.rmSync(staged, { recursive: true, force: true });
      } catch (fallbackErr) {
        restoreDisplaced();
        throw codedError(
          `Windows fallback failed: ${fallbackErr.message}`,
          fallbackErr.code || err.code || 'fallback',
        );
      }
    }
    if (pathExists(displaced)) fs.rmSync(displaced, { recursive: true, force: true });
  } catch (err) {
    restoreDisplaced();
    throw err;
  }
}

function applyOwnedCopies(root, skill) {
  const copies = Array.isArray(skill.metadata?.copies) ? skill.metadata.copies : [];
  for (const copy of copies) {
    const rel = String(copy.destination || '').replace(/\\/g, '/');
    if (!rel || rel === skill.canonicalRel) continue;
    const abs = path.resolve(root, ...rel.split('/'));
    if (copy.method && copy.method !== 'copy') {
      if (pathExists(abs)) removeManagedPath(abs);
      createSkillLink(abs, skill.canonicalAbs, root);
      continue;
    }
    if (copy.kind === 'host' || copy.method === 'copy') {
      if (pathExists(abs)) removeManagedPath(abs);
      copySkillTree(skill.canonicalAbs, abs);
    }
  }
}

function applyOneRestore(options, skill, state) {
  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const stateDir = resolveStateDir(scope, root, options.customStateDir);
  const stagingParent = path.join(stateDir, '.sigma-restore-staging');
  const stagingDir = path.join(
    stagingParent,
    `${skill.id}-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  );
  let undoBackup = null;

  const cleanupStaging = () => {
    try {
      if (pathExists(stagingDir)) fs.rmSync(stagingDir, { recursive: true, force: true });
      if (pathExists(stagingParent) && fs.readdirSync(stagingParent).length === 0) {
        fs.rmSync(stagingParent, { recursive: true, force: true });
      }
    } catch {
      // Staging cleanup is best-effort.
    }
  };

  try {
    copySkillTree(skill.backupDir, stagingDir);
    if (pathExists(path.join(stagingDir, BACKUP_METADATA_NAME))) {
      fs.unlinkSync(path.join(stagingDir, BACKUP_METADATA_NAME));
    }
    if (!inventoriesMatch(inventorySkillTree(stagingDir), inventorySkillTree(skill.backupDir))) {
      throw codedError(`tampered backup for '${skill.id}'`, 'tampered');
    }
    if (typeof options.afterStage === 'function') options.afterStage(stagingDir);

    if (pathExists(skill.canonicalAbs)) {
      const backupFn = options.backupSkill || commitSkillBackup;
      undoBackup = backupFn({
        stateDir,
        skillId: skill.id,
        sourceDir: skill.canonicalAbs,
        ownership: {
          scope,
          release: state.skills?.[skill.id]?.release || null,
          revision: state.skills?.[skill.id]?.revision || null,
          method: state.skills?.[skill.id]?.method || skill.metadata.method,
          canonicalTarget: skill.canonicalRel,
          copies: state.skills?.[skill.id]?.copies || skill.metadata.copies || [],
          ownedPaths: state.skills?.[skill.id]?.ownedPaths || skill.metadata.ownedPaths || [skill.canonicalRel],
        },
      });
    }

    swapLiveTree(stagingDir, skill.canonicalAbs, options);
    applyOwnedCopies(root, skill);
    cleanupStaging();
    return undoBackup;
  } catch (err) {
    if (undoBackup && pathExists(undoBackup)) {
      try {
        fs.rmSync(undoBackup, { recursive: true, force: true });
      } catch {
        // Drop the unused undo snapshot so the retained backup stays the latest.
      }
    }
    cleanupStaging();
    throw err;
  }
}

function recordRestoredSkill(state, skill, root, undoBackup, stateDir) {
  const computed = computeSkillRevisionAndHashes(skill.canonicalAbs);
  const copies = Array.isArray(skill.metadata.copies) && skill.metadata.copies.length > 0
    ? skill.metadata.copies
    : [{
      kind: 'canonical',
      destination: skill.canonicalRel,
      method: skill.metadata.method || 'copy',
      dependsOn: null,
      hostIds: [],
      ownedPaths: skill.metadata.ownedPaths || [skill.canonicalRel],
    }];
  const primary = copies.find((copy) => copy.kind === 'canonical') || copies[0];
  const backupAbs = undoBackup || skill.backupDir;
  const lastBackup = backupAbs
    ? path.relative(stateDir, backupAbs).replace(/\\/g, '/')
    : null;
  return recordSkillInState(state, {
    skillId: skill.id,
    release: skill.metadata.release || null,
    revision: skill.metadata.revision || computed.revision,
    method: skill.metadata.method || primary.method || 'copy',
    destination: primary.destination || skill.canonicalRel,
    projectRoot: root,
    ownedPaths: skill.metadata.ownedPaths || primary.ownedPaths || [skill.canonicalRel],
    baseHashes: computed.files,
    copies,
    lastBackup,
    cleanupDebt: [],
  });
}

/**
 * Restore the latest retained backup for selected skills.
 *
 * @param {object} options
 * @returns {object}
 */
export function executeRestore(options = {}) {
  const plan = createRestorePlan(options);
  if (options.dryRun) {
    return { ...plan, dryRun: true };
  }

  const blocked = plan.skills.filter((skill) => skill.blocked);
  if (blocked.length > 0) {
    const reasons = blocked.map((skill) => `${skill.id}: ${skill.blockedReasons.join(', ')}`).join('; ');
    const first = blocked[0].blockedReasons[0];
    const message = first === 'insufficient-space'
      ? `insufficient space to restore: ${reasons}`
      : first === 'occupied-unowned'
        ? `occupied-unowned destination stopped restore: ${reasons}`
        : first === 'stale-ownership'
          ? `stale-ownership stopped restore: ${reasons}`
          : first === 'schema-incompatible'
            ? `schema-incompatible backup stopped restore: ${reasons}`
            : blocked[0].error || `restore stopped: ${reasons}`;
    throw codedError(message, first);
  }

  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const customStateDir = options.customStateDir;
  const releaseLock = acquireConcurrencyLock(root, customStateDir);
  let state = loadState(scope, root, customStateDir);

  try {
    for (const skill of plan.skills) {
      if (skill.identical) {
        skill.action = 'no-op';
        continue;
      }
      const undoBackup = applyOneRestore(options, skill, state);
      state = recordRestoredSkill(state, skill, root, undoBackup, resolveStateDir(scope, root, customStateDir));
      const persist = options.saveState || (scope === 'global' ? saveGlobalState : saveProjectState);
      persist(root, state, customStateDir);
      if (scope !== 'global' && skill.metadata.revision) {
        const lock = loadProjectLock(root);
        saveProjectLock(root, updateProjectLockSkill(lock, skill.id, skill.metadata.revision, skill.metadata.release));
      }
      if (undoBackup) {
        pruneOlderBackups({
          stateDir: resolveStateDir(scope, root, customStateDir),
          skillId: skill.id,
          keepPath: undoBackup,
        });
      }
      skill.action = 'restored';
    }
    return { ...plan, dryRun: false, state };
  } finally {
    releaseLock();
  }
}

/**
 * @param {object} result
 * @returns {string}
 */
export function formatRestoreJson(result) {
  return `${JSON.stringify(result, null, 2)}\n`;
}

/**
 * @param {object} result
 * @returns {string}
 */
export function formatRestoreHuman(result) {
  const lines = [
    `SigmaSkills Restore ${result.dryRun ? 'Preview' : 'Result'}`,
    `Scope: ${result.scope}`,
    '',
  ];
  for (const skill of result.skills || []) {
    lines.push(`Skill: ${skill.id}`);
    lines.push(`  Action: ${skill.action}`);
    if (skill.preview?.release) lines.push(`  Release: ${skill.preview.release}`);
    if (skill.preview?.revision) lines.push(`  Revision: ${skill.preview.revision}`);
    if (skill.preview?.createdAt) lines.push(`  Created: ${skill.preview.createdAt}`);
    if (skill.preview?.sizeBytes) lines.push(`  Size: ${skill.preview.sizeBytes} bytes`);
    if (skill.preview?.scope) lines.push(`  Backup scope: ${skill.preview.scope}`);
    if (skill.preview?.canonicalTarget) lines.push(`  Canonical target: ${skill.preview.canonicalTarget}`);
    const links = (skill.preview?.links || []).map((link) => link.destination).join(', ');
    const copies = (skill.preview?.copies || []).map((copy) => copy.destination).join(', ');
    lines.push(`  Links: ${links || 'none'}`);
    lines.push(`  Copies: ${copies || 'none'}`);
    if (skill.blockedReasons?.length) lines.push(`  Blocked: ${skill.blockedReasons.join(', ')}`);
    lines.push('');
  }
  return lines.join('\n');
}
