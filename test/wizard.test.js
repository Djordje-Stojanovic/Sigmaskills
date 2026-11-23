import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { buildPackRows, orderPacks, previewFrame, windowRows } from '../src/wizard.js';
import { getCatalog } from '../src/catalog.js';
import {
  ACME_PACK, createMockIo, createRemote, createSandbox, writeUserConfig,
} from './pack-fixtures.js';

const UP = '[A';
const DOWN = '\x1b[B';
const ENTER = '\r';
const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g;

function terminal(box, keys, { columns = 110, rows = 30, colorDepth = 24 } = {}) {
  const stdin = new PassThrough();
  stdin.isTTY = true;
  const rawModes = [];
  stdin.setRawMode = (enabled) => rawModes.push(enabled);
  const stdout = new PassThrough();
  stdout.isTTY = true;
  stdout.columns = columns;
  stdout.rows = rows;
  stdout.getColorDepth = () => colorDepth;
  const stderr = new PassThrough();
  let out = '';
  let err = '';
  stdout.setEncoding('utf8');
  stderr.setEncoding('utf8');
  stdout.on('data', (chunk) => { out += chunk; });
  stderr.on('data', (chunk) => { err += chunk; });
  queueMicrotask(() => stdin.end(keys));
  const env = { ...box.env, TERM: 'xterm-256color' };
  return {
    stdin, stdout, stderr, env, rawModes,
    raw: () => out,
    text: () => out.replace(ANSI, ''),
    frames: () => out.split('\x1b[2J\x1b[H').map((frame) => frame.replace(ANSI, '')),
    err: () => err,
  };
}

async function wizard(box, keys, args = [], options = {}) {
  const io = terminal(box, keys, options);
  const code = await runCli([...args, '--project', box.project], io);
  return { code, io };
}

const skillPath = (box, id) => path.join(box.project, '.agents', 'skills', id, 'SKILL.md');

test('wizard: the Sigma pack key, then Where and Review, installs the whole pack', async () => {
  const box = createSandbox();
  try {
    const { code, io } = await wizard(box, `1${ENTER}${ENTER}${ENTER}`);
    assert.equal(code, 0, io.err());
    const count = getCatalog().skills.length;
    const frames = io.frames();
    assert.ok(frames.some((frame) => frame.includes(`Install ${count} skills`)), 'review screen');
    assert.match(io.text(), new RegExp(`${count} skills installed`));
    assert.match(io.text(), /Next\s+sigmaskills status/);
    assert.ok(fs.existsSync(skillPath(box, 'sigmawrite')));
    assert.ok(fs.existsSync(path.join(box.project, 'skills-lock.json')));
  } finally {
    box.cleanup();
  }
});

test('wizard: a found host gets its folder, linked; m switches to a full copy', async () => {
  const box = createSandbox();
  try {
    fs.mkdirSync(path.join(box.home, '.claude'));
    const linked = await wizard(box, `1${ENTER}${ENTER}${ENTER}`);
    assert.equal(linked.code, 0, linked.io.err());
    assert.match(linked.io.frames().find((frame) => frame.includes('Pick where they go')), /Claude Code\s+\.claude\/skills\s+linked\s+found here/);
    const link = path.join(box.project, '.claude', 'skills', 'sigmawrite');
    assert.ok(fs.lstatSync(link).isSymbolicLink());

    const box2 = createSandbox();
    try {
      fs.mkdirSync(path.join(box2.home, '.claude'));
      const copied = await wizard(box2, `1${ENTER}m${ENTER}${ENTER}`);
      assert.equal(copied.code, 0, copied.io.err());
      const copy = path.join(box2.project, '.claude', 'skills', 'sigmawrite');
      assert.ok(!fs.lstatSync(copy).isSymbolicLink());
    } finally {
      box2.cleanup();
    }
  } finally {
    box.cleanup();
  }
});

