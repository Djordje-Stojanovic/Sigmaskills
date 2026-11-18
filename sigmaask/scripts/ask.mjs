#!/usr/bin/env node
// SigmaAsk scan: what is on this machine, and which known skills match some words.
//   node ask.mjs [words...] [--project <dir>] [--offline]
//   node ask.mjs --where <skill>   where to read that skill's SKILL.md
// Node 22 standard library only. Reads references/catalog.json (generated from the registry).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const NPM = '@djordje-stojanovic/sigmaskills';
const INSTALL = (what) => `npx ${NPM} install ${what} --global --yes`;

const argv = process.argv.slice(2);
const flag = (name) => { const i = argv.indexOf(name); return i < 0 ? null : argv.splice(i, 2)[1] ?? ''; };
const projectArg = flag('--project');
const catalogArg = flag('--catalog');
const whereArg = flag('--where');
const offline = argv.includes('--offline') || Boolean(process.env.SIGMAASK_OFFLINE);
const words = argv.filter((a) => a !== '--offline');

const env = process.env;
const home = path.resolve(env.HOME || env.USERPROFILE || os.homedir());
const project = path.resolve(projectArg || process.cwd());
const cat = JSON.parse(fs.readFileSync(catalogArg || path.join(HERE, '..', 'references', 'catalog.json'), 'utf8'));

// Same bases as src/destinations.js in the installer.
const BASES = {
  home,
  configHome: env.XDG_CONFIG_HOME || path.join(home, '.config'),
  claudeHome: env.CLAUDE_CONFIG_DIR || path.join(home, '.claude'),
  codexHome: env.CODEX_HOME || path.join(home, '.codex'),
  hermesHome: env.HERMES_HOME || path.join(home, '.hermes'),
  vibeHome: env.VIBE_HOME || path.join(home, '.vibe'),
  autohandHome: env.AUTOHAND_HOME || path.join(home, '.autohand'),
};
const short = (p) => (p.startsWith(home) ? '~' + p.slice(home.length) : p).replace(/\\/g, '/');
const real = (p) => { try { return fs.realpathSync(p); } catch { return null; } };
const isDir = (p) => { try { return fs.statSync(p).isDirectory(); } catch { return false; } };
const readJson = (p) => { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return null; } };

// 1. Hosts present: a host's own config folder exists. Shared folders (~/.agents, ~/.config/agents) prove nothing.
const shared = new Set([home, BASES.configHome, path.join(home, '.agents'), path.join(BASES.configHome, 'agents')].map((p) => path.resolve(p)));
const dirs = []; // { path, label, hosts }
const addDir = (p, hostName, label) => {
  const d = dirs.find((x) => x.path === p);
  if (d) { if (hostName && !d.hosts.includes(hostName)) d.hosts.push(hostName); }
  else dirs.push({ path: p, label, hosts: hostName ? [hostName] : [] });
};
const present = [];
for (const host of cat.hosts) {
  if (host.global && BASES[host.global[0]]) {
    const dir = path.resolve(BASES[host.global[0]], ...host.global.slice(1));
    const root = path.dirname(dir);
    // A host on a shared folder (Codex, Amp, ...) shows by ~/.<id> or ~/.config/<id>.
    const own = shared.has(root) ? [path.join(home, '.' + host.id), path.join(BASES.configHome, host.id)] : [root];
    if (own.some(isDir)) present.push(host.name);
    addDir(dir, host.name, 'global');
  }
  if (host.project) addDir(path.resolve(project, host.project), host.name, 'project');
}
// Apps that keep no skills folder of their own.
const appData = env.APPDATA || (process.platform === 'darwin' ? path.join(home, 'Library', 'Application Support') : BASES.configHome);
if (isDir(path.join(appData, 'Claude'))) present.push('Claude desktop');
if (isDir(path.join(home, '.t3'))) present.push('T3 Code');

