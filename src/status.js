import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { findPackageRoot } from './catalog.js';
import { inspectCustomizationBlock, CUSTOM_BLOCK_END, CUSTOM_BLOCK_START } from './customization.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  listGlobalDestinationGroups,
  listProjectDestinationGroups,
  loadHostRegistry,
  resolveGlobalSkillPath,
  resolveSkillPath,
} from './destinations.js';
import { pathExists, recommendedLinkMethod } from './links.js';
import { inspectProjectLock } from './project-lock.js';
import { loadGlobalState, loadProjectState } from './state.js';

export const STATUS_SCHEMA_VERSION = 1;

function hashBytes(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function samePath(a, b) {
  const left = path.resolve(a);
  const right = path.resolve(b);
  return process.platform === 'win32' ? left.toLowerCase() === right.toLowerCase() : left === right;
}

function recordedDestinations(entry) {
  const destinations = [];
  if (entry?.destination) destinations.push(entry.destination);
  if (Array.isArray(entry?.copies)) {
    for (const copy of entry.copies) {
      if (copy?.destination) destinations.push(copy.destination);
    }
  }
  return [...new Set(destinations.map((value) => String(value).replace(/\\/g, '/')))];
}

function copyRecord(entry, relativeDestination) {
  const copies = Array.isArray(entry?.copies) ? entry.copies : [];
  return copies.find((copy) => String(copy?.destination || '').replace(/\\/g, '/') === relativeDestination) || null;
}

function relativeRootOf(relativeDestination, skillId) {
  const posix = String(relativeDestination || '').replace(/\\/g, '/');
  const suffix = `/${skillId}`;
  if (posix.endsWith(suffix)) return posix.slice(0, -suffix.length);
  const dirname = posix.split('/').slice(0, -1).join('/');
  return dirname || UNIVERSAL_PROJECT_DESTINATION;
}

function hostIdsFor(groups, relativeRoot) {
  const group = (groups || []).find((item) => item.relativeRoot === relativeRoot);
  return group ? group.hosts.map((host) => host.id) : [];
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
      if (stat.isDirectory()) {
        visit(full);
      } else if (stat.isFile()) {
        const rel = path.relative(dir, full).replace(/\\/g, '/');
        files[rel] = hashBytes(fs.readFileSync(full));
      }
    }
  };

  visit(dir);
  return files;
}

function officialMarkdownShell(markdown) {
  const start = markdown.indexOf(CUSTOM_BLOCK_START);
  const end = markdown.indexOf(CUSTOM_BLOCK_END);
  if (start === -1 || end === -1 || end < start) return markdown;
  return `${markdown.slice(0, start + CUSTOM_BLOCK_START.length)}${markdown.slice(end)}`;
}

function inspectSkillMarkdown(liveMarkdown, skillId, liveHash, bundledMarkdown, bundledHash) {
  const inspection = inspectCustomizationBlock(liveMarkdown, skillId);
  if (inspection.status !== 'valid') {
    return {
      status: inspection.status,
      officialHash: liveHash,
      hasCustomContent: false,
    };
  }
  if (typeof bundledMarkdown === 'string' && officialMarkdownShell(liveMarkdown) === officialMarkdownShell(bundledMarkdown)) {
    return {
      status: 'valid',
      officialHash: bundledHash || liveHash,
      hasCustomContent: true,
    };
  }
  return {
    status: 'valid',
    officialHash: liveHash,
    hasCustomContent: true,
  };
}

function isPackagedResource(file) {
  return /^(references|scripts|assets|agents)\//.test(file);
}

