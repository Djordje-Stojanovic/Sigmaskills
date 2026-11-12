#!/usr/bin/env node
/**
 * Maintainer script: move every pack pin to the newest commit of its repository, and check it.
 *
 *   node scripts/packs-update.js [--dry-run] [--file <packs.json>]
 *
 * For each pack with a pinned git source it fetches the repository head into a temporary folder
 * (nothing is installed or cached) and checks every SKILL.md the way the installer reads one: valid
 * frontmatter with a name and a description (src/catalog.js parseSkillFrontmatter). It prints one line per pack:
 *   <pack>  <old> -> <new>  PASS (<n> skills, +<added> -<removed>)
 * A pack that fails keeps its old pin. A pack without a `ref` follows the head and is skipped.
 * A pass writes the new `ref` and the new skill list to registry/packs.json (new skills get their
 * first sentence as description), and the new ref into scripts/packs-snapshot.js, so a later
 * snapshot run does not move it back. Exit code 1 when a pack fails.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseSkillFrontmatter } from '../src/catalog.js';
import { createSourceFetcher, findSkillDirs } from '../src/pack-source.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const fileFlag = args.indexOf('--file');
const file = fileFlag === -1 ? path.join(ROOT, 'registry', 'packs.json') : path.resolve(args[fileFlag + 1]);

const short = (ref) => (/^[0-9a-f]{40}$/.test(ref) ? ref.slice(0, 7) : ref);

function describe(dir) {
  const md = fs.readFileSync(path.join(dir, 'SKILL.md'), 'utf8');
  const block = md.match(/^description:\s*[>|][-+]?\s*\r?\n((?:[ \t]+.*\r?\n?)+)/m);
  const flat = (block ? block[1] : parseSkillFrontmatter(md).description).replace(/\s+/g, ' ').trim();
  const first = flat.split(/(?<=[.!?])\s/)[0];
  return first.length > 150 ? `${first.slice(0, 147).trimEnd()}...` : first;
}

/** Check one fetched source. Returns the new skill list, or the reasons it fails. */
function checkSource(source, root) {
  const found = findSkillDirs(root);
  if (found.size === 0) return { problems: ['no SKILL.md found'] };
  const problems = [];
  for (const [id, dir] of found) {
    try {
      parseSkillFrontmatter(fs.readFileSync(path.join(dir, 'SKILL.md'), 'utf8'));
    } catch (err) {
      problems.push(`${id}: ${err.message}`);
    }
  }
  if (problems.length > 0) return { problems };
  const old = new Map((source.skills || []).map((skill) => [skill.id, skill]));
  const skills = [...found.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([id, dir]) => old.get(id) || { id, description: describe(dir) });
  return { skills, added: skills.filter((skill) => !old.has(skill.id)).length, removed: [...old.keys()].filter((id) => !found.has(id)).length };
}

const registry = JSON.parse(fs.readFileSync(file, 'utf8'));
const fetcher = createSourceFetcher();
const moves = [];
let failed = false;
try {
  // shortcut: a transform source (design-md) writes only the skills in its list, so new brands there still need a description by hand (scripts/pack-list.js).
  const heads = (pack) => pack.sources.map(({ ref, ...rest }) => rest);
  const packs = registry.packs.filter((pack) => (pack.sources || []).some((source) => source.type === 'git'));
  await fetcher.warm(packs.filter((pack) => pack.sources.every((source) => source.ref)).flatMap(heads));
  for (const pack of packs) {
    const label = pack.id.padEnd(20);
    if (!pack.sources.every((source) => source.ref)) {
      console.log(`${label}unpinned (follows head)  skipped`);
      continue;
    }
    const checked = [];
    const problems = [];
    for (const [index, head] of heads(pack).entries()) {
      try {
        const { root, revision } = fetcher.fetch(head);
        const result = checkSource(pack.sources[index], root);
        checked.push({ source: pack.sources[index], revision, ...result });
        problems.push(...(result.problems || []).map((text) => `${head.repo}: ${text}`));
      } catch (err) {
        problems.push(err.message);
      }
    }
    const olds = pack.sources.map((source) => short(source.ref)).join(', ');
    if (problems.length > 0) {
      failed = true;
      const more = problems.length > 3 ? ` (+${problems.length - 3} more)` : '';
      console.log(`${label}${olds} kept  FAIL: ${problems.slice(0, 3).join('; ')}${more}`);
      continue;
    }
    const total = checked.reduce((sum, item) => sum + item.skills.length, 0);
    const added = checked.reduce((sum, item) => sum + item.added, 0);
    const removed = checked.reduce((sum, item) => sum + item.removed, 0);
    const moved = checked.filter((item) => item.revision !== item.source.ref);
    if (moved.length === 0) {
      console.log(`${label}${olds} unchanged  PASS (${total} skills)`);
      continue;
    }
    console.log(`${label}${olds} -> ${checked.map((item) => short(item.revision)).join(', ')}  PASS (${total} skills, +${added} -${removed})`);
    moves.push(...moved);
  }
} finally {
  fetcher.close();
}

if (moves.length > 0 && !dryRun) {
  const ascii = (text) => text.replace(/[\u0080-￿]/g, (ch) => `\\u${ch.charCodeAt(0).toString(16).padStart(4, '0')}`);
  const snapshot = path.join(ROOT, 'scripts', 'packs-snapshot.js');
  let snapshotText = fileFlag === -1 ? fs.readFileSync(snapshot, 'utf8') : '';
  for (const { source, revision, skills } of moves) {
    // The same source object sits in registry.packs, so this edits the file's data in place.
    snapshotText = snapshotText.replaceAll(source.ref, revision);
    source.ref = revision;
    source.skills = skills;
  }
  fs.writeFileSync(file, `${ascii(JSON.stringify(registry, null, 2))}\n`);
  if (fileFlag === -1) fs.writeFileSync(snapshot, snapshotText);
}
process.exit(failed ? 1 : 0);
