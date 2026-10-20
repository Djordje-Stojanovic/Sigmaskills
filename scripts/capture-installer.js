#!/usr/bin/env node
/**
 * Maintainer script: capture the Sigma Installer as SVG screenshots for the README.
 *
 *   node scripts/capture-installer.js [out-dir]     (default: docs/images)
 *
 * It runs the real wizard in a simulated 24-bit terminal, feeds it keys, and turns the ANSI
 * frames into SVG. The summary capture installs two packs, so it needs the network.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import { fileURLToPath } from 'node:url';
import { runCli } from '../src/cli.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.resolve(process.argv[2] || path.join(ROOT, 'docs', 'images'));
const COLS = 100;
const ROWS = 24;
const ANSI = /\x1b\[([0-9;?]*)([A-Za-z])/g;
const DEFAULT_FG = '#d4d4d8';
const CANVAS = '#09090b';

const DOWN = '\x1b[B';
const RIGHT = '\x1b[C';

function simulate(keys, env, args, { tty = true } = {}) {
  const stdin = new PassThrough();
  stdin.isTTY = tty;
  stdin.setRawMode = () => {};
  const stdout = new PassThrough();
  stdout.isTTY = tty;
  stdout.columns = COLS;
  stdout.rows = ROWS;
  stdout.getColorDepth = () => 24;
  const stderr = new PassThrough();
  let out = '';
  stdout.setEncoding('utf8');
  stdout.on('data', (chunk) => { out += chunk; });
  queueMicrotask(() => stdin.end(keys));
  return runCli(args, { stdin, stdout, stderr, env }).then(() => out);
}

function escapeXml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** One ANSI line to SVG tspans. Only foreground color and bold matter on this canvas. */
function lineToTspans(line) {
  let fg = DEFAULT_FG;
  let bold = false;
  let last = 0;
  let out = '';
  const emit = (text) => {
    if (!text) return;
    out += `<tspan fill="${fg}"${bold ? ' font-weight="700"' : ''}>${escapeXml(text)}</tspan>`;
  };
  for (const match of line.matchAll(ANSI)) {
    emit(line.slice(last, match.index));
    last = match.index + match[0].length;
    if (match[2] !== 'm') continue;
    const codes = match[1].split(';').map(Number);
    for (let index = 0; index < codes.length; index += 1) {
      const code = codes[index];
      if (code === 0) { fg = DEFAULT_FG; bold = false; }
      else if (code === 1) bold = true;
      else if (code === 38 && codes[index + 1] === 2) {
        const [red, green, blue] = codes.slice(index + 2, index + 5);
        fg = `#${[red, green, blue].map((value) => value.toString(16).padStart(2, '0')).join('')}`;
        index += 4;
      }
    }
  }
  emit(line.slice(last));
  return out;
}

export function framesToSvg(lines, title) {
  const cw = 8.45;
  const lh = 19;
  const pad = 18;
  const bar = 34;
  const width = Math.ceil(COLS * cw + pad * 2);
  const height = Math.ceil(lines.length * lh + pad * 2 + bar);
  const rows = lines.map((line, index) => (
    `<text x="${pad}" y="${bar + pad + (index + 0.8) * lh}" xml:space="preserve">${lineToTspans(line)}</text>`
  )).join('\n  ');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeXml(title)}">
  <title>${escapeXml(title)}</title>
  <rect width="${width}" height="${height}" rx="10" fill="${CANVAS}" stroke="#27272a"/>
  <circle cx="22" cy="17" r="5" fill="#3f3f46"/><circle cx="40" cy="17" r="5" fill="#3f3f46"/><circle cx="58" cy="17" r="5" fill="#34d399"/>
  <text x="${width / 2}" y="21" text-anchor="middle" fill="#a1a1aa" font-family="ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace" font-size="12">${escapeXml(title)}</text>
  <g font-family="ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace" font-size="14">
  ${rows}
  </g>
</svg>
`;
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-capture-'));
  const project = path.join(root, 'my-project');
  const home = path.join(root, 'home');
  fs.mkdirSync(project, { recursive: true });
  fs.mkdirSync(path.join(home, '.claude'), { recursive: true });
  fs.mkdirSync(path.join(home, '.codex'), { recursive: true });
  const env = { ...process.env, HOME: home, USERPROFILE: home, TERM: 'xterm-256color', CI: '' };
  delete env.NO_COLOR;
  delete env.SIGMA_STORGESTUDIO_DIR;

  // 1. What: Sigma, Matt Pocock and Three.js picked, HyperFrames opened with two skills picked.
  const what = await simulate(
    `123${DOWN}${DOWN}${DOWN}${RIGHT}${DOWN}${DOWN} ${DOWN} `,
    env,
    ['--project', project],
  );
  const whatFrames = what.split('\x1b[2J\x1b[H');
  const whatFrame = whatFrames.filter((frame) => frame.includes('Pick packs')).at(-1);

  // 2. Where: the same run, one step on.
  const where = await simulate(`123${'\r'}`, env, ['--project', project]);
  const whereFrame = where.split('\x1b[2J\x1b[H').filter((frame) => frame.includes('Method')).at(-1);

  // 3. Done: install Sigma and Three.js for Claude Code, then print the summary.
  const done = await simulate('', env, ['install', '--preset', 'sigma', '--preset', 'threejs', '--agent', 'claude', '--project', project], { tty: true });

  const trim = (frame) => frame.replace(/\x1b\[\?[0-9]+[hl]/g, '').split('\n').map((line) => line.replace(/\s+$/, '')).slice(0, ROWS - 1);
  const summary = done.replace(/\x1b\[\?[0-9]+[hl]/g, '').split('\n').map((line) => line.replace(/\s+$/, ''));
  while (summary.length && !summary[0].trim()) summary.shift();
  while (summary.length && !summary.at(-1).trim()) summary.pop();

  const tidy = (line) => line.split(project).join('~/my-project').split(home).join('~');
  const write = (name, lines, title) => {
    fs.writeFileSync(path.join(OUT, name), framesToSvg(lines.map(tidy), title));
    console.log(path.join(OUT, name));
  };
  write('installer-what.svg', trim(whatFrame), 'npx @djordje-stojanovic/sigmaskills');
  write('installer-where.svg', trim(whereFrame), 'npx @djordje-stojanovic/sigmaskills');
  write('installer-done.svg', summary, 'npx @djordje-stojanovic/sigmaskills install --preset sigma --preset threejs --agent claude');
  fs.rmSync(root, { recursive: true, force: true });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
