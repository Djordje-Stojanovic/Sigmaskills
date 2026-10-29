import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const skill = join(root, 'sigmaspeedloop');
const template = join(skill, 'assets', 'project-template');

function filesUnder(dir) {
  return fs.readdirSync(dir, { recursive: true }).map((rel) => join(dir, rel)).filter((p) => fs.statSync(p).isFile());
}

function findPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const r = spawnSync(cmd, ['-c', 'import sys; print(sys.version_info >= (3, 8))'], { encoding: 'utf8' });
    if (r.status === 0 && r.stdout.trim() === 'True') return cmd;
  }
  return null;
}

// The skill is shared, so it must carry no keys, no tokens and no one person's machine paths.
test('sigmaspeedloop holds no keys, tokens or personal paths', () => {
  const secret = [/\bhf_[A-Za-z0-9]{30,}\b/, /\b[a-f0-9]{64}\b/, /\bsk-[A-Za-z0-9]{20,}\b/, /BEGIN [A-Z ]*PRIVATE KEY/];
  const personal = [/C:\\Users\\[^\\<\s]+\\/i, /\/home\/[a-z0-9_-]+\//, /%APPDATA%\\Python\\Python3\d+/i];
  for (const p of filesUnder(skill)) {
    const text = fs.readFileSync(p, 'utf8');
    const rel = relative(root, p);
    for (const re of secret) assert.doesNotMatch(text, re, `${rel} looks like it holds a secret (${re})`);
    for (const re of personal) assert.doesNotMatch(text, re, `${rel} holds a personal path (${re})`);
  }
});

// Every helper the template copies into a new project must at least parse.
test('sigmaspeedloop template Python files compile', (t) => {
  const python = findPython();
  if (!python) {
    t.skip('python 3.8+ not found');
    return;
  }
  const scripts = filesUnder(template).filter((p) => p.endsWith('.py'));
  assert.ok(scripts.length >= 10, 'expected the template scripts');
  const code = 'import ast, sys\nfor p in sys.argv[1:]:\n    ast.parse(open(p, encoding="utf-8").read(), p)\n';
  const r = spawnSync(python, ['-c', code, ...scripts], { encoding: 'utf8' });
  assert.equal(r.status, 0, (r.stdout || '') + (r.stderr || ''));
});

// The template's score weights are the ones the verdict reads; they must add up to 1.
test('sigmaspeedloop template weights add up to 1 and match the verdict components', () => {
  const project = JSON.parse(fs.readFileSync(join(template, 'project.json'), 'utf8'));
  const sum = Object.values(project.weights).reduce((a, b) => a + b, 0);
  assert.ok(Math.abs(sum - 1) < 1e-9, `weights add up to ${sum}`);
  const verdict = fs.readFileSync(join(template, 'scripts', 'bench', 'verdict.py'), 'utf8');
  for (const name of Object.keys(project.weights)) assert.match(verdict, new RegExp(`"${name}"`), `verdict.py has no "${name}" component`);
});

// The lock step must run on baseline runs, and the verdict must read the bands it wrote.
test('sigmaspeedloop aa.py locks the evaluator and verdict.py reads the lock', (t) => {
  const python = findPython();
  if (!python) {
    t.skip('python 3.8+ not found');
    return;
  }
  const dir = fs.mkdtempSync(join(os.tmpdir(), 'speedloop-'));
  try {
    fs.cpSync(template, dir, { recursive: true });
    const write = (rel, data) => {
      fs.mkdirSync(dirname(join(dir, rel)), { recursive: true });
      fs.writeFileSync(join(dir, rel), JSON.stringify(data));
    };
    const runs = ['runs/0001', 'runs/0002', 'runs/0003', 'runs/0004'];
    runs.forEach((run, i) => {
      const k = 1 + 0.01 * (i % 3);
      const turns = [0, 1, 2].map(() => [{ ttft_s: 5 * k }, { ttft_s: k }, { ttft_s: k }]);
      write(`${run}/raw/meta.json`, { status: 'OK' });
      write(`${run}/raw/gate.json`, { tf_top1: 0.99, tf_dlp: 0.01, dec_dlp: 0.01, dec_prefix: 0.9, reliability_ok: 5, reliability_total: 5, empty_outputs: 0, looping_outputs: 0 });
      write(`${run}/raw/bw_before.json`, { copy_gbps: 200 });
      write(`${run}/raw/bw_after.json`, { copy_gbps: 200 });
      write(`${run}/raw/speed.json`, {
        short: { decode_tps_geo: 50 * k }, long: { decode_tps: 40 * k },
        prefill: { prefill_tps_geo: 3000 * k, '64k': { prefill_tps: 1 }, '128k': { ttft_s: 1 } },
        parallel: { aggregate_tps: 90 * k }, parallel2: { aggregate_tps: 70 * k },
        replay: { wall_s: 100 * k, ttft_p50_s: 1, version: 8, warm_hit_rate: 0.9, turns },
      });
    });
    write('runs/0004/invariants.json', { ok: true, problems: [] });
    write('state/champion.json', { runs: runs.slice(0, 3) });
    const lock = spawnSync(python, ['scripts/bench/aa.py', ...runs.slice(0, 3)], { cwd: dir, encoding: 'utf8' });
    assert.equal(lock.status, 0, lock.stderr);
    const verdict = spawnSync(python, ['scripts/bench/verdict.py', runs[3]], { cwd: dir, encoding: 'utf8' });
    assert.equal(verdict.status, 0, verdict.stderr);
    assert.match(verdict.stdout, /^VERDICT (KEEP|REJECT|ARCHIVE)/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// Edge runs the loop meets in practice: a perfect warm hit rate in the baseline, a candidate whose hit-rate
// counters are missing and whose warm turns all failed, and a champion set that mixes replay versions.
test('sigmaspeedloop aa.py and verdict.py survive missing or perfect cache numbers and mixed replay versions', (t) => {
  const python = findPython();
  if (!python) {
    t.skip('python 3.8+ not found');
    return;
  }
  const dir = fs.mkdtempSync(join(os.tmpdir(), 'speedloop-edge-'));
  try {
    fs.cpSync(template, dir, { recursive: true });
    const write = (rel, data) => {
      fs.mkdirSync(dirname(join(dir, rel)), { recursive: true });
      fs.writeFileSync(join(dir, rel), JSON.stringify(data));
    };
    const run = (name, { hit = 0.9, warm = 1, version = 8, wall = 100 } = {}) => {
      const turns = [0, 1, 2].map(() => [{ ttft_s: 5 }, { ttft_s: warm }, { ttft_s: warm }]);
      write(`${name}/raw/meta.json`, { status: 'OK' });
      write(`${name}/raw/gate.json`, { tf_top1: 0.99, tf_dlp: 0.01, dec_dlp: 0.01, dec_prefix: 0.9, reliability_ok: 5, reliability_total: 5, empty_outputs: 0, looping_outputs: 0 });
      write(`${name}/raw/bw_before.json`, { copy_gbps: 200 });
      write(`${name}/raw/bw_after.json`, { copy_gbps: 200 });
      write(`${name}/raw/speed.json`, {
        short: { decode_tps_geo: 50 }, long: { decode_tps: 40 },
        prefill: { prefill_tps_geo: 3000, '64k': { prefill_tps: 1 }, '128k': { ttft_s: 1 } },
        parallel: { aggregate_tps: 90 }, parallel2: { aggregate_tps: 70 },
        replay: { wall_s: wall, ttft_p50_s: 1, version, warm_hit_rate: hit, turns },
      });
    };
    run('runs/0001', { hit: 0.9 });
    run('runs/0002', { hit: 1.0 });
    run('runs/0003', { hit: 0.95 });
    run('runs/0004', { hit: 0.9, version: 6, wall: 10 });
    run('runs/0005', { hit: null, warm: null });
    write('runs/0005/invariants.json', { ok: true, problems: [] });
    const lock = spawnSync(python, ['scripts/bench/aa.py', 'runs/0001', 'runs/0002', 'runs/0003'], { cwd: dir, encoding: 'utf8' });
    assert.equal(lock.status, 0, lock.stderr);
    write('state/champion.json', { runs: ['runs/0001', 'runs/0002', 'runs/0003', 'runs/0004'] });
    const verdict = spawnSync(python, ['scripts/bench/verdict.py', 'runs/0005'], { cwd: dir, encoding: 'utf8' });
    assert.equal(verdict.status, 0, verdict.stderr);
    const out = JSON.parse(fs.readFileSync(join(dir, 'runs', '0005', 'verdict.json'), 'utf8'));
    assert.ok(!('miss' in out.ratios), 'a missing hit rate must drop the miss component, not count as a 100 % miss');
    assert.ok(!('warm' in out.ratios), 'warm turns without a first-token time must drop the warm component');
    assert.equal(out.ratios.replay, 1, 'the champion replay median must use only runs of the newest replay version');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
