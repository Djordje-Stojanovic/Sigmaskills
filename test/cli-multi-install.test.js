import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { runCli } from '../src/cli.js';

function createMockIo() {
  let stdout = '';
  let stderr = '';
  return {
    stdout: { write: (s) => { stdout += s; } },
    stderr: { write: (s) => { stderr += s; } },
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

function tempProject(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-multi-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

test('cli: unknown skill ids fail with unknown skill before planning, for every command', async (t) => {
  const projectRoot = tempProject(t);
  const commands = [
    ['install', 'sigmawrite', 'nope', '--yes'],
    ['add', 'nope'],
    ['install', '--skill', 'nope', '--dry-run'],
    ['update', '--skill', 'nope', '--yes'],
    ['restore', '--skill', 'nope', '--yes'],
    ['uninstall', '--skill', 'nope', '--yes'],
    ['uninstall', 'nope', '--dry-run'],
  ];
  for (const args of commands) {
    const io = createMockIo();
    const code = await runCli([...args, '--project', projectRoot], io);
    assert.equal(code, 1, args.join(' '));
    assert.match(io.getStderr(), /sigmaskills error: unknown skill 'nope'/, args.join(' '));
    assert.doesNotMatch(io.getStderr(), /stale-state/);
    assert.equal(io.getStdout(), '', args.join(' '));
    assert.deepEqual(fs.readdirSync(projectRoot), [], args.join(' '));
  }
});

test('cli: uninstall still accepts a retired skill id', async (t) => {
  const projectRoot = tempProject(t);
  const io = createMockIo();
  await runCli(['uninstall', '--skill', 'sigmaperformance', '--dry-run', '--project', projectRoot], io);
  assert.doesNotMatch(io.getStderr(), /unknown skill/);
});
