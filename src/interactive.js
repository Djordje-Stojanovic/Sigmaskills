import path from 'node:path';
import readline from 'node:readline';
import { createInstallPlan, createProjectSkillClassifier, formatPlanHuman } from './plan.js';
import { createNeedsResolutionError, createUnownedConflictError, executeProjectInstall } from './transaction.js';
import { isDestinationOwned } from './state.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  defaultSelectedRoots,
  findDestinationConflicts,
  listGlobalDestinationGroups,
  listProjectDestinationGroups,
  loadHostRegistry,
  resolveGlobalSkillPath,
  resolveHomeDir,
  searchHosts,
} from './destinations.js';
import { recommendedLinkMethod } from './links.js';

export const EMBERFORGE_PALETTE = Object.freeze({
  base: '#1a1714',
  crust: '#0e0c0a',
  text: '#e0d8cc',
  gold: '#d4a564',
  orange: '#cc8844',
  green: '#8cb87c',
  teal: '#7cb8a8',
  red: '#d4645c',
});

export const EMBERFORGE_REVEAL_MS = 650;

const RESET = '\x1b[0m';
const CLEAR = '\x1b[2J\x1b[H';
const ENTER_ALT_SCREEN = '\x1b[?1049h';
const LEAVE_ALT_SCREEN = '\x1b[?1049l';
const HIDE_CURSOR = '\x1b[?25l';
const SHOW_CURSOR = '\x1b[?25h';

const ANSI16_FG = Object.freeze({
  '#1a1714': 30,
  '#0e0c0a': 30,
  '#e0d8cc': 37,
  '#d4a564': 33,
  '#cc8844': 33,
  '#8cb87c': 32,
  '#7cb8a8': 36,
  '#d4645c': 31,
});

function hexToRgb(hex) {
  return [1, 3, 5].map((index) => Number.parseInt(hex.slice(index, index + 2), 16));
}

function rgbTo256(red, green, blue) {
  const cube = (value) => Math.round((value / 255) * 5);
  return 16 + (36 * cube(red)) + (6 * cube(green)) + cube(blue);
}

function truecolorFg(hex, bold = false) {
  const [red, green, blue] = hexToRgb(hex);
  return `\x1b[${bold ? '1;' : ''}38;2;${red};${green};${blue}m`;
}

function truecolorBg(hex) {
  const [red, green, blue] = hexToRgb(hex);
  return `\x1b[48;2;${red};${green};${blue}m`;
}

function detectColorMode(stdout, env, options) {
  if (
    options.noColor ||
    options.json ||
    env.NO_COLOR !== undefined ||
    env.TERM === 'dumb' ||
    !stdout.isTTY
  ) {
    return 'plain';
  }
  let depth = 24;
  if (typeof stdout.getColorDepth === 'function') {
    depth = stdout.getColorDepth(env);
  }
  if (depth >= 24) return 'truecolor';
  if (depth >= 8) return 'ansi256';
  if (depth >= 4) return 'ansi16';
  return 'plain';
}

function prefersReducedMotion(env = {}) {
  const reduced = String(env.REDUCED_MOTION || '').toLowerCase();
  const prefers = String(env.PREFERS_REDUCED_MOTION || '').toLowerCase();
  return reduced === '1' || reduced === 'true' || prefers === 'reduce' || prefers === '1' || prefers === 'true';
}

function wrapWords(value, width) {
  const max = Math.max(1, width);
  if (!value) return [''];
  const words = String(value).split(/\s+/);
  const lines = [];
  let line = '';
  const flush = () => {
    if (line) {
      lines.push(line);
      line = '';
    }
  };
  for (const word of words) {
    if (word.length > max) {
      flush();
      for (let index = 0; index < word.length; index += max) {
        const chunk = word.slice(index, index + max);
        if (index + max < word.length) lines.push(chunk);
        else line = chunk;
      }
      continue;
    }
    if (!line) {
      line = word;
    } else if (line.length + word.length + 1 <= max) {
      line += ` ${word}`;
    } else {
      lines.push(line);
      line = word;
    }
  }
  flush();
  return lines.length ? lines : [''];
}

