import fs from 'node:fs';
import path from 'node:path';

/**
 * Some sources are not skill folders yet. A transform reads the fetched repository and writes
 * real skill folders (one `SKILL.md` each) into `outDir`, where the pack installer finds them.
 *
 *   design-md           VoltAgent/awesome-design-md: each `<brand>/DESIGN.md` becomes a skill
 *   financial-services  anthropics/financial-services: plugin skills, agents and commands become skills
 *
 * `buildTransform(kind, params)` returns `[{ id, description, group }]` for what it wrote.
 * Params: `repoRoot` (the checkout), `sourcePath` (the source `path`), `outDir`, `revision`,
 * `repo` (for the source line) and `skills` (the registry list: `{ id, description }`).
 */

const TRANSFORMS = {
  'design-md': designMd,
  'financial-services': financialServices,
};

export function buildTransform(kind, params) {
  const transform = TRANSFORMS[kind];
  if (!transform) throw new Error(`unknown transform '${kind}'`);
  fs.mkdirSync(params.outDir, { recursive: true });
  return transform(params);
}

// ---- small helpers --------------------------------------------------------------------------

function listDir(dir) {
  try {
    return fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  } catch {
    return [];
  }
}

/** A value fit for one YAML line: plain when that is safe, double-quoted otherwise. */
function yamlValue(text) {
  const flat = String(text).replace(/\s+/g, ' ').trim();
  if (flat && !/^[\s\-?:,[\]{}#&*!|>'"%@`]/.test(flat) && !/: | #|:$/.test(flat)) return flat;
  return `"${flat.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

/**
 * Read the frontmatter of a Markdown file: `{ fields, body }`. Handles plain, quoted and folded
 * or literal (`>`, `|`) values; a file without frontmatter has no fields.
 */
export function readFrontmatter(text) {
  const normal = String(text).replace(/\r\n/g, '\n');
  const match = normal.match(/^---\n([\s\S]*?)\n---[ \t]*(?:\n|$)/);
  if (!match) return { fields: {}, body: normal };
  const fields = {};
  const lines = match[1].split('\n');
  for (let i = 0; i < lines.length; i += 1) {
    const head = lines[i].match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!head) continue;
    let value = head[2];
    const block = value.match(/^([>|])[-+]?$/);
    if (block || value === '') {
      const parts = [];
      while (i + 1 < lines.length && /^[ \t]+\S/.test(lines[i + 1])) parts.push(lines[++i].trim());
      value = parts.join(block && block[1] === '|' ? '\n' : ' ');
    } else if (/^(".*"|'.*')$/.test(value)) {
      value = value.slice(1, -1).replace(/\\"/g, '"');
    }
    fields[head[1]] = value.trim();
  }
  return { fields, body: normal.slice(match[0].length) };
}

function copyFolder(from, to) {
  fs.cpSync(from, to, { recursive: true, dereference: true, filter: (src) => path.basename(src) !== '.git' });
}

function firstLine(text) {
  return String(text).split(/\r?\n/)[0];
}

// ---- design-md ------------------------------------------------------------------------------

function designMd({ repoRoot, sourcePath, outDir, revision = '', repo = '', skills = [] }) {
  const base = path.join(repoRoot, sourcePath);
  const registry = new Map(skills.map((skill) => [skill.id, skill]));
  let license = '';
  try {
    license = fs.readFileSync(path.join(repoRoot, 'LICENSE'), 'utf8');
  } catch { /* no licence file at the root */ }
  const written = [];
  for (const entry of listDir(base)) {
    if (!entry.isDirectory() || entry.name.startsWith('.')) continue;
    const design = path.join(base, entry.name, 'DESIGN.md');
    if (!fs.existsSync(design)) continue;
    const id = `design-${entry.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')}`;
    const known = registry.get(id);
    if (!known) continue;
    const brand = (known.description.match(/in the (.+?) look:/) || [])[1] || entry.name;
    const dir = path.join(outDir, id);
    fs.mkdirSync(dir, { recursive: true });
    fs.copyFileSync(design, path.join(dir, 'DESIGN.md'));
    if (license) fs.writeFileSync(path.join(dir, 'LICENSE'), license);
    fs.writeFileSync(path.join(dir, 'SKILL.md'), [
      '---',
      `name: ${id}`,
      `description: ${yamlValue(known.description)}`,
      '---',
      '',
      `# ${brand} look`,
      '',
      'Read DESIGN.md in this folder before you style UI in this look. Use its colours, type and rules. Do not invent new tokens.',
      '',
      `Source: ${repo || 'awesome-design-md'}${revision ? ` at ${revision.slice(0, 8)}` : ''}. Licence: see LICENSE.`,
      '',
    ].join('\n'));
    written.push({ id, description: known.description, group: known.group });
  }
  return written;
}

// ---- financial-services ---------------------------------------------------------------------

/** Anthropic's own `skill-creator` copy: our Anthropic set already holds a better one. */
const FINANCE_SKIP = new Set(['skill-creator']);

function walkPlugins(dir, found, depth = 0) {
  if (depth > 6) return;
  for (const entry of listDir(dir)) {
    if (!entry.isDirectory() || entry.name.startsWith('.') || entry.name === 'node_modules') continue;
    const full = path.join(dir, entry.name);
    if (entry.name === 'skills') {
      for (const skill of listDir(full)) {
        if (skill.isDirectory() && fs.existsSync(path.join(full, skill.name, 'SKILL.md'))) found.skills.push({ id: skill.name, dir: path.join(full, skill.name), plugin: path.basename(dir) });
      }
    } else if (entry.name === 'agents' || entry.name === 'commands') {
      for (const file of listDir(full)) {
        if (file.isFile() && file.name.endsWith('.md')) {
          found[entry.name].push({ id: file.name.slice(0, -3), file: path.join(full, file.name), plugin: path.basename(dir), dir });
        }
      }
    } else {
      walkPlugins(full, found, depth + 1);
    }
  }
}

function setName(skillMd, id) {
  const normal = skillMd.replace(/\r\n/g, '\n');
  const match = normal.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return normal;
  const fixed = /^name:/m.test(match[1])
    ? match[1].replace(/^name:.*$/m, `name: ${id}`)
    : `name: ${id}\n${match[1]}`;
  return normal.replace(match[1], () => fixed);
}

function financialServices({ repoRoot, sourcePath, outDir }) {
  const found = { skills: [], agents: [], commands: [] };
  walkPlugins(path.join(repoRoot, sourcePath), found);
  const written = new Map();
  const claim = (id, suffix) => {
    let name = id;
    if (written.has(name)) name = `${id}-${suffix}`;
    return name;
  };

  // 1. Plugin skills: copy the folder as it is. The first copy of a name wins (copies are equal).
  for (const skill of found.skills) {
    if (FINANCE_SKIP.has(skill.id) || written.has(skill.id)) continue;
    const dest = path.join(outDir, skill.id);
    copyFolder(skill.dir, dest);
    const file = path.join(dest, 'SKILL.md');
    const text = setName(fs.readFileSync(file, 'utf8'), skill.id);
    fs.writeFileSync(file, text);
    written.set(skill.id, { id: skill.id, kind: 'skill', description: readFrontmatter(text).fields.description || skill.id, group: skill.plugin, file });
  }

  // 2. Commands: fold into the skill of the same name, else make a skill of the command.
  for (const command of found.commands) {
    const { fields, body } = readFrontmatter(fs.readFileSync(command.file, 'utf8'));
    const usage = `/${command.id}${fields['argument-hint'] ? ` ${fields['argument-hint']}` : ''}`;
    const target = written.get(command.id);
    if (target && target.kind === 'skill') {
      const text = fs.readFileSync(target.file, 'utf8').replace(/\s+$/, '');
      fs.writeFileSync(target.file, `${text}\n\n## When called as /${command.id}\n\nUsage: ${usage}\n\n${body.trim()}\n`);
      continue;
    }
    const id = claim(command.id, 'command');
    const dest = path.join(outDir, id);
    fs.mkdirSync(dest, { recursive: true });
    const description = fields.description || `The /${command.id} command.`;
    fs.writeFileSync(path.join(dest, 'SKILL.md'), `---\nname: ${id}\ndescription: ${yamlValue(description)}\n---\n\n# /${command.id}\n\nUsage: ${usage}\n\n${body.trim()}\n`);
    written.set(id, { id, kind: 'command', description, group: `${command.plugin} (command)`, file: path.join(dest, 'SKILL.md') });
  }

  // 3. Agents: the prompt becomes the body; the tools become a note, not a key.
  for (const agent of found.agents) {
    const { fields, body } = readFrontmatter(fs.readFileSync(agent.file, 'utf8'));
    const id = claim(fields.name || agent.id, 'agent');
    const description = fields.description || `The ${id} agent.`;
    const bundled = found.skills.filter((skill) => skill.plugin === agent.plugin && !FINANCE_SKIP.has(skill.id)).map((skill) => skill.id);
    const tools = fields.tools ? fields.tools.split(',').map((tool) => tool.trim()).filter(Boolean) : [];
    const notes = ['## Tools this skill expects', ''];
    if (tools.length) notes.push(`Tools: ${tools.join(', ')}`, '');
    if (bundled.length) notes.push(`Skills it uses: ${bundled.join(', ')}`, '');
    if (tools.some((tool) => tool.startsWith('mcp__'))) {
      notes.push('The `mcp__` tools come from MCP connectors that your host must have connected. If one is missing, say so and stop. Never invent data that a connector would give.', '');
    }
    const dest = path.join(outDir, id);
    fs.mkdirSync(dest, { recursive: true });
    fs.writeFileSync(path.join(dest, 'SKILL.md'), `---\nname: ${id}\ndescription: ${yamlValue(description)}\n---\n\n${body.trim()}\n\n${notes.join('\n').trim()}\n`);
    written.set(id, { id, kind: 'agent', description, group: `${agent.plugin} (agent)`, file: path.join(dest, 'SKILL.md') });
  }

  return [...written.values()].map(({ id, description, group }) => ({ id, description: firstLine(description), group }));
}
