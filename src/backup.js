import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { pathExists } from './links.js';

export const BACKUP_METADATA_NAME = '.sigma-backup.json';
export const BACKUP_SCHEMA_VERSION = 1;

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

function hashBytes(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function isInsideRoot(root, absolutePath) {
  const relative = path.relative(path.resolve(root), path.resolve(absolutePath));
  return relative === '' || (Boolean(relative) && !relative.startsWith('..') && !path.isAbsolute(relative));
}

/**
 * Inventory a skill tree without following symbolic links or junctions.
 *
 * @param {string} dir
 * @returns {{ entries: Record<string, object> }}
 */
export function inventorySkillTree(dir) {
  const entries = {};
  if (!pathExists(dir)) return { entries };
  const top = fs.lstatSync(dir);
  if (top.isSymbolicLink()) {
    let target = '';
    try {
      target = fs.readlinkSync(dir);
    } catch {
      target = '';
    }
    return { entries: { '': { kind: 'symlink', target, escaped: true } } };
  }
  if (!top.isDirectory()) return { entries };

  const visit = (current) => {
    let dirents;
    try {
      dirents = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const dirent of dirents) {
      const full = path.join(current, dirent.name);
      const rel = path.relative(dir, full).replace(/\\/g, '/');
      let stat;
      try {
        stat = fs.lstatSync(full);
      } catch {
        continue;
      }
      if (dirent.name === BACKUP_METADATA_NAME) continue;
      if (stat.isSymbolicLink()) {
        let target = '';
        try {
          target = fs.readlinkSync(full);
        } catch {
          target = '';
        }
        const resolved = path.resolve(path.dirname(full), target);
        entries[rel] = {
          kind: 'symlink',
          target,
          escaped: !isInsideRoot(dir, resolved),
        };
        continue;
      }
      if (stat.isDirectory()) {
        entries[rel] = { kind: 'directory' };
        visit(full);
        continue;
      }
      if (stat.isFile()) {
        const bytes = fs.readFileSync(full);
        entries[rel] = {
          kind: 'file',
          hash: hashBytes(bytes),
          binary: bytes.includes(0),
        };
      }
    }
  };
  visit(dir);
  return { entries };
}

export function inventoriesMatch(left, right) {
  const leftKeys = Object.keys(left.entries || {}).sort();
  const rightKeys = Object.keys(right.entries || {}).sort();
  if (leftKeys.join('\0') !== rightKeys.join('\0')) return false;
  for (const key of leftKeys) {
    const a = left.entries[key];
    const b = right.entries[key];
    if (a.kind !== b.kind) return false;
    if (a.kind === 'file' && a.hash !== b.hash) return false;
  }
  return true;
}

export function copySkillTree(sourceDir, destDir) {
  copyTreeNoFollow(sourceDir, destDir);
}

function treeSizeBytes(dir, inventory) {
  let total = 0;
  for (const [rel, entry] of Object.entries(inventory.entries || {})) {
    if (entry.kind !== 'file') continue;
    try {
      total += fs.statSync(path.join(dir, ...rel.split('/'))).size;
    } catch {
      // Size is best-effort for preview; integrity still uses hashes.
    }
  }
  return total;
}

/**
 * @param {string} backupDir
 * @returns {object}
 */
export function readBackupMetadata(backupDir) {
  const file = path.join(backupDir, BACKUP_METADATA_NAME);
  if (!pathExists(file)) {
    const err = new Error('schema-incompatible backup: missing metadata');
    err.code = 'schema';
    throw err;
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (cause) {
    const err = new Error(`schema-incompatible backup: ${cause.message}`);
    err.code = 'schema';
    throw err;
  }
  if (!parsed || typeof parsed !== 'object' || typeof parsed.schemaVersion !== 'number') {
    const err = new Error('schema-incompatible backup: metadata is not a versioned object');
    err.code = 'schema';
    throw err;
  }
  if (parsed.schemaVersion !== BACKUP_SCHEMA_VERSION) {
    const err = new Error(
      `schema-incompatible backup: schemaVersion ${parsed.schemaVersion} is not supported`,
    );
    err.code = 'schema';
    throw err;
  }
  return parsed;
}

function writeBackupMetadata(backupDir, metadata) {
  fs.writeFileSync(
    path.join(backupDir, BACKUP_METADATA_NAME),
    `${JSON.stringify(metadata, null, 2)}\n`,
    'utf8',
  );
}

/**
 * Locate the retained backup directory for a skill.
 *
 * @param {object} params
 * @returns {string | null}
 */
export function findLatestBackupDir(params) {
  const { stateDir, skillId, lastBackup } = params;
  if (lastBackup) {
    const fromState = path.isAbsolute(lastBackup)
      ? lastBackup
      : path.join(stateDir, lastBackup);
    if (pathExists(fromState) && fs.lstatSync(fromState).isDirectory()) {
      return fromState;
    }
  }
  const dir = path.join(getBackupRoot(stateDir), skillId);
  if (!pathExists(dir)) return null;
  const stamps = fs.readdirSync(dir)
    .map((name) => path.join(dir, name))
    .filter((full) => {
      try {
        return fs.lstatSync(full).isDirectory();
      } catch {
        return false;
      }
    })
    .sort();
  return stamps.length > 0 ? stamps[stamps.length - 1] : null;
}

/**
 * Integrity-check a retained backup before any restore write.
 *
 * @param {object} params
 * @returns {{ metadata: object, inventory: object, sizeBytes: number }}
 */
export function verifyBackupIntegrity(params) {
  const { backupDir, skillId } = params;
  if (!backupDir || !pathExists(backupDir)) {
    const err = new Error(`missing backup for '${skillId}'`);
    err.code = 'missing';
    throw err;
  }
  const metadata = readBackupMetadata(backupDir);
  if (metadata.skillId && metadata.skillId !== skillId) {
    const err = new Error(
      `stale-ownership: backup for '${metadata.skillId}' cannot restore '${skillId}'`,
    );
    err.code = 'stale-ownership';
    throw err;
  }
  const inventory = inventorySkillTree(backupDir);
  const expected = { entries: metadata.inventory || {} };
  const expectedKeys = Object.keys(expected.entries).sort();
  const actualKeys = Object.keys(inventory.entries || {}).sort();
  for (const key of expectedKeys) {
    if (!inventory.entries[key]) {
      const err = new Error(`truncated backup for '${skillId}': missing '${key}'`);
      err.code = 'truncated';
      throw err;
    }
  }
  if (actualKeys.join('\0') !== expectedKeys.join('\0') || !inventoriesMatch(expected, inventory)) {
    const err = new Error(`tampered backup for '${skillId}'`);
    err.code = 'tampered';
    throw err;
  }
  return {
    metadata,
    inventory,
    sizeBytes: typeof metadata.sizeBytes === 'number' ? metadata.sizeBytes : treeSizeBytes(backupDir, inventory),
  };
}

function copyTreeNoFollow(sourceDir, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  const inventory = inventorySkillTree(sourceDir);
  const keys = Object.keys(inventory.entries).sort((a, b) => {
    const depth = a.split('/').length - b.split('/').length;
    return depth !== 0 ? depth : a.localeCompare(b);
  });
  for (const rel of keys) {
    const entry = inventory.entries[rel];
    const from = path.join(sourceDir, ...rel.split('/'));
    const to = path.join(destDir, ...rel.split('/'));
    fs.mkdirSync(path.dirname(to), { recursive: true });
    if (entry.kind === 'directory') {
      fs.mkdirSync(to, { recursive: true });
    } else if (entry.kind === 'file') {
      fs.copyFileSync(from, to);
    } else if (entry.kind === 'symlink') {
      const type = process.platform === 'win32' ? 'junction' : 'dir';
      fs.symlinkSync(entry.target, to, type);
    }
  }
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
  try {
    copyTreeNoFollow(sourceDir, dest);
    const sourceInventory = inventorySkillTree(sourceDir);
    const backupInventory = inventorySkillTree(dest);
    if (!inventoriesMatch(sourceInventory, backupInventory)) {
      throw new Error('backup integrity check failed');
    }
    const ownership = params.ownership || {};
    const createdAt = (now instanceof Date ? now : new Date(now)).toISOString();
    writeBackupMetadata(dest, {
      schemaVersion: BACKUP_SCHEMA_VERSION,
      skillId,
      scope: ownership.scope || null,
      release: ownership.release || null,
      revision: ownership.revision || null,
      createdAt,
      sizeBytes: treeSizeBytes(dest, backupInventory),
      canonicalTarget: ownership.canonicalTarget || null,
      method: ownership.method || null,
      copies: Array.isArray(ownership.copies) ? ownership.copies : [],
      ownedPaths: Array.isArray(ownership.ownedPaths) ? ownership.ownedPaths : [],
      inventory: backupInventory.entries,
    });
  } catch (err) {
    if (pathExists(dest)) fs.rmSync(dest, { recursive: true, force: true });
    throw err;
  }
  return dest;
}

/**
 * Keep only the newly committed backup for a skill after the operation succeeds.
 * Failures leave extra backups in place and report them as cleanup debt.
 *
 * @param {object} params
 * @returns {{ debt: string[] }}
 */
export function pruneOlderBackups(params) {
  const { stateDir, skillId, keepPath } = params;
  const dir = path.join(getBackupRoot(stateDir), skillId);
  const debt = [];
  if (!pathExists(dir)) return { debt };
  const keep = path.resolve(keepPath);
  for (const name of fs.readdirSync(dir)) {
    const full = path.resolve(dir, name);
    if (full === keep) continue;
    try {
      fs.rmSync(full, { recursive: true, force: true });
    } catch {
      debt.push(path.relative(stateDir, full).replace(/\\/g, '/'));
    }
  }
  return { debt };
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
 * Export a complete skill tree to a planned destination.
 * Partial output is removed on failure. Existing collision targets are left untouched.
 *
 * @param {object} params
 * @returns {string}
 */
export function exportSkillTree(params) {
  const { sourceDir, exportRoot, skillId, dest: plannedDest, refuseCollision = false, copyFn } = params;
  const dest = plannedDest || collisionSafeExportDir(exportRoot, skillId);
  if (!pathExists(sourceDir)) {
    throw new Error(`failed to export '${skillId}' to '${dest}': missing source tree`);
  }
  if (refuseCollision && pathExists(dest)) {
    throw new Error(`export collision at '${dest}'`);
  }
  const destExisted = pathExists(dest);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const staging = path.join(
    path.dirname(dest),
    `.sigma-export-${skillId}-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  );
  const copy = copyFn || ((from, to) => copyTreeNoFollow(from, to));
  try {
    copy(sourceDir, staging);
    fs.renameSync(staging, dest);
    return dest;
  } catch (err) {
    if (pathExists(staging)) fs.rmSync(staging, { recursive: true, force: true });
    if (!destExisted && pathExists(dest)) fs.rmSync(dest, { recursive: true, force: true });
    if (String(err.message || '').includes('collision')) throw err;
    throw new Error(`failed to export '${skillId}' to '${dest}': ${err.message}`);
  }
}
