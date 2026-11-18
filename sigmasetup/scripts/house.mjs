#!/usr/bin/env node
// House files: keep a repo's copies of the owner's master rule files current.
//   check <repo>   one row per house file: current, drift or missing. Exit 1 on drift.
//   apply <repo>   bring every row up to date; saves the old copies first and prints the undo command.
//   undo <repo>    put back what the last apply changed, and delete what it created.
// --exact: a section becomes the master's word for word; without it, lines only the repo has stay at its end.
// Where the masters live: --source <dir|git url|owner/repo>, else SIGMASETUP_HOUSE, else a "house:" line
// in this skill's personal-instructions block. Map lines in that block ("copy:", "section:", "seed:") pick
// the files; without any, the default map below runs.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SKILL_MD = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'SKILL.md');
export const DEFAULT_MAP = ['copy: ENGINEERING.md', 'copy: DESIGN.md', 'section: AGENTS.md#How we work'];

/** The lines between <sigmaskills-custom> and </sigmaskills-custom> of a SKILL.md text. */
export function personalLines(text) {
  const m = /<sigmaskills-custom>([\s\S]*?)<\/sigmaskills-custom>/.exec(text || '');
  return m ? m[1].split(/\r?\n/).map((l) => l.trim().replace(/^[-*]\s+/, '')).filter(Boolean) : [];
}

/** { source, map } from the personal lines; map entries are { kind, from, heading, to }. */
export function readConfig(lines) {
  const value = (key) => lines.filter((l) => l.toLowerCase().startsWith(`${key}:`)).map((l) => l.slice(key.length + 1).trim());
  const rules = lines.filter((l) => /^(copy|section|seed):/i.test(l));
  const map = (rules.length ? rules : DEFAULT_MAP).map((line) => {
    const [, kind, rest] = /^(\w+):\s*(.*)$/.exec(line);
    const [left, to] = rest.split(/\s*->\s*/);
    const [from, heading] = left.split('#');
    return { kind: kind.toLowerCase(), from: from.trim(), heading: heading?.trim(), to: (to || from).trim() };
  });
  return { source: value('house')[0], map };
}

function resolveSource(source) {
  if (!source) {
    throw new Error('No house source. Set SIGMASETUP_HOUSE=<folder or git URL>, or add "house: <folder or git URL>" to the personal-instructions block of sigmasetup/SKILL.md.');
  }
  if (fs.existsSync(source) && fs.statSync(source).isDirectory()) return source;
  const url = /^[\w.-]+\/[\w.-]+$/.test(source) ? `https://github.com/${source}.git` : source;
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigmasetup-house-'));
  const r = spawnSync('git', ['clone', '--depth', '1', '-q', url, dir], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`git clone ${url} failed: ${(r.stderr || '').trim()}`);
  return dir;
}

const read = (file) => (fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null);
const lf = (text) => text.replace(/\r\n/g, '\n');
// The master's text in the repo copy's line endings, so git shows only real changes.
const sameEol = (repoText, text) => (repoText === null ? text : /\r\n/.test(repoText) ? lf(text).replace(/\n/g, '\r\n') : lf(text));