class TerminalRenderer {
  constructor(io, options) {
    this.stdout = io.stdout;
    this.stdin = io.stdin;
    this.env = io.env || process.env;
    this.forcedNarrow = Boolean(options.narrow);
    this.colorMode = detectColorMode(this.stdout, this.env, options);
    this.noColor = this.colorMode === 'plain';
    this.ascii = typeof this.stdout.getColorDepth === 'function'
      && this.stdout.getColorDepth(this.env) < 4;
    this.static = Boolean(
      options.static ||
      options.json ||
      this.noColor ||
      this.env.CI ||
      prefersReducedMotion(this.env) ||
      !this.stdin.isTTY ||
      !this.stdout.isTTY,
    );
    this.dynamic = Boolean(this.stdout.isTTY && !this.static && !this.noColor);
    this.cursorHidden = false;
    this.paint = null;
    this.altScreen = false;
    this.cleaned = false;
    this.onResize = () => {
      if (this.paint) this.paint();
    };
    if (typeof this.stdout.on === 'function') {
      this.stdout.on('resize', this.onResize);
    }
  }

  get width() {
    return this.forcedNarrow ? Math.min(this.stdout.columns || 80, 60) : (this.stdout.columns || 80);
  }

  get narrow() {
    return this.forcedNarrow || this.width < 76;
  }

  get block() {
    return this.ascii ? '#' : '█';
  }

  get brand() {
    return this.ascii ? 'SIGMA SKILLS' : 'Σ SIGMA SKILLS';
  }

  style(value, hex, bold = false) {
    if (this.noColor) return value;
    if (this.colorMode === 'truecolor') {
      return `${truecolorFg(hex, bold)}${value}${RESET}`;
    }
    if (this.colorMode === 'ansi256') {
      const [red, green, blue] = hexToRgb(hex);
      return `\x1b[${bold ? '1;' : ''}38;5;${rgbTo256(red, green, blue)}m${value}${RESET}`;
    }
    const code = ANSI16_FG[hex] || 37;
    return `\x1b[${bold ? '1;' : ''}${code}m${value}${RESET}`;
  }

  fill() {
    if (this.colorMode === 'truecolor') return truecolorBg(EMBERFORGE_PALETTE.base);
    if (this.colorMode === 'ansi256') {
      const [red, green, blue] = hexToRgb(EMBERFORGE_PALETTE.base);
      return `\x1b[48;5;${rgbTo256(red, green, blue)}m`;
    }
    if (this.colorMode === 'ansi16') return '\x1b[40m';
    return '';
  }

  start() {
    if (this.dynamic) {
      this.stdout.write(`${ENTER_ALT_SCREEN}${HIDE_CURSOR}`);
      this.cursorHidden = true;
      this.altScreen = true;
    }
  }

  cleanup() {
    this.paint = null;
    if (this.cleaned) return;
    this.cleaned = true;
    if (typeof this.stdout.removeListener === 'function') {
      this.stdout.removeListener('resize', this.onResize);
    }
    if (this.altScreen) {
      this.stdout.write(`${LEAVE_ALT_SCREEN}${RESET}${SHOW_CURSOR}`);
      this.altScreen = false;
      this.cursorHidden = false;
      return;
    }
    if (this.cursorHidden) {
      this.stdout.write(`${RESET}${SHOW_CURSOR}`);
      this.cursorHidden = false;
    }
  }

  screen(lines) {
    const content = lines.join('\n');
    if (this.dynamic) {
      this.stdout.write(`${CLEAR}${this.fill()}${content}${RESET}\n`);
    } else {
      this.stdout.write(`${content}\n`);
    }
  }

  line(value = '') {
    this.stdout.write(value.endsWith('\n') ? value : `${value}\n`);
  }
}

class KeyInput {
  constructor(stdin) {
    this.stdin = stdin;
    this.queue = [];
    this.waiters = [];
    this.ended = false;
    this.closed = false;
    this.previousRawMode = Boolean(stdin.isRaw);
    this.changedRawMode = false;

    readline.emitKeypressEvents(stdin);
    this.onKeypress = (_value, key = {}) => {
      const normalized = key.ctrl && key.name === 'c'
        ? { name: 'ctrl-c', ch: '', sequence: '', shift: false }
        : {
          name: key.name || key.sequence || 'unknown',
          ch: typeof _value === 'string' ? _value : '',
          sequence: key.sequence || '',
          shift: Boolean(key.shift),
        };
      this.push(normalized);
    };
    this.onEnd = () => {
      this.ended = true;
      this.push({ name: 'eof' });
    };
    this.onSigint = () => this.push({ name: 'ctrl-c' });

    stdin.on('keypress', this.onKeypress);
    stdin.once('end', this.onEnd);
    process.on('SIGINT', this.onSigint);

    if (stdin.isTTY && typeof stdin.setRawMode === 'function') {
      stdin.setRawMode(true);
      this.changedRawMode = true;
    }
    stdin.resume?.();
  }

