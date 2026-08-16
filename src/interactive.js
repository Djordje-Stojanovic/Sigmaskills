import readline from 'node:readline';
import { createInstallPlan } from './plan.js';
import { createUnownedConflictError, executeProjectInstall } from './transaction.js';

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
        ? { name: 'ctrl-c' }
        : { name: key.name || key.sequence || 'unknown' };
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

function pickerLines(renderer, catalog, selected, cursor, error) {
  const lines = [
    renderer.style('Σ SIGMA SKILLS', EMBERFORGE_PALETTE.gold, true),
    `Project Installation (default)${renderer.narrow ? ' · narrow' : ''}`,
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
  lines.push('↑/↓ move · space toggle · a select all · enter continue · esc cancel');
  return lines;
}

async function selectSkills(renderer, input, catalog) {
  const selected = new Set();
  let cursor = 0;
  let error = '';

  while (true) {
    renderer.screen(pickerLines(renderer, catalog, selected, cursor, error));
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
    if (key.name === 'return') {
      if (selected.size === 0) {
        error = 'Select at least one skill.';
      } else {
        return {
          cancelled: false,
          skillIds: catalog.skills.filter((skill) => selected.has(skill.id)).map((skill) => skill.id),
        };
      }
    }
  }
}

function summaryLines(renderer, plans) {
  const lines = [
    renderer.style('Confirm Project Installation', EMBERFORGE_PALETTE.gold, true),
    '',
    'Resolved destinations:',
  ];
  for (const plan of plans) {
    lines.push(`${plan.title} (${plan.skill})`);
    lines.push(`  ${plan.destination}`);
  }
  lines.push('');
  lines.push(`Install ${plans.length} selected skill${plans.length === 1 ? '' : 's'}? [y/N]`);
  lines.push('y confirm · n/enter/esc cancel');
  return lines;
}

async function confirmPlans(renderer, input, plans) {
  renderer.screen(summaryLines(renderer, plans));
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
  const renderer = new TerminalRenderer(io, options);
  const input = new KeyInput(io.stdin);

  renderer.start();
  try {
    const revealKey = await runReveal(renderer, input);
    if (revealKey === 'ctrl-c' || revealKey === 'eof') {
      renderer.line('Installation cancelled. No files were written.');
      return revealKey === 'ctrl-c' ? 130 : 0;
    }

    const selection = await selectSkills(renderer, input, catalog);
    if (selection.cancelled) {
      renderer.line('Installation cancelled. No files were written.');
      return selection.exitCode;
    }

    const plans = selection.skillIds.map((skillId) => createInstallPlan(catalog, {
      skillId,
      projectRoot,
      customStateDir,
    }));
    const conflict = plans.find((plan) => plan.unownedConflict);
    if (conflict) throw createUnownedConflictError(conflict);

    const confirmation = await confirmPlans(renderer, input, plans);
    if (!confirmation.confirmed) {
      renderer.line('Installation cancelled. No files were written.');
      return confirmation.exitCode;
    }

    input.close();
    renderer.cleanup();

    for (const skillId of selection.skillIds) {
      const result = executeProjectInstall({
        catalog,
        skillId,
        projectRoot,
        customStateDir,
        packageRoot,
      });
      renderer.line(`Installed ${result.plan.title} (${result.plan.skill}) to ${result.plan.destination}`);
    }
    renderer.line(`Project Installation complete: ${selection.skillIds.length} skill${selection.skillIds.length === 1 ? '' : 's'} installed.`);
    return 0;
  } finally {
    input.close();
    renderer.cleanup();
  }
}
