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
    stdout: {
      write: (s) => {
        stdout += s;
      },
    },
    stderr: {
      write: (s) => {
        stderr += s;
      },
    },
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

test('cli: install --dry-run prints plan without writing files', async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cli-dry-'));
  try {
    const io = createMockIo();
    const code = await runCli(['install', 'sigmawrite', '--dry-run', '--project', tmpDir], io);

    assert.equal(code, 0);
    assert.match(io.getStdout(), /SigmaSkills Project Installation Plan: SigmaWrite/);
    assert.match(io.getStdout(), /Dry run complete/);
    assert.ok(!fs.existsSync(path.join(tmpDir, '.agents')));
    assert.ok(!fs.existsSync(path.join(tmpDir, 'skills-lock.json')));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('cli: install --dry-run --json prints versioned JSON plan', async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cli-dry-json-'));
  try {
    const io = createMockIo();
    const code = await runCli(['install', 'sigmabrief', '--dry-run', '--json', '--project', tmpDir], io);

    assert.equal(code, 0);
    const parsed = JSON.parse(io.getStdout());
    assert.equal(parsed.schemaVersion, 1);
    assert.equal(parsed.skill, 'sigmabrief');
    assert.equal(parsed.scope, 'project');
    assert.equal(parsed.dryRun, true);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('cli: install <skill> performs actual installation into project', async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cli-install-'));
  try {
    const io = createMockIo();
    const code = await runCli(['install', 'sigmawrite', '--project', tmpDir], io);

    assert.equal(code, 0);
    assert.match(io.getStdout(), /Installed SigmaWrite \(sigmawrite\) to \.agents\/skills\/sigmawrite/);
    assert.ok(fs.existsSync(path.join(tmpDir, '.agents', 'skills', 'sigmawrite', 'SKILL.md')));
    assert.ok(fs.existsSync(path.join(tmpDir, 'skills-lock.json')));
    assert.ok(fs.existsSync(path.join(tmpDir, '.agents', 'state.json')));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('cli: add <skill> is alias for install', async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cli-add-'));
  try {
    const io = createMockIo();
    const code = await runCli(['add', 'sigmabrief', '--project', tmpDir], io);

    assert.equal(code, 0);
    assert.match(io.getStdout(), /Installed SigmaBrief \(sigmabrief\)/);
    assert.ok(fs.existsSync(path.join(tmpDir, '.agents', 'skills', 'sigmabrief', 'SKILL.md')));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('cli: install missing skill argument reports error', async () => {
  const io = createMockIo();
  const code = await runCli(['install'], io);

  assert.equal(code, 1);
  assert.match(io.getStderr(), /missing required skill name for install command/);
});

test('cli: install unknown skill reports error', async () => {
  const io = createMockIo();
  const code = await runCli(['install', 'nonexistent-skill'], io);

  assert.equal(code, 1);
  assert.match(io.getStderr(), /skill 'nonexistent-skill' was not found/);
});
