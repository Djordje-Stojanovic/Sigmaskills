import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { runProjectInstaller } from '../src/interactive.js';

function createTerminalIo(input, options = {}) {
  const stdin = new PassThrough();
  stdin.isTTY = options.tty ?? false;
  stdin.isRaw = false;
  const rawModes = [];
  stdin.setRawMode = (enabled) => {
    rawModes.push(enabled);
    stdin.isRaw = enabled;
  };

  const stdout = new PassThrough();
  stdout.isTTY = options.tty ?? false;
  stdout.columns = options.columns ?? 100;
  stdout.rows = 30;
  stdout.getColorDepth = () => 24;

  const stderr = new PassThrough();
  let out = '';
  let err = '';
  stdout.setEncoding('utf8');
  stderr.setEncoding('utf8');
  stdout.on('data', (chunk) => {
    out += chunk;
    options.onStdout?.(chunk, out, stdin);
  });
  stderr.on('data', (chunk) => {
    err += chunk;
  });

  if (!options.manualInput) queueMicrotask(() => stdin.end(input));

  return {
    stdin,
    stdout,
    stderr,
    getStdout: () => out,
    getStderr: () => err,
    getRawModes: () => rawModes,
  };
}

test('interactive Project Installation reads the skill picker from the manifest in static no-color mode', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-catalog-'));
  try {
    const io = createTerminalIo('\x1b');
    const code = await runCli(['--static', '--no-color', '--project', projectRoot], io);

    assert.equal(code, 0);
    assert.equal(io.getStderr(), '');
    assert.doesNotMatch(io.getStdout(), /\x1b\[/);
    assert.match(io.getStdout(), /Project Installation \(default\)/);
    assert.match(io.getStdout(), /sigmareview/);
    assert.match(io.getStdout(), /sigmaperformance/);
    assert.match(io.getStdout(), /sigmabrief/);
    assert.match(io.getStdout(), /sigmawrite/);
    assert.match(io.getStdout(), /Installation cancelled\. No files were written\./);
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
    assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('flag-only dry-run and yes invocations do not enter the interactive installer', async (t) => {
  for (const flag of ['--dry-run', '--yes']) {
    await t.test(flag, async () => {
      const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-flag-'));
      try {
        const io = createTerminalIo(' \ry');
        const code = await runCli([flag, '--static', '--project', projectRoot], io);

        assert.equal(code, 1);
        assert.match(io.getStderr(), /sigmaskills error: unknown option or command/);
        assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
        assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
      } finally {
        fs.rmSync(projectRoot, { recursive: true, force: true });
      }
    });
  }
});

test('interactive Project Installation includes future skills supplied by the manifest catalog', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-future-'));
  try {
    const io = createTerminalIo('\x1b');
    const catalog = {
      manifest: { name: 'sigmaskills', version: '0.1.0' },
      skills: [
        { id: 'future-skill', title: 'Future Skill', description: 'A future skill discovered from manifest metadata.' },
      ],
    };
    const code = await runProjectInstaller({
      catalog,
      packageRoot: projectRoot,
      projectRoot,
      io,
      options: { static: true, noColor: true },
    });

    assert.equal(code, 0);
    assert.match(io.getStdout(), /Future Skill \(future-skill\)/);
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('interactive Project Installation confirms exact destinations and installs only the selected subset through the command core', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-install-'));
  try {
    const keys = ' \x1b[B\x1b[B \ry';
    const io = createTerminalIo(keys);
    const code = await runCli(['--static', '--no-color', '--project', projectRoot], io);

    assert.equal(code, 0);
    assert.equal(io.getStderr(), '');

    const reviewDestination = path.join(projectRoot, '.agents', 'skills', 'sigmareview');
    const briefDestination = path.join(projectRoot, '.agents', 'skills', 'sigmabrief');
    const output = io.getStdout();
    assert.match(output, /Resolved destinations:/);
    assert.ok(output.indexOf(reviewDestination) < output.indexOf('Installed SigmaReview'));
    assert.ok(output.indexOf(briefDestination) < output.indexOf('Installed SigmaBrief'));

    assert.ok(fs.existsSync(path.join(reviewDestination, 'SKILL.md')));
    assert.ok(fs.existsSync(path.join(briefDestination, 'SKILL.md')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmaperformance')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite')));

    const lock = JSON.parse(fs.readFileSync(path.join(projectRoot, 'skills-lock.json'), 'utf8'));
    assert.deepEqual(Object.keys(lock.skills), ['sigmabrief', 'sigmareview']);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('interactive Project Installation preflights every selected destination before writing', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-conflict-'));
  const stateDir = path.join(projectRoot, 'private-state');
  const reviewDestination = path.join(projectRoot, '.agents', 'skills', 'sigmareview');
  const briefDestination = path.join(projectRoot, '.agents', 'skills', 'sigmabrief');
  try {
    fs.mkdirSync(briefDestination, { recursive: true });
    fs.writeFileSync(path.join(briefDestination, 'unowned.txt'), 'keep me', 'utf8');

    const io = createTerminalIo(' \x1b[B\x1b[B \ry');
    const code = await runCli([
      '--static',
      '--no-color',
      '--project', projectRoot,
      '--state-dir', stateDir,
    ], io);

    assert.equal(code, 1);
    assert.match(io.getStderr(), /sigmaskills error:.*already exists and is not owned/);
    assert.ok(!fs.existsSync(reviewDestination));
    assert.equal(fs.readFileSync(path.join(briefDestination, 'unowned.txt'), 'utf8'), 'keep me');
    assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
    assert.ok(!fs.existsSync(stateDir));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('Emberforge reveal uses the accepted warm palette and any key skips it', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-reveal-skip-'));
  try {
    const io = createTerminalIo('x\x1b', { tty: true });
    const startedAt = Date.now();
    const code = await runCli(['--project', projectRoot], io);
    const elapsed = Date.now() - startedAt;

    assert.equal(code, 0);
    assert.ok(elapsed < 300, `key skip took ${elapsed} ms`);
    assert.match(io.getStdout(), /\x1b\[48;2;26;23;20m/); // base #1a1714
    assert.match(io.getStdout(), /\x1b\[1;38;2;212;165;100m/); // gold #d4a564
    assert.match(io.getStdout(), /\x1b\[38;2;204;136;68m/); // orange #cc8844
    assert.match(io.getStdout(), /\x1b\[1;38;2;212;100;92m/); // red #d4645c
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('dynamic output separates the final prompt from the installation result', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-dynamic-output-'));
  try {
    const io = createTerminalIo('x \ry', { tty: true });
    const code = await runCli(['--project', projectRoot], io);

    assert.equal(code, 0);
    const output = io.getStdout();
    const finalPrompt = output.lastIndexOf('y confirm · n/enter/esc cancel');
    const installed = output.indexOf('Installed SigmaReview', finalPrompt);
    assert.ok(finalPrompt !== -1 && installed !== -1);
    assert.match(output.slice(finalPrompt, installed), /\n/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('Ctrl+C during the Emberforge reveal cancels before any prompt or write', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-reveal-cancel-'));
  try {
    const io = createTerminalIo('\x03', { tty: true });
    const code = await runCli(['--project', projectRoot], io);

    assert.equal(code, 130);
    assert.match(io.getStdout(), /Installation cancelled\. No files were written\./);
    assert.deepEqual(io.getRawModes(), [true, false]);
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('Emberforge reveal reaches the skill prompt within 700 ms', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-reveal-duration-'));
  try {
    const startedAt = Date.now();
    let resolvePrompt;
    const promptShown = new Promise((resolve) => {
      resolvePrompt = resolve;
    });
    const io = createTerminalIo('', {
      tty: true,
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

test('narrow terminals use the compact Project Installation layout', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-narrow-'));
  try {
    const io = createTerminalIo('\x1b', { columns: 44 });
    const code = await runCli(['--static', '--narrow', '--project', projectRoot], io);

    assert.equal(code, 0);
    assert.match(io.getStdout(), /Project Installation \(default\) · narrow/);
    assert.match(io.getStdout(), /██████████/);
    assert.doesNotMatch(io.getStdout(), /██████████████████/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('escape, EOF, Ctrl+C, and confirmation cancellation write nothing and restore terminal raw mode', async (t) => {
  const cases = [
    { name: 'escape at picker', keys: '\x1b', code: 0 },
    { name: 'EOF at picker', keys: '', code: 0 },
    { name: 'Ctrl+C at picker', keys: '\x03', code: 130 },
    { name: 'cancel at confirmation', keys: ' \rn', code: 0 },
    { name: 'EOF at confirmation', keys: ' \r', code: 0 },
  ];

  for (const scenario of cases) {
    await t.test(scenario.name, async () => {
      const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-cancel-'));
      try {
        const io = createTerminalIo(scenario.keys, { tty: true });
        const code = await runCli(['--static', '--project', projectRoot], io);

        assert.equal(code, scenario.code);
        assert.match(io.getStdout(), /Installation cancelled\. No files were written\./);
        assert.deepEqual(io.getRawModes(), [true, false]);
        assert.equal(io.stdin.isRaw, false);
        assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
        assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
      } finally {
        fs.rmSync(projectRoot, { recursive: true, force: true });
      }
    });
  }
});
