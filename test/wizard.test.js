import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { buildPackRows, windowRows } from '../src/wizard.js';
import { getCatalog } from '../src/catalog.js';
import {
  ACME_PACK, createRemote, createSandbox, writeUserConfig,
} from './pack-fixtures.js';

const DOWN = '\x1b[B';
const RIGHT = '\x1b[C';
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

test('wizard: opens on the grouped picker in the DESIGN.md palette', async () => {
  const box = createSandbox();
  try {
    const { code, io } = await wizard(box, '');
    assert.equal(code, 0);
    const first = io.frames()[1];
    assert.match(first, /Σ SIGMA SKILLS/);
    assert.match(first, /1 What\s+2 Where\s+3 Review/);
    for (const title of ['Sigma', 'Matt Pocock', 'Three.js', 'HyperFrames', 'MiniMax H3', 'StorgeStudio']) {
      assert.ok(first.includes(title), `${title} row`);
    }
    assert.match(first, /0\/38/);
    assert.match(first, /n\/a/, 'an unavailable pack is shown but marked');
    assert.match(io.raw(), /\x1b\[48;2;9;9;11m/, 'canvas #09090b');
    assert.match(io.raw(), /\x1b\[1;38;2;52;211;153m/, 'emerald #34d399');
    assert.match(io.text(), /Cancelled\. Nothing was written\./);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents')));
    assert.deepEqual(io.rawModes, [true, false], 'raw mode restored');
    assert.ok(io.raw().includes('\x1b[?1049l'), 'left the alternate screen');
    assert.ok(io.raw().endsWith('\n') && io.raw().includes('\x1b[?25h'), 'cursor shown again');
  } finally {
    box.cleanup();
  }
});

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
    assert.match(linked.io.frames().find((frame) => frame.includes('2 Where') && frame.includes('Method')), /Claude Code\s+\.claude\/skills\s+linked\s+found here/);
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
    const { code, io } = await wizard(box, `7${ENTER}${ENTER}${ENTER}`);
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
    // Filter for "beta", keep it, toggle the hit with space, then walk the three steps.
    const { code, io } = await wizard(box, `/beta${ENTER} ${ENTER}${ENTER}${ENTER}`);
    assert.equal(code, 0, io.err());
    assert.ok(io.frames().some((frame) => /Filter: beta/.test(frame)));
    assert.match(io.text(), /1 skill installed/);
    assert.ok(fs.existsSync(skillPath(box, 'beta')));
    assert.ok(!fs.existsSync(skillPath(box, 'alpha')));
  } finally {
    box.cleanup();
  }
});

test('wizard: right opens a pack, space toggles one skill, left closes it', async () => {
  const box = createSandbox();
  try {
    const { code, io } = await wizard(box, `${DOWN}${RIGHT}${DOWN} ${ENTER}`);
    assert.equal(code, 0);
    const pickerFrames = io.frames().filter((frame) => frame.includes('Pick packs'));
    assert.ok(pickerFrames.some((frame) => frame.includes('ask-matt')), 'the Matt Pocock skills are listed once the pack is open');
    const last = pickerFrames.at(-1);
    assert.match(last, /\[x\]\s+ask-matt/);
    assert.match(last, /1 skill selected from 1 pack/);
    assert.match(last, /\[-\]\s+2 Matt Pocock\s+1\/38/, 'the pack shows a partial mark');
  } finally {
    box.cleanup();
  }
});

test('wizard: nothing selected shows a notice and does not advance', async () => {
  const box = createSandbox();
  try {
    const { io } = await wizard(box, ENTER);
    assert.ok(io.frames().some((frame) => frame.includes('Select at least one skill.')));
    assert.ok(!io.frames().some((frame) => frame.includes('2 Where') && frame.includes('Method')));
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

test('wizard: a short, narrow terminal still shows every step within its bounds', async () => {
  const box = createSandbox();
  try {
    const { io } = await wizard(box, `1${ENTER}${ENTER}`, [], { columns: 50, rows: 14 });
    for (const frame of io.frames().slice(1)) {
      const lines = frame.split('\n').filter((line) => !/^\s*$/.test(line) || true);
      assert.ok(lines.length <= 15, `frame has ${lines.length} lines`);
      for (const line of lines) assert.ok(line.length <= 50, `line too wide: ${line.length}`);
    }
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
});
