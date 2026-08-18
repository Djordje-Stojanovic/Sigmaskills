import path from 'node:path';
import { chooseCanonical, classifySkillPath, loadSkillBaselines } from './adoption.js';
import { loadProjectLock } from './project-lock.js';
import { isDestinationOwned, loadGlobalState, loadProjectState } from './state.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  defaultSelectedRoots,
  findDestinationConflicts,
  listGlobalDestinationGroups,
  listProjectDestinationGroups,
  loadHostRegistry,
  normalizeRelativeRoot,
  resolveGlobalSkillPath,
  resolveHomeDir,
  resolveSkillPath,
} from './destinations.js';
import { plannedExportDir } from './backup.js';
import { findPackageRoot } from './catalog.js';
import { pathExists, recommendedLinkMethod } from './links.js';

export const PLAN_SCHEMA_VERSION = 1;

function resolutionFor(classification, relativeDestination, options = {}) {
  const explicit = options.resolutions?.[relativeDestination];
  if (explicit) return explicit;
  if (classification?.kind === 'changed') return options.adoptChanged;
  if (classification?.kind === 'legacy') return options.adoptLegacy;
  if (classification?.kind === 'unverified') return options.adoptUnverified;
  if (classification?.kind === 'malformed-custom') return options.adoptMalformed;
  return undefined;
}

/**
 * Project Installation classifier: valid Sigma state, then exact Skill Revision, then resolved link.
 *
 * @param {object} params
 * @returns {(skillId: string, destination: string) => object}
 */
export function createProjectSkillClassifier({ catalog, projectRoot, customStateDir, packageRoot, scope = 'project', homeDir }) {
  const root = scope === 'global' ? path.resolve(homeDir) : projectRoot;
  const managedState = scope === 'global'
    ? loadGlobalState(root, customStateDir)
    : loadProjectState(root, customStateDir);
  const baselines = loadSkillBaselines(packageRoot || findPackageRoot());
  const resolvePath = scope === 'global' ? resolveGlobalSkillPath : resolveSkillPath;
  return (skillId, destination) => {
    const skill = catalog.skills.find((item) => item.id === skillId);
    const expectedCanonical = resolvePath(root, UNIVERSAL_PROJECT_DESTINATION, skillId);
    const entry = managedState.skills?.[skillId];
    return classifySkillPath({
      destPath: destination,
      skillId,
      bundledRevision: skill?.revision,
      bundledFiles: skill?.files || {},
      bundledBaselines: Array.isArray(baselines?.[skillId]) ? baselines[skillId] : [],
      expectedCanonicalPath: expectedCanonical.destination,
      sigmaOwned: isDestinationOwned(root, skillId, destination, customStateDir, { scope }),
      sigmaRevision: entry?.revision || null,
      baseHashes: entry?.baseHashes || null,
    });
  };
}

