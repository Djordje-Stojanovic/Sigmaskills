import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { getCatalog } from '../src/catalog.js';
import { runCli } from '../src/cli.js';

const PACKAGE_VERSION = JSON.parse(
  fs.readFileSync(fileURLToPath(new URL('../package.json', import.meta.url)), 'utf8'),
).version;

function createMockIo() {
  const stdout = [];
  const stderr = [];
  return {
    stdout: {
      write: (str) => stdout.push(str),
    },
    stderr: {
      write: (str) => stderr.push(str),
    },
    getStdout: () => stdout.join(''),
    getStderr: () => stderr.join(''),
  };
}

test('cli: --version prints package version', async () => {
  const io = createMockIo();
  const exitCode = await runCli(['--version'], io);
  assert.equal(exitCode, 0);
  assert.equal(io.getStdout().trim(), PACKAGE_VERSION);
  assert.equal(io.getStderr(), '');
});

test('cli: -v prints package version', async () => {
  const io = createMockIo();
  const exitCode = await runCli(['-v'], io);
  assert.equal(exitCode, 0);
  assert.equal(io.getStdout().trim(), PACKAGE_VERSION);
});

test('cli: --help prints usage and dynamically lists skills', async () => {
  const io = createMockIo();
  const exitCode = await runCli(['--help'], io);
  assert.equal(exitCode, 0);
  const out = io.getStdout();
  assert.match(out, /Usage:\s+sigmaskills/i);
  assert.match(out, /Options:/i);
  assert.match(out, /Available Skills:/i);
  assert.match(out, /sigmareview/);
  assert.match(out, /sigmaimprove/);
  assert.match(out, /sigmabrief/);
  assert.match(out, /sigmawrite/);
});

test('cli: list --json outputs valid JSON array of skills with revisions', async () => {
  const io = createMockIo();
  const exitCode = await runCli(['list', '--json'], io);
  assert.equal(exitCode, 0);
  const parsed = JSON.parse(io.getStdout());
  assert.ok(Array.isArray(parsed.skills));
  assert.equal(parsed.name, 'sigmaskills');
  assert.equal(parsed.version, PACKAGE_VERSION);

  for (const skill of parsed.skills) {
    assert.ok(skill.id);
    assert.ok(skill.title);
    assert.match(skill.revision, /^[a-f0-9]{64}$/);
  }
});

test('cli: list shows short descriptions for people; list --json keeps the full description', async () => {
  const { skills } = getCatalog();
  const human = createMockIo();
  assert.equal(await runCli(['list'], human), 0);
  const json = createMockIo();
  assert.equal(await runCli(['list', '--json'], json), 0);
  const parsed = JSON.parse(json.getStdout());
  for (const skill of skills) {
    assert.ok(human.getStdout().includes(`  Description: ${skill.shortDescription}\n`), skill.id);
    assert.ok(!human.getStdout().includes(skill.description), `${skill.id} full description stays out of human list`);
    assert.equal(parsed.skills.find((entry) => entry.id === skill.id).description, skill.description);
  }
});

test('cli: verify reports integrity and revisions', async () => {
  const io = createMockIo();
  const exitCode = await runCli(['verify'], io);
  assert.equal(exitCode, 0);
  const out = io.getStdout();
  assert.match(out, /verified/i);
  assert.match(out, /sigmareview/);
  assert.match(out, /sigmawrite/);
});

test('cli: unknown command/flag exits with code 1 and shows error', async () => {
  const io = createMockIo();
  const exitCode = await runCli(['--unknown-flag'], io);
  assert.equal(exitCode, 1);
  assert.match(io.getStderr(), /unknown option or command: --unknown-flag/i);
});