  push(key) {
    const waiter = this.waiters.shift();
    if (waiter) {
      clearTimeout(waiter.timer);
      waiter.resolve(key);
    } else {
      this.queue.push(key);
    }
  }

  next(timeoutMs) {
    if (this.queue.length > 0) return Promise.resolve(this.queue.shift());
    if (this.ended) return Promise.resolve({ name: 'eof' });

    return new Promise((resolve) => {
      const waiter = { resolve, timer: null };
      if (timeoutMs !== undefined) {
        waiter.timer = setTimeout(() => {
          const index = this.waiters.indexOf(waiter);
          if (index !== -1) this.waiters.splice(index, 1);
          resolve(null);
        }, timeoutMs);
      }
      this.waiters.push(waiter);
    });
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    this.stdin.removeListener('keypress', this.onKeypress);
    this.stdin.removeListener('end', this.onEnd);
    process.removeListener('SIGINT', this.onSigint);
    for (const waiter of this.waiters.splice(0)) {
      clearTimeout(waiter.timer);
      waiter.resolve({ name: 'eof' });
    }
    if (this.changedRawMode) {
      try {
        this.stdin.setRawMode(this.previousRawMode);
      } catch {
        // The stream may already be closed. Cursor restoration still runs.
      }
    }
  }
}

function isHelpKey(key) {
  return Boolean(key && (key.ch === '?' || key.sequence === '?' || key.name === '?'));
}

function helpLines(renderer) {
  return [
    renderer.style(renderer.brand, EMBERFORGE_PALETTE.gold, true),
    'Keyboard',
    '',
    '↑/↓ move focus',
    'space toggle selection',
    'type to search Agent Hosts',
    'enter continue',
    'esc cancel',
    'Ctrl+C abort',
    'any key skips the opening reveal',
    '? close help',
  ];
}

async function readKeyedScreen(renderer, input, paint) {
  renderer.paint = paint;
  paint();
  const key = await input.next();
  if (isHelpKey(key)) {
    await showHelp(renderer, input);
    return { help: true, key };
  }
  return { help: false, key };
}

async function showHelp(renderer, input) {
  const paint = () => renderer.screen(helpLines(renderer));
  renderer.paint = paint;
  paint();
  await input.next();
}

function withHelp(hints) {
  return `${hints} · ? help`;
}

function revealLines(renderer, progress = 1) {
  const templates = renderer.narrow
    ? ['██████████', '      ███', '    ███', '  ███', '██████████']
    : ['██████████████████', '              ████', '           ████', '        ████', '     ████', '██████████████████'];
  const sigma = templates.map((row) => row.replaceAll('█', renderer.block));
  const visibleRows = Math.max(1, Math.ceil(sigma.length * progress));
  const firstVisible = sigma.length - visibleRows;
  const fire = [
    EMBERFORGE_PALETTE.red,
    EMBERFORGE_PALETTE.orange,
    EMBERFORGE_PALETTE.gold,
    EMBERFORGE_PALETTE.text,
  ];
  const lines = [''];

  for (let index = 0; index < sigma.length; index++) {
    if (index < firstVisible) {
      lines.push('');
      continue;
    }
    const colorIndex = Math.min(fire.length - 1, sigma.length - 1 - index);
    lines.push(`  ${renderer.style(sigma[index], fire[colorIndex], true)}`);
  }
  lines.push('');
  lines.push(`  ${renderer.style('SIGMA SKILLS', EMBERFORGE_PALETTE.gold, true)}`);
  lines.push(`  ${renderer.style('Project Installation', EMBERFORGE_PALETTE.orange)}`);
  return lines;
}

async function runReveal(renderer, input) {
  if (renderer.static) {
    renderer.screen(revealLines(renderer));
    return null;
  }

  const startedAt = Date.now();
  while (true) {
    const elapsed = Date.now() - startedAt;
    const progress = Math.min(1, elapsed / EMBERFORGE_REVEAL_MS);
    renderer.paint = () => renderer.screen(revealLines(renderer, progress));
    renderer.screen(revealLines(renderer, progress));
    if (progress >= 1) return null;

    const remaining = EMBERFORGE_REVEAL_MS - elapsed;
    const key = await input.next(Math.min(90, remaining));
    if (key) {
      renderer.screen(revealLines(renderer));
      return key.name;
    }
  }
}

