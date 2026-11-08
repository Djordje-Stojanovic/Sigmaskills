import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { commandLines } from './terminal-input.js';
import { runCli } from '../src/cli.js';

function createSimulatedTerminal(input, options = {}) {
  const stdin = new PassThrough();
  stdin.isTTY = options.tty ?? true;
  stdin.isRaw = false;
  const rawModes = [];
  stdin.setRawMode = (enabled) => {
    rawModes.push(enabled);
    stdin.isRaw = enabled;
  };

  const stdout = new PassThrough();
  stdout.isTTY = options.tty ?? true;
  stdout.columns = options.columns ?? 100;
  stdout.rows = options.rows ?? 30;
  stdout.getColorDepth = () => options.colorDepth ?? 24;

  const stderr = new PassThrough();
  let out = '';
  let err = '';
  stdout.setEncoding('utf8');
  stderr.setEncoding('utf8');
  stdout.on('data', (chunk) => {
    out += chunk;
    options.onStdout?.(chunk, out, stdin, stdout);
  });
  stderr.on('data', (chunk) => {
    err += chunk;
  });

  if (!options.manualInput) queueMicrotask(() => stdin.end((options.static || !stdin.isTTY || options.forceNoColor || options.colorDepth === 1 || options.env?.CI) ? commandLines(input) : input));

  const env = { ...(options.env ?? process.env), CI: options.env?.CI ?? '' };
  delete env.NO_COLOR;
  delete env.REDUCED_MOTION;
  delete env.PREFERS_REDUCED_MOTION;
  delete env.FORCE_COLOR;
  if (options.forceNoColor) env.NO_COLOR = '';
  if (options.env?.REDUCED_MOTION) env.REDUCED_MOTION = options.env.REDUCED_MOTION;
  if (options.env?.PREFERS_REDUCED_MOTION) env.PREFERS_REDUCED_MOTION = options.env.PREFERS_REDUCED_MOTION;
  if (options.env?.TERM) env.TERM = options.env.TERM;
  else if (stdout.isTTY) env.TERM = 'xterm-256color';

  return {
    stdin,
    stdout,
    stderr,
    env,
    getStdout: () => out,
    getStderr: () => err,
    getRawModes: () => rawModes,
  };
}

function sandboxProject() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-emberforge-'));
}

test('keyboard help, focus, search, selection, confirmation, and cancellation stay available without a mouse', async () => {
  const projectRoot = sandboxProject();
  try {
    const io = createSimulatedTerminal('x?x \rp\x1b\x1b');
    const code = await runCli(['--classic', '--project', projectRoot], io);
    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /\? help/);
    assert.match(output, /Keyboard/);
    assert.match(output, /↑\/↓ move focus/);
    assert.match(output, /space toggle selection/);
    assert.match(output, /type to search/);
    assert.match(output, /enter continue/);
    assert.match(output, /esc cancel/);
    assert.match(output, /Ctrl\+C abort/);
    assert.match(output, /Plain mode: type a command, then Enter./);
    assert.match(output, /> \[x\] SigmaReview/);
    assert.match(output, /Search: p/);
    assert.match(output, /Installation cancelled\. No files were written\./);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('cursor and raw mode restore after success, failure, interrupt, EOF, and exceptions', async (t) => {
  const cases = [
    { name: 'success', keys: 'x \r\ry', code: 0, write: true },
    { name: 'interrupt', keys: '\x03', code: 130, write: false },
    { name: 'EOF', keys: '', code: 0, write: false },
  ];

  for (const scenario of cases) {
    await t.test(scenario.name, async () => {
      const projectRoot = sandboxProject();
      try {
        const io = createSimulatedTerminal(scenario.keys);
        const code = await runCli(['--classic', '--project', projectRoot], io);
        assert.equal(code, scenario.code);
        assert.match(io.getStdout(), /\x1b\[\?25h/);
        assert.deepEqual(io.getRawModes(), [true, false]);
        assert.equal(io.stdin.isRaw, false);
        if (scenario.write) {
          assert.ok(fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmareview', 'SKILL.md')));
          const leaves = io.getStdout().match(/\x1b\[\?1049l/g) || [];
          assert.equal(leaves.length, 1);
        } else {
          assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
        }
      } finally {
        fs.rmSync(projectRoot, { recursive: true, force: true });
      }
    });
  }

  await t.test('exception', async () => {
    const projectRoot = sandboxProject();
    try {
      const dest = path.join(projectRoot, '.agents', 'skills', 'sigmareview');
      fs.mkdirSync(dest, { recursive: true });
      fs.writeFileSync(path.join(dest, 'unowned.txt'), 'keep', 'utf8');
      const io = createSimulatedTerminal('x \r\r');
      const code = await runCli(['--classic', '--project', projectRoot], io);
      assert.equal(code, 1);
      assert.match(io.getStderr(), /already exists and is not owned/);
      assert.match(io.getStdout(), /\x1b\[\?25h/);
      assert.deepEqual(io.getRawModes(), [true, false]);
    } finally {
      fs.rmSync(projectRoot, { recursive: true, force: true });
    }
  });
});

test('dynamic cancel leaves the alternate screen before printing persist copy', async () => {
  const projectRoot = sandboxProject();
  try {
    const io = createSimulatedTerminal('x\x1b');
    const code = await runCli(['--classic', '--project', projectRoot], io);
    assert.equal(code, 0);
    const output = io.getStdout();
    const enter = output.match(/\x1b\[\?1049h/g) || [];
    const leave = output.match(/\x1b\[\?1049l/g) || [];
    assert.equal(enter.length, 1);
    assert.equal(leave.length, 1);
    const leaveAt = output.lastIndexOf('\x1b[?1049l');
    const messageAt = output.lastIndexOf('Installation cancelled. No files were written.');
    assert.ok(leaveAt >= 0);
    assert.ok(messageAt > leaveAt);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