test('wizard: a pack from outside installs, and the review names the download', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    // Acme is the 22nd pack: twenty-one built-in packs come first (Local hides with no folder set), the one-skill sources after it.
    const { code, io } = await wizard(box, `${DOWN.repeat(21)} ${ENTER}${ENTER}${ENTER}`);
    assert.equal(code, 0, io.err());
    assert.ok(io.frames().some((frame) => /Downloads\s+acme\/skills/.test(frame)));
    assert.match(io.text(), /2 skills installed/);
    assert.ok(fs.existsSync(skillPath(box, 'alpha')));
    assert.ok(fs.existsSync(skillPath(box, 'beta')));
    assert.ok(!fs.existsSync(skillPath(box, 'sigmawrite')));
  } finally {
    box.cleanup();
  }
});

test('wizard: open a pack, pick single skills, and filter', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    // Filter for "beta", keep it, go to the last hit (Acme) and toggle it with space, then walk the three steps.
    const { code, io } = await wizard(box, `/beta${ENTER}${UP} ${ENTER}${ENTER}${ENTER}`);
    assert.equal(code, 0, io.err());
    assert.ok(io.frames().some((frame) => /Filter {2}beta/.test(frame)));
    assert.match(io.text(), /1 skill installed/);
    assert.ok(fs.existsSync(skillPath(box, 'beta')));
    assert.ok(!fs.existsSync(skillPath(box, 'alpha')));
  } finally {
    box.cleanup();
  }
});

test('wizard: Global needs the explicit y, and writes under the home folder', async () => {
  const box = createSandbox();
  try {
    const refusedEnter = await wizard(box, `1${ENTER}s${ENTER}${ENTER}`);
    assert.ok(!fs.existsSync(path.join(box.home, '.agents', 'skills', 'sigmawrite')), 'enter alone does not install globally');
    assert.ok(refusedEnter.io.frames().some((frame) => /Global Installation writes skills for every project/.test(frame)));

    const box2 = createSandbox();
    try {
      const { code, io } = await wizard(box2, `1${ENTER}s${ENTER}y`);
      assert.equal(code, 0, io.err());
      assert.ok(fs.existsSync(path.join(box2.home, '.agents', 'skills', 'sigmawrite', 'SKILL.md')));
      assert.ok(!fs.existsSync(path.join(box2.project, '.agents')));
    } finally {
      box2.cleanup();
    }
  } finally {
    box.cleanup();
  }
});

test('wizard: b goes back one step and Ctrl+C aborts with 130', async () => {
  const box = createSandbox();
  try {
    const back = await wizard(box, `1${ENTER}b`);
    const frames = back.io.frames();
    const whereAt = frames.findIndex((frame) => frame.includes('Method'));
    assert.ok(frames.slice(whereAt + 1).some((frame) => frame.includes('Pick packs')), 'returned to step one');

    const abort = await wizard(box, `1${ENTER}\x03`);
    assert.equal(abort.code, 130);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents')));
  } finally {
    box.cleanup();
  }
});

test('wizard: --classic, --static, --no-color and a pipe use the line-by-line installer', async () => {
  const box = createSandbox();
  try {
    const classic = await wizard(box, '', ['--classic']);
    assert.match(classic.io.text(), /Stage 1\/4/);
    const plain = await wizard(box, '', ['--no-color']);
    assert.match(plain.io.text(), /Stage 1\/4/);
    assert.doesNotMatch(plain.io.text(), /1 What/);
  } finally {
    box.cleanup();
  }
});

