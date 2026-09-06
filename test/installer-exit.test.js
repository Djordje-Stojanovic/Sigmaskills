import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import test from 'node:test';

const ROOT = path.resolve(import.meta.dirname, '..');
const BIN = path.join(ROOT, 'bin', 'sigmaskills.js');

test('interactive child exits after confirmation while stdin stays open', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-installer-exit-'));
  const child = spawn(process.execPath, [BIN, '--static', '--no-color', '--project', projectRoot], {
    cwd: ROOT,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let stdout = '';
  let stderr = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', (chunk) => { stdout += chunk; });
  child.stderr.on('data', (chunk) => { stderr += chunk; });

  try {
    child.stdin.write(' \r\ry');
    const result = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        child.kill();
        reject(new Error(`installer did not exit while stdin stayed open\nstdout: ${stdout}\nstderr: ${stderr}`));
      }, 2000);
      child.once('error', (error) => {
        clearTimeout(timer);
        reject(error);
      });
      child.once('close', (code, signal) => {
        clearTimeout(timer);
        resolve({ code, signal });
      });
    });

    assert.equal(result.signal, null);
    assert.equal(result.code, 0, stderr);
    assert.ok(fs.existsSync(path.join(projectRoot, '.agents', 'skills', 'sigmareview', 'SKILL.md')));
  } finally {
    child.stdin.destroy();
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
