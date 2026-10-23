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
import { createSourceFetcher } from './pack-source.js';
import { packStatus, uninstallPackSkills } from './pack-install.js';
import { runInstall } from './install-run.js';
import { formatSummary } from './report.js';
import { isSearchChar } from './destination-items.js';

/**
 * The full-screen installer: what to install (groups and presets), where (Agent Hosts), a
 * review, then live progress and a clean summary. It draws with the DESIGN.md palette.
 * Plain terminals, CI and pipes never reach it: runWizard returns null and the caller falls
 * back to the line-by-line installer.
 */

const RESET = '\x1b[0m';
const STEPS = ['What', 'Where', 'Review'];

/** Which rows scroll into view. Pure, so tests can check it. */
export function windowRows(total, cursor, limit) {
  if (total <= limit) return { start: 0, end: total };
  let start = Math.max(0, cursor - Math.floor(limit / 2));
  if (start + limit > total) start = total - limit;
  return { start, end: start + limit };
}

/** Build the rows of the "what" screen: one row per pack, skill rows under an open pack. */
export function buildPackRows(packs, expanded, query) {
  const needle = String(query || '').trim().toLowerCase();
  const rows = [];
  if (needle) {
    for (const pack of packs) {
      for (const skill of pack.skills) {
        if (skill.id.includes(needle) || (skill.description || '').toLowerCase().includes(needle) || (skill.group || '').toLowerCase().includes(needle) || pack.title.toLowerCase().includes(needle)) {
          rows.push({ type: 'skill', pack, skill });
        }
      }
    }
    return rows;
  }
  for (const pack of packs) {
    rows.push({ type: 'pack', pack });
    if (expanded.has(pack.id)) for (const skill of pack.skills) rows.push({ type: 'skill', pack, skill });
  }
  return rows;
}

function checkbox(state) {
  return state === 'all' ? '[x]' : state === 'some' ? '[-]' : '[ ]';
}

function packState(pack, selected) {
  const count = pack.skills.filter((skill) => selected.has(skill.id)).length;
  if (count === 0) return { state: 'none', count };
  return { state: count === pack.skills.length ? 'all' : 'some', count };
}

class Screen {
  constructor(renderer) {
    this.renderer = renderer;
  }

  get width() {
    return Math.max(20, this.renderer.width - 1);
  }

  get height() {
    return Math.max(8, this.renderer.height - 1);
  }

  /** One row from `[text, hex, bold]` parts, clipped to the width and padded with the canvas. */
  row(parts) {
    let used = 0;
    let out = '';
    for (const part of parts) {
      const [text, hex = C.text, bold = false] = typeof part === 'string' ? [part] : part;
      const room = this.width - used;
      if (room <= 0) break;
      const clipped = text.length > room ? `${text.slice(0, Math.max(0, room - 1))}…` : text;
      out += this.renderer.style(clipped, hex, bold);
      used += clipped.length;
    }
    return out + ' '.repeat(Math.max(0, this.width - used));
  }

  blank() {
    return this.row(['']);
  }

  rule() {
    return this.row([['─'.repeat(this.width), C.hairline]]);
  }