function pickerLines(renderer, catalog, selected, cursor, error, scope) {
  const scopeLabel = scope === 'global' ? 'Global Installation' : 'Project Installation (default)';
  const lines = [
    renderer.style(renderer.brand, EMBERFORGE_PALETTE.gold, true),
    `${scopeLabel}${renderer.narrow ? ' · narrow' : ''}`,
    '',
    'Select skills from this Skill Pack:',
  ];

  catalog.skills.forEach((skill, index) => {
    const current = index === cursor ? '>' : ' ';
    const checked = selected.has(skill.id) ? 'x' : ' ';
    lines.push(`${current} [${checked}] ${skill.title} (${skill.id})`);
    const descriptionWidth = Math.max(20, renderer.width - 6);
    for (const descriptionLine of wrapWords(skill.description, descriptionWidth)) {
      lines.push(`      ${descriptionLine}`);
    }
  });

  lines.push('');
  lines.push(`Selected: ${selected.size}/${catalog.skills.length}`);
  if (error) lines.push(renderer.style(`Error: ${error}`, EMBERFORGE_PALETTE.red, true));
  lines.push(withHelp(`↑/↓ move · space toggle · a select all${scope === 'global' ? '' : ' · g Global Installation'} · enter continue · esc cancel`));
  return lines;
}

function globalWarningLines(renderer) {
  return [
    renderer.style('Global Installation warning', EMBERFORGE_PALETTE.red, true),
    '',
    'Global Installation writes skills for this operating-system user.',
    'Other projects can pick them up. Project Installation remains the safer default.',
    '',
    'Continue with Global Installation? [y/N]',
    'y continue · n/enter/esc cancel · ? help',
  ];
}

async function confirmGlobalWarning(renderer, input) {
  while (true) {
    const { help, key } = await readKeyedScreen(renderer, input, () => renderer.screen(globalWarningLines(renderer)));
    if (help) continue;
    if (key.name === 'y') return { confirmed: true, exitCode: 0 };
    if (key.name === 'ctrl-c') return { confirmed: false, exitCode: 130 };
    if (key.name === 'eof' || key.name === 'escape' || key.name === 'n' || key.name === 'return') {
      return { confirmed: false, exitCode: 0 };
    }
  }
}

async function selectSkills(renderer, input, catalog, initialScope = 'project') {
  const selected = new Set();
  let cursor = 0;
  let error = '';
  let scope = initialScope === 'global' ? 'global' : 'project';

  while (true) {
    const { help, key } = await readKeyedScreen(
      renderer,
      input,
      () => renderer.screen(pickerLines(renderer, catalog, selected, cursor, error, scope)),
    );
    if (help) continue;
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape' || key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up' || (key.name === 'tab' && key.shift)) {
      cursor = (cursor + catalog.skills.length - 1) % catalog.skills.length;
    }
    if (key.name === 'down' || (key.name === 'tab' && !key.shift)) {
      cursor = (cursor + 1) % catalog.skills.length;
    }
    if (key.name === 'space') {
      const skillId = catalog.skills[cursor].id;
      if (selected.has(skillId)) selected.delete(skillId);
      else selected.add(skillId);
      error = '';
    }
    if (key.name === 'a') {
      if (selected.size === catalog.skills.length) selected.clear();
      else catalog.skills.forEach((skill) => selected.add(skill.id));
      error = '';
    }
    if (key.name === 'g' && scope !== 'global') {
      const warning = await confirmGlobalWarning(renderer, input);
      if (!warning.confirmed) return { cancelled: true, exitCode: warning.exitCode };
      scope = 'global';
      error = '';
      continue;
    }
    if (key.name === 'return') {
      if (selected.size === 0) {
        error = 'Select at least one skill.';
      } else {
        return {
          cancelled: false,
          scope,
          skillIds: catalog.skills.filter((skill) => selected.has(skill.id)).map((skill) => skill.id),
        };
      }
    }
  }
}

function persistOutput(renderer, text) {
  renderer.cleanup();
  renderer.line(text);
}

function destinationWindowSize(renderer, itemCount) {
  if (!renderer.dynamic) return itemCount;
  const rows = Number(renderer.stdout.rows) || 24;
  const chrome = 10;
  return Math.min(itemCount, Math.max(3, rows - chrome));
}

