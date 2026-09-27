import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { BASELINES_FILENAME } from './adoption.js';

function git(rootDir, args, encoding = 'utf8') {
  return execFileSync('git', args, { cwd: rootDir, encoding, maxBuffer: 64 * 1024 * 1024 });
}

/**
 * Read one skill folder's regular files from a git ref, as the bytes a clone gives.
 *
 * @param {string} rootDir
 * @param {string} ref
 * @param {string} skillId
 * @returns {Record<string, Buffer> | null} null when the skill has no SKILL.md at that ref
 */
export function readSkillTreeAtRef(rootDir, ref, skillId) {
  const listing = git(rootDir, ['ls-tree', '-r', '-z', ref, '--', `${skillId}/`]);
  const entries = [];
  for (const line of listing.split('\0').filter(Boolean)) {
    const tab = line.indexOf('\t');
    const [mode, type, object] = line.slice(0, tab).split(' ');
    // Symbolic links and submodules are not regular files; the revision hash skips them too.
    if (type !== 'blob' || mode === '120000') continue;
    entries.push({ rel: line.slice(tab + 1).slice(skillId.length + 1), object });
  }
  // Read no blobs for folders that are not skills (src/, test/, ...).
  if (!entries.some((entry) => entry.rel === 'SKILL.md')) return null;
  const tree = {};
  for (const { rel, object } of entries) {
    tree[rel] = git(rootDir, ['cat-file', 'blob', object], 'buffer');
  }
  return tree;
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
  const names = git(rootDir, ['ls-tree', '-d', '--name-only', ref]).split(/\r?\n/).filter(Boolean);
  const skills = {};
  for (const name of names.sort()) {
    const tree = readSkillTreeAtRef(rootDir, ref, name);
    if (tree) skills[name] = hashTree(tree);
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