function classifyLiveTree({ liveFiles, bundledFiles, skillId, skillMarkdown, bundledMarkdown }) {
  const classifications = [];
  const officialFiles = { ...liveFiles };

  if (typeof skillMarkdown === 'string' && liveFiles['SKILL.md']) {
    const markdown = inspectSkillMarkdown(
      skillMarkdown,
      skillId,
      liveFiles['SKILL.md'],
      bundledMarkdown,
      bundledFiles['SKILL.md'],
    );
    officialFiles['SKILL.md'] = markdown.officialHash;
    if (markdown.status === 'malformed') classifications.push('malformed-markers');
    else if (markdown.hasCustomContent) classifications.push('valid-customization');
  }

  const added = [];
  const replaced = [];
  const deleted = [];
  for (const file of Object.keys(officialFiles).sort()) {
    if (!(file in bundledFiles)) added.push(file);
    else if (officialFiles[file] !== bundledFiles[file]) replaced.push(file);
  }
  for (const file of Object.keys(bundledFiles).sort()) {
    if (!(file in officialFiles)) deleted.push(file);
  }

  if (added.some((file) => !isPackagedResource(file))) classifications.push('outside-addition');
  if (added.some((file) => isPackagedResource(file))) classifications.push('extra-resource');
  if (replaced.length) classifications.push('outside-change');
  if (deleted.some((file) => !isPackagedResource(file))) classifications.push('outside-deletion');
  if (deleted.some((file) => isPackagedResource(file))) classifications.push('missing-resource');

  const unique = [...new Set(classifications)];
  if (unique.length === 0) unique.push('clean');
  return {
    classifications: unique,
    files: { added, replaced, deleted },
    fingerprint: JSON.stringify(
      Object.keys(officialFiles).sort().map((file) => [file, officialFiles[file]]),
    ),
  };
}

function isInsideRoot(root, absolutePath) {
  const relative = path.relative(path.resolve(root), path.resolve(absolutePath));
  return relative === '' || (Boolean(relative) && !relative.startsWith('..') && !path.isAbsolute(relative));
}

function inspectLink(destPath, ownedAbsPaths, expectedTarget, root) {
  const method = recommendedLinkMethod();
  let raw;
  try {
    raw = fs.readlinkSync(destPath);
  } catch {
    return { method, broken: true };
  }

  const resolved = path.resolve(path.dirname(destPath), raw);
  const ownedHit = ownedAbsPaths.some((owned) => samePath(owned, resolved));
  if (!ownedHit) {
    if (!isInsideRoot(root, resolved)) {
      return { method, wrongTarget: true, target: resolved };
    }
    if (!pathExists(resolved)) {
      return { method, broken: true, target: resolved };
    }
    return { method, wrongTarget: true, target: resolved };
  }
  if (!pathExists(resolved)) {
    return { method, broken: true, target: resolved };
  }
  if (expectedTarget && !samePath(resolved, expectedTarget)) {
    return { method, wrongTarget: true, target: resolved };
  }
  return { method, target: resolved };
}

function resolveRecordedPath(root, relativeDestination, skillId, scope) {
  const relativeRoot = relativeRootOf(relativeDestination, skillId);
  try {
    return scope === 'global'
      ? resolveGlobalSkillPath(root, relativeRoot, skillId)
      : resolveSkillPath(root, relativeRoot, skillId);
  } catch {
    return {
      destination: path.resolve(root, ...String(relativeDestination).split('/')),
      relativeDestination,
      relativeRoot,
    };
  }
}

function installedRelease(state, lock) {
  for (const entry of Object.values(state.skills || {})) {
    if (entry?.release) return entry.release;
  }
  return lock.release || null;
}

function destinationGroupsFor(options, root, scope) {
  const packageRoot = options.packageRoot || findPackageRoot();
  const registry = options.registry || loadHostRegistry(packageRoot);
  const env = options.env || process.env;
  if (scope === 'global') {
    return listGlobalDestinationGroups({ registry, homeDir: root, env });
  }
  return listProjectDestinationGroups({ registry, projectRoot: root, env });
}

/**
 * Read-only Project or Global Installation status. Never writes, never fetches.
 *
 * @param {object} options
 * @returns {object}
 */
