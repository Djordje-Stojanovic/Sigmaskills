import fs from 'node:fs';
import path from 'node:path';
import { KeyInput } from './key-input.js';
import { SIGMA_PALETTE as C, TerminalRenderer, createStyler, wrapWords } from './terminal.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  listGlobalDestinationGroups,
  listProjectDestinationGroups,
  loadHostRegistry,
  searchHosts,
} from './destinations.js';
import { POPULAR_AGENTS, describeRoots, detectPopularAgents } from './agents.js';
import { createSourceFetcher, findSkillDirs } from './pack-source.js';
import { packStatus, uninstallPackSkills } from './pack-install.js';
import { runInstall } from './install-run.js';
import { executeUninstall } from './uninstall.js';
import { loadGlobalState, loadProjectState } from './state.js';
import { formatSummary } from './report.js';
import { isSearchChar } from './destination-items.js';
import { CATEGORIES } from './packs.js';

/**
 * The full-screen installer: what to install (groups and presets), where (Agent Hosts), a
 * review, then live progress and a clean summary. It draws with the DESIGN.md palette.
 * Plain terminals, CI and pipes never reach it: runWizard returns null and the caller falls
 * back to the line-by-line installer.
 */

const RESET = '\x1b[0m';
const STEPS = ['What', 'Where', 'Review'];
const TITLES = ['Pick packs to install', 'Pick where they go', 'Review and confirm'];

/** Which rows scroll into view. Pure, so tests can check it. */
export function windowRows(total, cursor, limit) {
  if (total <= limit) return { start: 0, end: total };
  let start = Math.max(0, cursor - Math.floor(limit / 2));
  if (start + limit > total) start = total - limit;
  return { start, end: start + limit };
}

/**
 * The packs the wizard shows: every multi-skill pack as itself, in registry order, under Packs,
 * then the one-skill sources under their category (Design, Engineering...). An available pack with no skills is hidden.
 */
export function orderPacks(packs) {
  const shown = packs.filter((pack) => !pack.available || pack.skills.length > 0);
  // A folder pack (Local) stays a pack, however few skills its folder holds.
  const single = (pack) => pack.available && pack.skills.length === 1 && !(pack.sources || []).some((source) => source.type === 'dir');
  const rank = (pack) => (CATEGORIES.includes(pack.category) ? CATEGORIES.indexOf(pack.category) : CATEGORIES.length);
  return [
    ...shown.filter((pack) => !single(pack)).map((pack) => ({ ...pack, group: 'Packs' })),
    ...shown.filter(single).sort((a, b) => rank(a) - rank(b)).map((pack) => ({ ...pack, group: pack.category || 'Other' })),
  ];
}

/** Build the rows of the "what" screen: a heading per group, one row per pack, skill rows under an open pack. */
export function buildPackRows(packs, expanded, query) {
  const needle = String(query || '').trim().toLowerCase();
  const rows = [];
  if (needle) {
    for (const pack of packs) {
      for (const skill of pack.skills) {
        if (skill.id.includes(needle) || (skill.description || '').toLowerCase().includes(needle) || (skill.group || '').toLowerCase().includes(needle) || pack.title.toLowerCase().includes(needle) || (pack.category || '').toLowerCase().includes(needle)) {
          rows.push({ type: 'skill', pack, skill });
        }
      }
    }
    return rows;
  }
  for (const [index, pack] of packs.entries()) {
    if (pack.group && pack.group !== packs[index - 1]?.group) rows.push({ type: 'group', group: pack.group });
    rows.push({ type: 'pack', pack });
    if (expanded.has(pack.id)) for (const skill of pack.skills) rows.push({ type: 'skill', pack, skill });
  }
  return rows;
}

/**
 * The part of a skill's text that shows in the preview: lines wrapped to the width with their
 * indent kept, and the scroll offset clamped to the text. Pure, so tests can check it.
 */
export function previewFrame(text, width, height, offset) {
  const lines = String(text).split(/\r?\n/).flatMap((line) => {
    const flat = line.replace(/\t/g, '  ').trimEnd();
    const indent = flat.match(/^ */)[0].slice(0, Math.max(0, width - 10));
    return flat.trim() ? wrapWords(flat.trim(), width - indent.length).map((part) => indent + part) : [''];
  });
  const top = Math.max(0, Math.min(offset, lines.length - height));
  return { lines: lines.slice(top, top + height), top, total: lines.length };
}

function checkbox(state) {
  return state === 'all' ? '●' : state === 'some' ? '◐' : '○';
}

function packState(pack, selected) {
  const count = pack.skills.filter((skill) => selected.has(skill.id)).length;
  if (count === 0) return { state: 'none', count };
  return { state: count === pack.skills.length ? 'all' : 'some', count };
}

/**
 * One screen of the wizard, drawn as one vertical flow (the clack layout of `npx skills`): a rail
 * on the left, finished steps folded into one line each, the active step open, and `└` at the end.
 */
class Screen {
  constructor(renderer, version) {
    this.renderer = renderer;
    this.version = version;
  }

  get width() {
    return Math.max(20, this.renderer.width - 1);
  }

  get height() {
    return Math.max(8, this.renderer.height - 1);
  }

