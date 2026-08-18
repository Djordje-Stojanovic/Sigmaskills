import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { findPackageRoot } from './catalog.js';
import {
  applyProposedRepair,
  diagnoseCustomizationMarkers,
  extractRawCustomContent,
  injectRawCustomContent,
  inspectCustomizationBlock,
} from './customization.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  loadHostRegistry,
  resolveHomeDir,
} from './destinations.js';
import { pathExists } from './links.js';
import { inspectProjectLock } from './project-lock.js';
import {
  STATE_SCHEMA_VERSION,
  getGlobalStateDir,
  getProjectStateDir,
  loadGlobalState,
  loadProjectState,
} from './state.js';
import { collectStatus } from './status.js';
import { executeProjectInstall } from './transaction.js';
import { commitSkillBackup, exportSkillTree, inventorySkillTree } from './backup.js';

export const UPDATE_SCHEMA_VERSION = 1;
export const CANONICAL_CUSTOMIZATION_OWNER = 'canonical';

const UNSAFE_KINDS = new Set([
  'missing-destination',
  'stale-state',
  'broken-link',
  'wrong-target',
  'copy-disagreement',
]);

function hashBytes(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function omitKey(map, key) {
  const next = { ...(map || {}) };
  delete next[key];
  return next;
}

function mapsEqual(left, right) {
  const keys = new Set([...Object.keys(left || {}), ...Object.keys(right || {})]);
  for (const key of keys) {
    if ((left || {})[key] !== (right || {})[key]) return false;
  }
  return true;
}

function fileDiff(fromFiles, toFiles) {
  const added = [];
  const replaced = [];
  const deleted = [];
  for (const file of Object.keys(toFiles || {}).sort()) {
    if (!(file in (fromFiles || {}))) added.push(file);
    else if (fromFiles[file] !== toFiles[file]) replaced.push(file);
  }
  for (const file of Object.keys(fromFiles || {}).sort()) {
    if (!(file in (toFiles || {}))) deleted.push(file);
  }
  return { added, replaced, deleted };
}

function relativeRootOf(relativeDestination, skillId) {
  const posix = String(relativeDestination || '').replace(/\\/g, '/');
  const suffix = `/${skillId}`;
  if (posix.endsWith(suffix)) return posix.slice(0, -suffix.length);
  return posix.split('/').slice(0, -1).join('/') || UNIVERSAL_PROJECT_DESTINATION;
}

function walkLiveFiles(dir) {
  const files = {};
  const inventory = inventorySkillTree(dir);
  for (const [rel, entry] of Object.entries(inventory.entries || {})) {
    if (entry.kind === 'file') files[rel] = entry.hash;
  }
  return { files, inventory };
}

function detectRenames(deleted, added, fromFiles, toFiles) {
  const unusedAdded = new Set(added);
  const renames = [];
  for (const from of deleted) {
    const hash = fromFiles[from];
    const match = [...unusedAdded].find((to) => toFiles[to] === hash);
    if (!match) continue;
    unusedAdded.delete(match);
    renames.push({ from, to: match, hash });
  }
  return renames;
}

function detectTypeChanges(baseFiles, inventory) {
  const changes = [];
  for (const [rel, entry] of Object.entries(inventory.entries || {})) {
    if (baseFiles[rel] && entry.kind !== 'file') {
      changes.push({ path: rel, from: 'file', to: entry.kind });
    }
  }
  for (const rel of Object.keys(baseFiles || {})) {
    if (!inventory.entries[rel] && !Object.keys(inventory.entries).some((key) => key.startsWith(`${rel}/`))) {
      continue;
    }
    const entry = inventory.entries[rel];
    if (entry && entry.kind === 'directory' && baseFiles[rel]) {
      if (!changes.some((change) => change.path === rel)) {
        changes.push({ path: rel, from: 'file', to: 'directory' });
      }
    }
  }
  return changes;
}

function symlinkEffects(inventory) {
  return Object.entries(inventory.entries || {})
    .filter(([, entry]) => entry.kind === 'symlink')
    .map(([pathName, entry]) => ({
      path: pathName,
      target: entry.target,
      escaped: Boolean(entry.escaped),
    }));
}

function releaseRelation(installed, running) {
  if (!installed || !running) return 'unknown';
  if (installed === running) return 'same';
  const left = String(installed).split('.').map((part) => Number(part));
  const right = String(running).split('.').map((part) => Number(part));
  if (left.some(Number.isNaN) || right.some(Number.isNaN)) {
    return String(installed) < String(running) ? 'older' : 'newer';
  }
  const len = Math.max(left.length, right.length);
  for (let i = 0; i < len; i++) {
    const a = left[i] || 0;
    const b = right[i] || 0;
    if (a < b) return 'older';
    if (a > b) return 'newer';
  }
  return 'same';
}

function readChangelog(packageRoot) {
  const changelogPath = path.join(packageRoot, 'CHANGELOG.md');
  if (!pathExists(changelogPath) || !fs.lstatSync(changelogPath).isFile()) return '';
  const text = fs.readFileSync(changelogPath, 'utf8');
  const match = text.match(/## \[Unreleased\][\s\S]*?(?=\n## \[|$)/);
  return (match ? match[0] : text.slice(0, 4000)).trim();
}

function assertSupportedSchema(state, label) {
  if (typeof state?.schemaVersion === 'number' && state.schemaVersion > STATE_SCHEMA_VERSION) {
    throw new Error(
      `unsupported ${label} schemaVersion ${state.schemaVersion}; this installer supports ${STATE_SCHEMA_VERSION}`,
    );
  }
}

function loadScopeState(options, root, scope) {
  if (scope === 'global') {
    return loadGlobalState(root, options.customStateDir);
  }
  const state = loadProjectState(root, options.customStateDir);
  assertSupportedSchema(state, 'project state');
  return state;
}

function canonicalCopy(entry, skillId) {
  const copies = Array.isArray(entry?.copies) ? entry.copies : [];
  const canonical = copies.find((copy) => copy.kind === 'canonical')
    || copies.find((copy) => String(copy.destination || '').replace(/\\/g, '/').startsWith(`${UNIVERSAL_PROJECT_DESTINATION}/`));
  if (canonical) return canonical;
  if (entry?.destination) {
    return { destination: entry.destination, method: entry.method || 'copy', kind: 'canonical' };
  }
  return {
    destination: `${UNIVERSAL_PROJECT_DESTINATION}/${skillId}`,
    method: 'copy',
    kind: 'canonical',
  };
}

function readSkillMarkdown(absDir) {
  const skillMd = path.join(absDir, 'SKILL.md');
  if (!pathExists(skillMd) || !fs.lstatSync(skillMd).isFile()) return null;
  return fs.readFileSync(skillMd, 'utf8');
}

function officialLiveFiles(liveFiles, liveMarkdown, bundledMarkdown, skillId) {
  const next = { ...liveFiles };
  if (typeof liveMarkdown !== 'string' || typeof bundledMarkdown !== 'string' || !next['SKILL.md']) {
    return next;
  }
  const inspection = inspectCustomizationBlock(liveMarkdown, skillId);
  if (inspection.status !== 'valid' && inspection.status !== 'empty') return next;
  const emptied = injectRawCustomContent(
    liveMarkdown,
    extractRawCustomContent(bundledMarkdown, skillId),
    skillId,
  );
  next['SKILL.md'] = hashBytes(Buffer.from(emptied, 'utf8'));
  return next;
}

function customizationKind(markdown, skillId) {
  if (typeof markdown !== 'string') return 'absent';
  const diagnosis = diagnoseCustomizationMarkers(markdown, skillId);
  if (diagnosis.status === 'valid') return 'populated';
  if (diagnosis.status === 'empty') return 'empty';
  if (diagnosis.status === 'malformed') return 'malformed';
  return 'absent';
}

function compareSkill(options) {
  const {
    skillId,
    catalogSkill,
    entry,
    statusSkill,
    root,
    packageRoot,
    bundledMarkdown,
  } = options;

  const owner = canonicalCopy(entry, skillId);
  const ownerRel = String(owner.destination || '').replace(/\\/g, '/');
  const ownerAbs = path.resolve(root, ...ownerRel.split('/'));
  const liveMarkdown = readSkillMarkdown(ownerAbs);
  const { files: liveFiles, inventory } = walkLiveFiles(ownerAbs);
  const baseHashes = entry?.baseHashes || {};
  const upstreamFiles = catalogSkill?.files || {};
  const diagnosis = typeof liveMarkdown === 'string'
    ? diagnoseCustomizationMarkers(liveMarkdown, skillId)
    : { status: 'absent', shape: 'missing-file', repairable: false };
  const officialLive = officialLiveFiles(liveFiles, liveMarkdown, bundledMarkdown, skillId);
  const liveChanged = !mapsEqual(officialLive, baseHashes)
    || symlinkEffects(inventory).length > 0
    || detectTypeChanges(baseHashes, inventory).length > 0;
  const hasOutsideDrift = !mapsEqual(omitKey(liveFiles, 'SKILL.md'), omitKey(baseHashes, 'SKILL.md'))
    || symlinkEffects(inventory).length > 0
    || detectTypeChanges(baseHashes, inventory).length > 0;
  const upstreamChanged = !mapsEqual(baseHashes, upstreamFiles);
  const customKind = customizationKind(liveMarkdown, skillId);
  const statusKinds = (statusSkill?.destinations || []).flatMap((dest) => dest.classifications || []);
  const unsafeKinds = [...new Set(statusKinds.filter((kind) => UNSAFE_KINDS.has(kind)))];
  const missingBundled = !catalogSkill;
  const markerProblem = customKind === 'malformed';

  let comparison = 'no-op';
  let changeKind = 'none';
  if (missingBundled) {
    comparison = 'missing-bundled';
  } else if (unsafeKinds.length) {
    comparison = 'unsafe';
  } else if (markerProblem) {
    comparison = 'malformed-markers';
  } else if (liveChanged && upstreamChanged) {
    comparison = 'concurrent';
    changeKind = 'concurrent';
  } else if (liveChanged) {
    comparison = 'local-only';
    changeKind = 'local-only';
  } else if (upstreamChanged && customKind === 'populated') {
    comparison = 'upstream-and-customization';
    changeKind = 'upstream-only';
  } else if (upstreamChanged) {
    comparison = 'upstream-only';
    changeKind = 'upstream-only';
  } else if (customKind === 'populated') {
    comparison = 'customization-only';
  }

  const blocked = comparison === 'unsafe' || comparison === 'missing-bundled';
  const needsMarkerResolution = comparison === 'malformed-markers';
  const needsResolution = changeKind === 'local-only' || changeKind === 'concurrent'
    || (needsMarkerResolution && hasOutsideDrift);
  const diff = fileDiff(officialLive, upstreamFiles);
  const liveOnlyFiles = {};
  for (const [rel, entry] of Object.entries(inventory.entries || {})) {
    if (entry.kind === 'file') liveOnlyFiles[rel] = entry.hash;
  }
  const vsLiveBase = fileDiff(baseHashes, liveOnlyFiles);
  const renames = detectRenames(vsLiveBase.deleted, vsLiveBase.added, baseHashes, liveOnlyFiles);
  const renamedFrom = new Set(renames.map((item) => item.from));
  const renamedTo = new Set(renames.map((item) => item.to));
  const typeChanges = detectTypeChanges(baseHashes, inventory);
  const effects = {
    added: vsLiveBase.added.filter((file) => !renamedTo.has(file)),
    replaced: vsLiveBase.replaced,
    deleted: vsLiveBase.deleted.filter((file) => !renamedFrom.has(file)),
    overwrite: diff.replaced,
    delete: [
      ...diff.deleted,
      ...Object.keys(inventory.entries || {}).filter((rel) => {
        const entry = inventory.entries[rel];
        return (entry.kind === 'symlink' || entry.kind === 'directory') && !(rel in upstreamFiles);
      }),
    ],
    renames,
    typeChanges,
    symlinks: symlinkEffects(inventory),
  };
  const exportRoot = options.exportDir || path.join(root, '.sigma-export');
  const exportPath = path.join(exportRoot, skillId);
  const skillChangelog = [
    ...diff.added.map((file) => `+ ${file}`),
    ...diff.replaced.map((file) => `~ ${file}`),
    ...diff.deleted.map((file) => `- ${file}`),
  ].join('\n');

  return {
    id: skillId,
    title: catalogSkill?.title || statusSkill?.title || skillId,
    installedRevision: entry?.revision || statusSkill?.installedRevision || null,
    runningRevision: catalogSkill?.revision || null,
    installedRelease: entry?.release || null,
    comparison,
    changeKind,
    customization: customKind,
    blocked,
    needsResolution,
    needsMarkerResolution,
    markerShape: diagnosis.shape || null,
    repairable: Boolean(diagnosis.repairable),
    proposedRepair: diagnosis.proposedRepair,
    repairEffects: needsMarkerResolution
      ? { added: [], replaced: ['SKILL.md'], deleted: [] }
      : undefined,
    hasOutsideDrift,
    blockedReasons: blocked
      ? (missingBundled ? ['missing bundled Skill Revision'] : unsafeKinds)
      : (needsMarkerResolution ? [diagnosis.error || 'malformed customization markers'] : []),
    diff,
    effects,
    changelog: skillChangelog,
    owner: CANONICAL_CUSTOMIZATION_OWNER,
    ownerDestination: ownerRel,
    destinations: (statusSkill?.destinations || []).map((dest) => ({
      relativeDestination: dest.relativeDestination,
      method: dest.method,
      classifications: dest.classifications,
    })),
    copies: Array.isArray(entry?.copies) ? entry.copies : [],
    rawCustom: (customKind === 'populated' || customKind === 'empty') && typeof liveMarkdown === 'string'
      ? extractRawCustomContent(liveMarkdown, skillId)
      : undefined,
    backup: { required: needsResolution },
    exportPath,
    exportCollision: pathExists(exportPath),
  };
}

/**
 * Plan a Release update against the Skill Pack bundled in this CLI.
 *
 * @param {object} options
 * @returns {object}
 */
export function createUpdatePlan(options = {}) {
  const catalog = options.catalog;
  if (!catalog) throw new Error('update requires a catalog');

  const scope = options.scope === 'global' ? 'global' : 'project';
  const env = options.env || process.env;
  const homeDir = path.resolve(options.homeDir || resolveHomeDir(env));
  const projectRoot = path.resolve(options.projectRoot || process.cwd());
  const root = scope === 'global' ? homeDir : projectRoot;
  const packageRoot = options.packageRoot || findPackageRoot();
  const state = loadScopeState(options, root, scope);
  const lockInspect = scope === 'project' ? inspectProjectLock(root) : { lock: { skills: {}, release: null } };
  const status = collectStatus({
    catalog,
    projectRoot,
    homeDir,
    scope,
    customStateDir: options.customStateDir,
    packageRoot,
    env,
    registry: options.registry || loadHostRegistry(findPackageRoot()),
  });

  const skillIds = [...new Set([
    ...Object.keys(state.skills || {}),
    ...Object.keys(lockInspect.lock.skills || {}),
  ])].sort();

  const missing = skillIds.filter((skillId) => !catalog.skills.some((skill) => skill.id === skillId));
  if (missing.length > 0) {
    throw new Error(
      `missing bundled Skill Revision for ${missing.join(', ')}; update stopped without mutation`,
    );
  }

  const skills = skillIds.map((skillId) => {
    const catalogSkill = catalog.skills.find((skill) => skill.id === skillId);
    const bundledPath = path.join(packageRoot, skillId, 'SKILL.md');
    const bundledMarkdown = pathExists(bundledPath) && fs.lstatSync(bundledPath).isFile()
      ? fs.readFileSync(bundledPath, 'utf8')
      : null;
    return compareSkill({
      skillId,
      catalogSkill,
      entry: state.skills?.[skillId],
      statusSkill: status.skills.find((skill) => skill.id === skillId),
      root,
      packageRoot,
      bundledMarkdown,
      exportDir: options.exportDir,
    });
  });

  const changed = skills.filter((skill) => (
    skill.comparison === 'upstream-only'
    || skill.comparison === 'upstream-and-customization'
    || skill.comparison === 'concurrent'
    || skill.comparison === 'local-only'
  ));
  const unchanged = skills.filter((skill) => (
    skill.comparison === 'no-op' || skill.comparison === 'customization-only'
  ));
  const blocked = skills.filter((skill) => skill.blocked);
  const needsResolution = skills.filter((skill) => skill.needsResolution);
  const needsMarkerResolution = skills.filter((skill) => skill.needsMarkerResolution);
  const kinds = [...new Set(skills.map((skill) => skill.changeKind).filter((kind) => kind && kind !== 'none'))];
  const prompts = [];
  if (kinds.length) {
    prompts.push(`Resolve ${kinds.join(', ')} outside-edit cases with skip, export, or replace.`);
  }
  if (needsMarkerResolution.length) {
    prompts.push('Resolve malformed customization markers with --malformed-markers skip, repair, or replace.');
  }

  return {
    schemaVersion: UPDATE_SCHEMA_VERSION,
    command: 'update',
    scope,
    dryRun: Boolean(options.dryRun),
    release: {
      installed: status.release?.installed || null,
      running: status.release?.running || catalog.manifest.version,
      relation: releaseRelation(status.release?.installed, status.release?.running || catalog.manifest.version),
    },
    changelog: readChangelog(packageRoot),
    owner: CANONICAL_CUSTOMIZATION_OWNER,
    prompt: prompts.join(' '),
    changed,
    unchanged,
    blocked,
    needsResolution,
    needsMarkerResolution,
    skills,
  };
}

function selectSkills(plan, options) {
  const requested = Array.isArray(options.skillIds) ? options.skillIds.filter(Boolean) : [];
  if (requested.length > 0) {
    const known = new Set(plan.skills.map((skill) => skill.id));
    const unknown = requested.filter((skillId) => !known.has(skillId));
    if (unknown.length > 0) {
      throw new Error(`skill '${unknown[0]}' is not a managed installation`);
    }
    return requested;
  }
  const selected = plan.changed.filter((skill) => !skill.blocked).map((skill) => skill.id);
  const malformedChoice = options.malformedMarkers;
  if (malformedChoice === 'repair' || malformedChoice === 'replace' || malformedChoice === 'skip') {
    for (const skill of plan.needsMarkerResolution || []) {
      if (!selected.includes(skill.id)) selected.push(skill.id);
    }
  }
  return selected;
}

function installOptionsFor(skill, options, scope) {
  const copies = skill.copies || [];
  const selectedRoots = [...new Set(copies.map((copy) => relativeRootOf(copy.destination, skill.id)))];
  const roots = selectedRoots.length > 0 ? selectedRoots : [UNIVERSAL_PROJECT_DESTINATION];
  const copyRoots = copies
    .filter((copy) => copy.kind !== 'canonical' && copy.method === 'copy')
    .map((copy) => relativeRootOf(copy.destination, skill.id));
  const hasLink = copies.some((copy) => copy.kind !== 'canonical' && copy.method && copy.method !== 'copy');
  return {
    catalog: options.catalog,
    skillId: skill.id,
    projectRoot: options.projectRoot,
    homeDir: options.homeDir,
    scope,
    customStateDir: options.customStateDir,
    packageRoot: options.packageRoot,
    dryRun: false,
    env: options.env,
    selectedRoots: roots,
    method: hasLink ? 'link' : 'copy',
    copyRoots,
    adoptChanged: 'replace',
    adoptMalformed: options.malformedMarkers === 'replace' ? 'replace' : undefined,
    preservedCustomRaw: skill.rawCustom !== undefined ? skill.rawCustom : undefined,
    registry: options.registry || loadHostRegistry(findPackageRoot()),
    afterBackup: options.afterBackup,
    saveState: options.saveState,
    pruneBackups: options.pruneBackups,
  };
}

function ownerAbsPath(skill, options) {
  return path.resolve(
    options.scope === 'global' ? options.homeDir : options.projectRoot,
    ...String(skill.ownerDestination).split('/'),
  );
}

function applyCanonicalRepair(skill, options) {
  const ownerAbs = ownerAbsPath(skill, options);
  const skillMd = path.join(ownerAbs, 'SKILL.md');
  const current = fs.readFileSync(skillMd, 'utf8');
  const repaired = applyProposedRepair(current, skill.id, { editor: options.repairEditor });
  const stateDir = options.scope === 'global'
    ? getGlobalStateDir(options.homeDir, options.customStateDir)
    : getProjectStateDir(options.projectRoot, options.customStateDir);
  const backupDir = commitSkillBackup({
    stateDir,
    skillId: skill.id,
    sourceDir: ownerAbs,
  });
  if (typeof options.afterBackup === 'function') {
    options.afterBackup(backupDir);
  }
  try {
    fs.writeFileSync(skillMd, repaired, 'utf8');
  } catch (err) {
    fs.writeFileSync(skillMd, current, 'utf8');
    throw err;
  }
  return backupDir;
}

/**
 * Apply a planned update through the shared install transaction.
 *
 * @param {object} options
 * @returns {object}
 */
export function executeUpdate(options = {}) {
  const plan = createUpdatePlan(options);
  const requested = Array.isArray(options.skillIds) ? options.skillIds.filter(Boolean) : [];
  const selectedIds = selectSkills(plan, options);
  const selected = plan.skills.filter((skill) => selectedIds.includes(skill.id));
  const skipped = plan.skills.filter((skill) => !selectedIds.includes(skill.id));
  const outsideEdit = options.outsideEdit || null;
  const malformedMarkers = options.malformedMarkers || null;

  const selectedBlocked = selected.filter((skill) => skill.blocked);
  if (selectedBlocked.length > 0) {
    const reasons = selectedBlocked.map((skill) => `${skill.id}: ${skill.blockedReasons.join(', ')}`).join('; ');
    throw new Error(`unsafe drift or missing revision stopped update without mutation: ${reasons}`);
  }
  if (!options.dryRun && requested.length === 0 && plan.blocked.length > 0) {
    const reasons = plan.blocked.map((skill) => `${skill.id}: ${skill.blockedReasons.join(', ')}`).join('; ');
    throw new Error(`unsafe drift or missing revision stopped update without mutation: ${reasons}`);
  }

  const selectedMalformed = selected.filter((skill) => skill.needsMarkerResolution);
  if (!options.dryRun && selectedMalformed.length > 0 && !malformedMarkers) {
    const ids = selectedMalformed.map((skill) => `${skill.id} (${skill.markerShape || 'malformed'})`).join(', ');
    throw new Error(`malformed customization markers need --malformed-markers skip, repair, or replace: ${ids}`);
  }
  if (!options.dryRun && requested.length === 0 && (plan.needsMarkerResolution || []).length > 0 && !malformedMarkers) {
    const ids = plan.needsMarkerResolution.map((skill) => `${skill.id} (${skill.markerShape || 'malformed'})`).join(', ');
    throw new Error(`malformed customization markers need --malformed-markers skip, repair, or replace: ${ids}`);
  }

  const unresolved = selected.filter((skill) => skill.needsResolution && !skill.needsMarkerResolution);
  if (!options.dryRun && unresolved.length > 0 && !outsideEdit) {
    const ids = unresolved.map((skill) => `${skill.id} (${skill.changeKind})`).join(', ');
    throw new Error(`outside edits need --outside-edit replace, skip, or export before mutation: ${ids}`);
  }

  const result = {
    ...plan,
    dryRun: Boolean(options.dryRun),
    selected: selected.map((skill) => skill.id),
    skipped: skipped.map((skill) => skill.id),
    outsideEdit,
    malformedMarkers,
    results: [],
  };

  if (options.dryRun) return result;

  const updatableComparisons = new Set(['upstream-only', 'upstream-and-customization', 'local-only', 'concurrent']);
  for (const skill of selected) {
    if (skill.needsMarkerResolution) {
      if (malformedMarkers === 'skip') {
        result.results.push({ id: skill.id, success: true, action: 'skip' });
        continue;
      }
      if (malformedMarkers === 'repair') {
        if (!skill.repairable) {
          throw new Error(`${skill.id}: invalid repair; marker boundaries cannot be inferred`);
        }
        if (skill.hasOutsideDrift && !outsideEdit) {
          throw new Error(`malformed markers combined with outside edits need --outside-edit skip, export, or replace: ${skill.id}`);
        }
        if (skill.hasOutsideDrift && outsideEdit === 'replace') {
          const executed = executeProjectInstall(installOptionsFor(
            skill,
            { ...options, malformedMarkers: 'replace' },
            options.scope === 'global' ? 'global' : 'project',
          ));
          const backupDir = (executed.plan?.destinations || []).find((dest) => dest.privateBackup)?.privateBackup;
          result.results.push({
            id: skill.id,
            success: executed.success,
            revision: executed.plan?.sourceRevision,
            action: 'replace',
            backupIntegrity: backupDir ? { ok: true, path: backupDir } : { ok: true },
          });
          continue;
        }
        const backupDir = applyCanonicalRepair(skill, options);
        if (skill.hasOutsideDrift && outsideEdit === 'export') {
          if (skill.exportCollision) throw new Error(`export collision at '${skill.exportPath}'`);
          exportSkillTree({
            sourceDir: ownerAbsPath(skill, options),
            exportRoot: path.dirname(skill.exportPath),
            skillId: skill.id,
            dest: skill.exportPath,
            refuseCollision: true,
          });
        }
        result.results.push({ id: skill.id, success: true, action: 'repair', backupIntegrity: { ok: true, path: backupDir } });
        continue;
      }
      if (malformedMarkers === 'replace') {
        if (skill.hasOutsideDrift && !outsideEdit) {
          throw new Error(`malformed markers combined with outside edits need --outside-edit skip, export, or replace: ${skill.id}`);
        }
        if (skill.hasOutsideDrift && (outsideEdit === 'skip' || outsideEdit === 'export')) {
          if (outsideEdit === 'export') {
            if (skill.exportCollision) throw new Error(`export collision at '${skill.exportPath}'`);
            exportSkillTree({
              sourceDir: ownerAbsPath(skill, options),
              exportRoot: path.dirname(skill.exportPath),
              skillId: skill.id,
              dest: skill.exportPath,
              refuseCollision: true,
            });
          }
          result.results.push({ id: skill.id, success: true, action: outsideEdit });
          continue;
        }
        const executed = executeProjectInstall(installOptionsFor(
          skill,
          options,
          options.scope === 'global' ? 'global' : 'project',
        ));
        const backupDir = (executed.plan?.destinations || []).find((dest) => dest.privateBackup)?.privateBackup;
        result.results.push({
          id: skill.id,
          success: executed.success,
          revision: executed.plan?.sourceRevision,
          action: 'replace',
          backupIntegrity: backupDir ? { ok: true, path: backupDir } : { ok: true },
        });
        continue;
      }
    }
    if (skill.needsResolution && outsideEdit === 'skip') {
      result.results.push({ id: skill.id, success: true, action: 'skip' });
      continue;
    }
    if (skill.needsResolution && outsideEdit === 'export') {
      if (skill.exportCollision) {
        throw new Error(`export collision at '${skill.exportPath}'`);
      }
      const exported = exportSkillTree({
        sourceDir: ownerAbsPath(skill, options),
        exportRoot: path.dirname(skill.exportPath),
        skillId: skill.id,
        dest: skill.exportPath,
        refuseCollision: true,
      });
      result.results.push({ id: skill.id, success: true, action: 'export', exportPath: exported });
      continue;
    }
    if (!updatableComparisons.has(skill.comparison)) continue;
    const executed = executeProjectInstall(installOptionsFor(
      skill,
      options,
      options.scope === 'global' ? 'global' : 'project',
    ));
    const backupDir = (executed.plan?.destinations || []).find((dest) => dest.privateBackup)?.privateBackup;
    result.results.push({
      id: skill.id,
      success: executed.success,
      revision: executed.plan?.sourceRevision,
      action: 'replace',
      backupIntegrity: backupDir ? { ok: true, path: backupDir } : { ok: true },
    });
  }

  return result;
}

/**
 * @param {object} plan
 * @returns {string}
 */
export function formatUpdateJson(plan) {
  const payload = JSON.parse(JSON.stringify({
    ...plan,
    skills: (plan.skills || []).map(({ rawCustom, copies, ...skill }) => skill),
    changed: (plan.changed || []).map(({ rawCustom, copies, ...skill }) => skill),
    unchanged: (plan.unchanged || []).map(({ rawCustom, copies, ...skill }) => skill),
    blocked: (plan.blocked || []).map(({ rawCustom, copies, ...skill }) => skill),
    needsResolution: (plan.needsResolution || []).map(({ rawCustom, copies, ...skill }) => skill),
    needsMarkerResolution: (plan.needsMarkerResolution || []).map(({ rawCustom, copies, ...skill }) => skill),
  }));
  return JSON.stringify(payload, null, 2);
}

/**
 * @param {object} plan
 * @returns {string}
 */
export function formatUpdateHuman(plan) {
  const scopeLabel = plan.scope === 'global' ? 'Global Installation' : 'Project Installation';
  const lines = [
    `SigmaSkills ${scopeLabel} Update`,
    `  Installed Release:   ${plan.release?.installed || 'none'}`,
    `  Running Release:     ${plan.release?.running || 'unknown'} (${plan.release?.relation || 'unknown'})`,
    `  Customization owner: ${plan.owner} copy`,
  ];
  if (plan.changelog) {
    lines.push('  Changelog:');
    for (const line of plan.changelog.split('\n')) {
      lines.push(`    ${line}`);
    }
  }

  const renderGroup = (title, skills) => {
    lines.push('');
    lines.push(`${title}:`);
    if (!skills.length) {
      lines.push('  (none)');
      return;
    }
    for (const skill of skills) {
      lines.push(`  ${skill.title} (${skill.id}) [${skill.comparison}]`);
      if (skill.changelog) {
        lines.push('    Whole-skill diff:');
        for (const line of skill.changelog.split('\n')) lines.push(`      ${line}`);
      }
      if (skill.blockedReasons?.length) {
        lines.push(`    blocked: ${skill.blockedReasons.join(', ')}`);
      }
      if (skill.needsMarkerResolution) {
        lines.push(`    marker shape: ${skill.markerShape || 'malformed'}`);
        lines.push(`    repairable: ${skill.repairable ? 'yes' : 'no'}`);
        if (skill.repairEffects) {
          lines.push(`    repair replacements: ${(skill.repairEffects.replaced || []).join(', ') || '(none)'}`);
          lines.push(`    repair deletions: ${(skill.repairEffects.deleted || []).join(', ') || '(none)'}`);
        }
        if (skill.effects?.delete?.length || skill.effects?.added?.length) {
          lines.push(`    whole-skill overwrite: ${(skill.effects.overwrite || []).join(', ') || '(none)'}`);
          lines.push(`    whole-skill deletions: ${(skill.effects.delete || []).join(', ') || '(none)'}`);
        }
        if (skill.proposedRepair) {
          lines.push('    proposed repair bytes:');
          for (const line of skill.proposedRepair.split('\n')) lines.push(`      ${line}`);
        }
      }
    }
  };

  renderGroup('Changed skills', plan.changed || []);
  renderGroup('Unchanged skills', plan.unchanged || []);
  renderGroup('Blocked skills', plan.blocked || []);
  renderGroup('Malformed markers', plan.needsMarkerResolution || []);
  if (plan.prompt) {
    lines.push('');
    lines.push(`Prompt: ${plan.prompt}`);
  }
  const localOnly = (plan.skills || []).filter((skill) => skill.changeKind === 'local-only');
  const upstreamOnly = (plan.skills || []).filter((skill) => skill.changeKind === 'upstream-only');
  const concurrent = (plan.skills || []).filter((skill) => skill.changeKind === 'concurrent');
  renderGroup('Local-only changes', localOnly);
  renderGroup('Upstream-only changes', upstreamOnly);
  renderGroup('Concurrent local/upstream changes', concurrent);
  if (Array.isArray(plan.selected)) {
    lines.push('');
    lines.push(`Selected: ${plan.selected.join(', ') || '(none)'}`);
    lines.push(`Skipped:  ${plan.skipped.join(', ') || '(none)'}`);
  }
  if (plan.dryRun) lines.push('', 'Dry run complete. No files were written.');
  return lines.join('\n');
}
