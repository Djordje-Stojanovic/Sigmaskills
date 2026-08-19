import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateCustomizationBlock, escapeRegExp } from './customization.js';
import { computeSkillRevisionAndHashes } from './revision.js';

/**
 * Locate repository / package root from a starting directory.
 *
 * @param {string} [startDir]
 * @returns {string}
 */
export function findPackageRoot(startDir) {
  let current = startDir || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  while (current && current !== path.dirname(current)) {
    if (fs.existsSync(path.join(current, 'package.json')) && fs.existsSync(path.join(current, 'manifest.json'))) {
      return current;
    }
    current = path.dirname(current);
  }
  return startDir || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
}

/**
 * Load and parse manifest.json from a directory.
 *
 * @param {string} rootDir
 * @returns {object}
 */
export function loadManifest(rootDir) {
  const manifestPath = path.join(rootDir, 'manifest.json');
  if (!fs.existsSync(manifestPath)) {
    throw new Error(`missing manifest.json at ${manifestPath}`);
  }
  try {
    const raw = fs.readFileSync(manifestPath, 'utf8');
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`failed to parse manifest.json: ${err.message}`);
  }
}

/**
 * Validate manifest schema.
 *
 * @param {object} manifest
 * @returns {boolean}
 */
export function validateManifest(manifest) {
  if (!manifest || typeof manifest !== 'object') {
    throw new Error('invalid manifest: expected JSON object');
  }
  if (!manifest.schemaVersion || typeof manifest.schemaVersion !== 'number') {
    throw new Error('invalid manifest: missing schemaVersion number');
  }
  if (!manifest.name || typeof manifest.name !== 'string') {
    throw new Error('invalid manifest: missing name string');
  }
  if (!manifest.version || typeof manifest.version !== 'string') {
    throw new Error('invalid manifest: missing version string');
  }
  if (!Array.isArray(manifest.skills) || manifest.skills.length === 0) {
    throw new Error('invalid manifest: missing skills array');
  }

  for (const skill of manifest.skills) {
    if (!skill.id || typeof skill.id !== 'string') {
      throw new Error('invalid manifest skill: missing id');
    }
    if (!skill.title || typeof skill.title !== 'string') {
      throw new Error(`invalid manifest skill ${skill.id}: missing title`);
    }
  }

  return true;
}

/**
 * Parse frontmatter and body from a SKILL.md content string.
 *
 * @param {string} md
 * @returns {{ name: string, description: string, rawFrontmatter: string, body: string }}
 */
export function parseSkillFrontmatter(md) {
  const match = md.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) {
    throw new Error('SKILL.md must start with YAML frontmatter delimited by ---');
  }
  const rawFrontmatter = match[1];
  const body = match[2];
  const name = rawFrontmatter.match(/^name:\s*(.+)\s*$/m)?.[1]?.trim();
  const description = rawFrontmatter.match(/^description:\s*(.+)\s*$/m)?.[1]?.trim();

  if (!name) {
    throw new Error('frontmatter must include name');
  }
  if (!description) {
    throw new Error('frontmatter must include description');
  }

  return { name, description, rawFrontmatter, body };
}

/**
 * Validate an individual skill folder against its metadata and repo standards.
 *
 * @param {string} skillDir
 * @param {object} skillMetadata
 * @returns {object} Validated skill detail with revision and file hashes
 */
export function validateSkill(skillDir, skillMetadata) {
  if (!fs.existsSync(skillDir)) {
    throw new Error(`skill directory does not exist: ${skillDir}`);
  }

  const skillMdPath = path.join(skillDir, 'SKILL.md');
  if (!fs.existsSync(skillMdPath)) {
    throw new Error(`skill ${skillMetadata.id}: missing SKILL.md at ${skillMdPath}`);
  }

  const skillMdContent = fs.readFileSync(skillMdPath, 'utf8');
  const { name, description, body } = parseSkillFrontmatter(skillMdContent);

  if (name !== skillMetadata.id) {
    throw new Error(
      `skill ${skillMetadata.id}: frontmatter name '${name}' does not match skill id '${skillMetadata.id}'`,
    );
  }

  const titleRegex = new RegExp(`^# ${escapeRegExp(skillMetadata.title)}\\s*$`, 'm');
  if (!titleRegex.test(body)) {
    throw new Error(
      `skill ${skillMetadata.id}: SKILL.md body missing expected title header '# ${skillMetadata.title}'`,
    );
  }

  // Validate customization block
  validateCustomizationBlock(skillMdContent, skillMetadata.id);

  // Validate agents/openai.yaml
  const yamlPath = path.join(skillDir, 'agents', 'openai.yaml');
  if (!fs.existsSync(yamlPath)) {
    throw new Error(`skill ${skillMetadata.id}: missing agents/openai.yaml at ${yamlPath}`);
  }
  const yamlContent = fs.readFileSync(yamlPath, 'utf8');
  if (!yamlContent.includes(`display_name: ${skillMetadata.title}`)) {
    throw new Error(
      `skill ${skillMetadata.id}: agents/openai.yaml missing display_name '${skillMetadata.title}'`,
    );
  }
  if (!yamlContent.includes(`$${skillMetadata.id}`)) {
    throw new Error(
      `skill ${skillMetadata.id}: agents/openai.yaml default_prompt must reference '$${skillMetadata.id}'`,
    );
  }

  // Validate references directory if required
  if (skillMetadata.needsReferences) {
    const refDir = path.join(skillDir, 'references');
    if (!fs.existsSync(refDir)) {
      throw new Error(`skill ${skillMetadata.id}: missing required references/ directory`);
    }
    const refFiles = fs.readdirSync(refDir).filter((f) => f.endsWith('.md'));
    if (refFiles.length === 0) {
      throw new Error(`skill ${skillMetadata.id}: references/ directory must contain at least one .md file`);
    }
  }

  const { revision, files } = computeSkillRevisionAndHashes(skillDir);

  return {
    id: skillMetadata.id,
    title: skillMetadata.title,
    description,
    needsReferences: Boolean(skillMetadata.needsReferences),
    revision,
    files,
  };
}

/**
 * Validate all skills in a skill pack against a manifest.
 *
 * @param {string} rootDir
 * @param {object} manifest
 * @returns {object[]}
 */
export function validateSkillPack(rootDir, manifest) {
  validateManifest(manifest);
  const validatedSkills = [];

  for (const skillMetadata of manifest.skills) {
    const skillDir = path.join(rootDir, skillMetadata.id);
    const validated = validateSkill(skillDir, skillMetadata);
    validatedSkills.push(validated);
  }

  return validatedSkills;
}

/**
 * Load manifest, validate all skills, and produce full verified catalog.
 *
 * @param {string} [rootDir]
 * @returns {{ manifest: object, skills: object[] }}
 */
export function getCatalog(rootDir = findPackageRoot()) {
  const manifest = loadManifest(rootDir);
  const skills = validateSkillPack(rootDir, manifest);
  return { manifest, skills };
}