  /**
   * One row from `[text, hex, bold]` parts, clipped to the width and padded with the canvas.
   * `right` is one more part, set against the right edge when it fits.
   */
  row(parts, right) {
    let used = 0;
    let out = '';
    // The right part keeps its room; a long left part is clipped instead.
    const limit = right?.[0] ? this.width - right[0].length - 2 : this.width;
    for (const part of parts) {
      const [text, hex = C.text, bold = false] = typeof part === 'string' ? [part] : part;
      const room = limit - used;
      if (room <= 0) break;
      const clipped = text.length > room ? `${text.slice(0, Math.max(0, room - 1))}…` : text;
      out += this.renderer.style(clipped, hex, bold);
      used += clipped.length;
    }
    if (right && right[0] && used + right[0].length + 2 <= this.width) {
      out += ' '.repeat(this.width - used - right[0].length) + this.renderer.style(right[0], right[1] || C.mute, right[2]);
      used = this.width;
    }
    return out + ' '.repeat(Math.max(0, this.width - used));
  }

  blank() {
    return this.row(['']);
  }

  /** A line on the rail. */
  rail(parts = [], right) {
    return this.row([['│  ', C.hairlineStrong], ...parts], right);
  }

  /** A list row on the rail: the cursor mark, then the parts. */
  item(here, parts) {
    return this.row([['│ ', C.hairlineStrong], here ? ['❯ ', C.primary, true] : ['  ', C.mute], ...parts]);
  }

  /** A group title with a hairline to the edge. */
  heading(title) {
    return this.rail([[title, C.ink, true], [` ${'─'.repeat(Math.max(0, this.width - title.length - 4))}`, C.hairline]]);
  }

  /** The top of every screen: the brand, each finished step on one line, then the active step. */
  header(step, done = []) {
    const lines = [this.row([['┌  ', C.hairlineStrong], ['Σ SIGMA SKILLS', C.primary, true], [`  v${this.version}`, C.mute]]), this.rail()];
    done.forEach((text, index) => lines.push(this.row([['◇  ', C.primary], [STEPS[index].padEnd(8), C.mute], [text, C.text]])));
    if (done.length) lines.push(this.rail());
    lines.push(this.row([['◆  ', C.primary, true], [TITLES[step], C.ink, true]], [`step ${step + 1} of ${STEPS.length}`, C.mute]));
    return lines;
  }

  /** Fill the rail down to the footer, then the footer: hint lines on the rail and the closing `└` line. */
  footer(lines, hints, last) {
    while (lines.length < this.height - hints.length - 1) lines.push(this.rail());
    for (const hint of hints) lines.push(typeof hint === 'string' ? hint : this.rail(hint));
    lines.push(this.row([['└  ', C.hairlineStrong], ...last]));
    return lines;
  }

  paint(lines) {
    const fill = this.renderer.fill();
    const rows = lines.slice(0, this.height);
    while (rows.length < this.height) rows.push(this.blank());
    this.renderer.screen(rows.map((line) => (fill ? line.split(RESET).join(`${RESET}${fill}`) : line)));
  }
}

function hostRowsFor(groups, homeDir, query) {
  const hosts = searchHosts(groups, '');
  const byId = new Map(hosts.map((host) => [host.id, host]));
  const found = detectPopularAgents(homeDir);
  const rows = [];
  for (const agent of POPULAR_AGENTS) {
    const host = byId.get(agent.id);
    if (!host || !host.relativeRoot) continue;
    rows.push({ host, root: host.relativeRoot, universal: host.relativeRoot === UNIVERSAL_PROJECT_DESTINATION, found: found.has(agent.id) || host.detected });
  }
  if (query) {
    const popular = new Set(rows.map((row) => row.host.id));
    for (const host of searchHosts(groups, query)) {
      if (popular.has(host.id) || !host.relativeRoot) continue;
      rows.push({ host, root: host.relativeRoot, universal: host.relativeRoot === UNIVERSAL_PROJECT_DESTINATION, found: host.detected, extra: true });
    }
  }
  return rows;
}

/** Whether this terminal can show the wizard: a real, colored TTY with no static flags. */
export function wizardAvailable(io, options = {}) {
  const probe = new TerminalRenderer(io, options);
  const available = !probe.static;
  probe.cleanup();
  return available;
}

/**
 * Run the wizard. Returns an exit code, or null when the terminal cannot show it.
 *
 * @param {object} params
 * @returns {Promise<number|null>}
 */