// 2. Installed skills, by the real folder behind every link.
const installed = new Map(); // name -> Map(realSkillDir -> [shown paths])
const shownDirs = new Map(); // realDir -> { paths, hosts, count, label }
for (const d of dirs) {
  const r = real(d.path);
  if (!r || !isDir(r)) continue;
  const entry = shownDirs.get(r) || { paths: [], hosts: [], count: 0, label: d.label };
  if (!entry.paths.includes(short(d.path))) entry.paths.push(short(d.path));
  for (const h of d.hosts) if (!entry.hosts.includes(h)) entry.hosts.push(h);
  if (!shownDirs.has(r)) {
    for (const name of fs.readdirSync(r)) {
      const skillDir = real(path.join(r, name));
      if (!skillDir || !fs.existsSync(path.join(skillDir, 'SKILL.md'))) continue;
      entry.count++;
      const copies = installed.get(name) || new Map();
      copies.set(skillDir, (copies.get(skillDir) || []).concat(short(path.join(d.path, name))));
      installed.set(name, copies);
    }
  }
  shownDirs.set(r, entry);
}

if (whereArg) {
  const pack = cat.packs.find((p) => p.skills.some(([id]) => id === whereArg));
  const skill = pack?.skills.find(([id]) => id === whereArg);
  const local = installed.has(whereArg) ? [...installed.get(whereArg).keys()].map((d) => path.join(d, 'SKILL.md')) : [];
  const lines = local.map((f) => `installed: ${f}`);
  if (pack && !local.length) {
    const [repo, rest] = pack.sources[skill[2] || 0].split('@');
    const [ref, ...dir] = rest.split('/');
    const sub = [...dir.filter(Boolean), whereArg].join('/');
    lines.push(`${pack.id}: https://raw.githubusercontent.com/${repo}/${ref}/${sub}/SKILL.md (404: look in https://github.com/${repo}/tree/${ref}/${dir.filter(Boolean).join('/')})`);
  }
  if (cat.retired[whereArg]) lines.push(`retired: use ${cat.retired[whereArg]}`);
  console.log(lines.join('\n') || `${whereArg}: not installed and in no pack: search the web`);
  process.exit(0);
}

// 3. Out of date: installer state against the pinned refs here and the newest npm release.
const states = [path.join(home, '.agents', '.sigmaskills'), path.join(project, '.agents', '.sigmaskills')];
const sigmaState = {}; const packState = {};
for (const dir of states) {
  Object.assign(sigmaState, readJson(path.join(dir, 'state.json'))?.skills || {});
  Object.assign(packState, readJson(path.join(dir, 'packs.json'))?.skills || {});
}
let latest = cat.release; let latestFrom = 'this skill';
if (!offline) {
  try {
    const res = await fetch(`https://registry.npmjs.org/${NPM}/latest`, { signal: AbortSignal.timeout(2500) });
    if (res.ok) { latest = (await res.json()).version; latestFrom = 'npm'; }
  } catch { /* offline: compare with the release this skill came from */ }
}
const newer = (a, b) => { const x = a.split('.').map(Number); const y = b.split('.').map(Number); for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i]; return false; };

// Output.
const out = [];
const sigma = cat.packs.find((p) => p.id === 'sigma');
const packOf = new Map();
for (const p of cat.packs) for (const [id] of p.skills) if (!packOf.has(id)) packOf.set(id, p);
const sigmaIds = sigma.skills.map(([id]) => id);
const releases = [...new Set(sigmaIds.map((id) => sigmaState[id]?.release).filter(Boolean))].sort();
out.push(`release: installed ${releases.join(', ') || 'none'} · latest ${latest} (${latestFrom})`);
out.push(`hosts: ${[...new Set(present)].join(', ') || 'none found'}`);
const dirLines = [...shownDirs.values()].filter((d) => d.count > 0).sort((a, b) => b.count - a.count)
  .map((d) => `  ${d.label} ${d.paths.join(' = ')}: ${d.count}${d.hosts.length ? ` (${d.hosts.slice(0, 4).join(', ')}${d.hosts.length > 4 ? ` +${d.hosts.length - 4}` : ''})` : ''}`);
out.push(`skill folders (real folder, count):`, ...(dirLines.length ? dirLines : ['  none']));

