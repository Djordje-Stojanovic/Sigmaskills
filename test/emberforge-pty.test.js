import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { runProjectInstaller } from '../src/interactive.js';

function createPty(input, options = {}) {
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

  if (!options.manualInput) queueMicrotask(() => stdin.end(input));

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

test('Emberforge keeps the warm LAPI palette and does not blend Prismgrid or Monolith', async () => {
  const projectRoot = sandboxProject();
  try {
    const io = createPty('\x1b');
    const code = await runCli(['--project', projectRoot], io);

    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /\x1b\[48;2;26;23;20m/);
    assert.match(output, /\x1b\[1;38;2;212;165;100m/);
    assert.match(output, /\x1b\[38;2;204;136;68m/);
    assert.match(output, /\x1b\[1;38;2;212;100;92m/);
    assert.match(output, /SIGMA SKILLS/);
    assert.doesNotMatch(output, /SIG\/\/SYS/);
    assert.doesNotMatch(output, /PRISMGRID/i);
    assert.doesNotMatch(output, /MONOLITH/i);
    assert.doesNotMatch(output, /holographic/i);
    assert.doesNotMatch(output, /scanline/i);
    assert.doesNotMatch(output, /chiseled/i);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('reduced motion, CI, NO_COLOR, and JSON disable Emberforge animation and decoration', async (t) => {
  const cases = [
    {
      name: 'REDUCED_MOTION',
      args: (projectRoot) => ['--project', projectRoot],
      options: { env: { REDUCED_MOTION: '1' } },
      expectJson: false,
    },
    {
      name: 'prefers-reduced-motion',
      args: (projectRoot) => ['--project', projectRoot],
      options: { env: { PREFERS_REDUCED_MOTION: 'reduce' } },
      expectJson: false,
    },
    {
      name: 'CI',
      args: (projectRoot) => ['--project', projectRoot],
      options: { env: { CI: 'true' } },
      expectJson: false,
    },
    {
      name: 'NO_COLOR',
      args: (projectRoot) => ['--project', projectRoot],
      options: { forceNoColor: true },
      expectJson: false,
    },
    {
      name: 'JSON',
      args: () => ['--json'],
      options: {},
      expectJson: true,
    },
  ];

  for (const scenario of cases) {
    await t.test(scenario.name, async () => {
      const projectRoot = sandboxProject();
      try {
        const io = createPty('\x1b', scenario.options);
        const code = await runCli(scenario.args(projectRoot), io);
        assert.equal(code, 0);
        const output = io.getStdout();
        assert.doesNotMatch(output, /\x1b\[\?25l/);
        assert.doesNotMatch(output, /\x1b\[2J/);
        if (scenario.expectJson) {
          const parsed = JSON.parse(output);
          assert.equal(parsed.name, 'sigmaskills');
          assert.doesNotMatch(output, /\x1b\[/);
        } else {
          assert.match(output, /Select skills from this Skill Pack:/);
          assert.match(output, /Installation cancelled\. No files were written\./);
        }
        if (scenario.name === 'NO_COLOR' || scenario.name === 'JSON') {
          assert.doesNotMatch(output, /\x1b\[/);
        }
      } finally {
        fs.rmSync(projectRoot, { recursive: true, force: true });
      }
    });
  }
});

test('truecolor, 256-color, basic color, and ASCII fallbacks stay readable and keep safety copy', async (t) => {
  const cases = [
    {
      name: 'truecolor',
      colorDepth: 24,
      match: /\x1b\[38;2;/,
      reject: null,
      ascii: false,
    },
    {
      name: '256-color',
      colorDepth: 8,
      match: /\x1b\[38;5;/,
      reject: /\x1b\[38;2;/,
      ascii: false,
    },
    {
      name: 'basic color',
      colorDepth: 4,
      match: /\x1b\[(?:1;)?3[1-7]m/,
      reject: /\x1b\[38;/,
      ascii: false,
    },
    {
      name: 'ASCII',
      colorDepth: 1,
      match: /Select at least one skill\./,
      reject: /\x1b\[/,
      ascii: true,
    },
  ];

  for (const scenario of cases) {
    await t.test(scenario.name, async () => {
      const projectRoot = sandboxProject();
      try {
        const io = createPty('x\r\x1b', { colorDepth: scenario.colorDepth });
        const code = await runCli(['--project', projectRoot], io);
        assert.equal(code, 0);
        const output = io.getStdout();
        assert.match(output, scenario.match);
        assert.match(output, /Select at least one skill\./);
        assert.match(output, /g Global Installation/);
        if (scenario.reject) assert.doesNotMatch(output, scenario.reject);
        if (scenario.ascii) {
          assert.doesNotMatch(output, /█/);
          assert.doesNotMatch(output, /Σ/);
          assert.match(output, /SIGMA SKILLS/);
        }
      } finally {
        fs.rmSync(projectRoot, { recursive: true, force: true });
      }
    });
  }
});

test('bounded PTY skip-any-key reveal stays under the 700 ms motion ceiling', async () => {
  const projectRoot = sandboxProject();
  try {
    const startedAt = Date.now();
    const io = createPty('x\x1b');
    const code = await runCli(['--project', projectRoot], io);
    const elapsed = Date.now() - startedAt;
    assert.equal(code, 0);
    assert.ok(elapsed < 300, `key skip took ${elapsed} ms`);
    assert.match(io.getStdout(), /Select skills from this Skill Pack:/);
    assert.match(io.getStdout(), /Installation cancelled\. No files were written\./);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('bounded PTY Emberforge reveal reaches the skill prompt within 700 ms without a skip key', async () => {
  const projectRoot = sandboxProject();
  try {
    const startedAt = Date.now();
    let resolvePrompt;
    const promptShown = new Promise((resolve) => {
      resolvePrompt = resolve;
    });
    const io = createPty('', {
      manualInput: true,
      onStdout: (_chunk, output, stdin) => {
        if (output.includes('Select skills from this Skill Pack:')) {
          resolvePrompt(Date.now() - startedAt);
          stdin.end('\x1b');
        }
      },
    });
    const run = runCli(['--project', projectRoot], io);
    const revealElapsed = await promptShown;
    const code = await run;
    assert.equal(code, 0);
    assert.ok(revealElapsed <= 750, `reveal took ${revealElapsed} ms`);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('layouts reflow on resize and wrap long paths at the documented 76-column narrow width', async () => {
  const projectRoot = sandboxProject();
  try {
    let resized = false;
    const io = createPty('', {
      columns: 100,
      manualInput: true,
      onStdout: (_chunk, output, stdin, stdout) => {
        if (!resized && output.includes('Select skills from this Skill Pack:')) {
          resized = true;
          stdout.columns = 44;
          stdout.emit('resize');
          queueMicrotask(() => stdin.end('\x1b'));
        }
      },
    });
    const catalog = {
      manifest: { name: 'sigmaskills', version: '0.1.0' },
      skills: [
        {
          id: 'future-skill',
          title: 'Future Skill',
          description: 'short',
        },
      ],
    };
    const registry = {
      schemaVersion: 1,
      hosts: [
        {
          id: 'amp',
          name: 'amp',
          displayName: 'Amp',
          destinations: { project: { kind: 'literal', path: '.agents/skills' }, global: { kind: 'none' } },
          aliases: [],
          detection: { envVars: [] },
        },
      ],
    };
    const code = await runProjectInstaller({
      catalog,
      registry,
      packageRoot: projectRoot,
      projectRoot,
      io,
      options: {},
    });
    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /· narrow/);
    assert.match(output, /██████████|#{10}/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('long destination paths wrap instead of overflowing the documented narrow width', async () => {
  const projectRoot = sandboxProject();
  try {
    const longToken = 'x'.repeat(90);
    const catalog = {
      manifest: { name: 'sigmaskills', version: '0.1.0' },
      skills: [
        { id: 'future-skill', title: 'Future Skill', description: longToken },
      ],
    };
    const io = createPty('\x1b', { columns: 44, colorDepth: 1 });
    const code = await runProjectInstaller({
      catalog,
      packageRoot: projectRoot,
      projectRoot,
      io,
      options: { static: true, narrow: true },
    });
    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, / · narrow/);
    const descriptionLines = output.split('\n').filter((line) => line.startsWith('      x'));
    assert.ok(descriptionLines.length >= 2, 'long description should wrap onto more than one line');
    for (const line of descriptionLines) {
      assert.ok(line.length <= 50, `wrapped line too long: ${line.length}`);
    }
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('keyboard help, focus, search, selection, confirmation, and cancellation stay available without a mouse', async () => {
  const projectRoot = sandboxProject();
  try {
    const io = createPty('x?x \rp\x1b\x1b');
    const code = await runCli(['--project', projectRoot], io);
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
    assert.match(output, /any key skips the opening reveal/);
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
        const io = createPty(scenario.keys);
        const code = await runCli(['--project', projectRoot], io);
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
      const io = createPty('x \r\r');
      const code = await runCli(['--project', projectRoot], io);
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
    const io = createPty('x\x1b');
    const code = await runCli(['--project', projectRoot], io);
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

test('dynamic destination picker windows a short terminal and shows a path status line', async () => {
  const projectRoot = sandboxProject();
  try {
    let phase = 0;
    const io = createPty('', {
      rows: 16,
      columns: 80,
      manualInput: true,
      onStdout: (_chunk, output, stdin) => {
        if (phase === 0 && output.includes('Select skills from this Skill Pack:')) {
          phase = 1;
          stdin.write(' \r');
        }
        if (phase === 1 && output.includes('Project Installation · destinations')) {
          phase = 2;
          stdin.end('\x1b');
        }
      },
    });
    const code = await runCli(['--project', projectRoot], io);
    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /Showing \d+–\d+ of \d+/);
    assert.match(output, /Path:/);
    const leave = output.match(/\x1b\[\?1049l/g) || [];
    assert.equal(leave.length, 1);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
