/**
 * CI counts only when the variable is set and is not empty, '0', or 'false' in any case.
 *
 * @param {NodeJS.ProcessEnv} env
 * @returns {boolean}
 */
export function isCiEnv(env) {
  const ci = env?.CI;
  return ci !== undefined && ci !== '' && ci !== '0' && String(ci).toLowerCase() !== 'false';
}

/**
 * The terminal side of DESIGN.md (Black Green): a near-black canvas, one emerald
 * accent used sparingly, zinc ink for text, and amber, red and sky for warn, error and info.
 */
export const SIGMA_PALETTE = Object.freeze({
  base: '#09090b',
  surface: '#111113',
  hairline: '#27272a',
  ink: '#f4f4f5',
  text: '#d4d4d8',
  mute: '#a1a1aa',
  primary: '#34d399',
  primaryDeep: '#10b981',
  onPrimary: '#022c22',
  ok: '#6ee7b7',
  warn: '#fbbf24',
  err: '#f87171',
  info: '#7dd3fc',
});

const RESET = '\x1b[0m';
const CLEAR = '\x1b[2J\x1b[H';
const ENTER_ALT_SCREEN = '\x1b[?1049h';
const LEAVE_ALT_SCREEN = '\x1b[?1049l';
const HIDE_CURSOR = '\x1b[?25l';
const SHOW_CURSOR = '\x1b[?25h';

const ANSI16_FG = Object.freeze({
  '#09090b': 30,
  '#111113': 30,
  '#27272a': 90,
  '#f4f4f5': 97,
  '#d4d4d8': 37,
  '#a1a1aa': 90,
  '#34d399': 32,
  '#10b981': 32,
  '#022c22': 30,
  '#6ee7b7': 32,
  '#fbbf24': 33,
  '#f87171': 31,
  '#7dd3fc': 36,
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

function paint(colorMode, value, hex, bold) {
  if (colorMode === 'plain') return value;
  if (colorMode === 'truecolor') return `${truecolorFg(hex, bold)}${value}${RESET}`;
  if (colorMode === 'ansi256') {
    const [red, green, blue] = hexToRgb(hex);
    return `\x1b[${bold ? '1;' : ''}38;5;${rgbTo256(red, green, blue)}m${value}${RESET}`;
  }
  return `\x1b[${bold ? '1;' : ''}${ANSI16_FG[hex] || 37}m${value}${RESET}`;
}

/**
 * A color helper for output that is not a full-screen renderer (summaries, progress lines).
 * It follows the same rules as the renderer: no color for NO_COLOR, TERM=dumb, --no-color,
 * --json, or a stream that is not a terminal.
 */
export function createStyler(stdout, env = process.env, options = {}) {
  const colorMode = detectColorMode(stdout, env, options);
  return {
    colorMode,
    noColor: colorMode === 'plain',
    ascii: typeof stdout.getColorDepth === 'function' && stdout.getColorDepth(env) < 4,
    style: (value, hex, bold = false) => paint(colorMode, value, hex, bold),
  };
}

export function wrapWords(value, width) {
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

export class TerminalRenderer {
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
      isCiEnv(this.env) ||
      !this.stdin.isTTY ||
      !this.stdout.isTTY,
    );
    this.dynamic = Boolean(this.stdout.isTTY && !this.static && !this.noColor);
    this.cursorHidden = false;
    this.paint = null;
    this.altScreen = false;
    this.cleaned = false;
    this.lastStaticScreen = null;
    this.page = 0;
    this.pages = 1;
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

  get height() {
    return Math.max(5, Number(this.stdout.rows) || 24);
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
    return paint(this.colorMode, value, hex, bold);
  }

  fill() {
    if (this.colorMode === 'truecolor') return truecolorBg(SIGMA_PALETTE.base);
    if (this.colorMode === 'ansi256') {
      const [red, green, blue] = hexToRgb(SIGMA_PALETTE.base);
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
    this.dynamic = false;
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
    const width = Math.max(1, this.width - 1);
    const rows = lines.flatMap((line) => {
      // Color only short headings. Wrap plain text so paths remain exact.
      const plain = line.replace(/\x1b\[[0-9;]*m/g, '');
      return plain.length <= width ? [line] : wrapWords(plain, width);
    });
    const limit = Math.max(1, this.height - (rows.length > this.height - 1 ? 3 : 1));
    this.pages = Math.max(1, Math.ceil(rows.length / limit));
    this.page = Math.min(this.page, this.pages - 1);
    const visible = rows.slice(this.page * limit, (this.page + 1) * limit);
    if (this.pages > 1) visible.push(`Page ${this.page + 1}/${this.pages}`, 'next/prev: page · esc: cancel');
    const content = visible.join('\n');
    if (!this.dynamic && this.lastStaticScreen === content) return;
    if (!this.dynamic) this.lastStaticScreen = content;
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