const missingSigma = sigmaIds.filter((id) => !installed.has(id));
const staleSigma = sigmaIds.filter((id) => sigmaState[id]?.release && newer(latest, sigmaState[id].release));
out.push(`sigma: ${sigmaIds.length - missingSigma.length}/${sigmaIds.length} installed` +
  (missingSigma.length ? ` · missing ${missingSigma.join(', ')}` : '') +
  (staleSigma.length ? ` · out of date ${staleSigma.length} (run: npx ${NPM}@latest update --global --yes)` : ''));

const packLines = [];
let anyStale = false;
for (const p of cat.packs) {
  if (p.id === 'sigma') continue;
  const have = p.skills.filter(([id]) => installed.has(id));
  if (!have.length) continue;
  const stale = have.filter(([id]) => { const s = packState[id]; return s && p.refs[s.source] && s.revision !== p.refs[s.source]; });
  anyStale ||= stale.length > 0;
  packLines.push(`${p.id} ${have.length}/${p.skills.length}${stale.length ? ` (${stale.length} out of date)` : ''}`);
}
out.push(`packs: ${packLines.join(' · ') || 'none'}${anyStale ? ` · update: npx ${NPM}@latest update --global --yes` : ''}`);

const retiredHere = [...installed.keys()].filter((id) => cat.retired[id]);
for (const id of retiredHere) out.push(`retired: ${id} → use ${cat.retired[id]} (${[...installed.get(id).values()].flat()[0]}; remove: npx ${NPM} uninstall --skill ${id} --global --yes)`);
// A project copy shadowing a global one is normal; two global copies are waste.
const inProject = (shown) => shown.startsWith(short(project) + '/');
const dupes = [...installed].filter(([, copies]) => copies.size > 1);
const shadow = []; const waste = [];
for (const [id, copies] of dupes) {
  const firsts = [...copies.values()].map((v) => v[0]);
  (firsts.filter((s) => !inProject(s)).length > 1 ? waste : shadow).push([id, firsts]);
}
const parent = (s) => s.slice(0, s.lastIndexOf('/'));
for (const [id, firsts] of waste.slice(0, 6)) out.push(`duplicate: ${id} ×${firsts.length} (${firsts.slice(0, 2).map(parent).join(', ')}${firsts.length > 2 ? ` +${firsts.length - 2}` : ''})`);
if (waste.length > 6) out.push(`duplicate: +${waste.length - 6} more`);
if (shadow.length) out.push(`project copies shadow global ones: ${shadow.length} (${shadow.slice(0, 6).map(([id]) => id).join(', ')}${shadow.length > 6 ? ', ...' : ''})`);
const other = [...installed.keys()].filter((id) => !packOf.has(id) && !cat.retired[id]).sort();
out.push(`other skills (in no pack): ${other.length}${other.length ? ': ' + other.slice(0, 30).join(', ') + (other.length > 30 ? ` +${other.length - 30}` : '') : ''}`);

// 4. Matches for the question's words.
if (words.length) {
  const stem = (w) => w.toLowerCase().replace(/[^a-z0-9.-]/g, '').replace(/ies$/, 'y').replace(/([^s])s$/, '$1');
  const terms = [...new Set(words.flatMap((w) => w.split(/\s+/)).map(stem))].filter((w) => w.length > 2);
  const hits = [];
  for (const p of cat.packs) {
    for (const [id, desc] of p.skills) {
      const text = desc.toLowerCase();
      const score = terms.reduce((s, t) => s + (id.includes(t) ? 3 : 0) + (text.includes(t) ? 1 : 0), 0);
      if (score) hits.push({ id, desc, p, score: score + (installed.has(id) ? 0.5 : 0) });
    }
  }
  hits.sort((a, b) => b.score - a.score);
  out.push(`matches for "${terms.join(' ')}" (${hits.length}):`);
  for (const h of hits.slice(0, 8)) {
    const where = installed.has(h.id) ? `installed ${[...installed.get(h.id).values()].flat()[0]}` : 'not installed';
    out.push(`  ${h.id} [${h.p.id}] ${h.desc.slice(0, 90)} | ${where}`);
  }
  if (hits.slice(0, 8).some((h) => !installed.has(h.id))) out.push(`  install: ${INSTALL('<id>')}`);
  if (!hits.length) out.push('  none in the registry: search the web or run sigmaresearch');
}
console.log(out.join('\n'));
