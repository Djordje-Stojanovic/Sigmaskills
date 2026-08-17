import fs from 'node:fs';
import path from 'node:path';
import { loadProjectLock } from './project-lock.js';
import { isDestinationOwned } from './state.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  defaultSelectedRoots,
  findDestinationConflicts,
  listProjectDestinationGroups,
  loadHostRegistry,
  normalizeRelativeRoot,
  resolveSkillPath,
} from './destinations.js';
import { findPackageRoot } from './catalog.js';
import { recommendedLinkMethod } from './links.js';

export const PLAN_SCHEMA_VERSION = 1;

function destinationGroupsFor(options, projectRoot) {
  if (options.destinationGroups) return options.destinationGroups;
  const packageRoot = options.packageRoot || findPackageRoot();
  return listProjectDestinationGroups({
    registry: options.registry || loadHostRegistry(packageRoot),
    projectRoot,
    env: options.env || process.env,
  });
}

function selectedRootsFor(options, groups) {
  if (Array.isArray(options.selectedRoots) && options.selectedRoots.length > 0) {
    return options.selectedRoots.map((root) => normalizeRelativeRoot(root));
  }
  const defaults = defaultSelectedRoots(groups);
  return defaults.length > 0 ? defaults : [UNIVERSAL_PROJECT_DESTINATION];
}

function requestedMethodFor(options, selectedRoots) {
  if (options.method === 'copy' || options.method === 'link') return options.method;
  const hasHost = selectedRoots.some((root) => root !== UNIVERSAL_PROJECT_DESTINATION);
  return hasHost ? 'link' : 'copy';
}

function rootsForRequestedMethod(selectedRoots, method) {
  if (method !== 'link') return selectedRoots;
  const hasHost = selectedRoots.some((root) => root !== UNIVERSAL_PROJECT_DESTINATION);
  if (!hasHost || selectedRoots.includes(UNIVERSAL_PROJECT_DESTINATION)) return selectedRoots;
  return [UNIVERSAL_PROJECT_DESTINATION, ...selectedRoots];
}

function destinationMethod(kind, skillId, requestedMethod, copyRoots, relativeRoot) {
  if (kind === 'canonical') {
    return { method: 'copy', dependsOn: null };
  }
  if (requestedMethod === 'copy' || (Array.isArray(copyRoots) && copyRoots.includes(relativeRoot))) {
    return { method: 'copy', dependsOn: null };
  }
  return {
    method: recommendedLinkMethod(),
    dependsOn: `${UNIVERSAL_PROJECT_DESTINATION}/${skillId}`,
  };
}

/**
 * Generate an install plan for a skill without mutating the filesystem.
 *
 * @param {object} catalog Catalog object containing manifest and validated skills
 * @param {object} options
 * @param {string} options.skillId
 * @param {string} [options.projectRoot]
 * @param {string} [options.customStateDir]
 * @param {boolean} [options.dryRun]
 * @param {string[]} [options.selectedRoots]
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

  const groups = destinationGroupsFor(options, projectRoot);
  const requestedRoots = selectedRootsFor(options, groups);
  const requestedMethod = requestedMethodFor(options, requestedRoots);
  const selectedRoots = rootsForRequestedMethod(requestedRoots, requestedMethod);
  const conflictErrors = findDestinationConflicts({
    projectRoot,
    skillIds: [skillId],
    selectedRoots,
    isOwned: (id, destination) => isDestinationOwned(projectRoot, id, destination, customStateDir),
  });
  const fatal = conflictErrors.filter((message) => !/not owned/i.test(message));
  if (fatal.length > 0) {
    throw new Error(fatal[0]);
  }

  const currentLock = loadProjectLock(projectRoot);
  const skillFiles = Object.keys(skill.files).sort();
  const groupByRoot = new Map(groups.filter((group) => group.selectable).map((group) => [group.relativeRoot, group]));
  const copyRoots = (options.copyRoots || []).map((root) => normalizeRelativeRoot(root));

  const destinations = selectedRoots.map((relativeRoot) => {
    const resolved = resolveSkillPath(projectRoot, relativeRoot, skillId);
    const group = groupByRoot.get(relativeRoot);
    const kind = relativeRoot === UNIVERSAL_PROJECT_DESTINATION ? 'canonical' : 'host';
    const owned = isDestinationOwned(projectRoot, skillId, resolved.destination, customStateDir);
    const { method, dependsOn } = destinationMethod(kind, skillId, requestedMethod, copyRoots, relativeRoot);
    return {
      kind,
      relativeRoot,
      destination: resolved.destination,
      relativeDestination: resolved.relativeDestination,
      method,
      dependsOn,
      hosts: (group?.hosts || []).map((host) => ({
        id: host.id,
        displayName: host.displayName,
        detected: Boolean(host.detected),
      })),
      unownedConflict: !owned && fs.existsSync(resolved.destination),
    };
  });

  const destPath = destinations[0].destination;
  const relDest = destinations[0].relativeDestination;
  const unownedConflict = destinations.some((dest) => dest.unownedConflict);

  const writes = destinations.flatMap((dest) => {
    if (dest.method === 'copy') {
      return skillFiles.map((file) => `${dest.relativeDestination}/${file}`);
    }
    return [dest.relativeDestination];
  });
  const replacements = destinations.flatMap((dest) => {
    const owned = isDestinationOwned(projectRoot, skillId, dest.destination, customStateDir);
    if (!owned) return [];
    if (dest.method === 'copy') {
      return skillFiles.map((file) => `${dest.relativeDestination}/${file}`);
    }
    return [dest.relativeDestination];
  });

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
    destinations,
    method: requestedMethod,
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
  const destinationLines = (plan.destinations || [{ destination: plan.destination, relativeDestination: plan.relativeDestination, hosts: [] }])
    .flatMap((dest) => {
      const hostNames = (dest.hosts || []).map((host) => host.displayName).join(', ');
      const lines = [`    ${dest.destination}`];
      if (dest.relativeDestination) lines.push(`      ${dest.relativeDestination}`);
      if (dest.method) lines.push(`      Method: ${dest.method}`);
      if (dest.dependsOn) lines.push(`      Depends on: ${dest.dependsOn}`);
      if (dest.fallbackFrom) lines.push(`      Fallback from: ${dest.fallbackFrom}`);
      if (hostNames) lines.push(`      Agent Hosts: ${hostNames}`);
      return lines;
    });

  const lines = [
    `SigmaSkills Project Installation Plan: ${plan.title} (${plan.skill})`,
    `  Scope:               ${plan.scope}`,
    `  Release:             v${plan.release}`,
    `  Source Revision:     ${plan.sourceRevision}`,
    `  Method:              ${plan.method}`,
    `  Destination:         ${plan.destination}`,
    `  Relative Path:       ${plan.relativeDestination}`,
    `  Resolved destinations:`,
    ...destinationLines,
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
    const conflictDest = (plan.destinations || []).find((dest) => dest.unownedConflict)?.destination || plan.destination;
    lines.push('');
    lines.push(`  ⚠ UNOWNED CONFLICT: Destination '${conflictDest}' already exists and is not owned by Sigma.`);
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
