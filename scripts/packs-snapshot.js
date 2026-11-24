#!/usr/bin/env node
/**
 * Maintainer script: rebuild registry/packs.json from local clones of the pack sources.
 *
 *   node scripts/packs-snapshot.js <clones-dir>
 *
 * <clones-dir> holds one shallow clone per repo, named by the repo name
 * (skills, threejs-skills, hyperframes, hyperframes-student-kit, MiniMax-H3, tstack, superpowers, impeccable,
 * security-audit-skill, anatomy, diagram-design, taste-skill, hallmark, ponytail, logo-design-skill, lieflat-charts,
 * pixel2motion, line-art-animation). The hyperframes
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
const HYPERFRAMES_RELEASE = 'v0.9.86';

// Theo Browne's tstack (MIT) is pinned to one commit. To move it, clone that commit, change this line, and re-run.
const TSTACK_COMMIT = '11e37a74d0a6868c121cd0910ab2b3bd9873b92a';

const PACKS = [
  {
    id: 'sigma',
    title: 'Sigma',
    blurb: 'Review, improve, ship, research and write. The first-party Sigma skills.',
    category: 'Engineering',
    aliases: ['sigmaskills'],
    bundled: true,
  },
  {
    id: 'mattpocock',
    title: 'Matt Pocock',
    blurb: 'Skills for real engineers: grill, spec, TDD, triage, deep modules.',
    category: 'Engineering',
    aliases: ['matt', 'pocock'],
    sources: [{ repo: 'mattpocock/skills', clone: 'matt', path: 'skills', ref: 'abeeaf95660ba9e8b7c753eb38f441ca707a8823' }],
  },
  {
    id: 'threejs',
    title: 'Three.js',
    blurb: 'Geometry, materials, lighting, shaders, loaders, post-processing, R3F.',
    category: 'Media',
    aliases: ['three'],
    sources: [{ repo: 'CloudAI-X/threejs-skills', clone: 'threejs-skills', path: 'skills', ref: '0e181866f095b5f06d005133876e926515390d95' }],
  },
  {
    id: 'hyperframes',
    title: 'HyperFrames',
    blurb: 'HTML to video: the HyperFrames skill, CLI, registry, media and slideshows, plus the student kit.',
    category: 'Media',
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
    category: 'Media',
    aliases: ['minimax', 'h3'],
    sources: [{ repo: 'MiniMax-AI/MiniMax-H3', clone: 'MiniMax-H3', path: 'skills' }],
  },
  {
    id: 'tstack',
    title: 'tstack',
    blurb: "Theo Browne's agent skills for shipping PRs: full-send, council, babysit-pr, file-pr and more.",
    category: 'Engineering',
    aliases: ['theo'],
    sources: [{ repo: 't3dotgg/tstack', clone: 'tstack', path: 'skills', ref: TSTACK_COMMIT }],
  },
  // The fastest-growing skill repos of October 2026 (#273). Each is pinned to one commit, ponytail to its release tag.
  {
    id: 'superpowers',
    title: 'Superpowers',
    blurb: "Jesse Vincent's workflow skills: brainstorm, write a plan, execute it, TDD, debug, review, finish the branch.",
    category: 'Engineering',
    aliases: ['obra'],
    sources: [{ repo: 'obra/superpowers', clone: 'superpowers', path: 'skills', ref: '22f0b463e7a5e579904dd6211a520321035526f7' }],
  },
  {
    id: 'impeccable',
    title: 'Impeccable',
    blurb: "Paul Bakaus's design vocabulary for agents: one skill with commands to audit, polish, critique and restyle a frontend.",
    category: 'Design',
    aliases: ['pbakaus'],
    sources: [{ repo: 'pbakaus/impeccable', clone: 'impeccable', path: 'plugin/skills', ref: 'b49177d32788f2dc585c42831d845dacf1ebed2c' }],
  },
  {
    id: 'security-audit',
    title: 'Security Audit',
    blurb: "Cloudflare's security audit skill: find vulnerabilities and verify each finding before it is reported.",
    category: 'Engineering',
    aliases: ['cloudflare', 'audit'],
    sources: [{ repo: 'cloudflare/security-audit-skill', clone: 'security-audit-skill', path: 'skills', ref: 'c1c8a8c1471069fb0e188eeaff69b8e8db6564a8' }],
  },
  {
    id: 'anatomy',
    title: 'Anatomy',
    blurb: 'Detailed, interactive isometric illustrations of real machines and how they work.',
    category: 'Design',
    aliases: ['isometric'],
    // The skill is the repo root itself: its SKILL.md sits at the top, so the source names the skill id.
    sources: [{ repo: 'wheresryan22/anatomy', clone: 'anatomy', path: '', rootSkill: 'anatomy', ref: '1482e8469b0a9e0d8cc18ea2740a01423d29ae80' }],
  },
  {
    id: 'diagram-design',
    title: 'Diagram Design',
    blurb: "Cathryn Lavery's editorial diagrams: architecture, flow, sequence and more as clean HTML and SVG.",
    category: 'Design',
    aliases: ['diagram', 'diagrams'],
    sources: [{ repo: 'cathrynlavery/diagram-design', clone: 'diagram-design', path: 'skills', ref: '0eeda75a708f419560d5e032693618bb9954f17b' }],
  },
  {
    id: 'taste-skill',
    title: 'Taste',
    blurb: 'Art direction for coding agents: reference images, a visual brief and a browser check, so a page does not look generated.',
    category: 'Design',
    aliases: ['taste', 'leonxlnx'],
    sources: [{ repo: 'Leonxlnx/taste-skill', clone: 'taste-skill', path: 'skills', ref: '6c0b5c78f5d31776e2210305abaa210cdc0030bf' }],
  },
  {
    id: 'hallmark',
    title: 'Hallmark',
    blurb: 'A design skill that refuses the AI look: new pages, audits, redesigns and design extraction.',
    category: 'Design',
    aliases: ['nutlope'],
    sources: [{ repo: 'Nutlope/hallmark', clone: 'hallmark', path: 'skills', ref: '04977e15f3dfd6ee4b74c887dac3eb52665d6c92' }],
  },
  {
    id: 'ponytail',
    title: 'Ponytail',
    blurb: 'The lazy senior developer: the smallest change that fully works, plus audit, review, debt and gain reports.',
    category: 'Engineering',
    aliases: ['lazy'],
    sources: [{ repo: 'DietrichGebert/ponytail', clone: 'ponytail', path: 'skills', ref: 'v5.3.3' }],
  },
  // The owner's November 2026 list (#338). Each is pinned to one commit.
  {
    id: 'anthropic-engineering',
    title: 'Anthropic Engineering',
    blurb: "Anthropic's engineering plugin as skills: architecture, code review, debugging, incidents, standups, system design, tech debt, testing.",
    category: 'Engineering',
    aliases: ['anthropic-eng'],
    sources: [{ repo: 'anthropics/knowledge-work-plugins', clone: 'knowledge-work-plugins', path: 'engineering/skills', ref: '2baf6d1eded3cd7aeff0b5c5918601a5799189b4' }],
  },
  {
    id: 'agent-skills',
    title: 'Agent Skills',
    blurb: "Addy Osmani's engineering workflow: spec, plan, build in small steps, test, review, harden and ship.",
    category: 'Engineering',
    aliases: ['addy', 'addyosmani'],
    sources: [{ repo: 'addyosmani/agent-skills', clone: 'agent-skills', path: 'skills', ref: '8c99fa36d90068c82d547f7c12a9d67a3e95f4ee' }],
  },
  {
    id: 'caveman',
    title: 'Caveman',
    blurb: 'Terse answers that keep every fact, plus lean build, patch, refactor and verify skills.',
    category: 'Engineering',
    aliases: ['cave'],
    // Only the skills that work as plain files. Left out: cavecrew (needs its plugin's sub-agents), caveman-stats
    // (needs its hook), caveman-learn (needs its CLI) and the five Caveman Cloud skills (setup, manage, optimize, discover, evidence-review).
    sources: [{
      repo: 'JuliusBrussee/caveman',
      clone: 'caveman',
      path: 'skills',
      ref: 'b89752f6bca5a26bfde8b019813554241800ca99',
      only: ['caveman', 'caveman-commit', 'caveman-compress', 'caveman-explore', 'caveman-help', 'caveman-review', 'investigate-first',
        'lean-build', 'megacave', 'migration', 'safe-refactor', 'surgical-patch', 'ultracave', 'verify-and-stop'],
    }],
  },
  {
    id: 'claude-red',
    title: 'Claude Red',
    blurb: 'Offensive security for authorized tests: web, API, cloud, Active Directory, wireless, exploit development and reports.',
    category: 'Engineering',
    aliases: ['red', 'snailsploit'],
    sources: [{ repo: 'SnailSploit/Claude-Red', clone: 'Claude-Red', path: 'Skills', ref: '6196ba7464662de34e8744d359f175d1a7bca530' }],
  },
  {
    id: 'dev-browser',
    title: 'Dev Browser',
    blurb: 'The agent drives a real Chrome through short scripts, with named pages that persist between runs.',
    category: 'Engineering',
    aliases: ['sawyerhood'],
    sources: [{ repo: 'SawyerHood/dev-browser', clone: 'dev-browser', path: 'skills', ref: '520ba5cb4fa2856a501376cd8a62fe54a6576549' }],
  },
  {
    id: 'emil-kowalski',
    title: 'Emil Kowalski',
    blurb: 'Design engineering from the maker of Sonner: animation, gestures, Apple-style design, taste and UI reviews.',
    category: 'Design',
    aliases: ['emil'],
    sources: [{ repo: 'emilkowalski/skills', clone: 'emil-skills', path: 'skills', ref: '64eb3deb9a5fbfa041faf783e0bc3fd635872e9c' }],
  },
  {
    id: 'marketingskills',
    title: 'Marketing Skills',
    blurb: "Corey Haines's marketing skills: copy, SEO, CRO, ads, email, pricing, launches, analytics and more.",
    category: 'Marketing',
    aliases: ['corey', 'coreyhaines'],
    sources: [{ repo: 'coreyhaines31/marketingskills', clone: 'marketingskills', path: 'skills', ref: '8fd2fcade2fd6629026e9dfe6d133b55b36968b9' }],
  },
  {
    id: 'linkedin',
    title: 'LinkedIn',
    blurb: 'LinkedIn posts, comments, replies, hooks, profiles and analytics, each drafted for your approval.',
    category: 'Marketing',
    aliases: ['linkedin-skills'],
    sources: [{ repo: 'sergebulaev/linkedin-skills', clone: 'linkedin-skills', path: 'skills', ref: '32083c0733e8850d3517bfe691b1e9870d37ba51' }],
  },
  {
    id: 'baoyu',
    title: 'Baoyu',
    blurb: "Baoyu's content skills: cover images, infographics, comics, slides, diagrams, translation and posting to X, WeChat and Weibo.",
    category: 'Media',
    aliases: ['baoyu-skills', 'jimliu'],
    // JimLiu/baoyu-skills is written in Chinese; this fork's `english` branch is the same skills in plain English.
    sources: [{ repo: 'Djordje-Stojanovic/baoyu-skills', clone: 'baoyu-skills', path: 'skills', ref: '5847f0ac444300bc9457122301ff6685a9011e09' }],
  },
  {
    id: 'i-have-adhd',
    title: 'I Have ADHD',
    blurb: 'Answers shaped for a reader with ADHD: next action first, numbered steps, no tangents, visible wins.',
    category: 'Productivity',
    aliases: ['adhd'],
    sources: [{ repo: 'ayghri/i-have-adhd', clone: 'i-have-adhd', path: 'skills', ref: '1ecea1993b7fce257ffbd686c070948b5e07eda6' }],
  },
  // The owner's 24 Nov list (#408): one pack per category, several one-skill repos in it, each pinned to one commit.
  {
    id: 'design-kit',
    title: 'Design Kit',
    blurb: 'Logos from brief to production files, and editorial charts, decks and reports from your data.',
    category: 'Design',
    aliases: ['logo', 'charts'],
    sources: [
      { repo: 'kaankiziltug/logo-design-skill', clone: 'logo-design-skill', path: 'skills', ref: 'e9eaddc07895575253d6663320354a708f53e955' },
      // The skill is the repo root itself, as in anatomy.
      { repo: 'larashero3-dotcom/lieflat-charts', clone: 'lieflat-charts', path: '', rootSkill: 'lieflat-charts', ref: '4b4e75bde11cbef44263de769f3705db54bbb277' },
    ],
  },
  {
    id: 'motion-kit',
    title: 'Motion Kit',
    blurb: 'A raster logo turned into a clean SVG and a logo animation; animated line-art scenes in SVG, exported to video.',
    category: 'Media',
    aliases: ['animation', 'motion'],
    sources: [
      { repo: 'nolangz/pixel2motion', clone: 'pixel2motion', path: '', rootSkill: 'pixel2motion', ref: 'e9faedb28930df0da2acf17da00c80730a78cfe8' },
      { repo: 'JDhruv14/line-art-animation', clone: 'line-art-animation', path: '', rootSkill: 'line-art-animation', ref: 'c43d698913cf0ad44f984c7ae14c5348010594d3' },
    ],
  },
  {
    id: 'local',
    title: 'Local',
    blurb: 'A folder of your own skills on this machine.',
    category: 'Productivity',
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
  const entry = { id: pack.id, title: pack.title, blurb: pack.blurb, category: pack.category, aliases: pack.aliases };
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
// First owner keeps a name (a Sigma skill first, then registry order): a later pack drops it, and the run says so.
const owners = new Map(fs.readdirSync(ROOT).filter((dir) => fs.existsSync(path.join(ROOT, dir, 'SKILL.md'))).map((id) => [id, 'sigma']));
for (const pack of out.packs) {
  for (const source of pack.sources || []) {
    if (!source.skills) continue;
    source.skills = source.skills.filter((skill) => {
      if (!owners.has(skill.id)) return owners.set(skill.id, pack.id);
      console.error(`${pack.id}: ${skill.id} dropped, ${owners.get(skill.id)} has it`);
      return false;
    });
  }
}
// The file stays plain ASCII (non-ASCII as \uXXXX), as the hand-curated packs were pasted in.
const ascii = (text) => text.replace(/[\u0080-￿]/g, (ch) => `\\u${ch.charCodeAt(0).toString(16).padStart(4, '0')}`);
fs.writeFileSync(file, `${ascii(JSON.stringify(out, null, 2))}\n`);
console.log(out.packs.map((pack) => `${pack.id}: ${(pack.sources || []).reduce((n, s) => n + (s.skills?.length || 0), 0)}`).join('\n'));
