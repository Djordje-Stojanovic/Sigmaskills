#!/usr/bin/env node
/**
 * Maintainer script: rebuild sigmaask/references/catalog.json from the installer's own data
 * (manifest.json, registry/packs.json, registry/agent-hosts.json).
 *
 *   node scripts/sigmaask-catalog.js          write the file
 *   node scripts/sigmaask-catalog.js --check  exit 1 when the file is stale
 *
 * test/sigmaask.test.js fails when the file drifts from the registry.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { getCatalog } from '../src/catalog.js';
import { loadPackCatalog } from '../src/packs.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const CATALOG_PATH = path.join(ROOT, 'sigmaask', 'references', 'catalog.json');

// A global skills folder as [base, ...segments]; sigmaask/scripts/ask.js resolves the base.
function globalDir(dest) {
  if (dest.kind === 'conditional') return globalDir(dest.cases[dest.cases.length - 1].formula);
  if (dest.kind !== 'join') return null;
  return [dest.base === 'homeDir' ? 'home' : dest.base, ...dest.segments];
}

export function buildCatalog(root = ROOT) {
  const catalog = getCatalog(root);
  const { packs } = loadPackCatalog({ catalog, packageRoot: root });
  const hosts = JSON.parse(fs.readFileSync(path.join(root, 'registry', 'agent-hosts.json'), 'utf8')).hosts;
  const retired = catalog.manifest.retired || [];
  const replacedBy = catalog.manifest.replacedBy || {};
  const unmapped = retired.filter((id) => !replacedBy[id]);
  if (unmapped.length) throw new Error(`manifest.json replacedBy has no entry for: ${unmapped.join(', ')}`);
  return {
    generatedBy: 'scripts/sigmaask-catalog.js',
    release: catalog.manifest.version,
    retired: Object.fromEntries(retired.map((id) => [id, replacedBy[id]])),
    packs: packs
      .filter((pack) => pack.skills.length > 0)
      .map((pack) => ({
        id: pack.id,
        title: pack.title,
        blurb: pack.blurb,
        // Pinned commit per source repo; the scan compares it with the installed revision.
        refs: Object.fromEntries(pack.sources.filter((s) => s.repo && /^[0-9a-f]{40}$/.test(s.ref || '')).map((s) => [s.repo, s.ref])),
        // Where to read a SKILL.md that is not installed: "repo@ref/path"; a skill's third field picks a later source.
        sources: pack.bundled ? ['Djordje-Stojanovic/Sigmaskills@main/'] : pack.sources.map((s) => `${s.repo}@${s.ref || 'HEAD'}/${s.path || ''}`),
        skills: pack.skills.map((skill) => {
          const i = pack.sources.indexOf(skill.source);
          // The scan prints 90 characters and SigmaAsk reads the SKILL.md before it recommends, so 100 carry the match words.
          const text = skill.description || '';
          const desc = text.length > 100 ? text.slice(0, 100).replace(/\s+\S*$/, '') : text;
          return i > 0 ? [skill.id, desc, i] : [skill.id, desc];
        }),
      })),
    hosts: hosts.map((host) => ({
      id: host.id,
      name: host.displayName,
      global: globalDir(host.destinations.global),
      project: host.destinations.project?.path || null,
    })),
  };
}

// One line per skill and per host: a script reads the file, and one line per entry keeps the diff readable.
export function renderCatalog({ packs, hosts, ...head }) {
  const line = (value) => JSON.stringify(value);
  const pack = ({ skills, ...rest }) => `  ${line(rest).slice(0, -1)},"skills":[\n${skills.map((skill) => `   ${line(skill)}`).join(',\n')}\n  ]}`;
  return `${line(head).slice(0, -1)},"packs":[\n${packs.map(pack).join(',\n')}\n ],"hosts":[\n${hosts.map((host) => `  ${line(host)}`).join(',\n')}\n ]}\n`;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const next = renderCatalog(buildCatalog());
  if (process.argv.includes('--check')) {
    const now = fs.existsSync(CATALOG_PATH) ? fs.readFileSync(CATALOG_PATH, 'utf8') : '';
    if (now !== next) {
      console.error('sigmaask/references/catalog.json is stale: run node scripts/sigmaask-catalog.js');
      process.exit(1);
    }
    console.log('sigmaask catalog is current');
  } else {
    fs.writeFileSync(CATALOG_PATH, next);
    console.log(`wrote ${path.relative(ROOT, CATALOG_PATH)}`);
  }
}
