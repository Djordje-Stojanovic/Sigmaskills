import fs from 'node:fs';
import path from 'node:path';
import { commitSkillBackup, copySkillTree, exportSkillTree, pruneOlderBackups } from './backup.js';
import { resolveHomeDir } from './destinations.js';
import { createSkillLink, inspectManagedPath, pathExists, removeManagedPath } from './links.js';
import { loadProjectLock, removeProjectLockSkill, saveProjectLock } from './project-lock.js';
import {
  getGlobalStateDir,
  getProjectStateDir,
  loadGlobalState,
  loadProjectState,
  removeSkillFromState,
  saveGlobalState,
  saveProjectState,
} from './state.js';
import { collectStatus } from './status.js';
import { acquireConcurrencyLock } from './transaction.js';

export const UNINSTALL_SCHEMA_VERSION = 1;
export const UNINSTALL_JOURNAL_FILENAME = 'uninstall-journal.json';

const CHANGED_KINDS = new Set([
  'outside-change',
  'outside-addition',
  'outside-deletion',
  'extra-resource',
  'missing-resource',
  'copy-disagreement',
]);

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

function posix(value) {
  return String(value || '').replace(/\\/g, '/');
}

function reviewKindFrom(classifications) {
  const kinds = classifications || [];
  if (kinds.includes('malformed-markers')) return 'malformed';
  if (kinds.some((kind) => CHANGED_KINDS.has(kind))) return 'changed';
  if (kinds.includes('valid-customization')) return 'customized';
  return 'clean';
}

function choicesFor(reviewKind) {
  return reviewKind === 'clean' ? ['keep', 'remove'] : ['backup', 'delete', 'export', 'keep'];
}

function deletionOrder(destinations) {
  const links = destinations.filter((dest) => dest.method && dest.method !== 'copy');
  const hostCopies = destinations.filter((dest) => dest.method === 'copy' && dest.kind !== 'canonical');
  const canonical = destinations.filter((dest) => dest.kind === 'canonical');
  const rest = destinations.filter((dest) => !links.includes(dest) && !hostCopies.includes(dest) && !canonical.includes(dest));
  return [...links, ...hostCopies, ...rest, ...canonical];
}

function resolveExpectedTarget(dest, root, canonicalAbs) {
  if (dest.method === 'copy' || !dest.method) return null;
  if (dest.dependsOn) return path.resolve(root, ...posix(dest.dependsOn).split('/'));
  return canonicalAbs;
}

