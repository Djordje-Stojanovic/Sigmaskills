import fs from 'node:fs';
import path from 'node:path';
import { pathExists } from './links.js';

/**
 * @param {string} stateDir
 * @returns {string}
 */
export function getBackupRoot(stateDir) {
  return path.join(stateDir, 'backups');
}

function filesystemSafeStamp(now = new Date()) {
  return now.toISOString().replace(/[:.]/g, '-');
}

/**
 * Copy a complete skill tree into private Sigma state. Does not write beside the live skill.
 *
 * @param {object} params
 * @returns {string} Backup directory
 */
export function commitSkillBackup(params) {
  const { stateDir, skillId, sourceDir, now = new Date() } = params;
  if (!pathExists(sourceDir)) {
    throw new Error(`cannot backup missing skill tree at ${sourceDir}`);
  }
  const dest = path.join(getBackupRoot(stateDir), skillId, filesystemSafeStamp(now));
  fs.mkdirSync(dest, { recursive: true });
  fs.cpSync(sourceDir, dest, { recursive: true });
  return dest;
}

/**
 * Keep only the newly committed backup for a skill after the operation succeeds.
 *
 * @param {object} params
 */
export function pruneOlderBackups(params) {
  const { stateDir, skillId, keepPath } = params;
  const dir = path.join(getBackupRoot(stateDir), skillId);
  if (!pathExists(dir)) return;
  const keep = path.resolve(keepPath);
  for (const name of fs.readdirSync(dir)) {
    const full = path.resolve(dir, name);
    if (full !== keep) {
      fs.rmSync(full, { recursive: true, force: true });
    }
  }
}

/**
 * @param {string} exportRoot
 * @param {string} skillId
 * @returns {string}
 */
export function plannedExportDir(exportRoot, skillId) {
  const primary = path.join(exportRoot, skillId);
  if (!pathExists(primary)) return primary;
  let n = 2;
  while (pathExists(path.join(exportRoot, `${skillId}-${n}`))) {
    n += 1;
  }
  return path.join(exportRoot, `${skillId}-${n}`);
}

/**
 * @param {string} exportRoot
 * @param {string} skillId
 * @returns {string}
 */
export function collisionSafeExportDir(exportRoot, skillId) {
  fs.mkdirSync(exportRoot, { recursive: true });
  return plannedExportDir(exportRoot, skillId);
}

/**
 * Export a complete skill tree to a planned collision-safe destination.
 * Partial output is removed on failure.
 *
 * @param {object} params
 * @returns {string}
 */
export function exportSkillTree(params) {
  const { sourceDir, exportRoot, skillId, dest: plannedDest } = params;
  const dest = plannedDest || collisionSafeExportDir(exportRoot, skillId);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const staging = path.join(
    path.dirname(dest),
    `.sigma-export-${skillId}-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  );
  try {
    fs.cpSync(sourceDir, staging, { recursive: true });
    fs.renameSync(staging, dest);
    return dest;
  } catch (err) {
    if (pathExists(staging)) fs.rmSync(staging, { recursive: true, force: true });
    if (pathExists(dest)) fs.rmSync(dest, { recursive: true, force: true });
    throw new Error(`failed to export '${skillId}' to '${dest}': ${err.message}`);
  }
}