function visibleDestinationItems(items, cursor, limit) {
  if (!items.length || items.length <= limit) {
    return { items, start: 0, total: items.length };
  }
  const half = Math.floor(limit / 2);
  let start = Math.max(0, cursor - half);
  if (start + limit > items.length) start = items.length - limit;
  return {
    items: items.slice(start, start + limit),
    start,
    total: items.length,
  };
}

function destinationRowTitle(item) {
  const detectedMark = item.detected || (item.hosts || []).some((host) => host.detected)
    ? ' [detected]'
    : '';
  if (item.kind === 'host') {
    return `${item.relativeRoot}  ${item.displayName} (${item.id})${detectedMark}`;
  }
  const hosts = item.hosts || [];
  const detectedCount = hosts.filter((host) => host.detected).length;
  if (item.universal) {
    const extra = detectedCount ? ` · ${detectedCount} detected` : '';
    return `${item.relativeRoot}  (universal default · ${hosts.length} hosts${extra})`;
  }
  if (hosts.length <= 2) {
    const names = hosts.map((host) => host.displayName).join(', ');
    const ids = hosts.map((host) => host.id).join(', ');
    return `${item.relativeRoot}  ${names} (${ids})${detectedMark}`;
  }
  return `${item.relativeRoot}  ${hosts[0].displayName} +${hosts.length - 1}${detectedMark}`;
}

function destinationPickerLines(renderer, items, selectedRoots, cursor, query, error, scope) {
  const scopeLabel = scope === 'global' ? 'Global Installation' : 'Project Installation';
  const view = visibleDestinationItems(items, cursor, destinationWindowSize(renderer, items.length));
  const focused = items[cursor];
  const lines = [
    renderer.style(renderer.brand, EMBERFORGE_PALETTE.gold, true),
    `${scopeLabel} · destinations${renderer.narrow ? ' · narrow' : ''}`,
    '',
    'Only .agents/skills is selected by default. Host-specific destinations stay unselected.',
  ];

  if (query) {
    lines.push(`Search: ${query}`);
  } else {
    lines.push('Type a host name to search. Arrow keys move. Space toggles.');
  }

  view.items.forEach((item, viewIndex) => {
    const index = view.start + viewIndex;
    const current = index === cursor ? '>' : ' ';
    const checked = selectedRoots.has(item.relativeRoot) ? 'x' : ' ';
    const marker = `${current} [${checked}] `;
    const titleLines = wrapWords(destinationRowTitle(item), Math.max(20, renderer.width - marker.length));
    titleLines.forEach((titleLine, titleIndex) => {
      lines.push(titleIndex === 0 ? `${marker}${titleLine}` : `      ${titleLine}`);
    });
  });

  if (view.total > view.items.length) {
    const from = view.start + 1;
    const to = view.start + view.items.length;
    lines.push(`Showing ${from}–${to} of ${view.total}`);
  }

  lines.push('');
  if (focused?.absoluteRoot) {
    for (const wrapped of wrapWords(`Path: ${focused.absoluteRoot}`, Math.max(20, renderer.width - 2))) {
      lines.push(wrapped);
    }
  }
  lines.push(`Selected destinations: ${selectedRoots.size}`);
  if (error) lines.push(renderer.style(`Error: ${error}`, EMBERFORGE_PALETTE.red, true));
  lines.push(withHelp('Type to search every Agent Host · space toggle · enter continue · esc cancel'));
  return lines;
}

function selectableGroups(groups) {
  return groups.filter((group) => group.selectable);
}

function pickerItems(groups, query) {
  if (query) {
    const matches = searchHosts(groups, query).filter((host) => host.relativeRoot);
    const byRoot = new Map();
    for (const host of matches) {
      const existing = byRoot.get(host.relativeRoot);
      if (!existing) {
        byRoot.set(host.relativeRoot, {
          kind: 'host',
          id: host.id,
          displayName: host.displayName,
          relativeRoot: host.relativeRoot,
          absoluteRoot: host.group?.absoluteRoot || '',
          detected: host.detected,
          universal: host.relativeRoot === UNIVERSAL_PROJECT_DESTINATION,
          hosts: [host],
        });
        continue;
      }
      existing.hosts.push(host);
      existing.detected = existing.detected || host.detected;
      existing.kind = 'group';
      existing.universal = existing.universal || host.relativeRoot === UNIVERSAL_PROJECT_DESTINATION;
    }
    return [...byRoot.values()];
  }
  return selectableGroups(groups).map((group) => ({
    kind: 'group',
    relativeRoot: group.relativeRoot,
    absoluteRoot: group.absoluteRoot,
    universal: group.universal,
    hosts: group.hosts,
  }));
}