export async function runWizard(params) {
  const {
    catalog, packCatalog, packageRoot, projectRoot, homeDir, customStateDir, io, options = {}, version,
  } = params;
  const env = io.env || process.env;
  const renderer = new TerminalRenderer(io, options);
  if (renderer.static) {
    renderer.cleanup();
    return null;
  }
  const input = new KeyInput(io.stdin, false);
  const screen = new Screen(renderer, version);
  const registry = loadHostRegistry(packageRoot);

  const state = {
    scope: params.initialScope === 'global' ? 'global' : 'project',
    selected: new Set(),
    expanded: new Set(),
    roots: new Set(),
    method: 'link',
    resolution: null,
    notice: '',
    drop: new Set(),
    pendingDrop: null,
  };
  const groupsFor = (scope) => (scope === 'global'
    ? listGlobalDestinationGroups({ registry, homeDir, env })
    : listProjectDestinationGroups({ registry, projectRoot, env }));
  let groups = groupsFor(state.scope);
  const resetRoots = () => {
    state.roots = new Set();
    const found = detectPopularAgents(homeDir);
    for (const row of hostRowsFor(groups, homeDir, '')) {
      if (!row.universal && found.has(row.host.id)) state.roots.add(row.root);
    }
  };
  resetRoots();

  const scopeName = (scope = state.scope) => (scope === 'global' ? 'Global' : 'Project');
  // A path under the home folder shows as ~, so the scope line fits.
  const tilde = (dir) => (dir === homeDir || dir.startsWith(homeDir + path.sep) ? `~${dir.slice(homeDir.length)}` : dir);
  const scopeRoot = () => tilde(state.scope === 'global' ? homeDir : projectRoot);
  /** u, x, the installed marks and the install itself all act on this one scope; both steps can switch it. */
  const switchScope = () => {
    state.scope = state.scope === 'project' ? 'global' : 'project';
    groups = groupsFor(state.scope);
    resetRoots();
    state.drop.clear();
  };
  const plural = (n, word = 'skill') => `${n} ${word}${n === 1 ? '' : 's'}`;
  /** The finished steps, one line each, for the header of a later step. */
  const doneWhat = () => {
    const picked = state.selected.size;
    const packs = packCatalog.packs.filter((pack) => pack.skills.some((skill) => state.selected.has(skill.id))).length;
    const parts = picked ? [`${plural(picked)} from ${plural(packs, 'pack')}`] : [];
    if (state.drop.size) parts.push(`${state.drop.size} to remove`);
    return parts.join(', ');
  };
  const doneWhere = () => {
    const hosts = state.roots.size;
    return `${scopeName()} · .agents/skills${hosts ? ` + ${plural(hosts, 'host folder')}, ${state.method === 'link' ? 'linked' : 'copied'}` : ''}`;
  };
  const packOf = (id) => packCatalog.packs.find((pack) => pack.skills.some((skill) => skill.id === id));
  const stateParams = (scope = state.scope) => ({ scope, projectRoot, homeDir, customStateDir });
  const installedByScope = new Map();
  const installedNow = (scope = state.scope) => {
    if (!installedByScope.has(scope)) {
      try {
        const sigma = scope === 'global' ? loadGlobalState(path.resolve(homeDir), customStateDir) : loadProjectState(path.resolve(projectRoot), customStateDir);
        installedByScope.set(scope, new Set([...packStatus(stateParams(scope)).map((row) => row.id), ...Object.keys(sigma.skills || {})]));
      } catch {
        installedByScope.set(scope, new Set());
      }
    }
    return installedByScope.get(scope);
  };
  /** The slots a limited pack holds now: what is installed (minus drops) and what is picked. */
  const slotsOf = (pack) => {
    const own = new Set(pack.skills.map((skill) => skill.id));
    const held = new Set([...installedNow()].filter((id) => own.has(id) && !state.drop.has(id)));
    for (const id of state.selected) if (own.has(id)) held.add(id);
    return held;
  };
  let previewFetcher = null;
  const selectedSkills = () => packCatalog.packs.flatMap((pack) => pack.skills).filter((skill) => state.selected.has(skill.id));

  // ---- step 1: what ------------------------------------------------------------------------
  async function stepWhat() {
    let cursor = 0;
    let move = 1;
    let query = '';
    let searching = false;
    const packs = orderPacks(packCatalog.packs);
    const nameWidth = Math.max(14, ...packs.map((pack) => pack.title.length + 2));
    while (true) {
      const rows = buildPackRows(packs, state.expanded, query);
      cursor = rows.length ? Math.min(cursor, rows.length - 1) : 0;
      // A heading is not a stop: the cursor walks past it in the direction it was moving.
      while (rows[cursor]?.type === 'group') cursor = (cursor + move + rows.length) % rows.length;
      const focus = rows[cursor];
      const installed = [...installedNow()];
      const updatable = installed.filter((id) => packOf(id));
      const other = state.scope === 'global' ? 'project' : 'global';
      // The other scope is counted too, so a forgotten Global Installation shows up from any project.
      const elsewhere = installedNow(other).size;
      const countWidth = Math.max(...packs.map((pack) => `${pack.skills.length}/${pack.skills.length}`.length));
      const paint = () => {
        const lines = screen.header(0);
        lines.push(screen.rail([[scopeName(), C.ink, true], ['  ', C.mute], [scopeRoot(), C.mute]], [`s switch to ${scopeName(state.scope === 'global' ? 'project' : 'global')}`, C.mute]));
        lines.push(screen.rail([
          ...(installed.length
            ? [[`${installed.length} installed here`, C.ok], [`   u update ${updatable.length === installed.length ? 'them' : updatable.length} · x uninstall them`, C.mute]]
            : [['Nothing installed here yet', C.mute]]),
          [elsewhere ? `   ${elsewhere} more in ${scopeName(other)}: s to see them` : '', C.warn],
        ]));
        lines.push(screen.rail(searching || query ? [['Filter  ', C.mute], [`${query}${searching ? '▏' : ''}`, C.ink]] : []));
        const footer = 8;
        const room = Math.max(3, screen.height - lines.length - footer);
        const view = windowRows(rows.length, cursor, room);
        for (let index = view.start; index < view.end; index += 1) {
          const item = rows[index];
          const here = index === cursor;
          if (item.type === 'group') {
            lines.push(screen.heading(item.group));
          } else if (item.type === 'pack') {
            const ordinal = packs.indexOf(item.pack);
            const { state: boxState, count } = packState(item.pack, state.selected);
            const slots = item.pack.limit ? slotsOf(item.pack).size : 0;
            const open = state.expanded.has(item.pack.id);
            const full = item.pack.limit && slots >= item.pack.limit.max;
            lines.push(screen.item(here, [
              [item.pack.available ? checkbox(boxState) : '!', !item.pack.available ? C.warn : boxState === 'none' ? C.mute : C.primary],
              [ordinal < 10 ? ` ${(ordinal + 1) % 10} ` : '   ', C.hairlineStrong],
              [item.pack.title.padEnd(nameWidth), !item.pack.available ? C.mute : here ? C.ink : C.text, here],
              [`${(!item.pack.available ? 'n/a' : item.pack.limit ? `${slots}/${item.pack.limit.max}` : `${count}/${item.pack.skills.length}`).padStart(countWidth)}  `, full ? C.warn : count ? C.primary : C.mute],
              [open ? '▾ ' : '', C.mute],
              [item.pack.available ? item.pack.blurb : item.pack.note, item.pack.available ? C.mute : C.warn],
            ]));
          } else {
            const chosen = state.selected.has(item.skill.id);
            const have = installedNow().has(item.skill.id);
            const going = state.drop.has(item.skill.id);
            const last = rows[index + 1]?.type !== 'skill' || rows[index + 1].pack !== item.pack;
            lines.push(screen.item(here, [
              [query ? '' : last ? '  └─ ' : '  ├─ ', C.hairlineStrong],
              [chosen || (have && !going) ? '●' : '○', chosen ? C.primary : have && !going ? C.ok : C.mute],
              [' ', C.mute],
              [item.skill.id.padEnd(30), here ? C.ink : C.text, here],
              [(query ? `${item.pack.title}${item.skill.group ? ` · ${item.skill.group}` : ''}` : (item.skill.group || '')).padEnd(query ? 0 : 24), C.mute],
              [have ? (going ? '  will remove' : chosen ? '  will update' : '  installed') : '', going ? C.warn : C.ok],
            ]));
          }
        }
        if (rows.length === 0) lines.push(screen.rail([['Nothing matches that filter.', C.warn]]));
        const hidden = [view.start ? `↑ ${view.start} more` : '', view.end < rows.length ? `↓ ${rows.length - view.end} more` : ''].filter(Boolean).join('  ');
        lines.push(screen.rail([[hidden, C.mute]]));
        const chosenCount = state.selected.size;
        const chosenPacks = packCatalog.packs.filter((pack) => pack.skills.some((skill) => state.selected.has(skill.id))).length;
        const about = focus ? (focus.type === 'pack' ? focus.pack.blurb : focus.skill.description) : '';
        const wrapped = wrapWords(about || '', screen.width - 4);
        screen.footer(lines, [
          [[wrapped[0] || '', C.text]],
          [[wrapped[1] || '', C.mute]],
          [],
          [
            [plural(chosenCount), chosenCount ? C.primary : C.mute, true],
            [` selected from ${plural(chosenPacks, 'pack')}`, C.mute],
            [state.drop.size ? ` · ${state.drop.size} to remove` : '', C.warn],
            [state.notice ? `   ${state.notice}` : '', C.warn],
          ],
          [[searching ? 'type to filter · enter keep · esc clear' : '↑↓ move · space pick · → open · p read · / filter · a all · 1-0 packs', C.mute]],
        ], [['enter', C.primary, true], [' next · esc cancel', C.mute]]);
        screen.paint(lines);
      };
      renderer.paint = paint;
      paint();
      const key = await input.next();
      state.notice = '';
      if (key.name === 'input-error') throw key.error;
      if (key.name === 'ctrl-c') return 'abort';
      if (key.name === 'eof') return 'cancel';
      if (searching) {
        if (key.name === 'escape') { query = ''; searching = false; cursor = 0; continue; }
        if (key.name === 'return') { searching = false; continue; }
        if (key.name === 'backspace') { query = query.slice(0, -1); cursor = 0; continue; }
        if (key.name === 'down' || key.name === 'up') {
          move = key.name === 'down' ? 1 : -1;
          cursor = (cursor + (key.name === 'down' ? 1 : rows.length - 1)) % Math.max(1, rows.length);
          continue;
        }
        if (key.name === 'space' && focus) {
          if (focus.type === 'skill') toggleSkill(focus.skill.id);
          if (state.pendingDrop) await chooseDrop();
          continue;
        }
        if (isSearchChar(key)) { query += key.ch || key.name; cursor = 0; }
        continue;
      }
      if (key.name === 'escape') {
        if (query) { query = ''; cursor = 0; continue; }
        return 'cancel';
      }
      if (key.name === 'up') { move = -1; cursor = (cursor + rows.length - 1) % Math.max(1, rows.length); }
      else if (key.name === 'down') { move = 1; cursor = (cursor + 1) % Math.max(1, rows.length); }
      else if (key.name === 'right' && focus?.type === 'pack') state.expanded.add(focus.pack.id);
      else if (key.name === 'left' && focus) {
        const id = focus.pack.id;
        if (state.expanded.has(id)) {
          state.expanded.delete(id);
          if (focus.type === 'skill') cursor = buildPackRows(packs, state.expanded, query).findIndex((row) => row.type === 'pack' && row.pack.id === id);
        }
      } else if (key.name === 'space' && focus) {
        if (focus.type === 'pack') togglePack(focus.pack);
        else toggleSkill(focus.skill.id);
        if (state.pendingDrop) await chooseDrop();
      } else if (/^[0-9]$/.test(key.name) && !query) {
        const pack = packs[(Number(key.name) + 9) % 10];
        if (pack) togglePack(pack);
      } else if (key.name === 's') {
        switchScope();
        state.notice = `Now in ${scopeName()}: u and x act on what is installed here.`;
      } else if (key.name === 'u' && installed.length) {
        for (const id of updatable) { state.drop.delete(id); state.selected.add(id); }
        state.notice = `${updatable.length} installed skill${updatable.length === 1 ? '' : 's'} will update. Enter to review.`;
      } else if (key.name === 'x' && installed.length) {
        for (const id of installed) { state.selected.delete(id); state.drop.add(id); }
        state.notice = `${installed.length} installed skill${installed.length === 1 ? '' : 's'} will be removed. Enter to review.`;
      } else if (key.name === 'a') {
        const all = packs.filter((pack) => pack.available && !pack.limit).flatMap((pack) => pack.skills);
        if (all.every((skill) => state.selected.has(skill.id))) state.selected.clear();
        else all.forEach((skill) => state.selected.add(skill.id));
      } else if (key.name === '/' || key.ch === '/') {
        searching = true;
        query = '';
        cursor = 0;
      } else if (key.name === 'p') {
        if (focus?.type !== 'skill') state.notice = 'Open a pack and highlight a skill, then p shows its full text.';
        else {
          const outcome = await showPreview(focus.skill);
          if (outcome) return outcome;
        }
      } else if (key.name === 'return') {
        if (state.selected.size === 0 && state.drop.size === 0) state.notice = 'Select at least one skill.';
        else return 'next';
      }
    }
  }

  /** The full SKILL.md of one skill: the bundled file, or the pack's pinned source (fetched once, then cached). */
  function skillText(skill) {
    if (skill.kind !== 'external') return fs.readFileSync(path.join(packageRoot, skill.id, 'SKILL.md'), 'utf8');
    previewFetcher ||= createSourceFetcher({ env });
    const dir = findSkillDirs(previewFetcher.fetch(skill.source).root).get(skill.id);
    if (!dir) throw new Error(`the source has no skill named ${skill.id}`);
    return fs.readFileSync(path.join(dir, 'SKILL.md'), 'utf8');
  }

  async function showPreview(skill) {
    let offset = 0;
    let text = null;
    while (true) {
      const room = Math.max(3, screen.height - 7);
      const frame = text === null ? { lines: ['Loading the text…'], top: 0, total: 0 } : previewFrame(text, screen.width - 4, room, offset);
      offset = frame.top;
      const paint = () => {
        const lines = screen.header(0);
        lines.push(screen.rail([
          [skill.id, C.ink, true],
          ['  SKILL.md', C.mute],
          [frame.total ? `   lines ${frame.top + 1}-${frame.top + frame.lines.length} of ${frame.total}` : '', C.mute],
        ]));
        for (const line of frame.lines) lines.push(screen.rail([[line, C.text]]));
        screen.footer(lines, [], [['↑↓ scroll · PgUp PgDn page · ', C.mute], ['esc close', C.primary, true]]);
        screen.paint(lines);
      };
      renderer.paint = paint;
      paint();
      if (text === null) {
        try {
          text = skillText(skill);
        } catch (err) {
          text = `Could not load the text of ${skill.id}: ${String(err.message || err).split('\n')[0]}\n\nA pack skill needs the network the first time. Close with esc and try again.`;
        }
        continue;
      }
      const key = await input.next();
      if (key.name === 'input-error') throw key.error;
      if (key.name === 'ctrl-c') return 'abort';
      if (key.name === 'eof') return 'cancel';
      if (['escape', 'p', 'q', 'return', 'left'].includes(key.name)) return '';
      if (key.name === 'up') offset -= 1;
      else if (key.name === 'down') offset += 1;
      else if (key.name === 'pageup') offset -= room;
      else if (key.name === 'pagedown' || key.name === 'space') offset += room;
      else if (key.name === 'home') offset = 0;
      else if (key.name === 'end') offset = frame.total;
      offset = Math.max(0, offset);
    }
  }

  function togglePack(pack) {
    if (!pack.available) {
      state.notice = pack.note;
      return;
    }
    if (pack.limit) {
      state.notice = `${pack.title} holds ${pack.limit.max} skills at a time: open it with the right arrow and pick up to ${pack.limit.max}.`;
      return;
    }
    const allOn = pack.skills.every((skill) => state.selected.has(skill.id));
    for (const skill of pack.skills) {
      if (allOn) state.selected.delete(skill.id);
      else state.selected.add(skill.id);
    }
  }

  function toggleSkill(id) {
    if (state.selected.has(id)) {
      state.selected.delete(id);
      return;
    }
    // An installed skill is ticked without being picked. Space unticks it: it is removed on confirm.
    // Space again picks it, and the install updates it.
    if (installedNow().has(id) && !state.drop.has(id)) {
      state.drop.add(id);
      return;
    }
    const pack = packOf(id);
    if (pack?.limit) {
      const held = slotsOf(pack);
      if (!held.has(id) && held.size >= pack.limit.max) {
        state.pendingDrop = { pack, id };
        return;
      }
    }
    state.drop.delete(id);
    state.selected.add(id);
  }

  /** The limit is full: show what the pack holds and let the person drop one to make room. */
  async function chooseDrop() {
    const { pack, id } = state.pendingDrop;
    state.pendingDrop = null;
    const held = [...slotsOf(pack)];
    const installed = installedNow();
    let cursor = 0;
    while (true) {
      const paint = () => {
        const lines = screen.header(0);
        lines.push(screen.rail([[`${pack.title} holds ${pack.limit.max} skills at a time.`, C.warn, true]]));
        lines.push(screen.rail([[`To add ${id}, drop one:`, C.text]]));
        lines.push(screen.rail());
        held.forEach((heldId, index) => {
          const here = index === cursor;
          lines.push(screen.item(here, [
            [heldId.padEnd(30), here ? C.ink : C.text, here],
            [installed.has(heldId) ? 'installed' : 'picked in this run', C.mute],
          ]));
        });
        screen.footer(lines, [[['↑↓ move · enter drop this one and add the new pick', C.mute]]], [['esc keep all three', C.primary, true]]);
        screen.paint(lines);
      };
      renderer.paint = paint;
      paint();
      const key = await input.next();
      if (key.name === 'input-error') throw key.error;
      if (key.name === 'ctrl-c' || key.name === 'eof' || key.name === 'escape') return;
      if (key.name === 'up') cursor = (cursor + held.length - 1) % held.length;
      else if (key.name === 'down') cursor = (cursor + 1) % held.length;
      else if (key.name === 'return') {
        const out = held[cursor];
        if (state.selected.has(out)) state.selected.delete(out);
        else state.drop.add(out);
        state.selected.add(id);
        return;
      }
    }
  }

  // ---- step 2: where -----------------------------------------------------------------------
  async function stepWhere() {
    let cursor = 0;
    let query = '';
    let searching = false;
    while (true) {
      const rows = hostRowsFor(groups, homeDir, query);
      cursor = rows.length ? Math.min(cursor, rows.length - 1) : 0;
      const universalNames = describeRoots(groups).get(UNIVERSAL_PROJECT_DESTINATION) || '';
      const paint = () => {
        const lines = screen.header(1, [doneWhat()]);
        const scopeDot = (scope) => [state.scope === scope ? `● ${scopeName(scope)}` : `○ ${scopeName(scope)}`, state.scope === scope ? C.primary : C.mute, state.scope === scope];
        lines.push(screen.rail([['Scope   ', C.mute], scopeDot('project'), ['   ', C.mute], scopeDot('global'), ['   ', C.mute], [scopeRoot(), C.mute]]));
        lines.push(screen.rail(searching || query
          ? [['Search  ', C.mute], [`${query}${searching ? '▏' : ''}`, C.ink]]
          : [['Everything lands in .agents/skills; a host you pick gets it too.', C.mute]]));
        lines.push(screen.heading('Agent Hosts'));
        const footer = 7;
        const room = Math.max(3, screen.height - lines.length - footer);
        const view = windowRows(rows.length, cursor, room);
        for (let index = view.start; index < view.end; index += 1) {
          const item = rows[index];
          const here = index === cursor;
          const covered = item.universal;
          const on = covered || state.roots.has(item.root);
          lines.push(screen.item(here, [
            [on ? '●' : '○', covered ? C.mute : on ? C.primary : C.mute],
            [' ', C.mute],
            [item.host.displayName.padEnd(18), here ? C.ink : C.text, here],
            [item.root.padEnd(22), C.mute],
            [covered ? 'reads .agents/skills' : on ? (state.method === 'link' ? 'linked' : 'copy') : '', C.mute],
            [item.found ? '  found here' : '', C.ok],
          ]));
        }
        const hidden = [view.start ? `↑ ${view.start} more` : '', view.end < rows.length ? `↓ ${rows.length - view.end} more` : ''].filter(Boolean).join('  ');
        lines.push(screen.rail([[hidden, C.mute]]));
        const hostCount = state.roots.size;
        screen.footer(lines, [
          [['.agents/skills', C.ink, true], [`  always on, read by ${universalNames}`, C.mute]],
          [
            ['Method  ', C.mute],
            [state.method === 'link' ? 'Link (recommended)' : 'Copy', C.primary, true],
            [hostCount ? (state.method === 'link' ? `  one copy, linked into ${plural(hostCount, 'host folder')}` : `  a full copy in ${plural(hostCount, 'host folder')}`) : '  only matters once a host folder is chosen', C.mute],
          ],
          [],
          [[searching ? 'type to search · enter keep · esc clear' : '↑↓ move · space pick · s scope · m method · / search all hosts', C.mute]],
        ], [['enter', C.primary, true], [' next · b back · esc cancel', C.mute]]);
        screen.paint(lines);
      };
      renderer.paint = paint;
      paint();
      const key = await input.next();
      if (key.name === 'input-error') throw key.error;
      if (key.name === 'ctrl-c') return 'abort';
      if (key.name === 'eof') return 'cancel';
      if (searching) {
        if (key.name === 'escape') { query = ''; searching = false; cursor = 0; continue; }
        if (key.name === 'return') { searching = false; continue; }
        if (key.name === 'backspace') { query = query.slice(0, -1); cursor = 0; continue; }
        if (key.name === 'down') { cursor = (cursor + 1) % Math.max(1, rows.length); continue; }
        if (key.name === 'up') { cursor = (cursor + rows.length - 1) % Math.max(1, rows.length); continue; }
        if (key.name === 'space' && rows[cursor] && !rows[cursor].universal) { flipRoot(rows[cursor].root); continue; }
        if (isSearchChar(key)) { query += key.ch || key.name; cursor = 0; }
        continue;
      }
      if (key.name === 'escape') {
        if (query) { query = ''; cursor = 0; continue; }
        return 'cancel';
      }
      if (key.name === 'up') cursor = (cursor + rows.length - 1) % Math.max(1, rows.length);
      else if (key.name === 'down') cursor = (cursor + 1) % Math.max(1, rows.length);
      else if (key.name === 'space' && rows[cursor] && !rows[cursor].universal) flipRoot(rows[cursor].root);
      else if (key.name === 's') {
        switchScope();
        cursor = 0;
      } else if (key.name === 'm') state.method = state.method === 'link' ? 'copy' : 'link';
      else if (key.name === '/' || key.ch === '/') { searching = true; query = ''; cursor = 0; }
      else if (key.name === 'b' || key.name === 'left') return 'back';
      else if (key.name === 'return') return 'next';
    }
  }

  function flipRoot(root) {
    if (state.roots.has(root)) state.roots.delete(root);
    else state.roots.add(root);
  }

  // ---- step 3: review ----------------------------------------------------------------------
  function planBundled(skills) {
    const bundled = skills.filter((skill) => skill.kind === 'bundled');
    if (bundled.length === 0) return { pending: 0, error: '' };
    try {
      const run = runInstall({
        catalog, skills: bundled, scope: state.scope, projectRoot, homeDir, customStateDir, packageRoot, env,
        dryRun: true, roots: [...state.roots], method: state.roots.size ? state.method : undefined,
        fetcher: null, version,
      });
      const pending = run.bundled.filter((result) => result.plan.requiresApproval).length;
      return { pending, error: '' };
    } catch (err) {
      return { pending: 0, error: String(err.message || err).split('\n')[0] };
    }
  }

  async function stepReview() {
    const skills = selectedSkills();
    const plan = planBundled(skills);
    const sources = [...new Set(skills.filter((skill) => skill.kind === 'external').map((skill) => skill.source.repo || skill.source.path || skill.source.env))];
    const names = describeRoots(groups);
    while (true) {
      const needsChoice = plan.pending > 0 && !state.resolution;
      const paint = () => {
        const lines = screen.header(2, skills.length ? [doneWhat(), doneWhere()] : [doneWhat()]);
        const titleWidth = Math.max(16, ...packCatalog.packs.map((pack) => pack.title.length + 2));
        const fresh = skills.filter((skill) => !installedNow().has(skill.id));
        const updates = skills.filter((skill) => installedNow().has(skill.id));
        if (fresh.length || (!updates.length && !state.drop.size)) lines.push(screen.rail([[`Install ${plural(fresh.length)}`, C.ink, true]]));
        for (const pack of packCatalog.packs) {
          const inPack = fresh.filter((skill) => skill.pack === pack.id).length;
          if (inPack) lines.push(screen.rail([['  ', C.mute], [pack.title.padEnd(titleWidth), C.text], [`${inPack}`, C.primary, true], [` of ${pack.skills.length}`, C.mute]]));
        }
        if (updates.length) {
          lines.push(screen.rail([[`Update ${plural(updates.length)}`, C.ink, true], ['  already installed', C.mute]]));
          lines.push(screen.rail([['  ', C.mute], [updates.map((skill) => skill.id).join(', '), C.text]]));
        }
        if (state.drop.size) {
          lines.push(screen.rail([[`Remove ${plural(state.drop.size)}`, C.warn, true], ['  an edited skill gets a private backup first', C.mute]]));
          lines.push(screen.rail([['  ', C.mute], [[...state.drop].join(', '), C.text]]));
        }
        lines.push(screen.rail());
        lines.push(screen.rail([[state.scope === 'global' ? 'Global  ' : 'Project ', C.primary, true], [scopeRoot(), C.mute]]));
        if (skills.length) lines.push(screen.rail([['  ', C.mute], ['.agents/skills'.padEnd(22), C.ink], ['copy'.padEnd(8), C.mute], [names.get(UNIVERSAL_PROJECT_DESTINATION) || '', C.mute]]));
        for (const root of skills.length ? state.roots : []) {
          lines.push(screen.rail([['  ', C.mute], [root.padEnd(22), C.ink], [(state.method === 'link' ? 'linked' : 'copy').padEnd(8), C.mute], [names.get(root) || '', C.mute]]));
        }
        if (sources.length) {
          lines.push(screen.rail());
          lines.push(screen.rail([['Downloads  ', C.info, true], [sources.join(', '), C.mute]]));
        }
        if (state.scope === 'global') {
          lines.push(screen.rail());
          lines.push(screen.rail([['Global Installation writes skills for every project of this user.', C.warn, true]]));
        }
        if (plan.error) {
          lines.push(screen.rail());
          lines.push(screen.rail([[`Cannot install: ${plan.error}`, C.err, true]]));
        } else if (needsChoice) {
          lines.push(screen.rail());
          lines.push(screen.rail([[`${plan.pending} skill${plan.pending === 1 ? '' : 's'} already exist with different content.`, C.warn, true]]));
          lines.push(screen.rail([['r replace after a private backup · s skip them · e export the old copies', C.mute]]));
        }
        const ready = !plan.error && !needsChoice;
        const verb = skills.length ? 'install' : 'remove';
        screen.footer(lines, [], ready
          ? [[state.scope === 'global' ? `y ${verb}` : `enter or y ${verb}`, C.primary, true], [' · b back · esc cancel', C.mute]]
          : [['b back · esc cancel', C.mute]]);
        screen.paint(lines);
      };
      renderer.paint = paint;
      paint();
      const key = await input.next();
      if (key.name === 'input-error') throw key.error;
      if (key.name === 'ctrl-c') return 'abort';
      if (key.name === 'eof' || key.name === 'escape') return 'cancel';
      if (key.name === 'b' || key.name === 'left') return 'back';
      if (needsChoice && ['r', 's', 'e'].includes(key.name)) {
        state.resolution = { r: 'replace', s: 'skip', e: 'export' }[key.name];
        continue;
      }
      if (plan.error || needsChoice) continue;
      if (key.name === 'y' || (key.name === 'return' && state.scope !== 'global')) return 'install';
    }
  }

  // ---- run ---------------------------------------------------------------------------------
  try {
    renderer.start();
    const flow = ['what', 'where', 'review'];
    let at = 0;
    while (true) {
      const outcome = await [stepWhat, stepWhere, stepReview][at]();
      if (outcome === 'abort') {
        renderer.cleanup();
        renderer.line('Cancelled. Nothing was written.');
        return 130;
      }
      if (outcome === 'cancel') {
        renderer.cleanup();
        renderer.line('Cancelled. Nothing was written.');
        return 0;
      }
      const skip = state.selected.size === 0 ? 2 : 1;
      if (outcome === 'next') at = Math.min(flow.length - 1, at + skip);
      else if (outcome === 'back') at = Math.max(0, at - skip);
      else if (outcome === 'install') break;
    }
    renderer.cleanup();
    return await execute();
  } finally {
    previewFetcher?.close();
    input.close();
    renderer.cleanup();
  }

  async function execute() {
    const styler = createStyler(io.stdout, env, options);
    const s = styler.style;
    const skills = selectedSkills();
    const adopt = state.resolution
      ? { adoptChanged: state.resolution, adoptLegacy: state.resolution, adoptUnverified: state.resolution, adoptMalformed: state.resolution }
      : {};
    const started = Date.now();
    renderer.line('');
    renderer.line(`${s(renderer.ascii ? 'SIGMA SKILLS' : 'Σ SIGMA SKILLS', C.primary, true)}  ${s(skills.length ? `installing ${skills.length} skill${skills.length === 1 ? '' : 's'}…` : 'removing…', C.mute)}`);
    const fetcher = createSourceFetcher({ env });
    let done = 0;
    const external = skills.filter((skill) => skill.kind === 'external').length;
    let run = { entries: [] };
    let dropped = [];
    let stuck = [];
    try {
      const sources = skills.filter((skill) => skill.kind === 'external').map((skill) => skill.source);
      if (sources.length > 0) {
        renderer.line(`  ${s('·', C.mute)} ${s(`fetching ${new Set(sources.map((source) => JSON.stringify(source))).size} source${sources.length === 1 ? '' : 's'}…`, C.mute)}`);
        await fetcher.warm(sources);
      }
      if (state.drop.size > 0) {
        const packs = uninstallPackSkills({ ...stateParams(), skillIds: [...state.drop] }).results;
        dropped = packs.filter((entry) => entry.status === 'removed').map((entry) => entry.id);
        stuck = packs.filter((entry) => entry.status !== 'removed' && entry.status !== 'not-installed').map((entry) => entry.id);
        // What the pack state does not know is a Sigma skill: its own uninstall keeps an edited copy as a private backup.
        const sigmaIds = packs.filter((entry) => entry.status === 'not-installed').map((entry) => entry.id);
        if (sigmaIds.length > 0) {
          const result = executeUninstall({
            catalog, projectRoot, homeDir, scope: state.scope, customStateDir, packageRoot, env, skillIds: sigmaIds, yes: true, clean: 'remove', changed: 'backup',
          });
          const gone = result.skills.filter((skill) => skill.outcome === 'removed').map((skill) => skill.id);
          dropped.push(...gone);
          stuck.push(...sigmaIds.filter((id) => !gone.includes(id)));
        }
        if (dropped.length > 0) renderer.line(`  ${s(renderer.ascii ? 'v' : '✓', C.ok, true)} removed ${dropped.join(', ')}`);
        if (stuck.length > 0) renderer.line(`  ${s('!', C.warn, true)} not removed: ${stuck.join(', ')}`);
      }
      if (skills.length > 0) run = runInstall({
        catalog, skills, scope: state.scope, projectRoot, homeDir, customStateDir, packageRoot, env,
        roots: [...state.roots], method: state.roots.size ? state.method : undefined, adopt, fetcher, version,
        packTitles: new Map(packCatalog.packs.map((pack) => [pack.id, pack.title])),
        onProgress: (event) => {
          if (event.phase === 'bundled') renderer.line(`  ${s('·', C.mute)} ${s(`writing ${event.count} Sigma skill${event.count === 1 ? '' : 's'}`, C.mute)}`);
          if (event.phase === 'done') {
            done += 1;
            const bad = ['failed', 'edited', 'conflict'].includes(event.result.status);
            renderer.line(`  ${bad ? s('!', C.warn, true) : s(renderer.ascii ? 'v' : '✓', C.ok, true)} ${event.id} ${s(`[${done}/${external}]`, C.mute)}`);
          }
        },
      });
    } catch (err) {
      renderer.line(`${s('✗', C.err, true)} ${s(String(err.message || err), C.err)}`);
      return 1;
    } finally {
      fetcher.close();
    }
    if (skills.length === 0) return stuck.length > 0 ? 1 : 0;
    const names = describeRoots(groups);
    const lines = formatSummary({
      styler,
      scope: state.scope,
      base: state.scope === 'global' ? homeDir : projectRoot,
      entries: run.entries,
      hostNames: names,
      roots: [{ root: UNIVERSAL_PROJECT_DESTINATION, method: 'copy' }, ...[...state.roots].map((root) => ({ root, method: state.method }))],
      version,
      seconds: (Date.now() - started) / 1000,
    });
    for (const line of lines) renderer.line(line);
    return stuck.length > 0 || run.entries.some((entry) => entry.status === 'failed') ? 1 : 0;
  }
}
