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

/** What a run saved, moved or refused, one line each. The CLI prints and empties it after every command. */
export const personalNotes = [];

export function personalFile(stateDir, skillId) {
  return path.join(stateDir, PERSONAL_DIRNAME, `${skillId}.md`);
}

const lf = (text) => text.replace(/\r\n/g, '\n');
/** The block's lines in LF, without the container newlines: what the personal file keeps and compares. */
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

/**
 * Write a file and remember its old bytes (null: it did not exist) so a failed run can restore it.
 * Files in the personal folder are the user's own: folder 0700, files 0600.
 */
function writeTracked(writes, file, text, personal = false) {
  writes.push({ file, before: readText(file) });
  const dir = path.dirname(file);
  fs.mkdirSync(dir, { recursive: true, ...(personal ? { mode: 0o700 } : {}) });
  if (personal) fs.chmodSync(dir, 0o700);
  fs.writeFileSync(file, text, { encoding: 'utf8', ...(personal ? { mode: 0o600 } : {}) });
  if (personal) fs.chmodSync(file, 0o600);
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
  const raw = inspection.rawCustomContent ?? '';
  return { file, markdown, raw, lines: linesOf(raw) };
}

/** The recorded copy folders of a skill's state entry, canonical first. Links show the canonical copy. */
export function recordedCopyFolders(root, entry) {
  const copies = entry?.copies?.length
    ? entry.copies
    : entry?.destination ? [{ destination: entry.destination, kind: 'canonical', method: entry.method }] : [];
  return copies
    .filter((copy) => copy?.destination && (copy.method || 'copy') === 'copy')
    .sort((a, b) => (a.kind === 'canonical' ? -1 : 0) - (b.kind === 'canonical' ? -1 : 0))
    .map((copy) => path.resolve(root, ...String(copy.destination).split(/[\\/]/)));
}

/** Take the lines in a skill's recorded blocks into its personal file before a command removes the folders. */
export function importPersonal({ stateDir, root, skillId, entry }) {
  return syncPersonalBlocks({ stateDir, skillId, read: recordedCopyFolders(root, entry) });
}

/**
 * Keep the personal file and the blocks of the given skill folders in step.
 *
 * - A MISSING file is rebuilt from the first non-empty block (the one-time move, or after it was deleted).
 *   Canonical first. An EMPTY file means: no lines, and the copies go empty.
 * - A block edit (lines that differ from the file and from what was last written) goes into the file, unless
 *   the file changed too: then the file wins.
 * - Every other differing block is saved beside the file, byte for byte, under a dated name, once.
 * - Then the file's lines are written into every folder in `write`, in that file's own line endings.
 * Every move, save and refusal is noted in `personalNotes` with its path.
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
  const dir = path.join(stateDir, PERSONAL_DIRNAME);
  const file = personalFile(stateDir, skillId);
  const renderedPath = path.join(dir, RENDERED);
  const fileText = readText(file);
  let rendered = {};
  try {
    rendered = JSON.parse(readText(renderedPath) || '{}');
  } catch {
    rendered = {};
  }
  const last = rendered[skillId] || null;
  const source = fileText === null ? null : linesOf(fileText);

  const blocks = [...new Set([...read, ...write])].map((folder) => blockIn(folder, skillId)).filter(Boolean);
  const firstBlock = new Map();
  for (const block of blocks) if (!firstBlock.has(block.lines)) firstBlock.set(block.lines, block);
  const savedBefore = fs.existsSync(dir)
    ? fs.readdirSync(dir).filter((name) => name.startsWith(`${skillId}.saved-`)).map((name) => readText(path.join(dir, name)))
    : [];
  // Lines already saved as a conflict never win later: a retry after an interrupted run must not flip the file.
  const savedLines = new Set(savedBefore.map((text) => linesOf(text)));
  const edits = absorb
    ? [...firstBlock.keys()].filter((lines) => lines && lines !== source && !savedLines.has(lines)
      && (source === null || hashOf(lines) !== last))
    : [];
  let next = source;
  if (edits.length > 0 && (source === null || hashOf(source) === last)) next = edits[0];
  const saved = [];
  const stamp = now.toISOString().replace(/[:.]/g, '-');
  edits.filter((lines) => lines !== next).forEach((lines, index) => {
    const block = firstBlock.get(lines);
    if (savedBefore.includes(block.raw)) return;
    const keep = path.join(dir, `${skillId}.saved-${stamp}-${index + 1}.md`);
    writeTracked(writes, keep, block.raw, true);
    saved.push(keep);
    personalNotes.push(`${skillId}: the personal lines in ${block.file} differ from ${file}; saved byte for byte to ${keep}`);
  });
  if (next === null) return { lines: null, writes, saved, refused: null };
  if (next !== source) {
    writeTracked(writes, file, asFile(next), true);
    personalNotes.push(`${skillId}: personal lines from ${firstBlock.get(next).file} are now kept in ${file}`);
  }
  // A marker in the user's lines would break every SKILL.md it reaches: keep the blocks and say so.
  if (next.includes(CUSTOM_BLOCK_START) || next.includes(CUSTOM_BLOCK_END)) {
    const refused = `${skillId}: ${file} holds a ${CUSTOM_BLOCK_START} or ${CUSTOM_BLOCK_END} marker; its lines were not written into any copy. Remove the marker from that file.`;
    personalNotes.push(refused);
    return { lines: next, writes, saved, refused };
  }

  const targets = new Set(write.map((folder) => path.resolve(folder)));
  for (const block of blocks) {
    if (!targets.has(path.resolve(path.dirname(block.file))) || block.lines === next) continue;
    const eol = block.markdown.includes('\r\n') ? '\r\n' : '\n';
    const raw = next ? `${eol}${next.split('\n').join(eol)}${eol}` : eol;
    writeTracked(writes, block.file, injectRawCustomContent(block.markdown, raw, skillId));
  }
  if (last !== hashOf(next)) writeTracked(writes, renderedPath, `${JSON.stringify({ ...rendered, [skillId]: hashOf(next) }, null, 2)}\n`, true);
  return { lines: next, writes, saved, refused: null };
}