function isSearchChar(key) {
  if (!key) return false;
  if (key.name === 'space' || key.name === 'return' || key.name === 'escape') return false;
  const ch = key.ch || '';
  if (ch.length === 1 && /[A-Za-z0-9._/-]/.test(ch)) return true;
  return Boolean(key.name && key.name.length === 1 && /[A-Za-z0-9._/-]/.test(key.name));
}

async function selectDestinations(renderer, input, groups, scope = 'project') {
  const selectedRoots = new Set(defaultSelectedRoots(groups));
  let query = '';
  let cursor = 0;
  let error = '';

  while (true) {
    const items = pickerItems(groups, query);
    if (items.length === 0) cursor = 0;
    else cursor = ((cursor % items.length) + items.length) % items.length;
    const { help, key } = await readKeyedScreen(
      renderer,
      input,
      () => renderer.screen(destinationPickerLines(renderer, items, selectedRoots, cursor, query, error, scope)),
    );
    if (help) continue;
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape') {
      if (query) {
        query = '';
        cursor = 0;
        error = '';
        continue;
      }
      return { cancelled: true, exitCode: 0 };
    }
    if (key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up' || (key.name === 'tab' && key.shift)) {
      if (items.length) cursor = (cursor + items.length - 1) % items.length;
    }
    if (key.name === 'down' || (key.name === 'tab' && !key.shift)) {
      if (items.length) cursor = (cursor + 1) % items.length;
    }
    if (key.name === 'backspace') {
      query = query.slice(0, -1);
      cursor = 0;
      error = '';
    }
    if (isSearchChar(key)) {
      query += key.ch || key.name;
      cursor = 0;
      error = '';
    }
    if (key.name === 'space') {
      const item = items[cursor];
      if (item?.relativeRoot) {
        if (selectedRoots.has(item.relativeRoot)) selectedRoots.delete(item.relativeRoot);
        else selectedRoots.add(item.relativeRoot);
        error = '';
      }
    }
    if (key.name === 'return') {
      if (selectedRoots.size === 0) {
        error = 'Select at least one destination.';
      } else {
        return {
          cancelled: false,
          selectedRoots: selectableGroups(groups)
            .map((group) => group.relativeRoot)
            .filter((root) => selectedRoots.has(root)),
        };
      }
    }
  }
}

function summaryLines(renderer, plans, scope = 'project') {
  const title = scope === 'global' ? 'Confirm Global Installation' : 'Confirm Project Installation';
  const lines = [
    renderer.style(title, EMBERFORGE_PALETTE.gold, true),
    '',
    'Resolved destinations:',
  ];
  for (const plan of plans) {
    lines.push(`${plan.title} (${plan.skill})`);
    for (const dest of plan.destinations || [{ destination: plan.destination }]) {
      const method = dest.method ? ` [${dest.method}]` : '';
      for (const wrapped of wrapWords(`${dest.destination}${method}`, Math.max(20, renderer.width - 2))) {
        lines.push(`  ${wrapped}`);
      }
      if (dest.dependsOn) {
        for (const wrapped of wrapWords(`depends on ${dest.dependsOn}`, Math.max(20, renderer.width - 4))) {
          lines.push(`    ${wrapped}`);
        }
      }
      if (scope === 'global') {
        const hostNames = (dest.hosts || []).map((host) => host.displayName).join(', ');
        if (hostNames) lines.push(`    Agent Hosts: ${hostNames}`);
        if (dest.method) lines.push(`    Method: ${dest.method}`);
        if (dest.overwrite) lines.push(`    Overwrite: ${dest.overwrite}`);
        if (dest.delete) lines.push(`    Delete: ${dest.delete}`);
        if (dest.backup) lines.push(`    Backup: ${dest.backup}`);
      }
    }
  }
  lines.push('');
  lines.push(`Install ${plans.length} selected skill${plans.length === 1 ? '' : 's'}? [y/N]`);
  lines.push(withHelp('y confirm · n/enter/esc cancel'));
  return lines;
}

