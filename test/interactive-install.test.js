import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { runCli } from '../src/cli.js';
import { runProjectInstaller } from '../src/interactive.js';
import { getCatalog, findPackageRoot } from '../src/catalog.js';

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

  const env = { ...(options.env ?? process.env), CI: options.env?.CI ?? '' };
  delete env.NO_COLOR;
  if (options.tty && (!env.TERM || env.TERM === 'dumb')) {
    env.TERM = 'xterm-256color';
  }

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
    const keys = ' \x1b[B\x1b[B \r\ry';
    const io = createTerminalIo(keys);
    const code = await runCli(['--static', '--no-color', '--project', projectRoot], io);

    assert.equal(code, 0);
    assert.equal(io.getStderr(), '');

    const reviewDestination = path.join(projectRoot, '.agents', 'skills', 'sigmareview');
    const briefDestination = path.join(projectRoot, '.agents', 'skills', 'sigmabrief');
    const output = io.getStdout();
    assert.match(output, /Resolved destinations:/);
    assert.match(output, /Only \.agents\/skills is selected by default/);
    assert.match(output, /\.agents\/skills\s+\(universal default/);
    assert.match(output, /\d+ hosts/);
    assert.match(output, /\[ \] \.claude\/skills/);
    assert.match(output, /\[ \] \.pi\/skills/);
    assert.ok(output.indexOf(reviewDestination) < output.indexOf('Installed SigmaReview'));
    assert.ok(output.indexOf(briefDestination) < output.indexOf('Installed SigmaBrief'));

    assert.ok(fs.existsSync(path.join(reviewDestination, 'SKILL.md')));
    assert.ok(fs.existsSync(path.join(briefDestination, 'SKILL.md')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmaperformance')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmawrite')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.claude')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.pi')));

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

    const io = createTerminalIo(' \x1b[B\x1b[B \r\ry');
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
    const io = createTerminalIo('x\x1b', { tty: true, env: { ...process.env, CI: '' } });
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
    const io = createTerminalIo('x \r\ry', { tty: true });
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
    { name: 'cancel at confirmation', keys: ' \r\rn', code: 0 },
    { name: 'EOF at confirmation', keys: ' \r\r', code: 0 },
    { name: 'escape at destinations', keys: ' \r\x1b', code: 0 },
    { name: 'EOF at destinations', keys: ' \r', code: 0 },
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

