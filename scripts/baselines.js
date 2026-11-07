import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { BASELINES_FILENAME } from '../src/adoption.js';

function git(rootDir, args, encoding = 'utf8') {
  return execFileSync('git', args, { cwd: rootDir, encoding, maxBuffer: 64 * 1024 * 1024 });
}

/**
 * Read every skill folder's regular files from a git ref, as the bytes a clone gives.
 * Two git processes per ref, however many folders it holds.
 *
 * @param {string} rootDir
 * @param {string} ref
 * @returns {Record<string, Record<string, Buffer>>} skill id to tree; folders without SKILL.md are left out
 */
export function readSkillTreesAtRef(rootDir, ref) {
  const listing = git(rootDir, ['ls-tree', '-r', '-z', ref]);
  const byFolder = {};
  for (const line of listing.split('\0').filter(Boolean)) {
    const tab = line.indexOf('\t');
    const [mode, type, object] = line.slice(0, tab).split(' ');
    const filePath = line.slice(tab + 1);
    const slash = filePath.indexOf('/');
    // Symbolic links and submodules are not regular files; the revision hash skips them too.
    if (slash < 0 || type !== 'blob' || mode === '120000') continue;
    (byFolder[filePath.slice(0, slash)] ||= []).push({ rel: filePath.slice(slash + 1), object });
  }
  // Read no blobs for folders that are not skills (src/, test/, ...).
  const entries = Object.entries(byFolder)
    .filter(([, files]) => files.some((entry) => entry.rel === 'SKILL.md'))
    .flatMap(([skillId, files]) => files.map((entry) => ({ skillId, ...entry })));
  const trees = {};
  if (entries.length === 0) return trees;
  // One git process reads every blob, in the order asked.
  const out = execFileSync('git', ['cat-file', '--batch'], {
    cwd: rootDir,
    input: entries.map((entry) => entry.object + '\n').join(''),
    maxBuffer: 256 * 1024 * 1024,
  });
  let at = 0;
  for (const { skillId, rel } of entries) {
    const eol = out.indexOf(0x0a, at);
    const size = Number(out.subarray(at, eol).toString('latin1').split(' ')[2]);
    (trees[skillId] ||= {})[rel] = Buffer.from(out.subarray(eol + 1, eol + 1 + size));
    at = eol + 1 + size + 1;
  }
  return trees;
}

/**
 * Read one skill folder's regular files from a git ref.
 *
 * @param {string} rootDir
 * @param {string} ref
 * @param {string} skillId
 * @returns {Record<string, Buffer> | null} null when the skill has no SKILL.md at that ref
 */
export function readSkillTreeAtRef(rootDir, ref, skillId) {
  return readSkillTreesAtRef(rootDir, ref)[skillId] || null;
}

/**
 * Hash a file tree exactly like computeSkillRevisionAndHashes hashes a folder on disk.
 *
 * @param {Record<string, Buffer>} tree
 * @returns {{ revision: string, files: Record<string, string> }}
 */
function hashTree(tree) {
  const folderHash = crypto.createHash('sha256');
  const files = {};
  for (const relPath of Object.keys(tree).sort()) {
    folderHash.update(relPath);
    folderHash.update('\0');
    folderHash.update(tree[relPath]);
    folderHash.update('\0');
    files[relPath] = crypto.createHash('sha256').update(tree[relPath]).digest('hex');
  }
  return { revision: folderHash.digest('hex'), files };
}

/**
 * Hash every top-level skill folder (a folder with SKILL.md) at a git ref.
 *
 * @param {string} rootDir
 * @param {string} ref
 * @returns {Record<string, { revision: string, files: Record<string, string> }>}
 */
export function hashSkillsAtRef(rootDir, ref) {
  const skills = {};
  for (const [name, tree] of Object.entries(readSkillTreesAtRef(rootDir, ref)).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))) {
    skills[name] = hashTree(tree);
  }
  return skills;
}

/**
 * Add one Release's skill hashes to registry/skill-baselines.json.
 * A Release already recorded for a skill is left as it is.
 *
 * @param {string} rootDir
 * @param {string} release
 * @param {Record<string, { revision: string, files: Record<string, string> }>} skills
 */
export function appendReleaseBaselines(rootDir, release, skills) {
  const file = path.join(rootDir, 'registry', BASELINES_FILENAME);
  const current = fs.existsSync(file)
    ? JSON.parse(fs.readFileSync(file, 'utf8'))
    : { schemaVersion: 1, skills: {} };
  for (const [skillId, hashed] of Object.entries(skills)) {
    const entries = current.skills[skillId] || [];
    if (entries.some((entry) => entry.release === release)) continue;
    current.skills[skillId] = [...entries, { release, ...hashed }];
  }
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(current, null, 2)}\n`, 'utf8');
}
