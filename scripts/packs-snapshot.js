#!/usr/bin/env node
/**
 * Maintainer script: rebuild registry/packs.json from local clones of the pack sources.
 *
 *   node scripts/packs-snapshot.js <clones-dir>
 *
 * <clones-dir> holds one shallow clone per repo, named by the repo name
 * (skills, threejs-skills, hyperframes, hyperframes-student-kit, MiniMax-H3). The hyperframes
 * clone must be at the tag named in HYPERFRAMES_RELEASE: `git clone --branch <tag> --depth 1`.
 * The snapshot lets the installer show every group at once, without cloning.
 * Packs this script does not list are kept as they are.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseSkillFrontmatter } from '../src/catalog.js';
import { findSkillDirs } from '../src/pack-source.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// The HyperFrames skills change shape often (14 were folded into `hyperframes` at once). The pack
// is pinned to one release tag; to move it, clone that tag, change this line, and re-run.
const HYPERFRAMES_RELEASE = 'v0.8.188';

const PACKS = [
  {
    id: 'sigma',
    title: 'Sigma',
    blurb: 'Review, improve, ship, research and write. The first-party Sigma skills.',
    aliases: ['sigmaskills'],
    bundled: true,
  },
  {
    id: 'mattpocock',
    title: 'Matt Pocock',
    blurb: 'Skills for real engineers: grill, spec, TDD, triage, deep modules.',
    aliases: ['matt', 'pocock'],
    sources: [{ repo: 'mattpocock/skills', clone: 'matt', path: 'skills' }],
  },
  {
    id: 'threejs',
    title: 'Three.js',
    blurb: 'Geometry, materials, lighting, shaders, loaders, post-processing, R3F.',
    aliases: ['three'],
    sources: [{ repo: 'CloudAI-X/threejs-skills', clone: 'threejs-skills', path: 'skills' }],
  },
  {
    id: 'hyperframes',
    title: 'HyperFrames',
    blurb: 'HTML to video: the HyperFrames skill, CLI, registry, media and slideshows, plus the student kit.',
    aliases: ['hf'],
    sources: [
      { repo: 'heygen-com/hyperframes', clone: 'hyperframes', path: 'skills', ref: HYPERFRAMES_RELEASE },
      {
        repo: 'nateherkai/hyperframes-student-kit',
        clone: 'hyperframes-student-kit',
        path: '.agents/skills',
        only: ['cut-mistakes', 'cut-silences', 'edit-video', 'gsap', 'hyperframes-video-beats', 'make-a-video',
          'motion-showreel', 'short-form-edit', 'style-library', 'video-storytelling', 'website-to-hyperframes'],
      },
    ],
  },
  {
    id: 'minimax-h3',
    title: 'MiniMax H3',
    blurb: 'Prompt writing and eight video recipes for the MiniMax H3 model.',
    aliases: ['minimax', 'h3'],
    sources: [{ repo: 'MiniMax-AI/MiniMax-H3', clone: 'MiniMax-H3', path: 'skills' }],
  },
  {
    id: 'local',
    title: 'Local',
    blurb: 'A folder of your own skills on this machine.',
    aliases: ['own'],
    sources: [{ type: 'dir', env: 'SIGMA_LOCAL_SKILLS_DIR' }],
  },
];

function shortDescription(text) {
  const flat = String(text).replace(/\s+/g, ' ').trim();
  const first = flat.split(/(?<=[.!?])\s/)[0];
  return (first.length > 150 ? `${first.slice(0, 147).trimEnd()}...` : first);
}

function readDescription(dir) {
  const md = fs.readFileSync(path.join(dir, 'SKILL.md'), 'utf8');
  try {
    return parseSkillFrontmatter(md).description;
  } catch {
    const folded = md.match(/^description:\s*[>|][-+]?\s*\r?\n((?:[ \t]+.*\r?\n?)+)/m);
    return folded ? folded[1] : '';
  }
}

const clones = process.argv[2];
if (!clones) {
  console.error('usage: node scripts/packs-snapshot.js <clones-dir>');
  process.exit(1);
}

const out = { schemaVersion: 1, generatedBy: 'scripts/packs-snapshot.js', packs: [] };
for (const pack of PACKS) {
  const entry = { id: pack.id, title: pack.title, blurb: pack.blurb, aliases: pack.aliases };
  if (pack.bundled) {
    entry.bundled = true;
  } else {
    entry.sources = [];
    for (const source of pack.sources) {
      if (source.type === 'dir') {
        entry.sources.push({ type: 'dir', env: source.env, prefix: source.prefix });
        continue;
      }
      const root = path.join(clones, source.clone);
      const found = findSkillDirs(path.join(root, source.path));
      const skills = [...found.entries()]
        .filter(([id]) => !source.only || source.only.includes(id))
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([id, dir]) => ({ id, description: shortDescription(readDescription(dir)) }));
      entry.sources.push({ type: 'git', repo: source.repo, path: source.path, ...(source.ref ? { ref: source.ref } : {}), skills });
    }
  }
  out.packs.push(entry);
}
// Four packs are curated by hand and pinned by commit or tag: Anthropic, Design.md, last30days and
// Financial Services (their skill lists come from scripts/pack-list.js). Keep them as they are, in place.
const file = path.join(ROOT, 'registry', 'packs.json');
const before = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')).packs : [];
const fresh = new Map(out.packs.map((pack) => [pack.id, pack]));
const merged = before.map((pack) => fresh.get(pack.id) || pack);
for (const pack of out.packs) if (!merged.some((entry) => entry.id === pack.id)) merged.splice(Math.max(merged.length - 1, 0), 0, pack);
out.packs = merged;
fs.writeFileSync(file, `${JSON.stringify(out, null, 2)}\n`);
console.log(out.packs.map((pack) => `${pack.id}: ${(pack.sources || []).reduce((n, s) => n + (s.skills?.length || 0), 0)}`).join('\n'));
