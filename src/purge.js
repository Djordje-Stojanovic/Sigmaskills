import fs from 'node:fs';
import path from 'node:path';
import { copySkillTree, getBackupRoot } from './backup.js';
import { resolveHomeDir } from './destinations.js';
import { createSkillLink, inspectManagedPath, pathExists, removeManagedPath } from './links.js';
import { inspectProjectLock, PROJECT_LOCK_FILENAME } from './project-lock.js';
import {
  STATE_FILENAME,
  getGlobalStateDir,
  getProjectStateDir,
} from './state.js';
import { acquireConcurrencyLock } from './transaction.js';
import { createUninstallPlan, UNINSTALL_JOURNAL_FILENAME } from './uninstall.js';

export const PURGE_SCHEMA_VERSION = 1;
export const PURGE_JOURNAL_FILENAME = 'purge-journal.json';
export const PURGE_QUARANTINE_DIRNAME = '.sigma-purge-quarantine';
export const PURGE_CONFIRMATION_PHRASE = 'purge SigmaSkills';

const PRIVATE_STAGING = [
  '.sigma-uninstall-staging',
  '.sigma-restore-staging',
  '.sigma-staging',
];
const HARD_STOP = new Set(['unowned', 'wrong-target', 'broken-link', 'copy-disagreement', 'stale-state']);

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

function posix(value) {
  return String(value || '').replace(/\\/g, '/');
}

function relativeToRoot(root, absolutePath) {
  const rel = path.relative(root, absolutePath);
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) {
    return posix(path.basename(absolutePath));
  }
  return posix(rel);
}

function deletionOrder(destinations) {
  const links = destinations.filter((dest) => dest.method && dest.method !== 'copy');
  const hostCopies = destinations.filter((dest) => dest.method === 'copy' && dest.kind !== 'canonical');
  const canonical = destinations.filter((dest) => dest.kind === 'canonical');
  const rest = destinations.filter((dest) => !links.includes(dest) && !hostCopies.includes(dest) && !canonical.includes(dest));
  return [...links, ...hostCopies, ...rest, ...canonical];
}