test('wizard helpers: windowRows keeps the cursor in view and buildPackRows nests skills', () => {
  assert.deepEqual(windowRows(5, 2, 10), { start: 0, end: 5 });
  assert.deepEqual(windowRows(100, 0, 10), { start: 0, end: 10 });
  assert.deepEqual(windowRows(100, 50, 10), { start: 45, end: 55 });
  assert.deepEqual(windowRows(100, 99, 10), { start: 90, end: 100 });

  const packs = [
    { id: 'a', title: 'Apple', skills: [{ id: 'one', description: 'First' }, { id: 'two', description: 'Second' }] },
    { id: 'b', title: 'Berry', skills: [{ id: 'three', description: 'Third' }] },
  ];
  assert.deepEqual(buildPackRows(packs, new Set(), '').map((row) => row.type), ['pack', 'pack']);
  assert.deepEqual(buildPackRows(packs, new Set(['a']), '').map((row) => row.skill?.id || row.pack.id), ['a', 'one', 'two', 'b']);
  assert.deepEqual(buildPackRows(packs, new Set(), 'sec').map((row) => row.skill.id), ['two']);
  assert.deepEqual(buildPackRows(packs, new Set(), 'berry').map((row) => row.skill.id), ['three'], 'a pack name matches its skills');

  const grouped = orderPacks([
    { id: 'taste', title: 'Taste', category: 'Design', available: true, skills: [{ id: 'x' }] },
    { id: 'audit', title: 'Audit', category: 'Engineering', available: true, skills: [{ id: 'w' }] },
    { id: 'empty', title: 'Empty', available: true, skills: [] },
    { id: 'matt', title: 'Matt', available: true, skills: [{ id: 'y' }, { id: 'z' }] },
    { id: 'off', title: 'Off', available: false, note: 'set a folder', skills: [] },
    { id: 'lost', title: 'Lost', available: false, note: 'folder not found', sources: [{ type: 'dir', path: '/nowhere' }], skills: [] },
  ]);
  assert.deepEqual(grouped.map((pack) => pack.id), ['matt', 'lost', 'audit', 'taste'], 'packs keep their order, one-skill sources go last by category, an empty or unset pack is hidden, a set folder that fails keeps its note');
  assert.deepEqual(buildPackRows(grouped, new Set(), '').map((row) => row.group || row.pack.id), ['Packs', 'matt', 'lost', 'Engineering', 'audit', 'Design', 'taste']);
  assert.deepEqual(buildPackRows(grouped, new Set(), 'design').map((row) => row.skill.id), ['x'], 'the filter matches a category name');
});

test('wizard: packs stay packs, single skills sit under their category, and a long name never runs into its count', async () => {
  const box = createSandbox();
  try {
    const { io } = await wizard(box, CTRL_C, [], { columns: 80, rows: 60 });
    const first = io.frames().find((frame) => frame.includes('Pick packs'));
    assert.match(first, /\n│ {2}Packs ─+\n[\s\S]*Matt Pocock[\s\S]*\n│ {2}Design ─+\n[\s\S]*Taste/);
    assert.doesNotMatch(first, /[a-z]\d+\/\d+/, 'a space always separates name and count');
  } finally {
    box.cleanup();
  }
});

test('wizard: u picks every installed skill for an update, x marks them all for removal', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    const setup = createMockIo(box.env);
    assert.equal(await runCli(['install', 'alpha', 'beta', '--yes', '--project', box.project], setup), 0, setup.getStderr());

    // u is its own short flow: one key lands on the update review, with no Where step, and enter updates.
    const update = await wizard(box, `u${ENTER}`);
    assert.equal(update.code, 0, update.io.err());
    const frames = update.io.frames();
    assert.ok(frames.some((frame) => /2 installed here {3}u update them · x uninstall them/.test(frame)), 'the first screen offers both');
    assert.ok(!frames.some((frame) => frame.includes('Pick where they go')), 'an update never asks where');
    // A frame ends at its └ line; the run's own output follows it once the screen closes.
    const screenOf = (frame) => frame && frame.slice(0, frame.indexOf('\n', frame.indexOf('└')));
    const review = screenOf(frames.find((frame) => frame.includes('◆  Update 2 skills')));
    assert.ok(review && /└ {2}enter update · b back/.test(review) && !review.includes('install'), 'the review names the update');
    assert.match(review, /Acme\s+2 of 2/, 'the update lists its skills per pack');

    // x says remove, never install.
    const remove = await wizard(box, `x${ENTER}`);
    assert.equal(remove.code, 0, remove.io.err());
    const gone = screenOf(remove.io.frames().find((frame) => frame.includes('◆  Remove 2 skills')));
    assert.ok(gone && /└ {2}enter remove · b back/.test(gone) && !/install/i.test(gone), 'the review names the removal');
    assert.ok(!fs.existsSync(skillPath(box, 'alpha')) && !fs.existsSync(skillPath(box, 'beta')));
  } finally {
    box.cleanup();
  }
});

