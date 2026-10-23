import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { buildHelpText, parseCliArgs, runCli } from '../src/cli.js';
import { getCatalog } from '../src/catalog.js';
import { ACME_PACK, createMockIo, createSandbox, writeUserConfig } from './pack-fixtures.js';

async function run(box, args) {
  const io = createMockIo(box.env);
  const code = await runCli([...args, '--project', box.project, '--no-color'], io);
  return { code, out: io.getStdout(), err: io.getStderr() };
}

test('parse: --preset, --pack, --agent, -a, --force, --classic and --packs', () => {
  const parsed = parseCliArgs(['install', '--preset', 'sigma,matt', '--pack', 'threejs', '-a', 'claude', '--agent=codex', '--force', '--classic']);
  assert.equal(parsed.command, 'install');
  assert.deepEqual(parsed.presets, ['sigma,matt', 'threejs']);
  assert.deepEqual(parsed.agents, ['claude', 'codex']);
  assert.equal(parsed.force, true);
  assert.equal(parsed.classic, true);
  assert.equal(parseCliArgs(['list', '--packs']).packs, true);
  assert.throws(() => parseCliArgs(['install', '--preset']), /--preset requires a value/);
  assert.throws(() => parseCliArgs(['install', '--agent', '--copy']), /--agent requires a value/);
  assert.deepEqual(parseCliArgs(['install', 'sigmawrite']).presets, []);
});

test('help: lists the presets, agents and force flags', () => {
  const text = buildHelpText(getCatalog());
  assert.match(text, /--preset <pack>/);
  assert.match(text, /-a, --agent <host>/);
  assert.match(text, /--force/);
  assert.match(text, /sigmaskills install --preset sigma --preset mattpocock --agent claude/);
});

test('list --packs: prints every pack, and --json prints the same data', async () => {
  const box = createSandbox();
  try {
    writeUserConfig(box.home, { packs: [ACME_PACK] });
    const human = await run(box, ['list', '--packs']);
    assert.equal(human.code, 0, human.err);
    assert.match(human.out, /Matt Pocock\s+38 skills/);
    assert.match(human.out, /--preset threejs/);
    assert.match(human.out, /Acme\s+2 skills/);
    assert.match(human.out, /Local.*not available/);
    assert.match(human.out, /--preset all/);

    const json = await run(box, ['list', '--packs', '--json']);
    const parsed = JSON.parse(json.out);
    assert.equal(parsed.packs.find((pack) => pack.id === 'local').available, false);
    assert.equal(parsed.packs.find((pack) => pack.id === 'hyperframes').skills.length, 18);
  } finally {
    box.cleanup();
  }
});

test('install: an unknown preset names the choices', async () => {
  const box = createSandbox();
  try {
    const { code, err } = await run(box, ['install', '--preset', 'nope']);
    assert.equal(code, 1);
    assert.match(err, /unknown preset 'nope'/);
    assert.match(err, /mattpocock/);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents')));
  } finally {
    box.cleanup();
  }
});

test('install: an unavailable pack stops with the reason', async () => {
  const box = createSandbox();
  try {
    const { code, err } = await run(box, ['install', '--preset', 'local']);
    assert.equal(code, 1);
    assert.match(err, /pack 'local' is not available on this machine/);
    assert.match(err, /SIGMA_LOCAL_SKILLS_DIR/);
  } finally {
    box.cleanup();
  }
});

test('install: an unknown agent suggests close names', async () => {
  const box = createSandbox();
  try {
    const { code, err } = await run(box, ['install', 'sigmawrite', '--agent', 'claud']);
    assert.equal(code, 1);
    assert.match(err, /unknown agent 'claud'/);
    assert.match(err, /claude-code/);
  } finally {
    box.cleanup();
  }
});

test('install: --preset sigma needs no network and --agent adds the host folder', async () => {
  const box = createSandbox();
  try {
    const { code, out, err } = await run(box, ['install', '--preset', 'sigma', '--agent', 'claude,codex']);
    assert.equal(code, 0, err);
    const count = getCatalog().skills.length;
    assert.match(out, new RegExp(`${count} skills installed`));
    assert.match(out, /\.claude\/skills\s+linked\s+Claude Code/);
    assert.ok(fs.existsSync(path.join(box.project, '.agents', 'skills', 'sigmawrite', 'SKILL.md')));
    assert.ok(fs.existsSync(path.join(box.project, '.claude', 'skills', 'sigmawrite', 'SKILL.md')));
    assert.ok(!fs.existsSync(path.join(box.project, '.codex')), 'Codex reads .agents/skills and needs no folder');
  } finally {
    box.cleanup();
  }
});

test('install: --global --agent agy writes a real copy in ~/.gemini/config/skills, a junction is invisible to agy', async () => {
  const box = createSandbox();
  try {
    const { code, out, err } = await run(box, ['install', 'sigmawrite', '--global', '--yes', '--agent', 'agy']);
    assert.equal(code, 0, err);
    assert.match(out, /\.gemini\/config\/skills\s+copy\s+Antigravity CLI/);
    const folder = path.join(box.home, '.gemini', 'config', 'skills', 'sigmawrite');
    assert.ok(fs.existsSync(path.join(folder, 'SKILL.md')));
    assert.ok(!fs.lstatSync(folder).isSymbolicLink(), 'a real folder, not a link');
  } finally {
    box.cleanup();
  }
});

test('install: --all still means every Sigma skill and keeps the old output', async () => {
  const box = createSandbox();
  try {
    const { code, out } = await run(box, ['install', '--all']);
    assert.equal(code, 0);
    assert.match(out, /✔ Installed SigmaWrite \(sigmawrite\)/);
  } finally {
    box.cleanup();
  }
});

test('install: --all with skill ids and an empty preset list are refused', async () => {
  const box = createSandbox();
  try {
    const both = await run(box, ['install', 'sigmawrite', '--all', '--preset', 'sigma']);
    assert.equal(both.code, 1);
    assert.match(both.err, /install --all cannot be combined with skill ids/);
    const none = await run(box, ['install', '--agent', 'claude']);
    assert.equal(none.code, 1);
    assert.match(none.err, /missing required skill name for install command/);
  } finally {
    box.cleanup();
  }
});

test('install: a preset without a command installs too', async () => {
  const box = createSandbox();
  try {
    const { code, err } = await run(box, ['--preset', 'sigma', '--dry-run']);
    assert.equal(code, 0, err);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents')));
  } finally {
    box.cleanup();
  }
});

test('install: an unknown skill id mentions packs', async () => {
  const box = createSandbox();
  try {
    const { code, err } = await run(box, ['install', 'not-a-skill']);
    assert.equal(code, 1);
    assert.match(err, /unknown skill 'not-a-skill'/);
    assert.match(err, /list --packs/);
  } finally {
    box.cleanup();
  }
});

test('uninstall and update: Sigma skills and an unknown id keep their old behavior', async () => {
  const box = createSandbox();
  try {
    await run(box, ['install', 'sigmawrite']);
    const unknown = await run(box, ['uninstall', '--skill', 'ghost', '--yes']);
    assert.equal(unknown.code, 1);
    assert.match(unknown.err, /unknown skill 'ghost'/);
    const removed = await run(box, ['uninstall', '--skill', 'sigmawrite', '--yes']);
    assert.equal(removed.code, 0, removed.err);
    assert.ok(!fs.existsSync(path.join(box.project, '.agents', 'skills', 'sigmawrite')));
    const update = await run(box, ['update', '--dry-run']);
    assert.equal(update.code, 0, update.err);
  } finally {
    box.cleanup();
  }
});
