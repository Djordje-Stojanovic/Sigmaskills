import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { CUSTOM_BLOCK_END, CUSTOM_BLOCK_START, inspectCustomizationBlock, injectRawCustomContent } from './customization.js';

/**
 * A user's personal instructions for a skill live in one file outside every skill folder:
 * `<state dir>/custom/<skill>.md`. The block in each copy's SKILL.md is its rendered view (#407).
 * Like a systemd drop-in or a git include, the user's lines never live only inside package files,
 * so no replace, repair or copy can lose them.
 */
export const PERSONAL_DIRNAME = 'custom';
const RENDERED = '.rendered.json';

export function personalFile(stateDir, skillId) {
  return path.join(stateDir, PERSONAL_DIRNAME, `${skillId}.md`);
}

const lf = (text) => text.replace(/\r\n/g, '\n');
/** The block's lines in LF, without the container newlines: what is kept and compared. */
const linesOf = (raw) => lf(raw).replace(/^\n+/, '').replace(/\s+$/, '');
const asFile = (lines) => (lines ? `${lines}\n` : '');
const hashOf = (lines) => crypto.createHash('sha256').update(lines).digest('hex');

function readText(file) {
  try {
    return fs.readFileSync(file, 'utf8');
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err;
  }
}

/** Write a file and remember its old bytes (null: it did not exist) so a failed run can restore it. */
function writeTracked(writes, file, text) {
  writes.push({ file, before: readText(file) });
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text, 'utf8');
}

/** Put back every file a run wrote, newest first. */
export function restorePersonalWrites(writes = []) {
  for (const { file, before } of [...writes].reverse()) {
    try {
      if (before === null) fs.rmSync(file, { force: true });
      else fs.writeFileSync(file, before, 'utf8');
    } catch {
      // Restore is best-effort, like the rest of rollback.
    }
  }
}

function blockIn(dir, skillId) {
  const file = path.join(dir, 'SKILL.md');
  let stat;
  try {
    stat = fs.lstatSync(file);
  } catch {
    return null;
  }
  if (!stat.isFile()) return null;
  const markdown = fs.readFileSync(file, 'utf8');
  const inspection = inspectCustomizationBlock(markdown, skillId);
  if (inspection.status !== 'valid' && inspection.status !== 'empty') return null;
  return { file, markdown, lines: linesOf(inspection.rawCustomContent ?? '') };
}

/**
 * Keep the personal file and the blocks of the given skill folders in step.
 *
 * - An edit made in a block (lines that differ from the file and from what was last rendered) is taken
 *   into the file, unless the file changed too: then the file wins and the block's lines are saved beside it.
 * - With no file yet, the first non-empty block becomes the file (the one-time move). Canonical first.
 * - Every other differing block is saved beside the file under a dated name. Nothing is deleted.
 * - Then the file's lines are written into every folder in `write`, in that file's own line endings.
 *
 * @param {object} params
 * @param {string} params.stateDir
 * @param {string} params.skillId
 * @param {string[]} params.read Skill folders whose blocks may hold the user's lines (canonical first)
 * @param {string[]} params.write Skill folders this run may write
 * @param {object[]} [params.writes] Collects { file, before } for rollback
 * @param {boolean} [params.absorb] false: only write the file's lines (after a run rewrote the folders)
 * @returns {{ lines: string|null, writes: object[], saved: string[], refused: string|null }}
 */
export function syncPersonalBlocks({ stateDir, skillId, read = [], write = [], writes = [], absorb = true, now = new Date() }) {
  const file = personalFile(stateDir, skillId);
  const renderedPath = path.join(stateDir, PERSONAL_DIRNAME, RENDERED);
  const fileText = readText(file);
  let rendered = {};
  try {
    rendered = JSON.parse(readText(renderedPath) || '{}');
  } catch {
    rendered = {};
  }
  const last = rendered[skillId] || null;
  const source = fileText === null ? null : linesOf(fileText);

  const blocks = [...new Set([...read, ...write])].map((dir) => blockIn(dir, skillId)).filter(Boolean);
  const edits = absorb ? [...new Set(blocks.map((block) => block.lines))]
    .filter((lines) => lines && lines !== source && hashOf(lines) !== last) : [];
  let next = source;
  if (edits.length > 0 && (source === null || hashOf(source) === last)) next = edits[0];
  const saved = [];
  const stamp = now.toISOString().replace(/[:.]/g, '-');
  edits.filter((lines) => lines !== next).forEach((lines, index) => {
    const keep = path.join(stateDir, PERSONAL_DIRNAME, `${skillId}.saved-${stamp}-${index + 1}.md`);
    writeTracked(writes, keep, asFile(lines));
    saved.push(keep);
  });
  if (next === null) return { lines: null, writes, saved, refused: null };
  if (next !== source) writeTracked(writes, file, asFile(next));
  // A marker in the user's lines would break every SKILL.md it reaches: keep the blocks and say so.
  if (next.includes(CUSTOM_BLOCK_START) || next.includes(CUSTOM_BLOCK_END)) {
    return { lines: next, writes, saved, refused: `${file} holds a ${CUSTOM_BLOCK_START} or ${CUSTOM_BLOCK_END} marker; its lines were not written into ${skillId}` };
  }

  const targets = new Set(write.map((dir) => path.resolve(dir)));
  for (const block of blocks) {
    if (!targets.has(path.resolve(path.dirname(block.file))) || block.lines === next) continue;
    const eol = block.markdown.includes('\r\n') ? '\r\n' : '\n';
    const raw = next ? `${eol}${next.split('\n').join(eol)}${eol}` : eol;
    writeTracked(writes, block.file, injectRawCustomContent(block.markdown, raw, skillId));
  }
  if (last !== hashOf(next)) writeTracked(writes, renderedPath, `${JSON.stringify({ ...rendered, [skillId]: hashOf(next) }, null, 2)}\n`);
  return { lines: next, writes, saved, refused: null };
}