function classifyUninstallSkill(options, skillId) {
  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const state = loadState(scope, root, options.customStateDir);
  const entry = state.skills?.[skillId];
  const status = collectStatus({
    ...options,
    projectRoot: scope === 'project' ? root : options.projectRoot,
    homeDir: scope === 'global' ? root : options.homeDir,
    scope,
  });
  const statusSkill = (status.skills || []).find((skill) => skill.id === skillId);
  const fallbackRel = entry?.destination || `.agents/skills/${skillId}`;
  const canonicalRel = posix(
    (Array.isArray(entry?.copies) ? entry.copies.find((copy) => copy.kind === 'canonical')?.destination : null)
    || entry?.destination
    || fallbackRel,
  );
  const canonicalAbs = path.resolve(root, ...canonicalRel.split('/'));
  const copies = Array.isArray(entry?.copies) && entry.copies.length > 0
    ? entry.copies
    : (entry ? [{
      kind: 'canonical',
      destination: canonicalRel,
      method: entry.method || 'copy',
      dependsOn: null,
      hostIds: [],
      ownedPaths: entry.ownedPaths || [canonicalRel],
    }] : []);

  const classifications = statusSkill
    ? statusSkill.destinations.flatMap((dest) => dest.classifications || [])
    : [];
  const reviewKind = reviewKindFrom(classifications);
  const destinations = copies.map((copy) => {
    const relativeDestination = posix(copy.destination);
    const absolutePath = path.resolve(root, ...relativeDestination.split('/'));
    const statusDest = statusSkill?.destinations?.find((dest) => posix(dest.relativeDestination) === relativeDestination);
    const method = copy.method || statusDest?.method || 'copy';
    const kind = copy.kind || (relativeDestination === canonicalRel ? 'canonical' : 'host');
    const dependsOn = copy.dependsOn || null;
    const inspect = pathExists(absolutePath)
      ? inspectManagedPath(absolutePath, resolveExpectedTarget({ method, dependsOn, absolutePath }, root, canonicalAbs))
      : { missing: true, method: null, wrongTarget: false, broken: false };
    const recordedLink = method && method !== 'copy';
    const liveLink = inspect.method && inspect.method !== 'copy';
    const methodMismatch = !inspect.missing && Boolean(recordedLink) !== Boolean(liveLink);
    return {
      relativeDestination,
      absolutePath,
      method,
      kind,
      dependsOn,
      hostIds: copy.hostIds || statusDest?.hostIds || [],
      classifications: statusDest?.classifications || (inspect.missing ? ['missing-destination'] : ['clean']),
      missing: Boolean(inspect.missing),
      wrongTarget: Boolean(inspect.wrongTarget),
      broken: Boolean(inspect.broken),
      unownedReplacement: Boolean(methodMismatch),
    };
  });

  const blockedReasons = [];
  if (!entry) {
    blockedReasons.push('stale-state');
    if (pathExists(canonicalAbs)) blockedReasons.push('unowned');
  }
  for (const dest of destinations) {
    if (dest.missing) blockedReasons.push('missing-destination');
    if (dest.wrongTarget) blockedReasons.push('wrong-target');
    if (dest.broken) blockedReasons.push('broken-link');
    if (dest.unownedReplacement) blockedReasons.push('unowned');
    if ((dest.classifications || []).includes('copy-disagreement')) blockedReasons.push('copy-disagreement');
    if ((dest.classifications || []).includes('stale-state')) blockedReasons.push('stale-state');
  }

  const uniqueReasons = [...new Set(blockedReasons)];
  const remainingCanonicalDependencies = destinations
    .filter((dest) => dest.dependsOn && posix(dest.dependsOn) === canonicalRel)
    .map((dest) => dest.relativeDestination);

  return {
    id: skillId,
    reviewKind,
    choices: choicesFor(reviewKind),
    choice: null,
    scope,
    lastBackup: entry?.lastBackup || null,
    canonicalRel,
    canonicalAbs,
    remainingCanonicalDependencies,
    destinations,
    blocked: uniqueReasons.length > 0,
    blockedReasons: uniqueReasons,
    owned: Boolean(entry),
  };
}

function resolveChoice(skill, options) {
  if (skill.reviewKind === 'clean') return options.clean || null;
  return options.changed || null;
}

function actionName(choice) {
  return choice || 'remove';
}

function plannedOutcome(skill) {
  if (skill.blocked && skill.choice !== 'keep') return 'skipped';
  if (skill.choice === 'keep') return 'retained';
  if (!skill.choice) return 'skipped';
  return 'removed';
}

function stateChangeFor(skill) {
  if (skill.choice === 'keep' || skill.outcome === 'retained' || skill.outcome === 'skipped' || skill.outcome === 'failed') {
    return 'unchanged';
  }
  return 'drop ownership';
}

function summarize(skills) {
  const summary = {
    removed: [],
    retained: [],
    skipped: [],
    failed: [],
  };
  for (const skill of skills) {
    const bucket = skill.outcome;
    if (summary[bucket]) summary[bucket].push(skill.id);
  }
  return summary;
}

function getJournalPath(stateDir) {
  return path.join(stateDir, UNINSTALL_JOURNAL_FILENAME);
}

