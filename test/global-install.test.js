import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { PassThrough } from 'node:stream';
import test from 'node:test';
import { getCatalog, findPackageRoot } from '../src/catalog.js';
import { runCli } from '../src/cli.js';
import {
  UNIVERSAL_PROJECT_DESTINATION,
  findDestinationConflicts,
  listGlobalDestinationGroups,
  loadHostRegistry,
  resolveGlobalSkillPath,
} from '../src/destinations.js';
import { runProjectInstaller } from '../src/interactive.js';
import { createInstallPlan, formatPlanHuman } from '../src/plan.js';
import {
  STATE_FILENAME,
  loadGlobalState,
  saveGlobalState,
} from '../src/state.js';
import { executeProjectInstall } from '../src/transaction.js';

const ROOT = findPackageRoot();

function sandboxHome() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-global-home-'));
}

function homeEnv(homeDir, extra = {}) {
  return {
    ...process.env,
    ...extra,
    HOME: homeDir,
    USERPROFILE: homeDir,
    CI: extra.CI ?? '',
  };
}

function createMockIo(env) {
  let stdout = '';
  let stderr = '';
  return {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    env,
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

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

function plantSkill(destDir, skillId = 'sigmawrite') {
  fs.mkdirSync(path.dirname(destDir), { recursive: true });
  fs.cpSync(path.join(ROOT, skillId), destDir, { recursive: true });
}

function skillBytes(destDir) {
  const files = {};
  const walk = (dir, prefix = '') => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === '.sigma-backup.json') continue;
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full, rel);
      else files[rel] = fs.readFileSync(full);
    }
  };
  walk(destDir);
  return files;
}

function snapshotTree(root) {
  const files = {};
  if (!fs.existsSync(root)) return files;
  const walk = (dir, prefix = '') => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full, rel);
      else files[rel] = fs.readFileSync(full);
    }
  };
  walk(root);
  return files;
}

