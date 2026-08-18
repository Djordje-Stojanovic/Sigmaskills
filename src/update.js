import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { findPackageRoot } from './catalog.js';
import {
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
  loadGlobalState,
  loadProjectState,
} from './state.js';
import { collectStatus } from './status.js';
import { executeProjectInstall } from './transaction.js';

export const UPDATE_SCHEMA_VERSION = 1;
export const CANONICAL_CUSTOMIZATION_OWNER = 'canonical';

const UNSAFE_KINDS = new Set([
  'malformed-markers',
  'missing-destination',
  'stale-state',
  'broken-link',
  'wrong-target',
  'copy-disagreement',
]);

function hashBytes(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
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
  if (!pathExists(dir)) return files;
  const top = fs.lstatSync(dir);
  if (top.isSymbolicLink() || !top.isDirectory()) return files;

  const visit = (current) => {
    let entries;
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      let stat;
      try {
        stat = fs.lstatSync(full);
      } catch {
        continue;
      }
      if (stat.isSymbolicLink()) continue;
      if (stat.isDirectory()) visit(full);
      else if (stat.isFile()) {
        const rel = path.relative(dir, full).replace(/\\/g, '/');
        files[rel] = hashBytes(fs.readFileSync(full));
      }
    }
  };
  visit(dir);
  return files;
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
  const inspection = inspectCustomizationBlock(markdown, skillId);
  if (inspection.status === 'valid') return 'populated';
  if (inspection.status === 'empty') return 'empty';
  if (inspection.status === 'malformed') return 'malformed';
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
  const liveFiles = walkLiveFiles(ownerAbs);
  const baseHashes = entry?.baseHashes || {};
  const upstreamFiles = catalogSkill?.files || {};
  const officialLive = officialLiveFiles(liveFiles, liveMarkdown, bundledMarkdown, skillId);
  const liveChanged = !mapsEqual(officialLive, baseHashes);
  const upstreamChanged = !mapsEqual(baseHashes, upstreamFiles);
  const customKind = customizationKind(liveMarkdown, skillId);
  const statusKinds = (statusSkill?.destinations || []).flatMap((dest) => dest.classifications || []);
  const unsafeKinds = [...new Set(statusKinds.filter((kind) => UNSAFE_KINDS.has(kind)))];
  const missingBundled = !catalogSkill;

  let comparison = 'no-op';
  if (missingBundled) {
    comparison = 'missing-bundled';
  } else if (unsafeKinds.length || liveChanged || customKind === 'malformed') {
    comparison = 'unsafe';
  } else if (upstreamChanged && customKind === 'populated') {
    comparison = 'upstream-and-customization';
  } else if (upstreamChanged) {
    comparison = 'upstream-only';
  } else if (customKind === 'populated') {
    comparison = 'customization-only';
  }

  const blocked = comparison === 'unsafe' || comparison === 'missing-bundled';
  const diff = fileDiff(officialLive, upstreamFiles);
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
    customization: customKind,
    blocked,
    blockedReasons: blocked
      ? (missingBundled ? ['missing bundled Skill Revision'] : (unsafeKinds.length ? unsafeKinds : ['live tree drifted from recorded base']))
      : [],
    diff,
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
    });
  });

  const changed = skills.filter((skill) => (
    skill.comparison === 'upstream-only' || skill.comparison === 'upstream-and-customization'
  ));
  const unchanged = skills.filter((skill) => (
    skill.comparison === 'no-op' || skill.comparison === 'customization-only'
  ));
  const blocked = skills.filter((skill) => skill.blocked);

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
    changed,
    unchanged,
    blocked,
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
  return plan.changed.filter((skill) => !skill.blocked).map((skill) => skill.id);
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
    preservedCustomRaw: skill.rawCustom !== undefined ? skill.rawCustom : undefined,
    registry: options.registry || loadHostRegistry(findPackageRoot()),
  };
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

  const selectedBlocked = selected.filter((skill) => skill.blocked);
  if (selectedBlocked.length > 0) {
    const reasons = selectedBlocked.map((skill) => `${skill.id}: ${skill.blockedReasons.join(', ')}`).join('; ');
    throw new Error(`unsafe drift or missing revision stopped update without mutation: ${reasons}`);
  }
  if (!options.dryRun && requested.length === 0 && plan.blocked.length > 0) {
    const reasons = plan.blocked.map((skill) => `${skill.id}: ${skill.blockedReasons.join(', ')}`).join('; ');
    throw new Error(`unsafe drift or missing revision stopped update without mutation: ${reasons}`);
  }

  const result = {
    ...plan,
    dryRun: Boolean(options.dryRun),
    selected: selected.map((skill) => skill.id),
    skipped: skipped.map((skill) => skill.id),
    results: [],
  };

  if (options.dryRun) return result;

  const updatable = selected.filter((skill) => (
    skill.comparison === 'upstream-only' || skill.comparison === 'upstream-and-customization'
  ));

  for (const skill of updatable) {
    const executed = executeProjectInstall(installOptionsFor(
      skill,
      options,
      options.scope === 'global' ? 'global' : 'project',
    ));
    result.results.push({
      id: skill.id,
      success: executed.success,
      revision: executed.plan?.sourceRevision,
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
    }
  };

  renderGroup('Changed skills', plan.changed || []);
  renderGroup('Unchanged skills', plan.unchanged || []);
  renderGroup('Blocked skills', plan.blocked || []);
  if (Array.isArray(plan.selected)) {
    lines.push('');
    lines.push(`Selected: ${plan.selected.join(', ') || '(none)'}`);
    lines.push(`Skipped:  ${plan.skipped.join(', ') || '(none)'}`);
  }
  if (plan.dryRun) lines.push('', 'Dry run complete. No files were written.');
  return lines.join('\n');
}
