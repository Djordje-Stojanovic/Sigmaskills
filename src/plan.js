import fs from 'node:fs';
import path from 'node:path';
import { loadProjectLock } from './project-lock.js';
import { loadProjectState } from './state.js';

export const PLAN_SCHEMA_VERSION = 1;

/**
 * Generate an install plan for a skill without mutating the filesystem.
 *
 * @param {object} catalog Catalog object containing manifest and validated skills
 * @param {object} options
 * @param {string} options.skillId
 * @param {string} [options.projectRoot]
 * @param {string} [options.customStateDir]
 * @param {boolean} [options.dryRun]
 * @returns {object} Versioned plan object
 */
export function createInstallPlan(catalog, options) {
  const { skillId, customStateDir, dryRun = false } = options;
  const projectRoot = path.resolve(options.projectRoot || process.cwd());

  if (!skillId || typeof skillId !== 'string') {
    throw new Error('missing or invalid skillId for install plan');
  }

  const skill = catalog.skills.find((s) => s.id === skillId);
  if (!skill) {
    throw new Error(`skill '${skillId}' was not found in Skill Pack ${catalog.manifest.name}`);
  }

  const destPath = path.join(projectRoot, '.agents', 'skills', skillId);
  const relDest = path.relative(projectRoot, destPath).replace(/\\/g, '/');

  const currentLock = loadProjectLock(projectRoot);
  const currentState = loadProjectState(projectRoot, customStateDir);

  const destExists = fs.existsSync(destPath);
  const stateEntry = currentState.skills?.[skillId];
  const isOwned = Boolean(
    stateEntry &&
      (stateEntry.destination === relDest ||
        path.resolve(projectRoot, stateEntry.destination) === path.resolve(destPath)),
  );
  const unownedConflict = destExists && !isOwned;

  const skillFiles = Object.keys(skill.files).sort();
  const writes = skillFiles.map((f) => `${relDest}/${f}`);

  const isReinstall = Boolean(stateEntry);
  const replacements = isReinstall ? [...writes] : [];

  const existingLockEntry = currentLock.skills?.[skillId] || null;
  const lockChanges = {
    file: 'skills-lock.json',
    action: existingLockEntry ? 'update' : 'add',
    previous: existingLockEntry,
    next: {
      revision: skill.revision,
    },
  };

  return {
    schemaVersion: PLAN_SCHEMA_VERSION,
    scope: 'project',
    action: 'install',
    skill: skillId,
    title: skill.title,
    release: catalog.manifest.version,
    sourceRevision: skill.revision,
    destination: destPath,
    relativeDestination: relDest,
    method: 'copy',
    files: skillFiles,
    writes,
    replacements,
    lockChanges,
    requiresApproval: false,
    unownedConflict,
    dryRun: Boolean(dryRun),
  };
}

/**
 * Format an install plan for human-readable display.
 *
 * @param {object} plan
 * @returns {string}
 */
export function formatPlanHuman(plan) {
  const lines = [
    `SigmaSkills Project Installation Plan: ${plan.title} (${plan.skill})`,
    `  Scope:               ${plan.scope}`,
    `  Release:             v${plan.release}`,
    `  Source Revision:     ${plan.sourceRevision}`,
    `  Method:              ${plan.method}`,
    `  Destination:         ${plan.destination}`,
    `  Relative Path:       ${plan.relativeDestination}`,
    `  Required Approval:   ${plan.requiresApproval ? 'Yes' : 'None'}`,
    `  Files to write (${plan.writes.length}):`,
    ...plan.writes.map((w) => `    + ${w}`),
  ];

  if (plan.replacements.length > 0) {
    lines.push(`  Files to replace (${plan.replacements.length}):`);
    lines.push(...plan.replacements.map((r) => `    ~ ${r}`));
  }

  lines.push(`  Lock changes (${plan.lockChanges.file}):`);
  lines.push(`    Action: ${plan.lockChanges.action}`);
  lines.push(`    Next Revision: ${plan.lockChanges.next.revision}`);

  if (plan.unownedConflict) {
    lines.push('');
    lines.push(`  ⚠ UNOWNED CONFLICT: Destination '${plan.destination}' already exists and is not owned by Sigma.`);
    lines.push('    Installation will fail closed.');
  }

  if (plan.dryRun) {
    lines.push('');
    lines.push('Dry run complete. No files, locks, or state were modified.');
  }

  return lines.join('\n');
}

/**
 * Format plan as versioned JSON.
 *
 * @param {object} plan
 * @returns {string}
 */
export function formatPlanJson(plan) {
  return JSON.stringify(plan, null, 2);
}