function readJsonIfPresent(file) {
  if (!pathExists(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function persistJson(file, payload) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  fs.renameSync(tmp, file);
}

function relocate(source, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  try {
    fs.renameSync(source, dest);
    return;
  } catch (err) {
    if (err.code !== 'EXDEV') throw err;
  }
  if (!pathExists(source)) return;
  const stat = fs.lstatSync(source);
  if (stat.isSymbolicLink()) {
    fs.symlinkSync(fs.readlinkSync(source), dest, process.platform === 'win32' ? 'junction' : 'dir');
    fs.unlinkSync(source);
    return;
  }
  if (stat.isFile()) {
    fs.copyFileSync(source, dest);
    fs.unlinkSync(source);
    return;
  }
  copySkillTree(source, dest);
  removeManagedPath(source);
}

function restoreQuarantined(root, items) {
  for (const item of items.slice().reverse()) {
    if (item.status !== 'quarantined' || !item.quarantinePath || !pathExists(item.quarantinePath)) continue;
    try {
      if (item.kind === 'link') {
        if (!pathExists(item.absolutePath) && item.target && pathExists(item.target)) {
          createSkillLink(item.absolutePath, item.target, root);
          removeManagedPath(item.quarantinePath);
        } else if (!pathExists(item.absolutePath)) {
          relocate(item.quarantinePath, item.absolutePath);
        }
      } else if (!pathExists(item.absolutePath)) {
        relocate(item.quarantinePath, item.absolutePath);
      }
      item.status = 'pending';
      item.quarantinePath = null;
    } catch {
      // Continue restoring remaining leaves.
    }
  }
}

function collectPrivateItems(root, stateDir) {
  const items = [];
  const backupRoot = getBackupRoot(stateDir);
  if (pathExists(backupRoot)) {
    items.push({
      kind: 'backups',
      relative: relativeToRoot(root, backupRoot),
      absolutePath: backupRoot,
      status: 'pending',
    });
  }
  for (const name of PRIVATE_STAGING) {
    const absolutePath = path.join(stateDir, name);
    if (pathExists(absolutePath)) {
      items.push({ kind: 'staging', relative: name, absolutePath, status: 'pending' });
    }
  }
  for (const name of [UNINSTALL_JOURNAL_FILENAME, PURGE_JOURNAL_FILENAME]) {
    const absolutePath = path.join(stateDir, name);
    if (pathExists(absolutePath)) {
      items.push({ kind: 'journal', relative: name, absolutePath, status: 'pending' });
    }
  }
  const lockPath = path.join(stateDir, '.sigma.lock');
  if (pathExists(lockPath)) {
    items.push({ kind: 'lock', relative: '.sigma.lock', absolutePath: lockPath, status: 'pending' });
  }
  const manifestPath = path.join(stateDir, STATE_FILENAME);
  if (pathExists(manifestPath)) {
    items.push({
      kind: 'manifest',
      relative: relativeToRoot(root, manifestPath),
      absolutePath: manifestPath,
      status: 'pending',
    });
  }
  return items;
}

function findResumeJournal(stateDir) {
  const primary = path.join(stateDir, PURGE_JOURNAL_FILENAME);
  const nested = path.join(stateDir, PURGE_QUARANTINE_DIRNAME, PURGE_JOURNAL_FILENAME);
  for (const file of [primary, nested]) {
    const journal = readJsonIfPresent(file);
    if (journal && journal.command === 'purge' && journal.status && journal.status !== 'complete') {
      return { journal, file };
    }
  }
  return null;
}

/**
 * Preview every revalidated Sigma-owned path in one Project or Global scope.
 *
 * @param {object} options
 * @returns {object}
 */
export function createPurgePlan(options = {}) {
  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const stateDir = resolveStateDir(scope, root, options.customStateDir);
  const resume = findResumeJournal(stateDir);
  if (resume?.journal?.items && (resume.journal.status === 'quarantined' || resume.journal.status === 'cleanup')) {
    return {
      schemaVersion: PURGE_SCHEMA_VERSION,
      command: 'purge',
      scope,
      dryRun: Boolean(options.dryRun),
      confirmationPhrase: PURGE_CONFIRMATION_PHRASE,
      resumed: true,
      blocked: [],
      items: resume.journal.items,
      skills: resume.journal.skills || [],
      quarantineDir: resume.journal.quarantineDir,
    };
  }

  const uninstallPlan = createUninstallPlan({
    ...options,
    all: true,
    yes: true,
  });
  const blocked = [];
  const destinationItems = [];
  for (const skill of uninstallPlan.skills) {
    const reasons = (skill.blockedReasons || []).filter((reason) => HARD_STOP.has(reason));
    if (reasons.length > 0) {
      blocked.push({ id: skill.id, reasons });
    }
    for (const dest of deletionOrder(skill.destinations || [])) {
      const kind = dest.method && dest.method !== 'copy' ? 'link' : 'tree';
      destinationItems.push({
        kind,
        skillId: skill.id,
        relative: dest.relativeDestination,
        absolutePath: dest.absolutePath,
        method: dest.method || null,
        role: dest.kind || null,
        dependsOn: dest.dependsOn || null,
        missing: Boolean(dest.missing),
        target: dest.method && dest.method !== 'copy' ? skill.canonicalAbs : null,
        status: dest.missing ? 'absent' : 'pending',
      });
    }
  }

  const items = [
    ...destinationItems,
    ...collectPrivateItems(root, stateDir),
  ];
  if (scope === 'project') {
    const lockInspect = inspectProjectLock(root);
    if (lockInspect.kind === 'sigma') {
      items.push({
        kind: 'project-lock',
        relative: PROJECT_LOCK_FILENAME,
        absolutePath: path.join(root, PROJECT_LOCK_FILENAME),
        status: 'pending',
      });
    }
  }

  return {
    schemaVersion: PURGE_SCHEMA_VERSION,
    command: 'purge',
    scope,
    dryRun: Boolean(options.dryRun),
    confirmationPhrase: PURGE_CONFIRMATION_PHRASE,
    resumed: false,
    blocked,
    items,
    skills: (uninstallPlan.skills || []).map((skill) => ({
      id: skill.id,
      destinations: skill.destinations,
      blockedReasons: skill.blockedReasons,
    })),
  };
}

function assertConfirmed(options) {
  const phrase = options.confirmPurge;
  if (phrase === undefined || phrase === null) {
    throw codedError(
      'purge requires --confirm-purge with the typed confirmation phrase; --yes, CI, non-TTY, and JSON are not authority',
      'confirmation',
    );
  }
  if (String(phrase).trim() === '') {
    throw codedError('purge cancelled', 'cancelled');
  }
  if (String(phrase) !== PURGE_CONFIRMATION_PHRASE) {
    throw codedError(
      `purge confirmation phrase is wrong; type exactly: ${PURGE_CONFIRMATION_PHRASE}`,
      'confirmation',
    );
  }
}

function revalidateDestinations(plan) {
  for (const item of plan.items) {
    if (item.kind !== 'link' && item.kind !== 'tree') continue;
    if (!pathExists(item.absolutePath)) {
      item.missing = true;
      item.status = item.status === 'quarantined' ? item.status : 'absent';
      continue;
    }
    const expected = item.kind === 'link' ? item.target : null;
    const inspect = inspectManagedPath(item.absolutePath, expected);
    const recordedLink = item.kind === 'link';
    const liveLink = inspect.method && inspect.method !== 'copy';
    if (inspect.wrongTarget || Boolean(recordedLink) !== Boolean(liveLink)) {
      throw codedError(
        `unowned occupant stopped purge at '${item.relative}'`,
        inspect.wrongTarget ? 'wrong-target' : 'unowned',
      );
    }
    if (inspect.broken) {
      throw codedError(`broken-link stopped purge at '${item.relative}'`, 'broken-link');
    }
  }
}

function journalPayload(plan, extra) {
  return {
    schemaVersion: PURGE_SCHEMA_VERSION,
    command: 'purge',
    scope: plan.scope,
    confirmationPhrase: PURGE_CONFIRMATION_PHRASE,
    ...extra,
    items: plan.items,
    skills: plan.skills,
  };
}

function finishCleanup(stateDir, plan) {
  const quarantineDir = path.join(stateDir, PURGE_QUARANTINE_DIRNAME);
  for (const item of plan.items) {
    if (item.kind === 'link' || item.kind === 'tree' || item.kind === 'backups') continue;
    if (item.kind === 'lock') continue;
    if (item.status === 'absent') continue;
    if (pathExists(item.absolutePath)) {
      removeManagedPath(item.absolutePath);
      item.status = 'removed';
    }
  }
  if (pathExists(quarantineDir)) {
    fs.rmSync(quarantineDir, { recursive: true, force: true });
  }
  const leftoverJournal = path.join(stateDir, PURGE_JOURNAL_FILENAME);
  if (pathExists(leftoverJournal)) fs.rmSync(leftoverJournal, { force: true });
  const lockPath = path.join(stateDir, '.sigma.lock');
  if (pathExists(lockPath)) {
    try {
      const existing = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
      if (!existing.pid || existing.pid === process.pid) fs.rmSync(lockPath, { force: true });
    } catch {
      // Lock removal is best-effort after the ownership plan is complete.
    }
  }
  for (const name of [...PRIVATE_STAGING, 'backups']) {
    const target = path.join(stateDir, name);
    if (pathExists(target)) fs.rmSync(target, { recursive: true, force: true });
  }
}

/**
 * Remove every revalidated Sigma-owned artifact in one chosen scope.
 *
 * @param {object} options
 * @returns {object}
 */
export function executePurge(options = {}) {
  const plan = createPurgePlan(options);
  if (options.dryRun) {
    return { ...plan, dryRun: true };
  }
  assertConfirmed(options);
  if ((plan.blocked || []).length > 0) {
    const first = plan.blocked[0];
    throw codedError(
      `${(first.reasons || []).join(', ') || 'unowned'} stopped purge of '${first.id}'`,
      first.reasons?.[0] || 'unowned',
    );
  }

  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const customStateDir = options.customStateDir;
  const stateDir = resolveStateDir(scope, root, customStateDir);
  const releaseLock = acquireConcurrencyLock(root, customStateDir);
  const quarantineDir = path.join(stateDir, PURGE_QUARANTINE_DIRNAME);
  const journalPath = path.join(stateDir, PURGE_JOURNAL_FILENAME);
  const writeJournal = (status) => {
    const payload = journalPayload(plan, { status, quarantineDir: posix(relativeToRoot(root, quarantineDir)) });
    persistJson(journalPath, payload);
    if (pathExists(quarantineDir)) {
      persistJson(path.join(quarantineDir, PURGE_JOURNAL_FILENAME), payload);
    }
  };

  try {
    if (plan.resumed) {
      writeJournal('cleanup');
      finishCleanup(stateDir, plan);
      return { ...plan, dryRun: false, resumed: true };
    }

    revalidateDestinations(plan);
    fs.mkdirSync(quarantineDir, { recursive: true });
    writeJournal('in-progress');
    let phase = 'quarantine';

    try {
      let index = 0;
      for (const item of plan.items) {
        if (item.kind !== 'link' && item.kind !== 'tree' && item.kind !== 'backups') continue;
        if (item.status === 'absent' || item.missing || !pathExists(item.absolutePath)) {
          item.status = 'absent';
          continue;
        }
        const slot = path.join(quarantineDir, `${String(index).padStart(3, '0')}-${item.kind}-${(item.skillId || item.kind)}`);
        index += 1;
        relocate(item.absolutePath, slot);
        item.quarantinePath = slot;
        item.status = 'quarantined';
        writeJournal('in-progress');
        if (typeof options.afterQuarantineItem === 'function') options.afterQuarantineItem(item);
      }
      writeJournal('quarantined');
      persistJson(path.join(quarantineDir, PURGE_JOURNAL_FILENAME), journalPayload(plan, {
        status: 'quarantined',
        quarantineDir: posix(relativeToRoot(root, quarantineDir)),
      }));
      phase = 'cleanup';
      if (typeof options.afterQuarantine === 'function') options.afterQuarantine(quarantineDir);
    } catch (err) {
      if (phase === 'quarantine') {
        restoreQuarantined(root, plan.items);
        writeJournal('failed');
        try {
          const leftover = pathExists(quarantineDir)
            ? fs.readdirSync(quarantineDir).filter((name) => name !== PURGE_JOURNAL_FILENAME)
            : [];
          if (leftover.length === 0 && pathExists(quarantineDir)) {
            fs.rmSync(quarantineDir, { recursive: true, force: true });
          }
        } catch {
          // Keep a failed journal when quarantine cannot be removed.
        }
      }
      throw err;
    }

    writeJournal('cleanup');
    finishCleanup(stateDir, plan);
    return { ...plan, dryRun: false, resumed: false };
  } finally {
    releaseLock();
  }
}

/**
 * @param {object} result
 * @returns {string}
 */
export function formatPurgeJson(result) {
  return `${JSON.stringify(result, null, 2)}\n`;
}

/**
 * @param {object} result
 * @returns {string}
 */
export function formatPurgeHuman(result) {
  const lines = [
    `SigmaSkills Purge ${result.dryRun ? 'Preview' : 'Result'}`,
    `Scope: ${result.scope}`,
    `Confirmation phrase: ${result.confirmationPhrase}`,
    '',
  ];
  if (result.resumed) lines.push('Mode: resume interrupted purge', '');
  lines.push('Ownership plan:');
  for (const item of result.items || []) {
    lines.push(`  ${item.relative} [${item.kind}${item.method ? `/${item.method}` : ''}]`);
  }
  if ((result.blocked || []).length > 0) {
    lines.push('');
    lines.push('Blocked:');
    for (const item of result.blocked) {
      lines.push(`  ${item.id}: ${(item.reasons || []).join(', ')}`);
    }
  }
  lines.push('');
  return lines.join('\n');
}