/** [start, end) line indexes of "## heading" up to the next level-1 or level-2 heading, or null. */
function sectionRange(lines, heading) {
  const start = lines.findIndex((l) => l.trim() === `## ${heading}`);
  if (start < 0) return null;
  let end = lines.findIndex((l, i) => i > start && /^#{1,2} /.test(l));
  if (end < 0) end = lines.length;
  while (end > start + 1 && lines[end - 1].trim() === '') end -= 1;
  return [start, end];
}

/** The repo text with its section replaced by the master's; repo-only lines stay at the section's end. */
export function mergeSection(repoText, masterText, heading, exact = false) {
  const master = lf(masterText).split('\n');
  const mr = sectionRange(master, heading);
  if (!mr) return null;
  const section = master.slice(mr[0], mr[1]);
  const eol = /\r\n/.test(repoText || '') ? '\r\n' : '\n';
  const lines = lf(repoText || '').split('\n');
  const rr = sectionRange(lines, heading);
  if (!rr) {
    const body = lf(repoText || '').replace(/\s+$/, '');
    return { text: (body ? `${body}\n\n` : '') + section.join('\n').concat('\n').replace(/\n/g, eol), kept: [] };
  }
  const known = new Set(section.map((l) => l.trim()));
  const kept = exact ? [] : lines.slice(rr[0] + 1, rr[1]).filter((l) => l.trim() && !known.has(l.trim()));
  const merged = [...section, ...(kept.length ? ['', ...kept] : [])];
  const out = [...lines.slice(0, rr[0]), ...merged, ...lines.slice(rr[1])].join('\n');
  return { text: out.replace(/\n/g, eol), kept };
}

/** One row per house file: { file, kind, state, note, next } where next is the new text (null = no write). */
export function plan(repo, masters, map, exact = false) {
  const rows = [];
  for (const rule of map) {
    const masterText = read(path.join(masters, rule.from));
    if (masterText === null) { rows.push({ file: rule.to, kind: rule.kind, state: 'no master', note: `${rule.from} is not in the house source` }); continue; }
    if (rule.kind === 'copy') {
      const repoText = read(path.join(repo, rule.to));
      // Line endings alone are not drift: git's autocrlf rewrites them on checkout.
      const state = repoText === null ? 'missing' : lf(repoText) === lf(masterText) ? 'current' : 'drift';
      rows.push({ file: rule.to, kind: 'copy', state, note: state === 'drift' ? diffLine(repoText, masterText) : '', next: state === 'current' ? null : sameEol(repoText, masterText) });
    } else if (rule.kind === 'seed') {
      const exists = read(path.join(repo, rule.to)) !== null;
      rows.push({ file: rule.to, kind: 'seed', state: exists ? 'current' : 'missing', note: exists ? '' : `write it from ${rule.from}: fill its placeholders with this repo's facts` });
    } else {
      // A section lands in every rule file that has it; with none, in the named file, else in CLAUDE.md when only that exists.
      const files = ['AGENTS.md', 'CLAUDE.md'].includes(rule.to) ? [rule.to, rule.to === 'AGENTS.md' ? 'CLAUDE.md' : 'AGENTS.md'] : [rule.to];
      const texts = Object.fromEntries(files.map((f) => [f, read(path.join(repo, f))]));
      let targets = files.filter((f) => texts[f] && sectionRange(lf(texts[f]).split('\n'), rule.heading));
      if (!targets.length) targets = [texts[rule.to] === null && texts[files[1]] ? files[1] : rule.to];
      for (const f of targets) {
        const merged = mergeSection(texts[f], masterText, rule.heading, exact);
        if (!merged) { rows.push({ file: f, kind: 'section', state: 'no master', note: `"## ${rule.heading}" is not in ${rule.from}` }); continue; }
        const has = texts[f] && sectionRange(lf(texts[f]).split('\n'), rule.heading);
        const state = texts[f] !== null && lf(texts[f]) === lf(merged.text) ? 'current' : has ? 'drift' : 'missing';
        const note = [`## ${rule.heading}`, merged.kept.length ? `keeps ${merged.kept.length} repo-only line(s)` : ''].filter(Boolean).join('; ');
        rows.push({ file: f, kind: 'section', state, note, kept: merged.kept, next: state === 'current' ? null : merged.text });
      }
    }
  }
  return rows;
}

function diffLine(a, b) {
  const x = lf(a).split('\n'); const y = lf(b).split('\n');
  const i = x.findIndex((l, n) => l !== y[n]);
  return `${x.length} vs ${y.length} lines; first change at line ${(i < 0 ? x.length : i) + 1}`;
}

function undoRoot(repo) {
  const r = spawnSync('git', ['-C', repo, 'rev-parse', '--absolute-git-dir'], { encoding: 'utf8' });
  return r.status === 0 ? path.join(r.stdout.trim(), 'sigmasetup-undo') : path.join(repo, '.sigmasetup-undo');
}

export function apply(repo, rows) {
  const todo = rows.filter((r) => r.next != null);
  if (!todo.length) return null;
  const dir = path.join(undoRoot(repo), new Date().toISOString().replace(/[:.]/g, '-'));
  const record = { changed: [], created: [] };
  for (const { file } of todo) {
    const target = path.join(repo, file);
    if (fs.existsSync(target)) {
      if (record.changed.includes(file)) continue;
      fs.mkdirSync(path.dirname(path.join(dir, 'files', file)), { recursive: true });
      fs.copyFileSync(target, path.join(dir, 'files', file));
      record.changed.push(file);
    } else record.created.push(file);
  }
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'undo.json'), JSON.stringify(record, null, 2));
  for (const { file, next } of todo) {
    fs.mkdirSync(path.dirname(path.join(repo, file)), { recursive: true });
    fs.writeFileSync(path.join(repo, file), next);
  }
  return dir;
}