export function collectStatus(options = {}) {
  const catalog = options.catalog;
  if (!catalog) throw new Error('status requires a catalog');

  const scope = options.scope === 'global' ? 'global' : 'project';
  const root = path.resolve(scope === 'global' ? (options.homeDir || options.projectRoot) : (options.projectRoot || process.cwd()));
  const customStateDir = options.customStateDir;
  const state = scope === 'global'
    ? loadGlobalState(root, customStateDir)
    : loadProjectState(root, customStateDir);
  const lockInspect = scope === 'project' ? inspectProjectLock(root) : { kind: 'missing', lock: { skills: {}, release: null } };
  const groups = destinationGroupsFor(options, root, scope);
  const running = catalog.manifest.version;
  const skillIds = [...new Set([
    ...Object.keys(state.skills || {}),
    ...Object.keys(lockInspect.lock.skills || {}),
  ])].sort();

  const skills = skillIds.map((skillId) => {
    const catalogSkill = catalog.skills.find((item) => item.id === skillId);
    const bundledFiles = catalogSkill?.files || {};
    const entry = state.skills?.[skillId];
    const recorded = recordedDestinations(entry);
    const ownedAbs = recorded.map((rel) => path.resolve(root, ...rel.split('/')));
    const canonicalRel = recorded.find((rel) => rel.replace(/\\/g, '/').startsWith(`${UNIVERSAL_PROJECT_DESTINATION}/`))
      || `${UNIVERSAL_PROJECT_DESTINATION}/${skillId}`;
    const canonicalAbs = path.resolve(root, ...canonicalRel.split('/'));
    const lockRevision = lockInspect.lock.skills?.[skillId]?.revision || null;
    const destinations = [];

    if (recorded.length === 0) {
      destinations.push({
        relativeDestination: canonicalRel,
        relativeRoot: UNIVERSAL_PROJECT_DESTINATION,
        absolutePath: canonicalAbs,
        method: null,
        owned: false,
        hostIds: hostIdsFor(groups, UNIVERSAL_PROJECT_DESTINATION),
        classifications: ['missing-destination', 'stale-state'],
        files: { added: [], replaced: [], deleted: [] },
      });
    }

    for (const relativeDestination of recorded) {
      const resolved = resolveRecordedPath(root, relativeDestination, skillId, scope);
      const copyEntry = copyRecord(entry, relativeDestination);
      const expectedTarget = copyEntry?.dependsOn
        ? path.resolve(root, ...String(copyEntry.dependsOn).split('/'))
        : (copyEntry?.method && copyEntry.method !== 'copy' ? canonicalAbs : null);
      const hostIds = hostIdsFor(groups, resolved.relativeRoot);
      const owned = Boolean(entry);

      if (!pathExists(resolved.destination)) {
        destinations.push({
          relativeDestination,
          relativeRoot: resolved.relativeRoot,
          absolutePath: resolved.destination,
          method: copyEntry?.method || null,
          owned,
          hostIds,
          classifications: ['missing-destination', 'stale-state'],
          files: { added: [], replaced: [], deleted: [] },
        });
        continue;
      }

      const stat = fs.lstatSync(resolved.destination);
      if (stat.isSymbolicLink()) {
        const link = inspectLink(resolved.destination, ownedAbs, expectedTarget, root);
        const classifications = [];
        if (link.broken) classifications.push('broken-link');
        if (link.wrongTarget) classifications.push('wrong-target');
        if (classifications.length === 0) classifications.push('clean');
        destinations.push({
          relativeDestination,
          relativeRoot: resolved.relativeRoot,
          absolutePath: resolved.destination,
          method: link.method || copyEntry?.method || recommendedLinkMethod(),
          owned,
          hostIds,
          classifications,
          target: link.target || null,
          files: { added: [], replaced: [], deleted: [] },
        });
        continue;
      }

      const liveFiles = walkLiveFiles(resolved.destination);
      let skillMarkdown;
      const skillMdPath = path.join(resolved.destination, 'SKILL.md');
      if (pathExists(skillMdPath) && fs.lstatSync(skillMdPath).isFile()) {
        skillMarkdown = fs.readFileSync(skillMdPath, 'utf8');
      }
      const bundledMarkdownPath = catalogSkill
        ? path.join(options.packageRoot || findPackageRoot(), skillId, 'SKILL.md')
        : null;
      const bundledMarkdown = bundledMarkdownPath && pathExists(bundledMarkdownPath) && fs.lstatSync(bundledMarkdownPath).isFile()
        ? fs.readFileSync(bundledMarkdownPath, 'utf8')
        : null;
      const classified = classifyLiveTree({
        liveFiles,
        bundledFiles,
        skillId,
        skillMarkdown,
        bundledMarkdown,
      });
      destinations.push({
        relativeDestination,
        relativeRoot: resolved.relativeRoot,
        absolutePath: resolved.destination,
        method: copyEntry?.method || 'copy',
        owned,
        hostIds,
        classifications: classified.classifications,
        files: classified.files,
        fingerprint: classified.fingerprint,
      });
    }

    const copyDests = destinations.filter((dest) => dest.method === 'copy' && dest.fingerprint);
    const fingerprints = new Set(copyDests.map((dest) => dest.fingerprint));
    if (fingerprints.size > 1) {
      for (const dest of copyDests) {
        if (!dest.classifications.includes('copy-disagreement')) {
          dest.classifications.push('copy-disagreement');
        }
      }
    }

    const corruptionKinds = new Set([
      'outside-change',
      'outside-addition',
      'outside-deletion',
      'extra-resource',
      'missing-resource',
      'malformed-markers',
      'missing-destination',
      'stale-state',
      'broken-link',
      'wrong-target',
      'copy-disagreement',
    ]);
    const allKinds = destinations.flatMap((dest) => dest.classifications);
    const corruption = allKinds.some((kind) => corruptionKinds.has(kind));

    for (const dest of destinations) {
      delete dest.fingerprint;
    }

    return {
      id: skillId,
      title: catalogSkill?.title || skillId,
      installedRevision: entry?.revision || lockRevision,
      runningRevision: catalogSkill?.revision || null,
      corruption,
      destinations,
    };
  });

  const drift = skills.some((skill) => skill.destinations.some((dest) => dest.classifications.some((kind) => kind !== 'clean')));

  return {
    schemaVersion: STATUS_SCHEMA_VERSION,
    command: 'status',
    scope,
    release: {
      installed: installedRelease(state, lockInspect.lock),
      running,
    },
    readOnly: true,
    drift,
    skills,
  };
}

