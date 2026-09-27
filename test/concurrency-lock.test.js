import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { acquireConcurrencyLock } from '../src/transaction.js';

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-lock-race-'));
  const dir = path.join(root, '.agents', '.sigmaskills');
  fs.mkdirSync(dir, { recursive: true });
  return { root, file: path.join(dir, '.sigma.lock') };
}

test('lock: fresh empty and malformed locks are held during the write grace period', () => {
  const { root, file } = fixture();
  try {
    for (const content of ['', '{']) {
      fs.writeFileSync(file, content);
      assert.throws(() => acquireConcurrencyLock(root), /Concurrent SigmaSkills/);
      assert.equal(fs.readFileSync(file, 'utf8'), content);
    }
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('lock: competing stale takeovers have exactly one holder', () => {
  const { root, file } = fixture();
  try {
    fs.writeFileSync(file, JSON.stringify({ pid: 99999999, createdAt: new Date(0).toISOString() }));
    let competed = false;
    const release = acquireConcurrencyLock(root, undefined, {
      beforeTakeover() {
        competed = true;
        const script = `import { acquireConcurrencyLock } from ${JSON.stringify(new URL('../src/transaction.js', import.meta.url).href)};
          try { acquireConcurrencyLock(${JSON.stringify(root)}); process.stdout.write('holder'); }
          catch (err) { process.stdout.write(err.message); }`;
        const second = execFileSync(process.execPath, ['--input-type=module', '-e', script], { encoding: 'utf8' });
        assert.match(second, /Concurrent SigmaSkills/);
      },
    });
    assert.equal(competed, true);
    assert.equal(JSON.parse(fs.readFileSync(file)).pid, process.pid);
    assert.throws(() => acquireConcurrencyLock(root), /Concurrent SigmaSkills/);
    release();
    assert.equal(fs.existsSync(file), false);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('lock: expired records recover and an old release cannot remove a replacement', () => {
  const { root, file } = fixture();
  try {
    fs.writeFileSync(file, JSON.stringify({ pid: process.pid, createdAt: new Date(0).toISOString() }));
    const release = acquireConcurrencyLock(root);
    const replacement = { pid: process.pid, token: 'different-owner', createdAt: new Date().toISOString() };
    fs.writeFileSync(file, JSON.stringify(replacement));
    release();
    assert.deepEqual(JSON.parse(fs.readFileSync(file)), replacement);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('lock: release waits for a competing guard and permits the next operation', async () => {
  const { root, file } = fixture();
  try {
    const release = acquireConcurrencyLock(root);
    fs.mkdirSync(`${file}.guard`);
    const script = `const fs = require('node:fs'); setTimeout(() => fs.rmdirSync(${JSON.stringify(`${file}.guard`)}), 100);`;
    const child = spawn(process.execPath, ['-e', script], { stdio: 'ignore' });
    const exited = new Promise((resolve, reject) => { child.on('error', reject); child.on('exit', resolve); });
    release();
    assert.equal(fs.existsSync(file), false);
    acquireConcurrencyLock(root)();
    assert.equal(await exited, 0);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