function persistJournal(stateDir, journal) {
  fs.mkdirSync(stateDir, { recursive: true });
  const target = getJournalPath(stateDir);
  const tmp = `${target}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, `${JSON.stringify(journal, null, 2)}\n`, 'utf8');
  fs.renameSync(tmp, target);
}

function clearJournal(stateDir) {
  const target = getJournalPath(stateDir);
  if (pathExists(target)) fs.rmSync(target, { force: true });
}

function journalFrom(plan, status) {
  return {
    schemaVersion: UNINSTALL_SCHEMA_VERSION,
    command: 'uninstall',
    all: true,
    scope: plan.scope,
    status,
    startedAt: plan.startedAt,
    skills: (plan.skills || []).map((skill) => ({
      id: skill.id,
      outcome: skill.outcome || 'pending',
      choice: skill.choice || null,
      lastBackup: skill.lastBackup || null,
      error: skill.error || null,
    })),
  };
}

function recordedSkillIds(options) {
  const requested = Array.isArray(options.skillIds) ? options.skillIds.filter(Boolean) : [];
  if (options.all && requested.length > 0) {
    throw codedError('uninstall --all cannot be combined with --skill', 'usage');
  }
  if (!options.all) return requested;
  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  return Object.keys(loadState(scope, root, options.customStateDir).skills || {}).sort();
}

/**
 * Preview Uninstall Review for selected skills or every recorded skill in one scope.
 *
 * @param {object} options
 * @returns {object}
 */
export function createUninstallPlan(options = {}) {
  const scope = options.scope || 'project';
  const skillIds = recordedSkillIds(options);
  const resolved = {
    ...options,
    clean: options.clean || (options.yes || options.all ? 'remove' : undefined),
    changed: options.changed || (options.all ? 'backup' : undefined),
  };
  const skills = skillIds.map((skillId) => {
    const skill = classifyUninstallSkill(resolved, skillId);
    return { ...skill, choice: resolveChoice(skill, resolved) };
  });
  const plan = {
    schemaVersion: UNINSTALL_SCHEMA_VERSION,
    command: 'uninstall',
    all: Boolean(options.all),
    scope,
    dryRun: Boolean(options.dryRun),
    skills,
  };
  if (plan.all) {
    for (const skill of skills) {
      skill.outcome = plannedOutcome(skill);
      skill.stateChange = stateChangeFor(skill);
    }
    plan.summary = summarize(skills);
  }
  return plan;
}

function inspectLiveLeaf(dest, root, canonicalAbs) {
  if (!pathExists(dest.absolutePath)) {
    return { missing: true, method: null, wrongTarget: false, broken: false };
  }
  return inspectManagedPath(
    dest.absolutePath,
    resolveExpectedTarget(dest, root, canonicalAbs),
  );
}

function leafStopReason(dest, inspect) {
  if (inspect.wrongTarget) return 'wrong-target';
  const recordedLink = dest.method && dest.method !== 'copy';
  const liveLink = inspect.method && inspect.method !== 'copy';
  if (!inspect.missing && Boolean(recordedLink) !== Boolean(liveLink)) return 'unowned';
  return null;
}

function restoreStaged(root, staged) {
  for (const item of staged.slice().reverse()) {
    try {
      if (item.kind === 'link') {
        if (!pathExists(item.absolutePath) && item.target && pathExists(item.target)) {
          createSkillLink(item.absolutePath, item.target, root);
        }
      } else if (item.kind === 'tree' && !pathExists(item.absolutePath) && pathExists(item.staged)) {
        fs.mkdirSync(path.dirname(item.absolutePath), { recursive: true });
        copySkillTree(item.staged, item.absolutePath);
      }
    } catch {
      // Rollback continues for remaining leaves.
    }
  }
}

function applyOneUninstall(options, skill) {
  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const stateDir = resolveStateDir(scope, root, options.customStateDir);
  const stagingParent = path.join(stateDir, '.sigma-uninstall-staging');
  const stagingDir = path.join(
    stagingParent,
    `${skill.id}-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  );
  const staged = [];
  let backupDir = null;

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
    const live = classifyUninstallSkill(options, skill.id);
    if (skill.choice === 'keep') {
      return { action: 'keep', backupDir: null, staged, cleanupStaging };
    }
    const hard = live.blockedReasons.filter((reason) => (
      reason === 'wrong-target'
      || reason === 'unowned'
      || reason === 'missing-destination'
      || reason === 'stale-state'
      || reason === 'broken-link'
      || (reason === 'copy-disagreement' && skill.reviewKind === 'clean')
    ));
    if (hard.length > 0) {
      throw codedError(`${hard[0]} stopped uninstall of '${skill.id}'`, hard[0]);
    }

    fs.mkdirSync(stagingDir, { recursive: true });
    const ordered = deletionOrder(live.destinations);
    for (const dest of ordered) {
      const inspect = inspectLiveLeaf(dest, root, live.canonicalAbs);
      const stop = leafStopReason(dest, inspect);
      if (stop) throw codedError(`${stop} stopped uninstall of '${skill.id}'`, stop);
      if (inspect.missing) continue;
      if (inspect.method && inspect.method !== 'copy') {
        staged.push({
          kind: 'link',
          absolutePath: dest.absolutePath,
          target: inspect.target || live.canonicalAbs,
        });
        continue;
      }
      const stagedPath = path.join(stagingDir, dest.relativeDestination.replace(/[\\/]/g, '__'));
      copySkillTree(dest.absolutePath, stagedPath);
      staged.push({
        kind: 'tree',
        absolutePath: dest.absolutePath,
        staged: stagedPath,
      });
    }

    if (skill.choice === 'export') {
      exportSkillTree({
        sourceDir: live.canonicalAbs,
        exportRoot: options.exportDir || path.join(root, 'sigmaskills-export'),
        skillId: skill.id,
        refuseCollision: true,
      });
    }

    if (skill.choice === 'backup') {
      const state = loadState(scope, root, options.customStateDir);
      const entry = state.skills?.[skill.id];
      const backupFn = options.backupSkill || commitSkillBackup;
      backupDir = backupFn({
        stateDir,
        skillId: skill.id,
        sourceDir: live.canonicalAbs,
        ownership: {
          scope,
          release: entry?.release || null,
          revision: entry?.revision || null,
          method: entry?.method || 'copy',
          canonicalTarget: live.canonicalRel,
          copies: entry?.copies || [],
          ownedPaths: entry?.ownedPaths || [live.canonicalRel],
        },
      });
    }

    for (const dest of ordered) {
      const inspect = inspectLiveLeaf(dest, root, live.canonicalAbs);
      const stop = leafStopReason(dest, inspect);
      if (stop) throw codedError(`${stop} stopped uninstall of '${skill.id}'`, stop);
      if (inspect.missing) continue;
      if (dest.kind === 'canonical') {
        const dependents = live.destinations.filter((item) => (
          item.dependsOn
          && posix(item.dependsOn) === live.canonicalRel
          && pathExists(item.absolutePath)
        ));
        if (dependents.length > 0) {
          throw codedError(
            `canonical content remains while destinations still depend on it: ${skill.id}`,
            'canonical-dependency',
          );
        }
      }
      removeManagedPath(dest.absolutePath);
      if (dest.method && dest.method !== 'copy' && typeof options.afterUnlink === 'function') {
        options.afterUnlink(dest.absolutePath);
      }
    }

    if (typeof options.afterStage === 'function') options.afterStage(stagingDir);
    return { action: actionName(skill.choice), backupDir, staged, cleanupStaging };
  } catch (err) {
    restoreStaged(root, staged);
    if (backupDir && pathExists(backupDir) && skill.choice === 'backup') {
      try {
        fs.rmSync(backupDir, { recursive: true, force: true });
      } catch {
        // Drop the unused snapshot so the retained backup stays the latest.
      }
    }
    cleanupStaging();
    throw err;
  }
}