test('interactive destinations keep every Agent Host searchable and never auto-select host-specific paths', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-search-'));
  try {
    const io = createTerminalIo(' \rp\x1b\x1b');
    const code = await runCli(['--static', '--no-color', '--project', projectRoot], io);

    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /Search: p/);
    assert.match(output, /Pi \(pi\)/);
    assert.match(output, /\.pi\/skills/);
    assert.match(output, /Type to search every Agent Host/);
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.pi')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('interactive destination search groups matching hosts that share one path', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-search-group-'));
  try {
    const io = createTerminalIo(' \rc\x1b\x1b');
    const code = await runCli(['--static', '--no-color', '--project', projectRoot], io);

    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /Search: c/);
    const start = output.lastIndexOf('Search: c');
    assert.ok(start >= 0);
    const rest = output.slice(start);
    const end = rest.search(/\nType a host name/);
    const searchView = end >= 0 ? rest.slice(0, end) : rest;
    const universalRows = searchView.match(/\[x\] \.agents\/skills/g) || [];
    assert.equal(universalRows.length, 1, 'shared .agents/skills matches must be one row');
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('interactive destinations label detected hosts without selecting them', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-detected-'));
  try {
    const catalog = {
      manifest: { name: 'sigmaskills', version: '0.1.0' },
      skills: [
        { id: 'future-skill', title: 'Future Skill', description: 'A future skill discovered from manifest metadata.' },
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
          detection: { envVars: ['AMP_PRESENT'] },
        },
        {
          id: 'claude-code',
          name: 'claude-code',
          displayName: 'Claude Code',
          destinations: { project: { kind: 'literal', path: '.claude/skills' }, global: { kind: 'none' } },
          aliases: [],
          detection: { envVars: ['CLAUDE_CODE'] },
        },
      ],
    };
    const io = createTerminalIo(' \r\x1b', { env: { ...process.env, CI: '', CLAUDE_CODE: '1', AMP_PRESENT: '1' } });
    const code = await runProjectInstaller({
      catalog,
      registry,
      packageRoot: projectRoot,
      projectRoot,
      io,
      options: { static: true, noColor: true },
    });

    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /Claude Code \(claude-code\) \[detected\]/);
    assert.match(output, /\[ \] \.claude\/skills/);
    assert.match(output, /\[x\] \.agents\/skills/);
    assert.match(output, /1 detected/);
    assert.ok(!fs.existsSync(path.join(projectRoot, '.claude')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('interactive destinations install a Claude Code link only after an explicit choice', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-claude-'));
  try {
    const io = createTerminalIo(' \rclaude-code \r\ry');
    const code = await runCli(['--static', '--no-color', '--project', projectRoot], io);

    assert.equal(code, 0);
    assert.match(io.getStdout(), /Link \(recommended\)/);
    assert.ok(fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmareview', 'SKILL.md')));
    assert.ok(fs.lstatSync(path.join(projectRoot, '.claude', 'skills', 'sigmareview')).isSymbolicLink());
    assert.ok(!fs.existsSync(path.join(projectRoot, '.pi')));
    const state = JSON.parse(fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8'));
    const copies = state.skills.sigmareview.copies;
    assert.equal(copies.length, 2);
    assert.ok(copies.some((copy) => copy.destination === '.claude/skills/sigmareview' && copy.kind === 'host' && copy.dependsOn === '.agents/skills/sigmareview'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('interactive link failure reports the exact cause and declining copy writes nothing', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-link-fail-'));
  try {
    const io = createTerminalIo(' \rclaude-code \r\ryn');
    const code = await runProjectInstaller({
      catalog: getCatalog(findPackageRoot()),
      packageRoot: findPackageRoot(),
      projectRoot,
      io,
      options: { static: true, noColor: true },
      createLink: () => {
        throw Object.assign(new Error('EPERM: operation not permitted, symlink'), { code: 'EPERM' });
      },
    });

    assert.equal(code, 0);
    assert.match(io.getStdout(), /EPERM: operation not permitted/);
    assert.match(io.getStdout(), /will not change method silently/);
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmareview')));
    assert.ok(!fs.existsSync(path.join(projectRoot, '.claude', 'skills', 'sigmareview')));
    assert.ok(!fs.existsSync(path.join(projectRoot, 'skills-lock.json')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('interactive link failure copy fallback writes an independent managed copy', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-interactive-link-copy-'));
  try {
    const io = createTerminalIo(' \rclaude-code \r\ryy');
    const code = await runProjectInstaller({
      catalog: getCatalog(findPackageRoot()),
      packageRoot: findPackageRoot(),
      projectRoot,
      io,
      options: { static: true, noColor: true },
      createLink: () => {
        throw Object.assign(new Error('EPERM: operation not permitted, symlink'), { code: 'EPERM' });
      },
    });

    assert.equal(code, 0);
    const host = path.join(projectRoot, '.claude', 'skills', 'sigmareview');
    assert.equal(fs.lstatSync(host).isSymbolicLink(), false);
    assert.ok(fs.existsSync(path.join(host, 'SKILL.md')));
    const state = JSON.parse(fs.readFileSync(path.join(projectRoot, '.agents', 'state.json'), 'utf8'));
    const hostCopy = state.skills.sigmareview.copies.find((copy) => copy.kind === 'host');
    assert.equal(hostCopy.method, 'copy');
    assert.equal(hostCopy.dependsOn, null);
    assert.ok(hostCopy.baseHashes['SKILL.md']);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