/**
 * Format status as versioned JSON.
 *
 * @param {object} report
 * @returns {string}
 */
export function formatStatusJson(report) {
  return JSON.stringify(report, null, 2);
}

/**
 * Format status for a terminal.
 *
 * @param {object} report
 * @returns {string}
 */
export function formatStatusHuman(report) {
  const scopeLabel = report.scope === 'global' ? 'Global Installation' : 'Project Installation';
  const lines = [
    `SigmaSkills ${scopeLabel} Status`,
    `  Scope:               ${report.scope}`,
    `  Release:             installed ${report.release?.installed || 'none'} / running v${report.release?.running || 'unknown'}`,
    `  Drift:               ${report.drift ? 'Yes' : 'No'}`,
  ];

  if (!report.skills?.length) {
    lines.push('  Skills:              none managed');
    return lines.join('\n');
  }

  for (const skill of report.skills) {
    lines.push('');
    lines.push(`  ${skill.title} (${skill.id})`);
    lines.push(`    Installed Skill Revision: ${skill.installedRevision || 'none'}`);
    lines.push(`    Running Skill Revision:   ${skill.runningRevision || 'none'}`);
    lines.push(`    Ownership:          ${skill.destinations.some((dest) => dest.owned) ? 'managed' : 'unmanaged'}`);
    lines.push(`    Corruption:         ${skill.corruption ? 'Yes' : 'No'}`);
    for (const dest of skill.destinations) {
      lines.push(`    Destination:        ${dest.relativeDestination}`);
      lines.push(`      Path:             ${dest.absolutePath}`);
      lines.push(`      Method:           ${dest.method || 'none'}`);
      lines.push(`      Owned:            ${dest.owned ? 'Yes' : 'No'}`);
      if (dest.hostIds?.length) lines.push(`      Agent Hosts:      ${dest.hostIds.join(', ')}`);
      lines.push(`      Classification:   ${dest.classifications.join(', ')}`);
      if (dest.target) lines.push(`      Link target:      ${dest.target}`);
    }
  }

  return lines.join('\n');
}