test('interactive installer stays on Project Installation until Global is chosen', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-global-default-'));
  try {
    const io = createTerminalIo('\x1b');
    const code = await runCli(['--static', '--no-color', '--project', projectRoot], io);

    assert.equal(code, 0);
    assert.match(io.getStdout(), /Project Installation \(default\)/);
    assert.doesNotMatch(io.getStdout(), /writes skills for this operating-system user/);
    assert.ok(!fs.existsSync(path.join(projectRoot, '.agents')));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('selecting Global Installation shows an immediate scope warning before destinations', async () => {
  const homeDir = sandboxHome();
  try {
    const io = createTerminalIo('g\x1b', { env: homeEnv(homeDir) });
    const code = await runCli(['--static', '--no-color', '--project', homeDir], io);

    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /Global Installation warning/i);
    assert.match(output, /operating-system user/);
    assert.ok(output.indexOf('Global Installation warning') < output.indexOf('Installation cancelled'));
    assert.doesNotMatch(output, /Resolved destinations:/);
    assert.ok(!fs.existsSync(path.join(homeDir, '.agents', 'skills')));
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('final Global confirmation repeats hosts, exact path, method, overwrite, and backup', async () => {
  const homeDir = sandboxHome();
  try {
    const dest = path.join(homeDir, '.agents', 'skills', 'sigmareview');
    const io = createTerminalIo('gy \r\rn', { env: homeEnv(homeDir) });
    const code = await runCli(['--static', '--no-color'], io);

    assert.equal(code, 0);
    const output = io.getStdout();
    assert.match(output, /Confirm Global Installation/);
    assert.match(output, /Agent Hosts:/);
    assert.ok(output.includes(dest));
    assert.match(output, /Method:/);
    assert.match(output, /Overwrite:/);
    assert.match(output, /Delete:/);
    assert.match(output, /Backup:/);
    assert.ok(!fs.existsSync(dest));
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('non-interactive Global mutation requires both --global and --yes', async (t) => {
  const cases = [
    { name: 'global without yes', args: ['install', 'sigmawrite', '--global'] },
    { name: 'CI does not grant authority', args: ['install', 'sigmawrite', '--global'], env: { CI: 'true' } },
    { name: 'JSON does not grant authority', args: ['install', 'sigmawrite', '--global', '--json'] },
  ];

  for (const scenario of cases) {
    await t.test(scenario.name, async () => {
      const homeDir = sandboxHome();
      try {
        const io = createMockIo(homeEnv(homeDir, scenario.env || {}));
        const code = await runCli(scenario.args, io);
        assert.equal(code, 1);
        assert.match(io.getStderr(), /--global and --yes/);
        assert.ok(!fs.existsSync(path.join(homeDir, '.agents', 'skills', 'sigmawrite')));
        assert.ok(!fs.existsSync(path.join(homeDir, '.agents', STATE_FILENAME)));
      } finally {
        fs.rmSync(homeDir, { recursive: true, force: true });
      }
    });
  }
});

test('Agent Host detection and TTY never imply Global Installation authority', async () => {
  const homeDir = sandboxHome();
  try {
    const io = createMockIo(homeEnv(homeDir, { CLAUDE_CODE: '1', CURSOR_TRACE_ID: 'abc' }));
    io.stdout.isTTY = true;
    const code = await runCli(['install', 'sigmawrite', '--global'], io);
    assert.equal(code, 1);
    assert.match(io.getStderr(), /--global and --yes/);
    assert.ok(!fs.existsSync(path.join(homeDir, '.agents', 'skills')));
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('global destination grouping defaults to ~/.agents/skills and keeps host-specific paths unselected', () => {
  const homeDir = sandboxHome();
  try {
    const groups = listGlobalDestinationGroups({
      registry: loadHostRegistry(ROOT),
      homeDir,
      env: homeEnv(homeDir),
    });
    const selected = groups.filter((group) => group.selectedByDefault).map((group) => group.relativeRoot);
    assert.deepEqual(selected, [UNIVERSAL_PROJECT_DESTINATION]);
    const universal = groups.find((group) => group.universal);
    assert.equal(universal.absoluteRoot, path.resolve(homeDir, '.agents', 'skills'));
    const claude = groups.find((group) => group.relativeRoot === '.claude/skills');
    assert.equal(claude.selectedByDefault, false);
    assert.ok(universal.hosts.some((host) => host.id === 'cline'));
    assert.ok(universal.hosts.length >= 1);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('global paths reject traversal, roots, UNC, escapes, collisions, and overlaps', () => {
  const homeDir = sandboxHome();
  try {
    const ok = resolveGlobalSkillPath(homeDir, '.agents/skills', 'sigmawrite');
    assert.equal(ok.destination, path.resolve(homeDir, '.agents', 'skills', 'sigmawrite'));

    assert.throws(() => resolveGlobalSkillPath(homeDir, '../outside', 'sigmawrite'), /traversal|invalid destination|escape/i);
    assert.throws(() => resolveGlobalSkillPath(homeDir, '/', 'sigmawrite'), /root|invalid destination/i);
    assert.throws(() => resolveGlobalSkillPath(homeDir, path.parse(homeDir).root, 'sigmawrite'), /root|invalid destination/i);
    assert.throws(() => resolveGlobalSkillPath(homeDir, '//server/share/skills', 'sigmawrite'), /UNC|invalid destination|escape/i);

    const collisions = findDestinationConflicts({
      projectRoot: homeDir,
      skillIds: ['sigmawrite'],
      selectedRoots: ['.agents/skills', '.agents/skills'],
      isOwned: () => false,
    });
    assert.match(collisions[0], /duplicate/i);

    const overlap = findDestinationConflicts({
      projectRoot: homeDir,
      skillIds: ['sigmawrite'],
      selectedRoots: ['.agents/skills', '.agents/skills/sigmawrite'],
      isOwned: () => false,
    });
    assert.match(overlap[0], /overlap/i);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('unknown newer global state schema fails without mutation', () => {
  const homeDir = sandboxHome();
  try {
    const stateDir = path.join(homeDir, '.agents');
    fs.mkdirSync(stateDir, { recursive: true });
    const statePath = path.join(stateDir, STATE_FILENAME);
    const newer = {
      schemaVersion: 99,
      scope: 'global',
      skills: {
        sigmawrite: {
          revision: 'abc',
          method: 'copy',
          destination: '.agents/skills/sigmawrite',
          ownedPaths: ['.agents/skills/sigmawrite'],
          baseHashes: { 'SKILL.md': 'abc' },
          lastBackup: 'backups/sigmawrite/kept',
        },
      },
    };
    fs.writeFileSync(statePath, `${JSON.stringify(newer, null, 2)}\n`);
    const before = fs.readFileSync(statePath);

    assert.throws(() => loadGlobalState(homeDir), /schemaVersion 99|unsupported.*schema/i);

    const catalog = getCatalog(ROOT);
    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          scope: 'global',
          homeDir,
          packageRoot: ROOT,
        });
      },
      /schemaVersion 99|unsupported.*schema/i,
    );
    assert.deepEqual(fs.readFileSync(statePath), before);
    assert.ok(!fs.existsSync(path.join(homeDir, '.agents', 'skills', 'sigmawrite')));
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('current project-scoped state at the global path is not relabeled as global', () => {
  const homeDir = sandboxHome();
  try {
    const stateDir = path.join(homeDir, '.agents');
    fs.mkdirSync(stateDir, { recursive: true });
    const statePath = path.join(stateDir, STATE_FILENAME);
    const projectState = {
      schemaVersion: 1,
      scope: 'project',
      skills: {
        sigmawrite: {
          revision: 'abc',
          method: 'copy',
          destination: '.agents/skills/sigmawrite',
          ownedPaths: ['.agents/skills/sigmawrite'],
          baseHashes: { 'SKILL.md': 'abc' },
        },
      },
    };
    fs.writeFileSync(statePath, `${JSON.stringify(projectState, null, 2)}\n`);
    const before = fs.readFileSync(statePath);
    assert.throws(() => loadGlobalState(homeDir), /expected scope 'global'/);
    assert.deepEqual(fs.readFileSync(statePath), before);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('supported global state migration keeps ownership, hashes, methods, and backup references', () => {
  const homeDir = sandboxHome();
  try {
    const stateDir = path.join(homeDir, '.agents');
    fs.mkdirSync(stateDir, { recursive: true });
    fs.writeFileSync(path.join(stateDir, STATE_FILENAME), `${JSON.stringify({
      schemaVersion: 0,
      skills: {
        sigmawrite: {
          revision: 'deadbeef',
          method: 'junction',
          destination: '.agents/skills/sigmawrite',
          ownedPaths: ['.agents/skills/sigmawrite'],
          baseHashes: { 'SKILL.md': 'hash-1' },
          backup: 'backups/sigmawrite/old-stamp',
        },
      },
    }, null, 2)}\n`);

    const migrated = loadGlobalState(homeDir);
    assert.equal(migrated.schemaVersion, 1);
    assert.equal(migrated.scope, 'global');
    assert.equal(migrated.skills.sigmawrite.destination, '.agents/skills/sigmawrite');
    assert.equal(migrated.skills.sigmawrite.method, 'junction');
    assert.equal(migrated.skills.sigmawrite.baseHashes['SKILL.md'], 'hash-1');
    assert.equal(migrated.skills.sigmawrite.lastBackup, 'backups/sigmawrite/old-stamp');
    assert.deepEqual(migrated.skills.sigmawrite.ownedPaths, ['.agents/skills/sigmawrite']);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('Global install adopts an exact copy instead of overwriting it', () => {
  const homeDir = sandboxHome();
  try {
    const dest = path.join(homeDir, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    const before = skillBytes(dest);
    const mtime = fs.statSync(path.join(dest, 'SKILL.md')).mtimeMs;

    const catalog = getCatalog(ROOT);
    const result = executeProjectInstall({
      catalog,
      skillId: 'sigmawrite',
      scope: 'global',
      homeDir,
      packageRoot: ROOT,
      env: homeEnv(homeDir),
    });

    assert.equal(result.plan.scope, 'global');
    assert.equal(result.plan.destinations[0].adoption, 'exact-revision');
    assert.deepEqual(skillBytes(dest), before);
    assert.equal(fs.statSync(path.join(dest, 'SKILL.md')).mtimeMs, mtime);
    assert.ok(!fs.existsSync(path.join(homeDir, 'skills-lock.json')));
    const state = loadGlobalState(homeDir);
    assert.equal(state.scope, 'global');
    assert.equal(state.skills.sigmawrite.destination, '.agents/skills/sigmawrite');
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('changed Global trees need replace/skip/export rather than a silent overwrite', () => {
  const homeDir = sandboxHome();
  try {
    const dest = path.join(homeDir, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'keep', 'utf8');
    const before = skillBytes(dest);

    const catalog = getCatalog(ROOT);
    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          scope: 'global',
          homeDir,
          packageRoot: ROOT,
          env: homeEnv(homeDir),
        });
      },
      /replace, skip, or export/,
    );
    assert.deepEqual(skillBytes(dest), before);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('cancellation at either Global confirmation leaves prior global state intact', async () => {
  const homeDir = sandboxHome();
  try {
    const dest = path.join(homeDir, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    const prior = snapshotTree(homeDir);

    const warningCancel = createTerminalIo('gn', { env: homeEnv(homeDir) });
    const warningCode = await runCli(['--static', '--no-color'], warningCancel);
    assert.equal(warningCode, 0);
    assert.match(warningCancel.getStdout(), /Installation cancelled\. No files were written\./);
    assert.deepEqual(snapshotTree(homeDir), prior);

    const finalCancel = createTerminalIo('gy \r\rn', { env: homeEnv(homeDir) });
    const finalCode = await runCli(['--static', '--no-color'], finalCancel);
    assert.equal(finalCode, 0);
    assert.match(finalCancel.getStdout(), /Installation cancelled\. No files were written\./);
    assert.deepEqual(snapshotTree(homeDir), prior);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('injected Global transaction failure restores the prior global state', () => {
  const homeDir = sandboxHome();
  try {
    const dest = path.join(homeDir, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'original', 'utf8');
    const before = skillBytes(dest);
    const catalog = getCatalog(ROOT);

    const originalState = loadGlobalState(homeDir);
    saveGlobalState(homeDir, {
      ...originalState,
      skills: {
        sigmawrite: {
          revision: 'prior',
          method: 'copy',
          destination: '.agents/skills/sigmawrite',
          ownedPaths: ['.agents/skills/sigmawrite'],
          baseHashes: { 'SKILL.md': 'prior' },
          lastBackup: 'backups/sigmawrite/prior',
        },
      },
    });
    const priorState = fs.readFileSync(path.join(homeDir, '.agents', STATE_FILENAME));

    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          scope: 'global',
          homeDir,
          packageRoot: ROOT,
          env: homeEnv(homeDir),
          adoptChanged: 'replace',
          adoptUnverified: 'replace',
          saveState: () => {
            throw new Error('global state write failed');
          },
        });
      },
      /global state write failed/,
    );
    assert.deepEqual(skillBytes(dest), before);
    assert.deepEqual(fs.readFileSync(path.join(homeDir, '.agents', STATE_FILENAME)), priorState);
    assert.ok(!fs.existsSync(path.join(homeDir, 'skills-lock.json')));

    assert.throws(
      () => {
        executeProjectInstall({
          catalog,
          skillId: 'sigmawrite',
          scope: 'global',
          homeDir,
          packageRoot: ROOT,
          env: homeEnv(homeDir),
          adoptChanged: 'replace',
          adoptUnverified: 'replace',
          afterBackup: () => {
            throw new Error('fail after global backup');
          },
        });
      },
      /fail after global backup/,
    );
    assert.deepEqual(skillBytes(dest), before);
    assert.deepEqual(fs.readFileSync(path.join(homeDir, '.agents', STATE_FILENAME)), priorState);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('Global dry-run shows confirmation requirements and full impact without writing', async () => {
  const homeDir = sandboxHome();
  try {
    const dest = path.join(homeDir, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'dry extra', 'utf8');
    const before = snapshotTree(homeDir);

    const io = createMockIo(homeEnv(homeDir));
    const code = await runCli(['install', 'sigmawrite', '--global', '--dry-run'], io);
    assert.equal(code, 0);
    const out = io.getStdout();
    assert.match(out, /Global Installation/);
    assert.match(out, /--global and --yes/);
    assert.match(out, /Dry run complete/);
    assert.ok(out.includes(dest));
    assert.match(out, /Overwrite:|Recognition:/);
    assert.deepEqual(snapshotTree(homeDir), before);

    const jsonIo = createMockIo(homeEnv(homeDir));
    const jsonCode = await runCli(['install', 'sigmawrite', '--global', '--dry-run', '--json'], jsonIo);
    assert.equal(jsonCode, 0);
    const plan = JSON.parse(jsonIo.getStdout());
    assert.equal(plan.scope, 'global');
    assert.equal(plan.dryRun, true);
    assert.deepEqual(plan.confirmationRequirements, ['--global', '--yes']);
    assert.ok(plan.destinations[0].overwrite);
    assert.ok(plan.destinations[0].backup);
    assert.deepEqual(snapshotTree(homeDir), before);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('approved non-interactive Global Installation writes only under the sandboxed home', async () => {
  const homeDir = sandboxHome();
  try {
    const io = createMockIo(homeEnv(homeDir));
    const code = await runCli(['install', 'sigmawrite', '--global', '--yes'], io);
    assert.equal(code, 0);
    assert.ok(fs.existsSync(path.join(homeDir, '.agents', 'skills', 'sigmawrite', 'SKILL.md')));
    assert.ok(!fs.existsSync(path.join(homeDir, 'skills-lock.json')));
    const state = JSON.parse(fs.readFileSync(path.join(homeDir, '.agents', STATE_FILENAME), 'utf8'));
    assert.equal(state.scope, 'global');
    assert.equal(state.schemaVersion, 1);
    assert.match(io.getStdout(), /Global Installation/);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('createInstallPlan global confirmation lists overwrite and backup actions', () => {
  const homeDir = sandboxHome();
  try {
    const dest = path.join(homeDir, '.agents', 'skills', 'sigmawrite');
    plantSkill(dest);
    fs.writeFileSync(path.join(dest, 'extra.md'), 'plan extra', 'utf8');
    const catalog = getCatalog(ROOT);
    const plan = createInstallPlan(catalog, {
      skillId: 'sigmawrite',
      scope: 'global',
      homeDir,
      packageRoot: ROOT,
      dryRun: true,
      env: homeEnv(homeDir),
      adoptUnverified: 'replace',
    });
    assert.equal(plan.scope, 'global');
    assert.match(plan.destinations[0].overwrite, /replace/i);
    assert.match(plan.destinations[0].backup, /backup/i);
    assert.match(plan.destinations[0].delete, /extra\.md|none/i);
    const human = formatPlanHuman(plan);
    assert.match(human, /Overwrite:/);
    assert.match(human, /Backup:/);
    assert.match(human, /--global and --yes/);
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});

test('interactive Global Installation still requires the warning when run through the installer seam', async () => {
  const homeDir = sandboxHome();
  try {
    const io = createTerminalIo('g\x1b', { env: homeEnv(homeDir) });
    const code = await runProjectInstaller({
      catalog: getCatalog(ROOT),
      packageRoot: ROOT,
      projectRoot: homeDir,
      io,
      options: { static: true, noColor: true },
    });
    assert.equal(code, 0);
    assert.match(io.getStdout(), /Global Installation warning/i);
    assert.ok(!fs.existsSync(path.join(homeDir, '.agents', 'skills', 'sigmareview')));
  } finally {
    fs.rmSync(homeDir, { recursive: true, force: true });
  }
});