function methodPickerLines(renderer, cursor) {
  const linkDetail = recommendedLinkMethod() === 'junction'
    ? 'Windows directory junctions to the canonical copy'
    : 'macOS/Linux symbolic links to the canonical copy';
  const options = [
    { title: 'Link (recommended)', detail: linkDetail },
    { title: 'Copy', detail: 'Independent managed copy at every destination' },
  ];
  const lines = [
    renderer.style(renderer.brand, EMBERFORGE_PALETTE.gold, true),
    `Project Installation · method${renderer.narrow ? ' · narrow' : ''}`,
    '',
    'Choose how host-specific destinations are written. The installer never changes method silently.',
  ];
  options.forEach((option, index) => {
    const current = index === cursor ? '>' : ' ';
    const checked = index === cursor ? 'x' : ' ';
    lines.push(`${current} [${checked}] ${option.title}`);
    for (const wrapped of wrapWords(option.detail, Math.max(20, renderer.width - 6))) {
      lines.push(`      ${wrapped}`);
    }
  });
  lines.push('');
  lines.push(withHelp('↑/↓ move · enter continue · esc cancel'));
  return lines;
}

async function selectMethod(renderer, input) {
  let cursor = 0;
  while (true) {
    const { help, key } = await readKeyedScreen(renderer, input, () => renderer.screen(methodPickerLines(renderer, cursor)));
    if (help) continue;
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape' || key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up' || key.name === 'down' || key.name === 'tab') cursor = cursor === 0 ? 1 : 0;
    if (key.name === 'return' || key.name === 'space') {
      return { cancelled: false, method: cursor === 0 ? 'link' : 'copy' };
    }
  }
}

function fallbackLines(renderer, failure) {
  return [
    renderer.style('Link failed', EMBERFORGE_PALETTE.red, true),
    '',
    ...wrapWords(failure.relativeDestination || failure.destination || '', Math.max(20, renderer.width - 2)),
    `Cause: ${failure.cause}`,
    '',
    'The installer will not change method silently.',
    'Install a complete managed copy at this destination instead? [y/N]',
    'y copy · n/enter/esc leave unchanged · ? help',
  ];
}

async function offerCopyFallback(renderer, input, failure) {
  while (true) {
    const { help, key } = await readKeyedScreen(renderer, input, () => renderer.screen(fallbackLines(renderer, failure)));
    if (help) continue;
    if (key.name === 'y') return 'copy';
    if (key.name === 'ctrl-c') return 'ctrl-c';
    if (key.name === 'n' || key.name === 'escape' || key.name === 'return' || key.name === 'eof') {
      return 'abort';
    }
  }
}

async function confirmPlans(renderer, input, plans, scope = 'project') {
  while (true) {
    const { help, key } = await readKeyedScreen(renderer, input, () => renderer.screen(summaryLines(renderer, plans, scope)));
    if (help) continue;
    if (key.name === 'ctrl-c') return { confirmed: false, exitCode: 130 };
    if (key.name === 'eof' || key.name === 'escape' || key.name === 'n' || key.name === 'return') {
      return { confirmed: false, exitCode: 0 };
    }
    if (key.name === 'y') return { confirmed: true, exitCode: 0 };
  }
}

/**
 * Run the interactive Emberforge Project Installation.
 *
 * @param {object} params
 * @param {object} params.catalog
 * @param {string} params.packageRoot
 * @param {string} params.projectRoot
 * @param {string} [params.customStateDir]
 * @param {object} params.io
 * @param {object} [params.options]
 * @returns {Promise<number>}
 */