function destinationGroupsFor(options, root, scope) {
  if (options.destinationGroups) return options.destinationGroups;
  const packageRoot = options.packageRoot || findPackageRoot();
  const registry = options.registry || loadHostRegistry(packageRoot);
  const env = options.env || process.env;
  if (scope === 'global') {
    return listGlobalDestinationGroups({ registry, homeDir: root, env });
  }
  return listProjectDestinationGroups({ registry, projectRoot: root, env });
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
function destinationImpact(dest) {
  if (dest.migratable && !dest.resolution) {
    return { overwrite: 'needs replace, skip, or export', delete: 'none until a choice is made', backup: 'none until a choice is made' };
  }
  if (dest.adoption) {
    return { overwrite: 'adopt in place', delete: 'none', backup: 'none' };
  }
  if (dest.resolution === 'skip') {
    return { overwrite: 'none', delete: 'none', backup: 'none' };
  }
  if (dest.resolution === 'export') {
    return { overwrite: 'none', delete: 'none', backup: 'export copy' };
  }
  const deleted = dest.diff?.deleted?.length ? dest.diff.deleted.join(', ') : 'none';
  if (dest.resolution === 'replace') {
    return { overwrite: 'replace existing tree', delete: deleted, backup: 'private backup before replace' };
  }
  if (pathExists(dest.destination)) {
    return { overwrite: 'replace existing tree', delete: deleted, backup: 'sidecar restore copy' };
  }
  return { overwrite: 'create', delete: 'none', backup: 'none' };
}

export function createInstallPlan(catalog, options) {
  const { skillId, customStateDir, dryRun = false } = options;
  const scope = options.scope || 'project';
  const projectRoot = path.resolve(options.projectRoot || process.cwd());
  const homeDir = path.resolve(options.homeDir || resolveHomeDir(options.env || process.env));
  const root = scope === 'global' ? homeDir : projectRoot;
  const resolvePath = scope === 'global' ? resolveGlobalSkillPath : resolveSkillPath;

  if (!skillId || typeof skillId !== 'string') {
    throw new Error('missing or invalid skillId for install plan');
  }

  const skill = catalog.skills.find((s) => s.id === skillId);
  if (!skill) {
    throw new Error(`skill '${skillId}' was not found in Skill Pack ${catalog.manifest.name}`);
  }

  const groups = destinationGroupsFor(options, root, scope);
  const requestedRoots = selectedRootsFor(options, groups);
  const requestedMethod = requestedMethodFor(options, requestedRoots);
  const selectedRoots = rootsForRequestedMethod(requestedRoots, requestedMethod);
  const classify = createProjectSkillClassifier({
    catalog,
    projectRoot: root,
    customStateDir,
    packageRoot: options.packageRoot,
    scope,
    homeDir,
  });
  const conflictErrors = findDestinationConflicts({
    projectRoot: root,
    skillIds: [skillId],
    selectedRoots,
    isOwned: (id, destination) => isDestinationOwned(root, id, destination, customStateDir, { scope }),
    classify,
    resolvePath: resolvePath,
  });
  const fatal = conflictErrors.filter((message) => !/not owned/i.test(message));
  if (fatal.length > 0) {
    throw new Error(fatal[0]);
  }

  const currentLock = scope === 'global' ? { skills: {} } : loadProjectLock(projectRoot);
  const skillFiles = Object.keys(skill.files).sort();
  const groupByRoot = new Map(groups.filter((group) => group.selectable).map((group) => [group.relativeRoot, group]));
  const copyRoots = (options.copyRoots || []).map((copyRoot) => normalizeRelativeRoot(copyRoot));

  const destinations = selectedRoots.map((relativeRoot) => {
    const resolved = resolvePath(root, relativeRoot, skillId);
    const group = groupByRoot.get(relativeRoot);
    const kind = relativeRoot === UNIVERSAL_PROJECT_DESTINATION ? 'canonical' : 'host';
    const owned = isDestinationOwned(root, skillId, resolved.destination, customStateDir, { scope });
    const classification = classify(skillId, resolved.destination);
    const planned = destinationMethod(kind, skillId, requestedMethod, copyRoots, relativeRoot);
    const method = classification.adoptable ? (classification.method || 'copy') : planned.method;
    const dependsOn = method === 'copy' ? null : `${UNIVERSAL_PROJECT_DESTINATION}/${skillId}`;
    const resolution = classification.migratable
      ? resolutionFor(classification, resolved.relativeDestination, options)
      : undefined;
    const migratable = Boolean(classification.migratable);
    const dest = {
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
      adoption: classification.adoptable ? classification.kind : undefined,
      recognition: classification.kind,
      confidence: classification.confidence || 'none',
      baselineRevision: classification.baselineRevision,
      diff: classification.diff,
      customization: classification.customization,
      migratable,
      resolution,
      baseHashes: classification.files,
      unownedConflict: !owned && pathExists(resolved.destination) && !classification.adoptable && !migratable,
    };
    if (scope === 'global') {
      const impact = destinationImpact(dest);
      dest.overwrite = impact.overwrite;
      dest.backup = impact.backup;
      dest.delete = impact.delete;
    }
    return dest;
  });

  const destPath = destinations[0].destination;
  const relDest = destinations[0].relativeDestination;
  const unownedConflict = destinations.some((dest) => dest.unownedConflict);
  const exportRoot = options.exportDir || path.join(root, '.sigma-export');
  const claimedExports = new Set();
  for (const dest of destinations) {
    if (dest.resolution !== 'export') continue;
    let exportPath = plannedExportDir(exportRoot, skillId);
    while (claimedExports.has(exportPath)) {
      const dir = path.dirname(exportPath);
      const name = path.basename(exportPath);
      const match = name.match(/^(.*)-(\d+)$/);
      const rootName = match ? match[1] : name;
      const next = match ? Number(match[2]) + 1 : 2;
      exportPath = path.join(dir, `${rootName}-${next}`);
    }
    claimedExports.add(exportPath);
    dest.exportPath = exportPath;
  }

  const writes = destinations.flatMap((dest) => {
    if (dest.adoption) return [];
    if (dest.resolution === 'skip' || dest.resolution === 'export') return [];
    if (dest.method === 'copy') {
      return skillFiles.map((file) => `${dest.relativeDestination}/${file}`);
    }
    return [dest.relativeDestination];
  });
  const replacements = destinations.flatMap((dest) => {
    if (dest.adoption) return [];
    if (dest.resolution === 'skip' || dest.resolution === 'export') return [];
    if (!pathExists(dest.destination)) return [];
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

  const adoptionDecision = chooseCanonical(destinations.map((dest) => ({
    relativeDestination: dest.relativeDestination,
    relativeRoot: dest.relativeRoot,
    destPath: dest.destination,
    resolution: dest.resolution,
    classification: {
      kind: dest.recognition || dest.adoption || 'missing',
      adoptable: Boolean(dest.adoption),
      migratable: Boolean(dest.migratable),
      confidence: dest.confidence,
    },
  })));
  const adoption = {
    canonical: adoptionDecision.canonical.relativeDestination,
    copies: [adoptionDecision.canonical, ...adoptionDecision.others].map((copy) => ({
      destination: copy.relativeDestination,
      fate: copy.fate,
      role: copy.role,
      recognition: copy.classification?.kind || 'missing',
      confidence: copy.classification?.confidence || 'none',
      resolution: copy.resolution,
    })),
  };
  const needsResolution = destinations.some((dest) => dest.migratable && !dest.resolution);

  return {
    schemaVersion: PLAN_SCHEMA_VERSION,
    scope,
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
    adoption,
    exportDir: options.exportDir || null,
    requiresApproval: needsResolution,
    confirmationRequirements: scope === 'global' ? ['--global', '--yes'] : [],
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
      if (plan.scope === 'global' && dest.overwrite) lines.push(`      Overwrite: ${dest.overwrite}`);
      if (plan.scope === 'global' && dest.delete) lines.push(`      Delete: ${dest.delete}`);
      if (plan.scope === 'global' && dest.backup) lines.push(`      Backup: ${dest.backup}`);
      if (dest.recognition) lines.push(`      Recognition: ${dest.recognition}`);
      if (dest.confidence) lines.push(`      Provenance: ${dest.confidence}`);
      if (dest.resolution) lines.push(`      Resolution: ${dest.resolution}`);
      if (dest.exportPath) lines.push(`      Export: ${dest.exportPath}`);
      if (dest.diff) {
        const added = dest.diff.added || [];
        const replaced = dest.diff.replaced || [];
        const deleted = dest.diff.deleted || [];
        if (added.length) lines.push(`      Additions: ${added.join(', ')}`);
        if (replaced.length) lines.push(`      Replacements: ${replaced.join(', ')}`);
        if (deleted.length) lines.push(`      Deletions: ${deleted.join(', ')}`);
      }
      if (hostNames) lines.push(`      Agent Hosts: ${hostNames}`);
      return lines;
    });

  const scopeLabel = plan.scope === 'global' ? 'Global Installation' : 'Project Installation';
  const lines = [
    `SigmaSkills ${scopeLabel} Plan: ${plan.title} (${plan.skill})`,
    `  Scope:               ${plan.scope}`,
    `  Release:             v${plan.release}`,
    `  Source Revision:     ${plan.sourceRevision}`,
    `  Method:              ${plan.method}`,
    `  Destination:         ${plan.destination}`,
    `  Relative Path:       ${plan.relativeDestination}`,
    `  Canonical:           ${plan.adoption?.canonical || plan.relativeDestination}`,
    `  Resolved destinations:`,
    ...destinationLines,
    `  Required Approval:   ${plan.requiresApproval ? 'Yes' : 'None'}`,
    ...(plan.confirmationRequirements?.length
      ? [`  Required confirmation: ${plan.confirmationRequirements.join(' and ')}`]
      : []),
    `  Files to write (${plan.writes.length}):`,
    ...plan.writes.map((w) => `    + ${w}`),
  ];

  if (plan.replacements.length > 0) {
    lines.push(`  Files to replace (${plan.replacements.length}):`);
    lines.push(...plan.replacements.map((r) => `    ~ ${r}`));
  }

  if (plan.adoption?.copies?.length) {
    lines.push('  Adoption:');
    for (const copy of plan.adoption.copies) {
      lines.push(`    ${copy.destination} (${copy.role}, ${copy.fate})`);
    }
  }

  if (plan.scope !== 'global' && plan.lockChanges) {
    lines.push(`  Lock changes (${plan.lockChanges.file}):`);
    lines.push(`    Action: ${plan.lockChanges.action}`);
    lines.push(`    Next Revision: ${plan.lockChanges.next.revision}`);
  }

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