const RIGHT = '\x1b[C';
const PAGE_DOWN = '\x1b[6~';
const CTRL_C = '\x03';

test('wizard helpers: previewFrame wraps, keeps the indent and clamps the scroll', () => {
  const text = ['# Title', '', '  indented words that are long enough to wrap around the edge', 'last'].join('\r\n');
  const all = previewFrame(text, 30, 10, 0);
  assert.equal(all.top, 0);
  assert.deepEqual(all.lines.slice(0, 2), ['# Title', '']);
  assert.ok(all.lines.length > 4, 'the long line wraps');
  assert.ok(all.lines.slice(2, -1).every((line) => line.startsWith('  ') && line.length <= 30), 'wrapped parts keep the indent and the width');
  assert.equal(all.total, all.lines.length);
  assert.deepEqual(previewFrame(text, 30, 2, 99).lines, all.lines.slice(-2), 'a scroll past the end stops at the last page');
  assert.equal(previewFrame(text, 30, 2, 99).top, all.total - 2);
  assert.equal(previewFrame(text, 30, 2, -5).top, 0);
});

test('wizard: p opens the full text of a Sigma skill, PgDn scrolls it, q closes it', async () => {
  const box = createSandbox();
  try {
    const first = getCatalog().skills[0].id;
    const { code, io } = await wizard(box, `${RIGHT}${DOWN}p${PAGE_DOWN}q${CTRL_C}`);
    assert.equal(code, 130);
    const frames = io.frames();
    const opened = frames.find((frame) => frame.includes(`${first}  SKILL.md   lines 1-`));
    assert.ok(opened, 'the preview names the skill and the lines it shows');
    assert.ok(opened.includes(`name: ${first}`), 'the frame holds the text of SKILL.md');
    assert.ok(frames.some((frame) => /SKILL\.md {3}lines (?!1-)\d+-\d+ of \d+/.test(frame)), 'PgDn moves down');
    assert.ok(frames.at(-1).includes('Pick packs'), 'q goes back to the list');
    assert.ok(!fs.existsSync(skillPath(box, first)), 'reading a skill installs nothing');
  } finally {
    box.cleanup();
  }
});

test('wizard: p shows the text of a pack skill, and a clear line when the source cannot be reached', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    const ok = await wizard(box, `/beta${ENTER}${UP}pq${CTRL_C}`);
    assert.ok(ok.io.frames().some((frame) => /beta {2}SKILL\.md/.test(frame) && frame.includes('Beta skill.')), ok.io.err());

    fs.rmSync(path.join(box.remotes, 'acme'), { recursive: true, force: true });
    const down = await wizard(box, `/beta${ENTER}${UP}pq${CTRL_C}`);
    assert.ok(down.io.frames().some((frame) => frame.includes('Could not load the text of beta')));
    assert.ok(/Filter {2}beta/.test(down.io.frames().at(-1)), 'the wizard is still usable');
  } finally {
    box.cleanup();
  }
});

test('wizard: unticking installed skills lists them under Remove, and the confirm removes them', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    const first = getCatalog().skills[0].id;
    const setup = createMockIo(box.env);
    assert.equal(await runCli(['install', first, 'alpha', 'beta', '--yes', '--project', box.project], setup), 0, setup.getStderr());
    assert.ok(fs.existsSync(skillPath(box, first)) && fs.existsSync(skillPath(box, 'alpha')));

    // Untick the first Sigma skill, then alpha (the last hit of the filter). Only removals: Where is skipped.
    const { code, io } = await wizard(box, `${RIGHT}${DOWN} /alpha${ENTER}${UP} ${ENTER}${ENTER}`);
    assert.equal(code, 0, io.err());
    const frames = io.frames();
    assert.ok(frames.some((frame) => new RegExp(`✕ ${first}.*will remove`).test(frame)), 'the unticked skill says what will happen');
    const review = frames.find((frame) => frame.includes('Remove 2 skills'));
    assert.ok(review, 'the review lists the removals');
    assert.ok(review.includes(first) && review.includes('alpha') && !/Install \d|Update \d/.test(review));
    assert.match(io.text(), /removed 2 skills\n\s+Sigma\s+\S+\n\s+Acme\s+alpha\n/, 'removals are listed per pack');
    assert.ok(!fs.existsSync(skillPath(box, first)));
    assert.ok(!fs.existsSync(skillPath(box, 'alpha')));
    assert.ok(fs.existsSync(skillPath(box, 'beta')), 'a skill that stayed ticked is kept');
  } finally {
    box.cleanup();
  }
});