export async function runProjectInstaller(params) {
  const {
    catalog,
    packageRoot,
    projectRoot,
    customStateDir,
    io,
    options = {},
  } = params;
  const env = io.env || process.env;
  const homeDir = path.resolve(params.homeDir || resolveHomeDir(env));
  const renderer = new TerminalRenderer(io, options);
  const input = new KeyInput(io.stdin);

  renderer.start();
  try {
    const revealKey = await runReveal(renderer, input);
    if (revealKey === 'ctrl-c' || revealKey === 'eof') {
      persistOutput(renderer, 'Installation cancelled. No files were written.');
      return revealKey === 'ctrl-c' ? 130 : 0;
    }

    if (params.initialScope === 'global') {
      const warning = await confirmGlobalWarning(renderer, input);
      if (!warning.confirmed) {
        persistOutput(renderer, 'Installation cancelled. No files were written.');
        return warning.exitCode;
      }
    }

    const selection = await selectSkills(renderer, input, catalog, params.initialScope === 'global' ? 'global' : 'project');
    if (selection.cancelled) {
      persistOutput(renderer, 'Installation cancelled. No files were written.');
      return selection.exitCode;
    }

    const scope = selection.scope || 'project';
    const root = scope === 'global' ? homeDir : projectRoot;
    const destinationGroups = scope === 'global'
      ? listGlobalDestinationGroups({
        registry: params.registry || loadHostRegistry(packageRoot),
        homeDir,
        env,
      })
      : listProjectDestinationGroups({
        registry: params.registry || loadHostRegistry(packageRoot),
        projectRoot,
        env,
      });
    const destinations = await selectDestinations(renderer, input, destinationGroups, scope);
    if (destinations.cancelled) {
      persistOutput(renderer, 'Installation cancelled. No files were written.');
      return destinations.exitCode;
    }

    const hostSelected = destinations.selectedRoots.some((selectedRoot) => selectedRoot !== UNIVERSAL_PROJECT_DESTINATION);
    let method = hostSelected ? 'link' : 'copy';
    if (hostSelected) {
      const methodChoice = await selectMethod(renderer, input);
      if (methodChoice.cancelled) {
        persistOutput(renderer, 'Installation cancelled. No files were written.');
        return methodChoice.exitCode;
      }
      method = methodChoice.method;
    }

    const classify = createProjectSkillClassifier({
      catalog,
      projectRoot: root,
      customStateDir,
      scope,
      homeDir,
    });
    const conflictErrors = findDestinationConflicts({
      projectRoot: root,
      skillIds: selection.skillIds,
      selectedRoots: destinations.selectedRoots,
      isOwned: (skillId, destination) => isDestinationOwned(root, skillId, destination, customStateDir, { scope }),
      classify,
      resolvePath: scope === 'global' ? resolveGlobalSkillPath : undefined,
    });
    if (conflictErrors.length > 0) {
      throw new Error(conflictErrors[0]);
    }

    const plans = selection.skillIds.map((skillId) => createInstallPlan(catalog, {
      skillId,
      projectRoot,
      homeDir,
      scope,
      customStateDir,
      packageRoot,
      selectedRoots: destinations.selectedRoots,
      destinationGroups,
      env,
      method,
    }));
    const conflict = plans.find((plan) => plan.unownedConflict);
    if (conflict) throw createUnownedConflictError(conflict);
    const pending = plans.find((plan) => plan.requiresApproval);
    if (pending) {
      renderer.cleanup();
      for (const plan of plans) {
        renderer.line(formatPlanHuman(plan));
      }
      throw createNeedsResolutionError(pending);
    }

    const confirmation = await confirmPlans(renderer, input, plans, scope);
    if (!confirmation.confirmed) {
      persistOutput(renderer, 'Installation cancelled. No files were written.');
      return confirmation.exitCode;
    }

    renderer.cleanup();

    const copyRoots = [];
    for (const skillId of selection.skillIds) {
      let result;
      while (true) {
        try {
          result = executeProjectInstall({
            catalog,
            skillId,
            projectRoot,
            homeDir,
            scope,
            customStateDir,
            packageRoot,
            selectedRoots: destinations.selectedRoots,
            destinationGroups,
            env,
            method,
            copyRoots,
            createLink: params.createLink,
          });
          break;
        } catch (err) {
          if (!err.linkFailure) throw err;
          const decision = await offerCopyFallback(renderer, input, err.linkFailure);
          if (decision !== 'copy') {
            persistOutput(renderer, 'Installation cancelled. No files were written.');
            return decision === 'ctrl-c' ? 130 : 0;
          }
          copyRoots.push(err.linkFailure.relativeRoot);
        }
      }
      for (const dest of result.plan.destinations) {
        const methodLabel = dest.method ? ` [${dest.method}]` : '';
        renderer.line(`Installed ${result.plan.title} (${result.plan.skill}) to ${dest.destination}${methodLabel}`);
      }
    }
    const doneLabel = scope === 'global' ? 'Global Installation' : 'Project Installation';
    renderer.line(`${doneLabel} complete: ${selection.skillIds.length} skill${selection.skillIds.length === 1 ? '' : 's'} installed.`);
    return 0;
  } finally {
    input.close();
    renderer.cleanup();
  }
}