export function undo(repo) {
  const root = undoRoot(repo);
  const last = fs.existsSync(root) ? fs.readdirSync(root).sort().pop() : null;
  if (!last) return null;
  const dir = path.join(root, last);
  const { changed, created } = JSON.parse(fs.readFileSync(path.join(dir, 'undo.json'), 'utf8'));
  for (const file of changed) fs.copyFileSync(path.join(dir, 'files', file), path.join(repo, file));
  for (const file of created) fs.rmSync(path.join(repo, file), { force: true });
  fs.rmSync(dir, { recursive: true, force: true });
  if (!fs.readdirSync(root).length) fs.rmSync(root, { recursive: true });
  return { changed, created };
}

function table(rows) {
  const out = ['| House file | Kind | State | Note |', '|---|---|---|---|'];
  for (const r of rows) out.push(`| ${r.file} | ${r.kind} | ${r.state} | ${r.note || ''} |`);
  return out.join('\n');
}

function main(argv) {
  const [cmd, repoArg = '.', ...rest] = argv;
  if (!['check', 'apply', 'undo'].includes(cmd)) {
    console.error('usage: node house.mjs check|apply|undo <repo> [--source <dir|git url|owner/repo>] [--exact]');
    return 2;
  }
  const repo = path.resolve(repoArg);
  if (cmd === 'undo') {
    const done = undo(repo);
    console.log(done ? `Put back: ${done.changed.join(', ') || 'none'}. Deleted: ${done.created.join(', ') || 'none'}.` : 'Nothing to undo.');
    return 0;
  }
  const lines = personalLines(read(SKILL_MD));
  const config = readConfig(lines);
  const at = rest.indexOf('--source');
  const source = at >= 0 ? rest[at + 1] : process.env.SIGMASETUP_HOUSE || config.source;
  const masters = resolveSource(source);
  try {
    return run(cmd, repo, masters, source, config.map, rest.includes('--exact'));
  } finally {
    if (masters !== source) fs.rmSync(masters, { recursive: true, force: true });
  }
}

function run(cmd, repo, masters, source, map, exact) {
  const rows = plan(repo, masters, map, exact);
  console.log(`House source: ${source}\n\n${table(rows)}`);
  for (const r of rows) if (r.kept?.length) console.log(`\n${r.file} keeps these repo-only lines in its section:\n${r.kept.map((l) => `  ${l}`).join('\n')}`);
  if (cmd === 'check') return rows.some((r) => r.next != null || (r.kind === 'seed' && r.state === 'missing')) ? 1 : 0;
  const dir = apply(repo, rows);
  console.log(dir ? `\nWrote ${rows.filter((r) => r.next != null).length} file(s). Undo: node "${fileURLToPath(import.meta.url)}" undo "${repo}"` : '\nEverything is current; nothing written.');
  const seeds = rows.filter((r) => r.kind === 'seed' && r.state === 'missing');
  if (seeds.length) console.log(`Still to write by hand: ${seeds.map((r) => r.file).join(', ')}.`);
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { process.exitCode = main(process.argv.slice(2)); } catch (e) { console.error(e.message); process.exitCode = 2; }
}
