import fs from 'node:fs';
import path from 'node:path';
import { parseSkillFrontmatter } from './catalog.js';
import { findSkillDirs } from './pack-source.js';

const USER_CONFIG_DIR = '.sigmaskills';
const USER_CONFIG_FILE = 'packs.json';

/**
 * The owner's own config: `~/.sigmaskills/packs.json`.
 *   { "dirs": { "<pack id>": "<folder>" }, "packs": [ <full pack definitions> ] }
 * `dirs` points a folder source (such as the Local pack) at a folder on this machine.
 * `packs` adds whole packs. Both are optional, and a missing file is fine.
 */
export function userConfigPath(homeDir) {
  return path.join(homeDir, USER_CONFIG_DIR, USER_CONFIG_FILE);
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw new Error(`could not read ${file}: ${err.message}`);
  }
}

function firstSentence(text) {
  const flat = String(text || '').replace(/\s+/g, ' ').trim();
  const first = flat.split(/(?<=[.!?])\s/)[0];
  return first.length > 150 ? `${first.slice(0, 147).trimEnd()}...` : first;
}

function discoverFolderSkills(source, env, dirs, packId) {
  const dir = dirs[packId] || source.path || (source.env ? env[source.env] : '');
  if (!dir) return { skills: [], note: source.env ? `set ${source.env} or add "dirs" to ~/.sigmaskills/packs.json` : 'no folder set' };
  if (!fs.existsSync(dir)) return { skills: [], note: `folder not found: ${dir}` };
  const skills = [];
  for (const [id, skillDir] of findSkillDirs(dir)) {
    if (source.prefix && !id.startsWith(source.prefix)) continue;
    let description = '';
    try {
      description = parseSkillFrontmatter(fs.readFileSync(path.join(skillDir, 'SKILL.md'), 'utf8')).description;
    } catch { /* A skill with odd frontmatter still installs; it just has no blurb. */ }
    skills.push({ id, description: firstSentence(description) });
  }
  skills.sort((a, b) => a.id.localeCompare(b.id));
  return { skills, dir };
}

/**
 * Every pack the installer knows: the bundled Sigma skills, the snapshot packs from
 * registry/packs.json, and the owner's own packs from the user config.
 *
 * A pack is `{ id, title, blurb, aliases, bundled, available, note, sources, skills }`.
 * Each skill is `{ id, title, description, pack, kind, source }`. `kind` is `bundled` or
 * `external`; `source` is the source object an external skill is fetched from.
 *
 * @param {object} params
 * @param {object} params.catalog bundled catalog from getCatalog()
 * @param {string} params.packageRoot
 * @param {string} params.homeDir
 * @param {NodeJS.ProcessEnv} [params.env]
 * @returns {{ packs: object[], skills: Map<string, object> }}
 */
export function loadPackCatalog({ catalog, packageRoot, homeDir, env = process.env }) {
  const registry = readJson(path.join(packageRoot, 'registry', 'packs.json')) || { packs: [] };
  const user = (homeDir && readJson(userConfigPath(homeDir))) || {};
  const dirs = user.dirs || {};
  const definitions = [...registry.packs, ...(Array.isArray(user.packs) ? user.packs : [])];

  const packs = [];
  const bySkill = new Map();
  for (const def of definitions) {
    const pack = {
      id: def.id,
      title: def.title || def.id,
      blurb: def.blurb || '',
      aliases: def.aliases || [],
      bundled: Boolean(def.bundled),
      available: true,
      note: '',
      sources: def.sources || [],
      skills: [],
    };
    if (def.bundled) {
      pack.skills = catalog.skills.map((skill) => ({
        id: skill.id,
        title: skill.title,
        description: skill.shortDescription || skill.description,
        pack: pack.id,
        kind: 'bundled',
        source: null,
      }));
    } else {
      for (const source of pack.sources) {
        if (source.type === 'dir') {
          const found = discoverFolderSkills(source, env, dirs, pack.id);
          if (found.dir) source.path = found.dir;
          if (found.skills.length === 0) {
            pack.available = false;
            pack.note = found.note || 'no skills found';
          }
          for (const skill of found.skills) {
            pack.skills.push({ id: skill.id, title: skill.id, description: skill.description, pack: pack.id, kind: 'external', source });
          }
        } else {
          for (const skill of source.skills || []) {
            pack.skills.push({ id: skill.id, title: skill.id, description: skill.description || '', pack: pack.id, kind: 'external', source });
          }
        }
      }
    }
    for (const skill of pack.skills) if (!bySkill.has(skill.id)) bySkill.set(skill.id, skill);
    packs.push(pack);
  }
  return { packs, skills: bySkill };
}

/** Find a pack by id or alias, case-insensitive. */
export function findPack(packCatalog, name) {
  const needle = String(name).trim().toLowerCase();
  return packCatalog.packs.find((pack) => pack.id === needle || pack.aliases.includes(needle)) || null;
}

/**
 * Turn `--preset` names and skill ids into one install list.
 *
 * `all` means every available pack. A preset that names no pack, or a pack with nothing
 * available on this machine, is reported instead of skipped silently.
 *
 * @param {{ packs: object[], skills: Map<string, object> }} packCatalog
 * @param {{ presets?: string[], skillIds?: string[] }} request
 * @returns {{ skills: object[], unknownPresets: string[], unavailable: object[], unknownSkills: string[] }}
 */
export function resolveSelection(packCatalog, { presets = [], skillIds = [] }) {
  const chosen = new Map();
  const unknownPresets = [];
  const unavailable = [];
  const unknownSkills = [];
  const add = (skill) => {
    if (!chosen.has(skill.id)) chosen.set(skill.id, skill);
  };
  for (const raw of presets.flatMap((value) => String(value).split(','))) {
    const name = raw.trim().toLowerCase();
    if (!name) continue;
    if (name === 'all') {
      for (const pack of packCatalog.packs) {
        if (pack.available) pack.skills.forEach(add);
      }
      continue;
    }
    const pack = findPack(packCatalog, name);
    if (!pack) unknownPresets.push(raw.trim());
    else if (!pack.available) unavailable.push(pack);
    else pack.skills.forEach(add);
  }
  for (const id of skillIds) {
    const skill = packCatalog.skills.get(id);
    if (skill) add(skill);
    else unknownSkills.push(id);
  }
  return { skills: [...chosen.values()], unknownPresets, unavailable, unknownSkills };
}