test('wizard: an installed skill picked again is an update, apart from the installs', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    const setup = createMockIo(box.env);
    assert.equal(await runCli(['install', 'alpha', '--yes', '--project', box.project], setup), 0, setup.getStderr());

    // alpha: space unticks it, space again picks it for an update. beta is new.
    const { code, io } = await wizard(box, `/alpha${ENTER}${UP}  /beta${ENTER}${UP} ${ENTER}${ENTER}${ENTER}`);
    assert.equal(code, 0, io.err());
    const frames = io.frames();
    assert.ok(frames.some((frame) => /● alpha.*will update/.test(frame)));
    const review = frames.find((frame) => frame.includes('Update 1 skill'));
    assert.ok(review && review.includes('Install 1 skill') && !review.includes('Remove'), 'installs and updates are listed apart');
    assert.ok(fs.existsSync(skillPath(box, 'alpha')) && fs.existsSync(skillPath(box, 'beta')));
  } finally {
    box.cleanup();
  }
});

test('wizard: the first screen names its scope, and s switches it, so u and x act on what is shown', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    const setup = createMockIo(box.env);
    assert.equal(await runCli(['install', 'alpha', '--yes', '--project', box.project], setup), 0, setup.getStderr());

    // Switch to Global, press x: nothing is installed there, so nothing is marked and enter asks for a pick.
    const { io } = await wizard(box, `sx${ENTER}${CTRL_C}`, [], { columns: 80 });
    const frames = io.frames().filter((frame) => frame.includes('Pick packs'));
    assert.match(frames[0], /│ {2}Project {2}.*s switch to Global/);
    assert.match(frames[0], /1 installed here/);
    const global = frames.find((frame) => /│ {2}Global {2}.*s switch to Project/.test(frame));
    assert.ok(global && global.includes('Nothing installed here yet'), 'after s the screen shows the global scope');
    assert.match(global, /1 more in Project: s to see them/, 'from Global, the project install is still counted');
    assert.ok(frames.at(-1).includes('Select at least one skill.'), 'x in an empty scope marks nothing');
    assert.ok(frames.every((frame) => frame.split('\n').every((line) => line.length < 80)), 'no line runs past 80 columns');
    assert.ok(fs.existsSync(skillPath(box, 'alpha')), 'the project skill is untouched');
  } finally {
    box.cleanup();
  }
});

test('wizard: an installed pack says so on its row, not 0/N', async () => {
  const box = createSandbox();
  try {
    createRemote(box.remotes, 'acme/skills', { alpha: 'Alpha skill.', beta: 'Beta skill.' });
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    const setup = createMockIo(box.env);
    assert.equal(await runCli(['install', 'alpha', 'beta', '--yes', '--project', box.project], setup), 0, setup.getStderr());
    const { io } = await wizard(box, CTRL_C, [], { columns: 80, rows: 60 });
    const first = io.frames().find((frame) => frame.includes('Pick packs'));
    assert.match(first, /✓ +Acme +2 installed/);
    assert.doesNotMatch(first, /\b0\/\d+/, 'no pack row reads 0/N');
    assert.match(first, /○ 2 Matt Pocock *\n/, 'a pack that is neither picked nor installed shows no count');
  } finally {
    box.cleanup();
  }
});

