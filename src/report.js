import { SIGMA_PALETTE as C, wrapWords } from './terminal.js';

/**
 * Summaries for install, update and uninstall runs. Pure functions: results in, lines out.
 * One entry per skill: `{ id, pack, status, note, destinations, backup }`.
 */

const STATUS_ORDER = ['installed', 'updated', 'removed', 'current', 'edited', 'conflict', 'retired', 'not-installed', 'failed'];

const STATUS_LABEL = {
  installed: 'installed',
  updated: 'updated',
  removed: 'removed',
  current: 'already current',
  edited: 'kept (local edits)',
  conflict: 'kept (folder in the way)',
  retired: 'kept (no longer in a pack)',
  'not-installed': 'not installed',
  failed: 'failed',
};

const GOOD = new Set(['installed', 'updated', 'removed']);
const WARN = new Set(['edited', 'conflict', 'retired', 'not-installed']);

/** Turn an executeProjectInstall result for a bundled Sigma skill into a report entry. */
export function entryFromBundled(result, packTitleOf = () => 'Sigma') {
  const plan = result.plan;
  return {
    id: plan.skill,
    pack: 'sigma',
    packTitle: packTitleOf('sigma'),
    status: 'installed',
    note: '',
    destinations: (plan.destinations || []).map((dest) => ({
      relativeDestination: dest.relativeDestination || dest.destination,
      destination: dest.destination,
      method: dest.method || 'copy',
    })),
  };
}