  header(step, version, scopeLabel) {
    const crumbs = STEPS.flatMap((name, index) => {
      const active = index === step;
      return [[`${index + 1} ${name}`, active ? C.primary : C.mute, active], ['   ', C.mute]];
    });
    return [
      this.row([[this.renderer.ascii ? 'SIGMA SKILLS' : 'Σ SIGMA SKILLS', C.primary, true], [`  v${version}`, C.mute], [`   ${scopeLabel}`, C.mute]]),
      this.row(crumbs),
      this.rule(),
    ];
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
  const screen = new Screen(renderer);
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

  const scopeLabel = () => (state.scope === 'global' ? 'Global Installation' : 'Project Installation');
  const packOf = (id) => packCatalog.packs.find((pack) => pack.skills.some((skill) => skill.id === id));
  const stateParams = () => ({ scope: state.scope, projectRoot, homeDir, customStateDir });
  const installedByScope = new Map();
  const installedNow = () => {
    if (!installedByScope.has(state.scope)) {
      try {
        installedByScope.set(state.scope, new Set(packStatus(stateParams()).map((row) => row.id)));
      } catch {
        installedByScope.set(state.scope, new Set());
      }
    }
    return installedByScope.get(state.scope);
  };
  /** The slots a limited pack holds now: what is installed (minus drops) and what is picked. */
  const slotsOf = (pack) => {
    const own = new Set(pack.skills.map((skill) => skill.id));
    const held = new Set([...installedNow()].filter((id) => own.has(id) && !state.drop.has(id)));
    for (const id of state.selected) if (own.has(id)) held.add(id);
    return held;
  };
  const selectedSkills = () => packCatalog.packs.flatMap((pack) => pack.skills).filter((skill) => state.selected.has(skill.id));

  // ---- step 1: what ------------------------------------------------------------------------
  async function stepWhat() {
    let cursor = 0;
    let query = '';
    let searching = false;
    while (true) {
      const rows = buildPackRows(packCatalog.packs, state.expanded, query);
      cursor = rows.length ? Math.min(cursor, rows.length - 1) : 0;
      const focus = rows[cursor];
      const paint = () => {
        const lines = screen.header(0, version, scopeLabel());
        const footer = 6;
        lines.push(screen.row([[searching || query ? `Filter: ${query}${searching ? '▏' : ''}` : 'Pick packs, or open one to pick single skills.', C.mute]]));
        const room = Math.max(3, screen.height - lines.length - footer);
        const view = windowRows(rows.length, cursor, room);
        for (let index = view.start; index < view.end; index += 1) {
          const item = rows[index];
          const here = index === cursor;
          const cursorMark = here ? [renderer.ascii ? '> ' : '› ', C.primary, true] : ['  ', C.mute];
          if (item.type === 'pack') {
            const { state: boxState, count } = packState(item.pack, state.selected);
            const slots = item.pack.limit ? slotsOf(item.pack).size : 0;
            const open = state.expanded.has(item.pack.id);
            const nameColor = !item.pack.available ? C.mute : here ? C.ink : C.text;
            lines.push(screen.row([
              cursorMark,
              [item.pack.available ? checkbox(boxState) : '[!]', boxState === 'none' ? C.mute : C.primary, true],
              ['  ', C.mute],
              [`${index < 10 && !query ? `${(index + 1) % 10} ` : '  '}`, C.mute],
              [item.pack.title.padEnd(14), nameColor, true],
              [(!item.pack.available ? 'n/a' : item.pack.limit ? `${slots}/${item.pack.limit.max}` : `${count}/${item.pack.skills.length}`).padEnd(8), item.pack.limit && slots >= item.pack.limit.max ? C.warn : C.mute],
              [item.pack.available ? item.pack.blurb : item.pack.note, item.pack.available ? C.mute : C.warn],
              [open ? '  ▾' : '', C.mute],
            ]));
          } else {
            const chosen = state.selected.has(item.skill.id);
            lines.push(screen.row([
              cursorMark,
              [query ? '' : '    ', C.mute],
              [chosen ? '[x]' : '[ ]', chosen ? C.primary : C.mute, chosen],
              ['  ', C.mute],
              [item.skill.id.padEnd(30), here ? C.ink : C.text, here],
              [(query ? `${item.pack.title}${item.skill.group ? ` · ${item.skill.group}` : ''}` : (item.skill.group || '')).padEnd(query ? 0 : 28), C.mute],
              [installedNow().has(item.skill.id) ? (state.drop.has(item.skill.id) ? '  will drop' : '  installed') : '', state.drop.has(item.skill.id) ? C.warn : C.ok],
            ]));
          }
        }
        if (rows.length === 0) lines.push(screen.row([['  Nothing matches that filter.', C.warn]]));
        while (lines.length < screen.height - footer) lines.push(screen.blank());
        lines.push(screen.rule());
        const chosenCount = state.selected.size;
        const chosenPacks = packCatalog.packs.filter((pack) => pack.skills.some((skill) => state.selected.has(skill.id))).length;
        lines.push(screen.row([
          [`${chosenCount} skill${chosenCount === 1 ? '' : 's'}`, chosenCount ? C.primary : C.mute, true],
          [` selected from ${chosenPacks} pack${chosenPacks === 1 ? '' : 's'}`, C.mute],
          [state.notice ? `   ${state.notice}` : '', C.warn],
        ]));
        const about = focus ? (focus.type === 'pack' ? focus.pack.blurb : focus.skill.description) : '';
        const wrapped = wrapWords(about || '', screen.width - 2);
        lines.push(screen.row([[wrapped[0] || '', C.text]]));
        lines.push(screen.row([[wrapped[1] || '', C.mute]]));
        lines.push(screen.row([[searching ? 'type to filter · enter keep · esc clear' : '↑↓ move · space select · →← open or close · 1-0 pick a pack · a all · / filter', C.mute]]));
        lines.push(screen.row([['enter next · esc cancel', C.mute]]));
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
      if (key.name === 'up') cursor = (cursor + rows.length - 1) % Math.max(1, rows.length);
      else if (key.name === 'down') cursor = (cursor + 1) % Math.max(1, rows.length);
      else if (key.name === 'right' && focus?.type === 'pack') state.expanded.add(focus.pack.id);
      else if (key.name === 'left' && focus) {
        const id = focus.pack.id;
        if (state.expanded.has(id)) {
          state.expanded.delete(id);
          if (focus.type === 'skill') cursor = buildPackRows(packCatalog.packs, state.expanded, query).findIndex((row) => row.type === 'pack' && row.pack.id === id);
        }
      } else if (key.name === 'space' && focus) {
        if (focus.type === 'pack') togglePack(focus.pack);
        else toggleSkill(focus.skill.id);
        if (state.pendingDrop) await chooseDrop();
      } else if (/^[0-9]$/.test(key.name) && !query) {
        const pack = packCatalog.packs[(Number(key.name) + 9) % 10];
        if (pack) togglePack(pack);
      } else if (key.name === 'a') {
        const all = packCatalog.packs.filter((pack) => pack.available && !pack.limit).flatMap((pack) => pack.skills);
        if (all.every((skill) => state.selected.has(skill.id))) state.selected.clear();
        else all.forEach((skill) => state.selected.add(skill.id));
      } else if (key.name === '/' || key.ch === '/') {
        searching = true;
        query = '';
        cursor = 0;
      } else if (key.name === 'return') {
        if (state.selected.size === 0) state.notice = 'Select at least one skill.';
        else return 'next';
      }
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
    const pack = packOf(id);
    if (pack?.limit) {
      const held = slotsOf(pack);
      if (!held.has(id) && held.size >= pack.limit.max) {
        state.pendingDrop = { pack, id };
        return;
      }
      state.drop.delete(id);
    }
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
        const lines = screen.header(0, version, scopeLabel());
        lines.push(screen.row([[`${pack.title} holds ${pack.limit.max} skills at a time.`, C.warn, true]]));
        lines.push(screen.row([[`To add ${id}, drop one:`, C.text]]));
        lines.push(screen.blank());
        held.forEach((heldId, index) => {
          const here = index === cursor;
          lines.push(screen.row([
            here ? [renderer.ascii ? '> ' : '› ', C.primary, true] : ['  ', C.mute],
            [heldId.padEnd(30), here ? C.ink : C.text, here],
            [installed.has(heldId) ? 'installed' : 'picked in this run', C.mute],
          ]));
        });
        while (lines.length < screen.height - 3) lines.push(screen.blank());
        lines.push(screen.rule());
        lines.push(screen.row([['↑↓ move · enter drop this one and add the new pick · esc keep all three', C.mute]]));
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
        const lines = screen.header(1, version, scopeLabel());
        const footer = 6;
        lines.push(screen.row([
          ['Scope  ', C.mute],
          [state.scope === 'project' ? '(•) Project' : '( ) Project', state.scope === 'project' ? C.primary : C.mute, state.scope === 'project'],
          ['   ', C.mute],
          [state.scope === 'global' ? '(•) Global' : '( ) Global', state.scope === 'global' ? C.primary : C.mute, state.scope === 'global'],
          [state.scope === 'project' ? `   ${projectRoot}` : `   ${homeDir}`, C.mute],
        ]));
        lines.push(screen.row([[searching || query ? `Search all hosts: ${query}${searching ? '▏' : ''}` : 'Agent Hosts. Everything lands in .agents/skills; a host with its own folder links to it.', C.mute]]));
        const room = Math.max(3, screen.height - lines.length - footer);
        const view = windowRows(rows.length, cursor, room);
        for (let index = view.start; index < view.end; index += 1) {
          const item = rows[index];
          const here = index === cursor;
          const covered = item.universal;
          const on = covered || state.roots.has(item.root);
          lines.push(screen.row([
            here ? [renderer.ascii ? '> ' : '› ', C.primary, true] : ['  ', C.mute],
            [on ? '[x]' : '[ ]', covered ? C.mute : on ? C.primary : C.mute, on && !covered],
            ['  ', C.mute],
            [item.host.displayName.padEnd(18), here ? C.ink : C.text, here],
            [item.root.padEnd(22), C.mute],
            [covered ? 'reads .agents/skills' : on ? (state.method === 'link' ? 'linked' : 'copy') : '', C.mute],
            [item.found ? '  found here' : '', C.ok],
          ]));
        }
        while (lines.length < screen.height - footer) lines.push(screen.blank());
        lines.push(screen.rule());
        lines.push(screen.row([
          ['.agents/skills', C.ink, true],
          [`  always on, read by ${universalNames}`, C.mute],
        ]));
        const hostCount = state.roots.size;
        lines.push(screen.row([
          ['Method  ', C.mute],
          [state.method === 'link' ? 'Link (recommended)' : 'Copy', C.primary, true],
          [hostCount ? (state.method === 'link' ? `  one copy, linked into ${hostCount} host folder${hostCount === 1 ? '' : 's'}` : `  a full copy in ${hostCount} host folder${hostCount === 1 ? '' : 's'}`) : '  only matters once a host folder is chosen', C.mute],
        ]));
        lines.push(screen.row([[searching ? 'type to search · enter keep · esc clear' : '↑↓ move · space toggle · s scope · m method · / search all hosts', C.mute]]));
        lines.push(screen.row([['enter next · b back · esc cancel', C.mute]]));
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
        state.scope = state.scope === 'project' ? 'global' : 'project';
        groups = groupsFor(state.scope);
        resetRoots();
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
        const lines = screen.header(2, version, scopeLabel());
        const count = skills.length;
        lines.push(screen.row([[`Install ${count} skill${count === 1 ? '' : 's'}`, C.ink, true]]));
        for (const pack of packCatalog.packs) {
          const inPack = skills.filter((skill) => skill.pack === pack.id).length;
          if (inPack) lines.push(screen.row([['  ', C.mute], [pack.title.padEnd(16), C.text], [`${inPack}`, C.primary, true], [` of ${pack.skills.length}`, C.mute]]));
        }
        if (state.drop.size) lines.push(screen.row([['  ', C.mute], ['Drop'.padEnd(16), C.warn, true], [[...state.drop].join(', '), C.mute]]));
        lines.push(screen.blank());
        lines.push(screen.row([[state.scope === 'global' ? 'Global  ' : 'Project ', C.primary, true], [state.scope === 'global' ? homeDir : projectRoot, C.mute]]));
        lines.push(screen.row([['  ', C.mute], ['.agents/skills'.padEnd(22), C.ink], ['copy'.padEnd(8), C.mute], [names.get(UNIVERSAL_PROJECT_DESTINATION) || '', C.mute]]));
        for (const root of state.roots) {
          lines.push(screen.row([['  ', C.mute], [root.padEnd(22), C.ink], [(state.method === 'link' ? 'linked' : 'copy').padEnd(8), C.mute], [names.get(root) || '', C.mute]]));
        }
        if (sources.length) {
          lines.push(screen.blank());
          lines.push(screen.row([['Downloads  ', C.info, true], [sources.join(', '), C.mute]]));
        }
        if (state.scope === 'global') {
          lines.push(screen.blank());
          lines.push(screen.row([['Global Installation writes skills for every project of this user.', C.warn, true]]));
        }
        if (plan.error) {
          lines.push(screen.blank());
          lines.push(screen.row([[`Cannot install: ${plan.error}`, C.err, true]]));
        } else if (needsChoice) {
          lines.push(screen.blank());
          lines.push(screen.row([[`${plan.pending} skill${plan.pending === 1 ? '' : 's'} already exist with different content.`, C.warn, true]]));
          lines.push(screen.row([['r replace after a private backup · s skip them · e export the old copies', C.mute]]));
        }
        while (lines.length < screen.height - 3) lines.push(screen.blank());
        lines.push(screen.rule());
        const ready = !plan.error && !needsChoice;
        lines.push(screen.row([[ready ? (state.scope === 'global' ? 'y install · b back · esc cancel' : 'enter or y install · b back · esc cancel') : 'b back · esc cancel', ready ? C.primary : C.mute, ready]]));
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
      if (outcome === 'next') at = Math.min(flow.length - 1, at + 1);
      else if (outcome === 'back') at = Math.max(0, at - 1);
      else if (outcome === 'install') break;
    }
    renderer.cleanup();
    return await execute();
  } finally {
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
    renderer.line(`${s(renderer.ascii ? 'SIGMA SKILLS' : 'Σ SIGMA SKILLS', C.primary, true)}  ${s(`installing ${skills.length} skill${skills.length === 1 ? '' : 's'}…`, C.mute)}`);
    const fetcher = createSourceFetcher({ env });
    let done = 0;
    const external = skills.filter((skill) => skill.kind === 'external').length;
    let run;
    let dropped = [];
    try {
      const sources = skills.filter((skill) => skill.kind === 'external').map((skill) => skill.source);
      if (sources.length > 0) {
        renderer.line(`  ${s('·', C.mute)} ${s(`fetching ${new Set(sources.map((source) => JSON.stringify(source))).size} source${sources.length === 1 ? '' : 's'}…`, C.mute)}`);
        await fetcher.prefetch(sources);
      }
      if (state.drop.size > 0) {
        dropped = uninstallPackSkills({ ...stateParams(), skillIds: [...state.drop] }).results.filter((entry) => entry.status === 'removed').map((entry) => entry.id);
        if (dropped.length > 0) renderer.line(`  ${s('·', C.mute)} ${s(`dropped ${dropped.join(', ')}`, C.mute)}`);
      }
      run = runInstall({
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
    return run.entries.some((entry) => entry.status === 'failed') ? 1 : 0;
  }
}
