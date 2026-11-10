#!/usr/bin/env node
/**
 * Maintainer script: rebuild registry/packs.json from local clones of the pack sources.
 *
 *   node scripts/packs-snapshot.js <clones-dir>
 *
 * <clones-dir> holds one shallow clone per repo, named by the repo name
 * (skills, threejs-skills, hyperframes, hyperframes-student-kit, MiniMax-H3, tstack, superpowers, impeccable,
 * security-audit-skill, anatomy, diagram-design, taste-skill, hallmark, ponytail). The hyperframes
 * clone must be at the tag named in HYPERFRAMES_RELEASE: `git clone --branch <tag> --depth 1`. A pack with
 * a `ref` must be cloned at that commit or tag.
 * The snapshot lets the installer show every group at once, without cloning.
 * Packs this script does not list are kept as they are. So is a pack whose clone is not in <clones-dir>:
 * to refresh one pack, clone only that one.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseSkillFrontmatter } from '../src/catalog.js';
import { findSkillDirs } from '../src/pack-source.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// The HyperFrames skills change shape often (14 were folded into `hyperframes` at once). The pack
// is pinned to one release tag; to move it, clone that tag, change this line, and re-run.
const HYPERFRAMES_RELEASE = 'v0.9.30';

// Theo Browne's tstack (MIT) is pinned to one commit. To move it, clone that commit, change this line, and re-run.
const TSTACK_COMMIT = '1085050f3baed1ac724caa4a8166145fb2ac88af';

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
    sources: [{ repo: 'mattpocock/skills', clone: 'matt', path: 'skills', ref: '4ae2317ddb22b046e26455e4f9c9b3aaaf62212d' }],
  },
  {
    id: 'threejs',
    title: 'Three.js',
    blurb: 'Geometry, materials, lighting, shaders, loaders, post-processing, R3F.',
    aliases: ['three'],
    sources: [{ repo: 'CloudAI-X/threejs-skills', clone: 'threejs-skills', path: 'skills', ref: '0e181866f095b5f06d005133876e926515390d95' }],
  },
  // Blender: 8 `blender-*` skills from ra100 and 94 specialist skills from arjun988, each pinned to one commit (#285 follow-up, 2026-11-10).
  {
    id: 'blender',
    title: 'Blender',
    blurb: 'Drive Blender 5 from code: modeling, rigging, shaders, physics, rendering, camera, lighting, VFX, styles and game export.',
    aliases: ['blender3d'],
    sources: [
      { repo: 'ra100/blender-claude-plugin', clone: 'blender-claude-plugin', path: 'skills', ref: '78e9151fdc9e01ce37f1d16a9b677c3047411885' },
      { repo: 'arjun988/blender-skills', clone: 'blender-skills', path: '.claude/skills', ref: '904f095d8f36a6e72adaebb08d07f884a074743d' },
    ],
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
        ref: '10511e5af86fc47756ea89803b397422e2d89284',
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
    id: 'tstack',
    title: 'tstack',
    blurb: "Theo Browne's agent skills for shipping PRs: full-send, council, babysit-pr, file-pr and more.",
    aliases: ['theo'],
    sources: [{ repo: 't3dotgg/tstack', clone: 'tstack', path: 'skills', ref: TSTACK_COMMIT }],
  },
  // The fastest-growing skill repos of October 2026 (#273). Each is pinned to one commit, ponytail to its release tag.
  {
    id: 'superpowers',
    title: 'Superpowers',
    blurb: "Jesse Vincent's workflow skills: brainstorm, write a plan, execute it, TDD, debug, review, finish the branch.",
    aliases: ['obra'],
    sources: [{ repo: 'obra/superpowers', clone: 'superpowers', path: 'skills', ref: '22f0b463e7a5e579904dd6211a520321035526f7' }],
  },
  {
    id: 'impeccable',
    title: 'Impeccable',
    blurb: "Paul Bakaus's design vocabulary for agents: one skill with commands to audit, polish, critique and restyle a frontend.",
    aliases: ['pbakaus'],
    sources: [{ repo: 'pbakaus/impeccable', clone: 'impeccable', path: 'plugin/skills', ref: 'ec229b48547f24685ffb22aa51c462c5ae27908c' }],
  },
  {
    id: 'security-audit',
    title: 'Security Audit',
    blurb: "Cloudflare's security audit skill: find vulnerabilities and verify each finding before it is reported.",
    aliases: ['cloudflare', 'audit'],
    sources: [{ repo: 'cloudflare/security-audit-skill', clone: 'security-audit-skill', path: 'skills', ref: 'c1c8a8c1471069fb0e188eeaff69b8e8db6564a8' }],
  },
  {
    id: 'anatomy',
    title: 'Anatomy',
    blurb: 'Detailed, interactive isometric illustrations of real machines and how they work.',
    aliases: ['isometric'],
    // The skill is the repo root itself: its SKILL.md sits at the top, so the source names the skill id.
    sources: [{ repo: 'wheresryan22/anatomy', clone: 'anatomy', path: '', rootSkill: 'anatomy', ref: '1482e8469b0a9e0d8cc18ea2740a01423d29ae80' }],
  },
  {
    id: 'diagram-design',
    title: 'Diagram Design',
    blurb: "Cathryn Lavery's editorial diagrams: architecture, flow, sequence and more as clean HTML and SVG.",
    aliases: ['diagram', 'diagrams'],
    sources: [{ repo: 'cathrynlavery/diagram-design', clone: 'diagram-design', path: 'skills', ref: 'f2496acbde9f45ccb55c24d4f75210c8a1355df8' }],
  },
  {
    id: 'taste-skill',
    title: 'Taste',
    blurb: 'Art direction for coding agents: reference images, a visual brief and a browser check, so a page does not look generated.',
    aliases: ['taste', 'leonxlnx'],
    sources: [{ repo: 'Leonxlnx/taste-skill', clone: 'taste-skill', path: 'skills', ref: 'f6b76575f949707b4e3c37cd86cb44b0b98643e8' }],
  },
  {
    id: 'hallmark',
    title: 'Hallmark',
    blurb: 'A design skill that refuses the AI look: new pages, audits, redesigns and design extraction.',
    aliases: ['nutlope'],
    sources: [{ repo: 'Nutlope/hallmark', clone: 'hallmark', path: 'skills', ref: '407fa689f4a276f2fd389208d271d0fef08f5058' }],
  },
  {
    id: 'ponytail',
    title: 'Ponytail',
    blurb: 'The lazy senior developer: the smallest change that fully works, plus audit, review, debt and gain reports.',
    aliases: ['lazy'],
    sources: [{ repo: 'DietrichGebert/ponytail', clone: 'ponytail', path: 'skills', ref: 'v5.3.3' }],
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
  // parseSkillFrontmatter reads `description: >-` as the bare marker, so a folded or literal block is read here first.
  const block = md.match(/^description:\s*[>|][-+]?\s*\r?\n((?:[ \t]+.*\r?\n?)+)/m);
  if (block) return block[1];
  try {
    return parseSkillFrontmatter(md).description;
  } catch {
    return '';
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
      if (!fs.existsSync(root)) {
        entry.missing = source.clone;
        break;
      }
      const found = source.rootSkill ? new Map([[source.rootSkill, root]]) : findSkillDirs(path.join(root, source.path));
      const skills = [...found.entries()]
        .filter(([id]) => !source.only || source.only.includes(id))
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([id, dir]) => ({ id, description: shortDescription(readDescription(dir)) }));
      entry.sources.push({
        type: 'git', repo: source.repo, path: source.path, ...(source.rootSkill ? { rootSkill: source.rootSkill } : {}), ...(source.ref ? { ref: source.ref } : {}), skills,
      });
    }
  }
  if (entry.missing) {
    console.error(`${pack.id}: no clone named ${entry.missing}; the pack is kept as it is`);
    continue;
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
// The file stays plain ASCII (non-ASCII as \uXXXX), as the hand-curated packs were pasted in.
const ascii = (text) => text.replace(/[\u0080-￿]/g, (ch) => `\\u${ch.charCodeAt(0).toString(16).padStart(4, '0')}`);
fs.writeFileSync(file, `${ascii(JSON.stringify(out, null, 2))}\n`);
console.log(out.packs.map((pack) => `${pack.id}: ${(pack.sources || []).reduce((n, s) => n + (s.skills?.length || 0), 0)}`).join('\n'));
