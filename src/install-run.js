import { executeProjectInstall, executeProjectInstallBatch } from './transaction.js';
import { UNIVERSAL_PROJECT_DESTINATION } from './destinations.js';
import { installPackSkills } from './pack-install.js';
import { entryFromBundled } from './report.js';

/**
 * Install a mixed selection: bundled Sigma skills go through the transactional engine, pack
 * skills through the pack installer. One call, one list of report entries.
 *
 * Bundled skills install first, as one transaction. If a pack skill then fails, the bundled
 * ones stay installed and the failure shows in the summary; nothing is rolled back silently.
 *
 * @param {object} params
 * @param {object} params.catalog bundled catalog
 * @param {object[]} params.skills chosen skills from resolveSelection() or the wizard
 * @param {'project'|'global'} params.scope
 * @param {string[]} [params.roots] host destination roots; the universal root is implied
 * @param {'link'|'copy'} [params.method]
 * @param {object} [params.adopt] `{ adoptChanged, adoptLegacy, adoptUnverified, adoptMalformed, exportDir }`
 * @param {object} params.fetcher from createSourceFetcher()
 * @returns {{ entries: object[], bundled: object[] }}
 */
export function runInstall(params) {
  const {
    catalog, skills, scope, projectRoot, homeDir, customStateDir, packageRoot, env, dryRun = false, force = false,
    adopt = {}, fetcher, version = '', onProgress, packTitles = new Map(),
  } = params;
  const hostRoots = (params.roots || []).filter((root) => root !== UNIVERSAL_PROJECT_DESTINATION);
  const method = params.method || undefined;
  const entries = [];
  let bundledResults = [];

  const bundledIds = skills.filter((skill) => skill.kind === 'bundled').map((skill) => skill.id);
  if (bundledIds.length > 0) {
    const installParams = {
      catalog, projectRoot, homeDir, scope, customStateDir, packageRoot, dryRun, env,
      selectedRoots: hostRoots.length > 0 ? hostRoots : undefined,
      method,
      ...adopt,
    };
    onProgress?.({ phase: 'bundled', count: bundledIds.length });
    bundledResults = bundledIds.length === 1
      ? [executeProjectInstall({ ...installParams, skillId: bundledIds[0] })]
      : executeProjectInstallBatch({ ...installParams, skillIds: bundledIds });
    for (const result of bundledResults) {
      const entry = entryFromBundled(result, (id) => packTitles.get(id) || 'Sigma');
      entry.destinations = entry.destinations.map((dest) => ({ ...dest, root: dest.root || rootOf(dest.relativeDestination) }));
      entries.push(entry);
    }
  }

  const external = skills.filter((skill) => skill.kind === 'external');
  if (external.length > 0) {
    const { results } = installPackSkills({
      skills: external, scope, projectRoot, homeDir, customStateDir, roots: hostRoots, method, dryRun, force, fetcher, version, onProgress,
    });
    for (const result of results) entries.push({ ...result, packTitle: packTitles.get(result.pack) || result.pack });
  }
  return { entries, bundled: bundledResults };
}

function rootOf(relativeDestination) {
  const parts = String(relativeDestination).split('/');
  return parts.slice(0, -1).join('/');
}