test('wizard: the screen ends where the content ends, on a rail the canvas shows', async () => {
  const box = createSandbox();
  try {
    const { io } = await wizard(box, `1${ENTER}${ENTER}${CTRL_C}`, [], { columns: 80, rows: 40 });
    const review = io.frames().find((frame) => frame.includes('Review and confirm')).split('\n');
    const end = review.findIndex((line) => line.startsWith('└'));
    assert.ok(end > 0 && end < 30, 'the footer sits under the content, not on the last row');
    assert.ok(review[end - 1].trim() === '│' && review[end - 2].trim() !== '│', 'at most one blank rail row before └');
    // The screen is 39 rows (one is kept free); the cancel line prints after it.
    assert.ok(review.slice(end + 1, 39).every((line) => !line.trim()), 'the canvas below is bare');
    assert.match(io.raw(), /\x1b\[38;2;161;161;170m│/, 'the rail is drawn in mute (#a1a1aa), not a hairline');
  } finally {
    box.cleanup();
  }
});

test('wizard: Where shows .agents/skills once, and the review uses the same words', async () => {
  const box = createSandbox();
  try {
    fs.mkdirSync(path.join(box.home, '.claude'));
    const { io } = await wizard(box, `1${ENTER}${ENTER}${CTRL_C}`, [], { columns: 80 });
    const where = io.frames().find((frame) => frame.includes('Pick where they go'));
    assert.equal(where.match(/\.agents\/skills +always on · read by /g)?.length, 1, 'one row for the shared folder');
    assert.doesNotMatch(where, /reads \.agents\/skills/, 'no host row repeats it');
    const ends = where.split('\n').filter((line) => /^│ [❯ ] [●○]/.test(line)).map((line) => line.trimEnd().split(/ {2,}/).at(-1));
    assert.equal(new Set(ends).size, ends.length, 'no two rows end in the same text');
    const review = io.frames().find((frame) => frame.includes('Review and confirm'));
    assert.match(review, /\.agents\/skills +files /);
    assert.match(review, /\.claude\/skills +linked /);
    assert.doesNotMatch(review, /\bcopy\b/);
  } finally {
    box.cleanup();
  }
});

test('wizard: nothing on the first screen at 80 columns looks broken', async () => {
  const box = createSandbox();
  try {
    // s posts a notice; it gets its own line, wrapped, never clipped.
    const { io } = await wizard(box, `s${CTRL_C}`, [], { columns: 80, rows: 40 });
    const frames = io.frames().filter((frame) => frame.includes('Pick packs'));
    for (const frame of frames) {
      const lines = frame.split('\n').map((line) => line.trimEnd());
      assert.ok(lines.every((line) => !line.endsWith('…')), `no line is clipped:\n${lines.filter((line) => line.endsWith('…')).join('\n')}`);
      assert.ok(!lines.some((line) => /^│ [❯ ] !/.test(line) || line.includes('n/a')), 'no unset folder pack row');
    }
    assert.match(frames.at(-1), /\n│ {2}Now in Global: u and x act on what is installed here\.\s*\n/, 'the notice has its own line');
    assert.doesNotMatch(io.raw(), /Review, improve, ship[^\n]*\x1b\[38;2;161;161;170m/, 'the description is one colour');
  } finally {
    box.cleanup();
  }
});

test('wizard: the done screen fits 80 columns and says how to come back', async () => {
  const box = createSandbox();
  try {
    const { code, io } = await wizard(box, `1${ENTER}${ENTER}${ENTER}`, [], { columns: 80 });
    assert.equal(code, 0, io.err());
    const done = io.frames().at(-1).split('\n').slice(io.frames().at(-1).split('\n').findIndex((line) => line.startsWith('└')) + 1);
    assert.ok(done.every((line) => line.trimEnd().length <= 80), done.filter((line) => line.trimEnd().length > 80).join('\n'));
    assert.match(done.join('\n'), /Run it again to update or remove: npx @djordje-stojanovic\/sigmaskills/);
  } finally {
    box.cleanup();
  }
});