/**
 * Uninstall selected skills, or every recorded skill in one scope, after Uninstall Review.
 *
 * @param {object} options
 * @returns {object}
 */
export function executeUninstall(options = {}) {
  const plan = createUninstallPlan(options);
  if (options.dryRun) {
    return { ...plan, dryRun: true };
  }

  for (const skill of plan.skills) {
    if (!skill.choice) {
      if (skill.reviewKind === 'clean') {
        throw codedError('uninstall of a clean skill needs --clean remove or keep', 'review');
      }
      throw codedError(
        `changed, customized, or malformed skill '${skill.id}' needs --changed backup, keep, export, or delete`,
        'review',
      );
    }
    if (skill.reviewKind === 'clean' && skill.choice !== 'remove' && skill.choice !== 'keep') {
      throw codedError('--clean must be remove or keep', 'review');
    }
    if (skill.reviewKind !== 'clean' && !['backup', 'keep', 'export', 'delete'].includes(skill.choice)) {
      throw codedError('--changed must be backup, keep, export, or delete', 'review');
    }
  }

  const scope = options.scope || 'project';
  const root = resolveRoot(options);
  const customStateDir = options.customStateDir;
  const stateDir = resolveStateDir(scope, root, customStateDir);
  const releaseLock = acquireConcurrencyLock(root, customStateDir);
  let state = loadState(scope, root, customStateDir);
  plan.startedAt = new Date().toISOString();

  const writeAllJournal = (status) => {
    if (!plan.all) return;
    persistJournal(stateDir, journalFrom(plan, status));
  };

  try {
    if (plan.all) writeAllJournal('in-progress');

    for (let index = 0; index < plan.skills.length; index += 1) {
      const skill = plan.skills[index];
      if (plan.all && skill.choice !== 'keep' && skill.blocked) {
        skill.outcome = 'skipped';
        skill.error = (skill.blockedReasons || []).join(', ') || 'blocked';
        skill.stateChange = stateChangeFor(skill);
        writeAllJournal('in-progress');
        continue;
      }

      try {
        const applied = applyOneUninstall(options, skill);
        skill.action = applied.action;
        if (skill.choice === 'keep') {
          skill.outcome = 'retained';
          skill.stateChange = stateChangeFor(skill);
          writeAllJournal('in-progress');
          continue;
        }

        const priorState = state;
        const persist = options.saveState || (scope === 'global' ? saveGlobalState : saveProjectState);
        try {
          state = removeSkillFromState(state, skill.id);
          persist(root, state, customStateDir);
          if (scope !== 'global') {
            const lock = loadProjectLock(root);
            saveProjectLock(root, removeProjectLockSkill(lock, skill.id));
          }
        } catch (err) {
          restoreStaged(root, applied.staged || []);
          persist(root, priorState, customStateDir);
          if (typeof applied.cleanupStaging === 'function') applied.cleanupStaging();
          throw err;
        }
        if (skill.choice === 'backup' && applied.backupDir) {
          pruneOlderBackups({
            stateDir,
            skillId: skill.id,
            keepPath: applied.backupDir,
          });
          skill.lastBackup = path.relative(stateDir, applied.backupDir).replace(/\\/g, '/');
        }
        if (typeof applied.cleanupStaging === 'function') applied.cleanupStaging();
        skill.outcome = 'removed';
        skill.stateChange = stateChangeFor(skill);
        writeAllJournal('in-progress');
      } catch (err) {
        skill.outcome = 'failed';
        skill.error = err.message;
        skill.stateChange = stateChangeFor(skill);
        if (plan.all) {
          for (const remaining of plan.skills.slice(index + 1)) {
            remaining.outcome = 'skipped';
            remaining.error = 'stopped-after-failure';
            remaining.stateChange = stateChangeFor(remaining);
          }
          writeAllJournal('failed');
          break;
        }
        throw err;
      }
    }

    if (plan.all) {
      plan.summary = summarize(plan.skills);
      if ((plan.summary.failed || []).length === 0) {
        clearJournal(stateDir);
      }
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
export function formatUninstallJson(result) {
  return `${JSON.stringify(result, null, 2)}\n`;
}

/**
 * @param {object} result
 * @returns {string}
 */
export function formatUninstallHuman(result) {
  const lines = [
    `SigmaSkills Uninstall ${result.dryRun ? 'Preview' : 'Result'}`,
    `Scope: ${result.scope}`,
    '',
  ];
  if (result.all) {
    lines.push('Mode: every recorded skill in this scope');
    lines.push('');
  }
  for (const skill of result.skills || []) {
    lines.push(`Skill: ${skill.id}`);
    lines.push(`  Review: ${skill.reviewKind}`);
    lines.push(`  Choices: ${(skill.choices || []).join(', ')}`);
    if (skill.choice) lines.push(`  Choice: ${skill.choice}`);
    if (skill.action) lines.push(`  Action: ${skill.action}`);
    if (skill.outcome) lines.push(`  Outcome: ${skill.outcome}`);
    lines.push(`  Scope: ${skill.scope}`);
    if (skill.canonicalRel) lines.push(`  Canonical: ${skill.canonicalRel}`);
    const deps = (skill.remainingCanonicalDependencies || []).join(', ');
    lines.push(`  Remaining canonical dependencies: ${deps || 'none'}`);
    if (result.all) {
      lines.push(`  Retained backup: ${skill.lastBackup || 'none'}`);
      lines.push(`  State: ${skill.stateChange || stateChangeFor(skill)}`);
    }
    for (const dest of skill.destinations || []) {
      lines.push(`  Path: ${dest.relativeDestination}`);
      lines.push(`    Method: ${dest.method || 'none'}`);
      if (dest.dependsOn) lines.push(`    Depends on: ${dest.dependsOn}`);
      if (dest.hostIds?.length) lines.push(`    Agent Hosts: ${dest.hostIds.join(', ')}`);
    }
    if (skill.blockedReasons?.length) lines.push(`  Blocked: ${skill.blockedReasons.join(', ')}`);
    if (skill.error) lines.push(`  Error: ${skill.error}`);
    lines.push('');
  }
  if (result.summary) {
    lines.push(`Removed: ${(result.summary.removed || []).join(', ') || 'none'}`);
    lines.push(`Retained: ${(result.summary.retained || []).join(', ') || 'none'}`);
    lines.push(`Skipped: ${(result.summary.skipped || []).join(', ') || 'none'}`);
    lines.push(`Failed: ${(result.summary.failed || []).join(', ') || 'none'}`);
    lines.push('');
  }
  return lines.join('\n');
}
