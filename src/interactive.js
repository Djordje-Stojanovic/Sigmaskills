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
const HIDE_CURSOR = '\x1b[?25l';
const SHOW_CURSOR = '\x1b[?25h';

function hexToRgb(hex) {
  return [1, 3, 5].map((index) => Number.parseInt(hex.slice(index, index + 2), 16));
}

function color(hex, bold = false) {
  const [red, green, blue] = hexToRgb(hex);
  return `\x1b[${bold ? '1;' : ''}38;2;${red};${green};${blue}m`;
}

function background(hex) {
  const [red, green, blue] = hexToRgb(hex);
  return `\x1b[48;2;${red};${green};${blue}m`;
}

function wrapWords(value, width) {
  if (value.length <= width) return [value];
  const words = value.split(/\s+/);
  const lines = [];
  let line = '';
  for (const word of words) {
    if (!line) {
      line = word;
    } else if (line.length + word.length + 1 <= width) {
      line += ` ${word}`;
    } else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  return lines;
}

class TerminalRenderer {
  constructor(io, options) {
    this.stdout = io.stdout;
    this.stdin = io.stdin;
    this.env = io.env || process.env;
    this.forcedNarrow = Boolean(options.narrow);
    this.noColor = Boolean(
      options.noColor ||
      this.env.NO_COLOR !== undefined ||
      this.env.TERM === 'dumb' ||
      !this.stdout.isTTY,
    );
    this.static = Boolean(
      options.static ||
      this.noColor ||
      this.env.CI ||
      !this.stdin.isTTY ||
      !this.stdout.isTTY,
    );
    this.dynamic = Boolean(this.stdout.isTTY && !this.static && !this.noColor);
    this.cursorHidden = false;
  }

  get width() {
    return this.forcedNarrow ? Math.min(this.stdout.columns || 80, 60) : (this.stdout.columns || 80);
  }

  get narrow() {
    return this.forcedNarrow || this.width < 76;
  }

  style(value, hex, bold = false) {
    if (this.noColor) return value;
    return `${color(hex, bold)}${value}${RESET}`;
  }

  start() {
    if (this.dynamic) {
      this.stdout.write(HIDE_CURSOR);
      this.cursorHidden = true;
    }
  }

  cleanup() {
    if (this.cursorHidden) {
      this.stdout.write(`${RESET}${SHOW_CURSOR}`);
      this.cursorHidden = false;
    }
  }

  screen(lines) {
    const content = lines.join('\n');
    if (this.dynamic) {
      this.stdout.write(`${CLEAR}${background(EMBERFORGE_PALETTE.base)}${content}${RESET}\n`);
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
        ? { name: 'ctrl-c', ch: '', sequence: '' }
        : {
          name: key.name || key.sequence || 'unknown',
          ch: typeof _value === 'string' ? _value : '',
          sequence: key.sequence || '',
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

function revealLines(renderer, progress = 1) {
  const compact = renderer.narrow;
  const sigma = compact
    ? ['██████████', '      ███', '    ███', '  ███', '██████████']
    : ['██████████████████', '              ████', '           ████', '        ████', '     ████', '██████████████████'];
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
    renderer.style('Σ SIGMA SKILLS', EMBERFORGE_PALETTE.gold, true),
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
  lines.push(`↑/↓ move · space toggle · a select all${scope === 'global' ? '' : ' · g Global Installation'} · enter continue · esc cancel`);
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
    'y continue · n/enter/esc cancel',
  ];
}

async function confirmGlobalWarning(renderer, input) {
  renderer.screen(globalWarningLines(renderer));
  while (true) {
    const key = await input.next();
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
    renderer.screen(pickerLines(renderer, catalog, selected, cursor, error, scope));
    const key = await input.next();
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape' || key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up') cursor = (cursor + catalog.skills.length - 1) % catalog.skills.length;
    if (key.name === 'down') cursor = (cursor + 1) % catalog.skills.length;
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

function affectedHostLabel(host) {
  return host.detected ? `${host.displayName} [detected]` : host.displayName;
}

function destinationPickerLines(renderer, items, selectedRoots, cursor, query, error, scope) {
  const scopeLabel = scope === 'global' ? 'Global Installation' : 'Project Installation';
  const lines = [
    renderer.style('Σ SIGMA SKILLS', EMBERFORGE_PALETTE.gold, true),
    `${scopeLabel} · destinations${renderer.narrow ? ' · narrow' : ''}`,
    '',
    'Only .agents/skills is selected by default. Host-specific destinations stay unselected.',
    'Detection labels Agent Hosts; it never selects host-specific destinations.',
  ];

  if (query) {
    lines.push('');
    lines.push(`Search: ${query}`);
  } else {
    lines.push('');
  }

  items.forEach((item, index) => {
    const current = index === cursor ? '>' : ' ';
    const checked = selectedRoots.has(item.relativeRoot) ? 'x' : ' ';
    const title = item.kind === 'host'
      ? `${item.displayName} (${item.id})`
      : `${item.relativeRoot}${item.universal ? '  (universal default)' : ''}`;
    lines.push(`${current} [${checked}] ${title}`);
    if (item.kind === 'group' && item.universal) {
      const names = item.hosts.map((host) => affectedHostLabel(host)).join(', ');
      for (const wrapped of wrapWords(`Affected Agent Hosts: ${names}`, Math.max(20, renderer.width - 6))) {
        lines.push(`      ${wrapped}`);
      }
    } else if (item.kind === 'host') {
      const detected = item.detected ? ' [detected]' : '';
      lines.push(`      ${item.relativeRoot}${detected}`);
    } else if (item.hosts?.length) {
      lines.push(`      ${item.hosts.map((host) => affectedHostLabel(host)).join(', ')}`);
    }
    if (item.absoluteRoot) {
      for (const wrapped of wrapWords(item.absoluteRoot, Math.max(20, renderer.width - 6))) {
        lines.push(`      ${wrapped}`);
      }
    }
  });

  lines.push('');
  lines.push(`Selected destinations: ${selectedRoots.size}`);
  if (error) lines.push(renderer.style(`Error: ${error}`, EMBERFORGE_PALETTE.red, true));
  lines.push('Type to search every Agent Host · space toggle · enter continue · esc cancel');
  return lines;
}

function selectableGroups(groups) {
  return groups.filter((group) => group.selectable);
}

function pickerItems(groups, query) {
  if (query) {
    return searchHosts(groups, query)
      .filter((host) => host.relativeRoot)
      .map((host) => ({
        kind: 'host',
        id: host.id,
        displayName: host.displayName,
        relativeRoot: host.relativeRoot,
        absoluteRoot: host.group?.absoluteRoot || '',
        detected: host.detected,
        universal: host.relativeRoot === UNIVERSAL_PROJECT_DESTINATION,
      }));
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
    renderer.screen(destinationPickerLines(renderer, items, selectedRoots, cursor, query, error, scope));
    const key = await input.next();
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
    if (key.name === 'up' && items.length) cursor = (cursor + items.length - 1) % items.length;
    if (key.name === 'down' && items.length) cursor = (cursor + 1) % items.length;
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
      lines.push(`  ${dest.destination}${method}`);
      if (dest.dependsOn) lines.push(`    depends on ${dest.dependsOn}`);
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
  lines.push('y confirm · n/enter/esc cancel');
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
    renderer.style('Σ SIGMA SKILLS', EMBERFORGE_PALETTE.gold, true),
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
  lines.push('↑/↓ move · enter continue · esc cancel');
  return lines;
}

async function selectMethod(renderer, input) {
  let cursor = 0;
  while (true) {
    renderer.screen(methodPickerLines(renderer, cursor));
    const key = await input.next();
    if (key.name === 'ctrl-c') return { cancelled: true, exitCode: 130 };
    if (key.name === 'escape' || key.name === 'eof') return { cancelled: true, exitCode: 0 };
    if (key.name === 'up' || key.name === 'down') cursor = cursor === 0 ? 1 : 0;
    if (key.name === 'return' || key.name === 'space') {
      return { cancelled: false, method: cursor === 0 ? 'link' : 'copy' };
    }
  }
}

function fallbackLines(renderer, failure) {
  return [
    renderer.style('Link failed', EMBERFORGE_PALETTE.red, true),
    '',
    failure.relativeDestination || failure.destination,
    `Cause: ${failure.cause}`,
    '',
    'The installer will not change method silently.',
    'Install a complete managed copy at this destination instead? [y/N]',
    'y copy · n/enter/esc leave unchanged',
  ];
}

async function offerCopyFallback(renderer, input, failure) {
  renderer.screen(fallbackLines(renderer, failure));
  while (true) {
    const key = await input.next();
    if (key.name === 'y') return 'copy';
    if (key.name === 'ctrl-c') return 'ctrl-c';
    if (key.name === 'n' || key.name === 'escape' || key.name === 'return' || key.name === 'eof') {
      return 'abort';
    }
  }
}

async function confirmPlans(renderer, input, plans, scope = 'project') {
  renderer.screen(summaryLines(renderer, plans, scope));
  while (true) {
    const key = await input.next();
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
      renderer.line('Installation cancelled. No files were written.');
      return revealKey === 'ctrl-c' ? 130 : 0;
    }

    if (params.initialScope === 'global') {
      const warning = await confirmGlobalWarning(renderer, input);
      if (!warning.confirmed) {
        renderer.line('Installation cancelled. No files were written.');
        return warning.exitCode;
      }
    }

    const selection = await selectSkills(renderer, input, catalog, params.initialScope === 'global' ? 'global' : 'project');
    if (selection.cancelled) {
      renderer.line('Installation cancelled. No files were written.');
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
      renderer.line('Installation cancelled. No files were written.');
      return destinations.exitCode;
    }

    const hostSelected = destinations.selectedRoots.some((selectedRoot) => selectedRoot !== UNIVERSAL_PROJECT_DESTINATION);
    let method = hostSelected ? 'link' : 'copy';
    if (hostSelected) {
      const methodChoice = await selectMethod(renderer, input);
      if (methodChoice.cancelled) {
        renderer.line('Installation cancelled. No files were written.');
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
      for (const plan of plans) {
        renderer.line(formatPlanHuman(plan));
      }
      throw createNeedsResolutionError(pending);
    }

    const confirmation = await confirmPlans(renderer, input, plans, scope);
    if (!confirmation.confirmed) {
      renderer.line('Installation cancelled. No files were written.');
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
            renderer.line('Installation cancelled. No files were written.');
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