function mark(styler, status) {
  const ascii = styler.ascii;
  if (GOOD.has(status)) return styler.style(ascii ? 'v' : '✓', C.ok, true);
  if (status === 'current') return styler.style(ascii ? '=' : '=', C.mute);
  if (WARN.has(status)) return styler.style('!', C.warn, true);
  return styler.style(ascii ? 'x' : '✗', C.err, true);
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

function pad(text, width) {
  return text.length >= width ? text : text + ' '.repeat(width - text.length);
}

function hostLines(styler, destinations, hostNames) {
  const rows = [];
  for (const dest of destinations) {
    const how = dest.method === 'link' || dest.method === 'junction' || dest.method === 'symlink' ? 'linked' : 'copy';
    const names = hostNames.get(dest.root) || '';
    rows.push(`  ${styler.style(pad(dest.root, 22), C.ink)} ${styler.style(pad(how, 7), C.mute)} ${styler.style(names, C.mute)}`);
  }
  return rows;
}

/**
 * The clean summary printed after an install, update or uninstall.
 *
 * @param {object} params
 * @param {{ style: Function, ascii?: boolean }} params.styler
 * @param {'Install'|'Update'|'Uninstall'} [params.action]
 * @param {boolean} [params.dryRun]
 * @param {'project'|'global'} params.scope
 * @param {string} params.base project root or home folder
 * @param {object[]} params.entries
 * @param {Map<string, string>} [params.hostNames] destination root to host names
 * @param {object[]} [params.roots] `{ root, method }` for the Where block
 * @param {string} [params.version]
 * @param {number} [params.seconds]
 * @returns {string[]}
 */
export function formatSummary({
  styler, action = 'Install', dryRun = false, scope, base, entries, hostNames = new Map(), roots = [], version = '', seconds,
}) {
  const s = styler.style;
  const counts = new Map();
  for (const entry of entries) counts.set(entry.status, (counts.get(entry.status) || 0) + 1);
  const done = (counts.get('installed') || 0) + (counts.get('updated') || 0) + (counts.get('removed') || 0);
  const lines = [];

  const verb = { Install: 'installed', Update: 'updated', Uninstall: 'removed' }[action];
  const allCurrent = entries.length > 0 && entries.every((entry) => entry.status === 'current');
  const headline = dryRun
    ? `Dry run: would ${action.toLowerCase()} ${plural(done || entries.length, 'skill')}. Nothing was written.`
    : allCurrent
      ? 'Everything is already up to date.'
      : done === 0
        ? `No skills ${verb}.`
        : `${plural(done, 'skill')} ${verb}${seconds !== undefined ? ` in ${seconds.toFixed(1)}s` : ''}`;
  lines.push('');
  lines.push(`${s(styler.ascii ? 'SIGMA SKILLS' : 'Σ SIGMA SKILLS', C.primary, true)}${version ? s(`  v${version}`, C.mute) : ''}`);
  lines.push(s(headline, done > 0 || dryRun ? C.ink : C.warn, true));
  lines.push('');

  const parts = STATUS_ORDER.filter((status) => counts.has(status))
    .map((status) => `${mark(styler, status)} ${counts.get(status)} ${STATUS_LABEL[status]}`);
  if (parts.length) lines.push(`  ${parts.join('   ')}`);

  const byPack = new Map();
  for (const entry of entries) {
    const key = entry.pack || 'other';
    if (!byPack.has(key)) byPack.set(key, { title: entry.packTitle || key, entries: [] });
    byPack.get(key).entries.push(entry);
  }
  if (byPack.size > 0) {
    lines.push('');
    const width = Math.max(...[...byPack.values()].map((group) => group.title.length)) + 2;
    for (const group of byPack.values()) {
      const ok = group.entries.filter((entry) => GOOD.has(entry.status) || entry.status === 'current').length;
      lines.push(`  ${s(pad(group.title, width), C.ink, true)}${s(`${ok} of ${group.entries.length}`, C.mute)}`);
    }
  }

  if (roots.length) {
    lines.push('');
    lines.push(`  ${s(scope === 'global' ? 'Global' : 'Project', C.primary, true)}  ${s(base, C.mute)}`);
    lines.push(...hostLines(styler, roots, hostNames));
  }

  const problems = entries.filter((entry) => !GOOD.has(entry.status) && entry.status !== 'current');
  if (problems.length) {
    lines.push('');
    for (const entry of problems) {
      const color = entry.status === 'failed' ? C.err : C.warn;
      lines.push(`  ${mark(styler, entry.status)} ${s(entry.id, color, true)} ${s(entry.note || STATUS_LABEL[entry.status], C.mute)}`);
    }
  }
  const backups = entries.filter((entry) => entry.backup);
  if (backups.length) {
    lines.push('');
    for (const entry of backups) lines.push(`  ${s('backup', C.info)} ${entry.id}  ${s(entry.backup, C.mute)}`);
  }

  if (!dryRun && action === 'Install' && done > 0) {
    const sample = entries.find((entry) => GOOD.has(entry.status))?.id;
    lines.push('');
    lines.push(`  ${s('Use', C.primary, true)}   ${s(`/${sample}`, C.ink)} ${s('in Claude Code', C.mute)}   ${s(`$${sample}`, C.ink)} ${s('in Codex', C.mute)}   ${s(`/skill:${sample}`, C.ink)} ${s('in Pi', C.mute)}`);
    lines.push(`  ${s('Next', C.primary, true)}  ${s('sigmaskills status', C.ink)} ${s('·', C.mute)} ${s('sigmaskills update', C.ink)} ${s('·', C.mute)} ${s('sigmaskills uninstall', C.ink)}`);
  }
  lines.push('');
  return lines;
}

const LIST_ROWS = 8;

/** The pack list for `list --packs`. */
export function formatPackList(styler, packCatalog) {
  const s = styler.style;
  const lines = [''];
  for (const pack of packCatalog.packs) {
    const flag = pack.available ? '' : s(`  (not available: ${pack.note})`, C.warn);
    lines.push(`${s(pack.title, C.primary, true)} ${s(`${pack.skills.length} skills`, C.mute)}${flag}`);
    lines.push(`  ${s('preset', C.mute)} ${s(`--preset ${pack.id}`, C.ink)}${pack.aliases.length ? s(`   aliases ${pack.aliases.join(', ')}`, C.mute) : ''}`);
    if (pack.blurb) lines.push(`  ${s(pack.blurb, C.mute)}`);
    if (pack.limit) lines.push(`  ${s(`Installs at most ${pack.limit.max} at a time. Pick by name: sigmaskills install ${pack.skills[0]?.id || '<skill>'}`, C.warn)}`);
    if (pack.skills.length) {
      const rows = wrapWords(pack.skills.map((skill) => skill.id).join(' '), 96);
      for (const row of rows.slice(0, LIST_ROWS)) lines.push(`  ${s(row, C.text)}`);
      if (rows.length > LIST_ROWS) lines.push(`  ${s(`... all ${pack.skills.length} names: sigmaskills list --packs --json`, C.mute)}`);
    }
    lines.push('');
  }
  lines.push(`${s('--preset all', C.ink)} ${s('installs every available pack.', C.mute)}`);
  lines.push('');
  return lines;
}
